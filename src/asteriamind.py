"""
AsteriaMind REPL — 交互式终端 (v3.0)

运行: python asteriamind.py --interactive

命令:
  status           系统状态
  learn <知识>     教她新知识: "learn 春天 CAUSES 花粉过敏"
  ask <问题>       查询知识: "ask 春天 CAUSES 什么?"
  predict          基于知识做预测
  verify <结果>    验证上次预测
  mother           看 MotherMind 在想什么
  knowledge        知识图谱概览
  run <N>          自主运行 N 轮
  help             帮助
"""
import cmd, math, random, sys, os

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

from hivemind_v2.knowledge import KnowledgeGraph
from hivemind_v2.world_model import WorldModel
from hivemind_v2.meta_learner import MetaLearner, BasisSet
from hivemind_v2.poly_learner import PolyLearner
from hivemind_v2.diagnosis import DiagnosticEngine, ExperimentDesigner
from hivemind_v2.tool_registry import ToolRegistry, Tool, orchestrate
from hivemind_v2.mother_adapter import MotherAdapter
from hivemind_v2.learner import Learner
from hivemind_v2.trust import TrustEngine
from hivemind_v2.mother import MotherMind
from hivemind_v2.argument import ArgumentEvaluator
from hivemind_v2.validator import CrossValidator
from hivemind_v2.portal import CuriosityEngine
from hivemind_v2.exploration_reward import DelayedVerificationQueue, ExplorationReward

random.seed(42)

# ═══════════════ 初始化 ═══════════════
kg = KnowledgeGraph()
wm = WorldModel()
meta = MetaLearner(switch_r2_gap=0.03, check_interval=10)
poly = PolyLearner(max_degree=5, upgrade_cooldown=6)
diag = DiagnosticEngine(history_window=50)
designer = ExperimentDesigner()
curiosity = CuriosityEngine(exploration_patience=12)
curiosity._experiment_interval = 15
reward_engine = ExplorationReward()
reward_queue = DelayedVerificationQueue(delay_rounds=10)

registry = ToolRegistry()
for t in [
    Tool("DiagnosticEngine", "诊断崩塌原因", "collapse"),
    Tool("ExperimentDesigner", "设计验证实验", "explore"),
    Tool("MetaLearner", "基函数切换", "explore"),
    Tool("PolyLearner", "多项式升阶", "collapse"),
    Tool("CuriosityEngine", "主动探索", "curiosity"),
    Tool("KnowledgeGraph", "归档发现", "discovery"),
    Tool("WorldModel", "预测验证", "prediction"),
    Tool("ExplorationReward", "奖励分配", "periodic"),
]:
    registry.register(t)

learners = [
    Learner(name="L1_optimist", window_size=5, initial_mu=+3.0, initial_sigma=8.0),
    Learner(name="L2_pessimist", window_size=5, initial_mu=-3.0, initial_sigma=8.0),
    Learner(name="L3_skeptic", window_size=10, initial_mu=0.0, initial_sigma=15.0),
]
trust = TrustEngine()
for l in learners: trust.register(l.learner_id)

mother = MotherMind()
adapter = MotherAdapter(rate_limit=8)
evaluator = ArgumentEvaluator(debate_rounds=2)
validator = CrossValidator()

last_prediction = None
ROUND = 0

def step(x, y):
    global ROUND
    ROUND += 1
    for l in learners:
        l.observe(y)
    meta.update(x, y)
    poly.update(x, y)

    if meta.current.n_updates > 5:
        pred = meta.current.predict(x)
        diag.observe(x, y - pred, meta.current.r_squared)
        curiosity.feed_r2(meta.current.r_squared)

    if ROUND % 5 == 0 and ROUND > 50:
        chains = [l.propose(y) for l in learners]
        proposals = {l.learner_id: c.proposal_value for l, c in zip(learners, chains)}
        evaluator.full_discussion(chains)
        decision = mother.deliberate(learners, chains, trust, y)
        adapter.apply(decision, learners, ROUND)
        for l in learners:
            l.learn(y, proposals[l.learner_id])
            trust.verify(l.learner_id, proposals[l.learner_id], y)
            reward_engine.record_prediction(l.learner_id, proposals[l.learner_id])
            reward_queue.submit(l.learner_id, proposals[l.learner_id], y, ROUND)
        reward_queue.resolve(ROUND, y)

    if ROUND % 50 == 0 and ROUND > 80 and meta.current.r_squared > 0.5:
        basis_name = meta.current.basis.name
        r2 = meta.current.r_squared
        kg.add("当前数据", "BEST_FIT_BY", basis_name, confidence=min(1.0, r2), source="observed")
        kg.add("当前数据", "PREDICTS", f"适合{basis_name}", confidence=min(1.0, r2), source="observed")

# ═══════════════ REPL ═══════════════

class AsteriaShell(cmd.Cmd):
    intro = """
╔════════════════════════════════════════════════╗
║  🧠 AsteriaMind REPL v3.0                     ║
║  输入 help 查看命令, 输入 quit 退出              ║
╚════════════════════════════════════════════════╝"""
    prompt = "🧠> "

    def do_status(self, arg):
        """系统状态概览"""
        ks = kg.summary()
        print(f"""
══ AsteriaMind 状态 (第 {ROUND} 轮) ══
  MetaLearner: {meta.current.basis.name} R²={meta.current.r_squared:.3f}
  知识图谱: {ks['entities']}实体 {ks['relations']}关系 (稳固{ks['consolidated']} 动摇{ks['contested']})
  Curiosity: {curiosity.search_count}次探索
  MotherMind: {mother.decision_count}次决策
  Learner:""")
        for l in sorted(learners, key=lambda x: -trust.get(x.learner_id)):
            print(f"    {l.learner_id}: μ={l.belief.mu:+.2f} σ={l.belief.sigma:.2f} trust={trust.get(l.learner_id):.3f}")

    def do_learn(self, arg):
        """教知识: learn 春天 CAUSES 花粉过敏 [0.8]"""
        parts = arg.split()
        if len(parts) >= 3:
            subj, pred, obj = parts[0], parts[1], parts[2]
            conf = float(parts[3]) if len(parts) > 3 else 0.7
            kg.add(subj, pred, obj, confidence=conf)
            print(f"  ✅ 已学习: {subj} --[{pred}]--> {obj} (置信度 {conf})")
        else:
            print("  用法: learn <主体> <关系> <客体> [置信度]")

    def do_ask(self, arg):
        """查询: ask 春天 CAUSES"""
        parts = arg.split()
        if len(parts) == 2:
            results = kg.query(parts[0], parts[1])
        else:
            results = kg.query(arg.strip())

        if not results:
            print("  ❓ 我还不知道。")
            return

        for r in results[:5]:
            bar = "█" * int(r.confidence * 10) + "░" * (10 - int(r.confidence * 10))
            print(f"  {r.subject} --[{r.predicate}]--> {r.object}  [{bar}] {r.confidence:.2f}  {r.belief.summary()}")
            if r.counter_evidence:
                for ce in r.counter_evidence:
                    print(f"    ↳ 但语境\"{ce.context}\"中是\"{ce.alternative}\"")

    def do_knowledge(self, arg):
        """知识图谱全览"""
        print(kg.dump())

    def do_predict(self, arg):
        """基于知识做预测"""
        global last_prediction
        preds = wm.predict_from_knowledge(kg)
        if not preds:
            print("  ❌ 没有可预测的知识。先用 learn 教一些 PREDICTS 关系。")
            return
        last_prediction = preds[0]
        print(f"  📋 预测: {last_prediction.description}")
        print(f"     预测值: {last_prediction.predicted_value}")
        print(f"     置信度: {last_prediction.confidence:.2f}")
        print(f"  💡 用 verify <正确|错误> 来验证")

    def do_verify(self, arg):
        """验证: verify 花粉过敏 (填入真实观测值)"""
        global last_prediction
        if last_prediction is None:
            print("  ❌ 还没有预测。先 predict。")
            return
        reality = arg.strip()
        if not reality:
            print("  用法: verify <现实值>  (例如: verify 花粉过敏)")
            return
        result = wm.verify_and_update(last_prediction.id, reality, kg)
        if result:
            icon = "✅" if result["correct"] else "❌"
            print(f"  {icon} 预测'{result['predicted']}' vs 现实'{result['reality']}' "
                  f"— 准确率: {wm.accuracy()['accuracy']:.0%}")

    def do_mother(self, arg):
        """MotherMind 最近在想什么"""
        decision = mother.decision_history[-1] if mother.decision_history else None
        if decision:
            print(f"""
  共识: {decision.consensus:.2f}  置信度: {decision.confidence:.2f}
  推理: {decision.reasoning}
  主导: {decision.primary_influence}
  反馈:""")
            for lid, fb in sorted(decision.learner_feedback.items()):
                print(f"    → {lid}: {fb[:80]}...")
        else:
            print("  MotherMind 还没做过决策。先 run <N> 让它看一些数据。")

    def do_run(self, arg):
        """自主运行 N 轮: run 100"""
        n = int(arg) if arg.strip().isdigit() else 50
        print(f"  🏃 自主运行 {n} 轮...")

        def world(x):
            return 30 * math.sin(x / 5) + 2 * x + random.gauss(0, 3)

        for _ in range(n):
            x = random.uniform(0, 25)
            y = world(x)
            step(x, y)
        print(f"  ✅ 完成。当前第 {ROUND} 轮。")

    def do_upload(self, arg):
        """上传数据点: upload x=5.2 y=42.3"""
        import re
        m = re.match(r'x=([\d.]+)\s+y=([\d.]+)', arg)
        if m:
            x, y = float(m.group(1)), float(m.group(2))
            step(x, y)
            print(f"  ✅ 已喂入 ({x}, {y})，第 {ROUND} 轮")
        else:
            print("  格式: upload x=5.2 y=42.3")

    def do_explore(self, arg):
        """自主闭环: 知识图谱自己产生目标→假说→实验→解释"""
        print("\n════════════════════════════════════════════")
        print("🔬 AM 自主探索 — 无模板闭环")
        print("════════════════════════════════════════════")

        # ── Step 1: 图谱自己生成目标 ──
        goals = kg.generate_goals(max_goals=3)
        if not goals:
            print("\n  ⚠️  知识图谱是空的。先建立基础认知...")
            def world(x):
                return 30 * math.sin(x / 5) + 2 * x + random.gauss(0, 3)
            for _ in range(60):
                x = random.uniform(0, 25)
                y = world(x)
                step(x, y)
            kg.add("当前数据", "BEST_FIT_BY", meta.current.basis.name,
                   confidence=min(1.0, meta.current.r_squared), source="observed")
            kg.add("当前数据", "PREDICTS", f"适合{meta.current.basis.name}",
                   confidence=min(1.0, meta.current.r_squared), source="observed")
            goals = kg.generate_goals(max_goals=3)

        if not goals:
            print("  ❌ 仍然没有可探索的目标。")
            return

        print(f"\n  🔍 图谱自主生成 {len(goals)} 个探索目标:")
        for i, g in enumerate(goals):
            tag = {"gap": "🕳️", "conflict": "⚡", "uncertain": "❓"}.get(g["type"], "?")
            print(f"    {i+1}. {tag} [{g['type']}] {g['reason']}")

        goal = goals[0]

        # ── Step 2: 图谱自己生成假说 ──
        hypotheses = kg.generate_hypothesis(goal["target"], goal["type"])
        print(f"\n  💭 关于\"{goal['target']}\"的假说 ({len(hypotheses)} 个):")
        for h in hypotheses:
            print(f"    · {h['statement']}")
            print(f"      ↳ {h['based_on']}")

        # ── Step 3: 设计实验, 采样, 执行 ──
        print(f"\n  🧪 实验: 采样 20 个点验证假说...")
        pre_rels = [(r.key(), r.confidence, r.belief.alpha, r.belief.beta)
                    for r in kg.relations if goal["target"] in r.key()]

        def world(x):
            return 30 * math.sin(x / 5) + 2 * x + random.gauss(0, 3)

        n = 20
        for _ in range(n):
            x = random.uniform(0, 25)
            y = world(x)
            step(x, y)

        # 根据目标类型确定验证逻辑
        if goal["type"] == "conflict":
            # 矛盾型: 看哪个 object 在当前数据下更合理
            target_rels = [r for r in kg.relations if goal["target"] in r.key()]
            best = None
            for r in target_rels:
                # 结构验证: 用基函数匹配度
                if meta.current.basis.name in r.object or r.object in meta.current.basis.name:
                    best = r
                    kg.observe(r.subject, r.predicate, r.object, correct=True, weight=1.0)
                elif r.confidence > 0.3:
                    kg.observe(r.subject, r.predicate, r.object, correct=False,
                               weight=0.5, context="实验不支持", alternative="数据不支持此关系")
            verdict = f"当前数据支持 {best.object}" if best else "无法确定哪个正确"
        else:
            # gap/uncertain: 直接验证 target 关系
            for r in kg.relations:
                if goal["target"] in r.key():
                    correct = r.confidence > 0.5
                    kg.observe(r.subject, r.predicate, r.object,
                               correct=correct, weight=1.0 if correct else 0.5)

            post_rels = [(r.key(), r.confidence, r.belief.alpha, r.belief.beta)
                         for r in kg.relations if goal["target"] in r.key()]
            verdict = "实验完成"

        # ── Step 4: 图谱自己解释变化 ──
        print(f"\n  📊 结果: {verdict}")
        for i, (key, before_conf, before_a, before_b) in enumerate(pre_rels):
            if i < len([r for r in kg.relations if goal["target"] in r.key()]):
                r = [r for r in kg.relations if goal["target"] in r.key()][i]
                delta = r.confidence - before_conf
                explanation = kg.explain_change(
                    key, before_conf, r.confidence,
                    before_a, r.belief.alpha, before_b, r.belief.beta,
                )
                arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
                print(f"    {arrow} {key[:50]}")
                print(f"      置信度 {before_conf:.2f}→{r.confidence:.2f}")
                print(f"      💡 {explanation}")

        print(f"\n════════════════════════════════════════════\n")

    def do_help(self, arg):
        print("""
命令:
  status              系统状态
  learn S P O [C]     教她: learn 春天 CAUSES 花粉过敏 0.8
  ask <问题>          查询: ask 春天 CAUSES 什么?
  predict             基于知识预测
  verify <现实值>      验证上次预测
  explore             自主提问→实验→闭环 (核心!)
  mother              MotherMind 在想什么
  knowledge           知识图谱全览
  run <N>             自主运行 N 轮
  upload x=X y=Y      喂入数据点
  quit                退出
""")

    def do_quit(self, arg):
        print("  👋")
        return True


# ═══════════════ 入口 ═══════════════
if __name__ == "__main__":
    if "--interactive" in sys.argv or "-i" in sys.argv:
        AsteriaShell().cmdloop()
    else:
        # 非交互模式: 跑一轮演示
        def world(x):
            return 30 * math.sin(x / 5) + 2 * x + random.gauss(0, 3)

        print("AsteriaMind v3.0 — 非交互模式 (用 --interactive 进入 REPL)")
        for t in range(400):
            x = random.uniform(0, 25)
            y = world(x)
            step(x, y)
        ks = kg.summary()
        print(f"  完成 400 轮。知识: {ks['entities']}实体 {ks['relations']}关系。")
        print(f"  用 python asteriamind.py --interactive 进入对话。")
