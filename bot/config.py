"""
Configuración centralizada del bot Robertito.

Lee los parámetros sensibles desde variables de entorno (archivo .env, que NO se
versiona). Además, centraliza la ESCALA DE RETENCIÓN de Ganancias para que Rubén
pueda ajustarla sin tocar la lógica del bot.
"""
from __future__ import annotations

import os
from pathlib import Path

# -------------------------------------------------------------------------
# Carga del .env (sin dependencias externas: parser mínimo)
# -------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_PATH = BASE_DIR / ".env"


def _load_env() -> None:
    """Carga pares CLAVE=valor del .env en os.environ (sin pisar lo ya seteado)."""
    if not _ENV_PATH.exists():
        return
    for raw in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_env()

# -------------------------------------------------------------------------
# Parámetros del bot (desde entorno)
# -------------------------------------------------------------------------
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL: str = os.environ.get("WEBHOOK_URL", "")
WEBAPP_URL: str = os.environ.get("WEBAPP_URL", "")
# Ruta secreta del endpoint del webhook y secret token de Telegram.
WEBHOOK_SECRET_PATH: str = os.environ.get("WEBHOOK_SECRET_PATH", "hook")
WEBHOOK_SECRET_TOKEN: str = os.environ.get("WEBHOOK_SECRET_TOKEN", "")

# Lista de chat IDs autorizados. Vacía => acceso denegado a todos (fail closed).
_raw_allow = os.environ.get("ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHAT_IDS: set[int] = set()
if _raw_allow:
    for part in _raw_allow.split(","):
        part = part.strip()
        if part:
            try:
                ALLOWED_CHAT_IDS.add(int(part))
            except ValueError:
                pass

# Puerto interno del proceso del bot (proxiado por nginx).
PORT: int = int(os.environ.get("PORT", "8081"))

# Base de datos SQLite (dentro de data/, ignorada por git).
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "robertito.db"

# CUIT del estudio/agente de retención (para la cabecera del archivo SICORE).
# Parametrizable: Rubén debe cargar el CUIT real del agente de retención.
CUIT_AGENTE_RETENCION: str = os.environ.get("CUIT_AGENTE_RETENCION", "20000000001")


def acceso_permitido(chat_id: int) -> bool:
    """True solo si el chat figura explícitamente en la lista de IDs autorizados."""
    return bool(ALLOWED_CHAT_IDS) and chat_id in ALLOWED_CHAT_IDS


# =========================================================================
# ESCALA DE RETENCIÓN — Impuesto a las Ganancias (Régimen General RG 830 AFIP)
# =========================================================================
# IMPORTANTE (parametrizable):
#   Los valores de esta escala son ILUSTRATIVOS y DEBEN validarse/actualizarse
#   con la normativa vigente (RG 830 AFIP y sus modificatorias, Anexo VIII).
#   El esquema general del Régimen General es:
#     retención = monto_fijo + alicuota * (base_sujeta - excedente_sobre)
#   donde la base_sujeta es el pago menos el "mínimo no sujeto a retención".
#
#   Rubén puede ajustar libremente:
#     - El mínimo no sujeto a retención por concepto.
#     - Los tramos (desde/hasta), el monto fijo, la alícuota y el excedente.
#     - El importe mínimo de retención (por debajo del cual no se retiene).
#
# La estructura permite definir distintos CONCEPTOS. Por defecto usamos
# "servicios" (locaciones de obra y servicios no ejecutados en relación de
# dependencia), que es el caso más común para clientes del estudio.
# -------------------------------------------------------------------------

ESCALA_RETENCION: dict = {
    "concepto_default": "servicios",
    "conceptos": {
        "servicios": {
            "descripcion": "Locaciones de obra y/o servicios (Anexo VIII RG 830)",
            # Mínimo no sujeto a retención: si el pago no lo supera, no se retiene.
            "minimo_no_sujeto": 67170.00,
            # Importe mínimo de retención: si la retención calculada es menor, no se retiene.
            "retencion_minima": 0.00,
            # Tramos sobre la BASE SUJETA (= pago - minimo_no_sujeto).
            # Cada tramo: desde/hasta de la base, monto fijo, alicuota sobre excedente,
            # y el valor "excedente_sobre" (base a partir de la cual aplica la alícuota).
            "tramos": [
                {"desde": 0.00,       "hasta": 5000.00,    "fijo": 0.00,     "alicuota": 0.02, "excedente_sobre": 0.00},
                {"desde": 5000.00,    "hasta": 10000.00,   "fijo": 100.00,   "alicuota": 0.03, "excedente_sobre": 5000.00},
                {"desde": 10000.00,   "hasta": 20000.00,   "fijo": 250.00,   "alicuota": 0.05, "excedente_sobre": 10000.00},
                {"desde": 20000.00,   "hasta": 40000.00,   "fijo": 750.00,   "alicuota": 0.07, "excedente_sobre": 20000.00},
                {"desde": 40000.00,   "hasta": 80000.00,   "fijo": 2150.00,  "alicuota": 0.10, "excedente_sobre": 40000.00},
                {"desde": 80000.00,   "hasta": None,       "fijo": 6150.00,  "alicuota": 0.12, "excedente_sobre": 80000.00},
            ],
        },
    },
}
