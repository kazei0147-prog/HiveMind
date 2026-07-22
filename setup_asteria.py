"""
AsteriaMind Self-Deploy — 独立环境部署脚本

让她自己建好家, 不需要人手动设置。

用法:
  python setup_asteria.py                  # 交互式安装
  python setup_asteria.py --auto           # 无人值守安装
  python setup_asteria.py --daemon         # 安装为系统服务

做的事:
  1. 检查 Python 环境
  2. 创建目录结构 (snapshots/ logs/ data/)
  3. 生成初始配置
  4. 创建启动脚本 (asteriamind.bat / asteriamind.sh)
  5. 可选: 安装为系统服务 (systemd / Windows Task Scheduler)
"""
import sys, os, json, shutil, platform
from pathlib import Path

VERSION = "3.2"


def check_python():
    """检查 Python 环境"""
    py_ver = sys.version_info
    print(f"  🐍 Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    if py_ver < (3, 9):
        print("  ❌ 需要 Python 3.9+")
        return False
    return True


def create_dirs(base: Path):
    """创建目录结构"""
    dirs = ["snapshots", "logs", "data"]
    for d in dirs:
        (base / d).mkdir(exist_ok=True)
        print(f"  📁 {base / d}")
    return True


def create_startup_script(base: Path):
    """创建启动脚本"""
    is_win = platform.system() == "Windows"
    src_dir = base / "src"

    if is_win:
        script = base / "asteriamind.bat"
        script.write_text(f"""@echo off
cd /d "{src_dir}"
echo AsteriaMind v{VERSION} Daemon
echo =========================
python asteriamind_daemon.py --kg "{base / 'snapshots' / 'kg_snapshot_latest.json'}"
pause
""", encoding='utf-8')
    else:
        script = base / "asteriamind.sh"
        script.write_text(f"""#!/bin/bash
cd "{src_dir}"
echo "AsteriaMind v{VERSION} Daemon"
echo "========================="
exec python3 asteriamind_daemon.py --kg "{base / 'snapshots' / 'kg_snapshot_latest.json'}"
""", encoding='utf-8')
        script.chmod(0o755)

    print(f"  📜 启动脚本: {script.name}")
    return True


def create_config(base: Path):
    """生成配置文件"""
    config = {
        "version": VERSION,
        "daemon": {
            "tick_interval": 0.5,
            "snapshot_interval": 300,
            "heartbeat_interval": 600,
        },
        "kg": {
            "autosave": True,
            "snapshot_dir": str(base / "snapshots"),
            "max_snapshots": 10,
        },
        "search": {
            "enabled": True,
            "max_results": 3,
            "source_credibility_default": 0.5,
        },
        "evolution": {
            "enabled": True,
            "min_rounds_before_evolve": 3,
        },
    }
    config_path = base / "asteria_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"  ⚙️  配置: {config_path.name}")
    return True


def install_service(base: Path):
    """安装系统服务"""
    is_win = platform.system() == "Windows"

    if is_win:
        # Windows: 使用 schtasks
        script = base / "asteriamind.bat"
        cmd = (f'schtasks /create /tn "AsteriaMindDaemon" '
               f'/tr ""{script}"" /sc ONSTART /ru SYSTEM /f')
        print(f"  🪟 Windows 服务: schtasks (需管理员权限)")
        print(f"     命令: {cmd}")
        print(f"     手动运行: schtasks /run /tn AsteriaMindDaemon")
        return True
    else:
        # Linux: systemd
        service_content = f"""[Unit]
Description=AsteriaMind Cognitive Daemon v{VERSION}
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'nobody')}
WorkingDirectory={base / 'src'}
ExecStart={sys.executable} asteriamind_daemon.py --kg {base / 'snapshots' / 'kg_snapshot_latest.json'}
Restart=always
RestartSec=10
StandardOutput=append:{base / 'logs' / 'daemon.log'}
StandardError=append:{base / 'logs' / 'daemon.err'}

[Install]
WantedBy=multi-user.target
"""
        service_path = base / "asteriamind.service"
        service_path.write_text(service_content, encoding='utf-8')
        print(f"  🐧 systemd 服务: {service_path.name}")
        print(f"     安装: sudo cp {service_path} /etc/systemd/system/")
        print(f"     启动: sudo systemctl enable --now asteriamind")
        return True


def main():
    auto = "--auto" in sys.argv
    daemon_flag = "--daemon" in sys.argv

    base = Path(__file__).parent.parent  # repo root
    print(f"\n╔══════════════════════════════════╗")
    print(f"║  AsteriaMind v{VERSION} 安装     ║")
    print(f"╚══════════════════════════════════╝")
    print(f"  📍 项目: {base}")

    if not auto:
        input("\n  按 Enter 继续...")

    ok = True
    ok &= check_python()
    ok &= create_dirs(base)
    ok &= create_startup_script(base)
    ok &= create_config(base)

    if daemon_flag:
        ok &= install_service(base)

    if ok:
        print(f"\n  ✅ AsteriaMind v{VERSION} 安装完成!")
        print(f"     启动: {'asteriamind.bat' if platform.system() == 'Windows' else './asteriamind.sh'}")
        print(f"     守护: python src/asteriamind_daemon.py --kg src/kg_snapshot_latest.json")
    else:
        print(f"\n  ❌ 安装失败, 请检查上面的错误信息。")
        sys.exit(1)


if __name__ == "__main__":
    main()
