"""
Lógica de conversación del bot Robertito.

Dispatcher de updates de Telegram (webhook). Mantiene un estado de conversación
simple por chat (en memoria) para los flujos guiados de "Clientes" y "Estudio".
Todos los textos están en español rioplatense.
"""
from __future__ import annotations

import logging

from . import config, db, retencion, sicore, telegram_api as tg

log = logging.getLogger("robertito.handlers")

# Estado de conversación por chat_id: {"flujo": ..., "paso": ..., "datos": {...}}
_estado: dict[int, dict] = {}

MSG_SIN_ACCESO = (
    "🔒 Este chat no está habilitado para usar Robertito.\n"
    "Pedile acceso al estudio para habilitarlo."
)


def _teclado_inicio() -> dict:
    """Teclado inline del mensaje de bienvenida (Clientes / Estudio / Mini App)."""
    botones = [
        [{"text": "🧾 Clientes · Retención de Ganancias", "callback_data": "clientes"}],
        [{"text": "📊 Estudio · Archivo SICORE", "callback_data": "estudio"}],
    ]
    if config.WEBAPP_URL:
        botones.append([{"text": "🤖 Abrir Robertito (Mini App)",
                         "web_app": {"url": config.WEBAPP_URL}}])
    return {"inline_keyboard": botones}


def _bienvenida(chat_id: int) -> None:
    texto = (
        "👋 ¡Hola! Soy *Robertito*, tu asistente contable.\n\n"
        "Elegí qué querés hacer:\n"
        "• 🧾 *Clientes*: calcular una retención de Ganancias.\n"
        "• 📊 *Estudio*: solicitar el archivo mensual para SICORE.\n\n"
        "También podés abrir la Mini App con el botón de abajo."
    )
    tg.send_message(chat_id, texto, reply_markup=_teclado_inicio())


# ---------------------------------------------------------------------------
# Flujos
# ---------------------------------------------------------------------------
def _iniciar_clientes(chat_id: int) -> None:
    _estado[chat_id] = {"flujo": "clientes", "paso": "monto", "datos": {}}
    tg.send_message(
        chat_id,
        "🧾 *Retención de Ganancias*\n\n"
        "Ingresá el *monto del pago/operación* (en pesos).\n"
        "Ejemplo: `150000` o `150000,50`.\n\n"
        "Escribí /cancelar para salir.",
    )


def _iniciar_estudio(chat_id: int) -> None:
    _estado[chat_id] = {"flujo": "estudio", "paso": "periodo", "datos": {}}
    actual = sicore.periodo_actual()
    mm, yyyy = actual[:2], actual[2:]
    tg.send_message(
        chat_id,
        "📊 *Archivo mensual para SICORE*\n\n"
        f"Indicá el *período* (MM/AAAA). Por defecto el mes corriente: *{mm}/{yyyy}*.\n"
        "Enviá /actual para usar el mes corriente, o escribí el período (p.ej. `10/2026`).\n\n"
        "Escribí /cancelar para salir.",
    )


def _parse_monto(texto: str) -> float | None:
    t = texto.strip().replace("$", "").replace(" ", "")
    # Soporta formato argentino (1.234,56) y simple (1234.56 / 1234)
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        val = float(t)
        return val if val >= 0 else None
    except ValueError:
        return None


def _procesar_clientes(chat_id: int, texto: str, est: dict) -> None:
    paso = est["paso"]
    if paso == "monto":
        monto = _parse_monto(texto)
        if monto is None:
            tg.send_message(chat_id,
                            "⚠️ No entendí el monto. Ingresá un número, p.ej. `150000`.")
            return
        est["datos"]["monto"] = monto
        est["paso"] = "cuit"
        tg.send_message(
            chat_id,
            "¿Tenés el *CUIT* del sujeto retenido? (opcional)\n"
            "Enviá el CUIT (11 dígitos) o /omitir para continuar sin CUIT.",
        )
        return

    if paso == "cuit":
        cuit = None
        if texto.strip().lower() not in ("/omitir", "omitir", "-", "no"):
            digitos = "".join(ch for ch in texto if ch.isdigit())
            if len(digitos) != 11:
                tg.send_message(chat_id,
                                "⚠️ El CUIT debe tener 11 dígitos. "
                                "Reenvialo o escribí /omitir.")
                return
            cuit = digitos
        est["datos"]["cuit"] = cuit
        _finalizar_clientes(chat_id, est)
        return


def _finalizar_clientes(chat_id: int, est: dict) -> None:
    monto = est["datos"]["monto"]
    cuit = est["datos"].get("cuit")
    try:
        res = retencion.calcular_retencion(monto)
    except ValueError as exc:
        tg.send_message(chat_id, f"⚠️ {exc}")
        _estado.pop(chat_id, None)
        return

    periodo = sicore.periodo_actual()
    db.registrar_retencion(
        monto_base=res.base, retencion=res.retencion, periodo=periodo,
        cuit_opcional=cuit, chat_id=chat_id,
    )
    desglose = retencion.formatear_desglose(res)
    desglose += "\n\n_Cálculo registrado para el archivo SICORE del período._"
    tg.send_message(chat_id, desglose)
    _estado.pop(chat_id, None)


def _procesar_estudio(chat_id: int, texto: str, est: dict) -> None:
    t = texto.strip().lower()
    if t in ("/actual", "actual"):
        periodo = sicore.periodo_actual()
    else:
        periodo = sicore.normalizar_periodo(texto)
        if periodo is None:
            tg.send_message(chat_id,
                            "⚠️ Período inválido. Usá el formato MM/AAAA (p.ej. `10/2026`) "
                            "o enviá /actual.")
            return
    _enviar_sicore(chat_id, periodo)
    _estado.pop(chat_id, None)


def _enviar_sicore(chat_id: int, periodo: str) -> None:
    nombre, contenido, es_plantilla = sicore.generar_archivo_sicore(periodo)
    n = db.contar_por_periodo(periodo)
    mm, yyyy = periodo[:2], periodo[2:]
    if es_plantilla:
        caption = (
            f"📄 *SICORE {mm}/{yyyy}* — _plantilla de ejemplo_\n"
            "No hay retenciones cargadas en este período, así que te mando un "
            "archivo de ejemplo con la estructura de registro (ancho fijo)."
        )
    else:
        caption = (
            f"📄 *SICORE {mm}/{yyyy}*\n"
            f"Archivo generado con *{n}* retención(es) acumulada(s) del período."
        )
    tg.send_document(chat_id, nombre, contenido, caption=caption)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
def _manejar_comando(chat_id: int, texto: str) -> bool:
    """Procesa comandos globales. Devuelve True si consumió el mensaje."""
    cmd = texto.strip().split()[0].lower().lstrip("/")
    cmd = cmd.split("@")[0]
    if cmd == "cancelar":
        _estado.pop(chat_id, None)
        tg.send_message(chat_id, "Operación cancelada. Escribí /start cuando quieras.")
        return True
    if cmd == "ayuda" or cmd == "help":
        _bienvenida(chat_id)
        return True
    return False


def _manejar_start(chat_id: int, texto: str) -> None:
    partes = texto.split(maxsplit=1)
    param = partes[1].strip().lower() if len(partes) > 1 else ""
    if param == "clientes":
        _iniciar_clientes(chat_id)
    elif param == "estudio":
        _iniciar_estudio(chat_id)
    else:
        _estado.pop(chat_id, None)
        _bienvenida(chat_id)


def procesar_update(update: dict) -> None:
    """Punto de entrada: recibe un update de Telegram y actúa."""
    # Callback (botones inline)
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq.get("data", "")
        tg.answer_callback_query(cq["id"])
        if not config.acceso_permitido(chat_id):
            tg.send_message(chat_id, MSG_SIN_ACCESO)
            return
        if data == "clientes":
            _iniciar_clientes(chat_id)
        elif data == "estudio":
            _iniciar_estudio(chat_id)
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    texto = msg.get("text", "") or ""

    if not config.acceso_permitido(chat_id):
        tg.send_message(chat_id, MSG_SIN_ACCESO)
        return

    if texto.startswith("/start"):
        _manejar_start(chat_id, texto)
        return

    if texto.startswith("/"):
        if _manejar_comando(chat_id, texto):
            return
        # comandos de flujo (/omitir, /actual) se manejan dentro del flujo activo

    est = _estado.get(chat_id)
    if est:
        if est["flujo"] == "clientes":
            _procesar_clientes(chat_id, texto, est)
        elif est["flujo"] == "estudio":
            _procesar_estudio(chat_id, texto, est)
        return

    # Sin estado ni comando reconocido: mostrar bienvenida.
    _bienvenida(chat_id)
