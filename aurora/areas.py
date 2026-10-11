"""Áreas comuns (dados estáticos de ``dados/areas.json``).

A taxa define se a reserva gera cobrança (regra 2): taxa > 0 gera cobrança e,
portanto, exige confirmação; taxa 0 não.

``resolver`` normaliza o nome da área vindo do modelo (ex.: "Salão de festas" ou
"salão") para o id canônico (ex.: "salao-de-festas"), para que a tool aceite a
forma como o morador escreve.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from typing import Any

from . import conf

# Apelidos -> id canônico (aplicados depois de normalizar o texto).
_ALIASES = {
    "salao": "salao-de-festas",
    "salao-de-festas": "salao-de-festas",
    "churrasqueira": "churrasqueira",
    "quadra": "quadra",
    "quadra-poliesportiva": "quadra",
}


@lru_cache(maxsize=1)
def _areas() -> dict[str, dict[str, Any]]:
    with open(conf.DADOS_DIR / "areas.json", encoding="utf-8") as f:
        lista = json.load(f)
    return {a["id"]: a for a in lista}


def _normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    return re.sub(r"[\s_]+", "-", s)


def resolver(nome: str) -> str | None:
    """Devolve o id canônico da área, ou ``None`` se desconhecida."""
    n = _normalizar(nome)
    if n in _areas():
        return n
    return _ALIASES.get(n)


def ids() -> list[str]:
    return sorted(_areas().keys())


def existe(nome: str) -> bool:
    return resolver(nome) is not None


def taxa(nome: str) -> float:
    a = _areas().get(resolver(nome) or "")
    return float(a["taxa"]) if a else 0.0


def nome(nome: str) -> str:
    a = _areas().get(resolver(nome) or "")
    return a["nome"] if a else str(nome)
