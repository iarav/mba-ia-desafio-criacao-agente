"""Áreas comuns (dados estáticos de ``dados/areas.json``).

A taxa define se a reserva gera cobrança (regra 2): taxa > 0 gera cobrança e,
portanto, exige confirmação; taxa 0 não.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from . import conf


@lru_cache(maxsize=1)
def _areas() -> dict[str, dict[str, Any]]:
    with open(conf.DADOS_DIR / "areas.json", encoding="utf-8") as f:
        lista = json.load(f)
    return {a["id"]: a for a in lista}


def existe(area: str) -> bool:
    return area in _areas()


def taxa(area: str) -> float:
    a = _areas().get(area)
    return float(a["taxa"]) if a else 0.0


def nome(area: str) -> str:
    a = _areas().get(area)
    return a["nome"] if a else area
