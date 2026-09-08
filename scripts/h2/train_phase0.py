"""H2 fase 0: entrena UN linaje (sparring neutral o piloto) en ESTE proceso.

APORTACION NUEVA de rlgym-selfplay-pool.

Este script entrena exactamente una corrida y termina. Nunca dos. Es el
conductor (`driver_h2.py`) quien lanza un proceso limpio por corrida, para que
el estado de sockets de rlgym_ppo no se herede entre corridas: esa fue la causa
del interbloqueo de H1 entre B1 y A2.

Esquemas:
  fijo  -> el rival es C0 congelado durante toda la corrida. Linaje NEUTRAL:
           no es el brazo A ni el brazo B. Ademas alimenta un pool de retencion
           16 SOLO para comprobar que la expulsion se activa; ese pool nunca se
           usa como rival.
  pool  -> el rival se muestrea de un pool con la retencion indicada. Con
           retencion 1 es el esquema de CONTROL (brazo A).

Garantias de reproducibilidad operativa:
  - marcador explicito COMPLETA / INCOMPLETA en informe.json;
  - una corrida INCOMPLETA se rehace entera desde C0, nunca se continua;
  - se archivan TODAS las instantaneas aparte, sin retencion, para poder medir
    diversidad sobre cualquier ventana;
  - se registra el estado RNG que de verdad puede conservarse.

Uso:
    python scripts/h2/train_phase0.py --config configs/experimento/h2/fase0.json
        --linaje sparring --meshes RUTA --raiz-salida DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

os.environ.setdefault("WANDB_MODE", "disabled")
os.environ.setdefault("WANDB_SILENT", "true")


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verificar_c0(cfg: dict) -> Path:
    # La ruta del protocolo es portable (%LOCALAPPDATA%): se expande.
    c0 = Path(os.path.expandvars(cfg["c0"]["ruta"]))
    for nombre, h in cfg["c0"]["hashes"].items():
        real = sha256_archivo(c0 / nombre)
        if real != h:
            raise SystemExit(f"  ! C0 alterado: {nombre}\n    {real} != {h}")
    return c0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/experimento/h2/fase0.json")
    ap.add_argument("--linaje", required=True, choices=["sparring", "piloto"])
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--raiz-salida", required=True)
    ap.add_argument("--presupuesto", type=int, default=None,
                    help="Solo para la prueba corta de infraestructura. Queda registrado.")
    ap.add_argument("--hitos", default=None,
                    help="Solo para la prueba corta. Lista separada por comas.")
    a = ap.parse_args()

    import numpy as np
    import torch
    from rlgym_ppo import Learner

    from rlbot.env.frozen_opponent import ConstructorPool, ConstructorRivalCongelado
    from rlbot.env.opponent_pool import PoolRivales
    from rlgym_ppo.ppo import DiscreteFF

    cfg = json.loads((RAIZ / a.config).read_text(encoding="utf-8"))
    lin = cfg["linajes"][a.linaje]
    c0 = verificar_c0(cfg)

    run_id = lin["id"]
    semilla = int(lin["semilla"])
    presupuesto = int(a.presupuesto) if a.presupuesto else int(lin["presupuesto"])
    K = int(lin["K_archivo"])
    hitos = sorted(int(x) for x in (a.hitos.split(",") if a.hitos else lin["hitos"]))
    prueba_corta = a.presupuesto is not None
    if prueba_corta:
        K = max(8000, presupuesto // 4)  # que el archivo y la retencion se ejerciten igual
    lote = int(cfg["ejecucion"]["lote_ppo"])
    n_proc = int(cfg["ejecucion"]["n_proc"])
    arch = tuple(cfg["modelo"]["arquitectura_politica"])
    ts0 = int(cfg["c0"]["cumulative_timesteps"])
    recompensa = cfg["recompensa"]["archivo"]
    ppo = cfg["ppo"]

    dir_run = Path(a.raiz_salida) / run_id
    # -- reanudacion idempotente: COMPLETA se respeta, INCOMPLETA se rehace ---
    inf_previo = dir_run / "informe.json"
    if inf_previo.exists():
        d = json.loads(inf_previo.read_text(encoding="utf-8"))
        if d.get("estado") == "COMPLETA":
            print(f"  [{run_id}] ya estaba COMPLETA. No se repite nada.")
            return 0
        print(f"  [{run_id}] habia una corrida INCOMPLETA: se descarta entera y se rehace desde C0.")
    if dir_run.exists():
        shutil.rmtree(dir_run)
    dir_ckpt = dir_run / "checkpoints"
    dir_pool = dir_run / "pool"
    dir_arch = dir_run / "archivo"
    dir_hitos = dir_run / "hitos"
    for d in (dir_ckpt, dir_pool, dir_arch, dir_hitos):
        d.mkdir(parents=True)

    torch.manual_seed(semilla)
    np.random.seed(semilla)
    torch.set_num_threads(1)
    estado_rng = {
        "semilla": semilla,
        "torch_rng_sha256": hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest(),
        "numpy_rng_sha256": hashlib.sha256(
            np.random.get_state()[1].tobytes()).hexdigest(),
        "nota": "estado tras sembrar y antes de construir nada; lo que de verdad se puede conservar",
    }

    # -- instantanea inicial desde C0, ANTES de construir el Learner ---------
    sd0 = torch.load(c0 / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    wk = [k for k in sd0 if k.endswith("weight")]
    pol0 = DiscreteFF(89, 90, tuple(int(sd0[k].shape[0]) for k in wk[:-1]), "cpu")
    pol0.load_state_dict(sd0)
    id_c0 = f"snap_{ts0:012d}"

    meta = {"linaje": run_id, "esquema": lin["esquema"], "semilla": semilla,
            "origen": "C0", "fase": "H2-fase0"}

    # Archivo SIN retencion: sirve para medir diversidad en cualquier ventana.
    archivo = PoolRivales(dir_arch, retencion=10_000)
    archivo.guardar_instantanea(pol0, ts0, meta)

    if lin["esquema"] == "fijo":
        # Linaje NEUTRAL: rival C0 fijo. El pool16 es solo un banco de pruebas
        # de la regla de retencion; jamas se consulta como rival.
        pool16 = PoolRivales(dir_pool, retencion=int(lin["retencion_prueba"]),
                             proteger=(id_c0,))
        pool16.guardar_instantanea(pol0, ts0, meta)
        ctor = ConstructorRivalCongelado(
            mallas=a.meshes, ckpt_rival=str(c0),
            hilos_torch=int(cfg["ejecucion"]["hilos_torch_por_trabajador"]),
            recompensa=recompensa, timeout_pasos=300,
        )
        pool_rival = None
    else:
        pool16 = None
        retencion = int(lin["retencion"])
        proteger = (id_c0,) if lin.get("protege_c0") else ()
        pool_rival = PoolRivales(dir_pool, retencion, proteger=proteger)
        pool_rival.guardar_instantanea(pol0, ts0, meta)
        ctor = ConstructorPool(
            mallas=a.meshes, carpeta_pool=str(dir_pool), retencion=retencion,
            semilla=semilla,
            hilos_torch=int(cfg["ejecucion"]["hilos_torch_por_trabajador"]),
            recompensa=recompensa, timeout_pasos=300,
        )

    learner = Learner(
        ctor, n_proc=n_proc, min_inference_size=max(1, n_proc // 2), metrics_logger=None,
        ppo_batch_size=lote, ts_per_iteration=lote, exp_buffer_size=lote,
        ppo_minibatch_size=int(ppo["minibatch"]), ppo_epochs=int(ppo["epochs"]),
        ppo_ent_coef=float(ppo["ent_coef"]),
        standardize_returns=bool(ppo["standardize_returns"]),
        standardize_obs=bool(ppo["standardize_obs"]),
        save_every_ts=lote * 25,
        timestep_limit=ts0 + presupuesto,
        log_to_wandb=False, checkpoints_save_folder=str(dir_ckpt),
        checkpoint_load_folder=str(c0),
        policy_layer_sizes=arch, critic_layer_sizes=arch,
        render=False, device="cpu",
    )
    pol = learner.ppo_learner.policy
    ts_inicial = int(learner.agent.cumulative_timesteps)

    filas: list[dict] = []
    hitos_guardados: list[dict] = []
    proxima = ts_inicial + K
    pendientes = list(hitos)
    t0 = time.perf_counter()
    original = learner.ppo_learner.learn
    t_ppo = [0.0]

    def guardar_hito(muestras: int, ts: int) -> dict:
        d = dir_hitos / f"h_{muestras:09d}"
        d.mkdir(parents=True, exist_ok=True)
        torch.save(pol.state_dict(), d / "PPO_POLICY.pt")
        reg = {"muestras": muestras, "timesteps": ts, "ruta": str(d),
               "sha256": sha256_archivo(d / "PPO_POLICY.pt")}
        print(f"    hito {muestras:,} muestras -> {reg['sha256'][:16]}", flush=True)
        return reg

    def hook(buffer):
        t = time.perf_counter()
        rep = original(buffer)
        t_ppo[0] += time.perf_counter() - t
        nonlocal proxima
        ts = int(learner.agent.cumulative_timesteps)
        muestras = ts - ts_inicial
        creada = None
        if ts >= proxima:
            creada = archivo.guardar_instantanea(pol, ts, meta)
            if pool16 is not None:
                pool16.guardar_instantanea(pol, ts, meta)
            proxima += K
        while pendientes and muestras >= pendientes[0]:
            hitos_guardados.append(guardar_hito(pendientes.pop(0), ts))
        filas.append({
            "iteracion": len(filas) + 1, "timesteps": ts, "muestras": muestras,
            "segundos": round(time.perf_counter() - t0, 2),
            "instantaneas_archivo": len(archivo.elegibles()),
            "instantaneas_pool": len(pool16.elegibles()) if pool16 is not None
                                 else (len(pool_rival.elegibles()) if pool_rival else 0),
            **{k: float(v) for k, v in rep.items() if isinstance(v, (int, float))},
        })
        if len(filas) % 25 == 0:
            f = filas[-1]
            print(f"    it{f['iteracion']:>4} muestras={muestras:>9,} "
                  f"arch={f['instantaneas_archivo']:>3} pool={f['instantaneas_pool']:>3} "
                  f"vf={f.get('Value Function Loss', 0):.4f} {f['segundos']:.0f}s", flush=True)
        return rep

    learner.ppo_learner.learn = hook

    print(f"  [{run_id}] linaje={a.linaje} esquema={lin['esquema']} semilla={semilla} "
          f"presupuesto={presupuesto:,} K={K:,}", flush=True)
    error = None
    try:
        learner.learn()
    except Exception as e:  # noqa: BLE001
        error = repr(e)
        print(f"  ! error durante el entrenamiento: {error}", flush=True)
    finally:
        try:
            learner.cleanup()
        except Exception as e:  # noqa: BLE001
            # Conocido en Windows: WinError 10038. Inofensivo AQUI porque este
            # proceso no ejecuta ninguna corrida mas.
            print(f"    (cleanup: {e!r} — sin efecto: un proceso por corrida)", flush=True)

    dt = time.perf_counter() - t0
    ts_final = int(learner.agent.cumulative_timesteps)
    muestras = ts_final - ts_inicial
    if pendientes and error is None:
        hitos_guardados.append(guardar_hito(pendientes[0], ts_final))

    finitos = all(torch.isfinite(p).all().item() for p in pol.parameters())
    # OJO: rlgym-ppo no escribe DENTRO de la carpeta que se le pasa, sino en una
    # hermana con sufijo: "checkpoints-<id>/<ts>/". Buscar solo en dir_ckpt da
    # cero resultados y marca la corrida INCOMPLETA aunque haya terminado bien.
    ckpts = sorted(dir_ckpt.parent.glob(dir_ckpt.name + "*/*/PPO_POLICY.pt"),
                   key=lambda p: int(p.parent.name))
    ckpt_final = ckpts[-1].parent if ckpts else None
    # Una corrida sin checkpoint final no es evaluable, asi que no puede ser
    # COMPLETA. En la prueba corta el presupuesto es menor que save_every_ts y
    # no da tiempo a escribir ninguno; solo ahi no se exige.
    completa = (error is None and muestras >= presupuesto and finitos
                and (ckpt_final is not None or prueba_corta))

    informe = {
        "estado": "COMPLETA" if completa else "INCOMPLETA",
        "linaje": run_id, "tipo": a.linaje, "esquema": lin["esquema"],
        "fase": "H2-fase0",
        "prueba_corta_de_infraestructura": prueba_corta,
        "no_forma_parte_del_resultado_experimental": True,
        "semilla": semilla,
        "config_sha256": hashlib.sha256(
            (RAIZ / a.config).read_bytes()).hexdigest(),
        "c0": {"ruta": str(c0), "hash_politica": cfg["c0"]["hashes"]["PPO_POLICY.pt"],
               "timesteps": ts0},
        "configuracion_resuelta": {
            "presupuesto": presupuesto, "K_archivo": K, "hitos": hitos,
            "lote": lote, "n_proc": n_proc, "arquitectura": list(arch),
            "recompensa": recompensa, "ppo": ppo,
            "retencion_pool": (int(lin["retencion_prueba"]) if lin["esquema"] == "fijo"
                               else int(lin["retencion"])),
        },
        "estado_rng": estado_rng,
        "resultado": {
            "error": error, "ts_inicial": ts_inicial, "ts_final": ts_final,
            "muestras": muestras, "actualizaciones": len(filas),
            "segundos_total": round(dt, 2), "segundos_ppo": round(t_ppo[0], 2),
            "muestras_por_segundo": round(muestras / dt, 1) if dt else None,
        },
        "integridad": {
            "parametros_finitos": bool(finitos),
            "instantaneas_archivo": len(archivo.elegibles()),
            "instantaneas_pool": (len(pool16.elegibles()) if pool16 is not None
                                  else (len(pool_rival.elegibles()) if pool_rival else 0)),
            "c0_intacto": sha256_archivo(c0 / "PPO_POLICY.pt") == cfg["c0"]["hashes"]["PPO_POLICY.pt"],
            "checkpoint_final": str(ckpt_final) if ckpt_final else None,
            "hash_checkpoint_final": sha256_archivo(ckpt_final / "PPO_POLICY.pt") if ckpt_final else None,
        },
        "hitos": hitos_guardados,
        "instantaneas_archivo": archivo.elegibles(),
        "metricas_por_iteracion": filas,
    }
    (dir_run / "informe.json").write_text(
        json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    r = informe["resultado"]
    print(f"  [{run_id}] {informe['estado']} muestras={r['muestras']:,} "
          f"it={r['actualizaciones']} {r['segundos_total']:,.0f}s "
          f"({r['muestras_por_segundo']:,.1f} m/s) hitos={len(hitos_guardados)}", flush=True)
    return 0 if completa else 1


if __name__ == "__main__":
    raise SystemExit(main())
