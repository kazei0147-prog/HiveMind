"""
梦境机制 - HiveMind 离线蒸馏 + 反事实杂交

系统在低负载或检测到"僵化"时，进入离线阶段：
- 蒸馏：将大量原始数据压缩为抽象规则
- 反事实杂交：将历史失败方案与当前主流方案强行组合，测试是否产生意外增益
"""

import random
import logging
from typing import List, Optional

from .consensus import ConsensusTracker
from .submodule import SubModule
from .config import HiveMindConfig

logger = logging.getLogger("hivemind.dream")


class DreamMechanism:
    """
    梦境机制（简化版 MVP）。

    触发条件：系统僵化检测（共识变化率低于阈值）
    执行内容：
    1. 蒸馏：从模块历史数据中提取模式规则
    2. 反事实杂交：组合失败方案与当前方案，测试增益
    成本：低功耗推演（成本比例 dream_cost_ratio）
    """

    def __init__(self, config: HiveMindConfig, consensus: ConsensusTracker):
        self.config = config
        self.consensus = consensus
        self.dream_count: int = 0
        self.dream_log: List[dict] = []
        self.distilled_rules: List[str] = []     # 蒸馏出的规则

    def should_trigger(self) -> bool:
        """检测是否应触发梦境（系统僵化）"""
        return self.consensus.is_stagnant()

    def execute(self, modules: List[SubModule], round_num: int) -> dict:
        """
        执行一轮梦境推演。
        返回梦境结果摘要。
        """
        self.dream_count += 1
        dream_cost = self.config.inference_cost * self.config.dream_cost_ratio

        # ── 1. 蒸馏 ──
        distilled = self._distill(modules, dream_cost)

        # ── 2. 反事实杂交 ──
        hybrids = self._counterfactual_hybridize(modules, dream_cost)

        result = {
            "round": round_num,
            "dream_id": self.dream_count,
            "distilled_rules": distilled,
            "hybrids": hybrids,
        }
        self.dream_log.append(result)

        logger.info(
            f"梦境 round={round_num}, "
            f"蒸馏规则={len(distilled)}, "
            f"杂交方案={len(hybrids)}"
        )
        return result

    def _distill(self, modules: List[SubModule], dream_cost: float) -> List[str]:
        """
        蒸馏：从模块历史数据中提取模式规则。
        模块以低功耗方式回顾自己的历史，提取统计特征。
        """
        rules = []
        for m in modules:
            if not m.alive or len(m.history) < 3:
                continue

            # 消耗低功耗能量（带地板保护）
            floor = m.config.energy_floor
            if m.wallet.can_afford(dream_cost, floor=floor):
                m.wallet.spend(dream_cost, reason=f"梦境蒸馏", floor=floor)

                # 提取统计特征
                avg = sum(m.history) / len(m.history)
                trend = m.history[-1] - m.history[0] if len(m.history) > 1 else 0
                volatility = max(m.history) - min(m.history)

                rule = (
                    f"[{m.module_id}] avg={avg:.2f}, "
                    f"trend={trend:.2f}, volatility={volatility:.2f}"
                )
                rules.append(rule)
                self.distilled_rules.append(rule)

        return rules

    def _counterfactual_hybridize(
        self, modules: List[SubModule], dream_cost: float
    ) -> List[dict]:
        """
        反事实杂交：将不同模块的历史方案强行组合。
        如果组合结果产生意外增益（比当前共识更接近目标），记录下来。
        """
        hybrids = []
        alive_modules = [m for m in modules if m.alive and len(m.history) >= 2]

        for i in range(len(alive_modules)):
            if random.random() > self.config.counterfactual_mix_prob:
                continue

            m1 = alive_modules[i]
            # 随机选取另一个模块做杂交
            m2 = random.choice(alive_modules) if alive_modules else None
            if m2 is None or m2.module_id == m1.module_id:
                continue

            # 消耗低功耗能量（带地板保护）
            floor = m1.config.energy_floor
            if m1.wallet.can_afford(dream_cost, floor=floor):
                m1.wallet.spend(dream_cost, reason="梦境杂交", floor=floor)

            # 杂交：取两个模块的历史值做加权混合
            weight = random.uniform(0.3, 0.7)
            hybrid_value = weight * m1.history[-1] + (1 - weight) * m2.history[-1]

            # 检查增益：与当前共识对比
            # 在仿真中，增益 = 更接近目标值
            current_dist = abs(self.consensus.current.value - self.config.target_value)
            hybrid_dist = abs(hybrid_value - self.config.target_value)
            gain = current_dist - hybrid_dist  # 正数=更接近目标=有增益

            hybrid = {
                "module1": m1.module_id,
                "module2": m2.module_id,
                "weight": weight,
                "hybrid_value": hybrid_value,
                "gain": gain,
                "useful": gain > 0,
            }
            hybrids.append(hybrid)

            # 如果杂交有增益，将杂交值注入共识作为扰动
            if gain > 0:
                perturbation_rate = 0.05  # 小幅度扰动
                self.consensus.current.value += perturbation_rate * (hybrid_value - self.consensus.current.value)
                logger.info(f"反事实杂交注入扰动: hybrid={hybrid_value:.2f}, gain={gain:.4f}")

        return hybrids

    def summary(self) -> dict:
        """返回梦境机制状态摘要"""
        return {
            "dream_count": self.dream_count,
            "distilled_rules_count": len(self.distilled_rules),
            "last_dream": self.dream_log[-1] if self.dream_log else None,
        }
