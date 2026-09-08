# Diseño de H2 — segunda iteración experimental

**Estado: DISEÑO. No ejecutado.** Sin protocolo congelado todavía, sin
entrenamientos, sin evaluación final, sin commits ni publicación.

H1 queda cerrado como **INCONCLUYENTE** y sus artefactos intactos. Este
documento usa H1 sólo como **diagnóstico**.

Cada afirmación va etiquetada:

- **[CONFIRMADO]** — medido en H1, con el dato a la vista.
- **[DISEÑO]** — decisión que tomo yo y que se puede discutir.
- **[ESTIMACIÓN]** — proyección; puede fallar.

---

## 1. Lecciones de H1

### 1.1 El efecto suelo era real, pero no era el único problema

**[CONFIRMADO]** Ambos brazos ganaron ~5 % (A 18/360, B 15/360) contra rivales
entrenados con 2.000–2.900 millones de pasos. A esa tasa base, 720 partidas no
tienen resolución.

### 1.2 El hallazgo que cambia el diseño: la manipulación fue casi nula

Medí la deriva de los parámetros sobre los checkpoints que H1 dejó en disco
(617.562 parámetros, norma de C0 = 100,67).

**[CONFIRMADO] Tras 504.000 muestras, la política sólo se alejó un 1,55 % de C0**,
y de forma llamativamente idéntica en las seis corridas:

| Corrida | A1 | B1 | A2 | B2 | A3 | B3 |
|---|---|---|---|---|---|---|
| ‖final−C0‖/‖C0‖ | 0,0156 | 0,0154 | 0,0153 | 0,0159 | 0,0155 | 0,0160 |

**[CONFIRMADO] El pool de B casi no tenía diversidad.** Distancia entre pares de
instantáneas: mediana 0,0074, máximo 0,0151. Las 13 «instantáneas distintas»
contra las que entrenó B estaban todas dentro del 1,5 % unas de otras.

Esto es más grave que el efecto suelo. Significa que **el tratamiento apenas se
diferenció del control**: entrenar contra 13 copias casi idénticas de uno mismo
no es muy distinto de entrenar contra una sola. H1 no sólo no tenía potencia
estadística; es que la intervención que medía era muy débil.

Un resultado inconcluyente era, en retrospectiva, el desenlace esperable. Esto
no rescata a H1 ni convierte su resultado en positivo: lo explica.

### 1.3 La deriva no se está saturando

**[CONFIRMADO]** El paso por cada 40.000 muestras se estabiliza en ~0,0021 y se
mantiene plano de 160.000 a 480.000. La distancia neta a C0 crece de forma
sostenida: 0,0090 → 0,0151 entre 160k y 480k, es decir **1,9 × 10⁻⁵ por cada
1.000 muestras**, sin señal de meseta.

Traducción: 500.000 muestras están en el régimen donde el entrenamiento apenas
empieza. Más presupuesto **sí** mueve la política.

### 1.4 Variación entre semillas

**[CONFIRMADO]** Diferencias B−A por semilla: −0,8, +0,8 y −2,5 pp
(desviación típica ≈ 1,7 pp). El rango entre semillas del mismo brazo (2,5 pp
en A, 1,7 pp en B) superaba a la diferencia entre brazos (0,83 pp).

### 1.5 Coste real

**[CONFIRMADO]** Con la máquina libre y un proceso por corrida: 1.067–1.247
muestras/s (A2 1.149, B2 1.067, A3 1.080, B3 1.247). Las corridas con
contención externa bajaron a 401–553 muestras/s.

**[DISEÑO]** Uso **1.150 muestras/s** como cifra de planificación, y asumo que
puede caer a la mitad si la máquina no está libre.

### 1.6 Comportamiento del pool

**[CONFIRMADO]** 12 instantáneas más C0, retención 16: **la regla de expulsión
nunca llegó a activarse**. El pool de B fue «todas las instantáneas pasadas».
La retención figuraba en el diseño pero no ejerció ningún efecto.

### 1.7 Incidencias de infraestructura

**[CONFIRMADO]** El `cleanup()` de `rlgym_ppo` falla en Windows
(`WinError 10038`) y deja estado de sockets corrupto **para la corrida
siguiente del mismo proceso**: A2 se quedó bloqueada con los 16 hilos en espera
y cero CPU. La evaluación final se cortó en la partida 389 de 720 y hubo que
reanudarla.

### 1.8 Un defecto estadístico de H1 que no cambió el resultado

**[CONFIRMADO]** El bootstrap de H1 remuestreaba **partidas** como si fueran
independientes. No lo son: 120 partidas comparten un mismo agente entrenado. La
unidad de independencia es la **corrida**, no la partida. El intervalo de H1 era
por tanto más estrecho de lo debido — y aun así incluía el cero, así que el
veredicto inconcluyente se sostiene con holgura. Pero el método debe corregirse
para H2.

---

## 2. Qué cambia en H2 y qué no

### Cambia

| | H1 | H2 | Por qué |
|---|---|---|---|
| Rivales de evaluación | Martin, Nachi, Marco (2–2,9 B pasos) | escalones calibrados de dificultad | salir del suelo |
| Presupuesto | 504.000 muestras | 2,5 M (recomendado) | §1.3: la deriva no se satura |
| K | 40.000 | 100.000 | pool más ancho, retención activa |
| Retención | 16 (nunca actuó) | 16 (actúa: 25 > 16) | que el diseño sea real |
| Semillas | 3 | 5 | la unidad de análisis es la corrida |
| Análisis | bootstrap sobre partidas | bootstrap jerárquico emparejado | §1.8 |
| Ejecución | un proceso para las 6 | un proceso por corrida, desde el diseño | §1.7 |

### No cambia

- La recompensa `stage_1_basics` heredada. **[DISEÑO]** Cambiarla haría H2
  incomparable con H1 y añadiría una variable no controlada.
- C0 como punto de partida común de todas las corridas.
- La arquitectura, los hiperparámetros de PPO, la observación y el parser de
  acciones.
- El principio conservador: una diferencia porcentual aislada no es evidencia.
- La separación estricta entre datos de calibración y datos de evaluación final.
- Congelar el protocolo, con su SHA256, **antes** de ejecutar.

---

## 3. Rivales: el cambio principal

### 3.1 El problema, y por qué no se resuelve con los rivales que ya hay

**[CONFIRMADO]** Hay una cuarta política heredada que H1 no usó:
`diego_1.18B_512` (1.180 millones de pasos, red de 512). Sigue siendo **tres
órdenes de magnitud** más entrenada que nuestros agentes. No resuelve el suelo.

**[CONFIRMADO]** Nuestros agentes se mueven un 1,5 % desde C0. Los únicos
rivales que pueden caer en una zona informativa son de **nuestra propia escala**.

### 3.2 El riesgo que hay que evitar: circularidad

Si los rivales finales fueran instantáneas del propio linaje, B quedaría
favorecido por construcción: B entrena precisamente contra instantáneas
históricas de sí mismo. Mediríamos familiaridad, no habilidad.

**[DISEÑO] Los rivales finales no pueden ser instantáneas de A ni de B.**

### 3.3 Propuesta: un linaje de sparring neutral

**[DISEÑO]** Entrenar **un único linaje S de sparring**, con:

- un **tercer esquema**, que no es el de A ni el de B: entrenamiento contra C0
  congelado y fijo durante toda la corrida (rival estático);
- una **semilla fuera del conjunto experimental** (p. ej. 20260931);
- checkpoints guardados en varios presupuestos: 0,5 M, 1 M, 2 M, 4 M.

Una sola corrida de 4 M muestras produce **cuatro escalones de dificultad**.
**[ESTIMACIÓN]** ≈ 58 min a 1.150 muestras/s.

Ventajas: los rivales no pertenecen al linaje de ningún brazo, están a nuestra
escala, y el coste es de una corrida.

### 3.4 Conjunto de DESARROLLO

**[DISEÑO]** El desarrollo se usa **sólo para elegir dificultad**, nunca para
comparar A contra B:

- Escalones del linaje S: S@0,5M, S@1M, S@2M, S@4M.
- C0 (referencia de «empate por construcción»).
- Diego (referencia de techo).

**Sonda de calibración:** un **agente piloto P**, entrenado con el presupuesto
candidato de H2, con el **esquema de control** (brazo A) y una **semilla piloto**
fuera del conjunto experimental (p. ej. 20260932).

**Regla que impide la trampa:** durante la calibración **sólo existe P**. No hay
brazo B piloto, así que es literalmente imposible elegir rivales mirando a quién
favorecen. La dificultad se mide contra un solo agente.

**Método:** 40 partidas de P contra cada escalón, semillas de partida
**9000–9039**. Se elige cada rival final por su tasa de victoria de P:

- **zona informativa: 35 %–65 %**;
- se descartan los escalones por debajo del 20 % o por encima del 80 %;
- si más de tres escalones caen en zona, se eligen los tres **más separados
  entre sí** en dificultad, para cubrir un rango.

Ningún dato de desarrollo entra en el análisis final.

### 3.5 Conjunto FINAL

**[DISEÑO]** Se congela tras la calibración y no se toca hasta que terminen los
entrenamientos:

- **tres escalones** del linaje S elegidos en §3.4 — el contraste primario;
- **Diego**, como referencia secundaria de generalización fuera del linaje. Se
  reporta aparte y **no entra en el criterio primario**, porque una tasa cercana
  a cero sólo añadiría ruido.

Semillas de partida finales: **7000–7059**, disjuntas de las de desarrollo
(9000–9039) y de las de H1 (5000–5039).

**[DISEÑO]** Martin, Nachi y Marco **no se reutilizan**. Ya produjeron su
resultado en H1 y su nivel es el que causó el suelo.

---

## 4. Presupuesto de entrenamiento

Proyección a partir de la deriva medida (1,9 × 10⁻⁵ por 1.000 muestras en el
régimen lineal). **[ESTIMACIÓN]**: extrapolación lineal de un proceso que es en
parte aleatorio; puede quedarse corta o larga.

| Presupuesto | Deriva prevista | ×H1 | Instantáneas (K=100k) | min/corrida | 10 corridas |
|---|---|---|---|---|---|
| 504 k (H1) | 0,0155 | 1,0× | 5 | 7 | — |
| **1,5 M (mínimo)** | ~0,035 | 2,3× | 15 | 22 | **3,6 h** |
| **2,5 M (recomendado)** | ~0,054 | 3,5× | 25 | 36 | **6,0 h** |
| **6 M (máximo razonable)** | ~0,120 | 7,7× | 60 | 87 | **14,5 h** |

**[DISEÑO] Recomendado: 2,5 M muestras por corrida.**

Razones: triplica largamente el movimiento de la política respecto a H1; hace
que la retención actúe (25 instantáneas frente a un tope de 16); y mantiene el
coste en una jornada de máquina. El mínimo de 1,5 M es el punto por debajo del
cual repetiríamos el problema de H1. El máximo de 6 M sólo tiene sentido si la
puerta go/no-go (§8) muestra que 2,5 M sigue siendo insuficiente.

Sigue estando **tres órdenes de magnitud** por debajo del upstream, y no
pretende otra cosa.

---

## 5. K y retención

**[CONFIRMADO]** Con K=40.000 y 504 k de presupuesto: 13 instantáneas, retención
16 nunca activada, y separación entre extremos del pool de sólo 0,0151.

**[DISEÑO] K = 100.000, retención = 16, C0 protegido.**

Justificación, **sin mirar tasas de victoria de H1**:

1. **La retención pasa a ejercer efecto real.** Con 2,5 M y K=100k salen 25
   instantáneas frente a un tope de 16: la expulsión de las más antiguas actúa
   durante la mayor parte de la corrida. Si seguimos afirmando que la retención
   forma parte del diseño, tiene que hacer algo.
2. **Diversidad temporal.** Con retención 16 y K=100k, el pool cubre las últimas
   1,6 M muestras de historia. **[ESTIMACIÓN]** eso corresponde a una separación
   entre extremos de ~0,030: el doble de ancho que **todo** el pool de H1.
3. **Coste.** Menos escrituras de instantáneas y menos recargas que con K=40.000
   sobre un presupuesto cinco veces mayor.

**[DISEÑO]** Mantener K=40.000 con 2,5 M daría 62 instantáneas y también activaría
la retención, pero el pool sólo cubriría las últimas 640 k muestras: un pool más
numeroso y más estrecho. Prefiero **ancho** a **número**, porque lo que H1
mostró escaso fue la diversidad, no la cantidad.

---

## 6. Reproducibilidad operativa

**[DISEÑO]** Diseñado desde el principio, aislado en nuestra capa. **No se
modifica `rlgym_ppo`**: se le rodea.

1. **Una invocación de proceso por corrida.** Ningún proceso ejecuta dos
   entrenamientos. Elimina de raíz la herencia de sockets de §1.7.
2. **Proceso padre limpio**: un conductor que sólo lanza subprocesos y observa;
   no importa `torch` ni `rlgym_sim`.
3. **Detección explícita de trabajadores vivos**: antes de dar una corrida por
   arrancada, comprobar que los procesos hijo existen y consumen CPU; si el
   avance se detiene más de N minutos, matar el árbol y marcar la corrida como
   FALLIDA en vez de colgarse.
4. **Marcador `COMPLETA` en disco** antes de pasar a la siguiente corrida: un
   `informe.json` con `completa: true`. El conductor no avanza sin él.
5. **Reanudación idempotente**: relanzar el conductor no repite corridas
   completas ni corrompe las existentes; una corrida fallida se descarta entera
   y se rehace desde C0, nunca se «continúa».
6. **JSONL de evaluación con identificador único por partida** (ya funciona en
   H1: la reanudación saltó 389 partidas sin repetir ninguna).
7. **Estado RNG reproducible**: sembrar por partida antes de construir nada, y
   **construir las políticas siempre en el mismo orden**, incluso al reanudar.
   Esto corrige el único artefacto que H1 tuvo que documentar: al reanudar, la
   política propia se cargaba en otro punto de la secuencia aleatoria.

**[DISEÑO]** Las trazas `WinError 10038` seguirán apareciendo al cerrar cada
corrida. Con un proceso por corrida son inofensivas de verdad, no sólo en
apariencia: no hay corrida siguiente que herede el estado.

---

## 7. Criterio estadístico

### 7.1 Qué estaba mal

**[CONFIRMADO]** Dos defectos en H1: el bootstrap trataba 720 partidas como
independientes (§1.8), y el criterio «magnitud > rango entre semillas» usa un
rango calculado sobre **tres** valores, que es un estimador muy inestable de la
variación y además descarta el emparejamiento por semilla.

### 7.2 Alternativas consideradas

| Método | A favor | En contra |
|---|---|---|
| Diferencias emparejadas por semilla | respeta el emparejamiento y la unidad experimental | con pocas semillas, la varianza se estima mal |
| **Bootstrap jerárquico emparejado** | respeta unidad y emparejamiento; pocos supuestos; no falla con pocos grupos | intervalos algo optimistas con muy pocos grupos |
| Logístico de efectos mixtos (brazo fijo; semilla y rival aleatorios) | usa toda la estructura; estima efectos por rival | problemas de convergencia con 5 grupos; más supuestos |
| Bootstrap sobre partidas (H1) | simple | **incorrecto**: sobreestima la precisión |

### 7.3 Recomendación

**[DISEÑO] Método principal: bootstrap jerárquico emparejado por semilla.**

- Unidad experimental: **la corrida** (un agente entrenado), no la partida.
- Variable primaria: **tasa de victoria en partidas completas** contra los tres
  rivales finales calibrados, agregada.
- Contraste: para cada semilla *s*, la diferencia emparejada
  d*ₛ* = tasa_B(*s*) − tasa_A(*s*). Estimando primario: la media de d*ₛ*.
- Intervalo: bootstrap de dos niveles — remuestrear semillas con reemplazo y,
  dentro de cada una, partidas con reemplazo; 10.000 réplicas; percentiles 2,5 y
  97,5.

**Análisis secundarios**, declarados de antemano y **no decisorios**: el modelo
logístico de efectos mixtos, y el desglose por rival.

### 7.4 Criterio de decisión, a congelar antes de ejecutar

**[DISEÑO]**

- **A FAVOR de H2** si el IC 95 % de la media de d*ₛ* **excluye el 0** y el signo
  de d*ₛ* es consistente en **≥ 4 de 5** semillas.
- **EN CONTRA** con lo mismo y el signo invertido.
- **INCONCLUYENTE** en cualquier otro caso, y se dirá literalmente.

Se elimina el criterio «magnitud > rango entre semillas»: la variación entre
semillas ya está **dentro** del intervalo por construcción, al remuestrear
semillas. Esto no relaja el listón, lo hace coherente.

### 7.5 Potencia: qué podrá y qué no podrá detectar H2

**[ESTIMACIÓN]** Con 5 semillas y una desviación típica de las diferencias por
semilla de ~4 pp en la zona informativa (frente a 1,7 pp observado en H1, donde
las tasas estaban pegadas al suelo y por tanto poco dispersas), el error típico
de la media emparejada sería ~1,8 pp.

**H2 podrá detectar diferencias del orden de 5 puntos porcentuales. No podrá
detectar diferencias de 1–2 pp.** Si el efecto real del pool es pequeño, H2
volverá a salir inconcluyente — y eso hay que aceptarlo antes de empezar, no
después.

---

## 8. Hipótesis H2 y criterio go/no-go

### 8.1 Enunciado

> **H2:** con un presupuesto de 2,5 millones de muestras por corrida y frente a
> rivales calibrados para producir tasas de victoria en el rango 35 %–65 %,
> un agente entrenado contra un pool de hasta 16 instantáneas históricas de sí
> mismo (K = 100.000, C0 protegido) obtiene una **tasa de victoria media
> emparejada por semilla superior** a la de un agente entrenado contra una única
> copia congelada de su yo reciente, con idéntico presupuesto de muestras.

| | |
|---|---|
| Variable primaria | tasa de victoria en partidas completas contra los 3 rivales finales |
| Unidad experimental | la corrida (agente entrenado) |
| Contraste | media sobre semillas de d*ₛ* = tasa_B(*s*) − tasa_A(*s*) |
| Intervalo | bootstrap jerárquico emparejado, 10.000 réplicas, IC 95 % |
| Éxito | IC excluye 0 **y** signo consistente en ≥ 4 de 5 semillas |
| Inconcluyente | cualquier otro caso, dicho literalmente |

### 8.2 Puerta go/no-go, antes de gastar el entrenamiento completo

**[DISEÑO]** Tras el linaje de sparring, el piloto y la calibración —y **antes**
de lanzar las 10 corridas— deben cumplirse las cuatro:

| | Puerta | Umbral |
|---|---|---|
| G1 | **No hay efecto suelo ni techo** | ≥ 3 escalones con tasa de P entre 35 % y 65 % |
| G2 | **La política se mueve de verdad** | deriva de P ≥ 3× la de H1 (≥ 0,046) |
| G3 | **El pool tiene diversidad** | separación entre extremos del pool ≥ 2× la de H1 (≥ 0,030) y retención activada |
| G4 | **La infraestructura aguanta** | 3 corridas consecutivas completas sin bloqueo, y reanudación de evaluación verificada |

**Si alguna falla, no se gasta el entrenamiento completo.** Se revisa el diseño
y se vuelve a la puerta. G2 y G3 se miden con las mismas herramientas de
diagnóstico usadas en este documento, no con tasas de victoria.

---

## 9. Plan completo y coste

**[ESTIMACIÓN]** a 1.150 muestras/s, con la máquina libre:

| Fase | Contenido | Coste |
|---|---|---|
| 0 | Infraestructura §6 y herramientas | sin cómputo |
| 1 | Linaje de sparring S, 4 M, checkpoints a 0,5/1/2/4 M | ~58 min |
| 2 | Piloto P, 2,5 M, semilla piloto | ~36 min |
| 3 | Calibración: P contra 6 rivales × 40 partidas (semillas 9000–9039) | ~15 min |
| 4 | **Puerta go/no-go** y congelación del protocolo H2 con su SHA256 | sin cómputo |
| 5 | 10 corridas: 5 semillas × 2 brazos × 2,5 M | ~6,0 h |
| 6 | Integridad ciega de las 10 | ~5 min |
| 7 | Evaluación final: 10 × 3 rivales × 60 partidas = **1.800 partidas** (semillas 7000–7059) | ~20 min |
| 8 | Análisis y documento de resultados | sin cómputo |

**Total ≈ 8 horas de máquina**, de las cuales 6 son la fase 5. Las fases 1–4
cuestan ~1,8 h y son las que evitan gastar las 6 h en un experimento condenado.

**[DISEÑO]** Semillas de entrenamiento: **20260921–20260925** (5), distintas de
las de H1. Sparring 20260931, piloto 20260932.

---

## 10. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| La extrapolación lineal de la deriva falla y 2,5 M sigue siendo poco | media | G2 lo detecta antes de gastar las 6 h |
| Ningún escalón cae en la zona 35–65 % | media | G1; se añaden escalones intermedios al linaje S, que es barato |
| El efecto real es < 5 pp | **alta** | no hay mitigación: se aceptará inconcluyente. Declarado de antemano |
| Los rivales de sparring comparten sesgos con nuestros agentes por venir de C0 | media | Diego como referencia secundaria fuera del linaje; se reporta aparte |
| Bloqueos de infraestructura | baja tras §6 | un proceso por corrida, detección de estancamiento, reanudación idempotente |
| Contención de CPU dobla los tiempos | media | los tiempos son estimaciones; no afecta a la validez, sólo al calendario |
| Tentación de reanalizar si sale inconcluyente | — | criterio congelado con SHA256 antes de ejecutar |

---

## 11. Estructura de archivos

**[DISEÑO]** H1 no se toca. Todo lo de H2 va aparte:

```
docs/experiments/h2/diseno-h2.md          <- este documento
docs/experiments/h2/protocolo-h2.md       <- pendiente, tras la puerta go/no-go
configs/experimento/h2/protocolo.json     <- pendiente, con su SHA256
%LOCALAPPDATA%/rlgym-selfplay-pool/h2/    <- sparring, piloto, corridas, evaluación
outputs/h2/                               <- logs
```

Intactos y sin sobrescribir: `configs/experimento/protocolo.json`,
`experimento/` completo, `eval-final.jsonl`, `analisis-h1.json`,
`integridad.json`, `docs/experiments/resultados-finales.md`,
`docs/experiments/incidencias.md`.

---

## 12. Recomendación única

> **Ejecutar H2 con: presupuesto de 2,5 M muestras por corrida, K = 100.000,
> retención 16 con C0 protegido, 5 semillas emparejadas (20260921–20260925),
> tres rivales finales elegidos de un linaje de sparring neutral por caer en la
> zona 35 %–65 % frente a un agente piloto, 60 partidas por rival y corrida
> (1.800 en total), y bootstrap jerárquico emparejado por semilla como método
> principal —con la puerta go/no-go de §8.2 antes de gastar las seis horas de
> entrenamiento.**

Y una advertencia que forma parte de la recomendación: **H2 está dimensionado
para detectar diferencias de ~5 puntos porcentuales.** Si el pool de versiones
históricas aporta menos que eso, H2 volverá a ser inconcluyente. Ese resultado
seguiría siendo informativo —acotaría el tamaño del efecto—, pero conviene
aceptarlo ahora y no cuando lleguen los números.
