from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors import register_error_handlers
from app.routers import diagnoses, items

app = FastAPI(title="factor-map-api")

# 開発用: すべてのオリジンからのアクセスを許可（本番では絞ること）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(items.router)
app.include_router(diagnoses.router)


@app.get("/")
def health_check():
    return {"status": "ok"}
