"""
共识追踪器 - HiveMind 共识管理

跟踪当前共识值和置信度。
置信度随时间衰减，触发保底机制。
"""

from dataclasses import dataclass, field
from typing import List, Optional
import random
import logging

from .config import HiveMindConfig

logger = logging.getLogger("hivemind.consensus")


@dataclass
class ConsensusState:
    """共识状态快照"""
    value: float = 0.0           # 当前共识值
    confidence: float = 1.0      # 当前置信度 [0, 1]
    round_number: int = 0        # 形成该共识的轮次
    contributors: List[str] = field(default_factory=list)  # 贡献模块列表
    change_rate: float = 0.0     # 共识变化率（用于僵化检测）


class ConsensusTracker:
    """
    共识追踪与置信度衰减管理。

    核心逻辑：
    1. 每轮收集模块提议，加权汇总形成共识
    2. 共识置信度每轮按 decay_rate 衰减
    3. 低置信度触发保底机制
    4. 低优先级内容定期被重新激活
    """

    def __init__(self, config: HiveMindConfig, initial_value: float = 0.0):
        self.config = config
        self.current = ConsensusState(value=initial_value, confidence=1.0)
        self.history: List[ConsensusState] = []
        self.shadow_value: Optional[float] = None     # 影子候选值
        self.shadow_rounds_active: int = 0            # 影子候选已活跃轮数
        self.reactivated_items: List[float] = []       # 被重新激活的历史共识

    def update(self, proposals: List, round_num: int) -> ConsensusState:
        """
        基于模块提议更新共识。
        加权平均：置信度高的模块权重更大。
        """
        if not proposals:
            # 无提议时，共识不变但置信度继续衰减
            self._decay_confidence()
            self.current.round_number = round_num
            self.history.append(self._snapshot())
            return self.current

        # 加权平均
        total_weight = 0.0
        weighted_sum = 0.0
        contributors = []

        for p in proposals:
            weight = p.confidence
            weighted_sum += p.value * weight
            total_weight += weight
            contributors.append(p.module_id)

        new_value = weighted_sum / total_weight if total_weight > 0 else self.current.value

        # 计算变化率
        change_rate = abs(new_value - self.current.value) / max(abs(self.current.value), 1.0)

        # 置信度：基于提议覆盖度和模块置信度
        new_confidence = self._compute_confidence(proposals)

        self.current = ConsensusState(
            value=new_value,
            confidence=new_confidence,
            round_number=round_num,
            contributors=contributors,
            change_rate=change_rate,
        )
        self.history.append(self._snapshot())
        return self.current

    def _compute_confidence(self, proposals: List) -> float:
        """基于提议质量计算新置信度"""
        if not proposals:
            return self.current.confidence * (1 - self.config.confidence_decay_rate)

        # 基础置信度 = 模块平均置信度
        avg_conf = sum(p.confidence for p in proposals) / len(proposals)

        # 多样性加分：如果来自不同模块，置信度更高
        unique_modules = len(set(p.module_id for p in proposals))
        diversity_bonus = 0.1 * min(unique_modules, 3)

        # 与目标值的接近度加分（仅仿真用）
        # 注意：真实系统不知道目标值，这里仅用于观测
        return min(avg_conf + diversity_bonus, 1.0)

    def _decay_confidence(self) -> None:
        """置信度时间衰减"""
        self.current.confidence *= (1 - self.config.confidence_decay_rate)
        self.current.confidence = max(self.current.confidence, 0.01)  # 保底最低值

    def should_fallback(self) -> bool:
        """判断是否需要触发保底机制"""
        return self.current.confidence < self.config.fallback_threshold

    def introduce_shadow(self, shadow_value: float) -> None:
        """引入影子候选"""
        self.shadow_value = shadow_value
        self.shadow_rounds_active = 0
        logger.info(f"影子候选引入, value={shadow_value:.2f}, 当前共识={self.current.value:.2f}")

    def tick_shadow(self) -> Optional[float]:
        """
        影子候选推演一轮。
        返回值表示影子是否优于主流：正数=影子更优，负数=主流更优，None=影子未活跃。
        """
        if self.shadow_value is None:
            return None

        self.shadow_rounds_active += 1

        # 影子候选轻微演化（添加微扰）
        perturbation = (self.shadow_value - self.current.value) * 0.1
        self.shadow_value += perturbation * 0.5

        # 比较影子与主流
        # 在仿真中，影子更接近目标值则更优
        advantage = self.shadow_value - self.current.value

        if self.shadow_rounds_active >= self.config.shadow_parallel_rounds:
            logger.info(f"影子候选推演完成, {self.shadow_rounds_active}轮, advantage={advantage:.4f}")
            return advantage

        return None  # 还在并行推演中

    def resolve_shadow(self, shadow_advantage: float) -> None:
        """
        影子候选推演结束后决定：
        - 影子持续更优 → 线性插值平滑过渡
        - 主流仍优 → 影子退出
        """
        if shadow_advantage is not None:
            # 简化判定：如果影子偏离方向更接近"修正方向"（在仿真中，接近目标）
            # 这里用简单的距离比较
            if abs(shadow_advantage) < abs(self.current.value - self.config.target_value) * 0.5:
                # 影子更接近目标，开始插值过渡
                rate = self.config.interpolation_rate
                self.current.value = self.current.value + rate * (self.shadow_value - self.current.value)
                self.current.confidence = 0.6  # 过渡期置信度重置
                logger.info(f"影子过渡: 共识={self.current.value:.2f}, rate={rate}")
            else:
                logger.info(f"主流仍优, 影子退出")

        # 清除影子状态
        self.shadow_value = None
        self.shadow_rounds_active = 0

    def try_reactivation(self, round_num: int) -> Optional[float]:
        """
        低优先级内容重新激活机制。
        每隔固定轮数或随机采样，将历史共识重新唤醒参与推演。
        """
        if round_num % self.config.reactivation_interval == 0:
            if self.history:
                old_consensus = random.choice(self.history)
                self.reactivated_items.append(old_consensus.value)
                logger.debug(f"重新激活历史共识 round={round_num}, value={old_consensus.value:.2f}")
                return old_consensus.value

        # 随机采样重新激活
        if random.random() < self.config.random_reactivation_prob and self.history:
            old_consensus = random.choice(self.history)
            return old_consensus.value

        return None

    def is_stagnant(self) -> bool:
        """检测系统是否僵化（变化率过低）"""
        return self.current.change_rate < self.config.dream_trigger_threshold

    def _snapshot(self) -> ConsensusState:
        """返回当前共识快照"""
        return ConsensusState(
            value=self.current.value,
            confidence=self.current.confidence,
            round_number=self.current.round_number,
            contributors=self.current.contributors.copy(),
            change_rate=self.current.change_rate,
        )

    def summary(self) -> dict:
        """返回追踪器状态摘要"""
        return {
            "current_value": self.current.value,
            "current_confidence": self.current.confidence,
            "change_rate": self.current.change_rate,
            "shadow_active": self.shadow_value is not None,
            "shadow_value": self.shadow_value,
            "history_length": len(self.history),
        }
