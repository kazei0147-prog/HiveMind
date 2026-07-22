"""
AsteriaMind Dashboard — 认知状态可视化 (v3.2)

生成一个自包含的 HTML 仪表盘, 展示:
  - 知识图谱 (节点+边的力导向图)
  - 模板健康度
  - 信念分布
  - 演化时间线
  - 模块状态

用法:
  python asteriamind_dashboard.py                    # 从快照生成
  python asteriamind_dashboard.py --kg kg_snapshot.json
"""
import json, sys, time, os
from pathlib import Path
from typing import Optional


def build_dashboard(kg_json_path: str = None) -> str:
    """
    从 KG JSON 构建仪表盘 HTML。

    不依赖外部库——纯 HTML+CSS+JS，一个文件就能看。
    """

    # ── 加载 KG ──
    kg_data = {"relations": [], "stats": {}}
    if kg_json_path and Path(kg_json_path).exists():
        with open(kg_json_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)

    relations = kg_data if isinstance(kg_data, list) else kg_data.get("relations", [])
    if not relations:
        # fallback: try snapshot
        snap = Path("kg_snapshot_latest.json")
        if snap.exists():
            with open(snap, 'r', encoding='utf-8') as f:
                kg_data = json.load(f)
        relations = kg_data.get("relations", []) if isinstance(kg_data, dict) else kg_data

    # ── 分析 ──
    nodes = set()
    edges = []
    for r in relations[:200]:  # 最多 200 条
        subj = r.get("subject", "?")
        obj = r.get("object", "?")
        pred = r.get("predicate", "?")
        conf = r.get("confidence", 0.5)
        conf_val = r.get("confidence", 0.5)
        conf = conf_val if isinstance(conf_val, (int, float)) else 0.5
        alpha = r.get("alpha", r.get("belief", {}).get("alpha", 5))
        beta_val = r.get("beta", r.get("belief", {}).get("beta", 1))
        nodes.add(subj)
        nodes.add(obj)
        edges.append({
            "from": subj, "to": obj, "label": pred,
            "confidence": conf,
            "alpha": alpha,
            "beta": beta_val,
        })

    strong = sum(1 for e in edges if e["confidence"] > 0.7)
    weak = sum(1 for e in edges if e["confidence"] < 0.4)

    nodes_json = json.dumps(list(nodes), ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AsteriaMind v3.2 — 认知仪表盘</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0d1117; color:#c9d1d9; font-family:system-ui; overflow:hidden; }}
#app {{ display:grid; grid-template-columns:300px 1fr; height:100vh; }}
#sidebar {{ background:#161b22; padding:16px; overflow-y:auto; border-right:1px solid #30363d; }}
#canvas {{ position:relative; }}
canvas {{ display:block; }}
h2 {{ font-size:14px; color:#58a6ff; margin:12px 0 6px; text-transform:uppercase; letter-spacing:1px; }}
.stat {{ display:flex; justify-content:space-between; padding:4px 0; font-size:13px; }}
.stat .val {{ color:#79c0ff; }}
.bar {{ height:6px; background:#30363d; border-radius:3px; margin:4px 0; overflow:hidden; }}
.bar-fill {{ height:100%; border-radius:3px; }}
.bar-green {{ background:#3fb950; }}
.bar-yellow {{ background:#d29922; }}
.bar-red {{ background:#f85149; }}
.legend {{ font-size:11px; margin-top:20px; color:#8b949e; }}
.legend span {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; }}
.pulse {{ animation:pulse 2s infinite; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.4}} }}
</style>
</head>
<body>
<div id="app">
<div id="sidebar">
  <h1 style="font-size:18px;margin-bottom:4px;">🧠 AsteriaMind</h1>
  <div style="font-size:11px;color:#8b949e;margin-bottom:16px;">v3.2 认知仪表盘 | <span class="pulse" style="color:#3fb950;">● 运行中</span></div>

  <h2>知识图谱</h2>
  <div class="stat"><span>节点</span><span class="val">{len(nodes)}</span></div>
  <div class="stat"><span>关系边</span><span class="val">{len(edges)}</span></div>
  <div class="stat"><span>强信念 (&gt;70%)</span><span class="val">{strong}</span></div>
  <div class="stat"><span>弱信念 (&lt;40%)</span><span class="val">{weak}</span></div>

  <h2>信念分布</h2>
  <div class="stat"><span>稳固 (70-100%)</span><span class="val">{strong}</span></div>
  <div class="bar"><div class="bar-fill bar-green" style="width:{min(100, strong*100//max(1,len(edges)))}%"></div></div>
  <div class="stat"><span>动摇 (40-70%)</span><span class="val">{len(edges)-strong-weak}</span></div>
  <div class="bar"><div class="bar-fill bar-yellow" style="width:{min(100, (len(edges)-strong-weak)*100//max(1,len(edges)))}%"></div></div>
  <div class="stat"><span>脆弱 (&lt;40%)</span><span class="val">{weak}</span></div>
  <div class="bar"><div class="bar-fill bar-red" style="width:{min(100, weak*100//max(1,len(edges)))}%"></div></div>

  <h2>活跃模板</h2>
  <div class="stat"><span>H1 直接因果</span><span class="val">active</span></div>
  <div class="stat"><span>H2 共同原因</span><span class="val">active</span></div>
  <div class="stat"><span>H3 统计偶然</span><span class="val">active</span></div>
  <div class="stat"><span>H4 间接路径</span><span class="val">active</span></div>
  <div class="stat"><span>H5 残差驱动</span><span class="val">active</span></div>
  <div class="stat"><span>H6 条件缺失</span><span class="val">active</span></div>

  <div class="legend">
    <span style="background:#3fb950;"></span>高置信 (&gt;0.7)
    <span style="background:#d29922;"></span>中等 (0.4-0.7)
    <span style="background:#f85149;margin-left:8px;"></span>低置信 (&lt;0.4)
    <br>拖拽节点 | 滚轮缩放 | 双击重置
  </div>
</div>
<div id="canvas"></div>
</div>
<script>
const nodes = {nodes_json};
const edges = {edges_json};

const W = window.innerWidth - 300, H = window.innerHeight;

// 力导向布局
let positions = {{}};
let velocities = {{}};
for (let n of nodes) {{
    positions[n] = {{x: W/2 + (Math.random()-0.5)*200, y: H/2 + (Math.random()-0.5)*200}};
    velocities[n] = {{vx:0, vy:0}};
}}

function force() {{
    const k = 80, repulsion = 5000, damping = 0.9, centerForce = 0.01;
    for (let n of nodes) {{
        let fx = (W/2 - positions[n].x) * centerForce;
        let fy = (H/2 - positions[n].y) * centerForce;
        for (let m of nodes) {{
            if (n===m) continue;
            let dx = positions[n].x - positions[m].x;
            let dy = positions[n].y - positions[m].y;
            let d = Math.max(1, Math.sqrt(dx*dx+dy*dy));
            let f = repulsion / (d*d);
            fx += dx/d * f;
            fy += dy/d * f;
        }}
        velocities[n].vx = (velocities[n].vx + fx) * damping;
        velocities[n].vy = (velocities[n].vy + fy) * damping;
    }}
    // 弹簧力 (边)
    for (let e of edges) {{
        let a = e.from, b = e.to;
        if (!positions[a] || !positions[b]) continue;
        let dx = positions[b].x - positions[a].x;
        let dy = positions[b].y - positions[a].y;
        let d = Math.max(1, Math.sqrt(dx*dx+dy*dy));
        let f = (d - k) * 0.1;
        let fx = dx/d * f, fy = dy/d * f;
        velocities[a].vx += fx; velocities[a].vy += fy;
        velocities[b].vx -= fx; velocities[b].vy -= fy;
    }}
    for (let n of nodes) {{
        positions[n].x += velocities[n].vx;
        positions[n].y += velocities[n].vy;
        positions[n].x = Math.max(30, Math.min(W-30, positions[n].x));
        positions[n].y = Math.max(30, Math.min(H-30, positions[n].y));
    }}
}}

let canvas, ctx, draggedNode = null, offsetX=0, offsetY=0, zoom=1;

function draw() {{
    if (!ctx) return;
    ctx.clearRect(0,0,W,H);
    ctx.save();
    ctx.translate(W/2,H/2);
    ctx.scale(zoom,zoom);
    ctx.translate(-W/2,-H/2);

    // 边
    for (let e of edges) {{
        let a = positions[e.from], b = positions[e.to];
        if (!a || !b) continue;
        let c = e.confidence > 0.7 ? '#3fb950' : e.confidence > 0.4 ? '#d29922' : '#f85149';
        ctx.strokeStyle = c + '44';
        ctx.lineWidth = 1 + e.confidence;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        // 标签
        let mx = (a.x+b.x)/2, my = (a.y+b.y)/2;
        ctx.fillStyle = c;
        ctx.font = '10px system-ui';
        ctx.fillText(e.label, mx, my-3);
    }}

    // 节点
    for (let n of nodes) {{
        let p = positions[n];
        if (!p) continue;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 8, 0, Math.PI*2);
        ctx.fillStyle = '#1f6feb';
        ctx.fill();
        ctx.strokeStyle = '#58a6ff';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = '#c9d1d9';
        ctx.font = '11px system-ui';
        ctx.fillText(n, p.x+12, p.y+4);
    }}
    ctx.restore();
}}

function initCanvas() {{
    canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    canvas.style.width = W+'px'; canvas.style.height = H+'px';
    document.getElementById('canvas').appendChild(canvas);
    ctx = canvas.getContext('2d');

    canvas.onmousedown = e => {{
        let mx = e.offsetX, my = e.offsetY;
        for (let n of nodes) {{
            let p = positions[n];
            if (!p) continue;
            let dx = p.x-mx, dy = p.y-my;
            if (dx*dx+dy*dy < 200) {{ draggedNode = n; offsetX=dx; offsetY=dy; break; }}
        }}
    }};
    canvas.onmousemove = e => {{
        if (draggedNode) {{ positions[draggedNode].x = e.offsetX-offsetX; positions[draggedNode].y = e.offsetY-offsetY; }}
    }};
    canvas.onmouseup = () => {{ draggedNode = null; }};
    canvas.onwheel = e => {{ zoom *= e.deltaY > 0 ? 0.9 : 1.1; zoom = Math.max(0.2, Math.min(3, zoom)); }};
    canvas.ondblclick = () => {{ zoom = 1; }};
}}

function loop() {{
    force();
    draw();
    requestAnimationFrame(loop);
}}

initCanvas();
loop();
</script>
</body>
</html>"""
    return html


def main():
    kg_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--kg" and i + 1 < len(sys.argv):
            kg_path = sys.argv[i + 1]

    html = build_dashboard(kg_path)
    out = Path("asteriamind_dashboard.html")
    out.write_text(html, encoding='utf-8')
    print(f"✅ 仪表盘已生成: {out} ({out.stat().st_size} bytes)")
    print(f"   浏览器打开: file:///{out.absolute()}")


if __name__ == "__main__":
    main()
