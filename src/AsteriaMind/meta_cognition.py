"""
MetaCognition — 轻量仲裁层 (AsteriaMind v3.2)

MotherFallback 的进化版。

不是总调度者——只做一件事: 当多个模块信号冲突时, 裁决。

输入:
  - Semantic say: IS_A (0.75)
  - Pragmatic say: info_request (0.70)
  - StarMap say: confirmed (0.62)
  - Dream say: [类比假说] 猫 CAN 汪 (0.20)

输出: 统一的 action + confidence + 回复策略
"""
from collections import defaultdict


class MetaCognition:
    """
    仲裁层——不是独裁者, 是加权投票。

    不控制模块怎么运行, 只对它们的结果做最终加权。
    """

    def __init__(self):
        self.conflict_log: list[dict] = []

    def arbitrate(self, signals: dict) -> dict:
        """
        多模块信号 → 统一裁决。

        signals = {
            "semantic": {"action": "IS_A", "confidence": 0.75},
            "pragmatic": {"action": "info_request", "confidence": 0.70},
            "star_map": {"action": "confirmed", "confidence": 0.62},
            "dream": {"action": "analogy", "confidence": 0.20},     # optional
        }

        返回: { "action", "confidence", "reason", "conflict" }
        """
        # 收集所有模块的投票
        votes: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for source, sig in signals.items():
            if sig and sig.get("action"):
                votes[sig["action"]].append((source, sig.get("confidence", 0.5)))

        if not votes:
            return {"action": "unknown", "confidence": 0.0, "reason": "无信号", "conflict": False}

        # 加权投票: 每个 action 的总权重 = Σ confidence
        scored = {}
        for action, sources in votes.items():
            scored[action] = sum(c for _, c in sources)

        # 找出最高分
        best_action = max(scored, key=scored.get)
        best_score = scored[best_action]

        # 检测冲突: 是否有第二名接近第一名?
        sorted_scores = sorted(scored.items(), key=lambda x: -x[1])
        has_conflict = False
        conflict_detail = ""
        if len(sorted_scores) > 1:
            runner_up = sorted_scores[1]
            if runner_up[1] > best_score * 0.6:  # 第二名 ≥ 第一名的 60%
                has_conflict = True
                conflict_detail = f"{best_action}({best_score:.0%}) vs {runner_up[0]}({runner_up[1]:.0%})"

        # 置信度归一化
        total_weight = sum(scored.values()) or 1
        confidence = best_score / total_weight

        result = {
            "action": best_action,
            "confidence": min(confidence, 0.95),
            "reason": f"加权投票: {best_action} ({', '.join(src for src, _ in votes[best_action])})",
            "conflict": has_conflict,
            "conflict_detail": conflict_detail,
            "all_votes": {a: f"{scored[a]:.2f}" for a in scored},
        }

        if has_conflict:
            self.conflict_log.append(result)

        return result

    def get_recent_conflicts(self, limit: int = 5) -> list[dict]:
        return self.conflict_log[-limit:]
