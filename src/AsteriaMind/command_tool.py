"""
CommandTool — AM 的终端指令执行能力 (AsteriaMind v3.2)

让她能执行终端命令，学习脚本，自举环境。

安全设计:
  - 白名单: 只允许安全命令 (pip/git/python/dir/ls/mkdir/...)
  - 输出截断: 单次最多 5000 字符
  - 超时: 单次最多 30 秒
  - 结果记录: 成功/失败都进 KG，α/β 追踪
"""
import subprocess, time, os, shlex
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandResult:
    """一次终端命令的执行结果"""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: float
    success: bool


class CommandTool:
    """
    AM 的终端工具——让她能执行命令、学习脚本。

    不是无限制 shell——白名单 + 超时 + 输出限制。
    """

    # 安全白名单: 允许的命令前缀
    ALLOWED_COMMANDS = [
        "python", "python3", "pip", "pip3",
        "git", "dir", "ls", "type", "cat", "echo",
        "mkdir", "cd", "pwd", "whoami", "hostname",
        "curl", "wget",
        "npx", "npm", "node",
        "systeminfo", "tasklist", "set",
    ]

    DANGEROUS_PATTERNS = [
        "rm -rf", "del /S", "format", "shutdown",
        "> /dev/sda", "dd if=", "mkfs",
    ]

    def __init__(self, max_output: int = 5000, timeout: int = 30):
        self.max_output = max_output
        self.timeout = timeout
        self.history: list[CommandResult] = []

    def run(self, command: str, cwd: str = None) -> CommandResult:
        """
        执行一条终端命令。

        返回 CommandResult，包含 exit_code/stdout/stderr/耗时。
        """
        # 安全检查
        if not self._is_safe(command):
            return CommandResult(
                command=command, exit_code=-1, stdout="",
                stderr=f"安全拒绝: 命令 '{command[:60]}' 不在白名单或匹配危险模式",
                elapsed_ms=0, success=False,
            )

        start = time.time()
        try:
            result = subprocess.run(
                command, shell=True, cwd=cwd or os.getcwd(),
                capture_output=True, text=True,
                timeout=self.timeout,
                encoding='utf-8', errors='replace',
            )
            elapsed = (time.time() - start) * 1000

            stdout = result.stdout[:self.max_output]
            stderr = result.stderr[:self.max_output]

            cmd_result = CommandResult(
                command=command,
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                elapsed_ms=elapsed,
                success=result.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            cmd_result = CommandResult(
                command=command, exit_code=-1, stdout="",
                stderr=f"超时 ({self.timeout}s)", elapsed_ms=elapsed,
                success=False,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            cmd_result = CommandResult(
                command=command, exit_code=-1, stdout="",
                stderr=str(e), elapsed_ms=elapsed, success=False,
            )

        self.history.append(cmd_result)
        return cmd_result

    def _is_safe(self, command: str) -> bool:
        """检查命令是否安全"""
        cmd_lower = command.lower().strip()

        # 危险模式检查
        for danger in self.DANGEROUS_PATTERNS:
            if danger.lower() in cmd_lower:
                return False

        # 白名单检查
        cmd_first = shlex.split(command)[0] if command else ""
        for allowed in self.ALLOWED_COMMANDS:
            if cmd_first == allowed or cmd_first.endswith(f"\\{allowed}") or cmd_first.endswith(f"/{allowed}"):
                return True

        return False

    def learn_from_history(self, kg=None) -> dict:
        """
        从命令历史中学习: 成功的命令模式存入 KG。
        """
        if not kg:
            return {"learned": 0}

        count = 0
        for result in self.history[-10:]:
            key = f"cmd:{result.command[:40]}"
            if result.success:
                kg.add(key, "IS_RELIABLE_COMMAND", "true",
                       confidence=min(0.95, 0.5 + 0.05 * len(self.history)),
                       source="command_tool")
            else:
                kg.add(key, "IS_RELIABLE_COMMAND", "false",
                       confidence=0.3, source="command_tool")
            count += 1
        return {"learned": count}

    def install_deps(self, requirements_file: str = "requirements.txt") -> CommandResult:
        """安装 Python 依赖"""
        if not os.path.exists(requirements_file):
            return CommandResult(
                command=f"pip install -r {requirements_file}",
                exit_code=-1, stdout="", stderr=f"文件不存在: {requirements_file}",
                elapsed_ms=0, success=False,
            )
        return self.run(f"pip install -r {requirements_file}")

    def check_env(self) -> dict:
        """检查运行环境"""
        results = {}
        results["python"] = self.run("python --version")
        results["git"] = self.run("git --version")
        results["pip"] = self.run("pip --version")
        results["pwd"] = self.run("pwd" if os.name != 'nt' else "cd")
        return {
            k: {"ok": v.success, "output": (v.stdout or v.stderr).strip()}
            for k, v in results.items()
        }
