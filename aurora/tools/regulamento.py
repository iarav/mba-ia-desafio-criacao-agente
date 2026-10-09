"""Tool de consulta ao regulamento interno.

Garantia 4 vive aqui: a tool devolve apenas o capítulo do assunto consultado,
nunca o regulamento inteiro. Assim, nenhum evento da sessão carrega trechos de
capítulos sobre outros assuntos, e o custo de tokens não cresce com o texto
completo.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .. import conf


@lru_cache(maxsize=1)
def _capitulos() -> list[dict[str, str]]:
    with open(conf.DADOS_DIR / "regulamento.md", encoding="utf-8") as f:
        texto = f.read()

    # Divide em capítulos pelo marcador "## Capítulo".
    partes = re.split(r"(?=^## Capítulo)", texto, flags=re.MULTILINE)
    capitulos: list[dict[str, str]] = []
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        linhas = parte.splitlines()
        titulo = linhas[0].removeprefix("## ").strip()
        corpo = "\n".join(linhas[1:]).strip()
        capitulos.append({"titulo": titulo, "corpo": corpo})
    return capitulos


def consultar_regulamento(assunto: str) -> dict[str, Any]:
    """Retorna o(s) capítulo(s) do regulamento que tratam do ``assunto``."""
    alvo = assunto.lower().strip()
    if not alvo:
        return {"erro": "Informe um assunto para consultar o regulamento."}

    capitulos = _capitulos()
    matches = [c for c in capitulos if alvo in c["titulo"].lower()]
    if not matches:
        matches = [c for c in capitulos if alvo in c["corpo"].lower()]

    if not matches:
        return {"erro": f"Nenhum capítulo do regulamento trata de '{assunto}'."}

    return {
        "capitulos": [
            {"titulo": c["titulo"], "texto": c["corpo"]} for c in matches
        ]
    }
