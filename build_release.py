"""一键打包发行版 EXE 到 发行版/（Windows）。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# 本地布局：源代码/ 与 发行版/、.venv-build/ 并列在项目根
# GitHub（把「源代码」里的文件上传为仓库根）：发行版/ 与 .venv-build/ 也在仓库根
PROJECT_ROOT = ROOT.parent if ROOT.name == "源代码" else ROOT
VENV = PROJECT_ROOT / ".venv-build"
RELEASE_DIR = PROJECT_ROOT / "发行版"


def main() -> int:
    venv_py = VENV / "Scripts" / "python.exe"
    if not venv_py.exists():
        print("创建打包虚拟环境 .venv-build ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    # Pillow 供 GUI 图片预览（PIL.Image / ImageTk）；PyInstaller 为打包器
    subprocess.check_call([
        str(venv_py), "-m", "pip", "install", "-q",
        "pyinstaller>=6.0", "pillow>=10.0",
    ])

    print("PyInstaller 打包中 ...")
    subprocess.check_call(
        [str(venv_py), "-m", "PyInstaller", "build.spec", "--noconfirm", "--clean"],
        cwd=str(ROOT),
    )

    src = ROOT / "dist" / "DLOUWebsiteCrawler.exe"
    if not src.exists():
        print("打包失败：未找到 dist/DLOUWebsiteCrawler.exe", file=sys.stderr)
        return 1

    RELEASE_DIR.mkdir(exist_ok=True)
    dst = RELEASE_DIR / "DLOUWebsiteCrawler.exe"
    shutil.copy2(src, dst)
    # 只保留发行版一份 EXE
    for junk in (ROOT / "dist", ROOT / "build"):
        try:
            shutil.rmtree(junk)
        except OSError:
            pass
    print(f"发行版已更新：{dst}  ({dst.stat().st_size / 1024 / 1024:.2f} MB)")
    print("已清理 dist/ 与 build/，仅保留 发行版/ 一份 EXE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
