"""Persistência das confirmações pendentes (Garantia 1).

Cada confirmação pendente guarda o ``id`` público (o que o morador devolve na
rota de confirmações) e o ``function_call_id`` do ``adk_request_confirmation``
do ADK (usado para retomar a execução). Persistir aqui — e não só em memória —
permite retomar a aprovação mesmo depois de reiniciar a API.
"""

from __future__ import annotations

import json
from typing import Any

from . import db


def criar(
    *,
    id: str,
    session_id: str,
    function_call_id: str,
    function_call_name: str,
    acao: str,
    detalhes: dict[str, Any],
) -> None:
    with db.write_tx() as conn:
        conn.execute(
            "INSERT INTO confirmacoes_pendentes"
            " (id, session_id, function_call_id, function_call_name, acao, detalhes_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (id, session_id, function_call_id, function_call_name, acao,
             json.dumps(detalhes, ensure_ascii=False)),
        )


def buscar(id: str, session_id: str) -> dict[str, Any] | None:
    """Retorna a confirmação pendente se existir e pertencer à sessão."""
    conn = db.read_conn()
    row = conn.execute(
        "SELECT * FROM confirmacoes_pendentes WHERE id = ? AND session_id = ?",
        (id, session_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "function_call_id": row["function_call_id"],
        "function_call_name": row["function_call_name"],
        "acao": row["acao"],
        "detalhes": json.loads(row["detalhes_json"]),
    }


def por_sessao(session_id: str) -> list[dict[str, Any]]:
    """Lista as confirmações pendentes de uma sessão (para a resposta da API)."""
    conn = db.read_conn()
    rows = conn.execute(
        "SELECT id, acao, detalhes_json FROM confirmacoes_pendentes"
        " WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    return [
        {"id": r["id"], "acao": r["acao"], "detalhes": json.loads(r["detalhes_json"])}
        for r in rows
    ]


def remover(id: str, session_id: str) -> None:
    """Remove a confirmação após responder (reenvio passa a dar 409)."""
    with db.write_tx() as conn:
        conn.execute(
            "DELETE FROM confirmacoes_pendentes WHERE id = ? AND session_id = ?",
            (id, session_id),
        )


def limpar_tudo() -> None:
    with db.write_tx() as conn:
        conn.execute("DELETE FROM confirmacoes_pendentes")
