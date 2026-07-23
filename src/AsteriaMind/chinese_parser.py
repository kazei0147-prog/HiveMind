"""
ChineseParser — 轻量中文理解引擎 (AsteriaMind v3.2)

不是正则匹配——是理解中文句法。

核心: 找关系词(是/属于/绕/导致/在...) → 前=主语, 后=宾语。
     没有关系词 → 检查能力/动作模式(会+动词)。
"""
import re
from typing import Optional

STOPWORDS = set('的了着呢吗吧啊呀哦嗯哈也在都和而或但且还很太更最不没别被把对从到向跟让用以')

CLASSIFIERS = set('个只种条张本杯碗块片辆架棵支根滴颗粒匹头位名件双')

RELATION_MARKERS = {
    '是': 'IS_A', '属于': 'BELONGS_TO',
    '围绕': 'ORBITS', '绕着': 'ORBITS', '绕': 'ORBITS',
    '导致': 'CAUSES', '引起': 'CAUSES', '产生': 'CAUSES', '造成': 'CAUSES',
    '增加': 'INCREASES', '减少': 'DECREASES',
    '包括': 'INCLUDES', '包含': 'CONTAINS',
}

ABILITY_VERBS = {'会', '能', '可以', '能够'}
MOTION_VERBS = {'跑', '走', '飞', '游', '爬', '跳', '滚', '流', '发光'}


def strip_classifier(s: str) -> str:
    """去除量词前缀: "一种饮料"→"饮料", "常见的"→去掉"""
    s = re.sub(r'^(?:一|两|三|几)?[个只种条张本杯碗块片辆架棵支根滴颗粒匹头位名件双]', '', s)
    s = re.sub(r'^(?:常见|普通|一般|特别|非常|十分|比较)的?', '', s)
    s = s.rstrip('的了呢吗吧啊呀哦')
    return s.strip()


def parse_sentence(text: str) -> Optional[dict]:
    """
    解析中文句子 → 结构化三元组。

    鱼会在水里游     → {type:action, subject:鱼, verb:游, location:水里}
    咖啡是一种饮料   → {type:fact, subject:咖啡, predicate:IS_A, object:饮料}
    """
    clean = re.sub(r'[，。！？、；：""''（）\\s]', '', text)

    # ── 找关系词 ──
    best_marker = None
    best_pos = len(clean) + 1
    for marker in sorted(RELATION_MARKERS.keys(), key=lambda x: -len(x)):
        pos = clean.find(marker)
        if 1 <= pos < best_pos:
            best_marker = marker
            best_pos = pos

    if best_marker:
        subject = clean[:best_pos].rstrip(''.join(STOPWORDS))
        obj_raw = clean[best_pos + len(best_marker):]
        obj = strip_classifier(obj_raw)

        if obj in ('什么', '谁', '哪', '怎么', '如何', ''):
            return {"type": "question", "subject": subject,
                    "predicate": RELATION_MARKERS[best_marker]}

        return {
            "type": "fact",
            "subject": subject if subject else None,
            "predicate": RELATION_MARKERS[best_marker],
            "object": obj,
            "confidence": 0.7 if RELATION_MARKERS[best_marker] in ("IS_A", "BELONGS_TO") else 0.6,
        }

    # ── 无关系词: 能力/动作 ──
    for av in ABILITY_VERBS:
        pos = clean.find(av)
        if pos < 1:
            continue
        subject = clean[:pos].rstrip(''.join(STOPWORDS))
        after = clean[pos + len(av):]

        # 找实际动词
        verb = None
        for mv in MOTION_VERBS:
            if mv in after:
                verb = mv
                break
        if not verb:
            for ch in after[:4]:
                if ch not in STOPWORDS and ch not in '的一':
                    verb = ch
                    break

        # 找位置
        location = None
        place_markers = {'在', '从', '到', '往', '向', '朝'}
        for pm in place_markers:
            if pm in after:
                start = after.index(pm) + 1
                end = min(start + 10, len(after))
                for i in range(start, end):
                    if after[i-1] in {'里', '上', '下', '中', '外', '边', '面', '内'}:
                        location = after[start:i]
                        break
                if location:
                    break

        return {
            "type": "action",
            "subject": subject if subject else None,
            "verb": verb,
            "predicate": "CAN" if verb in MOTION_VERBS else "DOES",
            "object": verb,
            "location": location,
            "confidence": 0.5,
        }

    return None
