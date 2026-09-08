# Incidencias de ejecución del experimento

Protocolo congelado: `8ae06382c83a85cae0bd5d68dc0f2d40b763e3dce9d5d81159393b45306f580e`
Fecha de ejecución: 2026-09-07

Este documento registra todo lo que se salió de lo previsto durante las seis
corridas, **antes** de mirar ningún resultado de juego. Se escribe para que el
lector pueda juzgar por sí mismo si algo de esto compromete la comparación.

**Ninguna incidencia cambió una decisión metodológica.** No se tocaron la
recompensa, C0, K, la retención, el presupuesto, las semillas, la arquitectura,
los hiperparámetros de PPO ni las reglas de evaluación. Por eso se registran
como **incidencias de infraestructura**, no como desviaciones del protocolo.

---

## 1. Caída transitoria de rendimiento durante A1

**Qué pasó.** Entre las iteraciones 20 y 30 de A1, el tiempo de recolección
subió de ~2 s a 61 s por iteración, y después se recuperó solo hasta 7,6 s.

**Qué se descartó como causa.** No hubo fuga de memoria (aprendiz 450 MB,
trabajadores 258 MB cada uno), ni falta de núcleos (12 lógicos, 3 procesos del
proyecto), ni recarga de políticas desde disco (`EntornoPool` las cachea por id
de instantánea). La causa fue contención externa de CPU en la máquina.

**Qué se hizo.** Nada. Se dejó correr.

**Efecto en los resultados.** Ninguno sobre el aprendizaje: el presupuesto se
mide en muestras, no en tiempo. Sí afecta a la duración registrada de A1
(1.257 s), que por eso no es comparable con la de las demás corridas. Las
duraciones de esta tabla miden la máquina, no la calidad del método.

---

## 2. Muerte del envoltorio de tarea, sin muerte del experimento

**Qué pasó.** El envoltorio de la tarea en segundo plano de la sesión fue
terminado mientras B1 entrenaba. El árbol de procesos de Python sobrevivió,
porque escribía a un archivo de log y no a la tubería que se cerró.

**Qué se hizo.** Nada sobre el experimento. Se comprobó que el log seguía
avanzando (B1 pasó de 112.000 a 192.000 durante la comprobación) y se rearmó
la señal de finalización.

**Efecto en los resultados.** Ninguno. Reiniciar aquí habría sido el error:
habría destruido una corrida sana en curso.

---

## 3. Interbloqueo en la transición de B1 a A2  ← la incidencia seria

**Qué pasó.** B1 terminó correctamente a las 21:32:52 y dejó su informe. La
carpeta de A2 se creó en ese mismo segundo y su pool se sembró con C0. A2 llegó
a lanzar sus dos trabajadores (`Initializing processes... 2/2`) y ahí se detuvo.

**Diagnóstico.** Bloqueo total, no lentitud:

| Comprobación | Resultado |
|---|---|
| CPU del proceso | 1.464,8 s → 1.464,8 s: 0,00 s en 25 s |
| Hilos | los 16 en estado `Wait` |
| Procesos trabajadores | ninguno vivo |
| Log | 15 min sin escribirse |

**Causa.** Al cerrar cada corrida, `rlgym_ppo/batched_agents/batched_agent_manager.py:506`
lanza `OSError [WinError 10038]` en `cleanup()`: intenta operar sobre un socket
que ya no lo es. Es un defecto de la biblioteca original en Windows. Para la
corrida que termina es inofensivo, porque ya guardó su informe. Para la
**siguiente corrida del mismo proceso** no lo es: hereda el estado de sockets
corrupto y su gestor se queda esperando a unos trabajadores que nunca responden.

Estas trazas aparecieron también al final de A1, y en su momento se juzgaron
inofensivas. Lo eran para A1; no para lo que venía después. El error de juicio
fue declararlas inofensivas en general tras observarlas en un solo caso.

**Qué se hizo.**

1. Se terminó el árbol de procesos bloqueado.
2. Se descartó la carpeta A2, que contenía 2 archivos (el pool sembrado con C0)
   y ningún entrenamiento.
3. Se relanzaron A2, B2, A3 y B3 **en invocaciones independientes**, una por
   proceso, con la opción `--solo` que el script ya tenía.

**Por qué esto no es una desviación.** El protocolo exige que cada corrida
empiece desde el mismo C0 original. Aislar cada corrida en su propio proceso
hace eso *más* literalmente cierto, no menos: elimina toda herencia de estado
entre corridas. No cambia ningún parámetro, ni el orden, ni las semillas.
A1 y B1, ya completas, no se tocaron.

**Efecto en los resultados.** Ninguno sobre la comparación A/B. Sí sobre las
duraciones: A1 y B1 se ejecutaron con la máquina cargada y con estado
compartido; A2, B2, A3 y B3 en procesos limpios y con la máquina libre, y son
entre 2 y 3 veces más rápidas. **Las duraciones no deben leerse como una
diferencia entre brazos.**

---

## 4. Efecto colateral: `resumen-ejecuciones.json` quedó parcial

**Qué pasó.** Cada invocación con `--solo` reescribe
`resumen-ejecuciones.json` con la única corrida que ejecutó. El archivo final
contiene solo B3.

**Qué se hizo.** Nada, porque no hace falta: la tabla de integridad y la
evaluación final leen los `informe.json` individuales de cada corrida, que están
completos e intactos. El agregado fiable es `integridad.json`.

---

## Estado de integridad tras las seis corridas

Verificado con `scripts/integrity_table.py`, **antes** de usar ningún rival
final: las seis corridas gastaron 504.000 muestras en 63 actualizaciones,
parten del mismo C0 y lo dejan intacto, respetan su retención, tienen
parámetros finitos, sus instantáneas cuadran con sus hashes, sus seis
checkpoints finales son distintos entre sí y distintos de C0, y cada uno se
recupera en un proceso nuevo con `weights_only=True` produciendo una acción
válida. Las tres semillas están emparejadas A/B.

**Veredicto: integridad SUPERADA.**
