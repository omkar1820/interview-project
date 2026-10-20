import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import db_ok, init_db
from .routers import admin, api, coding, ws

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Automated Candidate Interview & Evaluation System", version="1.0.0", lifespan=lifespan)
app.include_router(api.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(coding.router, prefix="/api")
app.include_router(ws.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/health")
def health(response: Response):
    ok = db_ok()
    if not ok:
        response.status_code = 503
    return {"status": "ok" if ok else "degraded", "database": ok}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/interview", include_in_schema=False)
def interview_page():
    return FileResponse(STATIC / "interview.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(STATIC / "dashboard.html")
