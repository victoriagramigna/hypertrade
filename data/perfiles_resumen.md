# Perfil de las alertas que rindieron (2026-11-21)

Casos con resultado a 20 ruedas: 959. Exploratorio: genera hipotesis, no reglas. Informativo.

Candidato = p < 0.0038 (corregido por 13 datos), |AUC-0.5| >= 0.15, misma direccion en las dos mitades por fecha.
AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.

## TODAS: 959 casos (464 ganan vs SPY, 495 pierden), 28 dias distintos, mediana vs SPY -0.23

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rs_score | 0.387 | 0.0003 | 64.85 | 75.8 | 0.39 | 0.384 | no |
| pendiente_ok | 0.409 | 0.0003 | 0.0 | 1.0 | 0.494 | 0.354 | no |
| dist_max52w_pct | 0.589 | 0.0003 | -9.8 | -14.15 | 0.619 | 0.568 | no |
| var_spy_dia_pct | 0.435 | 0.0017 | -0.03 | 0.12 | 0.45 | 0.445 | no |
| vol_rel | 0.436 | 0.0013 | 0.21 | 0.28 | 0.416 | 0.456 | no |
| apoyo_avwap | 0.555 | 0.0007 | 1.0 | 1.0 | 0.606 | 0.522 | no |

## Confluencia Alcista: 265 casos (110 ganan vs SPY, 155 pierden), 22 dias distintos, mediana vs SPY -3.47

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| regimen_score | 0.38 | 0.0017 | 63.0 | 66.0 | 0.425 | 0.354 | no |
| rs_score | 0.383 | 0.0007 | 66.75 | 76.1 | 0.389 | 0.375 | no |
| radar_score | 0.401 | 0.0047 | 53.0 | 57.7 | 0.501 | 0.302 | no |
| var_spy_dia_pct | 0.432 | 0.0653 | 0.01 | 0.15 | 0.498 | 0.343 | no |
| pendiente_ok | 0.436 | 0.009 | 1.0 | 1.0 | 0.468 | 0.407 | no |
| vol_rel | 0.439 | 0.0896 | 0.1 | 0.13 | 0.434 | 0.444 | no |

## Recién cruzó, sin confirmar: 219 casos (127 ganan vs SPY, 92 pierden), 27 dias distintos, mediana vs SPY 2.95

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| var_spy_dia_pct | 0.289 | 0.0003 | -0.06 | 0.31 | 0.403 | 0.25 | SI |
| dist_max52w_pct | 0.635 | 0.001 | -11.3 | -18.05 | 0.703 | 0.582 | no |
| apoyo_avwap | 0.574 | 0.001 | 1.0 | 1.0 | 0.607 | 0.541 | no |
| cruce_avwap_52w | 0.565 | 0.0953 | 0.0 | 0.0 | 0.564 | 0.547 | no |
| rsi | 0.559 | 0.1416 | 53.9 | 52.15 | 0.324 | 0.735 | no |
| vol_rel | 0.447 | 0.1819 | 0.18 | 0.23 | 0.442 | 0.47 | no |

## Confirmado: 144 casos (86 ganan vs SPY, 58 pierden), 25 dias distintos, mediana vs SPY 3.01

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.745 | 0.0003 | -9.8 | -24.8 | 0.811 | 0.658 | SI |
| vol_rel | 0.369 | 0.0067 | 0.29 | 0.56 | 0.388 | 0.353 | no |
| radar_score | 0.623 | 0.014 | 51.5 | 47.9 | 0.809 | 0.45 | no |
| cruce_avwap_52w | 0.619 | 0.0023 | 0.0 | 0.0 | 0.646 | 0.598 | no |
| rsi | 0.601 | 0.0353 | 53.45 | 51.2 | 0.453 | 0.73 | no |
| var_spy_dia_pct | 0.401 | 0.058 | 0.02 | 0.31 | 0.468 | 0.368 | no |

## Gap alcista con macrotendencia: 121 casos (38 ganan vs SPY, 83 pierden), 25 dias distintos, mediana vs SPY -8.16

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rs_score | 0.336 | 0.0037 | 84.3 | 93.1 | 0.299 | 0.364 | SI |
| radar_score | 0.354 | 0.0093 | 47.55 | 53.8 | 0.398 | 0.324 | no |
| rsi | 0.386 | 0.0463 | 59.75 | 67.1 | 0.211 | 0.495 | no |
| var_spy_dia_pct | 0.387 | 0.074 | 0.05 | 0.15 | 0.511 | 0.339 | no |
| var_dia_pct | 0.41 | 0.1413 | 3.2 | 3.4 | 0.4 | 0.388 | no |
| dist_max52w_pct | 0.581 | 0.2016 | -4.0 | -8.0 | 0.317 | 0.675 | no |

## Sacudón, sin definición clara: 61 casos (34 ganan vs SPY, 27 pierden), 19 dias distintos, mediana vs SPY 1.91

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.722 | 0.0083 | -9.95 | -26.5 | 0.766 | 0.687 | no |
| var_spy_dia_pct | 0.566 | 0.4409 | -0.08 | -0.2 | 0.453 | 0.619 | no |
| pendiente_ok | 0.559 | 0.5328 | 0.0 | 0.0 | 0.688 | 0.488 | no |
| regimen_score | 0.441 | 0.4875 | 64.0 | 67.5 | 0.67 | 0.333 | no |
| apoyo_avwap | 0.537 | 0.7258 | 1.0 | 1.0 | 0.5 | 0.552 | no |
| radar_score | 0.534 | 0.6731 | 46.0 | 44.3 | 0.534 | 0.528 | no |

## Rompió piso (SMA200): 59 casos (32 ganan vs SPY, 27 pierden), 19 dias distintos, mediana vs SPY 2.14

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.732 | 0.0013 | -18.25 | -29.5 | 0.773 | 0.687 | SI |
| radar_score | 0.695 | 0.0123 | 47.85 | 39.7 | 0.765 | 0.617 | no |
| pendiente_ok | 0.334 | 0.004 | 0.0 | 0.0 | 0.333 | 0.339 | no |
| rs_score | 0.627 | 0.0996 | 53.15 | 41.3 | 0.49 | 0.706 | no |
| apoyo_avwap | 0.605 | 0.1623 | 1.0 | 0.0 | 0.54 | 0.639 | no |
| rsi | 0.588 | 0.2519 | 47.95 | 46.6 | 0.405 | 0.739 | no |

## Líder apoyando en soporte: 43 casos (13 ganan vs SPY, 30 pierden), 17 dias distintos, mediana vs SPY -8.54

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.259 | 0.012 | 38.6 | 45.4 | 0.141 | 0.336 | no |
| var_spy_dia_pct | 0.729 | 0.0263 | -0.03 | -0.38 | 0.732 | 0.75 | no |
| rs_score | 0.301 | 0.044 | 85.3 | 90.0 | 0.545 | 0.204 | no |
| vol_rel | 0.323 | 0.0686 | 0.1 | 0.31 | 0.399 | 0.237 | no |
| dist_max52w_pct | 0.626 | 0.2389 | -15.5 | -17.0 | 0.714 | 0.5 | no |
| radar_score | 0.558 | 0.5478 | 61.0 | 56.5 | 0.859 | 0.079 | no |

Sin analizar por muestra chica: Perdió EMA200 tras rebote - stop sugerido (14), Gap alcista, ahora con volumen (17), Rebote en EMA200 (experimental, solo en medición) (16)
