# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for SF Scanner
# Build: pyinstaller sfscanner.spec
#
# Prerequisites:
#   1. pip install pyinstaller (in backend venv)
#   2. cd frontend && npm run build   (creates frontend/dist/)

from pathlib import Path
import sys

ROOT = Path(SPECPATH)

block_cipher = None

# ---------------------------------------------------------------------------
# Hidden imports — packages that PyInstaller misses via static analysis
# ---------------------------------------------------------------------------
hidden = [
    # FastAPI / Starlette internals
    "fastapi",
    "fastapi.responses",
    "fastapi.staticfiles",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.middleware.trustedhost",
    "starlette.middleware",
    "starlette.middleware.sessions",
    "starlette.middleware.cors",
    "starlette.middleware.base",
    "starlette.routing",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.requests",
    "starlette.background",
    "starlette.concurrency",
    "starlette.exceptions",
    "starlette.testclient",
    "starlette.types",
    # Uvicorn
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # Pydantic v2
    "pydantic",
    "pydantic.v1",
    "pydantic_settings",
    "pydantic_core",
    # HTTP
    "httpx",
    "httpcore",
    "h11",
    "anyio",
    "anyio.abc",
    "anyio._backends._asyncio",
    # Anthropic / OpenAI SDKs
    "anthropic",
    "openai",
    # Salesforce
    "simple_salesforce",
    # Misc
    "itsdangerous",
    "dotenv",
    "multipart",
    "aiofiles",
    "xmltodict",
    "email_validator",
    "sniffio",
    "certifi",
    "charset_normalizer",
]

# ---------------------------------------------------------------------------
# Data files — frontend dist bundle + backend skill files
# ---------------------------------------------------------------------------
datas = [
    # Bundled React app
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    # Any .md skill files shipped with the backend
    (str(ROOT / "backend"), "backend"),
]

# Exclude the virtualenv from the analysis path so PyInstaller doesn't
# accidentally bundle development-only packages.
excludes = [
    "pytest", "black", "mypy", "ruff", "ipython", "notebook",
    "matplotlib", "numpy", "pandas",
]

a = Analysis(
    [str(ROOT / "run_server.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sfscanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,          # compress with UPX if available (reduces size ~30%)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,      # keep console so users can see the server URL
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
