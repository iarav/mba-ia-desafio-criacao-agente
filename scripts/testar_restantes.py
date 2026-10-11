"""Valida o que falta (depois da confirmação): concorrência, reinício e piscina.

- Passo 14 (concorrência): dois moradores aprovando ao mesmo tempo -> 1 reserva.
- Passo 13 (reinício): a sessão sobrevive ao restart da API.
- Passo 12 (piscina): a resposta traz o horário de fechamento (20h).

Uso: ``uv run python scripts/testar_restantes.py``
"""

from __future__ import annotations

import concurrent.futures
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
        # --- Passo 14: concorrência ---
        s3 = client.post(f"{BASE}/sessoes", json={"apartamento": "101"}).json()["session_id"]
        s4 = client.post(f"{BASE}/sessoes", json={"apartamento": "201"}).json()["session_id"]
        r3 = client.post(f"{BASE}/sessoes/{s3}/mensagens",
                         json={"texto": "Reserve o salão de festas para 2030-05-11."}).json()
        r4 = client.post(f"{BASE}/sessoes/{s4}/mensagens",
                         json={"texto": "Reserve o salão de festas para 2030-05-11."}).json()
        assert len(r3["confirmacoes_pendentes"]) == 1 and len(r4["confirmacoes_pendentes"]) == 1, (r3, r4)
        c3, c4 = r3["confirmacoes_pendentes"][0]["id"], r4["confirmacoes_pendentes"][0]["id"]

        def aprovar(sid, cid):
            return client.post(f"{BASE}/sessoes/{sid}/confirmacoes", json={"id": cid, "confirmado": True})

        with concurrent.futures.ThreadPoolExecutor(2) as ex:
            f1, f2 = ex.submit(aprovar, s3, c3), ex.submit(aprovar, s4, c4)
            rs1, rs2 = f1.result(), f2.result()
        assert rs1.status_code == 200 and rs2.status_code == 200, (rs1.status_code, rs2.status_code)
        r101 = client.get(f"{BASE}/apartamentos/101/reservas").json()
        r201 = client.get(f"{BASE}/apartamentos/201/reservas").json()
        n = sum(1 for x in r101 + r201 if x["area"] == "salao-de-festas" and x["data"] == "2030-05-11")
        assert n == 1, f"esperava 1 reserva, veio {n}: {r101 + r201}"
        print("[PASS] concorrência: exatamente 1 reserva do salão 2030-05-11")

        # --- Passo 13: reinício ---
        sid = client.post(f"{BASE}/sessoes", json={"apartamento": "101"}).json()["session_id"]
        client.post(f"{BASE}/sessoes/{sid}/mensagens", json={"texto": "Quais são as minhas reservas?"})
        antes = len(client.get(f"{BASE}/sessoes/{sid}/eventos").json())
        _parar(proc)
        proc = _subir()
        depois = len(client.get(f"{BASE}/sessoes/{sid}/eventos").json())
        assert depois == antes, f"eventos mudaram após reinício: {antes} -> {depois}"
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens", json={"texto": "E agora, quais são as minhas reservas?"})
        assert r.status_code == 200, r.status_code
        assert len(client.get(f"{BASE}/sessoes/{sid}/eventos").json()) > depois
        print("[PASS] reinício: sessão persistiu e aceitou nova mensagem")

        # --- Passo 12: piscina ---
        r = client.post(f"{BASE}/sessoes/{sid}/mensagens",
                        json={"texto": "Até que horas a piscina funciona aos domingos?"}).json()
        assert "20h" in r["resposta"], f"resposta sem 20h: {r['resposta']}"
        print("[PASS] piscina: resposta traz 20h")

        print("\nTUDO OK — concorrência, reinício e piscina validados.")
    finally:
        _parar(proc)


if __name__ == "__main__":
    main()
