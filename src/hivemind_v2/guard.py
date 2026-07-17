"""
StabilityGuard — HiveMind 2.0 底层刹车

不参与学习，不修改信念，只读取状态并判断系统是否混乱。
核心原则: 区分"健康的 divergence"与"破坏性的 chaos"。

混乱的五个物理信号:
  1. 共识振幅扩大 (std 翻倍)
  2. 信任排序翻转 (spearman < 0.3)
  3. 信念背向而行 (μ 极差在增大)
  4. 误差连续上升 (EMA 持续 K 轮上行)
  5. 论证权重扁平化 (entropy > threshold)

关键保护: 如果偏离是由事后验证准确的 Learner 引起的，不算混乱。
"""
import math
import logging
from typing import List, Dict, Optional, Tuple
from collections import deque

logger = logging.getLogger("hivemind_v2.guard")

# ── 绝对不变量 ──
INVARIANTS = {
    "max_learners": 10,
    "min_confidence": 0.001,
    "max_learning_rate": 0.5,
    "debate_rounds_max": 5,
    "max_consecutive_chaos_rounds": 10,  # 连续混乱上限 → 硬冻结
}


class StabilityGuard:
    """底层守护者 — 只读，不参与学习回路"""

    def __init__(
        self,
        consensus_window: int = 20,
        error_window: int = 10,
        divergence_threshold: float = 2.0,      # std_ratio > 此值 → 信号1触发
        rank_stability_threshold: float = 0.3,   # spearman < 此值 → 信号2触发
        entropy_threshold: float = 0.8,          # normalized entropy > 此值 → 信号5触发
        error_rise_rounds: int = 5,              # 连续上升轮数 → 信号4触发
        chaos_persist_rounds: int = 3,           # 信号需持续多少轮才判定混乱
    ):
        self.consensus_window = consensus_window
        self.error_window = error_window
        self.divergence_threshold = divergence_threshold
        self.rank_stability_threshold = rank_stability_threshold
        self.entropy_threshold = entropy_threshold
        self.error_rise_rounds = error_rise_rounds
        self.chaos_persist_rounds = chaos_persist_rounds

        self.consensus_history: deque = deque(maxlen=consensus_window)
        self.error_history: deque = deque(maxlen=error_window)
        self.trust_rank_history: deque = deque(maxlen=10)
        self.chaos_signal_history: deque = deque(maxlen=chaos_persist_rounds)
        self.consecutive_chaos = 0

        self.last_stable_checkpoint: Optional[dict] = None
        self.checkpoint_round: int = 0

        # regime change cooldown: 检测到后 N 轮内继续覆盖相关信号
        self._regime_cooldown: int = 0
        self.REGIME_COOLDOWN_ROUNDS = 20

    # ──────────────── 核心: 识别信号来源 ────────────────

    def _classify_divergence(
        self, learners, trust
    ) -> Tuple[List[str], List[str]]:
        """
        区分"领路的偏离者"和"混乱的偏离者"。

        用近期表现 (最后10轮) 而非终身表现来判断。
        终身 track_record 在 regime change 后会滞后——
        一个之前不准但最近很准的 Learner 应该被识别为领路者。

        返回: (leaders, chaos_makers)
        """
        if not learners or len(learners) < 2:
            return [], []

        mus = [l.belief.mu for l in learners]
        consensus_mu = sum(mus) / len(mus)

        leaders = []
        chaos_makers = []

        for l in learners:
            deviation = abs(l.belief.mu - consensus_mu)
            if deviation < 1e-6:
                continue

            # ── 近期准确率 (最后 10 次验证) ──
            recent_n = min(10, len(l.error_history))
            if recent_n == 0:
                continue

            recent_errors = l.error_history[-recent_n:]
            recent_accuracy = sum(
                1 for e in recent_errors if abs(e) < 5.0  # CO2 scale: <5ppm = 准确
            ) / recent_n

            # 终身 track_record 做辅助参考
            lifetime_track = l.track_record()

            # 领路者: 近期准确率高 OR 终身 track_record 高 + 稳定偏离
            if recent_accuracy >= 0.6 or (lifetime_track > 0.6 and deviation > 0.5):
                leaders.append(l.learner_id)
            # 混乱者: 近期准确率低 AND 终身也低 + 偏离大
            elif recent_accuracy < 0.3 and lifetime_track < 0.4 and deviation > 1.0:
                chaos_makers.append(l.learner_id)

        return leaders, chaos_makers

    def _is_regime_change(self) -> bool:
        """
        检测 regime change: 用共识历史而非误差历史。
        共识值直接跳变 = 数据变了，误差增大是自然结果，不算混乱。
        """
        if len(self.consensus_history) < self.consensus_window:
            return False
        half = self.consensus_window // 2
        recent = list(self.consensus_history)[-half:]
        older = list(self.consensus_history)[:half]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        older_std = _std(older)
        if older_std < 0.01:
            older_std = 1.0
        # 共识均值偏移超过 3σ → regime change
        z_score = abs(recent_avg - older_avg) / older_std
        return z_score > 3.0

    # ──────────────── 五个信号检测 ────────────────

    def _signal_amplitude_growth(self) -> bool:
        """信号1: 共识振幅在扩大"""
        if len(self.consensus_history) < self.consensus_window:
            return False
        half = self.consensus_window // 2
        recent = list(self.consensus_history)[-half:]
        older = list(self.consensus_history)[:half]
        recent_std = _std(recent)
        older_std = _std(older)
        if older_std < 1e-8:
            return recent_std > 0.1
        return (recent_std / older_std) > self.divergence_threshold

    def _signal_trust_flip(self) -> bool:
        """信号2: 信任排序频繁翻转"""
        if len(self.trust_rank_history) < 3:
            return False
        # 比较最近两轮的排名相关性
        ranks = list(self.trust_rank_history)
        if len(ranks[-1]) < 2 or len(ranks[-2]) < 2:
            return False
        r = _spearman(ranks[-2], ranks[-1])
        return r is not None and r < self.rank_stability_threshold

    def _signal_belief_diverge(self, learners) -> bool:
        """信号3: 信念背向而行 (μ 极差在扩大)"""
        if len(learners) < 2:
            return False
        mus = [l.belief.mu for l in learners]
        current_range = max(mus) - min(mus)
        # 用 σ 的平均值做归一化
        avg_sigma = sum(l.belief.sigma for l in learners) / len(learners)
        if avg_sigma < 1e-8:
            return current_range > 2.0
        return (current_range / avg_sigma) > 3.0

    def _signal_error_rise(self) -> bool:
        """信号4: 误差连续上升"""
        if len(self.error_history) < self.error_rise_rounds:
            return False
        recent = list(self.error_history)[-self.error_rise_rounds:]
        # 检查是否连续上升
        for i in range(1, len(recent)):
            if recent[i] <= recent[i - 1]:
                return False
        return True

    def _signal_entropy_flat(self, learners, trust) -> bool:
        """
        信号5: 信任权重扁平化 (没人有说服力)

        关键区分:
        - 健康平权: 所有人都准确 → 熵虽高但 trust 值也高 → 不算混乱
        - 病态平权: 没有人准确 → 熵高且 trust 值低 → 混乱
        """
        if not learners:
            return False
        weights = [max(0.001, trust.get(l.learner_id)) for l in learners]
        total = sum(weights)
        if total < 1e-8:
            return True
        probs = [w / total for w in weights]
        entropy = -sum(p * math.log(p + 1e-12) for p in probs)
        max_entropy = math.log(len(learners))
        normalized = entropy / max_entropy if max_entropy > 0 else 0

        if normalized <= self.entropy_threshold:
            return False  # 有权重差异，正常

        # 熵高: 检查平均信任值
        avg_trust = sum(weights) / len(weights)
        # 如果平均信任 > 0.7，说明"大家都很准所以平权"——这不是混乱
        if avg_trust > 0.7:
            return False

        # 平均信任低 + 熵高 = 没有人能说服别人 = 真正的混乱
        return True

    # ──────────────── 主检查入口 ────────────────

    def check(
        self,
        learners,
        trust,
        consensus_value: float,
        current_error: float,
    ) -> dict:
        """
        返回:
        {
            "status": "stable" | "warning" | "chaos",
            "signals": [...],
            "leaders": [...],         # 领路的偏离者 (不算混乱)
            "chaos_makers": [...],    # 真正的混乱来源
            "interventions": [...],   # 建议的干预措施
            "overridden": bool,       # 是否有信号被 leader 覆盖
        }
        """
        self.consensus_history.append(consensus_value)
        self.error_history.append(current_error)

        # 保存信任排名
        rank = trust.rank() if hasattr(trust, 'rank') else []
        self.trust_rank_history.append(rank)

        # 分类偏离者
        leaders, chaos_makers = self._classify_divergence(learners, trust)

        # 扫描五个信号
        raw_signals = []
        if self._signal_amplitude_growth():
            raw_signals.append("amplitude_growth")
        if self._signal_trust_flip():
            raw_signals.append("trust_flip")
        if self._signal_belief_diverge(learners):
            raw_signals.append("belief_diverge")
        if self._signal_error_rise():
            raw_signals.append("error_rise")
        if self._signal_entropy_flat(learners, trust):
            raw_signals.append("entropy_flat")

        # ── 关键保护1: regime change 检测 ──
        # cooldown 期间不重复检测，直接继续覆盖
        if self._regime_cooldown > 0:
            self._regime_cooldown -= 1
            regime_active = True
        else:
            is_regime = self._is_regime_change()
            if is_regime:
                self._regime_cooldown = self.REGIME_COOLDOWN_ROUNDS
                regime_active = True
            else:
                regime_active = False

        regime_overrides = []
        if regime_active:
            for sig in raw_signals:
                if sig in ("error_rise", "amplitude_growth"):
                    regime_overrides.append(sig)

        # ── 关键保护2: 领路者保护 ──
        # 如果有领路者存在，与"偏离"相关的信号可能是健康的
        overridden = list(regime_overrides)
        effective_signals = []
        for sig in raw_signals:
            if sig in regime_overrides:
                continue
            if leaders and sig in ("amplitude_growth", "belief_diverge"):
                overridden.append(sig)
                continue
            effective_signals.append(sig)

        # 判定状态
        if len(effective_signals) == 0:
            status = "stable"
            interventions = []
            self.chaos_signal_history.append(0)
        elif len(effective_signals) <= 1:
            status = "warning"
            interventions = self._warning_interventions(effective_signals)
            self.chaos_signal_history.append(0)
        else:
            # 需要持久化验证
            self.chaos_signal_history.append(len(effective_signals))
            recent_chaos = list(self.chaos_signal_history)
            persistent = all(c >= 2 for c in recent_chaos[-self.chaos_persist_rounds:])

            if persistent:
                status = "chaos"
                interventions = self._chaos_interventions(
                    effective_signals, chaos_makers, learners, trust
                )
                self.consecutive_chaos += 1
            else:
                status = "warning"
                interventions = self._warning_interventions(effective_signals)

        # 回稳时重置
        if status == "stable":
            self.consecutive_chaos = 0

        result = {
            "status": status,
            "signals": raw_signals,
            "effective_signals": effective_signals,
            "overridden": overridden,
            "leaders": leaders,
            "chaos_makers": chaos_makers,
            "interventions": interventions,
            "consecutive_chaos": self.consecutive_chaos,
        }

        if overridden:
            logger.info(
                f"Guard: {len(overridden)} 个信号被领路者覆盖 (leaders={leaders}), "
                f"有效信号={len(effective_signals)}"
            )

        if status == "chaos":
            logger.warning(
                f"Guard: CHAOS detected — signals={effective_signals}, "
                f"chaos_makers={chaos_makers}, consecutive={self.consecutive_chaos}"
            )

        return result

    # ──────────────── 干预措施 ────────────────

    def _warning_interventions(self, signals: List[str]) -> List[dict]:
        """黄色: 减缓但不暂停"""
        interventions = []
        if "amplitude_growth" in signals or "belief_diverge" in signals:
            interventions.append({
                "action": "dampen_learning",
                "params": {"learning_rate_scale": 0.5},
                "reason": "共识振幅或信念发散增大，减半学习率",
            })
        if "trust_flip" in signals:
            interventions.append({
                "action": "trust_smoothing",
                "params": {"ema_alpha": 0.3},
                "reason": "信任频繁翻转，对信任值做指数平滑",
            })
        return interventions

    def _chaos_interventions(
        self, signals, chaos_makers, learners, trust
    ) -> List[dict]:
        """红色: 冻结 + 可能回滚"""
        interventions = []

        # 如果有明确的混乱制造者，隔离它们
        for cm in chaos_makers:
            interventions.append({
                "action": "isolate_learner",
                "target": cm,
                "reason": f"Learner {cm} 被识别为混乱来源，其提案权重降为 0.1",
            })

        # 冻结所有学习
        interventions.append({
            "action": "freeze_learning",
            "reason": "暂停所有信念更新",
        })

        # 信任回滚到上一个稳定 checkpoint
        interventions.append({
            "action": "trust_rollback",
            "reason": "回滚信任到最近稳定快照",
        })

        # 硬冻结 (连续混乱)
        if self.consecutive_chaos >= INVARIANTS["max_consecutive_chaos_rounds"]:
            interventions.append({
                "action": "hard_freeze",
                "reason": (
                    f"连续 {self.consecutive_chaos} 轮混乱，"
                    f"触发硬冻结——回滚到 checkpoint round={self.checkpoint_round}，"
                    f"用简单平均代偿"
                ),
            })

        return interventions

    # ──────────────── Checkpoint ────────────────

    def save_checkpoint(self, learners, trust) -> dict:
        """保存当前稳定状态"""
        from .dream import DreamStore
        store = DreamStore()
        state = store.save(learners, trust)
        self.last_stable_checkpoint = state
        self.checkpoint_round = max(
            l.total_rounds for l in learners
        ) if learners else 0
        return state

    def load_checkpoint(self):
        """返回上一个稳定 checkpoint"""
        return self.last_stable_checkpoint


# ── 工具函数 ──

def _std(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))


def _spearman(rank_a, rank_b):
    """计算两个排名的 Spearman 秩相关系数"""
    # 取交集
    common = set(rank_a) & set(rank_b)
    if len(common) < 2:
        return None
    a = [rank_a.index(x) for x in common]
    b = [rank_b.index(x) for x in common]
    n = len(a)
    d2 = sum((ai - bi) ** 2 for ai, bi in zip(a, b))
    r = 1 - (6 * d2) / (n * (n**2 - 1)) if n > 1 else 1.0
    return max(-1.0, min(1.0, r))
