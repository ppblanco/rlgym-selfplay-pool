"""Congela el protocolo del experimento y calcula su SHA256.

APORTACION NUEVA de rlgym-selfplay-pool.

Desde que este archivo existe, cualquier cambio metodologico es una DESVIACION
y debe registrarse como tal, no hacerse en silencio.

Uso:
    python scripts/freeze_protocol.py --salida configs/experimento/protocolo.json
"""
from __future__ import annotations

import argparse
import os
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

FUENTES_NUESTRAS = [
    "src/rlbot/env/rocketsim_init.py",
    "src/rlbot/env/frozen_opponent.py",
    "src/rlbot/env/opponent_pool.py",
    "scripts/preflight.py",
    "scripts/checks_sim.py",
    "scripts/check_adapter.py",
    "scripts/train_smoke.py",
    "scripts/eval_dev.py",
    "scripts/warmup_critic.py",
    "scripts/test_pool.py",
    "scripts/train_ab_smoke.py",
    "scripts/compare_rewards.py",
    "scripts/freeze_protocol.py",
]


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="configs/experimento/protocolo.json")
    ap.add_argument(
        "--c0",
        default=os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "rlgym-selfplay-pool", "runs", "C0_v2_stage1"
        ),
    )
    a = ap.parse_args()

    c0 = Path(a.c0)
    hashes_c0 = {f.name: sha256_archivo(f) for f in sorted(c0.iterdir()) if f.is_file()}
    bk = json.loads((c0 / "BOOK_KEEPING_VARS.json").read_text(encoding="utf-8"))

    codigo = {}
    for f in FUENTES_NUESTRAS:
        p = RAIZ / f
        codigo[f] = sha256_archivo(p) if p.exists() else "FALTA"

    try:
        upstream = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True
        ).strip()
    except Exception:  # noqa: BLE001
        upstream = "desconocido"

    protocolo = {
        "version": "1.0",
        "congelado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "H1 - un rival muestreado de instantaneas pasadas produce mayor "
                     "tasa de victorias frente a rivales reservados que un rival que es "
                     "siempre la version actual congelada, a igualdad de muestras.",

        "recompensa": {
            "archivo": "configs/reward_weights/stage_1_basics.yaml",
            "sha256": sha256_archivo(RAIZ / "configs/reward_weights/stage_1_basics.yaml"),
            "heredada": True,
            "componentes": ["velocity_player_to_ball 0.10", "face_ball 0.05",
                            "velocity_ball_to_goal 0.30",
                            "event 8.0 (goal 1, concede -1, shot 0.1, demo 0.1)"],
            "envoltura": "ZeroSumReward(team_spirit=0.0, opp_scale=1.0)",
        },

        "c0": {
            "ruta": str(c0),
            "recompensa_con_la_que_se_entreno": "stage_1_basics",
            "cumulative_timesteps": bk.get("cumulative_timesteps"),
            "cumulative_model_updates": bk.get("cumulative_model_updates"),
            "completo": True,
            "hashes": hashes_c0,
        },

        "modelo": {
            "arquitectura_politica": [512, 512, 512],
            "arquitectura_critico": [512, 512, 512],
            "obs": "DefaultObs (89)",
            "acciones": "LookupAction (90 discretas)",
        },

        "pool": {
            "K_muestras_por_instantanea": 40000,
            "muestreo": "uniforme entre elegibles, reproducible por (semilla, episodio)",
            "brazo_A": {"retencion": 1, "protegidas": [],
                        "descripcion": "una sola instantanea, refrescada cada K"},
            "brazo_B": {"retencion": 16, "protegidas": ["C0"],
                        "descripcion": "historicas hasta el maximo; C0 nunca se expulsa"},
            "regla_de_expulsion": "si se supera la retencion, se expulsa la mas antigua "
                                  "NO protegida; determinista, fijada antes del experimento",
        },

        "presupuesto": {
            "muestras_por_ejecucion": 500000,
            "lote_ppo": 8000,
            "actualizaciones_esperadas": 62,
            "instantaneas_esperadas": 12,
            "ejecuciones": 6,
            "nota": "500k por ejecucion = 6 ejecuciones (3 semillas x 2 brazos)",
        },

        "semillas": {
            "entrenamiento": [20260907, 20260908, 20260909],
            "emparejadas": "A_i y B_i comparten semilla",
            "no_determinismo_restante": [
                "orden de llegada de la experiencia de los trabajadores (asincrono)",
                "reducciones en coma flotante de torch en CPU",
                "planificacion del sistema operativo entre procesos",
            ],
        },

        "ejecucion": {"n_proc": 2, "hilos_torch_por_trabajador": 1,
                      "dispositivo": "cpu", "wandb": "desactivado"},

        "ppo": {"epochs": 1, "ent_coef": 0.01, "clip_range": 0.2,
                "gae_gamma": 0.99, "gae_lambda": 0.95,
                "standardize_returns": True, "standardize_obs": False,
                "minibatch": 8000},

        "entorno": {"tick_skip": 8, "team_size": 1, "spawn_opponents": True,
                    "state_setter": "DefaultState",
                    "terminales": ["GoalScoredCondition", "TimeoutCondition(300 pasos)"]},

        "evaluacion_desarrollo": {
            "para": "decisiones durante el desarrollo",
            "rivales": ["diego_1.18B_512 (artefacto de partida)",
                        "instantaneas propias"],
            "prohibido": "no se usan los rivales finales para ninguna decision",
        },

        "evaluacion_final": {
            "cuando": "una sola vez, con el protocolo ya congelado",
            "checkpoint_evaluado": "el checkpoint FINAL de cada ejecucion",
            "regla_de_seleccion": "ninguna: se evalua el final. No se elige el mejor "
                                  "checkpoint mirando ningun conjunto.",
            "rivales": [
                {"nombre": "martin_2.1B_1024", "obs": 107,
                 "sha256_politica": "e959aca4cb171adac7922d00356112518221f94174465a4ac461aebaa484a2e8"},
                {"nombre": "nachi_2.9B", "obs": 107,
                 "sha256_politica": "94be42a4f24bf222bb2d400ebe473d4892e3b2a8733f4e2270eada1e8d0558a8"},
                {"nombre": "marco_2.0B_1024", "obs": 89,
                 "sha256_politica": "74f169281224b444de5d4a7be76be73b74c6aabd20710ef6a8b8819f7b66cb76"},
            ],
            "partidas_por_rival_y_ejecucion": 40,
            "partidas_totales": 6 * 3 * 40,
            "semillas_de_partida": "5000..5039 por rival, lista fija",
            "alternancia_de_lados": "indice par -> nuestro bot de azul; impar -> de naranja",
            "modo_accion": "estocastico (unico modo primario; el determinista, si se "
                           "ejecuta, se reporta por separado y nunca mezclado)",
            "reglas": {
                "victoria_derrota": "gol marcado o encajado",
                "empate": "se agota TimeoutCondition del entorno de evaluacion",
                "incompleta": "cualquier otra terminacion o corte; se excluye de las "
                              "tasas y se reporta aparte. Una partida incompleta NO es empate.",
                "sin_desempate_administrativo": "no se resuelven empates por timesteps, "
                                                "siembra ni clasificacion",
            },
            "metricas": ["tasa de victoria sobre completas",
                         "tasa de victoria sobre decisivas",
                         "desglose por rival"],
            "incertidumbre": {
                "intervalo": "bootstrap 95% sobre las partidas, 10000 remuestreos",
                "entre_semillas": "media y rango de las 3 semillas por brazo",
            },
        },

        "criterio_H1": {
            "evidencia_a_favor": [
                "la diferencia B-A en tasa de victoria tiene IC bootstrap 95% que EXCLUYE el 0",
                "la magnitud de la diferencia supera el rango entre semillas de ambos brazos",
                "el signo es consistente en al menos 2 de 3 semillas",
                "el signo es consistente en al menos 2 de 3 rivales",
            ],
            "evidencia_en_contra": "los mismos cuatro criterios con el signo invertido",
            "inconcluyente": [
                "el IC incluye el 0, o",
                "la diferencia es menor que el rango entre semillas, o",
                "el signo no es consistente entre semillas o entre rivales",
            ],
            "prohibido": [
                "usar la recompensa de entrenamiento como prueba de calidad de juego",
                "reducir H1 a 'B tiene un porcentaje mayor que A'",
                "presentar como mejora robusta una diferencia menor que la variabilidad "
                "entre semillas",
            ],
        },

        "codigo": {
            "upstream_commit": upstream,
            "nota": "el SHA de upstream identifica la BASE; los hashes de abajo "
                    "identifican nuestras aportaciones",
            "hashes_fuentes_nuestras": codigo,
        },

        "dependencias": {
            "python": "3.11.16",
            "torch": "2.13.0+cpu",
            "numpy": "1.26.4",
            "rocketsim": "2.2.1",
            "rlgym-sim": "a1240530239d6b7671147b4f97e9b5e130d0acce",
            "rlgym-ppo": "4ffd2e924198bf4b2d59f4bf280b29919d7c07ea",
            "rlgym-tools": "NO instalado (su main es API v2, incompatible)",
            "mallas": "rlgym-rocket-league 2.0.1, sdist sha256 "
                      "3be8e9d2f1cfb6514e0e3d455fb33ff95e26eb7c399f819fff0258025cf4d501",
            "lockfile": "requirements/lock-2026-09-07.txt",
        },

        "deuda_tecnica": {
            "torch_load_sin_weights_only": {
                "donde": "rlgym_ppo/ppo/ppo_learner.py::load_from",
                "riesgo": "bajo en este experimento: solo se le pasan checkpoints "
                          "generados localmente por nosotros",
                "reglas": [
                    "no usar esa ruta con checkpoints externos",
                    "no relajar la carga de artefactos ajenos (siempre weights_only=True)",
                    "no modificar rlgym-ppo en esta fase solo por esto",
                ],
            },
        },
    }

    destino = RAIZ / a.salida
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(protocolo, indent=2, ensure_ascii=False, sort_keys=True)
    destino.write_text(texto + "\n", encoding="utf-8")

    sha = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    (destino.parent / "protocolo.sha256").write_text(
        f"{sha}  {destino.name}\n", encoding="utf-8"
    )

    print(f"Protocolo congelado -> {destino}")
    print(f"SHA256 del protocolo: {sha}")
    print(f"  recompensa   : stage_1_basics")
    print(f"  C0           : {protocolo['c0']['cumulative_timesteps']:,} muestras")
    print(f"  K            : {protocolo['pool']['K_muestras_por_instantanea']:,}")
    print(f"  retencion B  : {protocolo['pool']['brazo_B']['retencion']} (C0 protegido)")
    print(f"  presupuesto  : {protocolo['presupuesto']['muestras_por_ejecucion']:,} x 6")
    print(f"  semillas     : {protocolo['semillas']['entrenamiento']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
