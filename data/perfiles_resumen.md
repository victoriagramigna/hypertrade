# Perfil de las alertas que rindieron (2026-10-31)

Casos con resultado a 20 ruedas: 331. Exploratorio: genera hipotesis, no reglas. Informativo.

Candidato = p < 0.0038 (corregido por 13 datos), |AUC-0.5| >= 0.15, misma direccion en las dos mitades por fecha.
AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.

## TODAS: 331 casos (154 ganan vs SPY, 177 pierden), 13 dias distintos, mediana vs SPY -1.1

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.362 | 0.0003 | 47.9 | 53.6 | 0.329 | 0.394 | no |
| dist_max52w_pct | 0.625 | 0.0013 | -10.5 | -17.1 | 0.588 | 0.633 | no |
| vcp_valido | 0.617 | 0.0013 | 1.0 | 0.0 | 0.578 | 0.63 | no |
| radar_score | 0.603 | 0.0013 | 54.65 | 50.4 | 0.652 | 0.57 | no |
| rs_score | 0.403 | 0.0023 | 65.8 | 74.1 | 0.425 | 0.405 | no |
| regimen_score | 0.585 | 0.0297 | 62.0 | 61.0 | 0.404 | 0.542 | no |

## Confluencia Alcista: 83 casos (37 ganan vs SPY, 46 pierden), 7 dias distintos, mediana vs SPY -1.35

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rs_score | 0.385 | 0.071 | 69.5 | 76.0 | 0.375 | 0.397 | no |
| dist_max52w_pct | 0.613 | 0.076 | -7.5 | -9.25 | 0.681 | 0.573 | no |
| cruce_avwap_52w | 0.596 | 0.0963 | 1.0 | 1.0 | 0.762 | 0.487 | no |
| vol_rel | 0.431 | 0.2672 | 0.1 | 0.12 | 0.392 | 0.44 | no |
| atr_contraction | 0.551 | 0.3206 | 0.0 | 0.0 | 0.413 | 0.631 | no |
| rsi | 0.453 | 0.4862 | 49.1 | 50.5 | 0.594 | 0.365 | no |

## Recién cruzó, sin confirmar: 81 casos (39 ganan vs SPY, 42 pierden), 12 dias distintos, mediana vs SPY -0.32

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| regimen_score | 0.678 | 0.0383 | 62.0 | 61.0 | None | None | no |
| radar_score | 0.638 | 0.036 | 53.5 | 45.05 | 0.739 | 0.518 | no |
| var_spy_dia_pct | 0.367 | 0.13 | 0.03 | 0.03 | None | None | no |
| rsi | 0.37 | 0.0417 | 47.1 | 53.5 | 0.497 | 0.259 | no |
| dist_max52w_pct | 0.626 | 0.1549 | -16.7 | -19.8 | None | None | no |
| cruce_avwap_52w | 0.59 | 0.2616 | 0.0 | 0.0 | None | None | no |

## Confirmado: 56 casos (29 ganan vs SPY, 27 pierden), 11 dias distintos, mediana vs SPY 0.45

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| radar_score | 0.798 | 0.0003 | 55.5 | 45.0 | 0.81 | 0.813 | SI |
| dist_max52w_pct | 0.79 | 0.0023 | -12.25 | -35.0 | 1.0 | 0.744 | SI |
| vcp_valido | 0.658 | 0.0337 | 1.0 | 0.0 | 0.517 | 0.739 | no |
| apoyo_avwap | 0.639 | 0.1086 | 1.0 | 0.5 | 0.775 | 0.599 | no |
| regimen_score | 0.631 | 0.1776 | 62.0 | 61.0 | None | None | no |
| vol_rel | 0.374 | 0.102 | 0.3 | 0.77 | 0.32 | 0.445 | no |

## Gap alcista con macrotendencia: 44 casos (12 ganan vs SPY, 32 pierden), 11 dias distintos, mediana vs SPY -10.16

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.221 | 0.0037 | 57.85 | 66.9 | 0.382 | 0.117 | SI |
| vol_rel | 0.299 | 0.044 | 0.29 | 0.42 | 0.287 | 0.333 | no |
| rs_score | 0.309 | 0.052 | 86.3 | 94.0 | 0.544 | 0.183 | no |
| radar_score | 0.344 | 0.1133 | 42.2 | 52.9 | 0.471 | 0.242 | no |

## Sacudón, sin definición clara: 28 casos (16 ganan vs SPY, 12 pierden), 8 dias distintos, mediana vs SPY 1.65

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.385 | 0.3136 | 47.6 | 50.15 | 0.25 | 0.5 | no |
| vol_rel | 0.406 | 0.4189 | 0.17 | 0.45 | 0.438 | 0.321 | no |
| vcp_valido | 0.573 | 0.7164 | 1.0 | 0.0 | 0.675 | 0.473 | no |
| radar_score | 0.542 | 0.7211 | 46.0 | 43.5 | 0.525 | 0.562 | no |
| rs_score | 0.521 | 0.8514 | 55.05 | 50.9 | 0.425 | 0.607 | no |

Sin analizar por muestra chica: Líder apoyando en soporte (17), Rompió piso (SMA200) (18), Perdió EMA200 tras rebote - stop sugerido (2), Gap alcista, ahora con volumen (1), Rebote en EMA200 (experimental, solo en medición) (1)
