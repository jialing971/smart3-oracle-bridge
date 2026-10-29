# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置：目录模式，内置 Python + oracledb

from PyInstaller.utils.hooks import collect_all

block_cipher = None

_oracle_datas, _oracle_binaries, _oracle_hidden = collect_all("oracledb")
_crypto_datas, _crypto_binaries, _crypto_hidden = collect_all("cryptography")

# oracledb 间接依赖的标准库，PyInstaller 有时不会自动打进包
_stdlib_hidden = [
    "getpass",
    "secrets",
    "uuid",
    "decimal",
    "xml.etree.ElementTree",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=_oracle_binaries + _crypto_binaries,
    datas=_oracle_datas + _crypto_datas,
    hiddenimports=[
        "oracledb",
        "oracledb.thin",
        "oracledb.thin_impl",
        "cryptography",
        *_oracle_hidden,
        *_crypto_hidden,
        *_stdlib_hidden,
        "src.app.gui.main_window",
        "src.app.gui.settings_dialog",
        "src.app.service",
        "src.config.loader",
        "src.config.models",
        "src.tcp.server",
        "src.protocol.parser",
        "src.db.writer",
        "src.utils.logger",
        "src.utils.security",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FormassyBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FormassyBridge",
)
