"""
保底控制器 - HiveMind 渐进扰动 + 影子共识

当主流共识置信度衰减至阈值以下：
- 不强制替换，而是引入"影子候选"
- 影子候选与主流并行推演若干轮
- 如果影子持续更优，则通过线性插值完成平滑过渡
"""

import logging
import random

from .consensus import ConsensusTracker
from .config import HiveMindConfig

logger = logging.getLogger("hivemind.fallback")


class FallbackController:
    """
    保底控制器。

    核心逻辑：
    1. 监控共识置信度，低于阈值时触发保底
    2. 生成影子候选（基于历史数据、扰动、或外部参考）
    3. 影子候选与主流并行推演 shadow_parallel_rounds 轮
    4. 根据并行推演结果决定：过渡 or 保留主流
    """

    def __init__(self, config: HiveMindConfig, consensus: ConsensusTracker):
        self.config = config
        self.consensus = consensus
        self.fallback_events: list = []       # 保底触发事件记录
        self.shadow_state: str = "idle"       # idle / active / resolving

    def check_and_trigger(self, round_num: int) -> bool:
        """
        每轮检查是否需要触发保底。
        返回 True 表示触发了保底。
        """
        if self.shadow_state == "active":
            # 影子候选已在活跃中，继续推演
            return self._advance_shadow(round_num)

        if self.consensus.should_fallback():
            # 触发保底
            shadow_value = self._generate_shadow()
            self.consensus.introduce_shadow(shadow_value)
            self.shadow_state = "active"
            self.fallback_events.append({
                "round": round_num,
                "consensus_before": self.consensus.current.value,
                "confidence_before": self.consensus.current.confidence,
                "shadow_value": shadow_value,
            })
            logger.info(
                f"保底触发 round={round_num}, "
                f"consensus={self.consensus.current.value:.2f}, "
                f"confidence={self.consensus.current.confidence:.4f}, "
                f"shadow={shadow_value:.2f}"
            )
            return True

        return False

    def _generate_shadow(self) -> float:
        """
        生成影子候选值。
        策略：基于历史共识 + 渐进扰动 + 反方向偏移。
        """
        current = self.consensus.current.value

        # 策略1：从历史中寻找更好的共识值
        if self.consensus.history:
            best_historical = max(
                self.consensus.history,
                key=lambda s: s.confidence
            )
            # 历史最优值作为影子基础
            shadow_base = best_historical.value
        else:
            shadow_base = current

        # 策略2：施加渐进扰动（轻微偏离当前方向）
        perturbation = random.gauss(0, abs(current) * 0.1 + 1.0)

        # 策略3：反方向偏移（尝试修正可能的主流偏移）
        # 假设偏移方向是共识偏离目标的方向
        # 简化版：取历史均值作为修正方向
        if self.consensus.history and len(self.consensus.history) >= 3:
            recent_avg = sum(s.value for s in self.consensus.history[-3:]) / 3
            correction = -(current - recent_avg) * 0.3
        else:
            correction = 0

        shadow_value = shadow_base + perturbation + correction
        return shadow_value

    def _advance_shadow(self, round_num: int) -> bool:
        """推进影子候选推演"""
        result = self.consensus.tick_shadow()

        if result is not None:
            # 影子推演结束，需要裁决
            self.consensus.resolve_shadow(result)
            self.shadow_state = "idle"

            event = self.fallback_events[-1] if self.fallback_events else {}
            event["resolved_round"] = round_num
            event["result"] = result
            logger.info(f"影子候选裁决完成, result={result:.4f}")
            return True

        return True  # 影子仍在推演中

    def summary(self) -> dict:
        """返回保底控制器状态摘要"""
        return {
            "fallback_count": len(self.fallback_events),
            "shadow_state": self.shadow_state,
            "last_fallback": self.fallback_events[-1] if self.fallback_events else None,
        }
