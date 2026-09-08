# Autoría: qué es heredado y qué es nuestro

Base: [moanv2/rlgym](https://github.com/moanv2/rlgym), commit
`0c6965acf3d0405227282a80b1881dbfde3ef56b`, licencia MIT.

**Ningún archivo heredado fue modificado.** Verificado con `git status`: 0
archivos modificados, 27 entradas nuevas sin seguimiento. Los hashes de nuestras
aportaciones están en `MANIFIESTO_HASHES.txt`.

---

## 1. HEREDADO SIN MODIFICAR

Todo esto es trabajo de upstream. Se usa tal cual.

| Archivo / módulo | Función | Cómo lo usamos |
|---|---|---|
| `src/rlbot/rewards/` (`builder.py`, `builtin.py`, `registry.py`, `zero_sum.py`) | registro de recompensas, `CombinedReward`, `ZeroSumReward` | base de las cinco configuraciones probadas; `build_reward()` ya soportaba `zero_sum: false`, no hizo falta tocarlo |
| `src/rlbot/actions/lookup_action.py` | 90 acciones discretas → 8 controles | parser de acciones en todo el proyecto |
| `src/rlbot/tournament/` (`obs.py`, `policy_io.py`) | construcción de entornos de duelo, carga de políticas | arnés de toda la evaluación |
| `configs/reward_weights/stage_1_basics.yaml` | recompensa de etapa 1 | recompensa de H1 y referencia D_A |
| `configs/reward_weights/stage_2_offense.yaml` | recompensa de etapa 2 | configuración D_B |
| `scripts/{train,evaluate,export_model,train_stages,visualize}.py` | flujo original de entrenamiento | no se usaron en los experimentos |
| `docs/{architecture,setup,training_guide,roadmap_45_days}.md` | documentación original | conservada |
| `tests/` | pruebas de upstream | conservadas, sin modificar |
| `.gitignore` | exclusiones | ya cubría `*.pt`, `runs/`, `collision_meshes/`, `*.log` |

---

## 2. MODIFICADO POR NOSOTROS

**Ninguno.**

Fue una decisión deliberada: toda la funcionalidad nueva se añadió en archivos
nuevos que envuelven o componen lo heredado, nunca alterándolo. Así la
atribución queda limpia y `git status` lo demuestra de un vistazo.

---

## 3. CREADO POR NOSOTROS

### 3.1 Arranque y entorno

| Archivo | Función | Motivo | Evidencia |
|---|---|---|---|
| `scripts/preflight.py` (441 l.) | verifica intérprete, dependencias, mallas, importabilidad | la pila es frágil en Windows y falla tarde y mal | detectó el falso negativo `rocketsim`/`RocketSim` |
| `src/rlbot/env/rocketsim_init.py` (102 l.) | `asegurar_init()`: inicializa RocketSim una vez por proceso, con ruta absoluta | con `spawn`, los hijos **no** heredan `rsim.init()` y abortan | sin esto los trabajadores morían al arrancar |
| `scripts/checks_sim.py` (287 l.) | comprobaciones del simulador | validar el entorno antes de gastar cómputo | — |

### 3.2 Entrenamiento contra rival congelado y pool

| Archivo | Función | Motivo | Evidencia |
|---|---|---|---|
| `src/rlbot/env/frozen_opponent.py` (335 l.) | `EntornoRivalCongelado` expone **un solo agente** a rlgym-ppo; el rival actúa dentro de `step()`. `ConstructorRivalCongelado` y `ConstructorPool` son fábricas picklable | si el rival fuese un segundo agente, su experiencia entraría en PPO y contaminaría las actualizaciones | `check_adapter.py`; se detectó y corrigió que faltaba `action_space` al delegar |
| `src/rlbot/env/opponent_pool.py` (171 l.) | `PoolRivales`: instantáneas, manifiesto atómico (`os.replace`), retención con protección de C0, muestreo reproducible por semilla | el pool es el tratamiento del experimento; debía ser auditable y determinista | `test_pool.py`; en el linaje neutral se crearon 41 instantáneas, se conservaron 16 y se expulsaron 25 |
| `scripts/test_pool.py` (145 l.) | prueba de la regla de retención y del muestreo | verificar la expulsión sin depender de un experimento | — |
| `scripts/check_adapter.py` (144 l.) | comprueba que solo la experiencia del aprendiz llega a PPO | es la garantía central de validez del diseño | — |

### 3.3 Ejecución reproducible

| Archivo | Función | Motivo | Evidencia |
|---|---|---|---|
| `scripts/run_experiment.py` (317 l.) | ejecuta las 6 corridas de H1, verifica el SHA del protocolo y los hashes de C0, siembra el pool antes de construir el `Learner` | cada corrida debe partir del mismo C0 y nunca sobrescribir otra | se negó a sobrescribir carpetas existentes durante la recuperación del interbloqueo |
| `scripts/h2/train_phase0.py` (316 l.) | entrena **un** linaje por proceso; archivo de instantáneas sin retención; hitos; marcador COMPLETA/INCOMPLETA | el `cleanup()` de rlgym-ppo deja sockets corruptos para la corrida siguiente del mismo proceso | tras aislar por proceso, cero bloqueos |
| `scripts/h2/driver_h2.py` (159 l.) | proceso padre que no importa torch: lanza subprocesos, detecta estancamiento por antigüedad del log, mata el árbol, detecta huérfanos | el interbloqueo de H1 dejó 16 hilos en espera y cero CPU durante 15 minutos | prueba corta: 2 procesos, cero huérfanos, reanudación idempotente |
| `scripts/h2/repair_informe.py` (112 l.) | repara el marcador de una corrida verificando 6 condiciones desde disco, sin reentrenar | un defecto propio marcó INCOMPLETA una corrida terminada | reparación registrada dentro del propio informe |
| `scripts/reward_diagnostic/train_diag.py` (222 l.) | entrena una configuración de recompensa por proceso | comparar recompensas con todo lo demás idéntico | D_A/D_B/D_C y R1/R2 |

### 3.4 Evaluación

| Archivo | Función | Motivo | Evidencia |
|---|---|---|---|
| `scripts/eval_final.py` (224 l.) | evaluación final de H1, una sola vez; JSONL con id único, reanudable sin duplicados | la evaluación final no puede repetirse ni seleccionarse | se interrumpió en la partida 389 y reanudó sin repetir ninguna |
| `scripts/h2/duel.py` (177 l.) | duelo entre dos checkpoints, con IC de Wilson, JSONL y hashes | herramienta de diagnóstico reutilizable | 3.000 partidas de los diagnósticos |
| `scripts/h2/eval_calib.py` (204 l.) | calibración de dificultad; **carga todas las políticas por adelantado** | corrige el artefacto de H1: la carga perezosa hacía que reanudar cambiara el estado aleatorio | — |
| `scripts/eval_dev.py` (230 l.) | evaluación de desarrollo | medir sin tocar los rivales reservados | — |

### 3.5 Integridad y análisis

| Archivo | Función | Motivo | Evidencia |
|---|---|---|---|
| `scripts/integrity_table.py` (213 l.) | tabla **ciega** de integridad; recalcula hashes y recupera cada checkpoint en un **proceso nuevo** | verificar que las corridas son válidas y comparables antes de ver ningún resultado | las 6 corridas de H1 la superaron |
| `scripts/analyze_h1.py` (179 l.) | criterio congelado de H1: bootstrap, cuatro condiciones, veredicto | el criterio debía existir antes de los datos | veredicto INCONCLUYENTE |
| `scripts/h2/gate_check.py` (184 l.) | los cuatro criterios de la puerta de H2 | decidir GO/NO-GO con umbrales previos | veredicto NO-GO |
| `scripts/warmup_critic.py` (262 l.) | calentamiento del crítico | preparar C0 | descartó dos instrumentos inválidos (ver §4) |
| `scripts/compare_rewards.py` (217 l.) | comparación de recompensas como señal | elegir recompensa sin mirar resultados de juego | — |
| `scripts/train_smoke.py`, `scripts/train_ab_smoke.py` (259 + 238 l.) | pruebas cortas de entrenamiento | validar el ciclo antes de gastar cómputo | — |

### 3.6 Protocolos y documentación

| Archivo | Función |
|---|---|
| `scripts/freeze_protocol.py` (263 l.) | congela un protocolo y calcula su SHA256 |
| `configs/experimento/protocolo.json` | H1, SHA `8ae06382c83a85ca…` |
| `configs/experimento/h2/fase0.json` | fase 0 de H2 |
| `configs/experimento/reward-diagnostic/protocolo.json` | diagnóstico, SHA `4bf33f06e0942c8b…` |
| `configs/experimento/reward-final-check/protocolo.json` | prueba final, SHA `6c2a8cb2001bf9f7…` |
| `configs/experimento/reward-final-check/{r1_shaping_reducido,r2_solo_evento}.yaml` | R1 y R2, derivadas del YAML heredado sin inventar pesos |
| `configs/experimento/reward-diagnostic/stage_2_offense_nozs.yaml` | D_C: copia exacta del heredado con `zero_sum: false` |
| `docs/experiments/**`, `docs/FINAL_REPORT.md`, `docs/CONTRIBUTIONS.md`, `docs/REPRODUCE.md`, `ESTADO_PROYECTO.md`, `NOTICE`, `UPSTREAM.md`, `MANIFIESTO_HASHES.txt` | 3.038 líneas de documentación propia |

---

## 4. Instrumentos que construimos y luego descartamos

Forman parte del trabajo tanto como los que sobrevivieron.

| Instrumento | Por qué parecía razonable | Cómo se comprobó | Por qué se descartó |
|---|---|---|---|
| Varianza explicada del crítico | métrica estándar de ajuste | se revisó cómo se calculan los retornos | **circular**: `ret = val + adv`, así que mide la estructura de GAE, no el ajuste |
| Razón \|valor/retorno\| | calibración intuitiva | se midió bajo `ZeroSumReward` | con media cercana a cero la razón se disparó hasta 48,3 sin significar nada |
| `recompensa_media_ultimas_10` | resumir la señal de recompensa | salió 0,0000 en configuraciones que no podían dar 0 | `Policy Reward` no está en el diccionario que devuelve `learn()`; el campo debe **ignorarse** |

---

## 5. Resumen cuantitativo

| | Heredado | Nuestro |
|---|---|---|
| Archivos de código | 5 scripts + módulos `rewards`/`actions`/`tournament` + `tests/` | **24 archivos, 5.401 líneas** |
| Documentación | 4 documentos | **3.038 líneas** |
| Configuraciones | 2 YAML de recompensa | 3 protocolos + 3 YAML derivados |
| Archivos modificados | — | **0** |
