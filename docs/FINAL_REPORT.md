# Informe técnico final

**Autojuego con memoria en Rocket League 1v1: un experimento con resultado negativo**

Proyecto derivado de [moanv2/rlgym](https://github.com/moanv2/rlgym) (MIT).
Fecha de cierre: 2026-09-08. Línea experimental **cerrada**.

Este documento es autocontenido: se puede entender sin leer los diarios de
sesión. Todo lo que afirma procede de artefactos en disco.

---

## 1. Resumen ejecutivo

Quise responder una pregunta concreta: **¿entrenar contra un conjunto de
versiones antiguas de uno mismo produce un agente mejor que entrenar contra una
sola copia congelada del yo reciente, con el mismo presupuesto de muestras?**

La respuesta honesta es: **no lo pude demostrar.** El experimento principal (H1)
quedó **inconcluyente**, y el intento de rehacerlo mejor (H2) se **detuvo en su
propia puerta de calidad** antes de gastar el cómputo. Al investigar por qué,
descubrí un problema más básico: **entrenar más deterioraba el juego** frente al
punto de partida. Formulé una explicación —exceso de *reward shaping*—, la puse
a prueba y **los datos la falsaron**.

Lo que sí queda es un sistema experimental que funciona: protocolos congelados
por SHA256 antes de ejecutar, criterios de decisión escritos de antemano y
respetados cuando el resultado fue incómodo, evaluación reproducible y
trazabilidad por hashes de cada checkpoint.

No hay bot mejorado. Hay un experimento que sabe decir que no.

---

## 2. Pregunta de investigación

**H1:** un agente entrenado contra una mezcla de instantáneas congeladas de sí
mismo (*opponent pool*) alcanza una tasa de victoria mayor, frente a rivales
reservados, que uno entrenado contra una única copia congelada de su yo actual,
**con idéntico presupuesto de muestras de aprendizaje**.

- **Brazo A (control):** rival único, sustituido cada K muestras.
- **Brazo B (tratamiento):** pool con retención 16 y C0 protegido; en cada
  episodio se muestrea un rival del pool.

Es la idea del *fictitious self-play*: entrenar contra la propia historia para
evitar ciclos y olvidos. La pregunta era si aporta algo medible a esta escala.

---

## 3. Base utilizada y atribución

| | |
|---|---|
| Upstream | `moanv2/rlgym`, commit base `0c6965acf3d0405227282a80b1881dbfde3ef56b` |
| Licencia | MIT, conservada |
| Qué aporta | entorno 1v1 sobre `rlgym_sim` + RocketSim, `LookupAction`, registro de recompensas, `ZeroSumReward`, arnés de torneo, scripts de entrenamiento por etapas |

**No modifiqué ni un solo archivo heredado.** Verificado con `git status`: cero
archivos modificados, 27 entradas nuevas sin seguimiento. La atribución vive en
`NOTICE` y `UPSTREAM.md`; el inventario exacto de autoría, en
`docs/CONTRIBUTIONS.md`.

Los checkpoints de referencia (Martin, Nachi, Marco, Diego) y las mallas de
colisión son material ajeno: **no se redistribuyen**.

---

## 4. Aportaciones propias

Resumen; el detalle con archivo, función, motivo y evidencia está en
`docs/CONTRIBUTIONS.md`.

| Área | Qué construí |
|---|---|
| Arranque | `preflight.py`, `rocketsim_init.py`: inicialización de RocketSim por proceso bajo `spawn` en Windows |
| Entrenamiento | `frozen_opponent.py`: adaptador que expone **un solo agente** al aprendiz, de modo que solo su experiencia llega a PPO |
| Pool | `opponent_pool.py`: instantáneas con manifiesto atómico, retención con protección de C0 y muestreo reproducible |
| Ejecución | `run_experiment.py`, `driver_h2.py`: una corrida por proceso, detección de estancamiento y de huérfanos, marcador COMPLETA/INCOMPLETA, reanudación idempotente |
| Evaluación | `eval_final.py`, `duel.py`, `eval_calib.py`: JSONL sin duplicados, reanudable, con hashes y semillas |
| Integridad | `integrity_table.py`: tabla ciega, recuperación de checkpoints en proceso nuevo |
| Análisis | `analyze_h1.py`, `gate_check.py`: criterios congelados, bootstrap, intervalos de Wilson |
| Protocolos | tres protocolos congelados por SHA256 antes de ejecutar |

**5.401 líneas de código propio en 24 archivos** y **3.038 líneas de
documentación propia**, sin contar lo heredado.

---

## 5. Arquitectura del sistema

```
C0 (punto de partida común, 32.000 muestras, hash fijado)
 │
 ├── ConstructorRivalCongelado ─── rival fijo         → linaje neutral
 ├── ConstructorPool ───────────── rival del pool     → brazos A (ret. 1) y B (ret. 16)
 │      └── PoolRivales: manifiesto atómico, retención, muestreo por semilla
 │
 ├── EntornoRivalCongelado: expone UN agente a rlgym-ppo
 │      (el rival actúa dentro de step(); su experiencia nunca entra en PPO)
 │
 ├── Learner de rlgym-ppo, 2 trabajadores, 1 hilo torch cada uno
 │      └── hook sobre learn(): instantáneas cada K, hitos, métricas
 │
 └── Evaluación: duel.py / eval_final.py → JSONL → analyze_h1.py / gate_check.py
```

Decisión central: **el aprendiz ve un entorno de un solo agente**. Sin eso,
rlgym-ppo trataría al rival como un segundo aprendiz y su experiencia
contaminaría las actualizaciones.

---

## 6. Reproducibilidad

- **Protocolos congelados por SHA256** y verificados al inicio de cada
  ejecución: si el archivo cambia, el script se niega a ejecutar.
- **Semillas fijadas por escrito antes de entrenar**, y semillas de partida
  disjuntas entre fases para no reutilizar evaluaciones.
- **Hashes** de C0, de cada instantánea, de cada hito y de cada checkpoint final.
- **Un proceso por corrida**, para no heredar estado entre ejecuciones.
- **Recuperación verificada**: cada checkpoint final se carga en un proceso
  nuevo con `weights_only=True` y debe producir una acción válida.
- **Entorno anclado**: `requirements/lock-2026-09-07.txt`.
- Todo el material pesado vive fuera del repositorio, en `%LOCALAPPDATA%`.

Detalle operativo en `docs/REPRODUCE.md`.

---

## 6 bis. Trazabilidad de los hashes de protocolo

Los protocolos se congelaron con su SHA256 **antes** de ejecutar cada
experimento: esa es la prueba de que el criterio de decisión no se tocó después
de ver los datos.

Los archivos originales contenían la **ruta local absoluta** de la máquina donde
se ejecutaron. Esa ruta se ha **redactado por privacidad** en esta copia
pública, lo que cambia los bytes y, por tanto, el hash.

| Experimento | SHA256 original histórico | SHA256 copia pública saneada | Motivo de la diferencia |
|---|---|---|---|
| H1 | `8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e` | `c6506d17ec164a39eef6bc2063d3fa9ab8e6c23e9a6d63889044c364a02aff30` | privacy redaction only |
| H2 fase 0 | `bfb3cb729dcb1be9fbae68f092b68b63ff9452177bcb2aa6056db84ab73115a6` | `4eca11b25352be355b89a2ca5236b40ffc1d1a1565db9e1f9f19438b043c05f2` | privacy redaction only |
| Diagnóstico de recompensas | `4bf33f06e0942c8b98b1849ce16907fba9c1035a64a195561759e66e71ce1e12` | `655adfc0abd749ff27bbd6fbdc44bddeafd802a51602f1a33b0066fc0f776608` | privacy redaction only |
| Prueba final R1/R2 | `6c2a8cb2001bf9f732043f3fa8eb6ebef92fd87531dc10a1238e3c99131a000d` | `2e69b352712131feef2ffebd84865a84a8b0cf229018099a6961ff89c744cd87` | privacy redaction only |

**Qué significa cada columna:**

- **Original histórico** — calculado antes de ejecutar. Es el hash de
  preregistro. El archivo con esos bytes exactos **no se publica** y se conserva
  intacto en el archivo privado de investigación.
- **Copia pública saneada** — mismo contenido metodológico, con la ruta personal
  sustituida por `%LOCALAPPDATA%`. Verificable contra los archivos de este
  repositorio.

**Qué NO cambió al sanear:** ningún parámetro experimental, semilla,
presupuesto, recompensa, criterio de decisión ni resultado. La comprobación se
hizo campo a campo sobre el JSON, no por confianza: la única diferencia
detectada fue la cadena de ruta.

**Sé preciso al citarlo:** el archivo público **no es byte a byte idéntico** al
que se ejecutó. La evidencia del preregistro es el registro histórico y sus
hashes documentados aquí, no el archivo publicado.

Cada protocolo lleva al lado sus dos hashes: `protocolo.sha256` (público,
verificable contra el archivo vecino) y `protocolo.original.sha256` (histórico,
con la nota de que no corresponde al archivo publicado).

---

## 7. Experimento H1

Protocolo `8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e`,
congelado antes de entrenar.

| | |
|---|---|
| Corridas | 6 = 3 semillas × 2 brazos, todas desde el mismo C0 |
| Presupuesto | 504.000 muestras exactas cada una, 63 actualizaciones |
| K | 40.000 · Retención A = 1, B = 16 con C0 protegido |
| Rivales finales | Martin (2,1 B pasos), Nachi (2,9 B), Marco (2,0 B) |
| Evaluación | 720 partidas = 6 × 3 × 40, semillas 5000–5039, lados alternados |

**Integridad, verificada en ciego** antes de tocar los rivales finales: mismo C0
e intacto, presupuesto idéntico al dígito, parámetros finitos, hashes de
instantáneas correctos, retención respetada, seis checkpoints finales distintos
entre sí y de C0, y todos recuperables en proceso nuevo. **SUPERADA.**

---

## 8. Resultado de H1

| Brazo | Victorias | Tasa |
|---|---|---|
| A (rival único) | 18 / 360 | **5,00 %** |
| B (pool) | 15 / 360 | **4,17 %** |

**B − A = −0,83 pp**, IC bootstrap 95 % **[−3,89 pp, +2,22 pp]**.

De los cuatro criterios congelados se cumplen dos (consistencia de signo) y
fallan los dos que miden si la diferencia es real: el intervalo incluye el cero,
y la magnitud (0,83 pp) es **menor que la variación entre semillas del mismo
brazo** (2,5 pp en A, 1,7 pp en B).

### Veredicto: INCONCLUYENTE

Conviene decir con precisión qué significa. **No** significa que A fuera mejor
que B, ni que el pool perjudique. La diferencia observada es indistinguible de
cero: cambiar la semilla mueve el resultado más que cambiar el método. Los 18
frente a 15 triunfos no son un resultado a favor de nadie.

Las 720 partidas terminaron en gol; cero empates y cero incompletas.

---

## 9. Diagnóstico posterior a H1

Tres hallazgos, medidos sobre los checkpoints que H1 dejó en disco:

1. **Efecto suelo.** Ambos brazos ganaban ~5 % contra rivales entrenados con
   2.000–2.900 millones de pasos, frente a nuestras 504.000 muestras. A esa tasa
   base, 720 partidas no tienen resolución para separar métodos.

2. **Las instantáneas eran casi idénticas.** Distancia entre pares dentro del
   pool de B: mediana 0,0074, máximo 0,0151. Las 13 «rivales distintas» estaban
   todas dentro del 1,5 % unas de otras. **El tratamiento apenas se diferenciaba
   del control.**

3. **La política se movió muy poco.** Tras 504.000 muestras, la distancia
   relativa a C0 era 0,0155, casi idéntica en las seis corridas (0,0153–0,0160).

El tercero explica el segundo, y juntos explican el primero mejor que la fuerza
de los rivales por sí sola: H1 no solo carecía de potencia estadística, es que
**la intervención que medía era muy débil**.

---

## 10. Diseño y puerta de H2

H2 se diseñó para corregir exactamente eso: rivales calibrados en dificultad
mediante un **linaje neutral de sparring** (entrenado contra C0 fijo, con una
semilla fuera del conjunto experimental), presupuesto mayor, K mayor, 5 semillas
y bootstrap jerárquico emparejado.

Antes de gastar las diez corridas se ejecutó una **puerta GO/NO-GO** con
umbrales escritos de antemano:

| | Criterio | Umbral | Medido | |
|---|---|---|---|---|
| G1 | ≥ 3 escalones con tasa del piloto en 35–65 % | 3 | **4** | CUMPLE |
| G2 | deriva del piloto ≥ 3× la de H1 | 0,0465 | **0,0310** | **FALLA** |
| G3 | diversidad del pool ≥ 2× la de H1 | 0,0148 | **0,0135** | **FALLA** |
| G4 | infraestructura estable | — | sin bloqueos ni huérfanos | CUMPLE |

### Veredicto: NO-GO. Las diez corridas no se ejecutaron.

G1 funcionó: el linaje neutral sí produjo rivales en zona informativa (los
cuatro escalones dejaban al piloto en 55 %).

G2 falló por un **error de diseño mío**: extrapolé la deriva en línea recta.
Crece como **raíz cuadrada** del presupuesto, confirmado punto por punto
(504k → 0,0156; 1M → 0,0223; 2M → 0,0305; 4M → 0,0403). Alcanzar el umbral
habría exigido ~6 millones de muestras por corrida: unas 12 horas para las diez.

**La puerta evitó gastar esas 12 horas en un experimento condenado.** Es el
episodio del que estoy más conforme.

---

## 11. Diagnóstico de recompensas

Durante la calibración apareció algo no previsto: el agente piloto perdía contra
**C0**, su propio punto de partida. Eso invalidaba la premisa de medir por tasa
de victoria, así que se investigó con tres configuraciones fijadas de antemano,
500.000 muestras cada una, misma semilla, rival C0 fijo, 200 partidas por
checkpoint:

| Config | Recompensa | ZeroSum | 100k | 250k | 500k | Veredicto |
|---|---|---|---|---|---|---|
| D_A | `stage_1_basics` (heredada) | sí | 72,0 % | 67,5 % | **61,5 %** | NO PROMETEDORA |
| D_B | `stage_2_offense` (heredada) | sí | 14,0 % | 37,5 % | 22,5 % | NO PROMETEDORA |
| D_C | `stage_2_offense` sin envoltura | no | 56,5 % | 52,5 % | 16,0 % | NO PROMETEDORA |

D_A supera el 50 % y su intervalo excluye el 50 %, pero **cae 10,5 puntos** de
100k a 500k: 2,2 errores típicos. Falló el criterio de deterioro por 0,5 puntos
porcentuales, y se aplicó tal como estaba escrito.

**Sobre ZeroSum:** su efecto cambia de signo entre presupuestos (+42,5 pp a
favor de la variante sin envoltura a 100k, −6,5 pp en contra a 500k). Con una
sola semilla **no puede aislarse**, y no es el factor dominante: lo son los
componentes.

---

## 12. Prueba final R1/R2

Protocolo `6c2a8cb2001bf9f732043f3fa8eb6ebef92fd87531dc10a1238e3c99131a000d`.

Hipótesis a contrastar: los términos moldeados se cobran en cada paso y el gol
una sola vez, así que el moldeado domina en un orden de magnitud; **reducirlo
debería mejorar el resultado**.

| Config | Moldeado | 100k | 250k | 500k | IC95 a 500k | Veredicto |
|---|---|---|---|---|---|---|
| R1 | dividido por 10, `event` intacto | 9,5 % | 4,5 % | **2,0 %** | [0,8 %, 5,0 %] | NO PROMETEDORA |
| R2 | eliminado, solo `event` | 11,5 % | 2,0 % | **2,5 %** | [1,1 %, 5,7 %] | NO PROMETEDORA |

### La hipótesis quedó FALSADA

| Moldeado | Tasa a 500k |
|---|---|
| completo (D_A) | **61,5 %** |
| rebalanceado (D_B) | 22,5 % |
| dividido por 10 (R1) | **2,0 %** |
| eliminado (R2) | **2,5 %** |

**Cuanto menos moldeado, peor.** Y no por inestabilidad: ambas entrenaron sin
error, con parámetros finitos, sin NaN y sin colapso de entropía.

Mi aritmética sobre qué término domina la suma era correcta pero irrelevante:
confundí «qué término domina la recompensa» con «qué término aporta señal
aprovechable». Con goles como única señal, la mayoría de los pasos no informan.

---

## 13. Qué aprendimos

### CONFIRMADO — medido o ejecutado

- H1 quedó inconcluyente: B − A = −0,83 pp, IC95 [−3,89, +2,22].
- La variación entre semillas supera a la diferencia entre brazos.
- Tras 504.000 muestras la política se aleja solo un 1,55 % de C0.
- Las instantáneas del pool de H1 eran casi idénticas entre sí (mediana 0,0074).
- La deriva crece como **√muestras**, verificado en cinco puntos.
- La regla de retención funciona: 41 instantáneas creadas, 16 conservadas, 25
  expulsadas.
- Un linaje neutral **sí** produce rivales en zona informativa (55 %).
- **En las cinco configuraciones de recompensa probadas, la tasa de victoria
  frente a C0 se degrada al aumentar el presupuesto.**
- Reducir o eliminar el moldeado hunde el rendimiento (61,5 % → 2,0 %).
- La infraestructura aguanta: cero huérfanos, reanudación idempotente,
  recuperación de checkpoints verificada.

### HIPÓTESIS — explicaciones que propusimos

- Que el efecto suelo era la causa principal del resultado de H1. *Plausible y
  parcialmente apoyada, pero la debilidad de la intervención pesa al menos
  tanto.*
- Que C0 pudiera ocupar un óptimo local peculiar del que cualquier
  entrenamiento se aleja. **No comprobada.**
- Que el horizonte de 300 pasos con γ = 0,99, o `standardize_returns` con
  recompensas casi siempre nulas, contribuyan al deterioro. **No comprobadas.**

### FALSADO — contradicho por los datos

- **Que el exceso de *reward shaping* causara el deterioro.** Reducirlo por diez
  y eliminarlo empeoraron el resultado drásticamente.
- Que `DefaultReward` de `rlgym_sim` fuese «solo goles». Es
  `−|velocidad_angular|/100`: penaliza girar y no codifica la tarea.
- Que la varianza explicada sirviera para validar el crítico aquí. Es circular
  cuando los retornos se derivan de los valores.
- Que la razón |valor/retorno| sirviera de calibración bajo `ZeroSumReward`.
  Con media cercana a cero, la razón se dispara sin significar nada.
- Que los errores `WinError 10038` del cierre de sockets fueran inofensivos.
  Lo son para la corrida que termina; no para la siguiente del mismo proceso.

### NO RESUELTO

- **Por qué entrenar más deteriora el juego frente a C0.** Es el hallazgo
  central y **no tiene explicación identificada**. Lo que sabemos es qué
  explicaciones probadas **no** bastan: no es exceso de moldeado, no es la
  envoltura ZeroSum, no es inestabilidad numérica, y no es sobreajuste al rival
  —el rival de entrenamiento y el de evaluación son el mismo C0—.
- Si el pool de rivales aporta algo a escalas mayores. H1 no lo resolvió y H2 no
  llegó a ejecutarse.

---

## 14. Qué NO podemos concluir

Con claridad, para que nadie lea de más:

- **No** que el pool de rivales sea mejor ni peor que el rival único.
- **No** que el brazo A ganara. La diferencia estaba dentro de la incertidumbre.
- **No** que sepamos por qué el entrenamiento deteriora la política. Solo
  sabemos qué explicaciones descartamos.
- **No** que `stage_1_basics` sea «la buena recompensa». Es la menos mala de las
  cinco probadas, y también se degrada.
- **No** que ZeroSumReward sea perjudicial. Su efecto no pudo aislarse.
- **No** que exista un bot mejorado. No se demostró mejora sobre nada.

Ninguna correlación de este trabajo se ha convertido en causalidad.

---

## 15. Limitaciones

1. **Presupuesto muy pequeño**: 504.000 muestras por corrida, frente a los miles
   de millones del upstream. Escala de prueba de concepto.
2. **Efecto suelo en H1**: rivales fuera de alcance, tasas del 5 %.
3. **Tres semillas en H1**, una sola por configuración en los diagnósticos: no
   permite separar el efecto del método del de la semilla.
4. **La retención nunca se activó en H1** (13 instantáneas frente a un tope de
   16). La regla estaba en el diseño pero no ejerció efecto.
5. **Un único valor de K, retención y presupuesto** por experimento; sin
   análisis de sensibilidad.
6. **Duraciones no comparables entre corridas** por contención de CPU externa.
7. **El bootstrap de H1 remuestreaba partidas** como si fueran independientes.
   La unidad real es la corrida; el intervalo salía más estrecho de lo debido —y
   aun así incluía el cero, así que el veredicto se sostiene.
8. **Máquina única**, CPU, sin GPU: 1.100–1.350 muestras/s.

---

## 16. Trabajo futuro posible

Nada de esto se ha hecho, y **ninguno debe emprenderse sin abrir una línea nueva
explícita**:

- Averiguar por qué el rendimiento decae con el presupuesto: la pregunta viva.
  Empezaría por medir tasa de victoria contra C0 cada 50.000 muestras para
  localizar el punto de inflexión, y por comprobar el efecto de γ y del
  horizonte.
- Repetir el diagnóstico de recompensas con varias semillas, para separar
  recompensa de semilla.
- Retomar H2 solo si se resuelve lo anterior, con K = 150.000 y retención 16
  (que ya cumpliría G3 con 2,5 M, medido) y el presupuesto que exija G2 según la
  ley √ ya medida.

---

## 17. Reproducción de resultados

Guía completa en `docs/REPRODUCE.md`. En resumen:

| | |
|---|---|
| **Reproducible directamente** | los análisis: `analyze_h1.py`, `gate_check.py` y las tablas, desde los JSONL |
| **Requiere artefactos locales** | los entrenamientos y evaluaciones: necesitan C0, las mallas de colisión y los checkpoints de referencia |
| **No redistribuible** | mallas de colisión, checkpoints ajenos (Martin, Nachi, Marco, Diego) |
| **Costoso de repetir** | las 6 corridas de H1 (~1 h) y el linaje neutral de 4 M (~50 min) |

---

## 18. Mapa de artefactos

### En el repositorio

| Ruta | Contenido |
|---|---|
| `src/rlbot/env/{rocketsim_init,frozen_opponent,opponent_pool}.py` | núcleo propio |
| `scripts/` | 21 herramientas propias + 5 heredadas |
| `configs/experimento/` | tres protocolos congelados con sus SHA |
| `docs/experiments/` | H1, H2, diagnósticos e incidencias |
| `docs/{FINAL_REPORT,CONTRIBUTIONS,REPRODUCE}.md` | este informe, autoría y reproducción |
| `ESTADO_PROYECTO.md` | diario cronológico completo |
| `NOTICE`, `UPSTREAM.md`, `MANIFIESTO_HASHES.txt` | atribución y hashes |

### Fuera del repositorio (`%LOCALAPPDATA%\rlgym-selfplay-pool\`)

| Ruta | Contenido |
|---|---|
| `experimento/` | H1: 6 corridas, 720 partidas, análisis, integridad |
| `h2/fase0/` | linaje neutral, piloto, calibración, puerta |
| `diagnostico/`, `final-check/` | D_A/D_B/D_C y R1/R2, con sus duelos |
| `artifacts/`, `collision_meshes/` | material ajeno, **no redistribuible** |

### Volumen de trabajo

Calculado solo desde artefactos existentes:

| | |
|---|---|
| Entrenamientos con informe | **15** |
| Muestras procesadas | **12.112.000** |
| Tiempo de cómputo registrado | **3,00 h** (más ≥ 2 M de muestras descartadas al interrumpirse una corrida) |
| Partidas evaluadas | **3.960** en JSONL + 200 duelos sin JSONL propio |
| Checkpoints / hitos / instantáneas | 50 / 24 / 160 (0,54 GB) |
| Protocolos congelados por SHA256 | **3** |
| Código propio | **5.401 líneas en 24 archivos** |
| Documentación propia | **3.038 líneas** |

**Las 3.960 partidas son una magnitud de ingeniería, no una muestra
estadística**: proceden de protocolos distintos y no deben agregarse para
calcular ninguna tasa conjunta.
