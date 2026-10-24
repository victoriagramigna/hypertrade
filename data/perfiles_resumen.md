# Perfil de las alertas que rindieron (2026-10-24)

Casos con resultado a 20 ruedas: 151. Exploratorio: genera hipotesis, no reglas. Informativo.

Candidato = p < 0.0038 (corregido por 13 datos), |AUC-0.5| >= 0.15, misma direccion en las dos mitades por fecha.
AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.

## TODAS: 151 casos (76 ganan vs SPY, 75 pierden), 7 dias distintos, mediana vs SPY 0.01

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.329 | 0.0007 | 47.35 | 56.0 | 0.27 | 0.405 | SI |
| radar_score | 0.652 | 0.001 | 54.7 | 46.3 | 0.703 | 0.582 | SI |
| regimen_score | 0.404 | 0.3179 | 64.0 | 68.0 | None | None | no |
| apoyo_avwap | 0.596 | 0.1953 | 1.0 | 1.0 | None | None | no |
| dist_max52w_pct | 0.588 | 0.2889 | -11.4 | -16.9 | None | None | no |
| vol_rel | 0.419 | 0.0893 | 0.32 | 0.46 | 0.578 | 0.317 | no |

## Recién cruzó, sin confirmar: 49 casos (26 ganan vs SPY, 23 pierden), 6 dias distintos, mediana vs SPY 1.4

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| radar_score | 0.714 | 0.0077 | 53.6 | 42.4 | 0.766 | 0.579 | no |
| rs_score | 0.594 | 0.2639 | 51.9 | 48.5 | 0.562 | 0.702 | no |
| rsi | 0.414 | 0.3076 | 46.45 | 53.4 | 0.32 | 0.563 | no |
| vcp_valido | 0.549 | 0.5638 | 1.0 | 0.0 | 0.656 | 0.464 | no |
| vol_rel | 0.454 | 0.5848 | 0.23 | 0.33 | 0.598 | 0.282 | no |

## Gap alcista con macrotendencia: 30 casos (8 ganan vs SPY, 22 pierden), 6 dias distintos, mediana vs SPY -10.16

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| vol_rel | 0.315 | 0.14 | 0.32 | 0.41 | None | None | no |
| rsi | 0.352 | 0.2286 | 59.45 | 64.8 | None | None | no |
| rs_score | 0.415 | 0.5052 | 88.35 | 91.95 | None | None | no |
| radar_score | 0.429 | 0.5725 | 42.2 | 51.45 | None | None | no |

## Confirmado: 29 casos (18 ganan vs SPY, 11 pierden), 5 dias distintos, mediana vs SPY 2.83

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| radar_score | 0.821 | 0.004 | 54.8 | 41.6 | None | None | no |
| vol_rel | 0.389 | 0.3336 | 0.31 | 0.3 | None | None | no |
| rs_score | 0.609 | 0.3266 | 56.95 | 43.6 | None | None | no |
| rsi | 0.442 | 0.6261 | 51.0 | 53.3 | None | None | no |
| vcp_valido | 0.543 | 0.6961 | 1.0 | 1.0 | None | None | no |

Sin analizar por muestra chica: Líder apoyando en soporte (6), Rompió piso (SMA200) (8), Sacudón, sin definición clara (16), Perdió EMA200 tras rebote - stop sugerido (1), Confluencia Alcista (12)
