"""Rotas do contrato da API (ver README / enunciado)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from .. import runtime, storage
from .schemas import (
    CriarSessaoRequest,
    CriarSessaoResponse,
    EnviarMensagemRequest,
    ResponderConfirmacaoRequest,
    RespostaConversa,
)

router = APIRouter()


@router.post("/sessoes", status_code=201, response_model=CriarSessaoResponse)
async def criar_sessao(body: CriarSessaoRequest) -> CriarSessaoResponse:
    session_id = await runtime.criar_sessao(body.apartamento)
    return CriarSessaoResponse(session_id=session_id)


@router.post("/sessoes/{session_id}/mensagens", response_model=RespostaConversa)
async def enviar_mensagem(session_id: str, body: EnviarMensagemRequest) -> RespostaConversa:
    try:
        resultado = await runtime.enviar_mensagem(session_id, body.texto)
    except runtime.SessaoNaoEncontrada:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    except Exception as exc:  # ex.: 429 do Gemini (quota/rate limit)
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}")
    return RespostaConversa(**resultado)


@router.post("/sessoes/{session_id}/confirmacoes", response_model=RespostaConversa)
async def responder_confirmacao(
    session_id: str, body: ResponderConfirmacaoRequest
) -> RespostaConversa:
    try:
        resultado = await runtime.responder_confirmacao(
            session_id, body.id, body.confirmado
        )
    except runtime.SessaoNaoEncontrada:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    except runtime.ConfirmacaoNaoEncontrada:
        raise HTTPException(status_code=409, detail="Confirmação inexistente ou já respondida.")
    except Exception as exc:  # ex.: 429 do Gemini (quota/rate limit)
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}")
    return RespostaConversa(**resultado)


@router.get("/sessoes/{session_id}/eventos")
async def listar_eventos(session_id: str) -> list:
    try:
        return await runtime.listar_eventos(session_id)
    except runtime.SessaoNaoEncontrada:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.get("/apartamentos/{apartamento}/reservas")
async def reservas_do_apartamento(apartamento: str) -> list:
    return storage.reservas.por_apartamento(apartamento)


@router.get("/apartamentos/{apartamento}/visitantes")
async def visitantes_do_apartamento(apartamento: str) -> list:
    return storage.visitantes.por_apartamento(apartamento)
