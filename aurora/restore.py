"""Comando de restauração dos dados iniciais.

Uso: ``uv run python -m aurora.restore``

Volta reservas e visitantes ao estado de ``dados/*.json`` e limpa as
confirmações pendentes. As sessões de conversa não são apagadas (decisão
documentada no README).
"""

from __future__ import annotations

from .storage import confirmacoes, seed


def main() -> None:
    seed.restaurar()
    confirmacoes.limpar_tudo()
    print("Dados restaurados a partir de dados/*.json.")


if __name__ == "__main__":
    main()
