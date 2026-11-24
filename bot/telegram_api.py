"""
Cliente mínimo de la Bot API de Telegram (vía httpx).

Nunca imprime ni expone el token. El token se lee de config.BOT_TOKEN.
"""
from __future__ import annotations

import logging

import httpx

from . import config

log = logging.getLogger("robertito.telegram")

_API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"


def _call(method: str, **params) -> dict:
    """Llama a un método de la Bot API y devuelve el JSON de respuesta."""
    try:
        r = httpx.post(f"{_API}/{method}", json=params, timeout=30)
        data = r.json()
        if not data.get("ok"):
            log.warning("Telegram %s devolvió error: %s", method, data.get("description"))
        return data
    except Exception as exc:  # noqa: BLE001
        log.error("Error llamando a Telegram %s: %s", method, exc)
        return {"ok": False, "error": str(exc)}


def send_message(chat_id: int, text: str, reply_markup: dict | None = None,
                 parse_mode: str = "Markdown") -> dict:
    params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode,
              "disable_web_page_preview": True}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    return _call("sendMessage", **params)


def answer_callback_query(callback_query_id: str, text: str | None = None) -> dict:
    params = {"callback_query_id": callback_query_id}
    if text:
        params["text"] = text
    return _call("answerCallbackQuery", **params)


def send_document(chat_id: int, filename: str, content: bytes | str,
                  caption: str | None = None) -> dict:
    """Envía un documento (archivo) usando multipart/form-data."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
        data["parse_mode"] = "Markdown"
    files = {"document": (filename, content, "text/plain")}
    try:
        r = httpx.post(f"{_API}/sendDocument", data=data, files=files, timeout=60)
        out = r.json()
        if not out.get("ok"):
            log.warning("sendDocument error: %s", out.get("description"))
        return out
    except Exception as exc:  # noqa: BLE001
        log.error("Error en sendDocument: %s", exc)
        return {"ok": False, "error": str(exc)}


# --- Configuración del bot (webhook, menú, comandos) ---

def set_webhook(url: str, secret_token: str) -> dict:
    """Impedir que el backend sustituya el webhook de n8n."""
    raise RuntimeError(
        "El webhook de @Elrobertbot lo administra el Telegram Trigger de n8n; "
        "no se puede registrar desde este backend."
    )


def get_webhook_info() -> dict:
    return _call("getWebhookInfo")


def set_chat_menu_button(webapp_url: str, text: str = "Abrir Robertito") -> dict:
    return _call(
        "setChatMenuButton",
        menu_button={
            "type": "web_app",
            "text": text,
            "web_app": {"url": webapp_url},
        },
    )


def set_my_commands(commands: list[dict]) -> dict:
    return _call("setMyCommands", commands=commands)
