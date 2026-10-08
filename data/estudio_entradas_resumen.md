# Estudio 3 -- entradas y stops después de un Gap alcista

Generado: 2026-10-08T22:54 UTC. Papeles: 300.

## Volatilidad baja o media -- horizonte 20 ruedas (R medio: resultado / riesgo inicial)
| entrada | stop | n | ganadoras % | ret medio % | R medio | en stop % | dist. stop % |
|---|---|---|---|---|---|---|---|
| C_retroceso_nivel | sma50 | 1432 | 37.7 | 0.75 | 0.97 | 50.1 | 6.2 |
| B_retroceso_SMA20 | sma50 | 1671 | 37.8 | 0.66 | 0.34 | 52.0 | 5.3 |
| D_retroceso_3pct | sma50 | 1986 | 42.6 | 1.02 | 0.29 | 43.3 | 7.3 |
| A_mismo_dia | atr_2x | 3916 | 44.6 | 0.99 | 0.19 | 46.9 | 5.6 |
| A_mismo_dia | fijo_5 | 3925 | 41.6 | 0.94 | 0.19 | 51.5 | 5.0 |
| C_retroceso_nivel | estructural | 1715 | 35.6 | 0.52 | 0.17 | 57.4 | 4.9 |
| B_retroceso_SMA20 | estructural | 1959 | 34.9 | 0.42 | 0.16 | 58.8 | 4.5 |
| D_retroceso_3pct | fijo_5 | 2238 | 38.5 | 0.8 | 0.16 | 55.8 | 5.0 |
| A_mismo_dia | fijo_8 | 3908 | 50.5 | 1.24 | 0.15 | 32.6 | 8.0 |
| D_retroceso_3pct | atr_2x | 2238 | 44.1 | 0.9 | 0.15 | 46.8 | 6.3 |
| D_retroceso_3pct | estructural | 2244 | 42.3 | 0.86 | 0.15 | 46.0 | 6.6 |
| A_mismo_dia | estructural | 3911 | 53.0 | 1.31 | 0.12 | 21.6 | 10.7 |
| B_retroceso_SMA20 | atr_2x | 1954 | 43.2 | 0.59 | 0.12 | 47.7 | 6.3 |
| B_retroceso_SMA20 | fijo_5 | 1954 | 38.4 | 0.59 | 0.12 | 55.9 | 5.0 |
| C_retroceso_nivel | fijo_5 | 1711 | 36.5 | 0.6 | 0.12 | 57.9 | 5.0 |
| D_retroceso_3pct | fijo_8 | 2236 | 47.2 | 0.87 | 0.11 | 38.2 | 8.0 |
| C_retroceso_nivel | atr_2x | 1711 | 41.4 | 0.58 | 0.1 | 48.8 | 6.3 |
| C_retroceso_nivel | fijo_8 | 1710 | 44.9 | 0.7 | 0.09 | 39.6 | 8.0 |
| B_retroceso_SMA20 | fijo_8 | 1951 | 45.8 | 0.58 | 0.07 | 38.9 | 8.0 |
| A_mismo_dia | sma50 | 3787 | 49.5 | 1.31 | -57.29 | 27.3 | 10.4 |

## Protección de ganancia (largo, 60 ruedas) -- con y sin
- A_mismo_dia / fijo_8 / protección NO: n=3819, ret medio 2.45%, R 0.31, en stop 55.4%
- A_mismo_dia / fijo_8 / protección SÍ: n=3823, ret medio 2.2%, R 0.28, en stop 60.2%
- A_mismo_dia / sma50 / protección NO: n=3684, ret medio 2.94%, R -58.69, en stop 47.6%
- A_mismo_dia / sma50 / protección SÍ: n=3686, ret medio 2.69%, R -58.69, en stop 52.7%
- B_retroceso_SMA20 / fijo_8 / protección NO: n=1893, ret medio 1.5%, R 0.19, en stop 60.9%
- B_retroceso_SMA20 / fijo_8 / protección SÍ: n=1899, ret medio 1.53%, R 0.19, en stop 65.2%
- B_retroceso_SMA20 / sma50 / protección NO: n=1632, ret medio 1.16%, R 0.51, en stop 70.6%
- B_retroceso_SMA20 / sma50 / protección SÍ: n=1635, ret medio 1.18%, R 0.52, en stop 74.4%

## Cuántas órdenes de retroceso se ejecutan
- alta: A_mismo_dia: 100.0%; B_retroceso_SMA20: 59.6%; C_retroceso_nivel: 57.9%; D_retroceso_3pct: 74.6%
- baja: A_mismo_dia: 100.0%; B_retroceso_SMA20: 42.9%; C_retroceso_nivel: 33.7%; D_retroceso_3pct: 46.6%
- baja_o_media: A_mismo_dia: 100.0%; B_retroceso_SMA20: 49.5%; C_retroceso_nivel: 43.4%; D_retroceso_3pct: 56.8%