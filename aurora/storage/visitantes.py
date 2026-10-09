"""Persistência de autorizações de visitantes (regra de negócio 3)."""

from __future__ import annotations

from typing import Any

from . import db


def autorizar(apartamento: str, nome: str, data: str) -> dict[str, Any]:
    """Registra a autorização de entrada de um visitante."""
    with db.write_tx() as conn:
        conn.execute(
            "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
            (apartamento, nome, data),
        )
    return {"status": "autorizado", "nome": nome, "data": data}


def por_apartamento(apartamento: str) -> list[dict[str, Any]]:
    """Autorizações de um apartamento (para a rota de verificação)."""
    conn = db.read_conn()
    rows = conn.execute(
        "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data, nome",
        (apartamento,),
    ).fetchall()
    return [{"nome": r["nome"], "data": r["data"]} for r in rows]


def limpar_tudo() -> None:
    """Remove todas as autorizações (usado pela restauração)."""
    with db.write_tx() as conn:
        conn.execute("DELETE FROM visitantes")
