"""
Registra la configuración del bot en Telegram: webhook, botón de menú (Mini App)
y lista de comandos. NO imprime el token.

Uso (con el venv del proyecto):
    python scripts/registrar_telegram.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import config, telegram_api as tg  # noqa: E402


def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("Falta BOT_TOKEN en el .env. Corré scripts/poblar_env.py primero.")

    # El webhook de Telegram pertenece exclusivamente al Telegram Trigger de n8n.
    # No llamar setWebhook desde este backend: reemplazaría el endpoint activo de n8n.

    # 1) Botón de menú (Mini App)
    r = tg.set_chat_menu_button(config.WEBAPP_URL, text="Abrir Robertito")
    print("setChatMenuButton ok:", r.get("ok"), "-", r.get("description"))

    # 2) Comandos
    comandos = [
        {"command": "start", "description": "Iniciar / ver el menú de Robertito"},
        {"command": "ayuda", "description": "Ver las opciones disponibles"},
        {"command": "cancelar", "description": "Cancelar la operación en curso"},
    ]
    r = tg.set_my_commands(comandos)
    print("setMyCommands ok:", r.get("ok"), "-", r.get("description"))

    # 3) Verificar el estado del webhook (solo lectura; sin exponer el token)
    info = tg.get_webhook_info().get("result", {})
    url = info.get("url", "")
    # Ofuscar el secret_path en la URL mostrada.
    if "/webhook/" in url:
        url = url.split("/webhook/")[0] + "/webhook/<secret>"
    print("--- getWebhookInfo ---")
    print("url:", url)
    print("has_custom_certificate:", info.get("has_custom_certificate"))
    print("pending_update_count:", info.get("pending_update_count"))
    print("last_error_message:", info.get("last_error_message"))
    print("last_error_date:", info.get("last_error_date"))
    print("max_connections:", info.get("max_connections"))


if __name__ == "__main__":
    main()
