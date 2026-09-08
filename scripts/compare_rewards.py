"""Compara DefaultReward frente a stage_1_basics como senal de entrenamiento.

APORTACION NUEVA de rlgym-selfplay-pool.

LA PREGUNTA NO ES CUAL HACE MEJOR BOT
-------------------------------------
Es: con cual tenemos senal de aprendizaje suficientemente informativa para
estudiar H1 dentro de nuestro presupuesto.

Las escalas de recompensa NO son comparables entre si: stage_1_basics tiene
componentes densos y DefaultReward solo goles, asi que su retorno medio es
mayor por construccion. **Un retorno mas grande no es una ventaja.** Lo que se
compara es la INFORMATIVIDAD de la senal:

  - fraccion de pasos con recompensa distinta de cero (densidad),
  - dispersion relativa de la recompensa,
  - si el critico consigue calibrarse y como de rapido,
  - si la politica se mantiene estable (deriva, KL, entropia, clip),
  - coste de ejecucion.

Todo lo demas identico: mismo checkpoint inicial, mismas semillas, misma
arquitectura, 2 trabajadores, 1 hilo, mismas muestras.

Uso:
    python scripts/compare_rewards.py --meshes RUTA --politica CKPT
        --salida DIR --informe FILE.json [--iteraciones 8] [--lote 8000]
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


def _vec(modulo):
    import torch

    with torch.no_grad():
        return torch.cat([p.detach().reshape(-1) for p in modulo.parameters()]).clone()


def correr(nombre, recompensa, a) -> dict:
    import numpy as np
    import torch
    from rlgym_ppo import Learner

    from rlbot.env.frozen_opponent import ConstructorRivalCongelado

    torch.manual_seed(a.semilla)
    np.random.seed(a.semilla)
    torch.set_num_threads(1)

    salida = Path(a.salida) / nombre
    salida.mkdir(parents=True, exist_ok=True)

    ctor = ConstructorRivalCongelado(
        mallas=a.meshes, ckpt_rival=a.politica, hilos_torch=1, recompensa=recompensa
    )
    learner = Learner(
        ctor,
        n_proc=2, min_inference_size=1, metrics_logger=None,
        ppo_batch_size=a.lote, ts_per_iteration=a.lote,
        exp_buffer_size=a.lote, ppo_minibatch_size=a.lote,
        ppo_epochs=1, ppo_ent_coef=0.01,
        standardize_returns=True, standardize_obs=False,
        save_every_ts=a.lote * 1000,          # no queremos checkpoints aqui
        timestep_limit=a.iteraciones * a.lote,
        log_to_wandb=False,
        checkpoints_save_folder=str(salida),
        policy_layer_sizes=(512, 512, 512), critic_layer_sizes=(512, 512, 512),
        render=False, device="cpu",
    )
    pol, val = learner.ppo_learner.policy, learner.ppo_learner.value_net
    sd = torch.load(Path(a.politica) / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    pol.load_state_dict(sd)
    learner.agent.policy = pol
    p0 = _vec(pol)
    norma0 = float(p0.norm())

    filas: list[dict] = []
    t0 = time.perf_counter()
    original = learner.ppo_learner.learn

    def hook(buffer):
        with torch.no_grad():
            r = buffer.rewards.detach().reshape(-1).float()
            v = buffer.values.detach().reshape(-1).float()
            adv = buffer.advantages.detach().reshape(-1).float()
            ret = v + adv
            nz = float((r.abs() > 1e-9).float().mean())
            est = {
                "densidad_recompensa": nz,
                "recompensa_media": float(r.mean()),
                "recompensa_std": float(r.std()),
                "recompensa_absmax": float(r.abs().max()),
                "retorno_media": float(ret.mean()),
                "retorno_std": float(ret.std()),
                "valores_media": float(v.mean()),
                "calibracion_critico": float(v.mean() / ret.mean()) if abs(float(ret.mean())) > 1e-9 else float("nan"),
            }
        rep = original(buffer)
        with torch.no_grad():
            deriva = float((_vec(pol) - p0).norm() / (norma0 + 1e-12))
            gfin = all(torch.isfinite(q.grad).all().item() for q in pol.parameters() if q.grad is not None)
            gfin_v = all(torch.isfinite(q.grad).all().item() for q in val.parameters() if q.grad is not None)
        filas.append({
            "iteracion": len(filas) + 1,
            "timesteps": int(learner.agent.cumulative_timesteps),
            **est,
            "deriva_politica": deriva,
            "gradientes_finitos": bool(gfin and gfin_v),
            **{k: float(x) for k, x in rep.items() if isinstance(x, (int, float))},
        })
        f = filas[-1]
        print(f"    it{f['iteracion']:>2} dens={f['densidad_recompensa']:.3f} "
              f"r_std={f['recompensa_std']:.4f} calib={f['calibracion_critico']:+.3f} "
              f"vf={f.get('Value Function Loss', 0):.4f} deriva={deriva:.5f} "
              f"ent={f.get('Policy Entropy', 0):.3f} clip={f.get('SB3 Clip Fraction', 0):.4f}")
        return rep

    learner.ppo_learner.learn = hook
    print(f"  --- {nombre} ---")
    try:
        learner.learn()
    finally:
        try:
            learner.cleanup()
        except Exception:  # noqa: BLE001
            pass
    dt = time.perf_counter() - t0
    muestras = int(learner.agent.cumulative_timesteps)
    return {
        "nombre": nombre,
        "recompensa": recompensa or "default",
        "iteraciones": len(filas),
        "muestras": muestras,
        "segundos": round(dt, 2),
        "muestras_por_segundo": round(muestras / dt, 1) if dt else None,
        "metricas": filas,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--politica", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--informe", required=True)
    p.add_argument("--iteraciones", type=int, default=8)
    p.add_argument("--lote", type=int, default=8000)
    p.add_argument("--semilla", type=int, default=20260907)
    a = p.parse_args()

    raiz = Path(__file__).resolve().parents[1]
    stage1 = raiz / "configs" / "reward_weights" / "stage_1_basics.yaml"

    print("== Comparacion de recompensas (todo identico salvo la recompensa) ==")
    res_a = correr("A_default", None, a)
    res_b = correr("B_stage1", str(stage1), a)

    def resumen(r: dict) -> dict:
        m = r["metricas"]
        if not m:
            return {}
        ult3 = m[-3:] if len(m) >= 3 else m
        return {
            "densidad_media": round(sum(x["densidad_recompensa"] for x in m) / len(m), 4),
            "recompensa_std_media": round(sum(x["recompensa_std"] for x in m) / len(m), 5),
            "calibracion_primera": round(m[0]["calibracion_critico"], 4),
            "calibracion_ultima": round(m[-1]["calibracion_critico"], 4),
            "calibracion_media_ultimas3": round(sum(x["calibracion_critico"] for x in ult3) / len(ult3), 4),
            "deriva_final": round(m[-1]["deriva_politica"], 5),
            "entropia_final": round(m[-1].get("Policy Entropy", float("nan")), 4),
            "clip_max": round(max(x.get("SB3 Clip Fraction", 0) for x in m), 5),
            "kl_max": max(x.get("Mean KL Divergence", 0) for x in m),
            "vf_loss_primera": round(m[0].get("Value Function Loss", float("nan")), 5),
            "vf_loss_ultima": round(m[-1].get("Value Function Loss", float("nan")), 5),
            "gradientes_finitos_siempre": all(x["gradientes_finitos"] for x in m),
            "muestras_por_segundo": r["muestras_por_segundo"],
        }

    sa, sb = resumen(res_a), resumen(res_b)
    informe = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "configuracion_comun": {
            "politica_inicial": a.politica, "semilla": a.semilla, "lote": a.lote,
            "iteraciones": a.iteraciones, "n_proc": 2, "hilos_torch": 1,
            "arquitectura": [512, 512, 512], "ppo_epochs": 1,
        },
        "A_default": res_a, "B_stage1": res_b,
        "resumen_A_default": sa, "resumen_B_stage1": sb,
        "aviso": "Las escalas de recompensa no son comparables. Un retorno mayor NO es una ventaja.",
    }
    Path(a.informe).parent.mkdir(parents=True, exist_ok=True)
    Path(a.informe).write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== Comparacion ==")
    print(f"  {'metrica':<32}{'DefaultReward':>16}{'stage_1_basics':>18}")
    for k in sa:
        va, vb = sa[k], sb[k]
        fa = f"{va:.5g}" if isinstance(va, float) else str(va)
        fb = f"{vb:.5g}" if isinstance(vb, float) else str(vb)
        print(f"  {k:<32}{fa:>16}{fb:>18}")
    print(f"\n  informe -> {a.informe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
