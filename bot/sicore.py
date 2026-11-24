"""
Generador del archivo de importación para SICORE (aplicativo de AFIP de
retenciones y percepciones).

Genera un archivo de TEXTO de ancho fijo con el diseño de registro de
"Retenciones/Percepciones" de SICORE a partir de las retenciones acumuladas en
la base de datos. Si no hay datos del período, genera una PLANTILLA/archivo de
ejemplo con la estructura de campos para que Rubén vea el formato.

-------------------------------------------------------------------------------
DISEÑO DE REGISTRO (ancho fijo) — campo: posición(ini-fin) longitud  tipo
-------------------------------------------------------------------------------
 1. Código de comprobante ............  1- 3   (3)   numérico
 2. Fecha de emisión del comprobante .  4-13   (10)  DD/MM/AAAA
 3. Número del comprobante ...........  14-29  (16)  numérico (relleno con ceros a la izq.)
 4. Importe del comprobante ..........  30-45  (16)  numérico, 2 decimales SIN separador
 5. Código de impuesto ...............  46-49  (4)   numérico (0217 = Ganancias)
 6. Código de régimen ................  50-52  (3)   numérico
 7. Código de operación ..............  53-53  (1)   numérico (1 = retención)
 8. Base de cálculo ..................  54-67  (14)  numérico, 2 decimales SIN separador
 9. Fecha de emisión de la retención .  68-77  (10)  DD/MM/AAAA
10. Código de condición .............. 78-79  (2)   numérico
11. Retención a suj. suspendidos ..... 80-80  (1)   0/1
12. Importe de la retención .......... 81-94  (14)  numérico, 2 decimales SIN separador
13. Porcentaje de exclusión .......... 95-100 (6)   numérico, 2 decimales
14. Fecha fin de exclusión ...........101-110 (10)  DD/MM/AAAA (o ceros/espacios)
15. Tipo de documento del retenido ...111-112 (2)   numérico (80 = CUIT)
16. Número de documento del retenido .113-132 (20)  numérico (CUIT a la derecha, resto 0)
17. Número de certificado original ...133-146 (14)  numérico
-------------------------------------------------------------------------------
IMPORTANTE (parametrizable): longitudes, códigos de régimen/impuesto y formato
pueden variar según la versión del aplicativo SICORE y la normativa vigente.
Validar contra el "Diseño de registro" oficial de AFIP antes de presentar.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from . import config, db

# Códigos por defecto (parametrizables).
COD_IMPUESTO = "0217"      # Ganancias
COD_REGIMEN = "078"        # Régimen general de servicios (AJUSTAR según normativa)
COD_OPERACION = "1"        # Retención
COD_COMPROBANTE = "001"    # Factura / recibo
COD_CONDICION = "01"       # Inscripto
TIPO_DOC = "80"            # CUIT


def _num(valor: float, longitud: int) -> str:
    """Importe en centavos sin separador, relleno con ceros a la izquierda."""
    centavos = int(round(valor * 100))
    return str(centavos).rjust(longitud, "0")[:longitud]


def _entero(valor: int | str, longitud: int) -> str:
    return str(valor).rjust(longitud, "0")[:longitud]


def _fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _solo_digitos(s: str | None) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _registro(
    *,
    fecha_comprobante: date,
    nro_comprobante: str,
    importe_comprobante: float,
    base_calculo: float,
    fecha_retencion: date,
    importe_retencion: float,
    cuit_retenido: str | None,
    nro_certificado: str,
) -> str:
    cuit = _solo_digitos(cuit_retenido)
    campos = [
        _entero(COD_COMPROBANTE, 3),           # 1
        _fecha(fecha_comprobante),             # 2
        _entero(nro_comprobante, 16),          # 3
        _num(importe_comprobante, 16),         # 4
        _entero(COD_IMPUESTO, 4),              # 5
        _entero(COD_REGIMEN, 3),               # 6
        COD_OPERACION,                         # 7
        _num(base_calculo, 14),                # 8
        _fecha(fecha_retencion),               # 9
        _entero(COD_CONDICION, 2),             # 10
        "0",                                   # 11 suspendido no
        _num(importe_retencion, 14),           # 12
        _entero(0, 6),                         # 13 % exclusión
        "0" * 10,                              # 14 fecha fin exclusión
        _entero(TIPO_DOC, 2),                  # 15
        _entero(cuit, 20),                     # 16
        _entero(nro_certificado, 14),          # 17
    ]
    return "".join(campos)


def _parse_fecha(iso: str) -> date:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


def periodo_actual() -> str:
    """Período corriente en formato MMYYYY."""
    hoy = date.today()
    return f"{hoy.month:02d}{hoy.year}"


def normalizar_periodo(texto: str) -> str | None:
    """Acepta 'MM/AAAA', 'MM-AAAA' o 'MMAAAA' y devuelve 'MMYYYY', o None si inválido."""
    t = texto.strip().replace("-", "/").replace(" ", "")
    if "/" in t:
        partes = t.split("/")
        if len(partes) != 2:
            return None
        mm, yyyy = partes
    elif len(t) == 6 and t.isdigit():
        mm, yyyy = t[:2], t[2:]
    else:
        return None
    if not (mm.isdigit() and yyyy.isdigit()):
        return None
    m, y = int(mm), int(yyyy)
    if not (1 <= m <= 12 and 2000 <= y <= 2099):
        return None
    return f"{m:02d}{y}"


def generar_archivo_sicore(periodo: str | None = None) -> tuple[str, str, bool]:
    """
    Genera el contenido del archivo SICORE para un período (MMYYYY).

    Devuelve: (nombre_archivo, contenido, es_plantilla)
      - es_plantilla=True si no había datos y se generó un registro de ejemplo.
    """
    periodo = periodo or periodo_actual()
    filas = db.listar_por_periodo(periodo)

    lineas: list[str] = []
    es_plantilla = False

    if filas:
        for i, row in enumerate(filas, start=1):
            f = _parse_fecha(row["fecha"])
            lineas.append(
                _registro(
                    fecha_comprobante=f,
                    nro_comprobante=str(i),
                    importe_comprobante=float(row["monto_base"]),
                    base_calculo=float(row["monto_base"]),
                    fecha_retencion=f,
                    importe_retencion=float(row["retencion"]),
                    cuit_retenido=row["cuit_opcional"],
                    nro_certificado=str(row["id"]),
                )
            )
    else:
        # Sin datos persistidos: generar un registro de EJEMPLO (plantilla).
        es_plantilla = True
        hoy = date.today()
        lineas.append(
            _registro(
                fecha_comprobante=hoy,
                nro_comprobante="1",
                importe_comprobante=100000.00,
                base_calculo=100000.00,
                fecha_retencion=hoy,
                importe_retencion=3150.00,
                cuit_retenido="20111111112",
                nro_certificado="1",
            )
        )

    contenido = "\r\n".join(lineas) + "\r\n"
    nombre = f"SICORE_{periodo}{'_PLANTILLA' if es_plantilla else ''}.txt"
    return nombre, contenido, es_plantilla
