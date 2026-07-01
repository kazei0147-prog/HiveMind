"""
子模块 - HiveMind 认知节点种群

+1/-1 MVP: 激进型 (alpha, +1) + 反共识型 (gamma, -1)
每个模块自带能量钱包、认知偏见、推演能力。
"""

from dataclasses import dataclass
from typing import Optional, List
import random
import logging

from .energy import EnergyWallet
from .config import HiveMindConfig

logger = logging.getLogger("hivemind.submodule")


@dataclass
class Proposal:
    """子模块推演产出"""
    module_id: str
    value: float              # 提议值（对目标的估计）
    confidence: float         # 模块自身置信度 [0, 1]
    reasoning: str            # 简短推理说明
    energy_cost: float        # 本次推演消耗的能量
    round_number: int         # 产出轮次


class SubModule:
    """子模块基类"""

    def __init__(
        self,
        module_id: str,
        bias_type: str,
        wallet: EnergyWallet,
        config: HiveMindConfig,
    ):
        self.module_id = module_id
        self.bias_type = bias_type
        self.wallet = wallet
        self.config = config
        self.alive = True
        self.legacy_capsule: Optional[str] = None   # 临终胶囊
        self.history: List[float] = []               # 历史提议值
        self.adoption_count: int = 0                 # 被采纳次数
        self.total_rounds: int = 0                   # 参与推演总轮数
        self.last_proposal: Optional[Proposal] = None

    def observe(self, raw_data: float) -> float:
        """
        从原始数据中提取信息，施加模块偏见。
        不同模块对同一数据有不同的解读。
        """
        raise NotImplementedError("子类必须实现 observe()")

    def propose(self, observation: float, current_consensus: float, round_num: int) -> Optional[Proposal]:
        """
        基于观测和当前共识，生成提议。
        消耗能量。如果能量不足，返回 None。
        """
        if not self.alive:
            return None

        cost = self.config.inference_cost
        floor = self.config.energy_floor
        if not self.wallet.can_afford(cost, floor=floor):
            logger.warning(f"[{self.module_id}] 能量不足，无法推演 (floor={floor})")
            return None

        # 消耗能量（带地板保护）
        self.wallet.spend(cost, reason=f"推演 round={round_num}", floor=floor)

        # 施加偏见，生成提议值
        biased_estimate = self.observe(observation)
        self.total_rounds += 1

        # 置信度基于能量余额和自身特性
        confidence = self._compute_confidence()

        proposal = Proposal(
            module_id=self.module_id,
            value=biased_estimate,
            confidence=confidence,
            reasoning=f"{self.bias_type} 偏见推断, 基于 obs={observation:.2f}",
            energy_cost=cost,
            round_number=round_num,
        )
        self.last_proposal = proposal
        self.history.append(biased_estimate)
        return proposal

    def _compute_confidence(self) -> float:
        """计算模块自身置信度，与能量余额正相关"""
        base = 0.5
        energy_factor = min(self.wallet.balance / self.config.initial_module_energy, 1.0)
        return min(base + 0.3 * energy_factor, 1.0)

    def on_adopted(self, reward: float):
        """被采纳时回调：获得能量奖励"""
        self.wallet.earn(reward, reason="被采纳奖励")
        self.adoption_count += 1

    def on_rejected(self):
        """未被采纳时回调"""
        pass

    def generate_legacy_capsule(self) -> str:
        """
        临终协议：生成不超过1KB的遗产摘要。
        包含模块历史特征、核心观点、与主流共识的分歧。
        """
        if not self.history:
            return f"[{self.module_id}] 空模块, 无历史数据"

        avg_value = sum(self.history) / len(self.history)
        capsule = (
            f"[{self.module_id}/{self.bias_type}] "
            f"avg={avg_value:.2f}, rounds={self.total_rounds}, "
            f"adopted={self.adoption_count}, "
            f"earned={self.wallet.total_earned:.1f}, "
            f"spent={self.wallet.total_spent:.1f}"
        )
        # 确保不超过 capsule_max_size
        if len(capsule.encode('utf-8')) > self.config.capsule_max_size:
            capsule = capsule[:self.config.capsule_max_size]
        self.legacy_capsule = capsule
        logger.info(f"[{self.module_id}] 临终胶囊: {capsule}")
        return capsule

    def kill(self):
        """标记模块死亡"""
        self.alive = False
        self.generate_legacy_capsule()
        logger.info(f"[{self.module_id}] 已死亡, 胶囊已生成")


class AggressiveModule(SubModule):
    """
    激进型 (alpha, +1)
    偏好新数据和新信号，倾向于高估。
    特征：快速反应、大胆推断、容易被采纳但也容易偏移。
    """

    def __init__(self, config: HiveMindConfig):
        wallet = EnergyWallet(
            balance=config.initial_module_energy,
            loan_max=config.innovation_loan_max,
        )
        super().__init__(
            module_id="alpha_aggressive",
            bias_type="aggressive",
            wallet=wallet,
            config=config,
        )

    def observe(self, raw_data: float) -> float:
        """激进型：将观测数据乘以偏向系数，倾向高估"""
        # 施加正向偏见
        biased = raw_data * self.config.aggressive_bias
        # 加入少量随机扰动（激进型更愿意冒险）
        noise = random.gauss(0, self.config.observation_noise * 0.3)
        return biased + noise


class CounterConsensusModule(SubModule):
    """
    反共识型 (gamma, -1)
    主动关注异常值与少数派观点，倾向于逆主流而行。
    特征：纠正偏移、发现异常、但容易被忽视。
    """

    def __init__(self, config: HiveMindConfig):
        wallet = EnergyWallet(
            balance=config.initial_module_energy,
            loan_max=config.innovation_loan_max,
        )
        super().__init__(
            module_id="gamma_counter",
            bias_type="counter_consensus",
            wallet=wallet,
            config=config,
        )

    def observe(self, raw_data: float) -> float:
        """反共识型：偏离当前共识方向，主动寻找异常"""
        # 不直接处理原始数据，而是基于共识做反向偏移
        # 在propose中会使用current_consensus
        return raw_data  # 基础值不变，偏见在propose中施加

    def propose(self, observation: float, current_consensus: float, round_num: int) -> Optional[Proposal]:
        """
        反共识型提议：偏离当前共识方向。
        如果共识偏高了，就往低拉；偏低了就往高拉。
        """
        if not self.alive:
            return None

        cost = self.config.inference_cost
        if not self.wallet.can_afford(cost):
            return None

        self.wallet.spend(cost, reason=f"推演 round={round_num}")
        self.total_rounds += 1

        # 反共识偏见：将共识向观测方向反向拉回
        # 如果共识高于观测（共识偏高），就往下拉；低于观测就往上推
        drift = current_consensus - observation  # 共识偏离观测的方向
        counter_direction = -drift * self.config.counter_bias_strength  # 反向拉回
        biased_estimate = current_consensus + counter_direction

        # 加入少量随机性
        noise = random.gauss(0, self.config.observation_noise * 0.2)
        biased_estimate += noise

        confidence = self._compute_confidence()

        proposal = Proposal(
            module_id=self.module_id,
            value=biased_estimate,
            confidence=confidence,
            reasoning=f"反共识偏离, consensus={current_consensus:.2f}, counter_shift={counter_direction:.2f}",
            energy_cost=cost,
            round_number=round_num,
        )
        self.last_proposal = proposal
        self.history.append(biased_estimate)
        return proposal
