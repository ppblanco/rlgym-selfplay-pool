# Comprobación final de recompensa — resultados y cierre

Protocolo congelado **antes** de entrenar:
`configs/experimento/reward-final-check/protocolo.json`
**SHA256 `6c2a8cb2001bf9f732043f3fa8eb6ebef92fd87531dc10a1238e3c99131a000d`**

Fecha: 2026-09-08. Última prueba diagnóstica autorizada.

H1 sigue cerrado como INCONCLUYENTE. La puerta de H2 sigue en NO-GO. El
diagnóstico anterior (D_A/D_B/D_C) queda intacto.

---

## 1. La pregunta

No era «qué recompensa da el porcentaje más alto», sino:

> ¿Reducir o eliminar el *shaping* denso evita que entrenar más deteriore la
> capacidad de juego frente al punto de partida?

La hipótesis a contrastar, formulada en el diagnóstico anterior, era que los
términos moldeados dominaban al objetivo deportivo en un orden de magnitud —
0,30 por paso durante hasta 300 pasos frente a 8,0 por un gol— y que **reducir
el moldeado debería mejorar el resultado**.

## 2. Las dos configuraciones

Ambas parten literalmente de `stage_1_basics` heredado, verificadas componente a
componente contra el YAML original:

| | R1 · shaping reducido | R2 · solo evento |
|---|---|---|
| velocity_player_to_ball | 0,10 → **0,010** | **eliminado** |
| face_ball | 0,05 → **0,005** | **eliminado** |
| velocity_ball_to_goal | 0,30 → **0,030** | **eliminado** |
| event | **8,0, intacto** (gol 1,0 · encajar −1,0 · tiro 0,1 · demo 0,1) | **8,0, intacto**, mismos kwargs |
| ZeroSum / team_spirit / opp_scale | sin tocar (sí / 0,0 / 1,0) | sin tocar (sí / 0,0 / 1,0) |

SHA256: R1 `621a1835ec664bdd…`, R2 `797fe484fb9f5764…`.

Idéntico en las dos: mismo C0, semilla 20260951 (la misma del diagnóstico
anterior, para que sean comparables), arquitectura 512×3, 2 trabajadores con 1
hilo, lote 8.000, mismos hiperparámetros de PPO, 500.000 muestras, rival C0
fijo, un proceso por configuración, checkpoints a 100k/250k/500k.

Evaluación: 200 partidas por checkpoint contra C0, **semillas 13000–13199**
—nuevas, sin solaparse con las de H1 (5000–5039), la calibración de H2
(9000–9039), las finales previstas (7000–7059) ni el diagnóstico anterior
(11000–11199)—, lados 100/100, modo estocástico. 1.200 partidas.

## 3. Resultados

| Config | 100k | 250k | 500k | IC95 a 500k | Tendencia | Estabilidad | Veredicto |
|---|---|---|---|---|---|---|---|
| **R1** shaping reducido | 9,5 % | 4,5 % | **2,0 %** | [0,8 %, 5,0 %] | deterioro | entropía 4,40 · vf 0,104 · finita | **NO PROMETEDORA** |
| **R2** solo evento | 11,5 % | 2,0 % | **2,5 %** | [1,1 %, 5,7 %] | deterioro | entropía 4,44 · vf 0,147 · finita | **NO PROMETEDORA** |

Ninguna alcanza siquiera el primer requisito: la tasa a 500k debía superar el
50 % y se queda en el 2 %. No hace falta evaluar los demás criterios, pero se
deja constancia: ambas entrenaron sin error, con parámetros finitos, sin NaN y
sin colapso de entropía. **El fracaso no es de estabilidad numérica.**

Deriva desde C0: R1 0,0144 y R2 0,0154 a 500k, prácticamente igual que las
configuraciones anteriores (0,0157). Como antes, **la recompensa no cambia
cuánto se mueve la política, sino hacia dónde** — y aquí la mueve hacia mucho
peor.

## 4. Mi hipótesis queda falsada

Predije que reducir el moldeado mejoraría el resultado. Ocurre lo contrario, y
no por poco:

| Configuración | Moldeado | Tasa a 500k |
|---|---|---|
| D_A `stage_1_basics` | completo (0,10 / 0,05 / 0,30) | **61,5 %** |
| D_B `stage_2_offense` | rebalanceado (0,03 / — / 0,60) | 22,5 % |
| D_C `stage_2_offense` sin ZeroSum | igual que D_B | 16,0 % |
| **R1** | **dividido por 10** | **2,0 %** |
| **R2** | **eliminado** | **2,5 %** |

El orden es inequívoco: **cuanto menos moldeado, peor**. Dividirlo por diez
hunde el rendimiento de 61,5 % a 2,0 %; eliminarlo del todo deja 2,5 %.

La explicación es la contraria de la que propuse. Con `event` como única señal
—o casi—, el aprendizaje se queda **sin gradiente útil**: los goles son sucesos
raros, así que la mayoría de los pasos no aportan información y la política
deriva sin rumbo. Y como C0 sí fue entrenado con el moldeado completo, tiene
competencia que R1 y R2 destruyen en vez de construir.

Es decir: el moldeado denso no era el problema, era **lo único que sostenía el
aprendizaje**. Mi razonamiento sobre la magnitud relativa de los términos era
aritméticamente correcto pero irrelevante: confundí «qué término domina la suma
de la recompensa» con «qué término aporta señal aprovechable».

## 5. Qué queda en pie, y qué no

Se mantiene, ahora con más evidencia: **entrenar más deteriora la tasa de
victoria frente a C0 en todas las configuraciones probadas**. Las cinco caen
entre 100k y 500k. Esto ya no depende de la recompensa concreta.

Se cae: la explicación que yo había dado de ese deterioro. No es que el moldeado
dominara al objetivo deportivo. La causa sigue **sin identificar**, y esta
prueba la acota: no es exceso de moldeado, no es la envoltura ZeroSum, no es
inestabilidad numérica y no es sobreajuste al rival, porque el rival de
entrenamiento y el de evaluación son el mismo C0.

## 6. Conclusión

**Ninguna configuración es PROMETEDORA. Se cierra la línea experimental de
recompensas**, conforme a lo acordado antes de ejecutar: no habrá R3, ni H3, ni
vuelta a H2, ni más pruebas de pesos.

### Qué deja el proyecto

Un resultado negativo bien documentado, que es un resultado:

- **Infraestructura reproducible**: un proceso por corrida, detección de
  estancamiento y de huérfanos, reanudación idempotente, marcador
  COMPLETA/INCOMPLETA, JSONL sin duplicados, recuperación de checkpoints
  verificada en proceso nuevo.
- **Pool histórico implementado** y probado: retención con protección de C0 y
  expulsión determinista, ejercitada de verdad (41 instantáneas creadas, 16
  conservadas, 25 expulsadas).
- **Protocolo experimental** con criterios congelados por SHA256 antes de
  ejecutar, en tres ocasiones distintas, y respetados incluso cuando el
  resultado fue incómodo — H1 inconcluyente, H2 en NO-GO por 0,0155 de deriva,
  D_A descartada por 0,5 puntos porcentuales.
- **H1**: inconcluyente, con 720 partidas y análisis preinscrito.
- **H2**: detenido por una puerta que hizo exactamente su trabajo, evitando
  gastar 12 horas de cómputo en un experimento condenado.
- **Diagnóstico de reward shaping**: cinco configuraciones, 3.000 partidas de
  evaluación, con una hipótesis propia formulada y después falsada por los
  datos.

### Lo que quedaría por explicar, si algún día se retoma

Por qué el rendimiento frente a C0 decae con el presupuesto en todas las
configuraciones. Las sospechas razonables que **no** se han probado: que C0 esté
en un óptimo local peculiar del que cualquier entrenamiento se aleja; que el
horizonte de 300 pasos y γ = 0,99 no case con la escala temporal de un gol; o
que `standardize_returns` interactúe mal con recompensas casi siempre nulas.
Nada de esto se ha comprobado y no debe presentarse como conclusión.

---

## Artefactos

| Ruta | Contenido |
|---|---|
| `configs/experimento/reward-final-check/protocolo.json` | protocolo congelado |
| `configs/experimento/reward-final-check/protocolo.sha256` | `6c2a8cb2001bf9f7…` |
| `configs/experimento/reward-final-check/r1_shaping_reducido.yaml` | R1, SHA `621a1835ec664bdd…` |
| `configs/experimento/reward-final-check/r2_solo_evento.yaml` | R2, SHA `797fe484fb9f5764…` |
| `final-check/R1/informe.json`, `final-check/R2/informe.json` | configuración resuelta, hitos con hash, métricas |
| `final-check/duelos.jsonl` | las 1.200 partidas con semilla, lado, hashes y resultado |
| `final-check/resumen_*.json` | agregados con IC de Wilson |

Hashes de los checkpoints evaluados:

| Config | 100k | 250k | 500k |
|---|---|---|---|
| R1 | `5bfab2ac6c5b3f5c…` | `ae52cd03b00cecaf…` | `38e724e0d5fe5f23…` |
| R2 | `f7b0226abe7f1da4…` | `dd20cfb040cc815b…` | `ed317e811148c1cf…` |
