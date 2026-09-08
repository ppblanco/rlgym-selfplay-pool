"""Entorno 1v1 con UN aprendiz y UN rival congelado.

APORTACION NUEVA de rlgym-selfplay-pool. No forma parte de moanv2/rlgym.
Base: https://github.com/moanv2/rlgym (MIT, (c) 2026 Diego Alfaro Gomez).

QUE ES Y QUE NO ES
------------------
Es la version MINIMA del entorno que necesitara el experimento: el coche azul
aprende, el naranja lo controla una politica CONGELADA cargada de un
checkpoint. Nada mas.

NO tiene, a proposito y todavia:
  - historial de instantaneas (el "pool"),
  - seleccion o muestreo de rivales,
  - refresco periodico del rival.

Eso llega en el bloque siguiente. Aqui solo se demuestra que el circuito
aprendiz/rival funciona y que la contabilidad de muestras es la correcta.

POR QUE UN SOLO AGENTE HACIA rlgym-ppo
--------------------------------------
El trabajador de rlgym-ppo deduce el numero de agentes de la FORMA de lo que
devuelve reset() (batched_agent.py, lineas 78-80): si es un vector 1-D, asume
un agente, y ademas acepta la recompensa como escalar (linea 127). Asi que este
adaptador presenta un entorno de UN agente: el aprendiz. La experiencia del
rival nunca llega al buffer de PPO, que es exactamente lo que queremos.

Consecuencia para la contabilidad, ya anotada en el plan: en autojuego normal
un paso de entorno produce 2 muestras de aprendizaje; aqui produce 1. A
igualdad de muestras hace falta el doble de simulacion.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from rlbot.env.rocketsim_init import asegurar_init

AZUL, NARANJA = 0, 1


def construir_recompensa(spec: str | None):
    """Devuelve la funcion de recompensa a partir de una especificacion.

    spec = None o "default"  -> DefaultReward de rlgym_sim. OJO: NO son "solo
                                 goles". Es -vecmag(angular_velocity)/100, es
                                 decir penaliza girar y no codifica la tarea.
                                 Ver ESTADO_PROYECTO.md §13.1.
    spec = ruta a un YAML     -> se pasa por build_reward() HEREDADO, que ya
                                 sabe montar el CombinedReward y envolverlo en
                                 ZeroSumReward. No se inventan pesos nuevos.
    """
    if not spec or spec == "default":
        from rlgym_sim.utils.reward_functions import DefaultReward

        return DefaultReward()

    import yaml

    from rlbot.rewards import build_reward

    cfg = yaml.safe_load(Path(spec).read_text(encoding="utf-8"))
    return build_reward(cfg)


def cargar_politica_congelada(ckpt_dir: Path, obs_dim: int, device: str = "cpu"):
    """Carga una politica y la deja en modo evaluacion, sin gradientes.

    Carga restringida (weights_only=True): nunca deserializacion arbitraria.
    Se reutiliza el criterio del proyecto base (policy_io.py): la arquitectura
    se deduce de los pesos, no de una configuracion aparte.
    """
    import torch
    from rlgym_ppo.ppo import DiscreteFF

    sd = torch.load(Path(ckpt_dir) / "PPO_POLICY.pt", map_location=device, weights_only=True)
    wk = [k for k in sd if k.endswith("weight")]
    entrada = int(sd[wk[0]].shape[1])
    if entrada != obs_dim:
        raise ValueError(
            f"El rival espera obs de {entrada} y el entorno le da {obs_dim}. "
            "No se ajustan las observaciones para forzar que encaje."
        )
    pol = DiscreteFF(entrada, int(sd[wk[-1]].shape[0]), tuple(int(sd[k].shape[0]) for k in wk[:-1]), device)
    pol.load_state_dict(sd)
    pol.eval()
    for p in pol.parameters():
        p.requires_grad_(False)  # congelado de verdad, no solo por convenio
    return pol


class EntornoRivalCongelado:
    """Envuelve un env 1v1 de rlgym_sim y expone SOLO al aprendiz."""

    def __init__(self, env, rival=None, equipo_aprendiz: int = AZUL) -> None:
        self._env = env
        self._rival = rival
        self._i_aprendiz = equipo_aprendiz
        self._i_rival = NARANJA if equipo_aprendiz == AZUL else AZUL
        self._obs_rival: np.ndarray | None = None
        # Contadores propios: sirven para comprobar la contabilidad de muestras.
        self.pasos_entorno = 0
        self.episodios = 0

    # -- interfaz que consume el trabajador de rlgym-ppo -------------------
    # El trabajador siembra el espacio de acciones (batched_agent.py, linea 70),
    # asi que hay que exponerlo. Se delega en el entorno envuelto en vez de
    # inventar uno: el espacio real es el del LookupAction heredado.
    @property
    def action_space(self):
        return self._env.action_space

    @property
    def observation_space(self):
        return self._env.observation_space

    def __getattr__(self, nombre: str):
        # Cualquier otro atributo que rlgym-ppo espere del entorno se delega,
        # en vez de fallar con AttributeError a mitad de un entrenamiento.
        return getattr(self.__dict__["_env"], nombre)

    def reset(self) -> np.ndarray:
        obs = self._env.reset()
        self._obs_rival = np.asarray(obs[self._i_rival], dtype=np.float32)
        self.episodios += 1
        return np.asarray(obs[self._i_aprendiz], dtype=np.float32)

    def step(self, acciones) -> tuple[np.ndarray, float, bool, dict[str, Any]]:
        import torch

        a = np.asarray(acciones).reshape(-1)  # el aprendiz manda 1 indice
        with torch.no_grad():
            a_rival, _ = self._rival.get_action(self._obs_rival, deterministic=False)
        a_rival = int(np.asarray(a_rival).flat[0])

        ambas = np.empty((2, a.shape[0]), dtype=np.float32)
        ambas[self._i_aprendiz] = a
        ambas[self._i_rival] = a_rival

        obs, rew, done, info = self._env.step(ambas)
        self._obs_rival = np.asarray(obs[self._i_rival], dtype=np.float32)
        self.pasos_entorno += 1

        # Se devuelve SOLO lo del aprendiz. done y truncamiento se transmiten
        # tal cual los da el entorno: no se reinterpretan aqui.
        return (
            np.asarray(obs[self._i_aprendiz], dtype=np.float32),
            float(np.asarray(rew).reshape(-1)[self._i_aprendiz]),
            bool(done),
            info if isinstance(info, dict) else {},
        )

    def close(self) -> None:
        cerrar = getattr(self._env, "close", None)
        if callable(cerrar):
            cerrar()


class ConstructorRivalCongelado:
    """Fabrica picklable de entornos, una por proceso trabajador.

    Guarda solo datos planos (rutas y escalares) para poder viajar por pickle a
    los trabajadores que lanza rlgym-ppo. El entorno y la politica se construyen
    DENTRO de __call__, que ya se ejecuta en el proceso hijo: ahi es donde hay
    que inicializar RocketSim.
    """

    def __init__(
        self,
        mallas: str,
        ckpt_rival: str,
        tick_skip: int = 8,
        timeout_pasos: int = 300,
        equipo_aprendiz: int = AZUL,
        hilos_torch: int = 1,
        recompensa: str | None = None,
    ) -> None:
        self.mallas = str(mallas)
        self.ckpt_rival = str(ckpt_rival)
        self.recompensa = recompensa
        self.tick_skip = int(tick_skip)
        self.timeout_pasos = int(timeout_pasos)
        self.equipo_aprendiz = int(equipo_aprendiz)
        self.hilos_torch = int(hilos_torch)

    def __call__(self):
        import torch

        # Cada trabajador con 1 hilo: si cada uno intenta ocupar toda la CPU,
        # N trabajadores se pelean entre si y el rendimiento cae.
        torch.set_num_threads(self.hilos_torch)

        # AQUI, dentro del proceso hijo. Sin esto RocketSim aborta con spawn.
        asegurar_init(self.mallas)

        import rlgym_sim
        from rlgym_sim.utils.obs_builders import DefaultObs
        from rlgym_sim.utils.state_setters import DefaultState
        from rlgym_sim.utils.terminal_conditions.common_conditions import (
            GoalScoredCondition,
            TimeoutCondition,
        )

        from rlbot.actions.lookup_action import LookupAction

        env = rlgym_sim.make(
            tick_skip=self.tick_skip,
            team_size=1,
            spawn_opponents=True,
            obs_builder=DefaultObs(),
            action_parser=LookupAction(),
            reward_fn=construir_recompensa(self.recompensa),
            state_setter=DefaultState(),
            terminal_conditions=[GoalScoredCondition(), TimeoutCondition(self.timeout_pasos)],
        )
        rival = cargar_politica_congelada(Path(self.ckpt_rival), obs_dim=89)
        return EntornoRivalCongelado(env, rival, self.equipo_aprendiz)


# ---------------------------------------------------------------------------
# Version con POOL: la misma clase sirve para el brazo A y para el brazo B.
# ---------------------------------------------------------------------------


class EntornoPool(EntornoRivalCongelado):
    """Como EntornoRivalCongelado, pero el rival sale de un pool.

    En cada reset se consulta el pool y se elige rival. Si es el mismo que ya
    esta cargado no se recarga nada; si cambia, se carga (y se cachea, para que
    volver a el mas adelante no cueste otra lectura de disco).

    A y B usan ESTA clase. Lo unico que difiere es cuantas instantaneas tiene
    el pool, que lo decide su politica de retencion.
    """

    def __init__(self, env, pool, semilla: int, obs_dim: int = 89,
                 equipo_aprendiz: int = AZUL) -> None:
        super().__init__(env, rival=None, equipo_aprendiz=equipo_aprendiz)
        self._pool = pool
        self._semilla = int(semilla)
        self._obs_dim = int(obs_dim)
        self._cache: dict[str, Any] = {}
        self._id_actual: str | None = None
        # Contadores para medir el coste real que anade el pool.
        self.cargas_de_rival = 0
        self.aciertos_cache = 0
        self.segundos_cargando = 0.0

    def _asegurar_rival(self) -> None:
        import time as _t

        elegida = self._pool.elegir(self._semilla, self.episodios)
        if elegida is None:
            raise RuntimeError(
                "El pool esta vacio: no hay instantanea con la que jugar. "
                "El entrenamiento debe guardar la primera antes del primer reset."
            )
        if elegida["id"] == self._id_actual:
            return
        if elegida["id"] in self._cache:
            self._rival = self._cache[elegida["id"]]
            self._id_actual = elegida["id"]
            self.aciertos_cache += 1
            return
        t0 = _t.perf_counter()
        pol = cargar_politica_congelada(self._pool.ruta_de(elegida), self._obs_dim)
        self.segundos_cargando += _t.perf_counter() - t0
        self._cache[elegida["id"]] = pol
        self._rival = pol
        self._id_actual = elegida["id"]
        self.cargas_de_rival += 1

    def reset(self):
        self._asegurar_rival()
        return super().reset()

    def estadisticas_pool(self) -> dict:
        return {
            "cargas_de_rival": self.cargas_de_rival,
            "aciertos_cache": self.aciertos_cache,
            "segundos_cargando": round(self.segundos_cargando, 4),
            "instantaneas_vistas": len(self._cache),
            "rival_actual": self._id_actual,
        }


class ConstructorPool:
    """Fabrica picklable de entornos con pool. Identica para A y para B."""

    def __init__(self, mallas: str, carpeta_pool: str, retencion: int, semilla: int,
                 tick_skip: int = 8, timeout_pasos: int = 300,
                 equipo_aprendiz: int = AZUL, hilos_torch: int = 1,
                 recompensa: str | None = None) -> None:
        self.mallas = str(mallas)
        self.carpeta_pool = str(carpeta_pool)
        self.recompensa = recompensa
        self.retencion = int(retencion)
        self.semilla = int(semilla)
        self.tick_skip = int(tick_skip)
        self.timeout_pasos = int(timeout_pasos)
        self.equipo_aprendiz = int(equipo_aprendiz)
        self.hilos_torch = int(hilos_torch)

    def __call__(self):
        import torch

        torch.set_num_threads(self.hilos_torch)
        asegurar_init(self.mallas)

        import rlgym_sim
        from rlgym_sim.utils.obs_builders import DefaultObs
        from rlgym_sim.utils.state_setters import DefaultState
        from rlgym_sim.utils.terminal_conditions.common_conditions import (
            GoalScoredCondition,
            TimeoutCondition,
        )

        from rlbot.actions.lookup_action import LookupAction
        from rlbot.env.opponent_pool import PoolRivales

        env = rlgym_sim.make(
            tick_skip=self.tick_skip,
            team_size=1,
            spawn_opponents=True,
            obs_builder=DefaultObs(),
            action_parser=LookupAction(),
            reward_fn=construir_recompensa(self.recompensa),
            state_setter=DefaultState(),
            terminal_conditions=[GoalScoredCondition(), TimeoutCondition(self.timeout_pasos)],
        )
        pool = PoolRivales(self.carpeta_pool, self.retencion)
        return EntornoPool(env, pool, self.semilla, obs_dim=89,
                           equipo_aprendiz=self.equipo_aprendiz)
