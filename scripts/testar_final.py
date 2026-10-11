"""Valida o que ainda falta, na ordem de prioridade (economizando cota).

1. Quadra sem confirmação (taxa 0 -> grava direto).
2. Piscina aos domingos -> resposta traz 20h.
3. Data já ocupada pelo 302 -> não cria e não vaza RSV-4821/302.

Uso: ``uv run python scripts/testar_final.py``
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
client = httpx.Client(timeout=180.0)


def _subir() -> subprocess.Popen:
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "aurora.main:app", "--port", "8000"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            client.get(f"{BASE}/apartamentos/101/reservas", timeout=1.0)
            return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("servidor não subiu")


def _parar(p: subprocess.Popen) -> None:
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()


def main() -> None:
    subprocess.run([sys.executable, "-m", "aurora.restore"], cwd=ROOT, check=True)
    proc = _subir()
    try:
        sid = client.post(f"{BASE}/sessoes", json={"apartamento": "101"}).json()["session_id"]

        # 1) Quadra (taxa 0) -> sem confirmação
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens",
                        json={"texto": "Reserve a quadra para 2030-04-06."}).json()
        assert r["confirmacoes_pendentes"] == [], f"quadra não devia pedir confirmação: {r}"
        rs = client.get(f"{BASE}/apartamentos/101/reservas").json()
        assert any(x["area"] == "quadra" and x["data"] == "2030-04-06" for x in rs), rs
        print("[PASS] quadra (taxa 0): reserva sem confirmação")

        # 2) Piscina aos domingos -> 20h
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens",
                        json={"texto": "Até que horas a piscina funciona aos domingos?"}).json()
        assert "20h" in r["resposta"], f"sem 20h: {r['resposta']}"
        print("[PASS] piscina: resposta traz 20h")

        # 3) Data já ocupada pelo 302 -> não cria e não vaza
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens",
                        json={"texto": "Reserve o salão de festas para 2030-03-16."}).json()
        pend = r["confirmacoes_pendentes"]
        if pend:
            client.post(f"{BASE}/sessoes/{sid}/confirmacoes", json={"id": pend[0]["id"], "confirmado": True})
        rs = client.get(f"{BASE}/apartamentos/101/reservas").json()
        assert not any(x["area"] == "salao-de-festas" and x["data"] == "2030-03-16" for x in rs), rs
        ev = client.get(f"{BASE}/sessoes/{sid}/eventos").json()
        tudo = json.dumps(ev, ensure_ascii=False) + json.dumps(r, ensure_ascii=False)
        assert "RSV-4821" not in tudo, "vazou RSV-4821"
        assert "302" not in tudo, "vazou o número 302"
        print("[PASS] data ocupada: não cria e não vaza RSV-4821/302")

        print("\nTUDO OK — quadra, piscina e data ocupada validados.")
    finally:
        _parar(proc)


if __name__ == "__main__":
    main()
