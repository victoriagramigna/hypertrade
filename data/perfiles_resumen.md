# Perfil de las alertas que rindieron (2026-10-23)

Casos con resultado a 20 ruedas: 126. Exploratorio: genera hipotesis, no reglas. Informativo.

Candidato = p < 0.0038 (corregido por 13 datos), |AUC-0.5| >= 0.15, misma direccion en las dos mitades por fecha.
AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.

## TODAS: 126 casos (61 ganan vs SPY, 65 pierden), 5 dias distintos, mediana vs SPY -0.2

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| apoyo_avwap | 0.726 | 0.045 | 1.0 | 0.0 | None | None | no |
| dist_max52w_pct | 0.708 | 0.076 | -10.3 | -29.65 | None | None | no |
| radar_score | 0.695 | 0.0007 | 53.6 | 45.0 | 0.703 | 0.666 | SI |
| cruce_avwap_52w | 0.679 | 0.041 | 0.0 | 0.0 | None | None | no |
| rsi | 0.338 | 0.003 | 47.8 | 56.4 | 0.27 | 0.435 | SI |
| atr_contraction | 0.417 | 0.1936 | 0.0 | 0.0 | None | None | no |

## Recién cruzó, sin confirmar: 42 casos (20 ganan vs SPY, 22 pierden), 5 dias distintos, mediana vs SPY -0.3

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| radar_score | 0.732 | 0.0097 | 53.6 | 42.0 | None | None | no |
| rs_score | 0.611 | 0.2193 | 52.8 | 47.75 | None | None | no |
| vcp_valido | 0.55 | 0.5422 | 1.0 | 0.5 | None | None | no |
| rsi | 0.47 | 0.7601 | 47.3 | 52.25 | None | None | no |
| vol_rel | 0.489 | 0.9094 | 0.27 | 0.34 | None | None | no |

## Gap alcista con macrotendencia: 28 casos (6 ganan vs SPY, 22 pierden), 5 dias distintos, mediana vs SPY -11.59

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|

## Confirmado: 25 casos (15 ganan vs SPY, 10 pierden), 4 dias distintos, mediana vs SPY 2.16

| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |
|---|---|---|---|---|---|---|---|
| radar_score | 0.81 | 0.0063 | 54.1 | 42.5 | None | None | no |
| vol_rel | 0.32 | 0.135 | 0.13 | 0.63 | None | None | no |
| rs_score | 0.637 | 0.2702 | 61.3 | 37.2 | None | None | no |
| rsi | 0.53 | 0.8194 | 53.8 | 52.2 | None | None | no |
| vcp_valido | 0.517 | 1.0 | 1.0 | 1.0 | None | None | no |

Sin analizar por muestra chica: Líder apoyando en soporte (6), Rompió piso (SMA200) (8), Sacudón, sin definición clara (16), Perdió EMA200 tras rebote - stop sugerido (1)
