"""Tabla CIEGA de integridad de las seis ejecuciones.

APORTACION NUEVA de rlgym-selfplay-pool.

Se ejecuta ANTES de la evaluacion final. Deliberadamente NO mira ningun
resultado de juego: ni rivales finales, ni recompensa de entrenamiento, ni
ninguna metrica que permita ordenar los brazos por calidad. Solo comprueba
que las seis corridas son ejecuciones validas y comparables entre si.

Columnas (las del protocolo, sin anadir ninguna):
    corrida, brazo, semilla, muestras, actualizaciones, duracion,
    instantaneas, hash del checkpoint final, recuperacion OK/FALLO

Comprobaciones cruzadas:
    - las tres semillas aparecen exactamente una vez en cada brazo;
    - todas las corridas parten del MISMO C0 y lo dejan intacto;
    - todas gastan el mismo presupuesto de muestras;
    - los seis checkpoints finales son distintos entre si y distintos de C0;
    - cada checkpoint final se recupera en un PROCESO NUEVO con
      weights_only=True y produce una accion valida.

Uso:
    python scripts/integrity_table.py --experimento DIR [--salida FILE.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SHA_PROTOCOLO = "8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e"

# Comprobador de recuperacion: se ejecuta en un INTERPRETE NUEVO, no aqui.
# Asi "se recupera en otro proceso" significa lo que dice, y no que el objeto
# siga vivo en la memoria de este script.
RECUPERADOR = (
    "import sys, json\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[2])\n"
    "import numpy as np, torch\n"
    "from rlbot.tournament.policy_io import load_policy\n"
    "ck = Path(sys.argv[1])\n"
    "sd = torch.load(ck / 'PPO_POLICY.pt', map_location='cpu', weights_only=True)\n"
    "dim = int(sd[[k for k in sd if k.endswith('weight')][0]].shape[1])\n"
    "pol = load_policy(ck, dim)\n"
    "with torch.no_grad():\n"
    "    a, _ = pol.get_action(np.zeros(dim, dtype=np.float32), deterministic=True)\n"
    "i = int(np.asarray(a).flat[0])\n"
    "print(json.dumps({'ok': 0 <= i < 90, 'obs_dim': dim, 'accion': i}))\n"
)


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def recuperar(ckpt: Path) -> dict:
    """Carga el checkpoint en un proceso limpio y le pide una accion."""
    try:
        r = subprocess.run(
            [sys.executable, "-c", RECUPERADOR, str(ckpt), str(RAIZ / "src")],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            cola = (r.stderr or "").strip().splitlines()
            return {"ok": False, "error": cola[-1] if cola else "sin stderr"}
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experimento", required=True)
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()

    exp = Path(a.experimento)
    informes = sorted(exp.glob("*/informe.json"))
    print(f"  informes encontrados: {len(informes)}")

    filas: list[dict] = []
    problemas: list[str] = []

    for p in informes:
        d = json.loads(p.read_text(encoding="utf-8"))
        res, integ = d["resultado"], d["integridad"]
        ck = Path(integ["checkpoint_final"]) if integ["checkpoint_final"] else None

        # El hash se RECALCULA aqui; no se cree el que dejo el entrenamiento.
        hash_ahora = sha256_archivo(ck / "PPO_POLICY.pt") if ck and ck.exists() else None
        coincide = hash_ahora == integ["hash_checkpoint_final"]

        rec = recuperar(ck) if ck and ck.exists() else {"ok": False, "error": "sin checkpoint"}

        filas.append({
            "corrida": d["run_id"], "brazo": d["brazo"], "semilla": d["semilla"],
            "protocolo_sha256": d["protocolo_sha256"],
            "muestras": res["muestras_aprendizaje"],
            "actualizaciones": res["actualizaciones"],
            "segundos": res["segundos_total"],
            "muestras_por_segundo": res["muestras_por_segundo"],
            "instantaneas": integ["instantaneas"],
            "hash_checkpoint_final": hash_ahora,
            "hash_coincide_con_informe": coincide,
            "recuperacion_ok": bool(rec.get("ok")),
            "recuperacion_detalle": rec,
            "completa": res["completa"],
            "error": res["error"],
            "parametros_finitos": integ["parametros_finitos"],
            "instantaneas_hash_ok": integ["instantaneas_hash_ok"],
            "retencion_respetada": integ["retencion_respetada"],
            "c0_intacto": integ["c0_intacto"],
            "hash_c0": d["c0"]["hash_politica"],
            "ts_inicial": res["ts_inicial"],
            "presupuesto": d["configuracion_resuelta"]["presupuesto"],
        })

    for f in filas:
        eti = f["corrida"]
        if f["protocolo_sha256"] != SHA_PROTOCOLO:
            problemas.append(f"{eti}: protocolo distinto del aprobado")
        if not f["completa"]:
            problemas.append(f"{eti}: incompleta ({f['error']})")
        if f["muestras"] < f["presupuesto"]:
            problemas.append(f"{eti}: {f['muestras']} muestras < presupuesto {f['presupuesto']}")
        for clave, texto in (
            ("parametros_finitos", "parametros no finitos"),
            ("instantaneas_hash_ok", "hashes de instantaneas"),
            ("retencion_respetada", "retencion no respetada"),
            ("c0_intacto", "C0 alterado"),
            ("hash_coincide_con_informe", "hash final distinto del informe"),
            ("recuperacion_ok", "no se recupera en proceso nuevo"),
        ):
            if not f[clave]:
                problemas.append(f"{eti}: {texto}")

    # -- comprobaciones cruzadas -------------------------------------------
    cruz: dict = {"n_corridas": len(filas)}
    if len(filas) != 6:
        problemas.append(f"se esperaban 6 corridas y hay {len(filas)}")

    pares: dict = {}
    for f in filas:
        pares.setdefault(f["semilla"], []).append(f["brazo"])
    cruz["semillas_emparejadas"] = {str(s): sorted(b) for s, b in pares.items()}
    for s, bs in pares.items():
        if sorted(bs) != ["A", "B"]:
            problemas.append(f"la semilla {s} no esta emparejada A/B: {sorted(bs)}")

    c0s = {f["hash_c0"] for f in filas}
    cruz["c0_unico"] = len(c0s) == 1
    if len(c0s) != 1:
        problemas.append(f"las corridas no parten del mismo C0: {len(c0s)} hashes distintos")

    ts0 = {f["ts_inicial"] for f in filas}
    cruz["ts_inicial_unico"] = len(ts0) == 1
    if len(ts0) != 1:
        problemas.append(f"ts_inicial distinto entre corridas: {sorted(ts0)}")

    muestras = {f["muestras"] for f in filas}
    cruz["mismo_presupuesto_gastado"] = len(muestras) == 1
    cruz["muestras_por_corrida"] = sorted(muestras)

    finales = [f["hash_checkpoint_final"] for f in filas if f["hash_checkpoint_final"]]
    cruz["checkpoints_finales_distintos"] = len(set(finales)) == len(finales)
    if len(set(finales)) != len(finales):
        problemas.append("hay checkpoints finales repetidos entre corridas")
    if any(h in c0s for h in finales):
        problemas.append("algun checkpoint final es identico a C0: esa corrida no aprendio nada")

    # -- salida -------------------------------------------------------------
    orden = sorted(filas, key=lambda f: (f["semilla"], f["brazo"]))
    cab = (f"{'corrida':<9}{'brazo':<7}{'semilla':<10}{'muestras':>10}{'actual.':>9}"
           f"{'dur(s)':>9}{'inst.':>7}  {'hash final':<18}{'recup.':>7}")
    print("\n== TABLA CIEGA DE INTEGRIDAD ==")
    print("   Sin resultados de juego: los rivales finales aun no se han usado.\n")
    print(cab)
    print("-" * len(cab))
    for f in orden:
        h = (f["hash_checkpoint_final"] or "-")[:16]
        print(f"{f['corrida']:<9}{f['brazo']:<7}{f['semilla']:<10}{f['muestras']:>10,}"
              f"{f['actualizaciones']:>9}{f['segundos']:>9,.0f}{f['instantaneas']:>7}  "
              f"{h:<18}{'OK' if f['recuperacion_ok'] else 'FALLO':>7}")

    print("\n== Comprobaciones cruzadas ==")
    for k, v in cruz.items():
        print(f"  {k}: {v}")

    print("\n== Veredicto de integridad ==")
    if problemas:
        print(f"  NO SUPERADA: {len(problemas)} problema(s)")
        for x in problemas:
            print(f"    - {x}")
    else:
        print("  SUPERADA: las seis corridas son validas y comparables")

    if a.salida:
        Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(a.salida).write_text(json.dumps(
            {"protocolo_sha256": SHA_PROTOCOLO, "filas": orden, "cruzadas": cruz,
             "problemas": problemas, "integridad_superada": not problemas},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  -> {a.salida}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
