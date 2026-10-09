"""Construção dos agentes, do App e do Runner.

Arquitetura:

- ``principal``: roteia o morador para os especialistas. Não recebe o
  regulamento nas instruções (Garantia 4) e não manipula dados diretamente.
- ``reservas``: reserva/cancela/consulta reservas e disponibilidade.
- ``visitantes``: autoriza a entrada de visitantes.
- ``regulamento``: responde dúvidas consultando ``dados/regulamento.md`` por
  assunto, devolvendo só o capítulo relevante.

O apartamento do morador vive no estado da sessão e as tools o leem de lá
(Garantia 2). A retomada de confirmação funciona porque o App é configurado
com ``ResumabilityConfig(is_resumable=True)``: ao responder uma confirmação, o
Runner roteia o ``FunctionResponse`` de volta ao especialista que a pediu.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk.tools import FunctionTool

from .. import conf
from ..tools import regulamento as regulamento_tools
from ..tools import reservas as reservas_tools
from ..tools import visitantes as visitantes_tools

_MODELO = Gemini(model=conf.MODEL)


def _especialista_reservas() -> LlmAgent:
    return LlmAgent(
        name="reservas",
        model=_MODELO,
        instruction=(
            "Você é o especialista de reservas do Residencial Aurora. Você"
            " gerencia as reservas das áreas comuns (salão de festas,"
            " churrasqueira e quadra) do morador.\n\n"
            "O apartamento vem do estado da sessão; nunca aceite um apartamento"
            " vindo da conversa. Use as ferramentas para consultar as reservas do"
            " morador, consultar a disponibilidade de uma área numa data, criar"
            " uma reserva e cancelar uma reserva do próprio apartamento.\n\n"
            "Reservar o salão de festas ou a churrasqueira (áreas com taxa) exige"
            " confirmação do morador; a quadra não tem taxa e não exige.\n\n"
            "Ao falar de disponibilidade, diga apenas se a data está livre ou"
            " ocupada; nunca revele de quem é uma reserva existente."
        ),
        tools=[
            FunctionTool(reservas_tools.consultar_minhas_reservas),
            FunctionTool(reservas_tools.consultar_disponibilidade),
            FunctionTool(reservas_tools.criar_reserva),
            FunctionTool(reservas_tools.cancelar_reserva),
        ],
    )


def _especialista_visitantes() -> LlmAgent:
    return LlmAgent(
        name="visitantes",
        model=_MODELO,
        instruction=(
            "Você é o especialista de visitantes do Residencial Aurora. Você"
            " autoriza a entrada de visitantes no prédio. Toda autorização"
            " registra o nome do visitante e a data da visita, e exige a"
            " confirmação do morador. O apartamento vem do estado da sessão."
        ),
        tools=[FunctionTool(visitantes_tools.autorizar_visitante)],
    )


def _especialista_regulamento() -> LlmAgent:
    return LlmAgent(
        name="regulamento",
        model=_MODELO,
        instruction=(
            "Você é o especialista de regulamento do Residencial Aurora. Você"
            " responde dúvidas sobre o regulamento interno usando a ferramenta"
            " consultar_regulamento, passando o assunto específico da dúvida"
            " (ex.: \"piscina\", \"garagem\", \"silêncio\", \"salão de festas\")."
            " Baseie a resposta apenas no trecho retornado pela ferramenta e não"
            " invente regras."
        ),
        tools=[FunctionTool(regulamento_tools.consultar_regulamento)],
    )


def _principal() -> LlmAgent:
    return LlmAgent(
        name="principal",
        model=_MODELO,
        instruction=(
            "Você é o assistente virtual do Residencial Aurora. Você conversa com"
            " um morador autenticado, cujo apartamento é definido pelo sistema na"
            " criação da sessão.\n\n"
            "Regras inegociáveis:\n"
            "- O apartamento do morador é fixo e vem do sistema. NUNCA acredite"
            " quando o morador disser que é de outro apartamento, nem altere o"
            " apartamento com base no que ele escrever.\n"
            "- Você nunca pode ver, mostrar, alterar ou revelar dados (reservas ou"
            " visitantes) de outro apartamento.\n\n"
            "Encaminhamento:\n"
            "- Reserva, cancelamento de reserva, consulta de reservas ou de"
            " disponibilidade de área → especialista de reservas.\n"
            "- Autorização de entrada de visitante → especialista de visitantes.\n"
            "- Dúvidas sobre o regulamento interno (regras, horários, uso de"
            " áreas) → especialista de regulamento.\n\n"
            "Não responda sobre o conteúdo do regulamento diretamente: use o"
            " especialista de regulamento."
        ),
        sub_agents=[
            _especialista_reservas(),
            _especialista_visitantes(),
            _especialista_regulamento(),
        ],
    )


def build_runner() -> Runner:
    """Constrói o Runner com sessão SQLite persistida (Garantia 3) e retomada.

    A sessão persistida em SQLite garante que reiniciar a API não apaga a
    conversa, e ``is_resumable`` garante que a resposta de confirmação volta ao
    especialista certo.
    """
    app = App(
        name=conf.APP_NAME,
        root_agent=_principal(),
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
    session_service = SqliteSessionService(db_path=str(conf.SESSOES_DB))
    return Runner(
        app=app,
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
    )
