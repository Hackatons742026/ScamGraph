"""ScamGraph FastAPI entry point and production SPA fallback."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI(title="ScamGraph DNA", version="1")
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1"}


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    """Serve built assets, otherwise the SPA shell; never shadow /api routes."""
    if path.startswith("api/") or not FRONTEND_DIST.is_dir():
        raise HTTPException(status_code=404, detail="Not found")
    requested = (FRONTEND_DIST / path).resolve()
    if requested.is_relative_to(FRONTEND_DIST.resolve()) and requested.is_file():
        return FileResponse(requested)
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")
