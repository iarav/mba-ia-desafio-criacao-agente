"""Configurações centrais do assistente Aurora.

Caminhos, identificadores do app/sessão e leitura de variáveis de ambiente.
Nenhuma chave é versionada: a chave do Google AI Studio vem do ambiente
(``.env``), fora do Git.
"""

from __future__ import annotations

import os
from pathlib import Path

# Faz o Python confiar nos certificados do sistema operacional (Keychain no
# macOS, cert store no Windows, /etc/ssl no Linux). Necessário em redes com
# inspeção SSL corporativa (ex.: proxy com CA próprio), onde o bundle do
# certifi não contém o CA interno. Em ambiente limpo é inócuo.
try:
    import pip_system_certs  # noqa: F401
except Exception:  # pragma: no cover - nunca deve impedir a subida
    pass

from dotenv import load_dotenv

# Carrega `.env` se existir (fora do Git). Não falha se ausente.
load_dotenv()

# Raiz do projeto (um nível acima deste arquivo).
PROJETO_ROOT = Path(__file__).resolve().parent.parent

# Dados iniciais do condomínio (versionados, não podem mudar).
DADOS_DIR = PROJETO_ROOT / "dados"

# Estado de runtime (bancos SQLite). Fora do Git.
DATA_DIR = PROJETO_ROOT / "data"
CONDOMINIO_DB = DATA_DIR / "condominio.db"
SESSOES_DB = DATA_DIR / "sessoes.db"

# Identificadores do aplicativo ADK.
APP_NAME = "aurora"
# Um único usuário fictício: o apartamento autenticado vive no *estado da
# sessão*, então todas as sessões podem compartilhar este user_id.
USER_ID = "morador"

# Chave do Google AI Studio (Gemini). Aceita GOOGLE_API_KEY (padrão do SDK
# google-genai) ou GEMINI_API_KEY. Nunca versionada.
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
if GEMINI_API_KEY:
    # O SDK google-genai (usado pelo modelo nativo `Gemini`) lê esta variável.
    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)

# Modelo Gemini usado por todos os agentes (configurável via AURORA_MODEL).
MODEL = os.getenv("AURORA_MODEL", "gemini-2.5-flash")
