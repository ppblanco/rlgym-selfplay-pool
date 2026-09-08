"""H2 fase 0: calibracion de dificultad. Solo el PILOTO juega.

APORTACION NUEVA de rlgym-selfplay-pool.

Mide contra que escalones del linaje neutral el piloto cae en la zona
informativa (35 %-65 %). Sirve para ELEGIR RIVALES, no para comparar metodos.

Por que no se puede hacer trampa aqui: en esta fase **no existe ningun agente
del brazo B**. Solo juega el piloto, que usa el esquema de control. Es
imposible elegir rivales mirando a quien favorecen, porque solo hay uno.

Correccion respecto a H1: todas las politicas se cargan por ADELANTADO, en
orden fijo, antes de jugar. En H1 la politica propia se cargaba de forma
perezosa, asi que al reanudar consumia numeros aleatorios en otro punto y una
partida podia salir distinta. Aqui la siembra por partida ocurre justo antes de
jugar y ya no depende de si hubo reanudacion.

Uso:
    python scripts/h2/eval_calib.py --config configs/experimento/h2/fase0.json
        --meshes RUTA --fase0 DIR --artefactos DIR --jsonl SALIDA.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def obs_dim_de(ckpt: Path) -> int:
    import torch

    sd = torch.load(ckpt / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    wk = [k for k in sd if k.endswith("weight")]
    return int(sd[wk[0]].shape[1])


def jugar(env, pol_azul, pol_naranja, tope_pasos: int):
    import numpy as np
    import torch

    from rlbot.tournament.policy_io import action_to_int

    obs = env.reset()
    pasos = 0
    with torch.no_grad():
        while pasos < tope_pasos:
            a_az, _ = pol_azul.get_action(obs[0], deterministic=False)
            a_na, _ = pol_naranja.get_action(obs[1], deterministic=False)
            obs, _, done, info = env.step(
                np.asarray([[action_to_int(a_az)], [action_to_int(a_na)]])
            )
            pasos += 1
            if done:
                res = int((info or {}).get("result", 0))
                return (res, "gol", pasos) if res != 0 else (0, "tiempo", pasos)
    return None, "incompleta", pasos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/experimento/h2/fase0.json")
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--fase0", required=True)
    ap.add_argument("--artefactos", required=True)
    ap.add_argument("--jsonl", required=True)
    a = ap.parse_args()

    import numpy as np
    import torch

    from rlbot.env.rocketsim_init import asegurar_init
    from rlbot.tournament.obs import make_env
    from rlbot.tournament.policy_io import load_policy

    cfg = json.loads((RAIZ / a.config).read_text(encoding="utf-8"))
    cal = cfg["calibracion"]
    torch.set_num_threads(2)
    asegurar_init(a.meshes)

    fase0 = Path(a.fase0)
    inf_s = json.loads((fase0 / "S" / "informe.json").read_text(encoding="utf-8"))
    inf_p = json.loads((fase0 / "P" / "informe.json").read_text(encoding="utf-8"))
    for nombre, inf in (("S", inf_s), ("P", inf_p)):
        if inf["estado"] != "COMPLETA":
            raise SystemExit(f"  ! El linaje {nombre} no esta COMPLETA. No se calibra.")

    # -- la sonda: el piloto, en su presupuesto final ------------------------
    hito_p = max(inf_p["hitos"], key=lambda h: h["muestras"])
    sonda = {"nombre": "P", "ruta": Path(hito_p["ruta"]),
             "sha256": hito_p["sha256"], "muestras": hito_p["muestras"]}

    # -- los escalones candidatos, en orden fijo -----------------------------
    rivales = []
    for h in sorted(inf_s["hitos"], key=lambda x: x["muestras"]):
        rivales.append({"nombre": f"S@{h['muestras']}", "ruta": Path(h["ruta"]),
                        "sha256": h["sha256"], "clase": "escalon"})
    # La ruta del protocolo es portable (%LOCALAPPDATA%): se expande.
    c0 = Path(os.path.expandvars(cfg["c0"]["ruta"]))
    rivales.append({"nombre": "C0", "ruta": c0,
                    "sha256": sha256_archivo(c0 / "PPO_POLICY.pt"), "clase": "referencia"})
    diego = Path(a.artefactos) / "diego_1.18B_512"
    if diego.exists():
        rivales.append({"nombre": "diego_1.18B_512", "ruta": diego,
                        "sha256": sha256_archivo(diego / "PPO_POLICY.pt"),
                        "clase": "referencia"})

    n = int(cal["partidas_por_rival"])
    semillas = list(range(int(cal["semillas_partida"]["desde"]),
                          int(cal["semillas_partida"]["desde"]) + n))
    tope = int(cal["tope_pasos"])

    # -- TODAS las politicas por adelantado, en orden fijo -------------------
    # Asi la reanudacion no cambia el estado aleatorio de ninguna partida.
    print("  cargando politicas por adelantado (orden fijo)...", flush=True)
    dim_sonda = obs_dim_de(sonda["ruta"])
    pol_sonda = load_policy(sonda["ruta"], dim_sonda)
    for r in rivales:
        r["obs"] = obs_dim_de(r["ruta"])
        r["politica"] = load_policy(r["ruta"], r["obs"])
        print(f"    {r['nombre']:<20} obs={r['obs']:<4} {r['sha256'][:16]}", flush=True)
    print(f"    sonda P              obs={dim_sonda:<4} {sonda['sha256'][:16]}", flush=True)

    salida = Path(a.jsonl)
    salida.parent.mkdir(parents=True, exist_ok=True)
    ya = set()
    if salida.exists():
        for ln in salida.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                ya.add(json.loads(ln)["id"])
        print(f"  {len(ya)} partidas ya registradas; se continua sin repetirlas")

    entornos: dict[tuple[int, int], object] = {}
    t0 = time.perf_counter()
    nuevas = 0
    with salida.open("a", encoding="utf-8") as f:
        for r in rivales:
            for i, sem in enumerate(semillas):
                pid = f"P-{r['nombre']}-{sem}"
                if pid in ya:
                    continue
                sonda_azul = (i % 2 == 0)
                az_dim, na_dim = ((dim_sonda, r["obs"]) if sonda_azul
                                  else (r["obs"], dim_sonda))
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

                pol_az = pol_sonda if sonda_azul else r["politica"]
                pol_na = r["politica"] if sonda_azul else pol_sonda

                t = time.perf_counter()
                res_az, causa, pasos = jugar(env, pol_az, pol_na, tope)
                dur = time.perf_counter() - t

                if causa == "incompleta":
                    resultado = "incompleta"
                elif res_az == 0:
                    resultado = "empate"
                else:
                    resultado = "victoria" if ((res_az > 0) == sonda_azul) else "derrota"

                f.write(json.dumps({
                    "id": pid, "sonda": "P", "sonda_muestras": sonda["muestras"],
                    "hash_sonda": sonda["sha256"],
                    "rival": r["nombre"], "clase_rival": r["clase"],
                    "hash_rival": r["sha256"],
                    "semilla_partida": sem,
                    "lado_sonda": "azul" if sonda_azul else "naranja",
                    "modo": "estocastico", "resultado": resultado,
                    "causa_terminacion": causa, "pasos": pasos,
                    "duracion_s": round(dur, 3),
                    "fase": "H2-fase0-calibracion",
                }, ensure_ascii=False) + "\n")
                f.flush()
                nuevas += 1
                if nuevas % 40 == 0:
                    print(f"    {nuevas} partidas nuevas, {time.perf_counter()-t0:.0f}s",
                          flush=True)
            print(f"  {r['nombre']} listo ({time.perf_counter()-t0:.0f}s)", flush=True)

    print(f"\n  {nuevas} partidas nuevas en {time.perf_counter()-t0:.0f}s")
    print(f"  JSONL -> {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
