"""
Puebla el archivo .env del proyecto a partir del secrets file del VM, SIN imprimir
el token en ninguna salida.

Lee BOT_TOKEN de /home/ubuntu/.config/abacusai_auth_secrets.json (servicio
"telegram robertito", campo bot_token) y genera/actualiza /home/ubuntu/
Robertito-Asistente-Contable/.env con los valores de deploy.

Uso:
    python scripts/poblar_env.py
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ENV_PATH = BASE / ".env"
SECRETS_PATH = Path("/home/ubuntu/.config/abacusai_auth_secrets.json")

DOMAIN = "https://robertito-bot-ruben.abacusai.cloud"


def _leer_token() -> str:
    data = json.load(open(SECRETS_PATH, encoding="utf-8"))
    # Clave case-insensitive.
    for k in data:
        if k.lower() == "telegram robertito":
            return data[k]["secrets"]["bot_token"]["value"]
    raise SystemExit("No se encontró el servicio 'telegram robertito' en el secrets file.")


def _valor_existente(clave: str) -> str | None:
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(clave + "="):
            return line.split("=", 1)[1].strip()
    return None


def main() -> None:
    token = _leer_token()

    # Reutilizar secretos de webhook si ya existen (idempotente).
    secret_path = _valor_existente("WEBHOOK_SECRET_PATH") or secrets.token_urlsafe(16)
    secret_token = _valor_existente("WEBHOOK_SECRET_TOKEN") or secrets.token_urlsafe(24)
    allowed = _valor_existente("ALLOWED_CHAT_IDS") or ""
    cuit = _valor_existente("CUIT_AGENTE_RETENCION") or ""

    lineas = [
        "# Archivo generado por scripts/poblar_env.py — NO commitear.",
        f"BOT_TOKEN={token}",
        f"WEBHOOK_URL={DOMAIN}/webhook/{secret_path}",
        f"WEBAPP_URL={DOMAIN}/app",
        f"WEBHOOK_SECRET_PATH={secret_path}",
        f"WEBHOOK_SECRET_TOKEN={secret_token}",
        f"ALLOWED_CHAT_IDS={allowed}",
        "PORT=8081",
        f"CUIT_AGENTE_RETENCION={cuit}",
        "",
    ]
    ENV_PATH.write_text("\n".join(lineas), encoding="utf-8")
    ENV_PATH.chmod(0o600)
    print(".env generado/actualizado correctamente (token NO mostrado).")


if __name__ == "__main__":
    main()
