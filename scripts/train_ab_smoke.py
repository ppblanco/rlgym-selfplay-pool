"""Smoke test A/B: los dos brazos, misma maquinaria, distinta retencion.

APORTACION NUEVA de rlgym-selfplay-pool.

    Brazo A (control)  retencion = 1  -> una instantanea, refrescada cada K
    Brazo B (variante) retencion = N  -> varias historicas, muestreo uniforme

NO es el experimento. Es la comprobacion de que ambos brazos arrancan de C0,
consumen el mismo presupuesto, producen instantaneas, guardan checkpoints y
generan registros comparables.

Las diferencias en las metricas de entrenamiento entre A y B **no son
evidencia de mejora de nadie**: con este presupuesto no significan nada.

Uso:
    python scripts/train_ab_smoke.py --meshes RUTA --c0 DIR --brazo A|B
        --salida DIR --pool DIR --timesteps 40000 --k 8000 --informe FILE
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("WANDB_MODE", "disabled")
os.environ.setdefault("WANDB_SILENT", "true")

RETENCION = {"A": 1, "B": 8}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--c0", required=True, help="Checkpoint COMPLETO comun a los dos brazos.")
    p.add_argument("--brazo", choices=["A", "B"], required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--pool", required=True)
    p.add_argument("--timesteps", type=int, default=40_000, help="Presupuesto de muestras.")
    p.add_argument("--lote", type=int, default=8_000)
    p.add_argument("--k", type=int, default=8_000, help="Cada K muestras, una instantanea.")
    p.add_argument("--n-proc", type=int, default=2)
    p.add_argument("--semilla", type=int, default=20260907)
    p.add_argument("--minutos", type=float, default=4.0)
    p.add_argument("--recompensa", default=None)
    p.add_argument("--informe", required=True)
    a = p.parse_args()

    import numpy as np
    import torch
    from rlgym_ppo import Learner

    from rlbot.env.frozen_opponent import ConstructorPool
    from rlbot.env.opponent_pool import PoolRivales

    # Todo identico entre brazos salvo la retencion.
    torch.manual_seed(a.semilla)
    np.random.seed(a.semilla)
    torch.set_num_threads(1)

    retencion = RETENCION[a.brazo]
    salida, carpeta_pool = Path(a.salida), Path(a.pool)
    for d in (salida, carpeta_pool):
        d.mkdir(parents=True, exist_ok=True)

    ctor = ConstructorPool(
        mallas=a.meshes,
        carpeta_pool=str(carpeta_pool),
        retencion=retencion,
        semilla=a.semilla,
        hilos_torch=1,
        recompensa=a.recompensa,
    )

    # La instantanea inicial TIENE que existir antes de construir el Learner:
    # el Learner arranca los trabajadores y ya llama a env.reset() durante su
    # construccion (batched_agent.py, linea 71). Si el pool esta vacio en ese
    # momento, los trabajadores mueren y el entrenamiento se queda colgado.
    # Por eso la politica de C0 se lee del disco, no del Learner.
    import torch as _t
    from rlgym_ppo.ppo import DiscreteFF

    _sd = _t.load(Path(a.c0) / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    _wk = [k for k in _sd if k.endswith("weight")]
    _pol0 = DiscreteFF(89, 90, tuple(int(_sd[k].shape[0]) for k in _wk[:-1]), "cpu")
    _pol0.load_state_dict(_sd)

    pool = PoolRivales(carpeta_pool, retencion)
    cfg_snap = {"brazo": a.brazo, "retencion": retencion, "semilla": a.semilla, "origen": "C0"}
    _ts0 = json.loads((Path(a.c0) / "BOOK_KEEPING_VARS.json").read_text(encoding="utf-8"))["cumulative_timesteps"]
    pool.guardar_instantanea(_pol0, int(_ts0), cfg_snap)
    print(f"  instantanea inicial desde C0 (ts={int(_ts0):,}) en {carpeta_pool}")

    learner = Learner(
        ctor,
        n_proc=a.n_proc,
        min_inference_size=max(1, a.n_proc // 2),
        metrics_logger=None,
        ppo_batch_size=a.lote,
        ts_per_iteration=a.lote,
        exp_buffer_size=a.lote,
        ppo_minibatch_size=a.lote,
        ppo_epochs=1,
        ppo_ent_coef=0.01,
        standardize_returns=True,
        standardize_obs=False,
        save_every_ts=a.lote,
        # RELATIVO a C0: el contador ya viene en ts0, asi que un limite absoluto
        # de 40.000 haria que el bucle terminara sin hacer nada.
        timestep_limit=int(_ts0) + a.timesteps,
        log_to_wandb=False,
        checkpoints_save_folder=str(salida),
        checkpoint_load_folder=a.c0,          # AMBOS brazos parten de C0
        policy_layer_sizes=(512, 512, 512),
        critic_layer_sizes=(512, 512, 512),
        render=False,
        device="cpu",
    )

    pol = learner.ppo_learner.policy
    ts_inicial = int(learner.agent.cumulative_timesteps)

    # El pool necesita una instantanea ANTES del primer reset de los trabajadores.
    print(f"  brazo {a.brazo} | retencion={retencion} | C0 en ts={ts_inicial:,}")

    filas: list[dict] = []
    t0 = time.perf_counter()
    limite = a.minutos * 60
    proxima_snap = ts_inicial + a.k
    original = learner.ppo_learner.learn

    def learn_hook(buffer):
        nonlocal proxima_snap
        t_upd = time.perf_counter()
        rep = original(buffer)
        dt_upd = time.perf_counter() - t_upd

        ts = int(learner.agent.cumulative_timesteps)
        snaps_antes = len(pool.elegibles())
        creada = None
        if ts >= proxima_snap:
            creada = pool.guardar_instantanea(pol, ts, cfg_snap)
            proxima_snap += a.k

        filas.append({
            "iteracion": len(filas) + 1,
            "timesteps": ts,
            "muestras_ppo": int(buffer.rewards.shape[0]),
            "segundos_actualizacion": round(dt_upd, 4),
            "segundos_acumulados": round(time.perf_counter() - t0, 2),
            "instantaneas_en_pool": len(pool.elegibles()),
            "instantanea_creada": creada["id"] if creada else None,
            **{k: float(v) for k, v in rep.items() if isinstance(v, (int, float))},
        })
        print(f"  it{len(filas):>2} ts={ts:>7} muestras_ppo={filas[-1]['muestras_ppo']:>6} "
              f"pool={snaps_antes}->{len(pool.elegibles())} upd={dt_upd:.2f}s")

        if time.perf_counter() - t0 > limite:
            print(f"  [tope de {a.minutos} min]")
            learner.timestep_limit = 0
        return rep

    learner.ppo_learner.learn = learn_hook

    print(f"\n== Brazo {a.brazo}: hasta {a.timesteps:,} muestras ==")
    try:
        learner.learn()
    finally:
        try:
            learner.save(int(learner.agent.cumulative_timesteps))
        except Exception as e:  # noqa: BLE001
            print(f"  aviso al guardar: {e}")
        try:
            learner.cleanup()
        except Exception:  # noqa: BLE001
            pass

    dt = time.perf_counter() - t0
    ts_final = int(learner.agent.cumulative_timesteps)
    muestras = ts_final - ts_inicial
    t_upd = sum(f["segundos_actualizacion"] for f in filas)

    guardados = []
    for d in sorted(salida.parent.glob(salida.name + "*")):
        guardados += [x.name for x in d.iterdir() if x.is_dir()]

    informe = {
        "brazo": a.brazo,
        "retencion": retencion,
        "c0": a.c0,
        "semilla": a.semilla,
        "configuracion": {
            "lote": a.lote, "k": a.k, "n_proc": a.n_proc, "hilos_torch_por_trabajador": 1,
            "ppo_epochs": 1, "arquitectura": [512, 512, 512],
            "standardize_returns": True, "standardize_obs": False,
            "obs": "DefaultObs(89)", "acciones": "LookupAction(90)",
            "recompensa": a.recompensa or "DefaultReward", "timeout_pasos": 300,
        },
        "contabilidad": {
            "ts_inicial": ts_inicial,
            "ts_final": ts_final,
            "muestras_para_ppo": muestras,
            "pasos_entorno_equivalentes": muestras,   # 1 muestra = 1 paso (solo aprende el azul)
            "actualizaciones": len(filas),
            "inferencias_aprendiz_aprox": muestras,
            "inferencias_rival_aprox": muestras,      # el rival decide en cada paso
            "instantaneas_creadas": sum(1 for f in filas if f["instantanea_creada"]),
            "instantaneas_finales": len(pool.elegibles()),
            "segundos_totales": round(dt, 2),
            "segundos_actualizacion": round(t_upd, 2),
            "segundos_recogida_aprox": round(dt - t_upd, 2),
            "muestras_por_segundo": round(muestras / dt, 1) if dt > 0 else None,
        },
        "instantaneas": pool.elegibles(),
        "metricas_por_iteracion": filas,
        "checkpoints": guardados,
        "nota": "Smoke test. Las diferencias entre A y B NO son evidencia de mejora.",
    }
    Path(a.informe).parent.mkdir(parents=True, exist_ok=True)
    Path(a.informe).write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")

    c = informe["contabilidad"]
    print(f"\n== Brazo {a.brazo} ==")
    print(f"  muestras PPO      : {c['muestras_para_ppo']:,}   actualizaciones: {c['actualizaciones']}")
    print(f"  instantaneas      : creadas {c['instantaneas_creadas']}, en pool {c['instantaneas_finales']}")
    print(f"  recogida/actualiz : {c['segundos_recogida_aprox']}s / {c['segundos_actualizacion']}s")
    print(f"  muestras/s        : {c['muestras_por_segundo']}")
    print(f"  checkpoints       : {guardados}")
    print(f"  informe -> {a.informe}")
    return 0 if filas else 1


if __name__ == "__main__":
    raise SystemExit(main())
