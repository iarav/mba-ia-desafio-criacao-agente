"""Valida a mecânica de confirmação/retomada SEM chave Gemini.

Usa um modelo fake que emite a tool ``criar_reserva`` e verifica, contra o
código real de ``aurora/runtime.py``, que:

- o pedido de confirmação vira uma pendência na API;
- aprovar re-executa a tool e grava exatamente uma reserva;
- negar não grava nada;
- reenviar o id dá 409.

Isto prova a parte mais arriscada (retomada) sem gastar chave. O comportamento
de linguagem do modelo real ainda exige a chave Gemini.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk.tools import FunctionTool
from google.genai import types

from aurora import conf, runtime, storage
from aurora.storage import seed
from aurora.tools import reservas as reservas_tools


class FakeModel(BaseLlm):
    """Modelo fake: emite ``criar_reserva`` para pedido novo e texto na retomada."""

    def __init__(self) -> None:
        super().__init__(model="fake")
        self._n = 0

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        del stream
        last = llm_request.contents[-1] if llm_request.contents else None
        eh_retomada = bool(
            last and last.parts and any(part.function_response for part in last.parts)
        )
        if eh_retomada:
            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text="Concluído.")])
            )
        else:
            self._n += 1
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id=f"fc-teste-{self._n}",
                                name="criar_reserva",
                                args={"area": "salao-de-festas", "data": "2030-04-20"},
                            )
                        )
                    ],
                )
            )


def _montar_runner() -> Runner:
    agent = LlmAgent(
        name="teste",
        model=FakeModel(),
        tools=[FunctionTool(reservas_tools.criar_reserva)],
    )
    app = App(
        name=conf.APP_NAME,
        root_agent=agent,
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
    tmp = tempfile.mktemp(suffix=".db")
    return Runner(
        app=app,
        session_service=SqliteSessionService(db_path=tmp),
        artifact_service=InMemoryArtifactService(),
    )


def main() -> None:
    seed.restaurar()
    runtime._runner = _montar_runner()

    async def fluxo():
        sid = await runtime.criar_sessao("101")

        def tem_salao() -> int:
            return sum(
                1
                for x in storage.reservas.por_apartamento("101")
                if x["area"] == "salao-de-festas" and x["data"] == "2030-04-20"
            )

        r = await runtime.enviar_mensagem(sid, "Reserve o salão para 2030-04-20.")
        pend = r["confirmacoes_pendentes"]
        print("pendências:", pend)
        assert len(pend) == 1, "esperava 1 confirmação pendente"
        assert pend[0]["detalhes"] == {"area": "salao-de-festas", "data": "2030-04-20"}, pend[0]["detalhes"]
        cid = pend[0]["id"]

        # Antes de aprovar: nada gravado do salão.
        assert tem_salao() == 0, "não devia gravar antes de aprovar"

        # Negar não grava.
        await runtime.responder_confirmacao(sid, cid, False)
        assert tem_salao() == 0, "negar não devia gravar"

        # Novo pedido -> nova pendência -> aprovar grava uma vez.
        r2 = await runtime.enviar_mensagem(sid, "Reserve o salão para 2030-04-20.")
        cid2 = r2["confirmacoes_pendentes"][0]["id"]
        await runtime.responder_confirmacao(sid, cid2, True)
        assert tem_salao() == 1, f"esperava 1 reserva do salão, veio {storage.reservas.por_apartamento('101')}"

        # Reenviar o mesmo id -> 409 (ConfirmacaoNaoEncontrada).
        try:
            await runtime.responder_confirmacao(sid, cid2, True)
            raise AssertionError("reenvio devia dar 409")
        except runtime.ConfirmacaoNaoEncontrada:
            pass

        print("OK: aprovar grava 1x, negar não grava, reenvio 409.")

    asyncio.run(fluxo())


if __name__ == "__main__":
    main()
