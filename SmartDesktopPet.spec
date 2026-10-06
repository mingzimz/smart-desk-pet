# PyInstaller directory build. No external artwork is required for the built-in pets.
from pathlib import Path

root = Path(SPECPATH)
a = Analysis([str(root / 'run.py')], pathex=[str(root / 'src')], binaries=[], datas=[],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SmartDesktopPet', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SmartDesktopPet')

