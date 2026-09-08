"""Evaluacion final, UNA SOLA VEZ, segun el protocolo congelado.

APORTACION NUEVA de rlgym-selfplay-pool.

Reglas del protocolo que este script implementa literalmente:
  - se evalua el checkpoint FINAL de cada ejecucion; no hay regla de seleccion;
  - 40 partidas por rival y ejecucion, semillas 5000..5039, lista fija;
  - lados alternados por indice; modo estocastico;
  - gol -> victoria/derrota; agotar el tiempo -> empate;
  - cualquier otra terminacion -> INCOMPLETA: no cuenta como victoria, derrota
    ni empate, y se reporta aparte;
  - SIN desempates administrativos (nada de timesteps ni siembra);
  - los agregados se leen del JSONL, nunca se acumulan a mano.

Uso:
    python scripts/eval_final.py --protocolo ... --meshes ... --experimento DIR
        --artefactos DIR --jsonl SALIDA.jsonl --resumen SALIDA.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

# Hash del protocolo PUBLICO. El original de preregistro es
# 8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e
# y solo difiere en una ruta local redactada por privacidad.
# Ver docs/FINAL_REPORT.md, tabla de trazabilidad de hashes.
SHA_PROTOCOLO = "c6506d17ec164a39eef6bc2063d3fa9ab8e6c23e9a6d63889044c364a02aff30"


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def obs_dim_de(ckpt: Path) -> int:
    import torch

    sd = torch.load(ckpt / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    wk = [k for k in sd if k.endswith("weight")]
    return int(sd[wk[0]].shape[1])


def jugar(env, pol_azul, pol_naranja, tope_pasos: int):
    """Devuelve (resultado_azul, causa, pasos). resultado: +1 azul, -1 naranja, 0 empate."""
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
    ap.add_argument("--protocolo", default="configs/experimento/protocolo.json")
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--experimento", required=True, help="Raiz con A1/B1/... y sus informes.")
    ap.add_argument("--artefactos", required=True, help="Carpeta con los rivales finales.")
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--resumen", required=True)
    ap.add_argument("--tope-pasos", type=int, default=3000, help="Igual al TimeoutCondition del arnes.")
    ap.add_argument("--solo-run", default=None)
    a = ap.parse_args()

    import numpy as np
    import torch

    from rlbot.env.rocketsim_init import asegurar_init
    from rlbot.tournament.obs import make_env
    from rlbot.tournament.policy_io import load_policy

    texto = (RAIZ / a.protocolo).read_text(encoding="utf-8").rstrip("\n")
    if hashlib.sha256(texto.encode("utf-8")).hexdigest() != SHA_PROTOCOLO:
        raise SystemExit("  ! El protocolo no coincide con el aprobado. No se evalua.")
    prot = json.loads(texto)
    ev = prot["evaluacion_final"]

    torch.set_num_threads(2)
    asegurar_init(a.meshes)

    # -- rivales finales, con sus hashes congelados ------------------------
    art = Path(a.artefactos)
    nombres = {"martin_2.1B_1024": "martin_2.1B_1024",
               "nachi_2.9B": "nachi_2.9B",
               "marco_2.0B_1024": "marco_2.0B_1024"}
    rivales = []
    for r in ev["rivales"]:
        d = art / nombres[r["nombre"]]
        h = sha256_archivo(d / "PPO_POLICY.pt")
        if h != r["sha256_politica"]:
            raise SystemExit(f"  ! El rival {r['nombre']} no coincide con el hash congelado.")
        rivales.append({"nombre": r["nombre"], "ruta": d, "obs": int(r["obs"]), "sha256": h})
    print(f"  {len(rivales)} rivales verificados contra los hashes del protocolo")

    # -- checkpoints FINALES de las 6 ejecuciones --------------------------
    exp = Path(a.experimento)
    corridas = []
    for inf in sorted(exp.glob("*/informe.json")):
        d = json.loads(inf.read_text(encoding="utf-8"))
        if not d["resultado"]["completa"]:
            print(f"  ! {d['run_id']} incompleta: se excluye de la evaluacion")
            continue
        ck = Path(d["integridad"]["checkpoint_final"])
        corridas.append({
            "run_id": d["run_id"], "brazo": d["brazo"], "semilla": d["semilla"],
            "ckpt": ck, "sha256": d["integridad"]["hash_checkpoint_final"],
            "obs": obs_dim_de(ck),
        })
    corridas.sort(key=lambda c: (c["semilla"], c["brazo"]))
    print(f"  {len(corridas)} ejecuciones completas a evaluar")

    n_partidas = int(ev["partidas_por_rival_y_ejecucion"])
    semillas_partida = list(range(5000, 5000 + n_partidas))

    salida = Path(a.jsonl)
    salida.parent.mkdir(parents=True, exist_ok=True)
    ya = set()
    if salida.exists():   # reanudable sin repetir partidas
        for ln in salida.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                ya.add(json.loads(ln)["id"])
        print(f"  {len(ya)} partidas ya registradas; se continua")

    entornos: dict[tuple[int, int], object] = {}
    t0 = time.perf_counter()
    n_nuevas = 0

    with salida.open("a", encoding="utf-8") as f:
        for c in corridas:
            if a.solo_run and c["run_id"] != a.solo_run:
                continue
            pol_nuestro_cache = None
            for riv in rivales:
                for i, sem in enumerate(semillas_partida):
                    pid = f"{c['run_id']}-{riv['nombre']}-{sem}"
                    if pid in ya:
                        continue
                    nuestro_azul = (i % 2 == 0)      # alternancia por indice
                    azul_ck, azul_dim = (c["ckpt"], c["obs"]) if nuestro_azul else (riv["ruta"], riv["obs"])
                    nar_ck, nar_dim = (riv["ruta"], riv["obs"]) if nuestro_azul else (c["ckpt"], c["obs"])

                    clave = (azul_dim, nar_dim)
                    if clave not in entornos:
                        entornos[clave] = make_env(azul_dim, nar_dim)
                    env = entornos[clave]

                    np.random.seed(sem)
                    torch.manual_seed(sem)
                    try:
                        env.action_space.seed(sem)
                    except Exception:  # noqa: BLE001
                        pass

                    if pol_nuestro_cache is None:
                        pol_nuestro_cache = load_policy(c["ckpt"], c["obs"])
                    pol_riv = load_policy(riv["ruta"], riv["obs"])
                    pol_az = pol_nuestro_cache if nuestro_azul else pol_riv
                    pol_na = pol_riv if nuestro_azul else pol_nuestro_cache

                    t = time.perf_counter()
                    res_az, causa, pasos = jugar(env, pol_az, pol_na, a.tope_pasos)
                    dur = time.perf_counter() - t

                    if causa == "incompleta":
                        resultado = "incompleta"
                        marcador = None
                    elif res_az == 0:
                        resultado, marcador = "empate", "0-0"
                    else:
                        gana_azul = res_az > 0
                        nuestro_gana = (gana_azul == nuestro_azul)
                        resultado = "victoria" if nuestro_gana else "derrota"
                        marcador = "1-0" if nuestro_gana else "0-1"

                    fila = {
                        "id": pid,
                        "run_id": c["run_id"], "brazo": c["brazo"],
                        "semilla_entrenamiento": c["semilla"],
                        "rival": riv["nombre"],
                        "hash_agente": c["sha256"], "hash_rival": riv["sha256"],
                        "semilla_partida": sem,
                        "lado_agente": "azul" if nuestro_azul else "naranja",
                        "modo": "estocastico",
                        "marcador": marcador,
                        "resultado": resultado,
                        "causa_terminacion": causa,
                        "pasos": pasos,
                        "duracion_s": round(dur, 3),
                        "protocolo_sha256": SHA_PROTOCOLO,
                    }
                    f.write(json.dumps(fila, ensure_ascii=False) + "\n")
                    f.flush()
                    n_nuevas += 1
                    if n_nuevas % 20 == 0:
                        print(f"    {n_nuevas} partidas nuevas, {time.perf_counter()-t0:.0f}s",
                              flush=True)
            print(f"  {c['run_id']} listo ({time.perf_counter()-t0:.0f}s)", flush=True)

    print(f"\n  {n_nuevas} partidas nuevas en {time.perf_counter()-t0:.0f}s")
    print(f"  JSONL -> {salida}")
    Path(a.resumen).write_text(json.dumps(
        {"nota": "usa scripts/analyze_h1.py para los agregados", "jsonl": str(salida)},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
