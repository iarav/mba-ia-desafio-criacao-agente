"""Persistência de reservas.

Regras de negócio cobertas aqui:

- Regra 1: no máximo uma reserva *ativa* por área/data (índice único parcial).
- Regra 5: o código é gerado pelo sistema e nunca repete, nem de reserva
  cancelada (a linha cancelada permanece com ``ativa = 0``).
"""

from __future__ import annotations

import random
import sqlite3
from typing import Any

from . import db


def _gerar_codigo() -> str:
    """Gera um código novo, no formato livre exigido pela regra 5."""
    return "RSV-" + "".join(random.choices("0123456789", k=6))


def gravar(apartamento: str, area: str, data: str) -> dict[str, Any]:
    """Grava uma reserva ativa, garantindo exclusividade na escrita.

    Retorna ``{"status": "reservado", ...}`` ou ``{"status": "indisponivel"}``
    quando a data/área já está ocupada. A exclusividade vale no instante do
    ``INSERT`` (Garantia 5): o índice único parcial rejeita a segunda gravação
    concorrente com ``IntegrityError``, convertido em resposta normal.
    """
    for _ in range(5):
        codigo = _gerar_codigo()
        with db.write_tx() as conn:
            try:
                conn.execute(
                    "INSERT INTO reservas (codigo, apartamento, area, data, ativa)"
                    " VALUES (?, ?, ?, ?, 1)",
                    (codigo, apartamento, area, data),
                )
            except sqlite3.IntegrityError as exc:
                msg = str(exc)
                if "codigo" in msg:
                    # Colisão de código (improvável) — tenta outro.
                    continue
                # Colisão de área/data — data já ocupada por outra reserva.
                return {"status": "indisponivel", "area": area, "data": data}
        return {"status": "reservado", "codigo": codigo, "area": area, "data": data}

    raise RuntimeError("Não foi possível gerar um código único de reserva.")


def cancelar(apartamento: str, area: str, data: str) -> dict[str, Any]:
    """Cancela uma reserva ativa do próprio apartamento (regra 4, sem confirmação).

    Só altera reservas cujo ``apartamento`` bate com o da sessão. Se não houver
    reserva ativa do morador para aquela área/data, nada muda.
    """
    with db.write_tx() as conn:
        cur = conn.execute(
            "UPDATE reservas SET ativa = 0"
            " WHERE apartamento = ? AND area = ? AND data = ? AND ativa = 1",
            (apartamento, area, data),
        )
    if cur.rowcount:
        return {"status": "cancelada", "area": area, "data": data}
    return {"status": "nao_encontrada", "area": area, "data": data}


def por_apartamento(apartamento: str) -> list[dict[str, Any]]:
    """Reservas ativas de um apartamento (para a rota de verificação)."""
    conn = db.read_conn()
    rows = conn.execute(
        "SELECT codigo, area, data FROM reservas"
        " WHERE apartamento = ? AND ativa = 1 ORDER BY data, area",
        (apartamento,),
    ).fetchall()
    return [{"codigo": r["codigo"], "area": r["area"], "data": r["data"]} for r in rows]


def data_livre(area: str, data: str) -> bool:
    """True se não existe reserva ativa para a área/data (só livre/ocupada)."""
    conn = db.read_conn()
    row = conn.execute(
        "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND ativa = 1",
        (area, data),
    ).fetchone()
    return row is None


def _reset(apartamento: str, area: str, data: str, codigo: str) -> None:
    """Reinsere uma reserva inicial durante a restauração (uso interno)."""
    with db.write_tx() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reservas"
            " (codigo, apartamento, area, data, ativa) VALUES (?, ?, ?, ?, 1)",
            (codigo, apartamento, area, data),
        )


def limpar_tudo() -> None:
    """Remove todas as reservas (usado pela restauração)."""
    with db.write_tx() as conn:
        conn.execute("DELETE FROM reservas")
