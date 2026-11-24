"""
Cálculo de la retención de Ganancias (Régimen General RG 830 AFIP).

El cálculo es CONFIGURABLE: toma los parámetros desde bot.config.ESCALA_RETENCION.
Ver el comentario en config.py: los valores de la escala son ilustrativos y deben
validarse/actualizarse con la normativa vigente.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config


@dataclass
class ResultadoRetencion:
    base: float                 # monto del pago/operación informado
    concepto: str
    minimo_no_sujeto: float
    base_sujeta: float          # base - minimo_no_sujeto (>= 0)
    alicuota: float             # alícuota del tramo aplicado (fracción, p.ej. 0.10)
    monto_fijo: float           # monto fijo del tramo aplicado
    excedente_sobre: float      # valor a partir del cual se aplica la alícuota
    retencion: float            # retención final a practicar
    detalle_tramo: dict = field(default_factory=dict)


def calcular_retencion(base: float, concepto: str | None = None) -> ResultadoRetencion:
    """
    Calcula la retención para un pago `base` según el `concepto` de la escala.

    Fórmula del Régimen General:
        base_sujeta = max(0, base - minimo_no_sujeto)
        retencion   = monto_fijo + alicuota * (base_sujeta - excedente_sobre)

    Si la base no supera el mínimo no sujeto, o la retención queda por debajo del
    importe mínimo configurado, la retención es 0.
    """
    if base < 0:
        raise ValueError("El monto no puede ser negativo.")

    esc = config.ESCALA_RETENCION
    concepto = concepto or esc["concepto_default"]
    if concepto not in esc["conceptos"]:
        concepto = esc["concepto_default"]
    cfg = esc["conceptos"][concepto]

    minimo = float(cfg["minimo_no_sujeto"])
    base_sujeta = max(0.0, base - minimo)

    # Si no supera el mínimo no sujeto, no se retiene.
    if base_sujeta <= 0:
        return ResultadoRetencion(
            base=base, concepto=concepto, minimo_no_sujeto=minimo,
            base_sujeta=0.0, alicuota=0.0, monto_fijo=0.0, excedente_sobre=0.0,
            retencion=0.0,
            detalle_tramo={"motivo": "El pago no supera el mínimo no sujeto a retención."},
        )

    # Buscar el tramo que corresponde a la base sujeta.
    tramo = None
    for t in cfg["tramos"]:
        desde = float(t["desde"])
        hasta = t["hasta"]
        if base_sujeta >= desde and (hasta is None or base_sujeta <= float(hasta)):
            tramo = t
            break
    if tramo is None:  # fallback: último tramo
        tramo = cfg["tramos"][-1]

    fijo = float(tramo["fijo"])
    alicuota = float(tramo["alicuota"])
    excedente_sobre = float(tramo["excedente_sobre"])

    retencion = fijo + alicuota * (base_sujeta - excedente_sobre)
    retencion = max(0.0, round(retencion, 2))

    # Importe mínimo de retención.
    ret_min = float(cfg.get("retencion_minima", 0.0))
    if retencion < ret_min:
        retencion = 0.0

    return ResultadoRetencion(
        base=base, concepto=concepto, minimo_no_sujeto=minimo,
        base_sujeta=round(base_sujeta, 2), alicuota=alicuota,
        monto_fijo=fijo, excedente_sobre=excedente_sobre,
        retencion=retencion,
        detalle_tramo={
            "desde": tramo["desde"], "hasta": tramo["hasta"],
            "fijo": fijo, "alicuota": alicuota, "excedente_sobre": excedente_sobre,
        },
    )


def _fmt(n: float) -> str:
    """Formatea un número como moneda argentina: 1.234.567,89"""
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatear_desglose(r: ResultadoRetencion) -> str:
    """Devuelve el desglose del cálculo en texto (Markdown) para mostrar en el chat."""
    cfg = config.ESCALA_RETENCION["conceptos"][r.concepto]
    lineas = [
        "🧾 *Retención de Ganancias — Régimen General (RG 830)*",
        "",
        f"• Concepto: _{cfg['descripcion']}_",
        f"• Monto del pago (base): *${_fmt(r.base)}*",
        f"• Mínimo no sujeto: ${_fmt(r.minimo_no_sujeto)}",
    ]
    if r.retencion <= 0 and r.base_sujeta <= 0:
        lineas += [
            "",
            "✅ *No corresponde retención*: el pago no supera el mínimo no sujeto.",
        ]
    else:
        lineas += [
            f"• Base sujeta a retención: ${_fmt(r.base_sujeta)}",
            f"• Monto fijo del tramo: ${_fmt(r.monto_fijo)}",
            f"• Alícuota aplicada: {r.alicuota*100:.2f}%".replace(".", ","),
            f"• Excedente sobre: ${_fmt(r.excedente_sobre)}",
            "",
            f"💰 *Retención a practicar: ${_fmt(r.retencion)}*",
        ]
    lineas += [
        "",
        "_Valores de la escala parametrizables; validar con la normativa vigente._",
    ]
    return "\n".join(lineas)
