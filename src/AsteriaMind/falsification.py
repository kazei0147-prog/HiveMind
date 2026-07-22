"""
FalsificationController — 反证实验的控制层 + 来源权威评估 + WebSearch 接口 (AsteriaMind v3.1)

三个问题一起解决:

1. 停止条件: 反证实验不是无差别攻击——信念有 "抗压阈值"
2. 来源评估: 每个来源按领域追踪准确率, 动态调整可信度
3. WebSearch: 真正的网络查询接口 (通过 WorkBuddy 的 WebSearch 工具)
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Callable


# ═══════════════ 1. 反证停止条件 ═══════════════

@dataclass
class FalsificationResult:
    """一次反证实验的完整结果"""
    target_belief: str
    pre_alpha: float
    pre_beta: float
    pre_confidence: float
    post_alpha: float
    post_beta: float
    post_confidence: float
    rounds: int
    survived: bool       # 信念是否经受住了考验
    stop_reason: str


class FalsificationController:
    """
    反证实验控制器: 不是无差别攻击, 而是有限制的挑战。

    停止条件:
      1. 信念已稳固: 如果连续 N 次攻击后置信度变化 < ε → 停止 (这可能是真信念)
      2. 信念已崩溃: 如果置信度降到 0.2 以下 → 停止 (没必要继续打)
      3. 抗压上限: 最多攻击 20 轮, 之后无论结果如何 → 停止并标记为 "抗压测试完成"
      4. 自我纠正: 如果 β 的增长趋势在减速 → 信念可能找到了平衡点
    """

    MAX_ROUNDS = 20
    MIN_CONFIDENCE = 0.15
    STABILIZATION_THRESHOLD = 0.02  # 连续 3 轮置信度变化 < 2% → 稳定

    def run(self, kg, target_belief_key: str, max_rounds: int = None) -> FalsificationResult:
        """
        对一条信念执行反证实验——但知道什么时候该停。
        返回完整的实验记录。
        """
        max_r = max_rounds or self.MAX_ROUNDS
        rel = self._find_relation(kg, target_belief_key)
        if not rel:
            return FalsificationResult(
                target_belief=target_belief_key, pre_alpha=0, pre_beta=0,
                pre_confidence=0, post_alpha=0, post_beta=0, post_confidence=0,
                rounds=0, survived=False, stop_reason="belief_not_found",
            )

        pre_alpha = rel.belief.alpha
        pre_beta = rel.belief.beta
        pre_conf = rel.confidence

        subject = target_belief_key.split("--[")[0].strip()
        pred = target_belief_key.split("--[")[1].split("]-->")[0].strip()
        obj = target_belief_key.split("]-->")[1].strip()

        prev_conf = pre_conf
        stable_count = 0

        for round_num in range(max_r):
            kg.observe(subject, pred, obj, correct=False, weight=0.5,
                       context=f"反证实验第{round_num+1}轮",
                       alternative="系统审计触发的反设场景验证")

            current_rel = self._find_relation(kg, target_belief_key)
            if not current_rel:
                break
            current_conf = current_rel.confidence
            delta = abs(current_conf - prev_conf)

            # 停止条件 1: 信念已稳固 (攻击无效)
            if delta < self.STABILIZATION_THRESHOLD:
                stable_count += 1
                if stable_count >= 3:
                    return FalsificationResult(
                        target_belief=target_belief_key, pre_alpha=pre_alpha, pre_beta=pre_beta,
                        pre_confidence=pre_conf,
                        post_alpha=current_rel.belief.alpha, post_beta=current_rel.belief.beta,
                        post_confidence=current_conf,
                        rounds=round_num + 1, survived=True,
                        stop_reason=f"信念稳定 ({round_num+1}轮攻击无效, 变化<2%), 这可能是真信念",
                    )
            else:
                stable_count = 0
                prev_conf = current_conf

            # 停止条件 2: 信念已崩溃
            if current_conf < self.MIN_CONFIDENCE:
                return FalsificationResult(
                    target_belief=target_belief_key, pre_alpha=pre_alpha, pre_beta=pre_beta,
                    pre_confidence=pre_conf,
                    post_alpha=current_rel.belief.alpha, post_beta=current_rel.belief.beta,
                    post_confidence=current_conf,
                    rounds=round_num + 1, survived=False,
                    stop_reason=f"信念崩溃 (置信度 {current_conf:.2f} < {self.MIN_CONFIDENCE}), 该信念可能需要重新审视",
                )

        # 达到最大轮数
        final_rel = self._find_relation(kg, target_belief_key)
        final_conf = final_rel.confidence if final_rel else 0
        survived = final_conf > 0.5
        return FalsificationResult(
            target_belief=target_belief_key, pre_alpha=pre_alpha, pre_beta=pre_beta,
            pre_confidence=pre_conf,
            post_alpha=final_rel.belief.alpha if final_rel else 0,
            post_beta=final_rel.belief.beta if final_rel else 0,
            post_confidence=final_conf,
            rounds=max_r, survived=survived,
            stop_reason=f"达到最大轮数 ({max_r}), "
                        f"{'信念经受住了考验!' if survived else '信念已被显著削弱'}",
        )

    def _find_relation(self, kg, key: str):
        for r in kg.relations:
            if r.key() == key:
                return r
        return None


# ═══════════════ 2. 来源动态权威评估 ═══════════════

@dataclass
class SourceProfile:
    """一个来源的领域画像"""
    name: str
    overall_credibility: float = 0.5
    domain_accuracy: dict = field(default_factory=dict)  # {"医疗": 0.9, "金融": 0.5}
    claims_made: int = 0
    claims_accepted: int = 0
    claims_rejected: int = 0

    def update_accuracy(self, domain: str, correct: bool):
        if domain not in self.domain_accuracy:
            self.domain_accuracy[domain] = 0.5
        # 指数移动平均
        old = self.domain_accuracy[domain]
        self.domain_accuracy[domain] = old * 0.9 + (1.0 if correct else 0.0) * 0.1

    def credibility_for(self, subject: str, predicate: str) -> float:
        """
        动态可信度: 不是固定数字, 而是根据领域调整。

        如果来源在"医疗"领域历史准确率 90%, 那它的医疗主张更可信。
        如果还没被评估过, 返回默认值。
        """
        domain = self._infer_domain(subject, predicate)
        domain_acc = self.domain_accuracy.get(domain, 0.5)
        # 权重: 领域准确率 60% + 总体可信度 40%
        return domain_acc * 0.6 + self.overall_credibility * 0.4

    def _infer_domain(self, subject: str, predicate: str) -> str:
        keywords = {"体重": "健康", "血压": "医疗", "癌症": "医疗",
                    "金融": "金融", "股票": "金融", "温度": "气象",
                    "运动": "健康", "咖啡": "健康", "教育": "教育"}
        for kw, domain in keywords.items():
            if kw in subject or kw in predicate:
                return domain
        return "通用"


class SourceAuthorityTracker:
    """追踪所有来源的权威性, 动态调整可信度"""

    def __init__(self):
        self.sources: dict[str, SourceProfile] = {}

    def get_or_create(self, name: str, initial_credibility: float = 0.5) -> SourceProfile:
        if name not in self.sources:
            self.sources[name] = SourceProfile(name=name, overall_credibility=initial_credibility)
        return self.sources[name]

    def record_outcome(self, source_name: str, subject: str, predicate: str,
                       claim_correct: bool):
        source = self.get_or_create(source_name)
        domain = source._infer_domain(subject, predicate)
        source.update_accuracy(domain, claim_correct)
        if claim_correct:
            source.claims_accepted += 1
        else:
            source.claims_rejected += 1
        source.claims_made += 1

    def credibility_for(self, source_name: str, subject: str, predicate: str,
                        default: float = 0.5) -> float:
        if source_name not in self.sources:
            return default
        return self.sources[source_name].credibility_for(subject, predicate)


# ═══════════════ 3. WebSearch 接口 ═══════════════

@dataclass
class WebResult:
    """一次网络查询的结果"""
    query: str
    url: str
    title: str
    snippet: str
    source_credibility: float = 0.3  # 网络来源默认可信度低


class WebSearchInterface:
    """
    真正的网络查询接口。

    未来可以接入 WorkBuddy 的 WebSearch 工具或任何搜索引擎 API。
    目前是占位, 但接口已经定义好了——换实现不影响调用方。
    """

    def __init__(self, search_fn: Optional[Callable] = None):
        """
        search_fn: 实际执行搜索的函数。
        签名: (query: str) -> list[WebResult]
        """
        self.search_fn = search_fn or self._fallback_search

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        return self.search_fn(query, max_results)

    def _fallback_search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """兜底: 当没有真实搜索引擎时的占位实现"""
        return [WebResult(
            query=query, url=f"(search://{query})",
            title=f"搜索结果: {query}",
            snippet=f"外部搜索接口未连接。请为 AM 配置真实的 WebSearch 工具。",
            source_credibility=0.0,
        )]
