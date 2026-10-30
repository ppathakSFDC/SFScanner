from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .routers.auth_router import router as auth_router
from .routers.scan_router import router as scan_router
from .routers.setup_router import router as setup_router
from .routers.agents_router import router as agents_router
from .routers.export_router import router as export_router
from .routers.migrate_router import router as migrate_router
from .routers.info_router import router as info_router
from .routers.gdpr_router import router as gdpr_router
from .routers.compare_router import router as compare_router
from .routers.security_router import router as security_router
from .routers.mcp_router import router as mcp_router
from .routers.assessment_router import router as assessment_router

app = FastAPI(title="SF Scanner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(scan_router)
app.include_router(export_router)
app.include_router(agents_router)
app.include_router(migrate_router)
app.include_router(info_router)
app.include_router(gdpr_router)
app.include_router(compare_router)
app.include_router(security_router)
app.include_router(mcp_router)
app.include_router(assessment_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve the built React bundle when frontend/dist exists (packaged mode).
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.exists():
    _assets = _DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="spa_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        requested = _DIST / full_path
        if full_path and requested.is_file():
            return FileResponse(str(requested))
        return FileResponse(str(_DIST / "index.html"))
