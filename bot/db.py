"""
Persistencia mínima en SQLite para registrar las retenciones calculadas.

El archivo vive en data/robertito.db (ignorado por git). Las retenciones
acumuladas se usan para construir el archivo de importación de SICORE.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retenciones (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL,   -- ISO (YYYY-MM-DD) de la operación/pago
    monto_base    REAL    NOT NULL,   -- monto del pago/operación
    retencion     REAL    NOT NULL,   -- retención practicada
    cuit_opcional TEXT,               -- CUIT del sujeto retenido (opcional)
    periodo       TEXT    NOT NULL,   -- período fiscal MMYYYY (p.ej. 112026)
    chat_id       INTEGER,            -- quién la cargó (trazabilidad)
    creado_en     TEXT    NOT NULL    -- timestamp de alta
);
CREATE INDEX IF NOT EXISTS idx_retenciones_periodo ON retenciones(periodo);
"""


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def registrar_retencion(
    monto_base: float,
    retencion: float,
    periodo: str,
    cuit_opcional: str | None = None,
    fecha: str | None = None,
    chat_id: int | None = None,
) -> int:
    """Inserta una retención. `periodo` en formato MMYYYY. Devuelve el id."""
    fecha = fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    creado = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO retenciones
               (fecha, monto_base, retencion, cuit_opcional, periodo, chat_id, creado_en)
               VALUES (?,?,?,?,?,?,?)""",
            (fecha, monto_base, retencion, cuit_opcional, periodo, chat_id, creado),
        )
        conn.commit()
        return int(cur.lastrowid)


def listar_por_periodo(periodo: str) -> list[sqlite3.Row]:
    """Devuelve las retenciones de un período (MMYYYY), ordenadas por fecha."""
    with _connect() as conn:
        cur = conn.execute(
            "SELECT * FROM retenciones WHERE periodo = ? ORDER BY fecha, id",
            (periodo,),
        )
        return cur.fetchall()


def contar_por_periodo(periodo: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) AS n FROM retenciones WHERE periodo = ?", (periodo,)
        )
        return int(cur.fetchone()["n"])
