"""
AsteriaMind Web Chat — 浏览器交互窗口 (v3.2)

单文件实现: HTTP 服务器 + 聊天 HTML + AM 后端。

启动: python asteriamind_web.py
访问: http://localhost:8866

不需要 Flask/Django——纯 Python 内置 http.server。
"""
import http.server, json, re, time, os, sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))

from AsteriaMind.knowledge import KnowledgeGraph
from AsteriaMind.hypothesis_template import TemplateRegistry, _builtin_templates
from AsteriaMind.math_reasoner import MathReasoner
from AsteriaMind.skill_library import build_default_skills
from AsteriaMind.knowledge_db import KnowledgeDB

# ── AM 初始化 ──
kg = KnowledgeGraph()
db = KnowledgeDB("asteriamind.db")
reg = TemplateRegistry()
for t in _builtin_templates(): reg.register(t)
skill_lib = build_default_skills()
mr = MathReasoner()

# 从 DB 恢复已有知识
for r in db.query():
    kg.add(r["subject"], r["predicate"], r["object"], confidence=r["confidence"])

CHAT_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AsteriaMind — 对话</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:system-ui;display:flex;flex-direction:column;height:100vh}
#header{background:#161b22;padding:12px 16px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:8px}
#header h1{font-size:16px;color:#58a6ff}
#header .dot{width:8px;height:8px;background:#3fb950;border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
#chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.5;animation:slideIn .3s}
@keyframes slideIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.msg.user{align-self:flex-end;background:#238636;color:#fff}
.msg.am{align-self:flex-start;background:#21262d;border:1px solid #30363d}
.msg.error{align-self:flex-start;background:#490202;border:1px solid #f85149;color:#f85149}
.msg .meta{font-size:11px;color:#8b949e;margin-bottom:4px}
.msg.am .meta{color:#58a6ff}
#input-area{background:#161b22;padding:12px 16px;border-top:1px solid #30363d;display:flex;gap:8px}
#input-area input{flex:1;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 14px;color:#c9d1d9;font-size:14px;outline:none}
#input-area input:focus{border-color:#58a6ff}
#input-area button{background:#238636;color:white;border:none;border-radius:8px;padding:8px 18px;cursor:pointer;font-size:14px}
#input-area button:hover{background:#2ea043}
#stats{background:#161b22;padding:8px 16px;border-top:1px solid #30363d;display:flex;gap:16px;font-size:12px;color:#8b949e}
.hint{font-size:11px;color:#484f58;margin-top:4px}
</style>
</head>
<body>
<div id="header"><span class="dot"></span><h1>AsteriaMind v3.2</h1><span style="color:#8b949e;font-size:12px">自然语言对话</span></div>
<div id="chat">
  <div class="msg am"><div class="meta">🧠 AM</div>你好！我是 AsteriaMind。你可以：
  <br>· 告诉我事实：<i>地球是行星</i>
  <br>· 问我问题：<i>咖啡能让人清醒吗</i>
  <br>· 让我算数：<i>2+3×5 等于多少</i>
  <br>· 叫我搜索：<i>查一下黑洞</i></div>
</div>
<div id="input-area">
  <input id="msg-input" placeholder="说点什么..." autofocus onkeydown="if(event.key==='Enter')send()">
  <button onclick="send()">发送</button>
</div>
<div id="stats">数据库: ... | 模板: 6 | 模块就绪</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('msg-input');
const stats = document.getElementById('stats');

function addMsg(text, cls, meta) {
    const div = document.createElement('div');
    div.className = 'msg ' + cls;
    div.innerHTML = (meta ? '<div class="meta">' + meta + '</div>' : '') + text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

async function send() {
    const msg = input.value.trim();
    if (!msg) return;
    addMsg(msg, 'user', '💬 你');
    input.value = '';
    input.disabled = true;
    try {
        const res = await fetch('/api/talk', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: msg})
        });
        const data = await res.json();
        addMsg(data.reply, data.error ? 'error' : 'am', '🧠 AM' + (data.action ? ' · ' + data.action : ''));
        if (data.stats) stats.textContent = data.stats;
    } catch(e) {
        addMsg('连接失败: ' + e.message, 'error', '⚠ 错误');
    }
    input.disabled = false;
    input.focus();
}
</script>
</body>
</html>"""


class AMHandler(http.server.BaseHTTPRequestHandler):
    """AM 的 HTTP 请求处理器"""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        """静默日志"""
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/api/stats":
            self._json({"stats": db.stats(), "relations": db.count()})
        else:
            self.send_error(404)

    def do_POST(self):
        try:
            if self.path == "/api/talk":
                self._handle_talk()
            elif self.path == "/api/learn":
                self._handle_learn()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_error(500, str(e))

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(CHAT_HTML.encode('utf-8'))

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _handle_talk(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._json({"reply": "空请求", "error": True})
                return
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))
            text = data.get("text", "").strip()
            if not text:
                self._json({"reply": "请说点什么", "error": True})
                return
            reply, action = self._process(text)
            self._json({
                "reply": reply, "action": action,
                "stats": f"数据库: {db.count()} 条关系 | 模板: {len(reg.templates)} 个",
            })
        except Exception as e:
            self._json({"reply": f"内部错误: {e}", "error": True})

    def _handle_learn(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode('utf-8'))
            subj, pred, obj = body.get("s"), body.get("p"), body.get("o")
            conf = body.get("c", 0.7)
            if not all([subj, pred, obj]):
                self._json({"reply": "格式: {s,p,o,c}", "error": True})
                return
            kg.add(subj, pred, obj, confidence=conf)
            db.add_relation(subj, pred, obj, conf, source="web")
            self._json({"reply": f"学会了: {subj} --[{pred}]--> {obj}"})
        except Exception as e:
            self._json({"reply": f"错误: {e}", "error": True})

    def _process(self, text: str) -> tuple[str, str]:
        """处理一条自然语言消息, 返回 (回复, 动作类型)"""

        # ── 数学 ──
        if re.search(r'\d[\+\-\*/\^]', text) or re.search(r'算|等于|多少|几', text):
            m = skill_lib.best_match(text)
            if m:
                r = m.execute(text, kg)
                if r.get("success"):
                    return (f"计算结果: {r.get('result')}", "math")

        # ── 问题 ──
        if "?" in text or "?" in text or "吗" in text or "什么" in text or "谁" in text:
            # 提取关键词
            for kw in re.findall(r'[\u4e00-\u9fff\w]{2,}', text.replace("?", "").replace("？", "")):
                if kw in ("什么", "是什么", "吗", "可以", "怎么"): continue
                found = kg.query(subject=kw)
                if found:
                    lines = [f"{r.subject} --[{r.predicate}]--> {r.object} ({r.confidence:.0%})"
                             for r in found[:5]]
                    return ("关于 '" + kw + "' 我知道:\n" + "\n".join(lines), "kg_query")
            return (f"关于这个我还不知道。告诉我吧——比如 '{text[:4]} 是 什么'", "unknown")

        # ── 事实陈述 ──
        m = re.search(r'(.+?)是(.+)', text)
        if m:
            subj, obj = m.group(1).strip(), m.group(2).strip()
            subj = re.sub(r'^(一种|一个|一只)', '', subj)
            kg.add(subj, "IS_A", obj, confidence=0.7)
            db.add_relation(subj, "IS_A", obj, 0.7, source="web")
            return (f"学会了: {subj} 是一种 {obj} ✅", "learn_fact")

        # ── 因果 ──
        m = re.search(r'(.+?)(?:能|会|可以|导致|引起)(.+)', text)
        if m:
            subj, obj = m.group(1).strip(), m.group(2).strip()
            kg.add(subj, "CAUSES", obj, confidence=0.6)
            db.add_relation(subj, "CAUSES", obj, 0.6, source="web")
            return (f"学会了: {subj} 会导致 {obj} ✅", "learn_cause")

        return (f"没太理解。试试: 'X是Y' / 'X会导致Y' / 'X能Y吗' / '2+3=?'", "unclear")


if __name__ == "__main__":
    port = 8866
    print(f"\n╔══════════════════════════════╗")
    print(f"║  🧠 AsteriaMind Web Chat    ║")
    print(f"║  http://localhost:{port}       ║")
    print(f"║  Ctrl+C 退出                 ║")
    print(f"╚══════════════════════════════╝")
    print(f"  💾 {db.count()} 条已有知识")
    server = http.server.HTTPServer(("127.0.0.1", port), AMHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 再见")
        server.shutdown()
