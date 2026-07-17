"""
调度器 - HiveMind 2.3 主循环

v2.3 重构:
- 母模块升级为决策者 (MotherMind) — 综合 Learner 推理做出判断
- Guard 降级为纯架构保护 — 不再抑制认知过程
- 讨论流程: 提案 → 母模块深思 → 决策 → 反馈
"""
import random
import logging
from typing import List, Optional
from .learner import Learner
from .trust import TrustEngine
from .mother import MotherMind, Decision
from .guard import StabilityGuard

logger = logging.getLogger("hivemind_v2.orchestrator")


PRESET_PERSONAS = [
    {"name": "L1_optimist",    "mu": +3.0, "sigma": 8.0,  "window": 5,  "hint": "天生乐观"},
    {"name": "L2_pessimist",   "mu": -3.0, "sigma": 8.0,  "window": 5,  "hint": "天生悲观"},
    {"name": "L3_skeptic",     "mu":  0.0, "sigma": 15.0, "window": 10, "hint": "高度不确定，爱怀疑"},
    {"name": "L4_stubborn",    "mu":  0.0, "sigma": 3.0,  "window": 3,  "hint": "很自信，学得慢"},
    {"name": "L5_adaptable",   "mu":  0.0, "sigma": 10.0, "window": 12, "hint": "灵活，窗口大"},
]


class HiveMindV2:
    """HiveMind 2.3 — 母模块是决策者，子模块是大脑"""

    def __init__(
        self,
        n_learners: int = 5,
        warmup_rounds: int = 50,
        propose_interval: int = 5,
        debate_rounds: int = 2,
        verify_ratio: float = 0.1,
        use_personas: bool = True,
    ):
        if use_personas:
            self.learners = [
                Learner(name=p["name"], window_size=p["window"],
                        initial_mu=p["mu"], initial_sigma=p["sigma"])
                for p in PRESET_PERSONAS[:n_learners]
            ]
        else:
            self.learners = [Learner(name=f"L{i+1}") for i in range(n_learners)]

        # ── v2.3: 母模块升级 ──
        self.mother = MotherMind(debate_rounds=debate_rounds)

        # ── v2.3: Guard 只做架构保护 ──
        self.guard = StabilityGuard()

        self.trust = TrustEngine()
        for l in self.learners:
            self.trust.register(l.learner_id)

        self.warmup_rounds = warmup_rounds
        self.propose_interval = propose_interval
        self.verify_ratio = verify_ratio

        self.round_num = 0
        self.data_buffer: List[float] = []
        self.verify_buffer: List[float] = []
        self.consensus_history: List[float] = []
        self.log: List[dict] = []
        self.decisions: List[Decision] = []  # v2.3: 保存所有决策记录

    def run(self, datasource, max_rounds: int = 500) -> dict:
        """完整运行流程"""
        # Phase 1: 预热
        logger.info(f"预热期: {self.warmup_rounds} 轮")
        for _ in range(self.warmup_rounds):
            val = self._fetch(datasource)
            if val is None: break
            for learner in self.learners:
                learner.observe(val)
            self.round_num += 1

        # Phase 2: 运行
        logger.info(f"运行期开始, 最大 {max_rounds} 轮")
        for _ in range(max_rounds):
            val = self._fetch(datasource)
            if val is None: break
            self.round_num += 1

            for learner in self.learners:
                learner.observe(val)

            # 定期讨论
            if self.round_num % self.propose_interval == 0:
                self._discussion_round(val)

            # 事后验证
            if len(self.verify_buffer) >= 5:
                self._verify()
                self.verify_buffer = []

            if random.random() < self.verify_ratio:
                self.verify_buffer.append(val)

        return self._final_summary()

    def _discussion_round(self, current_obs: float) -> dict:
        """
        v2.3 重构: 母模块主持讨论

        旧: chains → evaluator.full_discussion() → 数字
        新: chains → mother.deliberate() → 有推理的决策
        """
        # 各 Learner 提案
        chains = []
        for learner in self.learners:
            chain = learner.propose(current_obs)
            chains.append(chain)

        # ── v2.3: 母模块深思熟虑 ──
        decision = self.mother.deliberate(
            self.learners, chains, self.trust, current_obs
        )
        self.decisions.append(decision)
        self.consensus_history.append(decision.consensus)

        # ── Guard 检查 (只保护架构，不抑制思考) ──
        guard_result = self.guard.check(
            self.learners, self.trust,
            decision.consensus,
            abs(decision.consensus - current_obs),
        )
        # Guard 的干预只用于记录，不影响决策流程
        if guard_result.get("violations"):
            logger.warning(f"架构违规: {guard_result['violations']}")

        return {
            "round": self.round_num,
            "consensus": decision.consensus,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "primary_influence": decision.primary_influence,
            "dissenting_view": decision.dissenting_view,
            "reservations": decision.reservations,
            "feedback": {
                lid: fb
                for lid, fb in decision.learner_feedback.items()
            },
            "trust_ranking": [
                f"{lid}:{t:.2f}"
                for lid, t in (self.trust.rank() if hasattr(self.trust, 'rank') else [])[:3]
            ],
            "guard": guard_result.get("status", "stable"),
        }

    def _verify(self):
        """事后验证: 更新信念 + 信任"""
        if not self.verify_buffer:
            return
        true_value = sum(self.verify_buffer) / len(self.verify_buffer)
        for learner in self.learners:
            if learner.history:
                learner.learn(true_value, learner.history[-1])
                self.trust.verify(learner.learner_id, learner.history[-1], true_value)

    def _fetch(self, datasource) -> Optional[float]:
        val = datasource.fetch()
        if val is not None:
            self.data_buffer.append(val)
        return val

    def _final_summary(self) -> dict:
        learners_summary = []
        for l in self.learners:
            learners_summary.append({
                "id": l.learner_id,
                "mu": l.belief.mu,
                "sigma": l.belief.sigma,
                "alpha": l.belief.alpha,
                "track_record": l.track_record(),
                "avg_error": l.average_error(),
                "trust": self.trust.get(l.learner_id),
                "total_rounds": l.total_rounds,
            })

        return {
            "version": "2.3.0-alpha",
            "total_rounds": self.round_num,
            "n_learners": len(self.learners),
            "warmup_rounds": self.warmup_rounds,
            "n_discussions": len(self.log),
            "n_decisions": self.mother.decision_count,
            "final_consensus": (
                self.consensus_history[-1] if self.consensus_history else None
            ),
            "mother_summary": self.mother.summary(),
            "learners": learners_summary,
            "trust_summary": self.trust.summary(),
        }

    # ── 梦境接口 (保持向后兼容) ──
    def save_dream(self, filepath: str):
        from .dream import DreamStore
        store = DreamStore()
        return store.save(self.learners, filepath)

    @classmethod
    def from_dream(cls, filepath: str, **kwargs) -> "HiveMindV2":
        from .dream import DreamStore
        store = DreamStore()
        states = store.load(filepath)
        instance = cls(use_personas=False, n_learners=0)
        instance.learners = DreamStore.restore_learners(states)
        for l in instance.learners:
            instance.trust.register(l.learner_id)
        instance.warmup_rounds = 0
        return instance
