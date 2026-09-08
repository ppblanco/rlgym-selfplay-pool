"""Diagnostico de recompensa: entrena UNA configuracion en ESTE proceso.

APORTACION NUEVA de rlgym-selfplay-pool.

Todo lo que no es la recompensa es identico entre configuraciones y sale del
protocolo: mismo C0, misma semilla, misma arquitectura, mismo entorno, mismos
trabajadores, mismo presupuesto y el mismo rival C0 fijo.

Un proceso por configuracion, como en la fase 0 de H2: asi no se hereda el
estado de sockets de rlgym_ppo entre corridas.

Uso:
    python scripts/reward_diagnostic/train_diag.py --config CONF.json
        --id D_A --meshes RUTA --raiz-salida DIR
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/experimento/reward-diagnostic/protocolo.json")
    ap.add_argument("--id", required=True)
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--raiz-salida", required=True)
    a = ap.parse_args()

    import numpy as np
    import torch
    from rlgym_ppo import Learner

    from rlbot.env.frozen_opponent import ConstructorRivalCongelado

    prot = json.loads((RAIZ / a.config).read_text(encoding="utf-8"))
    # El bloque comun se llama distinto segun cuantas configuraciones compare
    # el protocolo. Se acepta cualquiera en vez de fallar por el nombre.
    comunes = [k for k in prot if k.startswith("identico_en_las_")]
    if len(comunes) != 1:
        raise SystemExit(f"  ! Se esperaba un unico bloque comun y hay {comunes}")
    com = prot[comunes[0]]
    conf = prot["configuraciones"][a.id]

    # La ruta del protocolo es portable (%LOCALAPPDATA%): se expande.
    c0 = Path(os.path.expandvars(prot["c0"]["ruta"]))
    for nombre, h in prot["c0"]["hashes"].items():
        if sha256_archivo(c0 / nombre) != h:
            raise SystemExit(f"  ! C0 alterado: {nombre}")

    semilla = int(com["semilla_entrenamiento"])
    presupuesto = int(com["presupuesto"])
    hitos = sorted(int(x) for x in com["hitos"])
    lote = int(com["ejecucion"]["lote_ppo"])
    n_proc = int(com["ejecucion"]["n_proc"])
    arch = tuple(com["arquitectura_politica"])
    ts0 = int(prot["c0"]["cumulative_timesteps"])
    ppo = com["ppo"]
    recompensa = conf["recompensa"]

    dir_run = Path(a.raiz_salida) / a.id
    inf_previo = dir_run / "informe.json"
    if inf_previo.exists():
        d = json.loads(inf_previo.read_text(encoding="utf-8"))
        if d.get("estado") == "COMPLETA":
            print(f"  [{a.id}] ya estaba COMPLETA. No se repite nada.")
            return 0
    if dir_run.exists():
        shutil.rmtree(dir_run)
    dir_ckpt = dir_run / "checkpoints"
    dir_hitos = dir_run / "hitos"
    for d in (dir_ckpt, dir_hitos):
        d.mkdir(parents=True)

    torch.manual_seed(semilla)
    np.random.seed(semilla)
    torch.set_num_threads(1)

    ctor = ConstructorRivalCongelado(
        mallas=a.meshes, ckpt_rival=str(c0),
        hilos_torch=int(com["ejecucion"]["hilos_torch_por_trabajador"]),
        recompensa=recompensa, timeout_pasos=300,
    )
    learner = Learner(
        ctor, n_proc=n_proc, min_inference_size=max(1, n_proc // 2), metrics_logger=None,
        ppo_batch_size=lote, ts_per_iteration=lote, exp_buffer_size=lote,
        ppo_minibatch_size=int(ppo["minibatch"]), ppo_epochs=int(ppo["epochs"]),
        ppo_ent_coef=float(ppo["ent_coef"]),
        standardize_returns=bool(ppo["standardize_returns"]),
        standardize_obs=bool(ppo["standardize_obs"]),
        save_every_ts=lote * 25, timestep_limit=ts0 + presupuesto,
        log_to_wandb=False, checkpoints_save_folder=str(dir_ckpt),
        checkpoint_load_folder=str(c0),
        policy_layer_sizes=arch, critic_layer_sizes=arch,
        render=False, device="cpu",
    )
    pol = learner.ppo_learner.policy
    ts_inicial = int(learner.agent.cumulative_timesteps)

    filas: list[dict] = []
    guardados: list[dict] = []
    pendientes = list(hitos)
    t0 = time.perf_counter()
    original = learner.ppo_learner.learn

    def guardar(muestras: int, ts: int) -> dict:
        d = dir_hitos / f"h_{muestras:09d}"
        d.mkdir(parents=True, exist_ok=True)
        torch.save(pol.state_dict(), d / "PPO_POLICY.pt")
        reg = {"muestras": muestras, "timesteps": ts, "ruta": str(d),
               "sha256": sha256_archivo(d / "PPO_POLICY.pt")}
        print(f"    hito {muestras:,} -> {reg['sha256'][:16]}", flush=True)
        return reg

    def hook(buffer):
        rep = original(buffer)
        ts = int(learner.agent.cumulative_timesteps)
        muestras = ts - ts_inicial
        while pendientes and muestras >= pendientes[0]:
            guardados.append(guardar(pendientes.pop(0), ts))
        filas.append({
            "iteracion": len(filas) + 1, "muestras": muestras,
            "segundos": round(time.perf_counter() - t0, 2),
            **{k: float(v) for k, v in rep.items() if isinstance(v, (int, float))},
        })
        if len(filas) % 15 == 0:
            f = filas[-1]
            print(f"    it{f['iteracion']:>3} muestras={muestras:>8,} "
                  f"rew={f.get('Policy Reward', 0):>9.4f} "
                  f"ent={f.get('Policy Entropy', 0):.3f} "
                  f"vf={f.get('Value Function Loss', 0):.4f} {f['segundos']:.0f}s", flush=True)
        return rep

    learner.ppo_learner.learn = hook
    print(f"  [{a.id}] {conf['etiqueta']}", flush=True)
    print(f"      recompensa={recompensa}  zero_sum={conf['zero_sum']}  "
          f"semilla={semilla}  presupuesto={presupuesto:,}", flush=True)

    error = None
    try:
        learner.learn()
    except Exception as e:  # noqa: BLE001
        error = repr(e)
        print(f"  ! error: {error}", flush=True)
    finally:
        try:
            learner.cleanup()
        except Exception as e:  # noqa: BLE001
            print(f"    (cleanup: {e!r} — sin efecto: un proceso por configuracion)", flush=True)

    dt = time.perf_counter() - t0
    ts_final = int(learner.agent.cumulative_timesteps)
    muestras = ts_final - ts_inicial
    if pendientes and error is None:
        guardados.append(guardar(pendientes[0], ts_final))

    finitos = all(torch.isfinite(p).all().item() for p in pol.parameters())
    ult = filas[-1] if filas else {}
    ent_final = float(ult.get("Policy Entropy", 0.0))
    vf_final = float(ult.get("Value Function Loss", 0.0))
    import math
    vf_sano = math.isfinite(vf_final)
    # rlgym-ppo escribe en una carpeta HERMANA con sufijo, no dentro de la dada.
    ckpts = sorted(dir_ckpt.parent.glob(dir_ckpt.name + "*/*/PPO_POLICY.pt"),
                   key=lambda p: int(p.parent.name))
    ckpt_final = ckpts[-1].parent if ckpts else None
    completa = error is None and muestras >= presupuesto and finitos

    informe = {
        "estado": "COMPLETA" if completa else "INCOMPLETA",
        "id": a.id, "etiqueta": conf["etiqueta"], "fase": "diagnostico-recompensa",
        "recompensa": recompensa, "zero_sum": conf["zero_sum"],
        "recompensa_sha256": sha256_archivo(RAIZ / recompensa),
        "semilla": semilla,
        "protocolo_sha256": hashlib.sha256(
            (RAIZ / a.config).read_text(encoding="utf-8").rstrip("\n").encode("utf-8")).hexdigest(),
        "resultado": {
            "error": error, "muestras": muestras, "actualizaciones": len(filas),
            "segundos_total": round(dt, 2),
            "muestras_por_segundo": round(muestras / dt, 1) if dt else None,
        },
        "estabilidad": {
            "parametros_finitos": bool(finitos),
            "entropia_final": ent_final, "vf_loss_final": vf_final,
            "vf_loss_finito": vf_sano,
            "recompensa_media_ultimas_10": (
                round(sum(f.get("Policy Reward", 0.0) for f in filas[-10:]) / min(10, len(filas)), 4)
                if filas else None),
        },
        "integridad": {
            "c0_intacto": sha256_archivo(c0 / "PPO_POLICY.pt") == prot["c0"]["hashes"]["PPO_POLICY.pt"],
            "checkpoint_final": str(ckpt_final) if ckpt_final else None,
        },
        "hitos": guardados,
        "metricas_por_iteracion": filas,
    }
    (dir_run / "informe.json").write_text(
        json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    r = informe["resultado"]
    print(f"  [{a.id}] {informe['estado']} muestras={r['muestras']:,} "
          f"{r['segundos_total']:,.0f}s ent={ent_final:.3f} vf={vf_final:.4f} "
          f"hitos={len(guardados)}", flush=True)
    return 0 if completa else 1


if __name__ == "__main__":
    raise SystemExit(main())
