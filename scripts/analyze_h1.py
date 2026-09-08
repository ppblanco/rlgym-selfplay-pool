"""Analisis de H1 con el criterio congelado. Todo se lee del JSONL.

APORTACION NUEVA de rlgym-selfplay-pool.

CRITERIO CONGELADO (protocolo 8ae06382..., escrito ANTES de entrenar):

  A FAVOR  solo si los CUATRO a la vez:
    1. el IC bootstrap 95 % de la diferencia B-A EXCLUYE el 0
    2. la magnitud supera el rango entre semillas de ambos brazos
    3. el signo es consistente en >= 2 de 3 semillas
    4. el signo es consistente en >= 2 de 3 rivales
  EN CONTRA      los mismos cuatro con el signo invertido
  INCONCLUYENTE  cualquier otro resultado

Convencion: la diferencia se reporta como B - A.

Las partidas INCOMPLETAS se excluyen de las tasas y se reportan aparte.
No se usan metricas de entrenamiento como prueba de calidad de juego.

Uso:
    python scripts/analyze_h1.py --jsonl FILE --salida FILE.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

N_BOOT = 10000
SEMILLA_BOOT = 20260907


def tasas(filas: list[dict]) -> dict:
    """Tasa sobre completas y sobre decisivas. Las incompletas se excluyen."""
    v = sum(1 for f in filas if f["resultado"] == "victoria")
    d = sum(1 for f in filas if f["resultado"] == "derrota")
    e = sum(1 for f in filas if f["resultado"] == "empate")
    inc = sum(1 for f in filas if f["resultado"] == "incompleta")
    completas, decisivas = v + d + e, v + d
    return {
        "partidas": len(filas), "victorias": v, "derrotas": d, "empates": e,
        "incompletas": inc, "completas": completas, "decisivas": decisivas,
        "tasa_completas": (v / completas) if completas else None,
        "tasa_decisivas": (v / decisivas) if decisivas else None,
    }


def bootstrap_dif(a_vals: list[float], b_vals: list[float]) -> dict:
    """IC 95 % de la diferencia de medias B-A por bootstrap sobre las partidas."""
    import numpy as np

    rng = np.random.default_rng(SEMILLA_BOOT)
    A, B = np.asarray(a_vals, dtype=float), np.asarray(b_vals, dtype=float)
    if A.size == 0 or B.size == 0:
        return {"dif": None, "ic95": [None, None], "excluye_cero": False}
    difs = np.empty(N_BOOT)
    for i in range(N_BOOT):
        difs[i] = rng.choice(B, B.size, replace=True).mean() - rng.choice(A, A.size, replace=True).mean()
    lo, hi = float(np.percentile(difs, 2.5)), float(np.percentile(difs, 97.5))
    return {
        "dif": float(B.mean() - A.mean()),
        "ic95": [lo, hi],
        "excluye_cero": (lo > 0) or (hi < 0),
        "n_bootstrap": N_BOOT,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    filas = [json.loads(l) for l in Path(a.jsonl).read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"  partidas registradas: {len(filas)}")

    glob = tasas(filas)
    cuadra = (glob["victorias"] + glob["derrotas"] + glob["empates"] + glob["incompletas"]) == len(filas)
    print(f"  suma V+D+E+I == registradas: {cuadra}")

    por_brazo = {b: tasas([f for f in filas if f["brazo"] == b]) for b in ("A", "B")}
    por_rival = defaultdict(dict)
    for riv in sorted({f["rival"] for f in filas}):
        for b in ("A", "B"):
            por_rival[riv][b] = tasas([f for f in filas if f["rival"] == riv and f["brazo"] == b])
    por_semilla = defaultdict(dict)
    for s in sorted({f["semilla_entrenamiento"] for f in filas}):
        for b in ("A", "B"):
            por_semilla[str(s)][b] = tasas(
                [f for f in filas if f["semilla_entrenamiento"] == s and f["brazo"] == b]
            )

    # -- vector 0/1 por partida completa, para el bootstrap ---------------
    def vector(sel) -> list[float]:
        return [1.0 if f["resultado"] == "victoria" else 0.0
                for f in filas if sel(f) and f["resultado"] != "incompleta"]

    boot_global = bootstrap_dif(vector(lambda f: f["brazo"] == "A"),
                                vector(lambda f: f["brazo"] == "B"))

    # -- criterio 2: rango entre semillas ---------------------------------
    tasas_sem = {b: [por_semilla[s][b]["tasa_completas"] for s in por_semilla
                     if por_semilla[s][b]["tasa_completas"] is not None] for b in ("A", "B")}
    rango = {b: (max(v) - min(v)) if len(v) > 1 else 0.0 for b, v in tasas_sem.items()}
    rango_max = max(rango.values()) if rango else 0.0

    # -- criterios 3 y 4: consistencia de signo ---------------------------
    def signo(x): return 0 if x is None or abs(x) < 1e-12 else (1 if x > 0 else -1)

    sig_sem = []
    for s in por_semilla:
        ta, tb = por_semilla[s]["A"]["tasa_completas"], por_semilla[s]["B"]["tasa_completas"]
        sig_sem.append(signo(tb - ta) if (ta is not None and tb is not None) else 0)
    sig_riv = []
    for r in por_rival:
        ta, tb = por_rival[r]["A"]["tasa_completas"], por_rival[r]["B"]["tasa_completas"]
        sig_riv.append(signo(tb - ta) if (ta is not None and tb is not None) else 0)

    dif = boot_global["dif"]
    s_glob = signo(dif)
    consist_sem = sum(1 for x in sig_sem if x == s_glob and x != 0)
    consist_riv = sum(1 for x in sig_riv if x == s_glob and x != 0)

    c1 = bool(boot_global["excluye_cero"])
    c2 = bool(dif is not None and abs(dif) > rango_max)
    c3 = consist_sem >= 2
    c4 = consist_riv >= 2
    todos = c1 and c2 and c3 and c4

    if todos and s_glob > 0:
        veredicto = "A FAVOR"
    elif todos and s_glob < 0:
        veredicto = "EN CONTRA"
    else:
        veredicto = "INCONCLUYENTE"

    resumen = {
        "protocolo_sha256": "8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e",
        "convencion": "diferencia = B - A, sobre tasa de victoria en partidas completas",
        "totales": glob, "totales_cuadran": cuadra,
        "por_brazo": por_brazo,
        "por_rival": {k: v for k, v in por_rival.items()},
        "por_semilla": {k: v for k, v in por_semilla.items()},
        "bootstrap_global": boot_global,
        "rango_entre_semillas": rango,
        "rango_entre_semillas_max": rango_max,
        "criterios": {
            "1_ic_excluye_cero": c1,
            "2_magnitud_supera_rango_semillas": c2,
            "3_signo_consistente_semillas": {"cumple": c3, "coincidentes": consist_sem, "signos": sig_sem},
            "4_signo_consistente_rivales": {"cumple": c4, "coincidentes": consist_riv, "signos": sig_riv},
        },
        "veredicto_H1": veredicto,
        "nota": "Las metricas de entrenamiento no se usan como prueba de calidad de juego.",
    }
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== Tasas (partidas completas) ==")
    for b in ("A", "B"):
        t = por_brazo[b]
        print(f"  {b}: {t['victorias']}V {t['derrotas']}D {t['empates']}E {t['incompletas']}I "
              f"| completas={t['tasa_completas']} decisivas={t['tasa_decisivas']}")
    print(f"\n  B - A = {dif}")
    print(f"  IC95 bootstrap = [{boot_global['ic95'][0]}, {boot_global['ic95'][1]}]")
    print(f"  rango entre semillas: A={rango['A']:.4f} B={rango['B']:.4f} (max {rango_max:.4f})")
    print("\n== Criterios congelados ==")
    print(f"  1. IC excluye 0                  : {c1}")
    print(f"  2. |dif| > rango entre semillas  : {c2}")
    print(f"  3. signo consistente en semillas : {c3} ({consist_sem}/3)")
    print(f"  4. signo consistente en rivales  : {c4} ({consist_riv}/3)")
    print(f"\n  VEREDICTO H1: {veredicto}")
    print(f"  resumen -> {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
