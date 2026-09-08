# Autojuego con memoria — plan experimental

Proyecto: `rlgym-selfplay-pool`. Base: `moanv2/rlgym` (MIT, ver `UPSTREAM.md`).
Última revisión: **2026-09-07**, al cerrar la fase 0.

---

## 1. Hipótesis H1

> **H1.** Un agente PPO de Rocket League 1v1 que entrena contra **una mezcla de
> versiones congeladas anteriores de sí mismo** (un *pool* de oponentes) obtiene
> una **tasa de victorias mayor frente a un conjunto de rivales reservados** que
> un agente idéntico entrenado contra **una única copia congelada de su versión
> actual**, cuando ambos parten del mismo checkpoint, consumen el mismo número
> de muestras de aprendizaje y comparten el resto de la configuración.

**Variable independiente:** de qué política proceden las acciones del rival
durante el entrenamiento — versión actual congelada (control) frente a
distribución sobre instantáneas pasadas (variante).

**Variable dependiente:** tasa de victorias contra los rivales de evaluación
reservados, con intervalo de confianza.

**Por qué es plausible:** el autojuego contra la versión actual puede caer en
ciclos y olvido — la política se sobreajusta a su yo presente y pierde contra
versiones anteriores. Mantener oponentes históricos es la mitigación estándar
(la idea detrás de los pools de AlphaStar y OpenAI Five).

**Qué NO afirma:** no afirma que vayamos a superar a ningún bot del proyecto
original. No afirma que el efecto exista en este régimen de cómputo. Es una
hipótesis que puede salir negativa o inconcluyente, y las tres salidas son
resultados publicables.

**Tres desenlaces, y se distinguen:**

| Desenlace | Criterio |
|---|---|
| **Mejora** | El intervalo de confianza de la diferencia de tasas está por encima de 0 y la diferencia supera la dispersión entre semillas |
| **Empeoramiento** | El intervalo está por debajo de 0 en las mismas condiciones |
| **Inconcluyente** | El intervalo cruza el 0, o la diferencia no supera la dispersión entre semillas |

Un resultado inconcluyente es **falta de evidencia de mejora**, no prueba de que
el método no funcione. No se convertirá una cosa en la otra.

---

## 2. Contabilidad del cómputo — corregido

La primera versión de este plan afirmaba que cambiar el rival *"no cuesta más
cómputo"*. **Esa afirmación se retira: era una suposición sin medir.** Lo que sí
se ha comprobado, leyendo el código de `rlgym-ppo` en el SHA fijado:

En `rlgym_ppo/batched_agents/batched_agent_manager.py`, `n_collected = prev_n_agents`
(línea 318) y `cumulative_timesteps += n_collected` (línea 155). Es decir:

> **Un «timestep» de rlgym-ppo es una muestra de agente, no un paso de entorno
> ni un tick de física.**

Con `team_size=1, spawn_opponents=True` (1v1) y `tick_skip=8` a 120 Hz:

| Magnitud | Autojuego actual (los dos coches aprenden) | Rival congelado (solo aprende el azul) |
|---|---|---|
| Muestras de aprendizaje por paso de entorno | 2 | 1 |
| Pasos de entorno por 1M de muestras | 500.000 | 1.000.000 |
| Ticks de física por 1M de muestras | 4.000.000 | 8.000.000 |

Es decir: **a igualdad de «timesteps», el brazo con rival congelado necesita el
doble de simulación**, y por tanto más tiempo real.

Medido ya en un proceso (07/09/2026): simular cuesta 5.666 pasos/s con acciones
aleatorias, pero **523 pasos/s con la política decidiendo en los dos coches**. La
inferencia domina sobre el simulador, así que «el doble de simulación» **no**
equivale a «el doble de tiempo»: hay que medir el escalado con varios
trabajadores antes de traducirlo a coste real. Ese es el objetivo de la fase 3.

### Cómo aislamos el efecto que queremos estudiar

Si el control fuera «autojuego normal» y la variante «pool de oponentes», los dos
brazos se diferenciarían en **dos** cosas a la vez: quién es el rival **y** quién
aporta experiencia. Eso confundiría el experimento.

**Decisión de diseño:** en los dos brazos aprende **solo el coche azul**, y el
naranja es siempre una política **congelada**. Lo único que cambia es de dónde
sale esa política congelada:

| | Brazo A — control | Brazo B — variante |
|---|---|---|
| Aprende | solo el azul | solo el azul |
| Rival | copia congelada de la **política actual**, refrescada cada *K* pasos | política muestreada de un **pool** de instantáneas pasadas |
| Muestras de aprendizaje por paso de entorno | 1 | 1 |
| Coste de simulación por muestra | igual | igual |

Así los dos brazos tienen contabilidad idéntica y el único factor que varía es la
**identidad del rival**, que es exactamente H1. El coste extra frente al
autojuego original lo pagan los dos por igual.

### Presupuesto que se iguala

- **Principal:** muestras de aprendizaje (`cumulative_timesteps`). Es lo que
  determina cuántas actualizaciones ve PPO.
- **Se registran además, sin igualarse:** pasos de entorno, ticks simulados,
  actualizaciones del modelo, tiempo real de pared, memoria máxima.
- **Diferencia residual, ya medida (07/09/2026):** el brazo B carga políticas
  distintas a lo largo del entrenamiento. **Medido en el smoke A/B: el coste
  extra queda en +-1 %, dentro del ruido** (A: 1.259 muestras/s, B: 1.268). Con
  caché por instantánea en cada trabajador, volver a un rival ya visto no cuesta
  lectura de disco.
  **Dos matices**: se midió con 6 instantáneas —con un pool mucho mayor habría
  que repetirlo— y las estadísticas de carga viven en los trabajadores, así que
  la comparación se hizo con los tiempos globales del proceso principal.

---

## 3. Modelos de partida — comprobado, no supuesto

Comprobado con `scripts/preflight.py` sobre los checkpoints reales:

| Checkpoint | obs | Arquitectura | Archivos | Qué permite |
|---|---|---|---|---|
| `diego_1.18B_512` | 89 | 512×3 | política + book keeping | **solo inferencia o init de pesos** |
| `martin_2.1B_1024` | 107 | 1024×3 | política + book keeping | **solo inferencia o init de pesos** |
| `marco_2.0B_1024` | 89 | 1024×3 | política + **crítico** + **2 optimizadores** + book keeping | **reanudar entrenamiento** |
| `nachi_2.9B` | 107 | 1024×3 | política + **crítico** + **2 optimizadores** + book keeping | **reanudar entrenamiento** |

**Consecuencia que cambia el plan anterior.** Se había propuesto partir del
checkpoint de 512 de Diego por ser el más barato en CPU. Pero **es solo política**:
no trae crítico ni optimizadores. Arrancar PPO desde ahí significa:

- crítico **reinicializado al azar** → las ventajas de las primeras
  actualizaciones son ruido, y pueden degradar una política ya entrenada;
- estados de Adam **reinicializados** → los primeros pasos son más bruscos;
- `standardize_returns: true` en su configuración, y la estadística de
  recompensa sí viene en `BOOK_KEEPING_VARS.json`, así que esa sí se puede
  restaurar.

Eso **no invalida** el experimento si ambos brazos parten exactamente igual, pero
gasta presupuesto en recuperar el crítico y añade varianza. **Que coincidan las
dimensiones no basta para dar por equivalente el comportamiento.**

**Opciones de punto de partida, a decidir en la fase 1:**

| Opción | Ventaja | Coste |
|---|---|---|
| **P1** — `marco_2.0B_1024`, reanudación completa | condiciones limpias: crítico y optimizadores reales | 1024×3 es la arquitectura más cara en CPU; y Marco deja de poder ser rival reservado |
| **P2** — `diego_1.18B_512`, solo pesos, crítico nuevo en ambos brazos | red 3,7× más pequeña; deja libres a los cuatro rivales | hay que gastar una fase de calentamiento del crítico, idéntica en los dos brazos, antes de bifurcar |
| **P3** — desde cero, red pequeña | sin dependencia de pesos ajenos | en este hardware el nivel sería tan bajo que la diferencia probablemente no se detecte |

**Elegida: P2, y el calentamiento ya está medido.** C0 = 80.000 muestras desde
`diego_1.18B_512`, punto en que el crítico pasa a estar calibrado en nivel
(razón valores/retornos = 1,03) con una deriva de política de solo 0,0089.
El criterio, y el instrumento que descarté por circular, están en
`ESTADO_PROYECTO.md` §12.

Lo que sigue es el razonamiento previo, que se conserva: **Sigue siendo provisional**
tras la sesión del 07/09: se comprobó ejecutándolo que arrancar desde los pesos
de Diego con crítico aleatorio **degrada** la política al principio —24.000
muestras bastaron para que perdiera 5 de 6 partidas decisivas contra el propio
artefacto de partida—. Eso no invalida P2, pero confirma que el calentamiento
del crítico es obligatorio y que hay que medir cuánto dura antes de bifurcar.

**Confirmado por medición:** 2 trabajadores es la configuración de trabajo en
esta máquina (1.146 muestras/s frente a 854 con uno y 915 con cuatro).

**Carga de pesos:** siempre `torch.load(..., weights_only=True)`. Nunca
deserialización arbitraria para forzar que un archivo ajeno cargue.

---

## 4. Evaluación

### Rivales reservados

`martin_2.1B_1024` (obs 107) y, según el punto de partida elegido, los que no se
usen como origen. Que sean de otros autores **no garantiza** que no compartan
linaje con nuestro punto de partida: son bots del mismo curso, entrenados con la
misma base y posiblemente entre ellos.

**Por tanto la afirmación se limita a lo verificable:**

> Los rivales de evaluación **no se usan en nuestro entrenamiento ni en la
> selección de variantes**. No se afirma que sean rivales «nunca vistos» por el
> linaje del checkpoint de partida, porque su historial de entrenamiento previo
> no se puede verificar desde aquí.

Lo que sí sabemos, de sus `BOOK_KEEPING_VARS.json`: pasos acumulados,
arquitectura y, cuando está, la configuración de entrenamiento. Se registrará.

### Protocolo

- **N partidas por emparejamiento**, lados **intercambiados cada partida**.
- **Lista de semillas fijada de antemano** y registrada.
- **Reglas:** gol = victoria del que marca; agotar el tiempo = empate. Se
  reportan dos tasas: sobre todas las partidas y solo sobre las decisivas.
- **Determinista y estocástico se reportan por separado**, nunca agregados.
- Se reutiliza el arnés que ya existe en la base (`tournament/match.py` ya
  intercambia lados; `tournament/obs.py` ya enruta observaciones distintas por
  lado). **No se reconstruye la evaluación desde cero.**

### Registro de resultados

Una línea por partida en JSONL, con: rival, lado, semilla, resultado, diferencia
de goles, pasos del episodio, **SHA256 de los dos modelos**, SHA del código y
hash de la configuración. Más un `results.json` de resumen. **Nada escrito a mano.**

### Incertidumbre

- Intervalo del **95 % por bootstrap** sobre las partidas.
- **Tres semillas de entrenamiento por brazo**; se reporta la media y la
  dispersión entre semillas.
- Una diferencia menor que la dispersión entre semillas **no** se presenta como
  mejora.

### Desarrollo frente a evaluación final

Durante el desarrollo se usa un subconjunto de rivales y semillas. Cuando el
protocolo se congela, la evaluación final se ejecuta **una sola vez** con los
rivales y semillas reservados. **No se elige la mejor variante y se presentan
esas mismas partidas como evaluación independiente.**

### Lo que no cuenta como prueba

La recompensa de entrenamiento **no** vale como evidencia de que juega mejor: es
la magnitud que el propio entrenamiento optimiza, y los dos brazos ven
distribuciones de rival distintas, así que ni siquiera es comparable entre ellos.
Solo cuenta la tasa de victorias contra los rivales reservados.

---

## 5. Fases y criterios de aceptación

| Fase | Contenido | Criterio de aceptación | Estado |
|---|---|---|---|
| **0 · Preparación y viabilidad** | Clonar con procedencia, entorno aislado, `preflight.py`, comprobar artefactos y recursos | Informe de viabilidad reproducible que distinga OK / FALLO / NO EJECUTADO, y decisión razonada de continuar o replantear | **COMPLETADA** — 22 OK, 0 FALLO, 0 NO EJECUTADO |
| **1 · Base ejecutable** | Ejecutar una evaluación entre dos checkpoints de desarrollo | Dos bots juegan headless y sale una tasa de victorias con su JSONL | **COMPLETADA** — 8 partidas, JSONL con hashes, totales cuadran |
| **2 · Ingeniería** | Perfil de CPU; resultados por partida con hashes; intervalos por bootstrap; arreglo del roster; `ImportError` explícito | La suite pasa; el roster funciona en un clon limpio; los resultados salen con hash e intervalo | Pendiente |
| **3 · Medición de presupuesto** | Medir por separado simulación, simulación + inferencia y actualización PPO | Cifra medida en esta máquina, con su límite de validez declarado | **COMPLETADA en parte** — 1.309 muestras/s sostenidas con 2 trabajadores durante 2,5 min; falta el comportamiento en sesiones de horas |
| **4 · Variante** | Pool histórico sobre el adaptador ya validado, + configuración de los dos brazos | Un entrenamiento corto corre en A y B sin caerse y produce checkpoints comparables | **COMPLETADA** — pool 17/17 en pruebas; smoke A y B de 40.000 muestras cada uno desde C0, contabilidad idéntica salvo la retención |
| **5 · Experimento** | 3 semillas × 2 brazos, 500.000 muestras cada uno | Los dos brazos completan el mismo número de muestras, con su registro de coste | **HECHO.** Las seis corridas gastaron 504.000 muestras exactas; integridad superada en ciego. Resultado: **H1 INCONCLUYENTE** |
| **6 · Evaluación final** | Protocolo congelado, rivales y semillas reservados, una sola pasada | Informe con tasas, intervalos y desenlace declarado — mejora, empeoramiento o inconcluyente | Pendiente |

Ninguna fase posterior a la 0 está autorizada todavía.

---

## 5 bis. Protocolo congelado (07/09/2026)

Las cuatro decisiones pendientes están tomadas y registradas en
`configs/experimento/protocolo.json` (SHA256 `8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e`):

| Decisión | Valor | Base |
|---|---|---|
| Recompensa | `stage_1_basics` (heredada) | `DefaultReward` no codifica la tarea: penaliza la velocidad angular |
| C0 | 32.000 muestras, stage_1_basics | `vf_loss` cae un 97 % en una actualización y entra en meseta |
| K | 40.000 | 8.000 produce clones; 80.000 deja el pool demasiado pequeño |
| Retención B | 16, con C0 protegido | expulsión determinista de la más antigua no protegida |
| Presupuesto | 500.000 × 6 | mínimo con 12 rivales distinguibles |
| Semillas | 20260907/08/09, emparejadas | fijadas antes de entrenar |

El criterio de H1 y el protocolo de evaluación final están escritos **antes** del
entrenamiento. Detalle en `ESTADO_PROYECTO.md` §13.

## 5 ter. Resultado (07/09/2026)

720 partidas. Brazo A (rival único) 18/360 = 5,00 %; brazo B (pool) 15/360 =
4,17 %. **B − A = −0,83 pp**, IC bootstrap 95 % **[−3,89 pp, +2,22 pp]**.

De los cuatro criterios congelados fallan los dos decisivos: el intervalo
incluye el cero y la magnitud no supera el rango entre semillas del mismo brazo.

# H1: INCONCLUYENTE

Causa dominante: **efecto suelo**. Ambos brazos ganan ~5 % contra rivales
entrenados con miles de veces más pasos, y a esa tasa base 720 partidas no dan
resolución para separar los brazos.

Detalle completo en `resultados-finales.md`; incidencias de ejecución en
`incidencias.md`.

## 6. Riesgos declarados

1. ~~**Bloqueo de las mallas de colisión.**~~ **RESUELTO el 07/09/2026** con la
   distribución oficial de RLGym, sin instalar Rocket League. Detalle y
   condiciones de uso en `UPSTREAM.md`.
2. **Presupuesto todavía desconocido.** Medido en un proceso: 5.666 pasos/s
   simulando, pero solo **523 pasos/s con la política decidiendo** — la
   inferencia domina. Falta medir el escalado con varios trabajadores, que es
   donde rlgym-ppo agrupa las inferencias. Hasta tener esa cifra no se fija el
   presupuesto. Si sale demasiado baja, se reduce el alcance.
3. **Efecto posiblemente indetectable** con un presupuesto de portátil. Es el
   riesgo científico principal; se documentaría como inconcluyente.
4. **Linaje de los rivales no verificable**, ya tratado arriba limitando la
   afirmación.
5. **Coste extra del brazo B** por cambiar de política rival: se medirá, no se
   supondrá despreciable.
6. **Cada trabajador tendrá que inicializar RocketSim por su cuenta.** En
   Windows el proceso hijo no hereda `rsim.init()` (comprobado). El sitio para
   hacerlo es `_EnvBuilder.__call__` de la base, que ya corre en cada
   trabajador. Si se olvida, el entrenamiento aborta al arrancar los workers.
