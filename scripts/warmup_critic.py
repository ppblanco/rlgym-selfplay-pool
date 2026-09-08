"""Mide cuanto calentamiento necesita el critico antes de bifurcar A y B.

APORTACION NUEVA de rlgym-selfplay-pool.

EL PROBLEMA
-----------
El checkpoint de partida (diego_1.18B_512) trae SOLO la politica. El critico
arranca ALEATORIO, asi que sus ventajas son ruido y las primeras
actualizaciones degradan una politica ya entrenada. Bifurcar los brazos ahi
seria repartir ruido a partes iguales y llamarlo experimento.

Este script busca el punto donde:
  (a) el critico deja de estar claramente desalineado,
  (b) la politica no ha derivado demasiado del punto de partida,
  (c) el entrenamiento es estable.

LA METRICA QUE MANDA: VARIANZA EXPLICADA
----------------------------------------
    EV = 1 - Var(retornos - valores) / Var(retornos)

Se calcula ANTES de cada actualizacion, sobre datos frescos que el critico aun
no ha visto, con lo que ya tiene el buffer de rlgym-ppo:
retornos = values + advantages (definicion de GAE).

    EV ~ 0    el critico no predice mejor que la media -> desalineado
    EV -> 1   el critico explica la varianza de los retornos

No se decide con una sola metrica: EV se cruza con la deriva de la politica y
con la estabilidad de KL, entropia y clip fraction.

La recompensa de entrenamiento NO se usa como prueba de calidad del bot.

Uso:
    python scripts/warmup_critic.py --meshes RUTA --rival CKPT --politica CKPT
        --salida DIR --iteraciones 30 --lote 8000 --informe FILE.json
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


def _vector_parametros(modulo):
    import torch

    with torch.no_grad():
        return torch.cat([p.detach().reshape(-1) for p in modulo.parameters()]).clone()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--rival", required=True, help="Rival congelado de desarrollo.")
    p.add_argument("--politica", required=True, help="Checkpoint del que salen los pesos.")
    p.add_argument("--salida", required=True)
    p.add_argument("--iteraciones", type=int, default=30)
    p.add_argument("--lote", type=int, default=8000)
    p.add_argument("--n-proc", type=int, default=2)
    p.add_argument("--semilla", type=int, default=20260907)
    p.add_argument("--minutos", type=float, default=6.0)
    p.add_argument("--recompensa", default=None, help="YAML de recompensa; por defecto DefaultReward.")
    p.add_argument("--informe", required=True)
    a = p.parse_args()

    import numpy as np
    import torch
    from rlgym_ppo import Learner

    from rlbot.env.frozen_opponent import ConstructorRivalCongelado

    torch.manual_seed(a.semilla)
    np.random.seed(a.semilla)
    torch.set_num_threads(1)

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    ctor = ConstructorRivalCongelado(mallas=a.meshes, ckpt_rival=a.rival, hilos_torch=1,
                                     recompensa=a.recompensa)
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
        save_every_ts=a.lote,                 # un checkpoint por iteracion
        timestep_limit=a.iteraciones * a.lote,
        log_to_wandb=False,
        checkpoints_save_folder=str(salida),
        policy_layer_sizes=(512, 512, 512),
        critic_layer_sizes=(512, 512, 512),
        render=False,
        device="cpu",
    )

    pol, val = learner.ppo_learner.policy, learner.ppo_learner.value_net

    # Politica <- pesos ajenos. Critico y optimizadores NUEVOS: inicializar != reanudar.
    sd = torch.load(Path(a.politica) / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    pol.load_state_dict(sd)
    learner.agent.policy = pol
    p0 = _vector_parametros(pol)
    norma_p0 = float(p0.norm())
    print(f"  politica <- {a.politica}  |  critico ALEATORIO, optimizadores NUEVOS")
    print(f"  norma inicial de la politica: {norma_p0:.4f}")

    filas: list[dict] = []
    t0 = time.perf_counter()
    limite = a.minutos * 60
    original = learner.ppo_learner.learn

    def learn_instrumentado(buffer):
        # EV ANTES de actualizar: mide el critico contra datos que aun no ha visto.
        with torch.no_grad():
            v = buffer.values.detach().reshape(-1).float()
            adv = buffer.advantages.detach().reshape(-1).float()
            ret = v + adv                       # definicion de GAE
            var_ret = float(ret.var())
            ev = float(1.0 - (ret - v).var() / var_ret) if var_ret > 1e-12 else float("nan")
            est = {
                "ev_critico": ev,
                "valores_media": float(v.mean()),
                "valores_std": float(v.std()),
                "retornos_media": float(ret.mean()),
                "retornos_std": float(ret.std()),
                "muestras_buffer": int(v.numel()),
            }

        rep = original(buffer)

        with torch.no_grad():
            pt = _vector_parametros(pol)
            deriva = float((pt - p0).norm() / (norma_p0 + 1e-12))
            grad_pol_finitos = all(
                torch.isfinite(q.grad).all().item() for q in pol.parameters() if q.grad is not None
            )
            grad_val_finitos = all(
                torch.isfinite(q.grad).all().item() for q in val.parameters() if q.grad is not None
            )
            params_finitos = bool(torch.isfinite(pt).all())

        fila = {
            "iteracion": len(filas) + 1,
            "timesteps": int(learner.agent.cumulative_timesteps),
            "segundos": round(time.perf_counter() - t0, 2),
            **est,
            "deriva_politica_relativa": deriva,
            "gradientes_politica_finitos": bool(grad_pol_finitos),
            "gradientes_critico_finitos": bool(grad_val_finitos),
            "parametros_finitos": params_finitos,
            **{k: float(v2) for k, v2 in rep.items() if isinstance(v2, (int, float))},
        }
        filas.append(fila)
        print(
            f"  it{fila['iteracion']:>3} ts={fila['timesteps']:>7}  EV={ev:+.4f}  "
            f"vf_loss={fila.get('Value Function Loss', float('nan')):.5f}  "
            f"deriva={deriva:.5f}  ent={fila.get('Policy Entropy', 0):.3f}  "
            f"KL={fila.get('Mean KL Divergence', 0):.2e}  clip={fila.get('SB3 Clip Fraction', 0):.4f}"
        )

        if time.perf_counter() - t0 > limite:
            print(f"  [tope de {a.minutos} min alcanzado]")
            learner.timestep_limit = 0
        return rep

    learner.ppo_learner.learn = learn_instrumentado

    print(f"\n== Calentamiento: hasta {a.iteraciones} iteraciones de {a.lote:,} muestras ==")
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

    # ---- decision, cruzando VARIAS metricas ------------------------------
    decision = {"criterios": [
        "razon valores/retornos del critico dentro de [0,90, 1,10] (calibracion de nivel)",
        "esa razon estable en las ultimas 3 iteraciones (rango < 0,20)",
        "deriva relativa de la politica por debajo de 0,05",
        "gradientes y parametros finitos en todas las iteraciones",
        "KL y clip fraction sin dispararse",
    ]}
    elegida = None
    for i, f in enumerate(filas):
        if i < 2:
            continue
        razon = f["valores_media"] / f["retornos_media"] if abs(f["retornos_media"]) > 1e-9 else float("nan")
        f["calibracion_critico"] = razon
        ev_ok = 0.90 <= razon <= 1.10
        estable = f["deriva_politica_relativa"] < 0.05
        finito = f["gradientes_critico_finitos"] and f["parametros_finitos"]
        # "ya sin subir de forma marcada": la mejora media de las ultimas 3 < 0.05
        ventana = [x["valores_media"] / x["retornos_media"] for x in filas[max(0, i - 2): i + 1]
                   if abs(x["retornos_media"]) > 1e-9]
        meseta = bool(ventana) and (max(ventana) - min(ventana)) < 0.20
        if ev_ok and estable and finito and meseta:
            elegida = f
            break

    resumen = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "configuracion": {
            "politica_inicial": a.politica,
            "recompensa": a.recompensa or "default",
            "rival": a.rival,
            "semilla": a.semilla,
            "lote": a.lote,
            "n_proc": a.n_proc,
            "hilos_torch_por_trabajador": 1,
            "ppo_epochs": 1,
            "arquitectura": [512, 512, 512],
            "standardize_returns": True,
            "standardize_obs": False,
        },
        "iteraciones_completadas": len(filas),
        "metricas_por_iteracion": filas,
        "decision": decision,
        "punto_elegido": elegida,
        "nota": "La recompensa de entrenamiento no se usa como prueba de calidad del bot.",
    }
    Path(a.informe).parent.mkdir(parents=True, exist_ok=True)
    Path(a.informe).write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== Decision ==")
    if elegida:
        print(f"  punto de calentamiento: iteracion {elegida['iteracion']} "
              f"= {elegida['timesteps']:,} muestras")
        print(f"    EV={elegida['ev_critico']:+.4f}  deriva={elegida['deriva_politica_relativa']:.5f}")
    else:
        print("  NINGUN punto cumple los cuatro criterios en este presupuesto.")
        if filas:
            u = filas[-1]
            print(f"    ultima iteracion: EV={u['ev_critico']:+.4f} "
                  f"deriva={u['deriva_politica_relativa']:.5f}")
    print(f"  informe -> {a.informe}")
    return 0 if filas else 1


if __name__ == "__main__":
    raise SystemExit(main())
