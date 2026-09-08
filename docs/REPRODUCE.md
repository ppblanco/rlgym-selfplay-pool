# Reproducción

Qué se puede volver a ejecutar, qué necesita material local, qué no puede
redistribuirse y qué sale caro repetir.

Las rutas personales se abrevian como `$DATOS` =
`%LOCALAPPDATA%\rlgym-selfplay-pool\`. Nada pesado vive en el repositorio.

---

## Entorno

| | |
|---|---|
| Python | 3.11.16 |
| Dependencias | `requirements/lock-2026-09-07.txt` |
| Plataforma | Windows 11, CPU (sin GPU) |
| Rendimiento observado | 1.100–1.350 muestras/s con 2 trabajadores |
| Telemetría | W&B desactivado (`WANDB_MODE=disabled`) |

Verificación previa: `python scripts/preflight.py`

---

## A. Reproducible directamente

Solo necesita el repositorio y los JSONL de resultados. **No entrena nada.**

```bash
# Veredicto de H1 desde las 720 partidas
python scripts/analyze_h1.py --jsonl $DATOS/experimento/eval-final.jsonl \
    --salida /tmp/analisis-h1.json

# Tabla ciega de integridad de las seis corridas
python scripts/integrity_table.py --experimento $DATOS/experimento

# Puerta GO/NO-GO de H2
python scripts/h2/gate_check.py --fase0 $DATOS/h2/fase0 \
    --jsonl $DATOS/h2/fase0/calibracion.jsonl --salida /tmp/puerta.json
```

Los tres criterios están congelados en el código y en los protocolos: dan el
mismo veredicto siempre.

**Verificación de protocolos** (no necesita nada más):

```bash
python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('configs/experimento/protocolo.json').read_text(encoding='utf-8').rstrip('\n').encode()).hexdigest())"
# debe coincidir con configs/experimento/protocolo.sha256
```

| Protocolo | SHA256 de esta copia pública |
|---|---|
| H1 | `c6506d17ec164a39eef6bc2063d3fa9ab8e6c23e9a6d63889044c364a02aff30` |
| H2 fase 0 | `4eca11b25352be355b89a2ca5236b40ffc1d1a1565db9e1f9f19438b043c05f2` |
| Diagnóstico de recompensas | `655adfc0abd749ff27bbd6fbdc44bddeafd802a51602f1a33b0066fc0f776608` |
| Prueba final R1/R2 | `2e69b352712131feef2ffebd84865a84a8b0cf229018099a6961ff89c744cd87` |

> **Estos no son los hashes de preregistro.** Los originales contenían una ruta
> local que se ha redactado por privacidad, así que los bytes —y el hash—
> cambian. La correspondencia entre ambos está en la tabla de trazabilidad de
> `FINAL_REPORT.md`. El contenido metodológico es idéntico: se verificó campo a
> campo que lo único distinto es la cadena de ruta.

---

## B. Requiere artefactos locales

Necesita cosas que **no están en el repositorio** y hay que obtener aparte:

| Artefacto | Qué es | Cómo se obtuvo |
|---|---|---|
| `$DATOS/collision_meshes/` | mallas de colisión de RocketSim | extraídas localmente; **no se redistribuyen** |
| `$DATOS/runs/C0_v2_stage1/` | C0, punto de partida común (32.000 muestras) | entrenado localmente con `stage_1_basics` |
| `$DATOS/artifacts/` | checkpoints de referencia ajenos | de terceros; **no se redistribuyen** |

Con eso disponible:

```bash
# Entrenar una configuración de recompensa (500k muestras, ~6-7 min)
python scripts/reward_diagnostic/train_diag.py \
    --config configs/experimento/reward-final-check/protocolo.json \
    --id R1 --meshes $DATOS/collision_meshes --raiz-salida $DATOS/final-check

# Duelo contra C0 (200 partidas, ~2 min)
python scripts/h2/duel.py --meshes $DATOS/collision_meshes \
    --a $DATOS/final-check/R1/hitos/h_000500000 --b $DATOS/runs/C0_v2_stage1 \
    --nombre-a R1@500k --nombre-b C0 --partidas 200 --semilla-inicial 13000
```

**Determinismo:** las semillas están fijadas y las políticas se cargan por
adelantado, así que la reanudación no altera el estado aleatorio. Aun así, el
entrenamiento con dos trabajadores **no es bit a bit reproducible**: el orden de
llegada de la experiencia varía. Los checkpoints de una repetición no tendrán el
mismo hash. Es una limitación real y está declarada.

---

## C. No redistribuible

**Nunca subir a un repositorio público:**

| | Motivo |
|---|---|
| `collision_meshes/` | material del juego; su presencia en otros repositorios no es autorización general |
| `artifacts/` (Martin, Nachi, Marco, Diego) | checkpoints de terceros, sin licencia que permita redistribuirlos |
| `runs/`, `experimento/`, `h2/`, `diagnostico/`, `final-check/` | pesos entrenados; además son grandes (0,54 GB solo en políticas) |
| Cualquier `*.pt` | ya excluido por `.gitignore` |

El `.gitignore` heredado ya cubre `*.pt`, `runs/`, `collision_meshes/`, `*.log`,
`checkpoints/*`, `videos/*` y `teammates/*/`. No hay ningún archivo mayor de
1 MB fuera de `.git`.

**Sí se puede publicar**: el código propio, los protocolos, los documentos y los
JSONL de resultados (son texto, contienen hashes y resultados, no pesos).

---

## D. Costoso de repetir

Tiempos medidos en esta máquina, no estimados:

| Qué | Coste |
|---|---|
| Las 6 corridas de H1 (504.000 muestras cada una) | ~1 h |
| Evaluación final de H1 (720 partidas) | ~4 min |
| Linaje neutral de H2 (4 M muestras) | ~50 min |
| Piloto de H2 (2,5 M) | ~31 min |
| Calibración de H2 (240 partidas) | ~2 min |
| Cada configuración de recompensa (500.000) | ~6–7 min |
| Cada tanda de duelos (600 partidas) | ~5 min |
| **Total del proyecto** | **~3 h de cómputo registrado** |

Si solo se quiere comprobar que el sistema funciona, la prueba corta de
infraestructura cuesta **2 minutos**:

```bash
python scripts/h2/driver_h2.py --raiz-salida $DATOS/h2/prueba \
    --meshes $DATOS/collision_meshes --linajes sparring,piloto \
    --presupuesto 32000 --hitos 16000,32000
```

Comprueba: un proceso por corrida, cero huérfanos, marcador COMPLETA,
reanudación idempotente y recuperación de checkpoints en proceso nuevo.

---

## Orden completo, si se quisiera repetir todo

1. `preflight.py` → entorno correcto.
2. Obtener mallas y entrenar C0 (32.000 muestras con `stage_1_basics`).
3. `run_experiment.py` con el protocolo de H1 → 6 corridas.
4. `integrity_table.py` → tabla ciega. **No continuar si falla.**
5. `eval_final.py` **una sola vez** → 720 partidas.
6. `analyze_h1.py` → veredicto.

Los pasos 4 y 5 en ese orden son parte del método: la integridad se comprueba
**antes** de mirar ningún resultado de juego.
