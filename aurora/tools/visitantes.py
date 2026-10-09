"""Tool de autorização de visitantes (regra 3).

Toda autorização libera acesso, então sempre exige confirmação (Garantia 1).
O apartamento vem da sessão (Garantia 2).
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import ToolContext

from .. import storage


def autorizar_visitante(
    nome: str, data: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Autoriza a entrada de um visitante, no apartamento da sessão."""
    apartamento = tool_context.state["apartamento"]

    if tool_context.tool_confirmation is None:
        tool_context.request_confirmation(
            hint=f"Confirmar a entrada de {nome} no dia {data}?",
            payload={"nome": nome, "data": data},
        )
        return {"status": "pendente_confirmacao", "nome": nome, "data": data}

    if not tool_context.tool_confirmation.confirmed:
        return {"status": "negada", "nome": nome, "data": data}
    return storage.visitantes.autorizar(apartamento, nome, data)
