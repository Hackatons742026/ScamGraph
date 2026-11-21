"""ScamGraph FastAPI entry point and production SPA fallback."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from .routes import router

app = FastAPI(title="ScamGraph DNA", version="1")
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app.include_router(router)


@app.exception_handler(HTTPException)
def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    error = "not_found" if exc.status_code == 404 else "validation_error" if exc.status_code == 422 else "http_error"
    return JSONResponse(status_code=exc.status_code, content={"error": error, "detail": exc.detail})


@app.exception_handler(RequestValidationError)
def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = "; ".join(str(item.get("msg", "Invalid input")) for item in exc.errors())
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": detail})


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
