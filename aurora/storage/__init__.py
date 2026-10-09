"""Camada de persistência do condomínio (SQLite).

Os submódulos são importados aqui para que ``storage.reservas``,
``storage.visitantes`` e ``storage.confirmacoes`` estejam sempre disponíveis
como atributos do pacote (usados em ``tools``, ``runtime`` e ``api``).
"""

from . import confirmacoes, db, reservas, seed, visitantes

__all__ = ["confirmacoes", "db", "reservas", "seed", "visitantes"]
