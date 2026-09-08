"""Entrenamiento real MINIMO: experiencia del simulador, no datos sinteticos.

APORTACION NUEVA de rlgym-selfplay-pool.

Que demuestra:
  recoger experiencia real -> actualizar el modelo -> guardarlo -> recuperarlo.

Que NO demuestra: que el bot juegue mejor. Es un presupuesto de juguete.

INICIALIZAR NO ES REANUDAR
--------------------------
El checkpoint de desarrollo (diego_1.18B_512) trae SOLO PPO_POLICY.pt. No tiene
critico, ni optimizadores, ni estadisticas. Por tanto esto es una
INICIALIZACION DE PESOS DE LA POLITICA, no una reanudacion:

    politica      <- pesos del checkpoint ajeno
    critico       <- ALEATORIO (inicializacion nueva)
    optimizadores <- NUEVOS (estado de Adam a cero)
    normalizacion <- standardize_obs=False, asi que no hay estadistica de obs
                     que restaurar; standardize_returns si acumula, y empieza
                     de cero en esta ejecucion

Con el critico al azar, las primeras ventajas son ruido. Para el experimento
eso obliga a que los DOS brazos partan del mismo punto ya calentado. Aqui no
importa, porque no se compara nada.

Uso:
    python scripts/train_smoke.py --meshes RUTA --rival CKPT --salida DIR
           [--timesteps 30000] [--n-proc 2] [--minutos 5]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("WANDB_MODE", "disabled")   # sin telemetria ni sesiones
os.environ.setdefault("WANDB_SILENT", "true")


def hash_parametros(modulo) -> str:
    import hashlib

    import torch

    h = hashlib.sha256()
    with torch.no_grad():
        for p in modulo.parameters():
            h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()[:16]


def resumen_parametros(modulo) -> dict:
    import torch

    with torch.no_grad():
        vals = torch.cat([p.detach().reshape(-1) for p in modulo.parameters()])
        return {
            "n_parametros": int(vals.numel()),
            "media": float(vals.mean()),
            "norma": float(vals.norm()),
            "finitos": bool(torch.isfinite(vals).all()),
        }


def construir_learner(args, salida: Path):
    import torch
    from rlgym_ppo import Learner

    from rlbot.env.frozen_opponent import ConstructorRivalCongelado

    torch.set_num_threads(args.hilos)

    ctor = ConstructorRivalCongelado(
        mallas=args.meshes,
        ckpt_rival=args.rival,
        timeout_pasos=args.timeout_pasos,
        hilos_torch=1,          # cada trabajador con 1 hilo
    )

    learner = Learner(
        ctor,
        n_proc=args.n_proc,
        min_inference_size=max(1, args.n_proc // 2),
        metrics_logger=None,
        ppo_batch_size=args.lote,
        ts_per_iteration=args.lote,
        exp_buffer_size=args.lote,
        ppo_minibatch_size=args.lote,
        ppo_epochs=1,
        ppo_ent_coef=0.01,
        standardize_returns=True,
        standardize_obs=False,
        save_every_ts=args.lote,          # guarda cada iteracion
        timestep_limit=args.timesteps,
        log_to_wandb=False,
        checkpoints_save_folder=str(salida),
        checkpoint_load_folder=args.reanudar,
        policy_layer_sizes=(512, 512, 512),
        critic_layer_sizes=(512, 512, 512),
        render=False,
        device="cpu",
    )
    return learner


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--rival", required=True)
    p.add_argument("--salida", required=True, help="Carpeta EXCLUSIVA de esta prueba.")
    p.add_argument("--init-politica", default=None,
                   help="Checkpoint del que copiar SOLO los pesos de la politica.")
    p.add_argument("--reanudar", default=None,
                   help="Checkpoint COMPLETO nuestro del que reanudar de verdad.")
    p.add_argument("--timesteps", type=int, default=30_000)
    p.add_argument("--lote", type=int, default=10_000)
    p.add_argument("--n-proc", type=int, default=2)
    p.add_argument("--hilos", type=int, default=2)
    p.add_argument("--timeout-pasos", type=int, default=300)
    p.add_argument("--minutos", type=float, default=6.0, help="Tope duro de reloj.")
    p.add_argument("--informe", default=None)
    a = p.parse_args()

    import torch

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    inicio_total = time.perf_counter()
    print("== Construccion del learner ==")
    learner = construir_learner(a, salida)
    pol, val = learner.ppo_learner.policy, learner.ppo_learner.value_net

    info: dict = {
        "modo": "reanudacion" if a.reanudar else "inicializacion_de_pesos",
        "reanudar_desde": a.reanudar,
        "init_politica_desde": a.init_politica,
        "timesteps_objetivo": a.timesteps,
        "lote": a.lote,
        "n_proc": a.n_proc,
        "hilos_torch_principal": a.hilos,
        "ts_al_construir": int(learner.agent.cumulative_timesteps),
    }

    if a.init_politica:
        # INICIALIZACION, no reanudacion: solo la politica.
        ckpt = Path(a.init_politica) / "PPO_POLICY.pt"
        sd = torch.load(ckpt, map_location="cpu", weights_only=True)
        pol.load_state_dict(sd)
        learner.agent.policy = pol
        info["politica_cargada_de"] = str(ckpt)
        info["critico"] = "ALEATORIO (el checkpoint no trae PPO_VALUE_NET.pt)"
        info["optimizadores"] = "NUEVOS (el checkpoint no trae estado de Adam)"
        info["normalizacion_obs"] = "standardize_obs=False: no hay estadistica que restaurar"
        info["normalizacion_retornos"] = "standardize_returns=True: empieza de cero"
        print(f"  politica <- {ckpt}")
        print("  critico ALEATORIO, optimizadores NUEVOS  (inicializar != reanudar)")

    h_pol_ini, h_val_ini = hash_parametros(pol), hash_parametros(val)
    info["politica_antes"] = {"hash": h_pol_ini, **resumen_parametros(pol)}
    info["critico_antes"] = {"hash": h_val_ini, **resumen_parametros(val)}
    print(f"  politica antes: {h_pol_ini} | critico antes: {h_val_ini}")

    # -- tope duro de reloj, independiente de que termine una iteracion -----
    limite = a.minutos * 60.0
    t0 = time.perf_counter()
    original_learn = learner.ppo_learner.learn
    iteraciones = {"n": 0, "reportes": []}

    def learn_con_tope(buffer):
        rep = original_learn(buffer)
        iteraciones["n"] += 1
        iteraciones["reportes"].append(
            {k: float(v) for k, v in rep.items() if isinstance(v, (int, float))}
        )
        if time.perf_counter() - t0 > limite:
            print(f"\n  [tope de {a.minutos} min alcanzado tras {iteraciones['n']} iteraciones]")
            learner.timestep_limit = 0     # corta el bucle de learn()
        return rep

    learner.ppo_learner.learn = learn_con_tope

    print(f"\n== Entrenando (tope {a.timesteps:,} muestras o {a.minutos} min) ==")
    interrumpido = False
    try:
        learner.learn()
    except KeyboardInterrupt:
        interrumpido = True
        print("  interrumpido a mano")
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

    h_pol_fin, h_val_fin = hash_parametros(pol), hash_parametros(val)
    info.update(
        {
            "iteraciones_completadas": iteraciones["n"],
            "muestras_recogidas": ts_final - info["ts_al_construir"],
            "ts_final": ts_final,
            "segundos_entrenando": round(dt, 2),
            "segundos_totales": round(time.perf_counter() - inicio_total, 2),
            "interrumpido": interrumpido,
            "politica_despues": {"hash": h_pol_fin, **resumen_parametros(pol)},
            "critico_despues": {"hash": h_val_fin, **resumen_parametros(val)},
            "politica_cambio": h_pol_ini != h_pol_fin,
            "critico_cambio": h_val_ini != h_val_fin,
            "reportes_ppo": iteraciones["reportes"],
        }
    )
    if ts_final > info["ts_al_construir"] and dt > 0:
        info["muestras_por_segundo"] = round(info["muestras_recogidas"] / dt, 1)

    print("\n== Resultado ==")
    print(f"  iteraciones completadas : {iteraciones['n']}")
    print(f"  muestras recogidas      : {info['muestras_recogidas']:,}")
    print(f"  segundos                : {dt:,.1f}")
    if "muestras_por_segundo" in info:
        print(f"  muestras/s              : {info['muestras_por_segundo']:,}")
    print(f"  politica cambio         : {info['politica_cambio']} ({h_pol_ini} -> {h_pol_fin})")
    print(f"  critico  cambio         : {info['critico_cambio']} ({h_val_ini} -> {h_val_fin})")
    print(f"  parametros finitos      : politica={info['politica_despues']['finitos']} "
          f"critico={info['critico_despues']['finitos']}")
    if iteraciones["reportes"]:
        ult = iteraciones["reportes"][-1]
        for k in ("Policy Entropy", "Mean KL Divergence", "Policy Update Magnitude",
                  "Value Function Update Magnitude", "SB3 Clip Fraction"):
            if k in ult:
                print(f"  {k:<32}: {ult[k]:.6g}")

    guardados = sorted(d.name for d in salida.iterdir() if d.is_dir())
    info["checkpoints_guardados"] = guardados
    print(f"  checkpoints en {salida}: {guardados}")

    if a.informe:
        Path(a.informe).parent.mkdir(parents=True, exist_ok=True)
        Path(a.informe).write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  informe -> {a.informe}")

    # Una prueba sin iteraciones NO es un aprobado.
    return 0 if iteraciones["n"] > 0 and info["politica_cambio"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
