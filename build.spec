# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：DLOUWebsiteCrawler.exe（无控制台窗口）

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.html', '.'),
        ('app.css', '.'),
        ('app.js', '.'),
    ],
    hiddenimports=['tkinter', 'tkinter.ttk', 'PIL', 'PIL.Image', 'PIL.ImageTk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DLOUWebsiteCrawler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
