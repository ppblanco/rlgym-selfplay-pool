# Diagnóstico de recompensa — resultados y conclusión

Protocolo: `configs/experimento/reward-diagnostic/protocolo.json`, escrito
**antes** de entrenar. Fecha: 2026-09-08.

H1 sigue cerrado como INCONCLUYENTE. La puerta de H2 sigue en NO-GO. Nada de
lo anterior se ha sobrescrito ni reinterpretado.

---

## 1. Pregunta

¿Existe alguna configuración de recompensa bajo la cual entrenar **mejore** la
tasa de victoria contra C0? No se trataba de optimizar una recompensa hasta
arrancar una victoria, sino de comparar tres alternativas fijadas de antemano.

## 2. Las tres configuraciones

Inventario de lo que ya había en el proyecto heredado:

| Nombre | Componentes y pesos | ZeroSum | Qué incentiva | De dónde sale |
|---|---|---|---|---|
| `stage_1_basics` | velocity_player_to_ball 0,10 · face_ball 0,05 · velocity_ball_to_goal 0,30 · event 8,0 (gol 1, encajar −1, tiro 0,1, demo 0,1) | sí | ir hacia la pelota, mirarla y empujarla a portería | heredado, `configs/reward_weights/` |
| `stage_2_offense` | velocity_player_to_ball 0,03 · velocity_ball_to_goal 0,60 · touch_ball 0,05 · event 12,0 (gol 1, encajar −1, tiro 0,15, parada 0,3, demo 0,1) | sí | desplaza el peso hacia marcar y hacia mover la pelota a portería | heredado, `configs/reward_weights/` |

No hacía falta inventar nada para las dos primeras. La tercera reutiliza
`stage_2_offense` **sin tocar un solo peso**, desactivando únicamente la
envoltura, que `build_reward()` ya soportaba de forma nativa
(`if config.get("zero_sum", True)`). Verificado comparando los YAML: la única
clave que difiere es `zero_sum`.

| Config | Recompensa | ZeroSum | Papel |
|---|---|---|---|
| **D_A** | `stage_1_basics` | sí | referencia: la recompensa de H1 |
| **D_B** | `stage_2_offense` | sí | más señal de gol |
| **D_C** | `stage_2_offense` | **no** | aísla ZeroSum: difiere de D_B en exactamente una clave |

## 3. Lo que se mantuvo idéntico

Mismo C0, misma semilla de entrenamiento (20260951), misma arquitectura
(512×3), mismo entorno, 2 trabajadores con 1 hilo, lote 8.000, mismos
hiperparámetros de PPO, **500.000 muestras** y el mismo rival C0 fijo. Un
proceso por configuración. Checkpoints a 100k, 250k y 500k.

Evaluación: 200 partidas por checkpoint contra C0, semillas 11000–11199, lados
alternados (100 azul y 100 naranja), modo estocástico. 1.800 partidas en total.
Semillas nuevas: no se reutilizan las de H1 (5000–5039), ni las de calibración
de H2 (9000–9039), ni las previstas como finales (7000–7059). No se usaron
Martin, Nachi ni Marco, ni los escalones del linaje neutral.

## 4. Resultados

Tasa de victoria contra C0, con intervalo de Wilson al 95 %:

| Config | 100k | 250k | 500k | IC95 a 500k |
|---|---|---|---|---|
| **D_A** | **72,0 %** | 67,5 % | **61,5 %** | [54,6 %, 68,0 %] |
| **D_B** | 14,0 % | 37,5 % | 22,5 % | [17,3 %, 28,8 %] |
| **D_C** | 56,5 % | 52,5 % | 16,0 % | [11,6 %, 21,7 %] |

Estabilidad (mediana de las 10 últimas iteraciones):

| Config | Parámetros finitos | Entropía | vf_loss | Deriva a 500k |
|---|---|---|---|---|
| D_A | sí | 4,09 | 0,113 | 0,0157 |
| D_B | sí | 4,26 | 0,126 | 0,0157 |
| D_C | sí | 4,32 | 0,073 | 0,0157 |

Ninguna colapsa: entropía alta y estable, pérdidas finitas, sin NaN.

**La deriva es idéntica en las tres (0,0157).** La recompensa no cambia *cuánto*
se mueve la política, sino **hacia dónde**: mismo desplazamiento, resultados de
juego que van del 61,5 % al 16 %.

## 5. Veredicto según el criterio congelado

| Config | 500k > 50 % | IC excluye 50 % | Sin deterioro sistemático | Estable | **Veredicto** |
|---|---|---|---|---|---|
| D_A | sí (61,5 %) | sí | **NO**: 61,5 < 72,0 − 10 = 62,0 | sí | **NO PROMETEDORA** |
| D_B | no (22,5 %) | — | no | sí | **NO PROMETEDORA** |
| D_C | no (16,0 %) | — | no | sí | **NO PROMETEDORA** |

**D_A falla por 0,5 puntos porcentuales.** Conviene decirlo con precisión: no
falla por un umbral caprichoso. La caída de 72,0 % a 61,5 % son 10,5 puntos,
con un error típico de la diferencia de 4,7 puntos: **2,2 errores típicos**. El
deterioro es real, no ruido. El criterio hizo lo que debía.

**Ninguna configuración pasa.**

## 6. El patrón, que es el hallazgo

Las tres configuraciones **empeoran con más entrenamiento**:

- D_A: 72,0 → 67,5 → 61,5
- D_C: 56,5 → 52,5 → 16,0
- D_B sube de 14,0 a 37,5 y vuelve a caer a 22,5

Y encaja con lo medido antes en H2: el piloto de 2,5 M quedó en 15 % y el
linaje neutral a 1 M en 17,5 %. El perfil completo es **subida temprana y
declive sostenido**.

### Diagnóstico cuantificado

Los términos moldeados se cobran **en cada paso**; el gol se cobra **una vez**.
Con `stage_1_basics`, `velocity_ball_to_goal` aporta 0,30 por paso a lo largo de
episodios de hasta 300 pasos, frente a 8,0 por un gol. El término moldeado puede
dominar al de gol en un orden de magnitud.

Eso predice que subir el peso moldeado empeore las cosas. Es exactamente lo que
pasa: `stage_2_offense` **duplica** `velocity_ball_to_goal` (0,60) y es
drásticamente peor (22,5 % frente a 61,5 %), pese a llevar *más* peso nominal de
gol (12,0 frente a 8,0). El nombre del fichero sugiere lo contrario de lo que
hace.

Esto es desalineación entre recompensa y objetivo, no inestabilidad numérica ni
sobreajuste al rival: el rival de entrenamiento y el de evaluación son el mismo
C0, así que sobreajustar debería *ayudar*.

## 7. ZeroSum, analizado por separado

D_B y D_C difieren en exactamente una clave, así que el contraste es limpio:

| | 100k | 250k | 500k |
|---|---|---|---|
| D_B (con ZeroSum) | 14,0 % | 37,5 % | 22,5 % |
| D_C (sin ZeroSum) | 56,5 % | 52,5 % | 16,0 % |
| Diferencia C − B | **+42,5 pp** | +15,0 pp | **−6,5 pp** |

**El efecto cambia de signo.** Sin ZeroSum es mucho mejor al principio y peor al
final. Con una sola semilla por configuración no se puede separar el efecto de
la envoltura del de la semilla ni del ruido.

**Conclusión sobre ZeroSum: no puede aislarse con esta prueba, y no es el
factor dominante.** Lo que domina son los componentes: `stage_1_basics` (61,5 %)
supera con holgura a las dos variantes de `stage_2_offense` (22,5 % y 16,0 %),
lleven o no la envoltura. En estabilidad tampoco hay diferencia relevante: las
tres mantienen entropía alta y pérdidas finitas.

No se afirma causalidad. Haría falta repetir con varias semillas para separarlo.

## 8. Una corrección a lo que dije en la puerta de H2

En `docs/experiments/h2/puerta-go-no-go.md` escribí que **«los cinco agentes
entrenados pierden contra su propio punto de partida»**. Aquellos duelos tenían
**40 partidas** cada uno, con un margen de ±15 puntos que yo mismo señalé.

Con 200 partidas, `stage_1_basics` a 500.000 muestras **gana a C0 el 61,5 %**
(IC [54,6 %, 68,0 %]). La afirmación absoluta era **demasiado fuerte para la
evidencia que tenía**.

Lo que sí se confirma, y con mejor potencia, es la **dirección**: la tasa de
victoria se degrada según crece el presupuesto. Eso era lo relevante para la
decisión, y sigue en pie.

No modifico las conclusiones del documento de la puerta: el NO-GO se apoya en
G2 (deriva) y G3 (diversidad), que no dependen de esto.

## 9. Defecto propio detectado

El campo `recompensa_media_ultimas_10` de los informes vale 0,0000 en las tres
configuraciones, incluida la que no lleva ZeroSum. No es un resultado: es un
defecto. `Policy Reward` no viene en el diccionario que devuelve
`ppo_learner.learn()` —lo imprime el Learner por separado—, así que mi `.get()`
devolvía siempre 0. **Ese campo debe ignorarse.** No he reentrenado para
recuperarlo porque la variable primaria no depende de él, y para comparar la
magnitud del cambio he usado la deriva, que sí está medida.

## 10. Conclusión y recomendación

**Ninguna de las tres configuraciones es PROMETEDORA. H2 sigue en NO-GO.**

De las tres salidas posibles, recomiendo **cambiar la formulación del
objetivo**, y no cerrar todavía, por una razón concreta: ya no es una corazonada
sino una hipótesis cuantificada y direccional. Sabemos que el término moldeado
domina al de gol en un orden de magnitud, y que **duplicarlo empeoró el
resultado a la mitad**. La predicción que se sigue es clara y falsable:
reducirlo debería mejorarlo.

La prueba mínima que lo zanjaría, con el mismo arnés y ~20 minutos de máquina:
dos configuraciones a 500.000 muestras, misma semilla, mismo todo,

- una con `stage_1_basics` y los pesos moldeados divididos por diez;
- otra sólo con el término `event`, sin moldeado alguno.

Con el mismo criterio congelado que aquí, y **fijado antes de ejecutar**. Si
ninguna supera el 50 % con tendencia no decreciente, entonces la recomendación
es **cerrar la línea experimental**: querría decir que el problema no está en el
peso de los términos sino en el planteamiento, y a esa altura el proyecto ya
tiene un resultado honesto que contar.

Lo que **no** recomiendo: subir el presupuesto de H2, tocar K o la retención, ni
retomar el diseño de H2 con cualquiera de estas tres recompensas. Todas
empeoran con el entrenamiento, y comparar dos brazos sobre una base que se
degrada no responde a la pregunta de H2.

---

## Artefactos

| Ruta | Contenido |
|---|---|
| `configs/experimento/reward-diagnostic/protocolo.json` | protocolo, escrito antes de entrenar |
| `configs/experimento/reward-diagnostic/stage_2_offense_nozs.yaml` | variante C |
| `diagnostico/D_A|D_B|D_C/informe.json` | configuración resuelta, hitos con hash, métricas |
| `diagnostico/duelos.jsonl` | las 1.800 partidas, con semilla, lado, hashes y resultado |
| `diagnostico/resumen_*.json` | agregados con IC de Wilson |
