# Resultados finales del experimento H1

Protocolo congelado: `8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e`
Ejecutado el 2026-09-07. Evaluación final ejecutada **una sola vez**.

---

## 1. La pregunta

**H1:** un agente entrenado contra una mezcla de instantáneas congeladas de sí
mismo (un *pool* de rivales) alcanza una tasa de victoria mayor frente a
rivales reservados que uno entrenado contra una única copia congelada de su yo
actual, **con el mismo presupuesto de muestras de aprendizaje**.

- **Brazo A** (control): rival único, retención 1. El rival se refresca cada
  K = 40.000 muestras y sustituye al anterior.
- **Brazo B** (tratamiento): pool con retención 16 y C0 protegido. En cada
  episodio se muestrea un rival del pool.

Todo lo demás es idéntico entre brazos: mismo C0 de partida, misma recompensa
(`stage_1_basics` heredada), misma arquitectura, mismos hiperparámetros de PPO,
mismas semillas emparejadas y **el mismo presupuesto de 500.000 muestras**.

## 2. El protocolo, congelado antes de entrenar

El criterio de decisión se escribió **antes** de ver un solo resultado. H1 se
declara **A FAVOR** solo si se cumplen los cuatro a la vez:

1. el intervalo de confianza bootstrap al 95 % de la diferencia B − A excluye el 0;
2. la magnitud de la diferencia supera el rango entre semillas de ambos brazos;
3. el signo es consistente en al menos 2 de 3 semillas;
4. el signo es consistente en al menos 2 de 3 rivales.

**EN CONTRA** si se cumplen los cuatro con el signo invertido.
**INCONCLUYENTE** en cualquier otro caso. Convención: la diferencia es B − A.

Los tres rivales de evaluación (Martin, Nachi y Marco) se reservaron desde el
principio y **no se usaron para ninguna decisión previa**: ni para elegir la
recompensa, ni C0, ni K, ni la retención, ni el presupuesto, ni las semillas.

## 3. Cómo se ejecutó

Seis corridas, tres semillas por dos brazos, en el orden A1 B1 A2 B2 A3 B3.
Verificación de integridad **ciega** —sin ningún resultado de juego— antes de
tocar los rivales finales:

| Corrida | Brazo | Semilla | Muestras | Actualiz. | Instant. | Hash final | Recuperación |
|---|---|---|---|---|---|---|---|
| A1 | A | 20260907 | 504.000 | 63 | 1 | `18dba2b5d2ba05d3` | OK |
| B1 | B | 20260907 | 504.000 | 63 | 13 | `21e6d8f631158a27` | OK |
| A2 | A | 20260908 | 504.000 | 63 | 1 | `6b762725f0df3fa3` | OK |
| B2 | B | 20260908 | 504.000 | 63 | 13 | `69901f42bccd503c` | OK |
| A3 | A | 20260909 | 504.000 | 63 | 1 | `41f79cf67b63901b` | OK |
| B3 | B | 20260909 | 504.000 | 63 | 13 | `6b6350d1e571eb6b` | OK |

Las seis parten del mismo C0 y lo dejan intacto, gastan **exactamente** el mismo
presupuesto, tienen parámetros finitos, respetan su retención, sus instantáneas
cuadran con sus hashes, sus checkpoints finales son distintos entre sí y de C0,
y cada uno se recupera en un proceso nuevo con `weights_only=True`.
**Integridad: SUPERADA.**

Evaluación final: 720 partidas = 6 corridas × 3 rivales × 40 partidas, semillas
5000–5039, lados alternados por índice, modo estocástico, checkpoint **final**
de cada corrida (sin regla de selección de «el mejor»).

## 4. Resultados

**Las 720 partidas terminaron en gol.** Cero empates, cero incompletas.
Mediana de 290 pasos por partida. Los lados quedaron exactamente balanceados:
360 partidas como azul y 360 como naranja.

### Global

| Brazo | Victorias | Derrotas | Tasa de victoria |
|---|---|---|---|
| A (rival único) | 18 / 360 | 342 | **5,00 %** |
| B (pool) | 15 / 360 | 345 | **4,17 %** |

**B − A = −0,83 puntos porcentuales.**

### Por rival (120 partidas por celda)

| Rival | A | B | B − A |
|---|---|---|---|
| marco_2.0B_1024 | 10 (8,3 %) | 4 (3,3 %) | −5,0 pp |
| martin_2.1B_1024 | 4 (3,3 %) | 9 (7,5 %) | **+4,2 pp** |
| nachi_2.9B | 4 (3,3 %) | 2 (1,7 %) | −1,7 pp |

### Por semilla (120 partidas por celda)

| Semilla | A | B | B − A |
|---|---|---|---|
| 20260907 | 5 (4,2 %) | 4 (3,3 %) | −0,8 pp |
| 20260908 | 5 (4,2 %) | 6 (5,0 %) | **+0,8 pp** |
| 20260909 | 8 (6,7 %) | 5 (4,2 %) | −2,5 pp |

## 5. La incertidumbre

Intervalo de confianza bootstrap al 95 % de B − A (10.000 remuestreos, semilla
20260907): **[−3,89 pp, +2,22 pp]**.

El intervalo **contiene el cero con holgura**. La diferencia observada de
−0,83 pp es más pequeña que el rango entre semillas dentro de un mismo brazo
(2,5 pp en A, 1,7 pp en B). Dicho de otro modo: **la variación entre dos
semillas del mismo brazo es mayor que la diferencia entre brazos.** Cambiar la
semilla mueve el resultado más que cambiar el método.

El signo tampoco es estable: se invierte entre rivales (Marco favorece a A por
5 pp, Martin favorece a B por 4,2 pp) y entre semillas.

### Criterios congelados

| | Criterio | Resultado |
|---|---|---|
| 1 | el IC 95 % excluye el 0 | **No** |
| 2 | la magnitud supera el rango entre semillas | **No** |
| 3 | signo consistente en ≥ 2 de 3 semillas | Sí (2/3) |
| 4 | signo consistente en ≥ 2 de 3 rivales | Sí (2/3) |

## 6. Conclusión

# H1 queda INCONCLUYENTE.

Este experimento **no permite afirmar que el pool de rivales mejore la tasa de
victoria, ni que la empeore.** Se cumplen dos de los cuatro criterios, y fallan
precisamente los dos que miden si la diferencia es real: el intervalo de
confianza incluye el cero y la magnitud no supera el ruido entre semillas.

Conviene decir con claridad qué **no** significa esto:

- **No** significa que el autojuego con memoria no funcione. Significa que este
  montaje, con este presupuesto, no tiene resolución para detectarlo.
- **No** significa que A sea mejor que B. La diferencia de −0,83 pp es
  indistinguible de cero.
- Los 18 frente a 15 triunfos **no** son un resultado a favor de A. Son 33
  victorias repartidas entre 720 partidas, dentro del ruido.

## 7. Por qué salió inconcluyente: el efecto suelo

Ambos brazos ganan alrededor del 5 % de las partidas. Ese es el dato que
explica todo lo demás.

Los rivales de evaluación se entrenaron con entre 2.000 y 2.900 millones de
pasos. Nuestros agentes recibieron **504.000 muestras**, unas cuatro mil veces
menos. La comparación se hace, por tanto, entre dos agentes que pierden casi
siempre, contra oponentes que están fuera de su alcance.

Cuando ambos brazos están pegados al suelo, la métrica pierde capacidad de
discriminar: casi todo lo que se observa es la varianza de un suceso raro. Con
una tasa base del 5 %, distinguir de forma fiable una diferencia de 1 punto
porcentual exigiría del orden de decenas de miles de partidas, no 720.

El diseño no es defectuoso: el criterio estaba escrito de antemano, los brazos
son comparables y la ejecución es limpia. Lo que falta es **potencia
estadística**, y eso estaba determinado por el presupuesto desde el principio.

## 8. Limitaciones

1. **Presupuesto muy pequeño.** 504.000 muestras por corrida. Es una escala de
   prueba de concepto, no de entrenamiento competitivo.
2. **Efecto suelo.** Los tres rivales están muy por encima del nivel alcanzado;
   la tasa de victoria del 5 % deja poco margen para separar los brazos.
3. **La regla de retención nunca se activó.** Con presupuesto 500.000 y
   K = 40.000 salen 12 instantáneas más C0, y la retención de B era 16. El pool
   de B fue de hecho «todas las instantáneas pasadas», y la expulsión de las más
   antiguas no llegó a ejercitarse en este experimento. La lógica de expulsión
   está probada aparte en `scripts/test_pool.py`, pero no la validan estos datos.
4. **Tres semillas.** Suficientes para ver que el ruido entre semillas supera al
   efecto, insuficientes para estimar ese ruido con precisión.
5. **Un único valor de cada decisión.** K, retención y presupuesto se fijaron en
   un solo punto. No se explora su sensibilidad.
6. **Las duraciones no son comparables entre corridas.** A1 y B1 se ejecutaron
   con la máquina cargada; las otras cuatro, libres. La columna de tiempo mide
   la máquina, no el método.
7. **Sin evaluación de significación por rival.** El criterio congelado usa el
   agregado; los desgloses por rival y semilla son descriptivos.

## 9. Desviaciones del protocolo

**Ninguna decisión metodológica se cambió.** No se tocaron la recompensa, C0, K,
la retención, el presupuesto, las semillas, la arquitectura, los
hiperparámetros de PPO, el número de partidas ni el criterio de decisión. No se
descartó ninguna partida. No se seleccionó ningún checkpoint intermedio.

Sí hubo **incidencias de infraestructura**, todas registradas en
`docs/experiments/incidencias.md`:

1. Caída transitoria de rendimiento durante A1. No se intervino.
2. Muerte del envoltorio de tarea de la sesión, sin muerte del experimento. No
   se intervino.
3. **Interbloqueo entre B1 y A2**, causado por un fallo de `cleanup()` de
   `rlgym_ppo` en Windows (`WinError 10038`) que dejó estado de sockets corrupto
   para la corrida siguiente. Recuperación: se descartó la carpeta de A2 (que
   solo contenía el pool sembrado con C0, sin entrenamiento) y se relanzaron
   A2, B2, A3 y B3 en procesos independientes, cada una desde el mismo C0. A1 y
   B1 ya estaban completas y no se tocaron.
4. **La evaluación final se interrumpió en la partida 389 de 720** y se reanudó.
   El script salta las partidas ya registradas, de modo que **ninguna partida se
   jugó dos veces ni se descartó**: el conjunto de 720 está completo y es el
   fijado por el protocolo. Artefacto conocido: al reanudar, la política propia
   se carga en un punto distinto de la secuencia aleatoria, lo que puede haber
   alterado **una sola partida** (la primera reanudada de B2) respecto a una
   ejecución ininterrumpida. Se documenta por transparencia; no afecta al
   veredicto, que es inconcluyente por un margen muy superior.

## 10. Qué haría falta para responder la pregunta

Nada de esto se ha hecho, y no debe hacerse retocando este experimento:

- subir el presupuesto en uno o dos órdenes de magnitud, para salir del suelo;
- evaluar contra rivales de nivel comparable al alcanzado, no solo contra
  agentes muy superiores, de modo que la tasa de victoria caiga en una zona
  informativa;
- aumentar el número de semillas para estimar el ruido, y el de partidas para
  ganar resolución;
- forzar que la retención se active de verdad, con K menor o presupuesto mayor.

Un nuevo experimento con esos cambios sería **otro** experimento, con su propio
protocolo congelado de antemano. Reanalizar estos datos buscando un corte que
favorezca a B sería exactamente lo que el protocolo se escribió para impedir.

---

## Artefactos

| Archivo | Contenido |
|---|---|
| `experimento/eval-final.jsonl` | las 720 partidas, una por línea, con hashes de ambos agentes |
| `experimento/analisis-h1.json` | agregados, bootstrap y los cuatro criterios |
| `experimento/integridad.json` | tabla ciega de integridad y comprobaciones cruzadas |
| `experimento/<corrida>/informe.json` | configuración resuelta, métricas e integridad de cada corrida |
| `docs/experiments/incidencias.md` | las cuatro incidencias de ejecución |

Todos los agregados de este documento se derivan del JSONL mediante
`scripts/analyze_h1.py`; ninguno se acumuló a mano.
