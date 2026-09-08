"""Duelo directo entre dos checkpoints. Herramienta de diagnostico.

APORTACION NUEVA de rlgym-selfplay-pool.

Existe para responder una pregunta concreta que aparecio en la calibracion de
H2: entrenar mas, bajo esta recompensa, mejora o empeora la tasa de victoria
contra el punto de partida? No forma parte de ninguna evaluacion final.

Lados alternados por indice, modo estocastico, mismas reglas de terminacion que
el resto del proyecto. Ambas politicas se cargan por ADELANTADO y en orden fijo,
para que reanudar no cambie el estado aleatorio de ninguna partida.

Con --jsonl registra cada partida (semilla, lado, resultado, pasos, hashes) y
con --resumen escribe el agregado con intervalo de Wilson al 95 %.

Uso:
    python scripts/h2/duel.py --meshes RUTA --a DIR --b DIR [--nombre-a X]
        [--nombre-b Y] [--partidas 40] [--semilla-inicial 9000]
        [--jsonl F.jsonl] [--resumen F.json] [--etiqueta TXT]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wilson(exitos: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Intervalo de Wilson al 95 %. Mas honesto que el normal con n moderado."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = exitos / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (centro - medio, centro + medio)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--nombre-a", default="A")
    ap.add_argument("--nombre-b", default="B")
    ap.add_argument("--partidas", type=int, default=40)
    ap.add_argument("--semilla-inicial", type=int, default=9000)
    ap.add_argument("--tope-pasos", type=int, default=3000)
    ap.add_argument("--jsonl", default=None)
    ap.add_argument("--resumen", default=None)
    ap.add_argument("--etiqueta", default=None)
    a = ap.parse_args()

    import numpy as np
    import torch

    from rlbot.env.rocketsim_init import asegurar_init
    from rlbot.tournament.obs import make_env
    from rlbot.tournament.policy_io import action_to_int, load_policy

    torch.set_num_threads(2)
    asegurar_init(a.meshes)

    def dim_de(c: Path) -> int:
        sd = torch.load(c / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
        wk = [k for k in sd if k.endswith("weight")]
        return int(sd[wk[0]].shape[1])

    ca, cb = Path(a.a), Path(a.b)
    da, db = dim_de(ca), dim_de(cb)
    ha, hb = sha256_archivo(ca / "PPO_POLICY.pt"), sha256_archivo(cb / "PPO_POLICY.pt")
    pa, pb = load_policy(ca, da), load_policy(cb, db)   # ambas por adelantado

    ya: set[str] = set()
    f = None
    if a.jsonl:
        p = Path(a.jsonl)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            for ln in p.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    ya.add(json.loads(ln)["id"])
        f = p.open("a", encoding="utf-8")

    entornos: dict[tuple[int, int], object] = {}
    v = d = e = inc = 0
    for i in range(a.partidas):
        sem = a.semilla_inicial + i
        pid = f"{a.nombre_a}-vs-{a.nombre_b}-{sem}"
        a_azul = (i % 2 == 0)
        az_dim, na_dim = (da, db) if a_azul else (db, da)
        clave = (az_dim, na_dim)
        if clave not in entornos:
            entornos[clave] = make_env(az_dim, na_dim)
        env = entornos[clave]

        np.random.seed(sem)
        torch.manual_seed(sem)
        try:
            env.action_space.seed(sem)
        except Exception:  # noqa: BLE001
            pass

        p_az, p_na = (pa, pb) if a_azul else (pb, pa)
        obs = env.reset()
        pasos, res, causa = 0, None, "incompleta"
        with torch.no_grad():
            while pasos < a.tope_pasos:
                x_az, _ = p_az.get_action(obs[0], deterministic=False)
                x_na, _ = p_na.get_action(obs[1], deterministic=False)
                obs, _, done, info = env.step(
                    np.asarray([[action_to_int(x_az)], [action_to_int(x_na)]]))
                pasos += 1
                if done:
                    r = int((info or {}).get("result", 0))
                    res, causa = r, ("gol" if r != 0 else "tiempo")
                    break
        if causa == "incompleta":
            inc += 1
            resultado = "incompleta"
        elif res == 0:
            e += 1
            resultado = "empate"
        elif (res > 0) == a_azul:
            v += 1
            resultado = "victoria"
        else:
            d += 1
            resultado = "derrota"

        if f is not None and pid not in ya:
            f.write(json.dumps({
                "id": pid, "etiqueta": a.etiqueta,
                "a": a.nombre_a, "b": a.nombre_b,
                "hash_a": ha, "hash_b": hb,
                "semilla_partida": sem,
                "lado_a": "azul" if a_azul else "naranja",
                "modo": "estocastico", "resultado": resultado,
                "causa_terminacion": causa, "pasos": pasos,
            }, ensure_ascii=False) + "\n")
            f.flush()
    if f is not None:
        f.close()

    comp = v + d + e
    tasa = (v / comp) if comp else float("nan")
    lo, hi = wilson(v, comp)
    print(f"  {a.nombre_a} vs {a.nombre_b}: {v}V {d}D {e}E {inc}I "
          f"-> tasa de {a.nombre_a} = {tasa*100:.1f}%  IC95 Wilson "
          f"[{lo*100:.1f}%, {hi*100:.1f}%]  ({comp} completas)")

    if a.resumen:
        Path(a.resumen).parent.mkdir(parents=True, exist_ok=True)
        Path(a.resumen).write_text(json.dumps({
            "etiqueta": a.etiqueta, "a": a.nombre_a, "b": a.nombre_b,
            "hash_a": ha, "hash_b": hb,
            "partidas": a.partidas, "victorias": v, "derrotas": d,
            "empates": e, "incompletas": inc, "completas": comp,
            "tasa": tasa, "ic95_wilson": [lo, hi],
            "semillas": [a.semilla_inicial, a.semilla_inicial + a.partidas - 1],
            "lados": "alternados por indice",
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
