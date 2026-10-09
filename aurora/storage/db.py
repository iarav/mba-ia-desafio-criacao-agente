"""Conexão e esquema do banco SQLite do condomínio.

Garantias de concorrência que moram aqui (Garantia 5):

- O índice único parcial ``reservas(area, data) WHERE ativa = 1`` garante, no
  *instante da gravação*, que nunca existem duas reservas ativas para a mesma
  área na mesma data. Um ``INSERT`` concorrente que violar isso recebe
  ``IntegrityError``, que as tools convertem numa resposta normal ("data já
  ocupada"), sem erro de servidor.
- ``codigo`` é chave primária, então um código nunca se repete — nem de uma
  reserva cancelada (a linha cancelada permanece na tabela com ``ativa = 0``).

Usamos WAL + ``busy_timeout`` para leituras concorrentes e uma trava simples
em volta das escritas, já que as tools executam dentro do event loop async do
FastAPI/ADK e as escritas são rápidas.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

from .. import conf

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reservas (
    codigo      TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    area        TEXT NOT NULL,
    data        TEXT NOT NULL,
    ativa       INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reserva_ativa_area_data
    ON reservas(area, data) WHERE ativa = 1;

CREATE TABLE IF NOT EXISTS visitantes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento TEXT NOT NULL,
    nome        TEXT NOT NULL,
    data        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confirmacoes_pendentes (
    id                 TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    function_call_id   TEXT NOT NULL,
    function_call_name TEXT NOT NULL,
    acao               TEXT NOT NULL,
    detalhes_json      TEXT NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        conf.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(
            str(conf.CONDOMINIO_DB), check_same_thread=False
        )
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def init_db() -> None:
    """Garante que o banco e o esquema existam."""
    _get_conn()


@contextmanager
def write_tx() -> Iterator[sqlite3.Connection]:
    """Contexto serializado para escritas (Garantia 5: uma gravação por vez)."""
    conn = _get_conn()
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def read_conn() -> sqlite3.Connection:
    return _get_conn()
