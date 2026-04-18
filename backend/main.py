from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.upload import router as upload_router
from backend.routes.analyze import router as analyze_router
from backend.routes.chat import router as chat_router
app = FastAPI(title="ACTA AI Backend")
app.include_router(chat_router, prefix="/api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routes
app.include_router(upload_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")

@app.get("/")
def health():
    return {"status": "ACTA AI backend running"}