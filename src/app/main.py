from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, factor_analyses, surveys

app = FastAPI(title="factor-map-api")

# 開発用: すべてのオリジンからのアクセスを許可（本番では絞ること）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 研究データ保存 API (v1)
app.include_router(surveys.router)
app.include_router(factor_analyses.router)

# 管理者 API (v1)
app.include_router(admin.router)


@app.get("/")
def health_check():
    return {"status": "ok"}
