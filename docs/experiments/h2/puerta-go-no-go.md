# H2 — Puerta GO / NO-GO

**Veredicto: NO-GO. Las diez corridas no se ejecutan.**

Fecha: 2026-09-08. Fase 0 completa; protocolo H2 **no** congelado.
H1 permanece cerrado e intacto.

---

## 1. Resultado de los cuatro criterios

Los umbrales estaban escritos en `configs/experimento/h2/fase0.json` **antes**
de entrenar nada, derivados de H1.

| | Criterio | Umbral | Medido | |
|---|---|---|---|---|
| **G1** | ≥ 3 escalones con tasa del piloto en 35–65 % | 3 | **4** | **CUMPLE** |
| **G2** | deriva del piloto ≥ 3× la de H1 | 0,0465 | **0,0310** (2,0×) | **FALLA** |
| **G3** | diversidad del pool ≥ 2× la de H1, con retención activa | 0,0148 | **0,0135** (1,82×) | **FALLA** |
| **G4** | infraestructura estable | — | sin bloqueos ni huérfanos | **CUMPLE** |

Detalle en `%LOCALAPPDATA%/rlgym-selfplay-pool/h2/fase0/puerta.json`.

### G1 — la calibración funcionó

Tasas del piloto (40 partidas cada una, semillas 9000–9039, lados alternados):

| Rival | Clase | Tasa del piloto | En zona |
|---|---|---|---|
| S@500.000 | escalón | 55,0 % | sí |
| S@1.000.000 | escalón | 55,0 % | sí |
| S@2.000.000 | escalón | 55,0 % | sí |
| S@4.000.000 | escalón | 55,0 % | sí |
| C0 | referencia | 15,0 % | no |
| diego_1.18B_512 | referencia | 0,0 % | no |

Los cuatro 55 % idénticos son **coincidencia del agregado, no partidas
repetidas**: solo 3 de 40 semillas dan el mismo resultado en los cuatro
escalones, y los patrones de victoria por semilla son visiblemente distintos.
Los lados están equilibrados. El linaje neutral sí produce una zona informativa,
que era el objetivo principal del rediseño.

### G2 — la deriva crece como una raíz, no como una recta

El diseño extrapolaba la deriva linealmente y predecía ~0,054 a 2,5 M. Medido:
**0,0310**. El error era mío: la deriva de un proceso en parte aleatorio crece
como √muestras, y el linaje neutral lo confirma casi exactamente.

| Muestras | Deriva medida | Predicción √ |
|---|---|---|
| 504.000 (H1) | 0,0156 | 0,0155 |
| 1.000.000 | 0,0223 | 0,0218 |
| 2.000.000 | 0,0305 | 0,0309 |
| 3.000.000 | 0,0360 | 0,0378 |
| 4.000.000 | 0,0403 | 0,0437 |

Y por encima de 2 M va incluso **por debajo** de la raíz. Alcanzar 3× H1
(0,0465) exigiría del orden de **6 millones de muestras por corrida**: 74 min
por corrida y **~12,3 h** para las diez. La puerta existía exactamente para
detectar esto antes de gastarlas.

### G3 — falla por poco, y tiene arreglo barato

Medido 0,0135 frente a un umbral de 0,0148, con K = 100.000 y retención 16
sobre un presupuesto de 2,5 M. La **retención sí se activó de verdad**: el
linaje neutral creó 41 instantáneas y conservó 16, expulsando 25.

Midiendo sobre el archivo del linaje neutral qué configuraciones alcanzarían el
umbral, **sin tocar el presupuesto** y sin mirar ninguna tasa de victoria:

| K | Retención | Presupuesto | Instantáneas | Mediana | |
|---|---|---|---|---|---|
| 100.000 | 16 | 2,5 M | 16 | 0,0135 | falla |
| **150.000** | **16** | **2,5 M** | **24** | **0,0174** | **cumple** |
| 100.000 | 24 | 2,5 M | 24 | 0,0174 | cumple |
| 200.000 | 16 | 4 M | 33 | 0,0193 | cumple |

Con **K = 150.000 y retención 16** el criterio se cumpliría con el presupuesto
de 2,5 M ya previsto.

### G4 — la infraestructura aguantó

Un proceso por corrida, cero huérfanos, cero cortes por estancamiento, C0
intacto, checkpoint final presente y recuperable en proceso nuevo, reanudación
idempotente verificada por log. Las trazas `WinError 10038` siguen apareciendo
al cerrar cada corrida y ahora sí son inofensivas: ningún proceso ejecuta una
segunda corrida.

Dos incidencias propias, ambas corregidas:

1. Un corte de la sesión mató el árbol completo a mitad del linaje neutral. Se
   relanzó **desacoplado** de la sesión y se rehízo entero desde C0.
2. Marqué el linaje neutral como INCOMPLETA habiendo terminado bien: buscaba el
   checkpoint final dentro de `checkpoints/`, cuando rlgym-ppo escribe en la
   hermana `checkpoints-<id>/<ts>/`. Corregido en el código y reparado el
   marcador **sin reentrenar**, tras verificar de nuevo desde disco las seis
   condiciones. La reparación queda registrada dentro del propio informe.

---

## 2. El hallazgo que no estaba previsto, y que pesa más que G2 y G3

Durante la calibración, el piloto ganó solo el **15 %** contra C0. Como eso no
encajaba, se comprobó si le pasaba solo a él. **No: le pasa a todo el mundo.**

| Agente | Muestras entrenadas | Tasa contra C0 |
|---|---|---|
| S@500.000 | 500.000 | 42,5 % |
| S@1.000.000 | 1.000.000 | 17,5 % |
| S@2.000.000 | 2.000.000 | 32,5 % |
| S@4.000.000 | 4.000.000 | 22,5 % |
| P (control) | 2.500.000 | 15,0 % |

40 partidas cada uno, lados alternados. **Los cinco agentes entrenados pierden
contra su propio punto de partida**, y la relación no es ni siquiera monótona:
el de 500.000 muestras es el mejor de los cinco.

Con 40 partidas por emparejamiento el margen de error ronda ±15 puntos, así que
ninguna cifra individual es concluyente. Pero **cinco de cinco por debajo del
50 %, cuatro de ellas muy por debajo**, no es ruido.

### Por qué esto invalida la premisa

H1 y H2 comparan brazos por **tasa de victoria**. Eso presupone que entrenar
más mejora la tasa de victoria. Bajo esta recompensa, **no la mejora: la
empeora**. La deriva medida es consistente con una política que se aleja de C0
sin jugar mejor, y encaja con lo que ya sabíamos: la recompensa `stage_1_basics`
es mayoritariamente moldeada (velocidad hacia la pelota, orientación, velocidad
de la pelota a portería) y el término de gol pesa poco en comparación.

Subir el presupuesto a 6 M para superar G2 **no arregla esto**. Compararía dos
formas de empeorar, con más resolución.

---

## 3. Recomendación

**No ejecutar H2 tal como está diseñado, ni siquiera con más presupuesto.**

El orden correcto es:

1. **Primero, validar el objetivo.** Antes de gastar 12 h de entrenamiento, hay
   que responder una pregunta más básica y mucho más barata: *¿existe alguna
   configuración de recompensa bajo la cual entrenar mejore la tasa de victoria
   contra una referencia fija?* Mientras la respuesta sea no, la tasa de
   victoria no sirve como variable primaria y ningún experimento A/B sobre ella
   significa nada.

2. **Diagnóstico sugerido, barato**: entrenar dos o tres linajes cortos
   (500.000 muestras, ~7 min cada uno) con recompensas distintas —por ejemplo
   subiendo el peso del término de gol, o sin la envoltura `ZeroSumReward`— y
   medir cada uno contra C0 con el `duel.py` ya escrito. Coste total bajo el
   medio día. El criterio es simple y se fija de antemano: **la tasa contra C0
   debe superar el 50 % y crecer con el presupuesto.**

3. **Solo si eso se resuelve**, rehacer la puerta de H2 con:
   - **K = 150.000 y retención 16**, que ya cumple G3 con 2,5 M (medido: 0,0174);
   - el presupuesto que exija G2 con la recompensa nueva, recalculado con la ley
     √ ya medida, no extrapolando de nuevo en línea recta.

4. **Alternativa, si se prefiere no tocar la recompensa**: cambiar la variable
   primaria a una alineada con lo que el entrenamiento realmente optimiza. Es
   legítimo, pero **cambia la pregunta**: dejaría de ser «¿el pool hace ganar
   más partidas?» para ser «¿el pool mejora el retorno moldeado?». Hay que
   decirlo así de claro y no presentarlo como lo mismo.

Lo que **no** hay que hacer: bajar los umbrales de G2 o G3 para que la puerta
pase, ni elegir la recompensa mirando cuál favorece al brazo B.

---

## 4. Decisiones ya fijadas que siguen en pie

Aunque el veredicto sea NO-GO, esto queda escrito y no debe cambiarse después
de ver resultados:

- **Semillas de entrenamiento H2**: 20260941, 20260942, 20260943, 20260944,
  20260945. Emparejadas A/B. Distintas de las de H1 (20260907–09), del linaje
  neutral (20260931) y del piloto (20260932).
- **Semillas de partida**: calibración 9000–9039 (ya gastadas), finales
  7000–7059, sin reutilizar las de H1 (5000–5039).
- **Método estadístico principal**: bootstrap jerárquico emparejado por semilla,
  remuestreando primero semillas y después partidas. Unidad experimental: la
  corrida. El logístico de efectos mixtos queda como secundario y no puede
  sustituirlo a posteriori.
- **Criterio**: A FAVOR si el IC 95 % de la media de las diferencias por semilla
  excluye el 0 y el signo es consistente en ≥ 4 de 5 semillas; EN CONTRA con el
  signo invertido; INCONCLUYENTE en cualquier otro caso.
- **Martin, Nachi y Marco quedan fuera de H2.** Diego, solo como referencia
  secundaria.

---

## 5. Artefactos de la fase 0

| Ruta | Contenido |
|---|---|
| `h2/fase0/S/` | linaje neutral, 4 M, 4 hitos, 41 instantáneas archivadas |
| `h2/fase0/P/` | piloto de control, 2,5 M |
| `h2/fase0/calibracion.jsonl` | 240 partidas del piloto |
| `h2/fase0/puerta.json` | los cuatro criterios con sus números |
| `h2/prueba/` | prueba corta de infraestructura |

Nada de esto forma parte de un resultado experimental, y así está marcado en
cada informe (`no_forma_parte_del_resultado_experimental: true`).

**H1 sigue intacto**: protocolo `8ae06382…`, 720 partidas, veredicto
INCONCLUYENTE.
