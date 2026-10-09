"""Carrega o estado inicial do condomínio a partir de ``dados/*.json``.

Os arquivos em ``dados/`` são o estado inicial e não podem ser alterados; aqui
só os lemos e os gravamos no banco. A restauração volta reservas e visitantes
ao estado desses arquivos.
"""

from __future__ import annotations

import json
from typing import Any

from .. import conf
from . import db, reservas, visitantes


def _ler_json(nome: str) -> Any:
    caminho = conf.DADOS_DIR / nome
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def restaurar() -> None:
    """Reinicializa reservas e visitantes com os dados iniciais versionados."""
    db.init_db()
    reservas.limpar_tudo()
    visitantes.limpar_tudo()

    for r in _ler_json("reservas.json"):
        reservas._reset(
            apartamento=r["apartamento"],
            area=r["area"],
            data=r["data"],
            codigo=r["codigo"],
        )

    for v in _ler_json("visitantes.json"):
        visitantes.autorizar(
            apartamento=v["apartamento"], nome=v["nome"], data=v["data"]
        )
