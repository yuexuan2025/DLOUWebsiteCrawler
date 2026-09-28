"""一键打包发行版 EXE 到 项目根/发行版/（Windows）。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent          # .../源代码
PROJECT_ROOT = SRC_ROOT.parent                       # 项目根（仅 源代码/ 发行版/）
VENV = SRC_ROOT / ".venv-build"
RELEASE_DIR = PROJECT_ROOT / "发行版"


def main() -> int:
    venv_py = VENV / "Scripts" / "python.exe"
    if not venv_py.exists():
        print("创建打包虚拟环境 .venv-build ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
        subprocess.check_call([str(venv_py), "-m", "pip", "install", "-q", "pyinstaller"])

    print("PyInstaller 打包中 ...")
    subprocess.check_call(
        [str(venv_py), "-m", "PyInstaller", "build.spec", "--noconfirm", "--clean"],
        cwd=str(SRC_ROOT),
    )

    src = SRC_ROOT / "dist" / "DLOUWebsiteCrawler.exe"
    if not src.exists():
        print("打包失败：未找到 source/dist/DLOUWebsiteCrawler.exe", file=sys.stderr)
        return 1

    release = RELEASE_DIR
    release.mkdir(exist_ok=True)
    dst = release / "DLOUWebsiteCrawler.exe"
    shutil.copy2(src, dst)
    # 只保留发行版一份 EXE
    for junk in (SRC_ROOT / "dist", SRC_ROOT / "build"):
        try:
            shutil.rmtree(junk)
        except OSError:
            pass
    print(f"发行版已更新：{dst}  ({dst.stat().st_size / 1024 / 1024:.2f} MB)")
    print("已清理 源代码/dist 与 源代码/build，仅保留 发行版/ 一份 EXE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
