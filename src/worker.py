from workers import asgi

from app.main import app

# Cloudflare Workers の入口。FastAPI アプリを ASGI 経由で公開する
Default = asgi.entrypoint(app)
