import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import dashboard, questions, run, tasks

# Path to the Vite build output (populated during Docker build)
DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")


def create_app() -> FastAPI:
    app = FastAPI(title="AI Factory UI", docs_url="/api/docs", redoc_url=None)

    # --- API routers (must be registered BEFORE the static / catch-all routes) ---
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(questions.router, prefix="/api")
    app.include_router(run.router, prefix="/api")

    # --- Static assets (Vite hashed bundles: /assets/index-abc123.js, etc.) ---
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # --- SPA fallback — serves index.html for all remaining paths ---
    # MUST be registered last so it does not shadow API routes.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = os.path.join(DIST_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        # Friendly message when running without a built frontend
        return {
            "detail": "Frontend not built yet. Run: docker-compose build ui",
            "api_docs": "/api/docs",
        }

    return app


app = create_app()
