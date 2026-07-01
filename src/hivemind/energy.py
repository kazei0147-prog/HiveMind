"""
能量钱包 - HiveMind 能量经济学核心

每个子模块持有独立能量余额。
支出：推演、通信、策略更新。
收入：被母模块采纳获得奖励。
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("hivemind.energy")


@dataclass
class EnergyWallet:
    """子模块能量钱包"""

    balance: float = 100.0
    total_earned: float = 0.0
    total_spent: float = 0.0
    loan_balance: float = 0.0          # 创新借贷余额
    loan_rounds_remaining: int = 0     # 借贷剩余轮数
    loan_max: float = 50.0             # 借贷上限

    def can_afford(self, cost: float, floor: float = 0.0) -> bool:
        """检查余额是否足够支付（且不低于地板值）"""
        # 地板保护：支付后余额不得低于 floor
        available_after_cost = self.balance - cost
        if available_after_cost >= floor:
            return True
        # 如果余额不够但有借贷空间
        if self.balance + self.loan_balance - cost >= floor:
            return True
        return False

    def spend(self, cost: float, reason: str = "", floor: float = 0.0) -> bool:
        """
        消耗能量。如果余额不足但有借贷额度，自动触发借贷。
        floor: 能量地板值，余额支付后不得低于此值（防完全破产）。
        返回 True 表示成功支付，False 表示完全无法支付。
        """
        # 地板保护：如果支付后余额低于 floor，不允许支付
        if self.balance >= cost and (self.balance - cost) >= floor:
            self.balance -= cost
            self.total_spent += cost
            logger.debug(f"能量支出 {cost:.1f} ({reason}), 余额 {self.balance:.1f}")
            return True

        # 尝试借贷补足
        shortfall = cost - self.balance + floor  # 需要补足到 floor 以上
        if self.loan_balance < self.loan_max and shortfall <= (self.loan_max - self.loan_balance):
            # 先用掉现有余额（但保留 floor）
            usable_balance = self.balance - floor
            if usable_balance > 0:
                self.total_spent += usable_balance
                self.balance = floor
                remaining_cost = cost - usable_balance
            else:
                remaining_cost = cost
            # 借贷补足剩余部分
            self.loan_balance += remaining_cost
            self.total_spent += remaining_cost
            self.loan_rounds_remaining = 5
            logger.info(f"触发创新借贷 {remaining_cost:.1f}, 借贷余额 {self.loan_balance:.1f}, 余额底线={floor:.1f}")
            return True

        # 完全无法支付
        logger.warning(f"能量不足! 需要 {cost:.1f}, 余额 {self.balance:.1f}, 借贷 {self.loan_balance:.1f}")
        return False

    def earn(self, reward: float, reason: str = "") -> None:
        """获得能量奖励"""
        self.balance += reward
        self.total_earned += reward
        logger.debug(f"能量收入 {reward:.1f} ({reason}), 余额 {self.balance:.1f}")

        # 如果有借贷，优先偿还
        if self.loan_balance > 0 and self.loan_rounds_remaining > 0:
            repayment = min(reward * 0.5, self.loan_balance)  # 50%奖励用于还贷
            self.loan_balance -= repayment
            self.loan_rounds_remaining -= 1
            if self.loan_balance <= 0:
                self.loan_balance = 0
                self.loan_rounds_remaining = 0
                logger.info(f"借贷已全部偿还")

    def tick_loan(self) -> bool:
        """
        每轮调用，递减借贷轮数。
        如果借贷到期未偿还，返回 True 表示需要强制剪枝。
        """
        if self.loan_rounds_remaining > 0:
            self.loan_rounds_remaining -= 1
            if self.loan_rounds_remaining <= 0 and self.loan_balance > 0:
                logger.warning(f"借贷到期未偿还 {self.loan_balance:.1f}, 标记强制剪枝")
                return True  # 需要剪枝
        return False

    def is_dead(self, threshold: float = 0.0) -> bool:
        """检查模块是否已死亡（能量耗尽）"""
        return self.balance <= threshold and self.loan_balance <= threshold

    def snapshot(self) -> dict:
        """返回钱包状态快照"""
        return {
            "balance": self.balance,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "loan_balance": self.loan_balance,
            "loan_rounds_remaining": self.loan_rounds_remaining,
        }
