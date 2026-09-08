# Opponent Pool Self-Play — experimentos reproducibles sobre Rocket League 1v1

> ## Based on [moanv2/rlgym](https://github.com/moanv2/rlgym)
>
> | | |
> |---|---|
> | Proyecto original | https://github.com/moanv2/rlgym |
> | Commit utilizado | `0c6965acf3d0405227282a80b1881dbfde3ef56b` |
> | Licencia | MIT — © 2026 Diego Alfaro Gomez |
> | Origen | *Final Project for Reinforcement Learning*, IE School of Science and Technology |
>
> **El bot de Rocket League, su entorno de entrenamiento y su arnés de torneo
> son obra de sus autores originales.** Este repositorio es una capa
> experimental construida encima; no sustituye al proyecto original ni reclama
> su autoría. El README original se conserva íntegro en
> [`docs/upstream/README-original.md`](docs/upstream/README-original.md).

**Pregunta:** ¿ayuda entrenar contra versiones anteriores de uno mismo?

**Respuesta honesta:** con el presupuesto disponible, **no pude demostrarlo**.
El experimento quedó inconcluyente, y al investigar por qué apareció un problema
más profundo que tampoco quedó resuelto. Este repositorio documenta el proceso
completo, incluidos los errores.

No hay un bot mejorado aquí. Hay un experimento que sabe decir que no.

---

## Qué es upstream y qué es de este proyecto

| | |
|---|---|
| **Upstream** (`moanv2/rlgym`) | el bot 1v1 de Rocket League: entorno sobre `rlgym_sim` + RocketSim, PPO, `LookupAction` de 90 acciones discretas, registro de recompensas, `ZeroSumReward`, arnés de torneo |
| **Este proyecto** | la capa experimental: pool de rivales históricos, ejecución reproducible, protocolos congelados por SHA256, evaluación trazable y análisis estadístico |

**Ningún archivo heredado fue modificado.** `git status` lo confirma: 0
modificados, 27 entradas nuevas. Inventario completo en
[`docs/CONTRIBUTIONS.md`](docs/CONTRIBUTIONS.md).

---

## La pregunta y el resultado

**H1:** ¿un agente entrenado contra una mezcla de instantáneas congeladas de sí
mismo (*opponent pool*) gana más, frente a rivales reservados, que uno entrenado
contra una única copia congelada de su yo reciente, con el mismo presupuesto de
muestras?

| Brazo | Victorias | Tasa |
|---|---|---|
| A — rival único | 18 / 360 | 5,00 % |
| B — pool | 15 / 360 | 4,17 % |

**B − A = −0,83 pp**, IC bootstrap 95 % **[−3,89, +2,22]**.

### Veredicto: INCONCLUYENTE

La diferencia está dentro de la incertidumbre: cambiar la semilla mueve el
resultado más que cambiar el método. **No** significa que el pool sea peor, ni
que el control fuera mejor.

> 📖 **[Read the full experimental story →](docs/PROJECT_STORY.md)**
> El proyecto entero contado desde cero, con las seis figuras: qué intentaba
> averiguar, qué construí, qué salió mal y por qué cerré la investigación.
>
> **[Read the full report (PDF)](deliverables/RLGym_SelfPlay_Project_Report.pdf)** ·
> **[View presentation (PDF)](deliverables/RLGym_SelfPlay_Portfolio_Presentation.pdf)** ·
> **[Download presentation (PPTX)](deliverables/RLGym_SelfPlay_Portfolio_Presentation.pptx)**

### Lo que vino después

1. **Diagnóstico:** efecto suelo frente a rivales miles de veces más entrenados,
   instantáneas del pool casi idénticas entre sí, y una política que se movía
   muy poco (1,55 % desde el punto de partida).
2. **H2** se diseñó para corregirlo y se **detuvo en su propia puerta de
   calidad** (NO-GO) antes de gastar 12 horas de cómputo.
3. **Diagnóstico de recompensas:** entrenar más **deterioraba** el juego frente
   al punto de partida, en las cinco configuraciones probadas.
4. **Mi explicación** —exceso de *reward shaping*— quedó **falsada**: reducirlo
   o eliminarlo empeoró el resultado de 61,5 % a 2,0 %.

**La causa del deterioro no quedó identificada.** Sabemos qué explicaciones no
bastan, no cuál es la buena.

---

## Cómo ejecutar lo reproducible

Sin entrenar nada, solo desde los resultados guardados:

```bash
python scripts/analyze_h1.py --jsonl $DATOS/experimento/eval-final.jsonl --salida out.json
python scripts/integrity_table.py --experimento $DATOS/experimento
python scripts/h2/gate_check.py --fase0 $DATOS/h2/fase0 \
    --jsonl $DATOS/h2/fase0/calibracion.jsonl --salida puerta.json
```

Prueba corta de la infraestructura (2 minutos, requiere mallas y C0 locales):

```bash
python scripts/h2/driver_h2.py --raiz-salida $DATOS/h2/prueba \
    --meshes $DATOS/collision_meshes --linajes sparring,piloto \
    --presupuesto 32000 --hitos 16000,32000
```

Guía completa: [`docs/REPRODUCE.md`](docs/REPRODUCE.md).

---

## Estructura

```
src/rlbot/env/          rocketsim_init · frozen_opponent · opponent_pool   (propio)
src/rlbot/{rewards,actions,tournament}/                                    (heredado)
scripts/                21 herramientas propias + 5 heredadas
scripts/h2/             infraestructura aislada por proceso, duelos, puerta
configs/experimento/    tres protocolos congelados con su SHA256
configs/reward_weights/ recompensas heredadas, sin modificar
docs/PROJECT_STORY.md   la historia completa, con figuras  ← empieza aquí
docs/FINAL_REPORT.md    informe técnico completo
docs/CONTRIBUTIONS.md   qué es heredado y qué es nuestro
docs/REPRODUCE.md       cómo reproducirlo
docs/figures/           las seis figuras, generadas desde results/
docs/experiments/       H1, H2, diagnósticos, incidencias
docs/upstream/          README y documentación originales, intactos
deliverables/           informe en PDF y presentación (PDF y PPTX)
results/                JSONL de partidas, análisis e informes (sin pesos)
tests/                  pruebas heredadas
ESTADO_PROYECTO.md      diario cronológico
```

> **Nota sobre los protocolos.** Los cuatro protocolos se congelaron con su
> SHA256 **antes** de ejecutar cada experimento. Los archivos publicados aquí
> tienen la ruta local de la máquina de ejecución **redactada por privacidad**,
> así que **no son byte a byte idénticos** a los originales y su hash es otro.
> Cada uno lleva al lado sus dos hashes, y la correspondencia completa está en la
> [tabla de trazabilidad](docs/FINAL_REPORT.md#6-bis-trazabilidad-de-los-hashes-de-protocolo).
> Se verificó campo a campo que lo único distinto es la cadena de ruta: ningún
> parámetro, semilla, criterio ni resultado cambió. Los scripts siguen
> verificando la integridad, ahora contra el hash público.

---

## Qué NO se redistribuye

- **Mallas de colisión** de RocketSim: material del juego.
- **Checkpoints de terceros** (los bots de referencia del torneo original).
- **Pesos entrenados**: 0,54 GB, fuera del repositorio por diseño.

Todo el material pesado vive en `%LOCALAPPDATA%\rlgym-selfplay-pool\`, nunca en
el repositorio. El `.gitignore` heredado ya excluye `*.pt`, `runs/`,
`collision_meshes/` y `*.log`.

Sí se publica: código propio, protocolos, documentación y los JSONL de
resultados (texto, con hashes y resultados, sin pesos).

---

## Volumen del trabajo

Calculado solo desde artefactos existentes:

| | |
|---|---|
| Entrenamientos con informe | 15 |
| Muestras procesadas | 12.112.000 |
| Cómputo registrado | 3,00 h |
| Partidas evaluadas | 3.960 (magnitud de ingeniería, **no** una muestra estadística: son protocolos distintos) |
| Protocolos congelados por SHA256 | 3 |
| Código propio | 5.401 líneas en 24 archivos |
| Documentación propia | 3.038 líneas |

---

## Licencia y atribución

Este proyecto hereda la **licencia MIT** de `moanv2/rlgym`, commit base
`0c6965acf3d0405227282a80b1881dbfde3ef56b`. Ver [`LICENSE`](LICENSE),
[`NOTICE`](NOTICE) y [`UPSTREAM.md`](UPSTREAM.md).

El README original del proyecto upstream se conserva sin modificar en
[`docs/upstream/README-original.md`](docs/upstream/README-original.md), junto con
su documentación (`docs/upstream/`). Los hashes de las aportaciones propias están
en [`MANIFIESTO_HASHES.txt`](MANIFIESTO_HASHES.txt).

### Reparto de autoría en una línea

| Heredado de `moanv2/rlgym` | Aportado por este proyecto |
|---|---|
| entorno 1v1 sobre `rlgym_sim` + RocketSim, PPO, `LookupAction`, registro de recompensas, `ZeroSumReward`, arnés de torneo, `src/rlbot/{rewards,actions,tournament,models,obs,...}` | pool de rivales históricos, ejecución aislada por proceso, protocolos congelados por SHA256, evaluación trazable, análisis estadístico, `src/rlbot/env/{rocketsim_init,frozen_opponent,opponent_pool}.py` y 21 scripts |

**0 archivos heredados modificados.**
