"""Comprobaciones de simulacion, inferencia integrada y actualizacion PPO.

APORTACION NUEVA de rlgym-selfplay-pool. No forma parte de moanv2/rlgym.
Base: https://github.com/moanv2/rlgym (MIT, (c) 2026 Diego Alfaro Gomez).

Se separa de preflight.py porque estas comprobaciones necesitan la pila de
simulacion instalada, mientras que el diagnostico basico no.

TRES MEDICIONES DISTINTAS, y no se mezclan:
  1. Simulacion sola (acciones aleatorias) -> valida integracion, NO juego.
  2. Simulacion + inferencia de la politica -> coste real de decidir.
  3. Una actualizacion PPO minima -> coste de aprender.

Ninguna de las tres es, por si sola, la velocidad de entrenamiento sostenida.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

# El LookupAction del proyecto base vive en src/. Se anade al path para poder
# usarlo: es el parser con el que se entrenaron TODOS los checkpoints (90
# acciones discretas -> 8 controles), y sin el la politica no encaja con el env.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

OK, FALLO, NO_EJEC = "OK", "FALLO", "NO_EJEC"


_INICIADO = False


def init_rocketsim(meshes: Path) -> None:
    """Inicializa RocketSim con una ruta explicita de mallas.

    IMPORTANTE (Windows): el metodo de arranque de multiprocessing es 'spawn',
    asi que un proceso hijo NO hereda esta inicializacion. Comprobado: sin
    llamar a init() en el hijo, RocketSim aborta con
    'No arena meshes found for gamemode soccar'. Cada proceso trabajador tiene
    que llamar a esta funcion por su cuenta.
    """
    global _INICIADO
    if _INICIADO:
        return
    import RocketSim as rsim

    rsim.init(str(meshes))
    _INICIADO = True


def comprobar_arena(inf, meshes: Path) -> bool:
    print("\n== Arena de RocketSim ==")
    if not (meshes / "soccar").is_dir():
        inf.add("arena_init", FALLO, f"no hay mallas de soccar en {meshes}")
        return False
    try:
        import RocketSim as rsim

        init_rocketsim(meshes)
        arena = rsim.Arena(rsim.GameMode.SOCCAR)
        arena.add_car(rsim.Team.BLUE, rsim.CarConfig(rsim.CarConfig.OCTANE))
        arena.add_car(rsim.Team.ORANGE, rsim.CarConfig(rsim.CarConfig.OCTANE))
        arena.step(120)
        z = arena.ball.get_state().pos.z
        # El radio de la pelota es ~92.75: si reposa sobre el suelo, z ~ 93.
        # Si la colision no cargara, atravesaria el suelo (z <= 0).
        plausible = 80.0 < z < 110.0
        inf.add(
            "arena_init",
            OK if plausible else FALLO,
            f"arena creada, 120 ticks, pelota en z={z:.2f} "
            f"({'colision correcta' if plausible else 'FISICA SOSPECHOSA'})",
            ball_z=round(z, 2),
            n_coches=len(arena.get_cars()),
        )
        return plausible
    except Exception as e:
        inf.add("arena_init", FALLO, f"{type(e).__name__}: {e}")
        return False


def comprobar_entorno_1v1(inf, meshes: Path) -> Any:
    """Reset y avance de un entorno 1v1 del proyecto, con validacion numerica."""
    print("\n== Entorno 1v1 (rlgym_sim) ==")
    try:
        import numpy as np
        import rlgym_sim
        from rlgym_sim.utils.obs_builders import DefaultObs
        from rlgym_sim.utils.reward_functions import DefaultReward
        from rlgym_sim.utils.state_setters import DefaultState
        from rlgym_sim.utils.terminal_conditions.common_conditions import (
            GoalScoredCondition,
            TimeoutCondition,
        )

        from rlbot.actions.lookup_action import LookupAction

        init_rocketsim(meshes)
        env = rlgym_sim.make(
            tick_skip=8,
            team_size=1,
            spawn_opponents=True,
            obs_builder=DefaultObs(),
            action_parser=LookupAction(),  # heredado del proyecto base
            reward_fn=DefaultReward(),
            state_setter=DefaultState(),
            terminal_conditions=[GoalScoredCondition(), TimeoutCondition(200)],
        )
        obs = env.reset()
        n_agentes = len(obs)
        dims = [len(np.asarray(o).ravel()) for o in obs]
        inf.add(
            "env_reset",
            OK if n_agentes == 2 else FALLO,
            f"{n_agentes} agentes, dims={dims}",
            n_agentes=n_agentes,
            obs_dims=dims,
        )

        # LookupAction espera un indice por coche, con forma (n_agentes, 1)
        acciones = np.asarray([[np.random.randint(0, 90)] for _ in range(n_agentes)])
        obs2, rew, done, info = env.step(acciones)
        arr = np.asarray(obs2, dtype=np.float64)
        finito = bool(np.all(np.isfinite(arr)))
        rew_fin = bool(np.all(np.isfinite(np.asarray(rew, dtype=np.float64))))
        inf.add(
            "env_step",
            OK if (finito and rew_fin) else FALLO,
            f"paso ok | obs finitas={finito} recompensas finitas={rew_fin} "
            f"| rango obs [{arr.min():.2f}, {arr.max():.2f}] | done={done}",
            obs_finitas=finito,
            recompensas_finitas=rew_fin,
        )
        return env
    except Exception as e:
        inf.add("env_1v1", FALLO, f"{type(e).__name__}: {e}")
        return None


def bench_simulacion(inf, env, segundos: float) -> float | None:
    """Solo simulacion, acciones aleatorias. Valida integracion, NO juego."""
    print(f"\n== Benchmark: simulacion sola (tope {segundos:.0f}s) ==")
    if env is None:
        inf.add("bench_simulacion", NO_EJEC, "sin entorno")
        return None
    import numpy as np

    env.reset()
    pasos = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < segundos:
        acciones = np.asarray([[np.random.randint(0, 90)] for _ in range(2)])
        _, _, done, _ = env.step(acciones)
        pasos += 1
        if done:
            env.reset()
    dt = time.perf_counter() - t0
    pps = pasos / dt
    inf.add(
        "bench_simulacion",
        OK,
        f"{pps:,.0f} pasos de entorno/s (1 proceso) = {pps * 2:,.0f} muestras de agente/s "
        f"| acciones ALEATORIAS: valida integracion, no juego",
        pasos_entorno_por_s=round(pps, 1),
        procesos=1,
        pasos=pasos,
        segundos=round(dt, 2),
    )
    return pps


def bench_inferencia_integrada(inf, env, ckpt: Path, segundos: float) -> float | None:
    """Simulacion + politica real decidiendo. Modelo de DESARROLLO, no reservado."""
    print(f"\n== Benchmark: simulacion + inferencia (tope {segundos:.0f}s) ==")
    if env is None:
        inf.add("bench_sim_inferencia", NO_EJEC, "sin entorno")
        return None
    try:
        import numpy as np
        import torch
        from rlgym_ppo.ppo import DiscreteFF

        sd = torch.load(ckpt / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
        wk = [k for k in sd if k.endswith("weight")]
        obs_dim = int(sd[wk[0]].shape[1])
        n_act = int(sd[wk[-1]].shape[0])
        capas = tuple(int(sd[k].shape[0]) for k in wk[:-1])

        obs = env.reset()
        if len(np.asarray(obs[0]).ravel()) != obs_dim:
            inf.add(
                "bench_sim_inferencia",
                NO_EJEC,
                f"el entorno da obs de {len(np.asarray(obs[0]).ravel())} y el modelo espera {obs_dim}",
            )
            return None

        pol = DiscreteFF(obs_dim, n_act, capas, "cpu")
        pol.load_state_dict(sd)
        pol.eval()

        pasos = 0
        t0 = time.perf_counter()
        with torch.no_grad():
            while time.perf_counter() - t0 < segundos:
                acts = []
                for o in obs:
                    a, _ = pol.get_action(np.asarray(o, dtype=np.float32), deterministic=False)
                    acts.append(int(a) if np.isscalar(a) or getattr(a, "ndim", 0) == 0 else int(np.asarray(a).flat[0]))
                obs, _, done, _ = env.step(np.asarray(acts).reshape(2, 1))
                pasos += 1
                if done:
                    obs = env.reset()
        dt = time.perf_counter() - t0
        pps = pasos / dt
        inf.add(
            "bench_sim_inferencia",
            OK,
            f"{pps:,.0f} pasos de entorno/s con los DOS coches decidiendo con la politica "
            f"(arq {list(capas)}, obs {obs_dim})",
            pasos_entorno_por_s=round(pps, 1),
            arquitectura=list(capas),
            obs_dim=obs_dim,
            checkpoint=str(ckpt),
            segundos=round(dt, 2),
        )
        return pps
    except Exception as e:
        inf.add("bench_sim_inferencia", FALLO, f"{type(e).__name__}: {e}")
        return None


def bench_ppo(inf, obs_dim: int, n_act: int, capas: tuple, muestras: int, segundos: float) -> None:
    """Coste de UNA actualizacion PPO sobre un lote sintetico.

    Mide el paso de aprendizaje aislado del simulador. No entrena nada util:
    los datos son sinteticos y el resultado se descarta.
    """
    print(f"\n== Benchmark: una actualizacion PPO (tope {segundos:.0f}s) ==")
    try:
        import numpy as np
        import torch
        from rlgym_ppo.ppo import DiscreteFF, ValueEstimator

        dev = "cpu"
        pol = DiscreteFF(obs_dim, n_act, capas, dev)
        val = ValueEstimator(obs_dim, capas, dev)
        opt_p = torch.optim.Adam(pol.parameters(), lr=3e-4)
        opt_v = torch.optim.Adam(val.parameters(), lr=3e-4)

        rng = np.random.default_rng(0)
        obs = torch.from_numpy(rng.standard_normal((muestras, obs_dim), dtype=np.float32))
        acts = torch.from_numpy(rng.integers(0, n_act, size=(muestras, 1)).astype(np.int64))
        # (N,) a secas: mas abajo se aplana el ratio para que NO haya broadcasting
        # a (N,N), que es lo que reventaba la memoria.
        ventajas = torch.from_numpy(rng.standard_normal(muestras).astype(np.float32))
        retornos = torch.from_numpy(rng.standard_normal(muestras).astype(np.float32))
        with torch.no_grad():
            logp_old, _ = pol.get_backprop_data(obs, acts)

        t0 = time.perf_counter()
        logp, entropia = pol.get_backprop_data(obs, acts)
        ratio = torch.exp(logp - logp_old).ravel()   # (N,), no (N,1)
        p1 = ratio * ventajas
        p2 = torch.clamp(ratio, 0.8, 1.2) * ventajas
        perdida_pol = -torch.min(p1, p2).mean() - 0.01 * entropia.mean()
        opt_p.zero_grad(); perdida_pol.backward(); opt_p.step()

        perdida_val = torch.nn.functional.mse_loss(val(obs).ravel(), retornos)
        opt_v.zero_grad(); perdida_val.backward(); opt_v.step()
        dt = time.perf_counter() - t0

        inf.add(
            "bench_ppo_update",
            OK,
            f"1 actualizacion sobre {muestras:,} muestras sinteticas en {dt * 1000:,.0f} ms "
            f"= {muestras / dt:,.0f} muestras/s (solo el paso de aprendizaje)",
            muestras=muestras,
            segundos=round(dt, 4),
            muestras_por_s=round(muestras / dt, 1),
            arquitectura=list(capas),
        )
    except Exception as e:
        inf.add("bench_ppo_update", FALLO, f"{type(e).__name__}: {e}")
