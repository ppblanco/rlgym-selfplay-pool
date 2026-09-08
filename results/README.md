# Resultados

Todo lo necesario para verificar las conclusiones **sin distribuir un solo peso
de modelo**. Son archivos de texto: partidas, agregados e informes.

| Carpeta | Contenido |
|---|---|
| `h1/` | las 720 partidas de la evaluación final, el análisis con el criterio congelado, la tabla ciega de integridad y los 6 informes de corrida |
| `h2/` | las 240 partidas de calibración, los cuatro criterios de la puerta GO/NO-GO y los informes del linaje neutral y del piloto |
| `reward-diagnostic/` | 1.800 duelos de D_A/D_B/D_C contra C0, con sus resúmenes e informes |
| `reward-final-check/` | 1.200 duelos de R1/R2 contra C0, con sus resúmenes e informes |

## Cómo leerlos

Cada línea de un `.jsonl` es una partida, con su semilla, el lado, el resultado
y los **hashes SHA256** de las dos políticas que jugaron. Los agregados se
derivan de ahí; ninguno se acumuló a mano.

```bash
python scripts/analyze_h1.py --jsonl results/h1/eval-final.jsonl --salida out.json
```

## Avisos

- **Los informes están saneados**: la ruta local absoluta de la máquina de
  ejecución se sustituyó por `%LOCALAPPDATA%`. Ningún valor numérico se tocó.
- **Las partidas de protocolos distintos no se agregan.** Sumar los 3.960
  duelos para calcular una tasa conjunta no tendría sentido: proceden de
  experimentos con rivales, presupuestos y criterios diferentes.
- **Los pesos no están aquí** y no se redistribuyen. Los hashes permiten
  comprobar la identidad de cada política, no reconstruirla.
