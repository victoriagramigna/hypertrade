# Estudio de ondas de Elliott v2 (conteo mecánico, escala logarítmica)

Datos: 2024-11-14 a 2026-11-13 · 346 activos · giros de K=5 ruedas (sensibilidad K=3 y K=8).

Es descriptivo: no valida ni descarta el método. Ver límites al final.


## Setup onda 3 (se confirma el mínimo de la onda 2)

Eventos: 1789 · riesgo mediano hasta la invalidación: 5.58%

| Horizonte | n | Retorno mediano | Exceso prom. vs SPY | Exceso mediano | % con exceso > 0 | IC95% del exceso |
|---|---|---|---|---|---|---|
| 5 ruedas | 1759 | 0.22% | 0.04 | -0.08 | 48.9% | [-0.25, 0.33] |
| 10 ruedas | 1725 | 0.19% | 0.14 | -0.34 | 47.1% | [-0.32, 0.6] |
| 20 ruedas | 1705 | 0.68% | 0.22 | -0.64 | 46.8% | [-0.46, 0.9] |

Qué pasa primero en 20 ruedas, por objetivo (múltiplo de la onda 1):
- 1.0: objetivo 29.0% · invalidación 49.6% · ninguno 21.3% (n=1705)
- 1.618: objetivo 11.2% · invalidación 52.2% · ninguno 36.6% (n=1705)
- 2.0: objetivo 6.0% · invalidación 52.4% · ninguno 41.6% (n=1705)
- 2.618: objetivo 2.5% · invalidación 52.6% · ninguno 44.9% (n=1705)

Por trimestre (n y exceso a 20 ruedas): 2025Q3: 203 / 2.92 · 2025Q4: 405 / 1.24 · 2026Q1: 301 / 0.7 · 2026Q2: 367 / -1.31 · 2026Q3: 395 / -0.51 · 2026Q4: 118 / -7.34

## Setup onda 5 (se confirma el mínimo de la onda 4)

Eventos: 196 · riesgo mediano hasta la invalidación: 6.04%

| Horizonte | n | Retorno mediano | Exceso prom. vs SPY | Exceso mediano | % con exceso > 0 | IC95% del exceso |
|---|---|---|---|---|---|---|
| 5 ruedas | 193 | 0.27% | 0.34 | 0.06 | 50.8% | [-0.58, 1.26] |
| 10 ruedas | 192 | 0.44% | 0.55 | -0.11 | 49.5% | [-0.8, 1.9] |
| 20 ruedas | 190 | 0.21% | 1.42 | -1.17 | 44.7% | [-0.99, 3.83] |

Qué pasa primero en 20 ruedas, por objetivo (múltiplo de la onda 1):
- 1.0: objetivo 38.9% · invalidación 46.3% · ninguno 14.7% (n=190)
- 1.618: objetivo 19.5% · invalidación 50.0% · ninguno 30.5% (n=190)
- 0.618: objetivo 65.3% · invalidación 33.7% · ninguno 1.1% (n=190)

Por trimestre (n y exceso a 20 ruedas): 2025Q3: 17 / 13.45 · 2025Q4: 49 / 0.2 · 2026Q1: 49 / 2.76 · 2026Q2: 30 / -0.1 · 2026Q3: 44 / -2.39 · 2026Q4: 7 / 3.66

## Control: mínimo confirmado sobre la media de 50, sin reglas de Elliott

Eventos: 2316 · riesgo mediano hasta la invalidación: 7.45%

| Horizonte | n | Retorno mediano | Exceso prom. vs SPY | Exceso mediano | % con exceso > 0 | IC95% del exceso |
|---|---|---|---|---|---|---|
| 5 ruedas | 2278 | 0.29% | 0.11 | -0.02 | 49.3% | [-0.15, 0.37] |
| 10 ruedas | 2224 | 0.52% | 0.68 | -0.06 | 49.3% | [0.26, 1.1] |
| 20 ruedas | 2196 | 0.88% | 0.75 | -0.23 | 48.8% | [0.13, 1.36] |

Qué pasa primero en 20 ruedas (sin objetivo): invalidación 40.4% · ninguno 59.6% (n=2196).

Por trimestre (n y exceso a 20 ruedas): 2025Q3: 267 / 4.35 · 2025Q4: 509 / 0.82 · 2026Q1: 423 / 1.34 · 2026Q2: 468 / -0.26 · 2026Q3: 465 / -0.66 · 2026Q4: 184 / -1.21

## Hipótesis fijadas de antemano (exceso a 20 ruedas, IC99%, corte de mitades: 2026-04-08)

Solo vale lo que va en el mismo sentido en las dos mitades. Con tantas comparaciones, alguna puede salir por azar.

| Hipótesis | Mitad 1 (con / sin) | Mitad 2 (con / sin) | Todo (con / sin) | Mismo sentido |
|---|---|---|---|---|
| H1: ONDA5 contra CONTROL | 3.18 (n=116) / 2.0 (n=1224) · dif 1.18 | -1.35 (n=74) / -0.84 (n=972) · dif -0.51 | 1.42 (n=190) / 0.75 (n=2196) · dif 0.67 | no |
| H2: ONDA5 con alternancia (onda 2 >= 50% y onda 4 <= 38,2%) | 4.99 (n=40) / 2.23 (n=76) · dif 2.76 | 0.46 (n=31) / -2.65 (n=43) · dif 3.11 | 3.01 (n=71) / 0.47 (n=119) · dif 2.54 | sí |
| H3: ONDA5 con RSI >= 70 en el maximo de la onda 3 | 3.62 (n=81) / 2.18 (n=35) · dif 1.44 | -1.1 (n=54) / -2.02 (n=20) · dif 0.92 | 1.73 (n=135) / 0.65 (n=55) · dif 1.08 | sí |
| H4: ONDA5 con volumen de la onda 3 mayor que el de la onda 1 | 1.94 (n=84) / 6.45 (n=32) · dif -4.51 | -3.83 (n=42) / 1.91 (n=32) · dif -5.74 | 0.02 (n=126) / 4.18 (n=64) · dif -4.16 | sí |
| H5: ONDA3 con onda 2 profunda (>= 50%) | 1.63 (n=477) / 1.25 (n=449) · dif 0.38 | -0.37 (n=444) / -2.39 (n=335) · dif 2.02 | 0.67 (n=921) / -0.31 (n=784) · dif 0.98 | sí |
| H6: ONDA3 con volumen de la onda 2 menor que el de la onda 1 | 1.17 (n=548) / 1.86 (n=378) · dif -0.69 | -1.56 (n=535) / -0.54 (n=244) · dif -1.02 | -0.18 (n=1083) / 0.92 (n=622) · dif -1.1 | sí |

## Sensibilidad al largo del giro (K)

- K=3: ONDA3 n=2247 exceso20=0.54 · ONDA5 n=248 exceso20=-0.6 · CONTROL n=2714 exceso20=0.52
- K=5: ONDA3 n=1789 exceso20=0.22 · ONDA5 n=196 exceso20=1.42 · CONTROL n=2316 exceso20=0.75
- K=8: ONDA3 n=1323 exceso20=-0.23 · ONDA5 n=134 exceso20=-2.4 · CONTROL n=1842 exceso20=0.06

## Límites
- El conteo de Elliott es subjetivo; esta es una sola forma mecánica y estricta de contarlo (sin diagonales, sin zigzag/flat/triángulo ni subdivisión interna).
- Universo actual (sesgo de supervivencia); ~1 año de eventos útiles en un solo régimen de mercado.
- Eventos de activos distintos en el mismo día están correlacionados: los intervalos son optimistas.
- Umbrales y proporciones (5%, 23,6–78,6%, 1,618, onda 5 = onda 1, RSI 70, alternancia 50%/38,2%) elegidos por mí, no validados.
- "Onda 3 mayor que la onda 1" es más estricta que la regla de Elliott (la 3 no es la más corta de 1, 3 y 5).
- Salida simulada al nivel exacto de la invalidación/objetivo; no incluye comisiones ni deslizamiento.
- No es una recomendación de compra ni de venta.
