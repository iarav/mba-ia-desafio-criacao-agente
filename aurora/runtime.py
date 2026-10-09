"""Ponte entre a API e o ADK: sessão, execução e confirmações.

Aqui mora a mecânica de *retomada de confirmação* (Garantia 1). Quando uma tool
pede confirmação, o ADK emite um ``FunctionCall`` de nome ``adk_request_confirmation``
(com ``originalFunctionCall`` nos argumentos). Registramos essa pendência num id
próprio e, quando o morador responde pela rota de confirmações, devolvemos ao
Runner um ``FunctionResponse`` com esse mesmo id — o Runner (com
``ResumabilityConfig.is_resumable``) roteia a resposta de volta ao especialista
que pediu a confirmação, que então grava (ou não) exatamente uma vez.
"""

from __future__ import annotations

import uuid
from typing import Any

from google.genai import types

from . import conf, storage
from .agents.build import build_runner

REQUISICAO_CONFIRMACAO = "adk_request_confirmation"


class SessaoNaoEncontrada(Exception):
    """Sessão inexistente (vira 404 na API)."""


class ConfirmacaoNaoEncontrada(Exception):
    """Confirmação inexistente ou já respondida nesta sessão (vira 409)."""


_runner = None


def get_runner():
    global _runner
    if _runner is None:
        _runner = build_runner()
    return _runner


def _texto_do_evento(event) -> list[str]:
    """Extrai os trechos de texto de um evento (ignora chamadas/respostas de tool)."""
    partes = []
    if not event.content or not event.content.parts:
        return partes
    for part in event.content.parts:
        if getattr(part, "text", None):
            partes.append(part.text)
    return partes


def _acao_e_detalhes(original_name: str, original_args: dict[str, Any]):
    """Mapeia a tool original para a ação e os detalhes expostos na API."""
    if original_name == "criar_reserva":
        return "reservar_area", {
            "area": original_args.get("area"),
            "data": original_args.get("data"),
        }
    if original_name == "autorizar_visitante":
        return "autorizar_visitante", {
            "nome": original_args.get("nome"),
            "data": original_args.get("data"),
        }
    return original_name, dict(original_args)


def _registrar_confirmacoes(events, session_id: str) -> None:
    """Varre os eventos do turno e registra as confirmações pendentes.

    Cada ``adk_request_confirmation`` vira uma pendência com id próprio,
    persistida (para sobreviver a reinício) junto do ``function_call_id`` usado
    na retomada.
    """
    for event in events:
        for fc in event.get_function_calls() or []:
            if fc.name != REQUISICAO_CONFIRMACAO:
                continue
            args = fc.args or {}
            original = args.get("originalFunctionCall") or {}
            original_name = original.get("name", "")
            original_args = original.get("args") or {}
            acao, detalhes = _acao_e_detalhes(original_name, original_args)
            storage.confirmacoes.criar(
                id=str(uuid.uuid4()),
                session_id=session_id,
                function_call_id=fc.id,
                function_call_name=fc.name,
                acao=acao,
                detalhes=detalhes,
            )


async def _executar(session_id: str, content: types.Content) -> str:
    """Executa um turno do Runner e devolve o texto final acumulado."""
    runner = get_runner()
    textos: list[str] = []
    eventos: list[Any] = []
    async for event in runner.run_async(
        user_id=conf.USER_ID, session_id=session_id, new_message=content
    ):
        eventos.append(event)
        textos.extend(_texto_do_evento(event))
    _registrar_confirmacoes(eventos, session_id)
    return "\n".join(t for t in textos if t).strip()


async def criar_sessao(apartamento: str) -> str:
    """Cria a sessão ADK com o apartamento no estado (Garantia 2)."""
    runner = get_runner()
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=conf.USER_ID,
        state={"apartamento": apartamento},
    )
    return session.id


async def _exige_sessao(session_id: str) -> None:
    runner = get_runner()
    session = await runner.session_service.get_session(
        app_name=runner.app_name, user_id=conf.USER_ID, session_id=session_id
    )
    if session is None:
        raise SessaoNaoEncontrada(session_id)


async def enviar_mensagem(session_id: str, texto: str) -> dict[str, Any]:
    await _exige_sessao(session_id)
    content = types.Content(role="user", parts=[types.Part(text=texto)])
    resposta = await _executar(session_id, content)
    return {
        "resposta": resposta,
        "confirmacoes_pendentes": storage.confirmacoes.por_sessao(session_id),
    }


async def responder_confirmacao(
    session_id: str, cid: str, confirmado: bool
) -> dict[str, Any]:
    await _exige_sessao(session_id)
    registro = storage.confirmacoes.buscar(cid, session_id)
    if registro is None:
        raise ConfirmacaoNaoEncontrada(cid)

    # Remove antes de retomar: reenvio do mesmo id passa a dar 409.
    storage.confirmacoes.remover(cid, session_id)

    function_response = types.FunctionResponse(
        id=registro["function_call_id"],
        name=registro["function_call_name"],
        response={"confirmed": confirmado},
    )
    content = types.Content(
        role="user", parts=[types.Part(function_response=function_response)]
    )
    resposta = await _executar(session_id, content)
    return {
        "resposta": resposta,
        "confirmacoes_pendentes": storage.confirmacoes.por_sessao(session_id),
    }


async def listar_eventos(session_id: str) -> list[dict[str, Any]]:
    await _exige_sessao(session_id)
    runner = get_runner()
    session = await runner.session_service.get_session(
        app_name=runner.app_name, user_id=conf.USER_ID, session_id=session_id
    )
    return [event.model_dump(mode="json", exclude_none=True) for event in session.events]
