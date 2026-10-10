"""Testa SÓ a confirmação (o ponto de risco da retomada), com ~8 chamadas.

Sobe a API, cria a sessão, pede uma reserva paga (salão), confere a pendência,
aprova e confere que gravou; nega e confere que não gravou; reenvia e confere 409.

Uso: ``uv run python scripts/testar_confirmacao.py``
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
client = httpx.Client(timeout=180.0)


def main() -> None:
    subprocess.run([sys.executable, "-m", "aurora.restore"], cwd=ROOT, check=True)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "aurora.main:app", "--port", "8000"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                client.get(f"{BASE}/apartamentos/101/reservas", timeout=1.0)
                break
            except Exception:
                time.sleep(0.5)

        sid = client.post(f"{BASE}/sessoes", json={"apartamento": "101"}).json()["session_id"]

        def tem_salao(data="2030-04-20") -> int:
            rs = client.get(f"{BASE}/apartamentos/101/reservas").json()
            return sum(1 for r in rs if r["area"] == "salao-de-festas" and r["data"] == data)

        # 1) pedir reserva paga -> pendência
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens",
                        json={"texto": "Reserve o salão de festas para 2030-04-20."}).json()
        pend = r["confirmacoes_pendentes"]
        assert len(pend) == 1, f"esperava 1 pendência, veio {pend}"
        assert pend[0]["detalhes"]["area"] == "salao-de-festas", pend[0]
        print("[PASS] pendência com area/data:", pend[0]["detalhes"])
        assert tem_salao() == 0, "não devia gravar antes de aprovar"
        print("[PASS] nada gravado antes de aprovar")

        # 2) negar -> não grava
        cid_neg = pend[0]["id"]
        client.post(f"{BASE}/sessoes/{sid}/confirmacoes", json={"id": cid_neg, "confirmado": False})
        assert tem_salao() == 0, "negar não devia gravar"
        print("[PASS] negar não grava")

        # 3) novo pedido -> aprovar -> grava uma vez
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens",
                        json={"texto": "Reserve o salão de festas para 2030-04-20."}).json()
        cid_aprov = r["confirmacoes_pendentes"][0]["id"]
        client.post(f"{BASE}/sessoes/{sid}/confirmacoes", json={"id": cid_aprov, "confirmado": True})
        assert tem_salao() == 1, f"aprovar devia gravar 1 reserva, veio {client.get(f'{BASE}/apartamentos/101/reservas').json()}"
        print("[PASS] aprovar grava exatamente uma")

        # 4) reenviar o mesmo id -> 409
        rr = client.post(f"{BASE}/sessoes/{sid}/confirmacoes", json={"id": cid_aprov, "confirmado": True})
        assert rr.status_code == 409, f"reenvio devia dar 409, veio {rr.status_code}"
        print("[PASS] reenvio dá 409")

        print("\nTUDO OK — a retomada da confirmação funciona com o Gemini real.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
