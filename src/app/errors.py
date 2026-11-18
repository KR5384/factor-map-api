"""API 共通のエラー形式 {"error": {"code", "message", "field"}} を返すための部品。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.field = field


def _body(code: str, message: str, field: str | None = None) -> dict:
    error = {"code": code, "message": message}
    if field:
        error["field"] = field
    return {"error": error}


def _field_name(loc: tuple) -> str | None:
    # ("body", "answers", "q07") → "answers.q07"
    parts = [str(p) for p in loc if p != "body"]
    return ".".join(parts) or None


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, exc.field))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        return JSONResponse(
            status_code=400,
            content=_body("VALIDATION_ERROR", first.get("msg", "入力が正しくありません"), _field_name(first.get("loc", ()))),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException):
        # 400 は本文が JSON として読めないとき（UTF-8 でない文字を含む場合など）
        code = {400: "VALIDATION_ERROR", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, __: Exception):
        return JSONResponse(status_code=500, content=_body("SERVER_ERROR", "サーバーでエラーが発生しました"))
