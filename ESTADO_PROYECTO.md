# Estado del proyecto

**LINEA EXPERIMENTAL CERRADA (§17).** Cierre tecnico y documentacion completos. H1 inconcluyente (§14), H2 en NO-GO (§15.1), cinco recompensas probadas y ninguna evita el deterioro (§15.2, §16).

> **Corrección que afecta a las secciones 11 y 12:** allí se describe
> `DefaultReward` como «solo goles y muy dispersa». **Es falso**: penaliza la
> velocidad angular del coche y no tiene relación con marcar. Detalle en §13.1.
> Las mediciones de esas secciones son válidas; su interpretación de la
> recompensa, no.

**Fase 0 COMPLETADA. Bloque «ciclo real de entrenamiento» COMPLETADO.**
Última actualización: **2026-09-07** (tercera sesión).

Este archivo dice lo que está **hecho y comprobado ejecutándolo**, y lo que no.

---

## 1. Resumen en una línea

El bloqueo de las mallas de colisión **está resuelto sin instalar Rocket League**, la
pila completa funciona, y se ha medido por separado simulación, inferencia
integrada y actualización PPO: **22 OK · 0 FALLO · 0 NO EJECUTADO**.

---

## 2. Rutas

| Qué | Dónde |
|---|---|
| Original, **intacto** | `CVs\Nuevo trabajo\rlgym-main\rlgym-main` |
| Proyecto | `CVs\Nuevo trabajo\rlgym-selfplay-pool` |
| Entorno **histórico** (torch 2.5.1, conservado) | `%LOCALAPPDATA%\rlgym-selfplay-pool\venv` |
| Entorno **en uso** (torch 2.13.0 + pila) | `%LOCALAPPDATA%\rlgym-selfplay-pool\venv-val` |
| Mallas de colisión | `%LOCALAPPDATA%\rlgym-selfplay-pool\collision_meshes\soccar\` |
| Checkpoints ajenos | `%LOCALAPPDATA%\rlgym-selfplay-pool\artifacts\` (114 MB) |
| Paquete oficial descargado | `%LOCALAPPDATA%\rlgym-selfplay-pool\vendor\` |
| Informes | `%LOCALAPPDATA%\rlgym-selfplay-pool\outputs\` |

Nada pesado vive en OneDrive ni en el repositorio. No se ha tocado ninguna
instalación global, ni el PATH, ni la configuración de seguridad.

**Original verificado sin cambios**: huella SHA256 de sus 85 archivos, idéntica.

---

## 3. Bloqueos: resueltos y pendientes

### Los 4 FALLO del informe anterior

Eran **dos causas**, no cuatro:

| FALLO original | Causa | Estado |
|---|---|---|
| `rlgym_sim` no instalado | decisión previa: no instalar sin poder ejecutar | **resuelto** — instalado al SHA fijado |
| `rlgym-ppo` no instalado | misma causa | **resuelto** — instalado al SHA fijado |
| `rocketsim` no instalado | misma causa **+ un fallo del propio preflight**: buscaba `rocketsim` cuando el módulo se importa como `RocketSim` | **resuelto** — instalado y comprobación corregida |
| `collision_meshes` ausente | causa independiente | **resuelto** — ver abajo |

Los tres primeros eran el mismo asunto (pila sin instalar) y uno de ellos, además,
un falso negativo mío por el nombre de importación. Obtener las mallas **no** los
habría resuelto: eran independientes.

### Los 2 NO EJECUTADO

Ambos derivaban de la misma causa (sin simulador no hay nada que medir). Los dos
**se han ejecutado ya**, y además desglosados en tres mediciones distintas.

### Pendiente

**Ninguno dentro del alcance de la fase 0.**

---

## 4. Carga de modelos: corregida

**Avisos consultados y su consecuencia real:**

| Aviso | Severidad | Afecta a | Corregido en |
|---|---|---|---|
| CVE-2025-32434 (GHSA-53q9-r3pm-6pq6) | crítica | `< 2.6.0` | 2.6.0 |
| CVE-2026-24747 (GHSA-63cw-57p8-fm3p) | alta | `< 2.10.0` | 2.10.0 |
| GHSA-vgrw-7cvw-pwgx | media | `< 2.9.1` | 2.9.1 |
| GHSA-887c-mr87-cxwp | media | `<= 2.7.1` | 2.8.0 |
| GHSA-rrmf-rvhw-rf47 | baja | `<= 2.12.1` | **2.13.0** |
| GHSA-qfhq-4f3w-5fph | baja | `< 2.10.0` | 2.10.0 |

**Subir a 2.6.0 no habría bastado**, y por eso no se hizo automáticamente. La
versión más baja que resuelve **todos** los avisos con corrección publicada es
**2.13.0**, y es la elegida: se queda lo más cerca posible de lo que espera la
pila antigua sin dejar ninguna vulnerabilidad conocida abierta. 2.14.0 también
valdría; se prefiere no ir más lejos de lo necesario.

**Versión final: `torch==2.13.0+cpu`.**

**Comprobaciones de carga realizadas** (bajo 2.13.0, con `weights_only=True`
explícito en todas las rutas):

- Los 4 checkpoints cargan, con **hash SHA256 verificado** contra el registrado.
- El contenido es **solo tensores** (`{'Tensor'}`), sin objetos exóticos.
- **No** se ha usado `weights_only=False` ni allowlists de deserialización.
- Se revisó también la ruta heredada: `src/rlbot/tournament/policy_io.py` ya usa
  `weights_only=True`. `src/rlbot/evaluation/evaluate.py`, también.

El entorno anterior (torch 2.5.1) **se conserva** en `venv\` como registro
histórico y **no se usa para cargar checkpoints**.

> Un venv separa dependencias. **No es un aislamiento de seguridad** frente a
> código o modelos maliciosos, y no se presenta como tal. La protección real aquí
> es la combinación de: versión de torch sin vulnerabilidades conocidas, carga
> restringida, y procedencia verificada por hash.

---

## 5. Mallas de colisión: resueltas sin instalar el juego

**No hace falta instalar Rocket League.** Las mallas se obtienen de la
distribución oficial de RLGym.

| | |
|---|---|
| Paquete | `rlgym-rocket-league` **2.0.1** (sdist de PyPI) |
| SHA256 del paquete | `3be8e9d2f1cfb6514e0e3d455fb33ff95e26eb7c399f819fff0258025cf4d501` (coincide con PyPI) |
| Contenido usado | `rlgym/rocket_league/sim/collision_meshes/soccar/` — 16 archivos `.cmf`, 168 KB |
| Licencia del repositorio | Apache-2.0 |
| Descargado sin instalar sus dependencias | sí (`pip download --no-deps`, luego extracción manual) |

**Compatibilidad realmente comprobada, no supuesta:**

1. `setup_rocket_league.py` de RLGym declara `rocketsim >=2.0.0,<3.0.0`. Nuestro
   pin es **2.2.1**, dentro del rango.
2. `rsim.init(<ruta>)` es API de **RocketSim**, no de RLGym v2. Existe en 2.2.1.
3. **Prueba ejecutada**: `rsim.init(ruta)` → `Arena(SOCCAR)` → 2 coches → 120
   ticks → **la pelota reposa en z = 93,15**. El radio de la pelota es ~92,75, así
   que reposa sobre el suelo: **la colisión está cargada de verdad**. Si las
   mallas no estuvieran, atravesaría el suelo o RocketSim abortaría.
4. **No se ha instalado RLGym v2 ni se ha migrado nada.** Solo se usan los datos
   `.cmf`; la API antigua (`rlgym_sim`) se mantiene intacta.

**Comportamiento en procesos de Windows — comprobado, no presupuesto:**

`rlgym_sim` **nunca llama a `rsim.init()`**: va directo a `rsim.Arena(...)`, y
RocketSim busca por defecto en `./collision_meshes/` relativo al directorio de
trabajo. Se probó explícitamente qué pasa con `multiprocessing` en Windows
(método `spawn`):

```
padre con init()          -> arena ok, ball z = 93.15
hijo SIN init()           -> RuntimeError: ROCKETSIM FATAL ERROR:
                             No arena meshes found for gamemode soccar
hijo CON init() propio    -> arena ok, ball z = 93.15
```

> **El hijo NO hereda la inicialización del padre.** Cada proceso trabajador
> tendrá que llamar a `rsim.init(ruta)` por su cuenta. El sitio natural es
> `_EnvBuilder.__call__` del proyecto base, que ya se ejecuta dentro de cada
> trabajador y ya es picklable.

Además, `rsim.init()` **solo admite una llamada por proceso** (la segunda lanza
`RuntimeError: Already inited`), así que la inicialización lleva una guarda.

### Condiciones de uso — lo que sí y lo que no se afirma

RLGym distribuye estas mallas oficialmente en un paquete Apache-2.0. **No hay
ninguna declaración de procedencia junto a los archivos**, y son geometría
derivada del juego. Por tanto:

- **Uso local**: se usan como cualquier usuario que instala el paquete oficial.
- **Redistribución: NO.** No se copian al repositorio, no se publican y no se
  suben a ningún sitio. Viven solo en `%LOCALAPPDATA%`.
- **No se interpreta** que su presencia en GitHub autorice a redistribuirlas, ni
  que Apache-2.0 conceda derechos sobre geometría derivada de Rocket League.
- El README de la base afirma que estos datos «no se pueden compartir». Esa
  tensión se deja anotada, no resuelta: no nos corresponde resolverla.

---

## 6. Qué funciona, comprobado ejecutándolo

Informe: `outputs/preflight-2026-09-07b-sim.json` — **22 OK · 0 FALLO · 0 NO EJECUTADO**.

| Comprobación | Resultado |
|---|---|
| Arena de RocketSim | creada, 120 ticks, física de colisión correcta |
| `env.reset()` 1v1 | 2 agentes, obs de 89 dimensiones cada uno |
| `env.step()` | obs y recompensas **finitas**, rango [-2,00, 2,00] |
| Inferencia integrada | los **dos coches deciden con la política real** cargada de un checkpoint |
| Actualización PPO | una actualización completa (política + crítico) sobre lote **sintético** |

> **Precisión añadida el 07/09 (tercera sesión).** Esa actualización PPO usó
> **muestras sintéticas**: valida el *componente* de aprendizaje —que la red, el
> optimizador y el paso hacia atrás funcionan—, **no** un entrenamiento integrado
> con experiencia recogida del simulador. El ciclo completo con experiencia real
> se comprueba aparte, en la sección 11. Los 22 OK siguen siendo el resultado
> válido de lo que se ejecutó entonces; no se retiran ni se reinterpretan.

El entorno usa el `LookupAction` **heredado del proyecto base** (90 acciones
discretas → 8 controles). Eso valida de paso que ese código funciona: con el
`DefaultAction` de rlgym_sim la política no encaja, porque emite un índice y el
parser espera 8 valores continuos.

---

## 7. Rendimiento medido — y qué NO significa

Todo en **un solo proceso**, CPU, 3 s por medición. Carga total de benchmark:
**menos de 30 segundos**, muy por debajo del tope de 5 minutos.

| Medición | Resultado |
|---|---|
| **Simulación sola** (acciones aleatorias) | **5.666 pasos de entorno/s** = 11.332 muestras de agente/s |
| **Simulación + inferencia** (los 2 coches, red 512×3) | **523 pasos de entorno/s** = 1.046 muestras/s |
| **Actualización PPO** (50.000 muestras sintéticas) | 1,96 s → **25.501 muestras/s** |
| Inferencia aislada, lote 1 | 8.256/s (512×3) · 4.866/s (1024×3, obs 89) · 3.164/s (1024×3, obs 107) |

**Lo que estos números NO son:**

- **La simulación con acciones aleatorias no es velocidad de entrenamiento.**
  Valida la integración; no dice nada sobre jugar.
- **El salto de 5.666 a 523 pasos/s es la medida importante**: con la política
  decidiendo, el coste se multiplica por ~11. La inferencia domina, no el
  simulador. Pero es el caso **más desfavorable**: se llama a `get_action` por
  coche, con lote 1. rlgym-ppo agrupa las inferencias de varios trabajadores
  (`min_inference_size`), así que en entrenamiento real el coste por muestra
  será menor. **Cuánto menor, no se ha medido.**
- **Un proceso no son N procesos.** No se ha medido el escalado con varios
  trabajadores, ni el efecto de la temperatura en un chip de 15 W durante horas.
- **3 segundos no permiten estimar una carga prolongada.** Sigue sin haber una
  cifra fiable de muestras/hora sostenidas.
- Al **brazo B no se le atribuye ningún rendimiento**: no está implementado.
- La comparación de inferencia aislada con el informe anterior (1.818/s vs
  8.256/s para 512×3) **no es válida**: cambió la versión de torch.

---

## 8. Archivos creados o modificados en esta sesión

| Archivo | Cambio |
|---|---|
| `scripts/preflight.py` | ampliado: argumentos `--meshes` y `--dev-ckpt`, comprobaciones de simulación, y **corregido** un falso negativo (`rocketsim` vs `RocketSim`) |
| `scripts/checks_sim.py` | **nuevo**: arena, entorno 1v1, y las tres mediciones separadas |
| `requirements/lock-2026-09-07.txt` | **nuevo**: entorno reproducible con la justificación de la versión de torch |
| `ESTADO_PROYECTO.md` | este archivo |
| `UPSTREAM.md` | añadida la procedencia de las mallas y sus hashes |
| `docs/experiments/plan.md` | estados de fases actualizados |

Archivos heredados modificados: **ninguno**. `LICENSE` intacto.

Informe anterior conservado: `outputs/preflight-2026-09-07.json`.

---

## 9. Higiene

- **W&B**: entra como dependencia de `rlgym-ppo` (0.29.0). **No hay sesión
  iniciada**, no se ha hecho login y no se ha enviado nada. En el entrenamiento
  irá con `WANDB_MODE=disabled` explícito.
- **Sin procesos vivos** al terminar; comprobado.
- Sin commits, push, publicación, servicios de pago ni instalaciones globales.
- Atribución original conservada.

---

## 11. Ciclo real de entrenamiento (tercera sesión, 07/09/2026)

Objetivo del bloque: demostrar que **podemos recoger experiencia real, actualizar
un modelo, guardarlo, recuperarlo y evaluarlo con trazabilidad**. Conseguido.

### 11.1 Inicialización de RocketSim, integrada

`src/rlbot/env/rocketsim_init.py` (nuevo): inicializa **una sola vez por proceso**,
con **ruta absoluta**, sin depender del directorio de trabajo, y **sin tragarse
excepciones** — solo se ignora «Already inited», que es el único caso benigno.
La llamada vive en `ConstructorRivalCongelado.__call__`, que se ejecuta dentro de
cada trabajador. Comprobado con spawn y ejecutando desde otro directorio.

### 11.2 Adaptador aprendiz / rival congelado

`src/rlbot/env/frozen_opponent.py` (nuevo). **Versión mínima**: un aprendiz y un
rival fijo. **Sin pool, sin historial, sin selección de rivales, sin refresco.**

`scripts/check_adapter.py` — 9 comprobaciones, **todas OK**:

| Comprobación | Resultado |
|---|---|
| Un solo agente hacia rlgym-ppo | `reset()` devuelve forma `(89,)` |
| El aprendiz recibe su propia observación | equipo 0 (azul), verificado contra el env interno |
| Recompensa escalar del aprendiz | como espera rlgym-ppo con 1 agente |
| Obs y recompensas finitas | 400 pasos |
| Fin de episodio se transmite | 1 final en 400 pasos, 3 episodios |
| **Rival congelado** | hash de pesos idéntico tras 400 pasos, `requires_grad=False` en todos |
| Proceso hijo con spawn | 60 pasos, obs `[89]` |

Que el entorno se presente como **un solo agente** es lo que garantiza
estructuralmente que **solo la experiencia del aprendiz entra en PPO**: la del
rival nunca llega al buffer.

### 11.3 Entrenamiento real con experiencia del simulador

`scripts/train_smoke.py` (nuevo). **No son datos sintéticos.**

**Inicializar no es reanudar.** Se partió de `diego_1.18B_512`, que trae solo
`PPO_POLICY.pt`. Por tanto:

| Componente | Estado al arrancar |
|---|---|
| Política | pesos del checkpoint ajeno |
| **Crítico** | **ALEATORIO** — el checkpoint no trae `PPO_VALUE_NET.pt` |
| **Optimizadores** | **NUEVOS** — sin estado de Adam |
| Normalización de obs | `standardize_obs=False`: no hay estadística que restaurar |
| Normalización de retornos | `standardize_returns=True`: empieza de cero |

Resultado (`outputs/train-smoke-a.json`):

- **3 iteraciones completadas, 24.000 muestras reales**, 21,7 s
- política: `98b8b18d...` → `fc975e55...` (**cambió**)
- crítico: `60741d87...` → `fa1c39e7...` (**cambió**)
- todos los parámetros **finitos**
- entropía 4,051 (el máximo con 90 acciones es ln 90 = 4,4998)

**Valor que parecía anómalo y no lo es:** KL ~ 2e-7 y clip fraction = 0. Con
`ppo_epochs=1` y minilote igual al lote, la primera pasada tiene ratio
exactamente 1, así que KL ~ 0 y no se recorta nada. Es lo esperado, no un fallo.
No se ha debilitado ninguna comprobación para que saliera verde.

### 11.4 Guardado y recuperación en otro proceso

Checkpoint nuevo en carpeta exclusiva. **Ningún original se ha sobrescrito.**
rlgym-ppo añade un sufijo temporal a la carpeta (`smoke_a-1788801969692197900`),
que es justo lo que rodea `_find_latest_checkpoint` de la base.

**Los nuestros sí son checkpoints completos**: política + crítico + los dos
optimizadores + book keeping.

Recuperación en un **proceso distinto** (`outputs/train-smoke-b-resume.json`):

| Qué | Restaurado |
|---|---|
| Contador de timesteps | **sí** — 24.000 -> 24.000 |
| Pesos de la política | **sí** — `fc975e55ab869151` idéntico |
| Pesos del crítico | **sí** — `fa1c39e790912885` idéntico |
| Estadística de retornos | rlgym-ppo la guarda en el book keeping; **no verificada byte a byte** |
| Semilla / estado del RNG | **no se conserva**: cada ejecución vuelve a sembrar |

Continuación real: 1 iteración, 8.000 muestras, 24.000 -> 32.000.

### 11.5 Escalado medido

Configuraciones **secuenciales**, nunca en paralelo con la evaluación. 1 hilo de
torch por trabajador, para que no se peleen por la CPU.

| Trabajadores | Muestras | Segundos | **Muestras/s** |
|---|---|---|---|
| 1 | 12.000 | 14,1 | 854 |
| **2** | 12.000 | 10,5 | **1.146** |
| 4 | 12.002 | 13,1 | 915 |

**4 trabajadores es peor que 2.** En un chip de 15 W con 2 núcleos P y 8 E, más
procesos no compensan. Por eso **no se probaron 6 ni 8**: las mediciones no lo
justificaban.

**Estabilidad con 2 trabajadores**, 2,5 min (`outputs/estabilidad-2proc.json`):

- **25 iteraciones, 200.000 muestras, 152,7 s -> 1.309 muestras/s sostenidas**
- por iteración: ~6,0-6,2 s totales, de los cuales **~5,3 s de recogida (~88 %)**
  y **~0,62 s de actualización PPO (~10 %)**
- «Collected Steps per Second» entre 1.487 y 1.528: sin degradación visible

> **La recogida domina, no la actualización.** Y 1.309 muestras/s **no son**
> «4,7 M muestras/hora medidas»: son 2,5 minutos medidos. Extrapolar a una hora
> es una extrapolación, y no se ha comprobado el efecto térmico en sesiones
> largas. Tampoco se ha separado el coste de inferencia del aprendiz del coste
> del rival: el rival se evalúa coche a coche dentro del entorno y **no se
> beneficia del agrupamiento** que rlgym-ppo hace con el aprendiz.
> **Al pool histórico, que no existe, no se le atribuye ningún rendimiento.**

### 11.6 Evaluación de desarrollo con registro

`scripts/eval_dev.py` (nuevo). Reutiliza `tournament/obs.py` y
`tournament/policy_io.py` heredados; no reconstruye el arnés.

**Diferencia deliberada con el torneo heredado:** `tournament/match.py` desempata
por diferencia de goles y, en último término, por «más timesteps de
entrenamiento» (`decided_by="seed"`). Eso vale para un cuadro de competición pero
**falsearía un experimento**. Aquí un empate se registra como empate.

Serie: 8 partidas fijadas de antemano, semillas 1000-1007 registradas, lados
alternados, modo estocástico declarado. Resultado:

- 6 partidas terminadas **por gol**
- 2 partidas alcanzaron el tope de 900 pasos -> marcadas **`incompleta`**, y
  **NO cuentan como empate**
- 0 empates reales por tiempo (el tope de 900 pasos es menor que el
  `TimeoutCondition` de 3.000 del arnés, así que ninguna llegó a agotar el
  tiempo de juego)
- totales del resumen **cuadran** con el JSONL

Ficheros: `outputs/eval-dev-2026-09-07.jsonl` (una línea por partida, con id,
modelos, SHA256, config, semilla, lado, modo, resultado, causa y duración) y
`outputs/eval-dev-2026-09-07-resumen.json`, generado **leyendo el JSONL**.

> **Esto no dice nada sobre calidad de juego.** Nuestro checkpoint de 24.000
> muestras perdió 5 de 6 decisivas contra el artefacto de desarrollo, que tiene
> 1.180 millones de pasos. Es lo esperado: 24.000 muestras con un crítico
> aleatorio degradan una política ya entrenada. **La serie valida el arnés y su
> registro, nada más.**

### 11.7 Presupuesto de carga

~15 minutos de los 20 autorizados. Sin trabajos nocturnos, sin procesos en
segundo plano, sin cambios de plan energético. Comprobado al terminar: **ningún
proceso vivo**.

---

## 12. Calentamiento del crítico, C0 y pool mínimo (cuarta sesión, 07/09/2026)

### 12.1 El instrumento que diseñé no medía lo que creía

Diseñé la prueba alrededor de la **varianza explicada** del crítico:
`EV = 1 - Var(retornos - valores) / Var(retornos)`, esperando verla subir desde
~0 con un crítico aleatorio. **No ocurrió: EV valió 0,748 ya en la primera
iteración, con el crítico todavía sin actualizar, y se quedó plana ahí.**

El motivo, mirando los datos: `valores_std` es sistemáticamente ≈ la mitad de
`retornos_std`, en todas las iteraciones. Como los retornos se derivan de los
propios valores (`retornos = valores + ventajas`, definición de GAE), la métrica
es **circular**: mide la proporción estructural entre ventaja y retorno que
impone GAE con λ=0,95, no la calidad del crítico. Es la EV convencional —la
misma que usa Stable-Baselines3— pero en este régimen no discrimina.

**No se elige el punto de calentamiento con esa métrica.** Queda registrada como
instrumento descartado, con su explicación.

### 12.2 El indicador que sí funcionó: calibración del nivel

Lo que sí evoluciona de forma monótona e interpretable es si el crítico predice
el **nivel** correcto: la razón entre la media de sus valores y la media de los
retornos observados.

| it | ts | \|val/ret\| | vf_loss | deriva política | veredicto |
|---|---|---|---|---|---|
| 1 | 8.000 | 0,483 | 0,193 | 0,0022 | infra-predice |
| 5 | 40.000 | 0,697 | 0,268 | 0,0058 | infra-predice |
| 8 | 64.000 | 0,905 | 0,128 | 0,0078 | **calibrado** |
| 9 | 72.000 | 0,955 | 0,149 | 0,0084 | calibrado |
| **10** | **80.000** | **1,034** | **0,163** | **0,0089** | **calibrado** |
| 11 | 88.000 | 1,063 | 0,204 | 0,0094 | calibrado |
| 13 | 104.000 | 1,096 | 0,268 | 0,0104 | empieza a sobre-predecir |

**Criterio de decisión, cruzando cuatro cosas** (no una sola métrica):

1. razón |val/ret| dentro de [0,90, 1,10] — el crítico ya no está desalineado;
2. deriva relativa de la política < 0,05 — no ha habido deriva fuerte;
3. gradientes y parámetros **finitos en las 13 iteraciones**;
4. entropía (4,02-4,05), KL (~1e-7) y clip fraction (0) estables.

**Punto elegido: iteración 10 = 80.000 muestras.** Antes de la 8 el crítico
infra-predice más de un 10 %; a partir de la 11 empieza a irse al otro lado
mientras la deriva sigue creciendo. La 10 es el centro de la ventana calibrada
con la menor deriva posible.

**Presupuesto usado:** 13 iteraciones (104.000 muestras, ~5 min). No se convirtió
en un entrenamiento largo.

> **Limitación que hay que decir.** La recompensa es `DefaultReward`, que solo
> premia goles: extremadamente dispersa. Con una recompensa moldeada —la de
> `stage_1_basics` de la base— la señal del crítico sería mucho más informativa y
> este análisis convendría repetirlo. La recompensa de entrenamiento **no** se ha
> usado en ningún momento como prueba de calidad del bot.

### 12.3 C0: el checkpoint común

| | |
|---|---|
| Ruta | `%LOCALAPPDATA%\rlgym-selfplay-pool\runs\C0\` |
| Origen | iteración 10 del calentamiento, semilla 20260907 |
| `cumulative_timesteps` | **80.000** |
| `cumulative_model_updates` | 10 |
| Completo | **sí**: política + crítico + los dos optimizadores + book keeping |
| `reward_running_stats` | presente |

Hashes en `runs/C0-hashes.json`. `PPO_POLICY.pt` →
`e6a87faee7e8238e7732e192c39b387b...`

**Recuperación comprobada en procesos nuevos:** los dos brazos del smoke A/B
cargaron C0 y arrancaron ambos en `ts_inicial = 80.000`.

**No se reutilizó** el checkpoint de 24.000 de la smoke test anterior: la
evidencia del calentamiento sitúa la calibración en 80.000, no en 24.000, donde
el crítico todavía infra-predecía un ~42 %.

### 12.4 Diseño del pool

`src/rlbot/env/opponent_pool.py` (nuevo) + `EntornoPool` / `ConstructorPool`.

- Instantáneas en disco, con **manifiesto** (`meta.json`) que registra id,
  timestep, **SHA256**, fecha y configuración.
- Escritura **atómica** del manifiesto: los trabajadores leen mientras el
  principal escribe.
- Cargar una instantánea **no la modifica**; hay verificación por hash.
- **Muestreo uniforme** entre las elegibles, reproducible: depende de
  `(semilla, número de episodio)`, no del reloj ni del orden de los procesos.
- Caché por instantánea en cada trabajador: solo se leen pesos del disco la
  primera vez que se usa una.

**Por qué uniforme y nada más.** Es la regla más simple capaz de producir el
efecto que estudia H1. Elo, prioridades adaptativas o currículos añadirían cada
uno una variable más que aislar, y el experimento pregunta una sola cosa: si
importa *de dónde sale el rival*.

**Coordinación entre procesos**: por sistema de archivos, porque en Windows los
trabajadores son procesos spawneados sin memoria compartida con el padre.

### 12.5 A y B con la misma maquinaria

La **única** diferencia es la política de retención del pool:

| | Brazo A (control) | Brazo B (variante) |
|---|---|---|
| Retención | **1** | **8** |
| Rival | la única instantánea, refrescada cada K | muestreada entre las históricas |
| Clase de entorno | `EntornoPool` | `EntornoPool` (la misma) |

**K = 8.000 muestras**, que coincide con el lote de una iteración. Razón: hace
que crear instantáneas caiga en la frontera natural de actualización, sin
sincronización adicional, y da a B un pool que crece una por iteración. Para el
experimento real, con presupuesto mayor, K debería crecer en proporción.

### 12.6 Pruebas de mecánica — 17/17 OK

`scripts/test_pool.py`: guardado y hash estable · política congelada que no
cambia al usarla · cargar no modifica el archivo · **A reemplaza** su única
instantánea y borra las antiguas · **B conserva** varias · muestreo reproducible
con la misma semilla y distinto con otra · usa más de una instantánea ·
**con una sola instantánea A y B eligen lo mismo** · en el entorno: un agente
hacia PPO, aprendiz azul, obs y recompensas finitas, reset y fin de episodio,
instantáneas intactas tras jugar.

### 12.7 Smoke A/B

`outputs/ab-smoke-A.json` y `outputs/ab-smoke-B.json`.

| Magnitud | A | B | Dif. |
|---|---|---|---|
| Muestras para PPO | 40.000 | 40.000 | 0,0 % |
| Pasos de entorno | 40.000 | 40.000 | 0,0 % |
| Actualizaciones | 5 | 5 | 0,0 % |
| Inferencias aprendiz / rival | 40.000 / 40.000 | 40.000 / 40.000 | 0,0 % |
| Instantáneas creadas | 5 | 5 | 0,0 % |
| **Instantáneas en el pool** | **1** | **6** | diferencia buscada |
| Segundos de recogida | 28,54 | 28,31 | −0,8 % |
| Segundos de actualización | 3,22 | 3,25 | +0,9 % |
| Muestras/s | 1.259,3 | 1.267,5 | +0,7 % |

**Configuración: ninguna diferencia** salvo la retención. Mismo C0, misma
semilla, misma arquitectura, recompensa, observaciones, acciones, trabajadores,
hilos, lote y K.

> **El coste añadido por el pool no es relevante a esta escala**: ±1 %, dentro
> del ruido entre ejecuciones, y B salió incluso marginalmente más rápido.
> Ahora sí se puede decir «mismo cómputo», **pero con dos matices**: (a) medido
> con 6 instantáneas y caché en cada trabajador —con un pool mucho mayor habría
> que volver a medirlo—, y (b) las estadísticas de carga del pool viven en los
> procesos trabajadores y **no se han recogido** en el informe del principal;
> la comparación se hace con los tiempos globales.
>
> **La variable que se iguala en el experimento final sigue siendo las muestras
> de aprendizaje**, y se registrarán además pasos de entorno, actualizaciones y
> tiempo de reloj.

**Las diferencias en métricas de entrenamiento entre A y B no son evidencia de
mejora de nadie.** Con 40.000 muestras y una semilla no significan nada.

### 12.8 Dos fallos propios, corregidos

1. El `Learner` arranca los trabajadores y llama a `env.reset()` **durante su
   construcción**. Guardar la instantánea inicial después dejaba el pool vacío,
   los trabajadores morían y el entrenamiento se colgaba. Ahora la instantánea
   inicial se crea leyendo la política de C0 del disco, **antes** de construir
   el Learner.
2. `timestep_limit` es **absoluto**, no un presupuesto. Con C0 en 80.000 y
   límite 40.000 el bucle terminaba sin hacer nada. Ahora es `ts0 + presupuesto`.

### 12.9 Riesgo residual anotado

`rlgym_ppo/ppo/ppo_learner.py::load_from` usa `torch.load(...)` **sin**
`weights_only=True`. Es código heredado de terceros y solo se le pasan
checkpoints **producidos por nosotros**, así que el riesgo es bajo, pero conviene
saberlo: la carga restringida que aplicamos en nuestro propio código no cubre
esa ruta.

---

## 13. Calibración final y congelación del protocolo (quinta sesión, 07/09/2026)

### 13.1 Corrección importante: qué es DefaultReward

En las secciones anteriores escribí varias veces que `DefaultReward` «solo premia
goles y por eso es muy dispersa». **Era falso.** Al comparar recompensas medí una
densidad de recompensa no nula de 1,000, lo que no encajaba, y fui al código:

```python
# rlgym_sim/utils/reward_functions/default_reward.py
def get_reward(self, player, state, previous_action) -> float:
    return - math.vecmag(player.car_data.angular_velocity) / 100
```

**`DefaultReward` penaliza la velocidad angular del coche. No tiene nada que ver
con goles.** Es un marcador de posición que premia *no girar*. Es densa, sí, pero
**no codifica la tarea**: un agente entrenado con ella aprende a girar poco.

Eso cambia la decisión de recompensa de «cuál da más señal» a algo mucho más
básico: **con `DefaultReward` el experimento no mediría nada relacionado con
jugar**, y H1 pregunta por robustez *jugando*.

Las secciones 11 y 12 se conservan como registro, pero **su caracterización de
`DefaultReward` es incorrecta** y queda corregida aquí.

### 13.2 Comparación de recompensas

`scripts/compare_rewards.py`, 8 iteraciones de 8.000 muestras por brazo, todo
idéntico salvo la recompensa: mismo checkpoint de política, misma semilla
(20260907), misma arquitectura, 2 trabajadores, 1 hilo.

`stage_1_basics.yaml` es **heredado y está intacto** (commit `e4b8c39` de
upstream). Componentes: `velocity_player_to_ball` 0,10 · `face_ball` 0,05 ·
`velocity_ball_to_goal` 0,30 · `event` 8,0 (gol +1, encajar −1, tiro 0,1,
demo 0,1), todo envuelto en `ZeroSumReward`.

| Métrica | DefaultReward | stage_1_basics |
|---|---|---|
| Densidad de recompensa | 1,000 | 0,9995 |
| **Dispersión de la recompensa** | **0,0168** | **0,4597** (≈27×) |
| `vf_loss` primera → última | 0,188 → 0,110 (−42 % en 8 it) | **2,62 → 0,133 (−95 %)** |
| Entropía final | 4,026 (plana) | 3,964 (bajando) |
| KL máxima | 4,2e−7 | 2,5e−5 |
| Clip fraction máxima | 0 | 0,00013 |
| Deriva de política final | 0,00809 | 0,00798 |
| Gradientes finitos | sí | sí |
| Muestras/s | 1.295 | 1.194 (−8 %) |

**Lectura.** Un retorno mayor no sería una ventaja —las escalas no son
comparables— así que no lo uso como criterio. Lo que decide es:

1. `DefaultReward` **no es la tarea**. Punto de partida decisivo.
2. Con `stage_1_basics` la entropía **se mueve** y la KL es ~60× mayor: la
   política está aprendiendo algo. Con `DefaultReward` la entropía es plana:
   con nuestro presupuesto, H1 sería indetectable porque no cambiaría nada.
3. **Sin coste de estabilidad**: deriva prácticamente idéntica, sin recorte,
   gradientes finitos.
4. El coste de cómputo es un 8 % mayor. Asumible.

**Decisión: `stage_1_basics`.** Y en consecuencia, tal y como estaba acordado:

> **C0 (80.000 muestras, DefaultReward) queda INVÁLIDO** para el experimento.
> No se mezclan checkpoints entrenados con recompensas distintas. No se reutiliza
> ninguna estadística del crítico anterior.

### 13.3 El calentamiento, rehecho — y una segunda métrica descartada

Al repetir el calentamiento con `stage_1_basics`, la razón valores/retornos que
funcionó en §12 **se volvió inservible**: 0,579 · −0,591 · 0,258 · 0,938 · 1,220
· 2,509 · −1,090 · … · **48,310**.

El motivo: `stage_1_basics` va envuelta en **ZeroSumReward**, así que el retorno
medio ronda cero y el cociente divide por casi nada. La métrica solo servía
porque con `DefaultReward` el retorno medio era claramente negativo.

**Van dos instrumentos descartados** —la varianza explicada por circular (§12.1)
y ahora la razón de calibración por denominador nulo—. Lo dejo escrito porque es
el tipo de error que se repite si no queda registrado.

**La métrica que sí sirve aquí es `vf_loss`**, el error cuadrático del crítico:

| it | ts | vf_loss | deriva | entropía |
|---|---|---|---|---|
| 1 | 8.000 | **2,910** | 0,00223 | 4,008 |
| 2 | 16.000 | **0,091** | 0,00361 | 4,001 |
| 3 | 24.000 | 0,125 | 0,00465 | 3,971 |
| 4 | 32.000 | 0,104 | 0,00550 | 3,993 |

El crítico baja su error un **97 % en una sola actualización** y entra en meseta
(0,06–0,13) a partir de la segunda. Verificado dos veces con la misma semilla:
mismo patrón (2,910 y 3,478 en la primera iteración, meseta idéntica después).

**Punto elegido: 32.000 muestras (4 iteraciones).** Criterio cruzado: `vf_loss`
ya en su meseta desde la it 2 (se dan 4 para no depender de una sola
actualización) · deriva de solo 0,0055 · entropía estable · KL ~1e−10 · clip 0 ·
gradientes y parámetros finitos en todas.

`vf_loss` es dependiente de escala, así que **no comparo su valor absoluto entre
recompensas**; lo que comparo es la caída relativa.

### 13.4 C0 definitivo

| | |
|---|---|
| Ruta | `%LOCALAPPDATA%\rlgym-selfplay-pool\runs\C0_v2_stage1\` |
| Recompensa | **stage_1_basics** |
| `cumulative_timesteps` | **32.000** |
| `cumulative_model_updates` | 4 |
| Completo | sí (política + crítico + 2 optimizadores + book keeping) |
| `reward_running_stats` | presente |
| SHA256 de `PPO_POLICY.pt` | `2144e0e0e1f1df75e4a1c1b9a2270bdc56a9e80a…` |

Hashes completos en `runs/C0_v2-hashes.json`. **Recuperación verificada**: los
brazos A y B lo cargaron en procesos nuevos y arrancaron ambos en 32.000.

El C0 anterior se conserva en `runs/C0\` como registro histórico, marcado como
**no válido para el experimento**.

### 13.5 K = 40.000 — decisión de diseño

Elegido por diseño y coste, **no** por resultados de juego.

| K | Instantáneas con 250k / 500k / 1M | Disco a 500k | Deriva entre consecutivas |
|---|---|---|---|
| 8.000 | 31 / 63 / 125 | ~149 MB | ~0,0003 |
| **40.000** | **6 / 12 / 25** | **~30 MB** | **~0,0015** |
| 80.000 | 3 / 6 / 12 | ~15 MB | ~0,0030 |

La deriva sale de lo medido: relativa de 0,00223 (it1) a 0,01087 (it16), es decir
~0,009 en 128.000 muestras y creciendo de forma sublineal.

**Por qué 40.000:**

- **8.000 produce clones.** 63 instantáneas separadas por 0,0003 de deriva son
  casi la misma política repetida. La diversidad sería aparente, y solo añadiría
  disco y recargas.
- **80.000 deja el pool demasiado pequeño**: 6 rivales con el presupuesto
  recomendado es poco margen para que el muestreo signifique algo.
- **40.000 da 12 rivales distinguibles** con el presupuesto recomendado, ~30 MB
  de disco y un cambio de rival poco frecuente, que mantiene despreciable el
  coste de recarga que medimos en §12.7.

**Idéntico para A y B**, como exige el diseño.

### 13.6 Retención — política congelable

| | Brazo A | Brazo B |
|---|---|---|
| Retención | **1** | **16** |
| Protegidas | ninguna | **C0** |

- **C0 nunca se expulsa** en B: es el punto del que partieron los dos brazos y
  por tanto el ancla de la comparación.
- **Regla de expulsión, determinista y fijada de antemano:** si se supera la
  retención, se expulsa la **más antigua no protegida**, y se repite hasta caber.
- **Muestreo uniforme** entre las elegibles.
- Con el presupuesto recomendado (12 instantáneas + C0 = 13 < 16) la expulsión
  **no llega a activarse**; la regla existe para el presupuesto máximo (25 + C0).
- **Nada de Elo, recencia ponderada ni matchmaking adaptativo.**
- El brazo A usa la misma infraestructura con retención 1 y sin protegidas:
  exactamente el mecanismo ya validado.

### 13.7 Presupuesto

Rendimiento **medido** con `stage_1_basics`: **1.194 muestras/s** (2 trabajadores,
1 hilo). Lo medido de forma sostenida son 2,5 minutos; **todo lo que exceda eso
es una estimación, no una medición.**

| | Muestras/ejec. | Actualiz. | Instantáneas (K=40k) | Por ejecución | 6 ejecuciones |
|---|---|---|---|---|---|
| Pequeño | 250.000 | 31 | 6 | ~3,5 min *(est.)* | ~21 min *(est.)* |
| **Recomendado** | **500.000** | **62** | **12** | **~7 min** *(est.)* | **~42 min** *(est.)* |
| Máximo razonable | 1.000.000 | 125 | 25 | ~14 min *(est.)* | ~84 min *(est.)* |

**Elegido: 500.000 muestras por ejecución.** Es el mínimo con posibilidades
razonables de que H1 sea detectable: 12 rivales distinguibles en el pool y
suficiente cambio de política para que «contra quién entrenas» pueda importar.
Con 250.000 el pool tendría 6 rivales muy próximos entre sí.

No se intenta reproducir los miles de millones de pasos de los autores
originales: nuestro alcance es otro.

### 13.8 Semillas

**20260907, 20260908, 20260909.** Emparejadas: A₁/B₁ comparten semilla, y así las
tres. Fijadas **antes** de entrenar y guardadas en el protocolo. La semilla
controla la inicialización de torch y numpy y **el muestreo del pool**
(`(semilla, episodio)`).

**No determinismo que permanece**, declarado:

- el orden de llegada de la experiencia de los trabajadores es asíncrono;
- las reducciones en coma flotante de torch en CPU no son bit a bit reproducibles;
- la planificación del sistema operativo entre procesos.

### 13.9 Protocolo de evaluación — congelado, no ejecutado

- **Rivales finales:** `martin_2.1B_1024` (obs 107), `nachi_2.9B` (obs 107),
  `marco_2.0B_1024` (obs 89). Hashes en el protocolo. **No se usan para ninguna
  decisión** sobre recompensa, K, retención, presupuesto ni checkpoints.
- **Qué se evalúa:** el **checkpoint final** de cada ejecución. Sin regla de
  selección: no se elige el mejor mirando ningún conjunto, ni el de desarrollo.
- **40 partidas por rival y ejecución** → 6 × 3 × 40 = **720 partidas**.
- Semillas de partida 5000–5039 por rival, lista fija.
- Lados alternados por índice; **modo estocástico** como único modo primario.
- **Reglas:** gol → victoria/derrota · agotar el tiempo → empate · cualquier otra
  terminación → **incompleta**, excluida de las tasas y reportada aparte. **Una
  partida incompleta no es un empate.** **Sin desempate administrativo**: nada de
  resolver por timesteps ni por siembra.
- **Incertidumbre:** bootstrap 95 % sobre las partidas (10.000 remuestreos) y
  media ± rango entre las 3 semillas.
- Si hiciera falta evaluar durante el entrenamiento, se usa **solo** el conjunto
  de desarrollo.

### 13.10 Criterio de H1, escrito antes de entrenar

**Evidencia a favor** — los cuatro a la vez:

1. el IC bootstrap 95 % de la diferencia B−A **excluye el 0**;
2. la magnitud supera el **rango entre semillas** de ambos brazos;
3. el signo es consistente en **≥ 2 de 3 semillas**;
4. el signo es consistente en **≥ 2 de 3 rivales**.

**Evidencia en contra:** los mismos cuatro con el signo invertido.

**Inconcluyente:** el IC incluye el 0, o la diferencia es menor que el rango
entre semillas, o el signo no es consistente.

**Prohibido:** reducir H1 a «B tiene un porcentaje mayor que A»; usar la
recompensa de entrenamiento como prueba de calidad de juego; presentar como
mejora robusta una diferencia menor que la variabilidad entre semillas.

### 13.11 Deuda técnica: torch.load

`rlgym_ppo/ppo/ppo_learner.py::load_from` usa `torch.load(...)` **sin**
`weights_only=True`. Riesgo bajo en este experimento porque solo se le pasan
checkpoints generados localmente por nosotros. Reglas que quedan fijadas:

- **no** usar esa ruta con checkpoints externos;
- **no** relajar la carga de artefactos ajenos (siempre `weights_only=True` en
  nuestro código);
- **no** modificar `rlgym-ppo` en esta fase solo por esto.

### 13.12 Protocolo congelado

```
configs/experimento/protocolo.json
SHA256: 8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e
```

Contiene recompensa, C0 y hashes, arquitectura, K, retención, muestreo,
presupuesto, semillas, trabajadores/hilos, PPO, observaciones, acciones, reglas
del entorno, evaluación de desarrollo, evaluación final, criterio de H1, y los
SHA de código y dependencias.

**Desde aquí, cualquier cambio metodológico es una DESVIACIÓN** y debe quedar
registrada como tal, no hacerse en silencio.

---

## 14. Ejecucion del experimento y resultado (sexta sesion, 07/09/2026)

Las seis corridas se ejecutaron conforme al protocolo congelado
`8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e`, y la
evaluacion final se ejecuto **una sola vez**.

### 14.1 Integridad, verificada en ciego

Antes de tocar los rivales finales se genero la tabla ciega de integridad
(`scripts/integrity_table.py`, salida en `experimento/integridad.json`).

| Corrida | Brazo | Semilla | Muestras | Actualiz. | Instant. | Recuperacion |
|---|---|---|---|---|---|---|
| A1 | A | 20260907 | 504.000 | 63 | 1 | OK |
| B1 | B | 20260907 | 504.000 | 63 | 13 | OK |
| A2 | A | 20260908 | 504.000 | 63 | 1 | OK |
| B2 | B | 20260908 | 504.000 | 63 | 13 | OK |
| A3 | A | 20260909 | 504.000 | 63 | 1 | OK |
| B3 | B | 20260909 | 504.000 | 63 | 13 | OK |

Mismo C0 en las seis y C0 intacto al terminar; mismo presupuesto exacto;
parametros finitos; hashes de instantaneas correctos; retencion respetada; seis
checkpoints finales distintos entre si y de C0; cada uno recuperable en un
proceso nuevo con `weights_only=True`. **Integridad SUPERADA.**

### 14.2 Resultado

720 partidas, todas terminadas en gol. Cero empates y cero incompletas. Lados
balanceados 360/360.

| Brazo | Victorias | Tasa |
|---|---|---|
| A (rival unico) | 18 / 360 | 5,00 % |
| B (pool) | 15 / 360 | 4,17 % |

**B - A = -0,83 pp**, IC bootstrap 95 % **[-3,89 pp, +2,22 pp]**. El intervalo
contiene el cero, y la diferencia es menor que el rango entre semillas dentro de
un mismo brazo (2,5 pp en A, 1,7 pp en B).

De los cuatro criterios congelados se cumplen dos (consistencia de signo en 2 de
3 semillas y en 2 de 3 rivales) y fallan los dos que miden si la diferencia es
real (el IC no excluye el cero; la magnitud no supera el ruido entre semillas).

# H1 queda INCONCLUYENTE.

No se puede afirmar que el pool mejore la tasa de victoria, ni que la empeore.

### 14.3 Por que: efecto suelo

Ambos brazos ganan alrededor del 5 %. Los rivales de evaluacion se entrenaron
con 2.000 a 2.900 millones de pasos; nuestros agentes con 504.000 muestras, unas
cuatro mil veces menos. Con ambos brazos pegados al suelo, la metrica no tiene
resolucion para separarlos: lo que se observa es sobre todo la varianza de un
suceso raro. El diseno no falla; falta potencia estadistica, y eso lo fijaba el
presupuesto desde el principio.

### 14.4 Incidencias

Cuatro, todas de infraestructura y ninguna metodologica, detalladas en
`docs/experiments/incidencias.md`. La seria: un interbloqueo entre B1 y A2 por
un fallo de `cleanup()` de `rlgym_ppo` en Windows (`WinError 10038`) que dejo
estado de sockets corrupto para la corrida siguiente. Se descarto la carpeta de
A2 (solo contenia el pool sembrado con C0) y se relanzaron A2, B2, A3 y B3 en
procesos independientes desde el mismo C0. A1 y B1 no se tocaron.

La evaluacion final se interrumpio en la partida 389 y se reanudo saltando las
ya registradas: ninguna partida se jugo dos veces ni se descarto.

**Correccion a las secciones anteriores:** las trazas `WinError 10038` que
aparecen al cerrar cada corrida se describieron como inofensivas tras observarlas
en A1. Lo son para la corrida que termina, que ya guardo su informe; **no** para
la siguiente del mismo proceso.

### 14.5 Documento completo

`docs/experiments/resultados-finales.md`: pregunta, protocolo, ejecucion,
resultados, incertidumbre, conclusion, limitaciones y desviaciones.

## 15. Puerta de H2 y diagnostico de recompensa (septima sesion, 08/09/2026)

**H1 no se toca. Sigue cerrado como INCONCLUYENTE.**

### 15.1 H2: puerta GO/NO-GO -> NO-GO

Se ejecuto la fase 0 (linaje neutral de 4 M, piloto de 2,5 M, calibracion de
240 partidas). Resultado: G1 CUMPLE (4 escalones en zona 35-65 %), G4 CUMPLE
(infraestructura estable), **G2 FALLA** (deriva 0,0310 frente a 0,0465 exigido)
y **G3 FALLA** (diversidad 0,0135 frente a 0,0148). Las diez corridas no se
ejecutaron y no se congelo ningun protocolo H2.

Error de diseno detectado: extrapole la deriva en linea recta. Crece como
**raiz cuadrada** del presupuesto, confirmado punto por punto por el linaje
neutral. Detalle en `docs/experiments/h2/puerta-go-no-go.md`.

### 15.2 Diagnostico de recompensa -> ninguna configuracion prometedora

Tres configuraciones, 500.000 muestras cada una, misma semilla y mismo rival C0
fijo, evaluadas con 200 partidas por checkpoint contra C0:

| Config | Recompensa | ZeroSum | 100k | 250k | 500k | Veredicto |
|---|---|---|---|---|---|---|
| D_A | stage_1_basics | si | 72,0 % | 67,5 % | 61,5 % | NO PROMETEDORA |
| D_B | stage_2_offense | si | 14,0 % | 37,5 % | 22,5 % | NO PROMETEDORA |
| D_C | stage_2_offense | no | 56,5 % | 52,5 % | 16,0 % | NO PROMETEDORA |

**Las tres empeoran con mas entrenamiento.** D_A falla por 0,5 puntos el
criterio de deterioro, pero su caida de 10,5 puntos son 2,2 errores tipicos:
es real.

Diagnostico: los terminos moldeados se cobran en cada paso y el gol una sola
vez, asi que el moldeado domina en un orden de magnitud. `stage_2_offense`
duplica el peso moldeado y es drasticamente peor pese a llevar mas peso nominal
de gol.

ZeroSum **no puede aislarse** con esta prueba: su efecto cambia de signo entre
presupuestos. No es el factor dominante; lo son los componentes.

### 15.3 Correccion a lo dicho en la puerta de H2

Escribi que los cinco agentes entrenados perdian contra C0. Aquellos duelos
tenian 40 partidas. Con 200, `stage_1_basics` a 500k **gana el 61,5 %**. La
afirmacion absoluta era demasiado fuerte para la evidencia. La **direccion**
(degradacion al crecer el presupuesto) si se confirma, y es lo que importaba
para la decision. El NO-GO se apoya en G2 y G3, que no dependen de esto.

### 15.4 Estado

H2 sigue en NO-GO. Recomendacion: **cambiar la formulacion del objetivo** y
probar dos configuraciones con el moldeado reducido, con criterio congelado de
antemano. Si tampoco superan el 50 % con tendencia no decreciente, cerrar la
linea experimental. Detalle en `docs/experiments/reward-diagnostic/analisis.md`.

## 16. Comprobacion final de recompensa y CIERRE de la linea experimental (08/09/2026)

Protocolo congelado antes de entrenar:
**SHA256 6c2a8cb2001bf9f732043f3fa8eb6ebef92fd87531dc10a1238e3c99131a000d**

Dos configuraciones derivadas literalmente de `stage_1_basics`: **R1** con los
tres terminos moldeados densos divididos por 10 y `event` intacto, y **R2** con
solo `event`. 500.000 muestras cada una, misma semilla 20260951, rival C0 fijo,
200 partidas por checkpoint contra C0 con semillas nuevas 13000-13199.

| Config | 100k | 250k | 500k | IC95 a 500k | Veredicto |
|---|---|---|---|---|---|
| R1 shaping reducido | 9,5 % | 4,5 % | **2,0 %** | [0,8 %, 5,0 %] | NO PROMETEDORA |
| R2 solo evento | 11,5 % | 2,0 % | **2,5 %** | [1,1 %, 5,7 %] | NO PROMETEDORA |

### 16.1 La hipotesis quedo falsada

Yo habia predicho que reducir el moldeado mejoraria el resultado, porque los
terminos densos dominaban al de gol en un orden de magnitud. Pasa lo contrario:

| Configuracion | Moldeado | Tasa a 500k |
|---|---|---|
| D_A stage_1_basics | completo | **61,5 %** |
| D_B stage_2_offense | rebalanceado | 22,5 % |
| D_C stage_2_offense sin ZeroSum | igual que D_B | 16,0 % |
| R1 | dividido por 10 | **2,0 %** |
| R2 | eliminado | **2,5 %** |

Cuanto menos moldeado, peor. Con `event` como unica senal el aprendizaje se
queda sin gradiente util: los goles son raros y la politica deriva sin rumbo.
El moldeado denso no era el problema, era lo unico que sostenia el aprendizaje.
Confundi "que termino domina la suma" con "que termino aporta senal
aprovechable".

### 16.2 Que queda en pie

Se mantiene, con mas evidencia: **entrenar mas deteriora la tasa de victoria
frente a C0 en las cinco configuraciones probadas**. Se cae mi explicacion de
ese deterioro. La causa sigue **sin identificar**; esta prueba solo acota lo que
NO es: ni exceso de moldeado, ni la envoltura ZeroSum, ni inestabilidad
numerica, ni sobreajuste al rival (rival de entrenamiento y de evaluacion son el
mismo C0).

### 16.3 Cierre

**Linea experimental de recompensas CERRADA**, conforme a lo acordado antes de
ejecutar. No habra R3, ni H3, ni vuelta a H2, ni mas pruebas de pesos.

El proyecto cierra como: infraestructura reproducible, pool historico
implementado y ejercitado, protocolo experimental con criterios congelados por
SHA256 y respetados aun cuando el resultado fue incomodo, H1 inconcluyente, H2
detenido por puerta NO-GO, y un diagnostico de reward shaping con hipotesis
propia formulada y falsada por los datos.

Detalle en `docs/experiments/reward-final-check/analisis.md`.

## 17. LINEA EXPERIMENTAL CERRADA (08/09/2026)

**No se haran mas experimentos sin abrir una linea nueva explicita.**

### 17.1 Registro de cierre

| Fase | Resultado |
|---|---|
| **H1** (pool frente a rival unico) | **INCONCLUYENTE**. B-A = -0,83 pp, IC95 [-3,89, +2,22]. La diferencia esta dentro de la incertidumbre: ni A fue mejor ni B fue peor |
| **Puerta H2** | **NO-GO**. G1 y G4 cumplen; G2 (deriva 0,0310 < 0,0465) y G3 (diversidad 0,0135 < 0,0148) fallan. Las diez corridas NO se ejecutaron |
| **Diagnostico de recompensas** | D_A 61,5 %, D_B 22,5 %, D_C 16,0 % a 500k. Ninguna PROMETEDORA |
| **Prueba final** | **R1 2,0 % y R2 2,5 % a 500k. NO PROMETEDORAS.** Hipotesis del exceso de shaping **FALSADA** |
| **Causa del deterioro** | **NO IDENTIFICADA.** Solo se sabe que no es exceso de moldeado, ni ZeroSum, ni inestabilidad numerica, ni sobreajuste al rival |

### 17.2 Estado operativo

Sin procesos en ejecucion: ni entrenamiento, ni evaluacion, ni benchmark. Los
dos monitores auxiliares (`tail -f` sobre logs) se cerraron, y tambien los dos
procesos `tail.exe` que quedaron huerfanos. Cero procesos python vivos.

### 17.3 Documentacion de cierre

| Documento | Contenido |
|---|---|
| `docs/FINAL_REPORT.md` | informe tecnico autocontenido, 18 secciones |
| `docs/CONTRIBUTIONS.md` | heredado / modificado / creado, con evidencia |
| `docs/REPRODUCE.md` | que se reproduce, que necesita artefactos, que no se redistribuye |
| `docs/CLEANUP_PLAN.md` | conservar / archivar / candidato a eliminar. **Nada borrado** |
| `docs/PORTFOLIO_DRAFT.md` | borrador de presentacion. **El portfolio no se ha tocado** |
| `README_PROYECTO.md` | README del proyecto derivado. El heredado `README.md` queda intacto |

### 17.4 Volumen final, medido sobre artefactos

15 entrenamientos con informe, 12.112.000 muestras, 3,00 h de computo
registrado, 3.960 partidas evaluadas en JSONL, 3 protocolos congelados por
SHA256, 5.401 lineas de codigo propio en 24 archivos y 3.038 lineas de
documentacion propia. **Cero archivos heredados modificados.**

Las 3.960 partidas son magnitud de ingenieria, no una muestra estadistica: son
protocolos distintos y no deben agregarse en una tasa conjunta.

### 17.5 Lo que queda prohibido sin nueva autorizacion

R3, H3, volver a H2, nuevas recompensas, nuevos entrenamientos, nuevas busquedas
de hiperparametros, y reanalizar H1 buscando un corte favorable.

## 10. Siguiente paso recomendado

**LINEA EXPERIMENTAL CERRADA (§17).** No queda trabajo de computo.

Lo unico pendiente es de decision: aprobar el plan de limpieza
(`docs/CLEANUP_PLAN.md`) y decidir si se pasa a fase de publicacion.

Sigue **sin autorizar**: commits, push, GitHub publico, portfolio, CV, LinkedIn,
publicacion de modelos y de mallas.
