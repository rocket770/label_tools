# -*- mode: python ; coding: utf-8 -*-

import sys ; sys.setrecursionlimit(sys.getrecursionlimit() * 5)
import os

def find_ffi_dll():
    search_roots = [sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix]
    for root in search_roots:
        root = os.path.abspath(root)
        for subdir in ('Library\\bin', 'DLLs'):
            candidate = os.path.join(root, subdir, 'ffi.dll')
            if os.path.exists(candidate):
                return candidate
    for root, _, files in os.walk(sys.base_prefix):
        if 'ffi.dll' in files:
            return os.path.join(root, 'ffi.dll')
    return None

ffi_dll = find_ffi_dll()
binaries = [(ffi_dll, '.')] if ffi_dll else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=['_ctypes'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pkg_resources', 'setuptools'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
