"""
临终协议 - HiveMind 遗忘权与认知化石管理

当子模块被判定为"认知化石"时：
- 系统强制其产出不超过1KB的"临终胶囊"（特征摘要）
- 胶囊与主流共识哈希池比对
- 若为异见，归档至考古索引；若为共识冗余，直接丢弃
- 原始数据逻辑删除，物理空间释放
"""

import logging
from typing import List, Optional

from .submodule import SubModule
from .consensus import ConsensusTracker
from .config import HiveMindConfig

logger = logging.getLogger("hivemind.death")


class DeathProtocol:
    """
    临终协议管理器。

    触发条件：
    1. 模块能量耗尽 → 立即触发
    2. 模块长期未被采纳 + 借贷到期 → 强制剪枝
    3. 知识条目超过 fossil_age_threshold 轮未更新 → 认知化石

    处理流程：
    1. 模块生成临终胶囊（≤1KB）
    2. 胶囊与主流共识比对
    3. 异见 → 归档至考古索引
    4. 共识冗余 → 丢弃
    """

    def __init__(self, config: HiveMindConfig, consensus: ConsensusTracker):
        self.config = config
        self.consensus = consensus
        self.archaeology_index: List[str] = []     # 考古索引（异见胶囊）
        self.discarded_count: int = 0              # 丢弃的冗余胶囊数
        self.death_events: List[dict] = []          # 死亡事件记录

    def check_modules(self, modules: List[SubModule], round_num: int) -> List[SubModule]:
        """
        检查所有模块，判断是否需要触发临终协议。
        返回本轮死亡的模块列表。
        """
        dead_modules = []

        for m in modules:
            if not m.alive:
                continue

            # 条件1：能量耗尽
            if m.wallet.is_dead(self.config.death_energy_threshold):
                logger.info(f"[{m.module_id}] 能量耗尽, 触发临终协议")
                self._execute_death(m, "energy_exhausted", round_num)
                dead_modules.append(m)
                continue

            # 条件2：借贷到期未偿还
            if m.wallet.tick_loan():
                logger.info(f"[{m.module_id}] 借贷到期未偿还, 触发强制剪枝")
                self._execute_death(m, "loan_expired", round_num)
                dead_modules.append(m)

        return dead_modules

    def _execute_death(self, module: SubModule, reason: str, round_num: int) -> None:
        """执行临终协议"""
        # 1. 生成临终胶囊
        capsule = module.generate_legacy_capsule()

        # 2. 胶囊与主流共识比对
        classification = self._classify_capsule(capsule, module)

        # 3. 分类处理
        if classification == "dissent":
            # 异见 → 归档至考古索引
            self.archaeology_index.append(capsule)
            logger.info(f"[{module.module_id}] 胶囊分类=异见, 已归档至考古索引")
        else:
            # 共识冗余 → 丢弃
            self.discarded_count += 1
            logger.info(f"[{module.module_id}] 胶囊分类=冗余, 已丢弃")

        # 4. 标记模块死亡
        module.kill()

        # 5. 记录事件
        self.death_events.append({
            "round": round_num,
            "module_id": module.module_id,
            "bias_type": module.bias_type,
            "reason": reason,
            "capsule": capsule,
            "classification": classification,
            "wallet_snapshot": module.wallet.snapshot(),
        })

    def _classify_capsule(self, capsule: str, module: SubModule) -> str:
        """
        将临终胶囊与主流共识比对，判断是异见还是冗余。

        简化版 MVP：
        - 如果模块历史均值与当前共识差距 > threshold → 异见
        - 否则 → 共识冗余
        """
        if not module.history:
            return "redundant"

        avg_module_value = sum(module.history) / len(module.history)
        consensus_value = self.consensus.current.value

        divergence = abs(avg_module_value - consensus_value)
        # 用相对偏差衡量
        relative_div = divergence / max(abs(consensus_value), 1.0)

        if relative_div > 0.2:  # 偏差超过20%视为异见
            return "dissent"
        return "redundant"

    def check_fossil_knowledge(self, modules: List[SubModule], round_num: int) -> List[str]:
        """
        检查知识条目是否成为"认知化石"。
        模块中超过 fossil_age_threshold 轮未更新的条目被标记。
        """
        fossils = []
        for m in modules:
            if not m.alive:
                continue
            if m.total_rounds > 0 and m.adoption_count == 0:
                # 从未被采纳的模块，如果存活轮数超过阈值
                if m.total_rounds > self.config.fossil_age_threshold:
                    fossils.append(f"{m.module_id}: 存活{m.total_rounds}轮但从未被采纳")
        return fossils

    def summary(self) -> dict:
        """返回临终协议状态摘要"""
        return {
            "total_deaths": len(self.death_events),
            "archaeology_count": len(self.archaeology_index),
            "discarded_count": self.discarded_count,
            "death_events": self.death_events[-3:] if self.death_events else [],
        }
