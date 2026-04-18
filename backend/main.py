from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.db import init_db
from backend.routes.analyze import router as analyze_router
from backend.routes.annotations import router as annotations_router
from backend.routes.versions import router as versions_router

settings = get_settings()

app = FastAPI(title="CTA Agent Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(analyze_router, prefix="/api")
app.include_router(versions_router, prefix="/api")
app.include_router(annotations_router, prefix="/api")


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "CTA Agent backend running"}
