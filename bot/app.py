"""
Servidor web del bot Robertito (FastAPI, modo webhook).

Expone:
  - POST /webhook/<secret_path>  → endpoint legado; n8n recibe los updates en producción.
  - GET  /app                    → sirve la Mini App (webapp/index.html).
  - GET  /                       → idem (home).
  - GET  /health                 → healthcheck simple.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from . import config, db, handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("robertito.app")

app = FastAPI(title="Robertito · Asistente contable", docs_url=None, redoc_url=None)

_WEBAPP_FILE = config.BASE_DIR / "webapp" / "index.html"


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    log.info("Base de datos inicializada. Puerto %s.", config.PORT)


@app.get("/health")
def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.get("/app")
@app.get("/")
def webapp() -> FileResponse:
    if not _WEBAPP_FILE.exists():
        raise HTTPException(status_code=404, detail="Mini App no encontrada")
    return FileResponse(str(_WEBAPP_FILE), media_type="text/html")


@app.post("/webhook/{secret_path}")
async def webhook(
    secret_path: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    # Validar la ruta secreta.
    if secret_path != config.WEBHOOK_SECRET_PATH:
        raise HTTPException(status_code=404, detail="Not found")
    # Validar el secret token de Telegram.
    if config.WEBHOOK_SECRET_TOKEN:
        if x_telegram_bot_api_secret_token != config.WEBHOOK_SECRET_TOKEN:
            raise HTTPException(status_code=403, detail="Forbidden")
    try:
        update = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Bad request")
    try:
        handlers.procesar_update(update)
    except Exception as exc:  # noqa: BLE001
        log.exception("Error procesando update: %s", exc)
    # Siempre 200 para que Telegram no reintente en loop.
    return {"ok": True}
