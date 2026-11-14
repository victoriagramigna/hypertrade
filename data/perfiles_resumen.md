# Perfil de las alertas que rindieron (2026-11-14)

Casos con resultado a 20 ruedas: 815. Exploratorio: genera hipotesis, no reglas. Informativo.

Candidato = p < 0.0038 (corregido por 13 datos), |AUC-0.5| >= 0.15, misma direccion en las dos mitades por fecha.
AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.

## TODAS: 815 casos (401 ganan vs SPY, 414 pierden), 23 dias distintos, mediana vs SPY -0.12

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.608 | 0.0003 | -9.35 | -14.4 | 0.617 | 0.599 | no |
| rs_score | 0.4 | 0.0003 | 65.4 | 75.9 | 0.397 | 0.4 | no |
| pendiente_ok | 0.417 | 0.0003 | 0.0 | 1.0 | 0.492 | 0.368 | no |
| var_dia_pct | 0.429 | 0.2612 | 3.2 | 3.4 | 0.495 | 0.368 | no |
| var_spy_dia_pct | 0.433 | 0.0017 | -0.06 | 0.03 | 0.487 | 0.406 | no |
| apoyo_avwap | 0.567 | 0.0007 | 1.0 | 1.0 | 0.574 | 0.564 | no |

## Confluencia Alcista: 220 casos (95 ganan vs SPY, 125 pierden), 17 dias distintos, mediana vs SPY -2.37

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| regimen_score | 0.38 | 0.0013 | 63.0 | 66.0 | 0.481 | 0.33 | no |
| rs_score | 0.383 | 0.0033 | 66.9 | 76.1 | 0.383 | 0.381 | no |
| radar_score | 0.41 | 0.0207 | 53.6 | 58.0 | 0.501 | 0.317 | no |
| cruce_avwap_52w | 0.571 | 0.0343 | 1.0 | 1.0 | 0.626 | 0.519 | no |
| dist_max52w_pct | 0.57 | 0.0746 | -8.0 | -9.4 | 0.613 | 0.529 | no |
| pendiente_ok | 0.431 | 0.0133 | 1.0 | 1.0 | 0.473 | 0.39 | no |

## Recién cruzó, sin confirmar: 185 casos (110 ganan vs SPY, 75 pierden), 22 dias distintos, mediana vs SPY 3.39

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| var_spy_dia_pct | 0.298 | 0.0003 | -0.09 | 0.2 | 0.367 | 0.268 | SI |
| dist_max52w_pct | 0.674 | 0.0003 | -10.3 | -20.1 | 0.626 | 0.68 | SI |
| radar_score | 0.613 | 0.0093 | 52.1 | 46.2 | 0.638 | 0.577 | no |
| apoyo_avwap | 0.599 | 0.0007 | 1.0 | 1.0 | 0.555 | 0.621 | no |
| cruce_avwap_52w | 0.581 | 0.0643 | 1.0 | 0.0 | 0.59 | 0.545 | no |
| vol_rel | 0.422 | 0.0703 | 0.17 | 0.25 | 0.48 | 0.382 | no |

## Confirmado: 124 casos (77 ganan vs SPY, 47 pierden), 21 dias distintos, mediana vs SPY 3.27

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.776 | 0.0003 | -9.7 | -24.9 | 0.78 | 0.721 | SI |
| radar_score | 0.675 | 0.001 | 52.9 | 47.7 | 0.796 | 0.548 | SI |
| vol_rel | 0.379 | 0.024 | 0.29 | 0.56 | 0.381 | 0.402 | no |
| cruce_avwap_52w | 0.615 | 0.015 | 0.0 | 0.0 | 0.611 | 0.566 | no |
| var_spy_dia_pct | 0.404 | 0.1053 | -0.03 | 0.18 | 0.414 | 0.39 | no |
| apoyo_avwap | 0.596 | 0.0457 | 1.0 | 1.0 | 0.628 | 0.554 | no |

## Gap alcista con macrotendencia: 107 casos (34 ganan vs SPY, 73 pierden), 21 dias distintos, mediana vs SPY -7.41

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.331 | 0.005 | 58.0 | 67.1 | 0.211 | 0.429 | no |
| radar_score | 0.348 | 0.0147 | 47.6 | 54.4 | 0.398 | 0.294 | no |
| rs_score | 0.353 | 0.0173 | 85.05 | 92.8 | 0.299 | 0.403 | no |
| var_dia_pct | 0.395 | 0.1113 | 3.2 | 3.5 | 0.4 | 0.36 | no |
| var_spy_dia_pct | 0.399 | 0.1293 | 0.06 | 0.15 | 0.511 | 0.347 | no |
| pendiente_ok | 0.402 | 0.0716 | 1.0 | 1.0 | 0.256 | 0.477 | no |

## Sacudón, sin definición clara: 54 casos (30 ganan vs SPY, 24 pierden), 16 dias distintos, mediana vs SPY 1.65

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.804 | 0.0017 | -9.05 | -29.1 | 0.825 | 0.816 | SI |
| pendiente_ok | 0.599 | 0.1946 | 0.0 | 0.0 | 0.688 | 0.571 | no |
| radar_score | 0.569 | 0.3769 | 49.3 | 44.65 | 0.566 | 0.597 | no |
| rs_score | 0.565 | 0.4142 | 60.4 | 55.65 | 0.494 | 0.643 | no |
| rsi | 0.451 | 0.5242 | 47.25 | 48.1 | 0.388 | 0.508 | no |
| apoyo_avwap | 0.541 | 0.7058 | 1.0 | 1.0 | 0.475 | 0.571 | no |

## Rompió piso (SMA200): 47 casos (26 ganan vs SPY, 21 pierden), 16 dias distintos, mediana vs SPY 2.14

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| dist_max52w_pct | 0.757 | 0.005 | -16.65 | -38.6 | 0.714 | 0.731 | no |
| radar_score | 0.73 | 0.009 | 53.75 | 43.2 | 0.859 | 0.633 | no |
| pendiente_ok | 0.335 | 0.0203 | 0.0 | 0.0 | 0.333 | 0.338 | no |
| rs_score | 0.616 | 0.1766 | 53.15 | 40.2 | 0.397 | 0.71 | no |
| vcp_valido | 0.613 | 0.1516 | 1.0 | 0.0 | 0.756 | 0.497 | no |
| apoyo_avwap | 0.587 | 0.3499 | 1.0 | 0.0 | 0.524 | 0.608 | no |

## Líder apoyando en soporte: 43 casos (13 ganan vs SPY, 30 pierden), 17 dias distintos, mediana vs SPY -8.54

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| rsi | 0.259 | 0.0143 | 38.6 | 45.4 | 0.141 | 0.336 | no |
| var_spy_dia_pct | 0.729 | 0.03 | -0.03 | -0.38 | 0.732 | 0.75 | no |
| rs_score | 0.301 | 0.0457 | 85.3 | 90.0 | 0.545 | 0.204 | no |
| vol_rel | 0.323 | 0.0623 | 0.1 | 0.31 | 0.399 | 0.237 | no |
| dist_max52w_pct | 0.626 | 0.2179 | -15.5 | -17.0 | 0.714 | 0.5 | no |
| radar_score | 0.558 | 0.5578 | 61.0 | 56.5 | 0.859 | 0.079 | no |

Sin analizar por muestra chica: Perdió EMA200 tras rebote - stop sugerido (10), Gap alcista, ahora con volumen (13), Rebote en EMA200 (experimental, solo en medición) (12)
