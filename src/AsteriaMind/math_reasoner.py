"""
MathReasoner — AM 的数学推理模块 (AsteriaMind v3.2)

不是传统符号数学引擎。
是 AM 认知体系中的数学工具: 计算结果以 "derived" 来源进入 KG,
经过 α/β 验证, 可被反证挑战, 可参与假说竞争。

支持: 四则运算 / 简单代数 / 模式识别 / 单位转换
"""
import re
import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class MathResult:
    """一次数学推理的结果"""
    expression: str
    result: float
    steps: list[str]
    confidence: float     # 计算结果的可信度 (计算本身是确定的, 但解析可能出错)
    source: str = "math_derived"


class MathReasoner:
    """
    AM 的数学推理引擎。

    计算结果以 derived 来源进入 KG:
      confidence = 0.95 (计算是确定的)
      source = "math_derived"
      → 可被反证挑战 (比如用户说"算错了")
    """

    def solve(self, query: str) -> Optional[MathResult]:
        """解析并求解数学问题。返回 None 如果无法处理。"""
        q = query.strip()

        # 四则运算
        result = self._arithmetic(q)
        if result is not None:
            return result

        # 简单代数: "x + 5 = 10"
        result = self._algebra(q)
        if result is not None:
            return result

        # 模式识别: "2, 4, 6, 8, ?"
        result = self._pattern(q)
        if result is not None:
            return result

        # 单位转换: "1 mile = ? km"
        result = self._convert(q)
        if result is not None:
            return result

        # 乘方/开方
        result = self._sqrt(q)
        if result is not None:
            return result
        result = self._power(q)
        if result is not None:
            return result

        return None

    def _arithmetic(self, q: str) -> Optional[MathResult]:
        """四则运算: 2 + 3 * 4, (5 - 2) / 3 等"""
        # 只保留数字和运算符
        cleaned = re.sub(r'[^0-9+\-*/().^%\s]', '', q)
        if not cleaned or not re.search(r'[+\-*/]', cleaned):
            return None
        try:
            cleaned = cleaned.replace('^', '**')
            result = eval(cleaned, {"__builtins__": {}},
                         {"math": math, "sqrt": math.sqrt, "pi": math.pi,
                          "sin": math.sin, "cos": math.cos, "tan": math.tan,
                          "log": math.log, "log10": math.log10, "exp": math.exp,
                          "abs": abs, "pow": pow})
            return MathResult(
                expression=q,
                result=result,
                steps=[f"计算: {cleaned} = {result}"],
                confidence=0.95,
            )
        except Exception:
            return None

    def _algebra(self, q: str) -> Optional[MathResult]:
        """简单代数: x + 5 = 10, 2x = 8, x/2 = 5"""
        # 匹配: (数字)*(x) (+-*/) (数字) = (数字)
        m = re.search(r'([\d.]*)\s*\*?\s*x\s*([+\-*/])\s*([\d.]+)\s*=\s*([\d.]+)', q)
        if m:
            coeff = float(m.group(1)) if m.group(1) else 1.0
            op = m.group(2)
            b = float(m.group(3))
            c = float(m.group(4))

            if op == '+':
                x = (c - b) / coeff
            elif op == '-':
                x = (c + b) / coeff
            elif op == '*':
                x = c / (coeff * b) if b != 0 else None
            elif op == '/':
                x = c * b / coeff
            else:
                return None

            if x is not None:
                return MathResult(
                    expression=q,
                    result=x,
                    steps=[f"解: x = {x}"],
                    confidence=0.95,
                )

        # 匹配: x = 数字
        m = re.search(r'x\s*=\s*([\d.]+)', q)
        if m:
            return MathResult(
                expression=q,
                result=float(m.group(1)),
                steps=[f"x = {m.group(1)}"],
                confidence=0.95,
            )

        return None

    def _pattern(self, q: str) -> Optional[MathResult]:
        """模式识别: 2, 4, 6, 8, ?"""
        m = re.search(r'([\d\s,.]+)\s*\?', q)
        if not m:
            return None

        nums_str = m.group(1).strip()
        nums = [float(n) for n in re.findall(r'[\d.]+', nums_str)]
        if len(nums) < 3:
            return None

        # 检测等差数列
        diffs = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
        if max(diffs) - min(diffs) < 0.001:
            next_val = nums[-1] + diffs[0]
            return MathResult(
                expression=q,
                result=next_val,
                steps=[f"等差数列, 公差={diffs[0]:.1f}, 下一个={next_val}"],
                confidence=0.9,
            )

        # 检测等比数列
        if all(d != 0 for d in nums):
            ratios = [nums[i+1] / nums[i] for i in range(len(nums)-1)]
            if max(ratios) - min(ratios) < 0.001:
                next_val = nums[-1] * ratios[0]
                return MathResult(
                    expression=q,
                    result=next_val,
                    steps=[f"等比数列, 公比={ratios[0]:.2f}, 下一个={next_val}"],
                    confidence=0.85,
                )

        return None

    def _convert(self, q: str) -> Optional[MathResult]:
        """单位转换"""
        conversions = {
            ("mile", "km"): 1.60934,
            ("km", "mile"): 0.621371,
            ("inch", "cm"): 2.54,
            ("cm", "inch"): 0.393701,
            ("foot", "meter"): 0.3048,
            ("meter", "foot"): 3.28084,
            ("pound", "kg"): 0.453592,
            ("kg", "pound"): 2.20462,
            ("celsius", "fahrenheit"): "lambda c: c * 9/5 + 32",
            ("fahrenheit", "celsius"): "lambda f: (f - 32) * 5/9",
            ("hour", "minute"): 60,
            ("minute", "second"): 60,
            ("day", "hour"): 24,
        }

        m = re.search(r'([\d.]+)\s*(\w+)\s*(?:[=＝to到→]|\s)\s*\??\s*(\w+)', q, re.IGNORECASE)
        if not m:
            return None

        value = float(m.group(1))
        from_unit = m.group(2).lower()
        to_unit = m.group(3).lower() if m.group(3) else ""

        # 尝试匹配
        for (f, t), factor in conversions.items():
            if f in from_unit:
                if not to_unit or t in to_unit:
                    if isinstance(factor, str):
                        # lambda 字符串 → eval
                        result = eval(factor)(value)
                    else:
                        result = value * factor
                    return MathResult(
                        expression=q,
                        result=result,
                        steps=[f"{value} {from_unit} = {result:.4f} {t}"],
                        confidence=0.95,
                    )

        return None

    def _sqrt(self, q: str) -> Optional[MathResult]:
        """开方: sqrt 16, sqrt(25)"""
        m = re.search(r'sqrt\s*\(?\s*([\d.]+)\s*\)?', q)
        if m:
            val = float(m.group(1))
            result = math.sqrt(val)
            return MathResult(
                expression=q,
                result=result,
                steps=[f"sqrt({val}) = {result}"],
                confidence=0.95,
            )
        return None

    def _power(self, q: str) -> Optional[MathResult]:
        """乘方: 2^10"""
        m = re.search(r'([\d.]+)\s*\^?\s*(\d+)', q)
        if m:
            base = float(m.group(1))
            exp = int(m.group(2))
            result = base ** exp
            return MathResult(
                expression=q,
                result=result,
                steps=[f"{base}^{exp} = {result}"],
                confidence=0.95,
            )
        return None
