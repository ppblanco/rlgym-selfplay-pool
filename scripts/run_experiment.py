"""Ejecuta el experimento congelado: 3 semillas x 2 brazos, secuencialmente.

APORTACION NUEVA de rlgym-selfplay-pool.

TODA la configuracion sale de configs/experimento/protocolo.json. Este script no
tiene valores por defecto propios que puedan desviarse del protocolo: si algo
falta ahi, falla. El SHA del protocolo se verifica antes de empezar y se graba
en cada artefacto.

Orden: A1 B1 A2 B2 A3 B3, alternando brazo por semilla para repartir cualquier
efecto temporal del equipo. Nunca dos entrenamientos a la vez. Cada ejecucion
parte del MISMO C0 original, nunca del resultado de la anterior.

Uso:
    python scripts/run_experiment.py --protocolo configs/experimento/protocolo.json
        --meshes RUTA --raiz-salida DIR [--solo A1]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

os.environ.setdefault("WANDB_MODE", "disabled")
os.environ.setdefault("WANDB_SILENT", "true")

# Hash del protocolo PUBLICO. El original de preregistro es
# 8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e
# y solo difiere en una ruta local redactada por privacidad.
# Ver docs/FINAL_REPORT.md, tabla de trazabilidad de hashes.
SHA_ESPERADO = "c6506d17ec164a39eef6bc2063d3fa9ab8e6c23e9a6d63889044c364a02aff30"


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cargar_protocolo(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8").rstrip("\n")
    sha = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    if sha != SHA_ESPERADO:
        raise SystemExit(
            f"\n  ! El protocolo NO coincide con el aprobado.\n"
            f"    calculado {sha}\n    esperado  {SHA_ESPERADO}\n"
            f"    No se ejecuta nada.\n"
        )
    return json.loads(texto)


def verificar_c0(p: dict) -> Path:
    # La ruta del protocolo es portable (%LOCALAPPDATA%): se expande.
    c0 = Path(os.path.expandvars(p["c0"]["ruta"]))
    for nombre, h in p["c0"]["hashes"].items():
        real = sha256_archivo(c0 / nombre)
        if real != h:
            raise SystemExit(f"\n  ! C0 alterado: {nombre}\n    {real} != {h}\n")
    return c0


def hash_modulo(modulo) -> str:
    import torch

    h = hashlib.sha256()
    with torch.no_grad():
        for q in modulo.parameters():
            h.update(q.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def una_ejecucion(run_id: str, brazo: str, semilla: int, prot: dict, c0: Path,
                  meshes: str, raiz_salida: Path) -> dict:
    """Una corrida completa, con su directorio exclusivo y sus comprobaciones."""
    import numpy as np
    import torch
    from rlgym_ppo import Learner
    from rlgym_ppo.ppo import DiscreteFF

    from rlbot.env.frozen_opponent import ConstructorPool
    from rlbot.env.opponent_pool import PoolRivales

    dir_run = raiz_salida / run_id
    if dir_run.exists():
        raise SystemExit(f"  ! {dir_run} ya existe. No se sobrescribe nada.")
    dir_ckpt, dir_pool = dir_run / "checkpoints", dir_run / "pool"
    for d in (dir_ckpt, dir_pool):
        d.mkdir(parents=True)

    cfg_pool = prot["pool"][f"brazo_{brazo}"]
    retencion = int(cfg_pool["retencion"])
    K = int(prot["pool"]["K_muestras_por_instantanea"])
    presupuesto = int(prot["presupuesto"]["muestras_por_ejecucion"])
    lote = int(prot["presupuesto"]["lote_ppo"])
    n_proc = int(prot["ejecucion"]["n_proc"])
    arch = tuple(prot["modelo"]["arquitectura_politica"])
    ts0 = int(prot["c0"]["cumulative_timesteps"])
    recompensa = prot["recompensa"]["archivo"]

    torch.manual_seed(semilla)
    np.random.seed(semilla)
    torch.set_num_threads(1)

    # -- instantanea inicial desde C0, ANTES de construir el Learner --------
    sd0 = torch.load(c0 / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    wk = [k for k in sd0 if k.endswith("weight")]
    pol0 = DiscreteFF(89, 90, tuple(int(sd0[k].shape[0]) for k in wk[:-1]), "cpu")
    pol0.load_state_dict(sd0)

    id_c0 = f"snap_{ts0:012d}"
    # Solo el brazo B protege C0. El A conserva unicamente la version actual.
    proteger = (id_c0,) if cfg_pool["protegidas"] else ()
    pool = PoolRivales(dir_pool, retencion, proteger=proteger)
    meta_snap = {"brazo": brazo, "semilla": semilla, "origen": "C0",
                 "protocolo_sha256": SHA_ESPERADO}
    pool.guardar_instantanea(pol0, ts0, meta_snap)

    ctor = ConstructorPool(
        mallas=meshes, carpeta_pool=str(dir_pool), retencion=retencion,
        semilla=semilla, hilos_torch=int(prot["ejecucion"]["hilos_torch_por_trabajador"]),
        recompensa=recompensa,
        timeout_pasos=300,
    )
    ppo = prot["ppo"]
    learner = Learner(
        ctor, n_proc=n_proc, min_inference_size=max(1, n_proc // 2), metrics_logger=None,
        ppo_batch_size=lote, ts_per_iteration=lote, exp_buffer_size=lote,
        ppo_minibatch_size=int(ppo["minibatch"]), ppo_epochs=int(ppo["epochs"]),
        ppo_ent_coef=float(ppo["ent_coef"]),
        standardize_returns=bool(ppo["standardize_returns"]),
        standardize_obs=bool(ppo["standardize_obs"]),
        save_every_ts=lote * 10,
        timestep_limit=ts0 + presupuesto,
        log_to_wandb=False, checkpoints_save_folder=str(dir_ckpt),
        checkpoint_load_folder=str(c0),
        policy_layer_sizes=arch, critic_layer_sizes=arch,
        render=False, device="cpu",
    )
    pol, val = learner.ppo_learner.policy, learner.ppo_learner.value_net
    ts_inicial = int(learner.agent.cumulative_timesteps)
    h_rival_inicial = sha256_archivo(pool.ruta_de(pool.elegibles()[0]) / "PPO_POLICY.pt")

    filas: list[dict] = []
    proxima = ts_inicial + K
    t0 = time.perf_counter()
    original = learner.ppo_learner.learn
    t_ppo_total = [0.0]

    def hook(buffer):
        t = time.perf_counter()
        rep = original(buffer)
        t_ppo_total[0] += time.perf_counter() - t
        nonlocal proxima
        ts = int(learner.agent.cumulative_timesteps)
        creada = None
        if ts >= proxima:
            creada = pool.guardar_instantanea(pol, ts, meta_snap)
            proxima += K
        filas.append({
            "iteracion": len(filas) + 1, "timesteps": ts,
            "muestras_ppo": int(buffer.rewards.shape[0]),
            "segundos": round(time.perf_counter() - t0, 2),
            "instantaneas": len(pool.elegibles()),
            "instantanea_creada": creada["id"] if creada else None,
            **{k: float(v) for k, v in rep.items() if isinstance(v, (int, float))},
        })
        if len(filas) % 10 == 0 or creada:
            f = filas[-1]
            print(f"    it{f['iteracion']:>3} ts={ts:>8} pool={f['instantaneas']:>2} "
                  f"ent={f.get('Policy Entropy', 0):.3f} vf={f.get('Value Function Loss', 0):.4f} "
                  f"{f['segundos']:.0f}s", flush=True)
        return rep

    learner.ppo_learner.learn = hook

    print(f"  [{run_id}] brazo={brazo} semilla={semilla} retencion={retencion} "
          f"protegidas={proteger} K={K:,} presupuesto={presupuesto:,}", flush=True)
    error = None
    try:
        learner.learn()
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
        print(f"  ! {run_id} fallo tecnico: {error}", flush=True)
    finally:
        try:
            learner.save(int(learner.agent.cumulative_timesteps))
        except Exception as e:  # noqa: BLE001
            print(f"    aviso al guardar: {e}", flush=True)
        try:
            learner.cleanup()
        except Exception:  # noqa: BLE001
            pass

    dt = time.perf_counter() - t0
    ts_final = int(learner.agent.cumulative_timesteps)
    muestras = ts_final - ts_inicial

    # -- integridad --------------------------------------------------------
    import torch as _t

    with _t.no_grad():
        vp = _t.cat([q.detach().reshape(-1) for q in pol.parameters()])
        vv = _t.cat([q.detach().reshape(-1) for q in val.parameters()])
        finitos = bool(_t.isfinite(vp).all() and _t.isfinite(vv).all())

    ckpts = []
    for d in sorted(dir_ckpt.parent.glob(dir_ckpt.name + "*")):
        ckpts += [x for x in d.iterdir() if x.is_dir() and x.name.isdigit()]
    ckpt_final = max(ckpts, key=lambda x: int(x.name)) if ckpts else None

    snaps = pool.elegibles()
    snaps_ok = all(pool.verificar(s) for s in snaps)
    retencion_ok = len(snaps) <= retencion
    c0_intacto = all(
        sha256_archivo(c0 / n) == h for n, h in prot["c0"]["hashes"].items()
    )
    # El rival del brazo A se refresca, asi que su hash CAMBIA a proposito; lo
    # que se comprueba es que ninguna instantanea guardada se haya modificado
    # despues de escribirse (eso es snaps_ok) y que C0 siga intacto.

    informe = {
        "run_id": run_id, "brazo": brazo, "semilla": semilla,
        "protocolo_sha256": SHA_ESPERADO,
        "c0": {"ruta": str(c0), "hash_politica": prot["c0"]["hashes"]["PPO_POLICY.pt"],
               "timesteps": ts0},
        "configuracion_resuelta": {
            "recompensa": recompensa, "K": K, "retencion": retencion,
            "protegidas": list(proteger), "presupuesto": presupuesto, "lote": lote,
            "n_proc": n_proc, "hilos_torch": 1, "arquitectura": list(arch),
            "ppo": ppo, "obs": prot["modelo"]["obs"], "acciones": prot["modelo"]["acciones"],
            "entorno": prot["entorno"],
        },
        "resultado": {
            "completa": error is None and muestras >= presupuesto,
            "error": error,
            "ts_inicial": ts_inicial, "ts_final": ts_final,
            "muestras_aprendizaje": muestras,
            "actualizaciones": len(filas),
            "segundos_total": round(dt, 2),
            "segundos_ppo": round(t_ppo_total[0], 2),
            "segundos_recogida": round(dt - t_ppo_total[0], 2),
            "muestras_por_segundo": round(muestras / dt, 1) if dt else None,
        },
        "integridad": {
            "parametros_finitos": finitos,
            "instantaneas": len(snaps),
            "instantaneas_hash_ok": snaps_ok,
            "retencion_respetada": retencion_ok,
            "c0_intacto": c0_intacto,
            "hash_rival_inicial": h_rival_inicial,
            "checkpoint_final": str(ckpt_final) if ckpt_final else None,
            "hash_checkpoint_final": sha256_archivo(ckpt_final / "PPO_POLICY.pt") if ckpt_final else None,
        },
        "instantaneas": snaps,
        "metricas_por_iteracion": filas,
    }
    (dir_run / "informe.json").write_text(
        json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    r = informe["resultado"]
    print(f"  [{run_id}] {'COMPLETA' if r['completa'] else 'INCOMPLETA'} "
          f"muestras={r['muestras_aprendizaje']:,} it={r['actualizaciones']} "
          f"{r['segundos_total']:.0f}s ({r['muestras_por_segundo']} m/s) "
          f"snaps={len(snaps)} finitos={finitos}", flush=True)
    return informe


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocolo", default="configs/experimento/protocolo.json")
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--raiz-salida", required=True)
    ap.add_argument("--solo", default=None, help="Ejecutar solo un run_id (p.ej. A1).")
    a = ap.parse_args()

    prot = cargar_protocolo(RAIZ / a.protocolo)
    c0 = verificar_c0(prot)
    semillas = prot["semillas"]["entrenamiento"]
    raiz_salida = Path(a.raiz_salida)
    raiz_salida.mkdir(parents=True, exist_ok=True)

    print("=" * 74)
    print("EXPERIMENTO — protocolo verificado", SHA_ESPERADO[:16] + "...")
    print(f"C0 verificado: {c0}")
    print("=" * 74)

    # Orden: A1 B1 A2 B2 A3 B3
    plan = []
    for i, s in enumerate(semillas, start=1):
        plan.append((f"A{i}", "A", s))
        plan.append((f"B{i}", "B", s))

    informes = []
    for run_id, brazo, semilla in plan:
        if a.solo and run_id != a.solo:
            continue
        informes.append(una_ejecucion(run_id, brazo, semilla, prot, c0, a.meshes, raiz_salida))

    resumen = {
        "protocolo_sha256": SHA_ESPERADO,
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ejecuciones": [
            {k: i[k] for k in ("run_id", "brazo", "semilla")} | i["resultado"] | i["integridad"]
            for i in informes
        ],
    }
    (raiz_salida / "resumen-ejecuciones.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResumen -> {raiz_salida / 'resumen-ejecuciones.json'}")
    return 0 if all(i["resultado"]["completa"] for i in informes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
