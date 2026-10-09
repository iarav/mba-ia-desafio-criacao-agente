"""Tools de reservas.

Garantia 2 vive aqui: o apartamento é lido de ``tool_context.state`` e nunca é
um parâmetro que o modelo escolhe. Nenhuma tool aceita um apartamento vindo da
conversa — só o apartamento fixado na criação da sessão.

Garantia 1 vive em ``criar_reserva``: área com taxa > 0 pede confirmação pelo
``tool_context.request_confirmation`` e só grava na retomada com
``tool_confirmation.confirmed == True``.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import ToolContext

from .. import areas, storage


def consultar_minhas_reservas(tool_context: ToolContext) -> dict[str, Any]:
    """Lista as reservas ativas do apartamento da sessão."""
    apartamento = tool_context.state["apartamento"]
    return {"reservas": storage.reservas.por_apartamento(apartamento)}


def consultar_disponibilidade(area: str, data: str) -> dict[str, Any]:
    """Informa se a área está livre ou ocupada na data. Nunca revela o dono."""
    if not areas.existe(area):
        return {"erro": f"Área desconhecida: {area}"}
    livre = storage.reservas.data_livre(area, data)
    return {"area": area, "data": data, "status": "livre" if livre else "ocupada"}


def criar_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """Reserva uma área para a data, no apartamento da sessão.

    Área com taxa (salão, churrasqueira) exige confirmação do morador; a quadra
    (taxa 0) não. A exclusividade é garantida na gravação (índice único).
    """
    apartamento = tool_context.state["apartamento"]

    if not areas.existe(area):
        return {"status": "erro", "mensagem": f"Área desconhecida: {area}"}

    if tool_context.tool_confirmation is None:
        # Primeira chamada da tool.
        if areas.taxa(area) > 0:
            tool_context.request_confirmation(
                hint=(
                    f"Confirmar a reserva de {areas.nome(area)} para {data}?"
                    " Essa área tem taxa e gera cobrança."
                ),
                payload={"area": area, "data": data},
            )
            return {"status": "pendente_confirmacao", "area": area, "data": data}
        # Taxa zero: grava direto, sem confirmação.
        return storage.reservas.gravar(apartamento, area, data)

    # Retomada após a resposta do morador pela rota de confirmações.
    if not tool_context.tool_confirmation.confirmed:
        return {"status": "negada", "area": area, "data": data}
    return storage.reservas.gravar(apartamento, area, data)


def cancelar_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """Cancela uma reserva do próprio apartamento, sem confirmação (regra 4).

    Só age sobre reservas do apartamento da sessão; pedidos de cancelamento de
    outro apartamento não encontram nada e não alteram nada.
    """
    apartamento = tool_context.state["apartamento"]
    return storage.reservas.cancelar(apartamento, area, data)
