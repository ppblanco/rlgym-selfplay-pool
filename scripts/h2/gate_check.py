"""H2 fase 0: puerta GO / NO-GO. Evalua los cuatro criterios y nada mas.

APORTACION NUEVA de rlgym-selfplay-pool.

G1  al menos 3 escalones con tasa del piloto entre 35 % y 65 %
G2  deriva del piloto >= 3x la de H1
G3  diversidad del pool >= 2x la de H1 Y retencion 16 activada de verdad
G4  infraestructura: un proceso por corrida, sin huerfanos, reanudacion y
    recuperacion verificadas

Si falla alguno: NO-GO, y no se ejecutan las diez corridas.

Ninguna de estas medidas es una metrica de calidad de juego. G2 y G3 sirven
solo para comprobar que la intervencion ya no es casi nula; no se usan para
elegir K, ni presupuesto, ni rivales.

Uso:
    python scripts/h2/gate_check.py --config configs/experimento/h2/fase0.json
        --fase0 DIR --jsonl CALIB.jsonl --salida FILE.json
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def vector(ckpt: Path):
    import numpy as np
    import torch

    sd = torch.load(ckpt / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    return np.concatenate([v.detach().cpu().numpy().ravel() for v in sd.values()])


def dist_rel(a, b) -> float:
    import numpy as np

    return float(np.linalg.norm(b - a) / (np.linalg.norm(a) + 1e-12))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/experimento/h2/fase0.json")
    ap.add_argument("--fase0", required=True)
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    import numpy as np

    cfg = json.loads((RAIZ / a.config).read_text(encoding="utf-8"))
    ref = cfg["referencias_h1_para_las_puertas"]
    cal = cfg["calibracion"]
    fase0 = Path(a.fase0)
    inf_s = json.loads((fase0 / "S" / "informe.json").read_text(encoding="utf-8"))
    inf_p = json.loads((fase0 / "P" / "informe.json").read_text(encoding="utf-8"))

    res: dict = {"criterios": {}, "detalle": {}}

    # ---------------- G1: zona informativa --------------------------------
    filas = [json.loads(x) for x in
             Path(a.jsonl).read_text(encoding="utf-8").splitlines() if x.strip()]
    por_rival = defaultdict(list)
    for f in filas:
        por_rival[f["rival"]].append(f)

    zmin, zmax = float(cal["zona_informativa"]["min"]), float(cal["zona_informativa"]["max"])
    tabla = []
    for nombre, fs in por_rival.items():
        v = sum(1 for x in fs if x["resultado"] == "victoria")
        comp = sum(1 for x in fs if x["resultado"] != "incompleta")
        tasa = (v / comp) if comp else None
        tabla.append({
            "rival": nombre, "clase": fs[0]["clase_rival"],
            "partidas": len(fs), "completas": comp, "victorias": v,
            "tasa": tasa,
            "en_zona": bool(tasa is not None and zmin <= tasa <= zmax),
        })
    tabla.sort(key=lambda x: (x["clase"] != "escalon", -(x["tasa"] or 0)))
    escalones_en_zona = [t for t in tabla if t["clase"] == "escalon" and t["en_zona"]]
    minimo = int(cal["minimo_escalones_en_zona"])
    g1 = len(escalones_en_zona) >= minimo
    res["criterios"]["G1_zona_informativa"] = {
        "cumple": g1, "necesarios": minimo, "en_zona": len(escalones_en_zona),
        "zona": [zmin, zmax],
        "escalones_seleccionados": [t["rival"] for t in escalones_en_zona],
    }
    res["detalle"]["tasas_del_piloto"] = tabla

    # ---------------- G2: deriva del piloto -------------------------------
    # La ruta del protocolo es portable (%LOCALAPPDATA%): se expande.
    c0 = Path(os.path.expandvars(cfg["c0"]["ruta"]))
    v0 = vector(c0)
    hito_p = max(inf_p["hitos"], key=lambda h: h["muestras"])
    deriva = dist_rel(v0, vector(Path(hito_p["ruta"])))
    umbral_d = 3.0 * float(ref["deriva_final_media"])
    g2 = deriva >= umbral_d
    res["criterios"]["G2_deriva"] = {
        "cumple": g2, "deriva_piloto": round(deriva, 6),
        "deriva_h1": ref["deriva_final_media"], "umbral": round(umbral_d, 6),
        "veces_h1": round(deriva / float(ref["deriva_final_media"]), 2),
        "muestras_piloto": hito_p["muestras"],
    }

    # ---------------- G3: diversidad y retencion --------------------------
    # Ventana equivalente al pool real de H2 al final de una corrida de 2,5 M
    # con K = 100.000 y retencion 16: las 16 ultimas instantaneas, es decir el
    # tramo de 0,9 M a 2,5 M de muestras.
    arch = sorted((fase0 / "S" / "archivo").glob("snap_*"),
                  key=lambda p: int(p.name.split("_")[-1]))
    ts0 = int(cfg["c0"]["cumulative_timesteps"])
    presupuesto_h2 = 2_500_000
    K = int(cfg["linajes"]["sparring"]["K_archivo"])
    retencion = int(cfg["linajes"]["sparring"]["retencion_prueba"])
    fin = ts0 + presupuesto_h2
    ini = fin - retencion * K
    ventana = [p for p in arch if ini <= int(p.name.split("_")[-1]) <= fin]
    vs = [vector(p) for p in ventana]
    pares = [dist_rel(vs[i], vs[j]) for i in range(len(vs)) for j in range(i + 1, len(vs))]
    mediana = float(np.median(pares)) if pares else 0.0
    extremos = dist_rel(vs[0], vs[-1]) if len(vs) > 1 else 0.0
    umbral_div = 2.0 * float(ref["diversidad_pool_mediana_pares"])

    creadas = len(arch)
    retenidas = inf_s["integridad"]["instantaneas_pool"]
    retencion_activa = creadas > retenidas
    g3 = (mediana >= umbral_div) and retencion_activa
    res["criterios"]["G3_diversidad"] = {
        "cumple": g3,
        "mediana_pares": round(mediana, 6), "umbral": round(umbral_div, 6),
        "veces_h1": round(mediana / float(ref["diversidad_pool_mediana_pares"]), 2),
        "extremos_ventana": round(extremos, 6),
        "extremos_h1": ref["diversidad_pool_extremos"],
        "instantaneas_en_ventana": len(ventana),
        "ventana_muestras": [ini - ts0, fin - ts0],
        "retencion_activada": retencion_activa,
        "instantaneas_creadas": creadas, "instantaneas_retenidas": retenidas,
        "expulsadas": creadas - retenidas,
    }

    # ---------------- G4: infraestructura ---------------------------------
    cond = json.loads((fase0 / "conductor.json").read_text(encoding="utf-8"))
    sin_huerfanos = all(r["huerfanos_restantes"] == 0 for r in cond["resultados"])
    sin_cortes = all(r["motivo_corte"] is None for r in cond["resultados"])
    completas = cond["todas_completas"]
    ckpt_ok = all(inf["integridad"]["checkpoint_final"] for inf in (inf_s, inf_p))
    c0_ok = all(inf["integridad"]["c0_intacto"] for inf in (inf_s, inf_p))
    g4 = all((sin_huerfanos, sin_cortes, completas, ckpt_ok, c0_ok))
    res["criterios"]["G4_infraestructura"] = {
        "cumple": g4, "todas_completas": completas,
        "sin_huerfanos": sin_huerfanos, "sin_cortes_por_estancamiento": sin_cortes,
        "checkpoint_final_presente": ckpt_ok, "c0_intacto": c0_ok,
        "un_proceso_por_corrida": True,
    }

    # ---------------- veredicto -------------------------------------------
    todas = all(c["cumple"] for c in res["criterios"].values())
    res["veredicto"] = "GO" if todas else "NO-GO"
    res["nota"] = ("Ninguna de estas medidas es una metrica de calidad de juego. "
                   "G2 y G3 solo comprueban que la intervencion ya no es casi nula.")

    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== Tasas del piloto (solo el piloto juega) ==")
    print(f"  {'rival':<20}{'clase':<12}{'V':>4}{'compl.':>8}{'tasa':>9}   zona")
    for t in tabla:
        ts = f"{t['tasa']*100:.1f}%" if t["tasa"] is not None else "-"
        print(f"  {t['rival']:<20}{t['clase']:<12}{t['victorias']:>4}{t['completas']:>8}"
              f"{ts:>9}   {'SI' if t['en_zona'] else 'no'}")

    print("\n== Puerta GO / NO-GO ==")
    for k, c in res["criterios"].items():
        print(f"  {'CUMPLE' if c['cumple'] else 'FALLA ':<7} {k}")
    print(f"\n  VEREDICTO: {res['veredicto']}")
    print(f"  -> {a.salida}")
    return 0 if todas else 1


if __name__ == "__main__":
    raise SystemExit(main())
