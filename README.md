# Assistente virtual do Residencial Aurora

Assistente de condomínio construído com **Google ADK** (série 2), exposto por uma
**API em Python (FastAPI)** em `http://localhost:8000`. O morador reserva áreas
comuns, cancela as próprias reservas, autoriza visitantes e tira dúvidas do
regulamento — e nenhuma mensagem consegue furar as regras do condomínio.

A filosofia da entrega cabe numa frase: **o modelo decide o caminho, o código
decide o que é permitido.**

---

## Arquitetura

O assistente tem um **agente principal** e **três especialistas**, todos
`LlmAgent` do ADK com modelo Gemini (`gemini-2.5-flash`).

| Agente | Responsabilidade | Como é acionado | Por quê |
|---|---|---|---|
| `principal` | recebe o morador e roteia | agente raiz do `App` | manter o apartamento da sessão longe da conversa e não misturar competências |
| `reservas` | reservar, cancelar e consultar reservas/disponibilidade | `transfer_to_agent` (sub-agent) | isolar a leitura/escrita de reservas em tools próprias |
| `visitantes` | autorizar entrada de visitantes | `transfer_to_agent` (sub-agent) | a autorização tem regra e confirmação próprias |
| `regulamento` | responder dúvidas consultando `dados/regulamento.md` | `transfer_to_agent` (sub-agent) | manter o texto longo fora do agente principal e da janela de contexto |

Os agentes são declarados em [`aurora/agents/build.py`](aurora/agents/build.py).
O principal lista os três especialistas em `sub_agents` (o ADK os expõe como
ferramenta de transferência) e **não recebe o regulamento nas instruções**.

Reservas e visitantes são lidos e gravados **por tools** que acessam o SQLite do
condomínio — nunca por algo que o modelo lembra ou inventa. As tools estão em
[`aurora/tools/`](aurora/tools/) e a persistência em [`aurora/storage/`](aurora/storage/).

```
morador ──► POST /sessoes/{id}/mensagens
              │  Runner (ADK) com sessão SQLite persistida
              ▼
          principal ──transfer──► reservas ──tools──► storage (SQLite)
                             ├──► visitantes ──tool──► storage
                             └──► regulamento ──tool──► dados/regulamento.md
```

---

## Garantias

As cinco garantias são implementadas em código, nunca no prompt. Arquivo e
trecho de cada uma:

### Garantia 1 — cobrança ou acesso só com confirmação

Ações que geram cobrança (reservar área com taxa) ou liberam acesso (visitante)
ficam pendentes até a rota de confirmações.

- `criar_reserva` pede confirmação **somente** quando a área tem taxa
  ([`aurora/tools/reservas.py`](aurora/tools/reservas.py#L44) → `tool_context.request_confirmation`); a
  quadra (taxa 0) grava direto, sem confirmação.
- `autorizar_visitante` sempre pede confirmação
  ([`aurora/tools/visitantes.py`](aurora/tools/visitantes.py#L19)).
- A retomada está em [`aurora/runtime.py`](aurora/runtime.py#L135): ao responder a
  confirmação, a API devolve um `FunctionResponse` do `adk_request_confirmation`
  ao Runner, que re-executa a tool exatamente uma vez. Reenvio do mesmo id ou id
  inexistente recebe `409` (a pendência é removida antes da retomada).
- A rota está em [`aurora/api/routes.py`](aurora/api/routes.py#L39).

Por que não depende do modelo: a pendência nasce de `request_confirmation`
(mecanismo do ADK, não de uma instrução), a ação só executa quando
`tool_confirmation.confirmed` é `True`, e o id é validado na rota contra a
pendência gravada no banco — escrever "já confirmo aqui" na conversa não faz
nada.

### Garantia 2 — cada sessão pertence a um apartamento

O apartamento é definido **uma vez**, na criação da sessão, e fica no estado da
sessão.

- [`aurora/runtime.py`](aurora/runtime.py#L97) grava `state={"apartamento": ...}` ao criar a sessão.
- As tools leem o apartamento de `tool_context.state["apartamento"]`
  ([`aurora/tools/reservas.py`](aurora/tools/reservas.py#L25), [`aurora/tools/visitantes.py`](aurora/tools/visitantes.py#L20)).
- **Nenhuma tool tem parâmetro `apartamento`**: o modelo não escolhe o
  apartamento; ele vem da sessão e é validado por construção.
- Disponibilidade devolve só `livre`/`ocupada`, nunca o dono
  ([`aurora/tools/reservas.py`](aurora/tools/reservas.py#L30)); cancelamento só
  age sobre reservas do próprio apartamento ([`aurora/storage/reservas.py`](aurora/storage/reservas.py#L59)).

### Garantia 3 — nada se perde no reinício

A sessão é persistida em SQLite pelo próprio ADK, e os dados do condomínio em
SQLite.

- [`aurora/agents/build.py`](aurora/agents/build.py#L126) usa `SqliteSessionService` (arquivo
  `data/sessoes.db`), então os eventos sobrevivem ao reinício da API.
- Reservas e visitantes ficam em `data/condominio.db`
  ([`aurora/storage/db.py`](aurora/storage/db.py)).

### Garantia 4 — o regulamento é consultado, não carregado

O regulamento nunca entra nas instruções do agente principal, e a tool devolve
só o capítulo do assunto.

- O principal não menciona o regulamento em `instruction`
  ([`aurora/agents/build.py`](aurora/agents/build.py#L105)).
- [`aurora/tools/regulamento.py`](aurora/tools/regulamento.py#L37) divide o arquivo por capítulo e
  retorna apenas o(s) capítulo(s) que tratam do `assunto` — nenhum evento carrega
  capítulos de outros temas.

### Garantia 5 — dois moradores, uma reserva

A exclusividade vale **no instante da gravação**, não numa conferência anterior.

- Índice único parcial em [`aurora/storage/db.py`](aurora/storage/db.py#L31):
  `UNIQUE (area, data) WHERE ativa = 1`.
- [`aurora/storage/reservas.py`](aurora/storage/reservas.py#L29) faz o `INSERT` e converte o
  `IntegrityError` de concorrência em `{"status": "indisponivel"}` (resposta
  normal), enquanto o código é chave primária e nunca repete (regra 5).

---

## Como rodar

### Pré-requisitos

- Python 3.12+ e [`uv`](https://docs.astral.sh/uv/).
- Chave do Google AI Studio (Gemini).

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha a chave:

```bash
cp .env.example .env
```

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | sim | chave do Google AI Studio (Gemini) |
| `AURORA_MODEL` | não | modelo Gemini (padrão `gemini-2.5-flash`) |

A chave **nunca** é versionada: `.env` está no `.gitignore` e `.env.example`
lista só os nomes das variáveis.

### Instalar dependências

```bash
uv sync
```

### Restaurar os dados iniciais

Volta reservas e visitantes ao estado de `dados/*.json` e limpa confirmações
pendentes (as sessões de conversa não são apagadas):

```bash
uv run python -m aurora.restore
```

### Subir a API

```bash
uv run uvicorn aurora.main:app --host 0.0.0.0 --port 8000
```

A API responde em `http://localhost:8000`.

### Exemplo rápido

```bash
# cria a sessão do apartamento 101
curl -s -X POST http://localhost:8000/sessoes -H 'Content-Type: application/json' \
  -d '{"apartamento":"101"}'
# → {"session_id":"..."}

# envia uma mensagem
curl -s -X POST http://localhost:8000/sessoes/<session_id>/mensagens \
  -H 'Content-Type: application/json' -d '{"texto":"Reserve a quadra para 2030-04-06"}'
```

### Contrato da API

| Rota | Descrição |
|---|---|
| `POST /sessoes` | cria a sessão (`{"apartamento":"101"}` → `201 {"session_id":"..."}`) |
| `POST /sessoes/{id}/mensagens` | envia mensagem (`{"texto":"..."}`) |
| `POST /sessoes/{id}/confirmacoes` | responde confirmação (`{"id":"...","confirmado":true}`) |
| `GET /sessoes/{id}/eventos` | lista os eventos da sessão |
| `GET /apartamentos/{n}/reservas` | reservas ativas do apartamento |
| `GET /apartamentos/{n}/visitantes` | autorizações do apartamento |

As rotas com `{id}` respondem `404` para sessão inexistente; responder uma
confirmação inexistente ou já respondida responde `409`.
