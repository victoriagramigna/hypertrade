# Perfil de las alertas que rindieron (2026-11-07)

Casos con resultado a 20 ruedas: 590. Exploratorio: genera hipotesis, no reglas. Informativo.

Candidato = p < 0.0038 (corregido por 13 datos), |AUC-0.5| >= 0.15, misma direccion en las dos mitades por fecha.
AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.

## TODAS: 590 casos (271 ganan vs SPY, 319 pierden), 18 dias distintos, mediana vs SPY -1.51

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.353 | 0.0003 | 48.3 | 55.25 | 0.384 | 0.326 | no |
| dist_max52w_pct | 0.632 | 0.0003 | -9.0 | -15.4 | 0.641 | 0.634 | no |
| vcp_valido | 0.61 | 0.001 | 1.0 | 0.0 | 0.595 | 0.624 | no |
| rs_score | 0.412 | 0.0003 | 66.5 | 75.9 | 0.419 | 0.407 | no |
| apoyo_avwap | 0.587 | 0.0007 | 1.0 | 1.0 | 0.546 | 0.608 | no |
| radar_score | 0.573 | 0.0023 | 54.7 | 52.1 | 0.617 | 0.537 | no |

## Confluencia Alcista: 162 casos (68 ganan vs SPY, 94 pierden), 12 dias distintos, mediana vs SPY -2.37

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.377 | 0.0093 | 48.8 | 56.5 | 0.452 | 0.302 | no |
| rs_score | 0.396 | 0.0227 | 69.7 | 77.25 | 0.381 | 0.41 | no |
| dist_max52w_pct | 0.598 | 0.032 | -7.55 | -9.7 | 0.615 | 0.583 | no |
| cruce_avwap_52w | 0.588 | 0.0283 | 1.0 | 1.0 | 0.597 | 0.579 | no |
| pendiente_ok | 0.439 | 0.071 | 1.0 | 1.0 | 0.467 | 0.41 | no |
| regimen_score | 0.442 | 0.1979 | 64.0 | 65.0 | 0.465 | 0.425 | no |

## Recién cruzó, sin confirmar: 130 casos (67 ganan vs SPY, 63 pierden), 17 dias distintos, mediana vs SPY 0.7

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.734 | 0.0003 | -9.3 | -23.2 | 0.722 | 0.747 | SI |
| radar_score | 0.709 | 0.0003 | 55.5 | 45.1 | 0.739 | 0.677 | SI |
| var_spy_dia_pct | 0.331 | 0.0067 | 0.17 | 0.31 | 0.439 | 0.303 | no |
| rsi | 0.374 | 0.0143 | 47.5 | 53.8 | 0.395 | 0.355 | no |
| cruce_avwap_52w | 0.618 | 0.0313 | 1.0 | 0.0 | 0.631 | 0.622 | no |
| apoyo_avwap | 0.613 | 0.0017 | 1.0 | 1.0 | 0.516 | 0.65 | no |

## Confirmado: 87 casos (49 ganan vs SPY, 38 pierden), 16 dias distintos, mediana vs SPY 2.88

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.828 | 0.0003 | -9.5 | -30.2 | 0.876 | 0.79 | SI |
| radar_score | 0.801 | 0.0003 | 56.0 | 46.6 | 0.844 | 0.757 | SI |
| vcp_valido | 0.655 | 0.006 | 1.0 | 0.0 | 0.632 | 0.675 | no |
| apoyo_avwap | 0.652 | 0.01 | 1.0 | 0.0 | 0.731 | 0.61 | no |
| pendiente_ok | 0.648 | 0.0097 | 0.0 | 0.0 | 0.731 | 0.6 | no |
| cruce_avwap_52w | 0.626 | 0.0223 | 0.0 | 0.0 | 0.654 | 0.605 | no |

## Gap alcista con macrotendencia: 84 casos (24 ganan vs SPY, 60 pierden), 16 dias distintos, mediana vs SPY -9.48

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.293 | 0.0037 | 57.85 | 67.5 | 0.233 | 0.332 | SI |
| rs_score | 0.325 | 0.0107 | 84.3 | 93.75 | 0.301 | 0.336 | no |
| radar_score | 0.329 | 0.0123 | 46.5 | 54.0 | 0.358 | 0.297 | no |
| pendiente_ok | 0.335 | 0.0103 | 1.0 | 1.0 | 0.226 | 0.4 | no |
| var_spy_dia_pct | 0.371 | 0.0973 | 0.19 | 0.45 | 0.595 | 0.314 | no |
| var_dia_pct | 0.392 | 0.1866 | 3.2 | 3.55 | 0.381 | 0.364 | no |

## Sacudón, sin definición clara: 43 casos (25 ganan vs SPY, 18 pierden), 12 dias distintos, mediana vs SPY 2.81

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.878 | 0.0003 | -8.8 | -36.8 | None | None | no |
| pendiente_ok | 0.735 | 0.0093 | 0.0 | 0.0 | None | None | no |
| radar_score | 0.622 | 0.1756 | 49.2 | 41.35 | 0.5 | 0.72 | no |
| var_spy_dia_pct | 0.615 | 0.2899 | -0.11 | -0.4 | None | None | no |
| rsi | 0.386 | 0.2039 | 47.2 | 48.9 | 0.319 | 0.447 | no |
| regimen_score | 0.599 | 0.3685 | 68.0 | 63.0 | None | None | no |

## Rompió piso (SMA200): 32 casos (18 ganan vs SPY, 14 pierden), 11 dias distintos, mediana vs SPY 2.41

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.83 | 0.0037 | -15.15 | -44.65 | 0.64 | 0.905 | SI |
| radar_score | 0.764 | 0.0107 | 56.45 | 44.1 | 0.855 | 0.627 | no |
| vcp_valido | 0.675 | 0.073 | 1.0 | 0.0 | 0.709 | 0.635 | no |
| pendiente_ok | 0.357 | 0.106 | 0.0 | 0.0 | 0.3 | 0.389 | no |
| apoyo_avwap | 0.577 | 0.6944 | 1.0 | 0.0 | 0.6 | 0.548 | no |
| rsi | 0.429 | 0.4915 | 43.05 | 46.95 | 0.218 | 0.627 | no |

## Líder apoyando en soporte: 28 casos (11 ganan vs SPY, 17 pierden), 12 dias distintos, mediana vs SPY -8.34

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.778 | 0.0257 | -10.5 | -27.9 | 0.65 | 0.867 | no |
| var_spy_dia_pct | 0.738 | 0.06 | 0.31 | -0.36 | 0.3 | 0.922 | no |
| rsi | 0.275 | 0.0477 | 38.6 | 45.6 | 0.083 | 0.4 | no |
| radar_score | 0.695 | 0.094 | 69.7 | 54.7 | 0.917 | 0.356 | no |
| vol_rel | 0.348 | 0.1893 | 0.1 | 0.35 | 0.5 | 0.2 | no |
| rs_score | 0.401 | 0.3909 | 85.3 | 88.8 | 0.646 | 0.178 | no |

Sin analizar por muestra chica: Perdió EMA200 tras rebote - stop sugerido (6), Gap alcista, ahora con volumen (9), Rebote en EMA200 (experimental, solo en medición) (9)
