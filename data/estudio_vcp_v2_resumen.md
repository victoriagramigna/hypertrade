# Estudio VCP v2 -- forma y stop

Universo: 346 activos. Yahoo del 2024-10-31 al 2026-10-30. Operacion simulada: entrada al cierre de la ruptura; salida en el primer cierre bajo el stop o a las 20 ruedas.

## 1. Hoy: quien cumple cada forma

Cantidad de activos que cumplen hoy (2026-10-30): F0: 19, F0T: 9, F1: 2, F2: 2, F3: 2.

| Ticker | F0 | F0T | F1 | F2 | F3 | Rango ultimo tramo | Riesgo S20 | Riesgo S10 | Riesgo S5 | Riesgo S8 |
|---|---|---|---|---|---|---|---|---|---|---|
| AAPL | si | si | si | si | si | 4.6% | -4.6% | -2.7% | -1.5% | -8.0% |
| ABBV | si | si | - | - | - | 10.4% | -10.4% | -4.1% | -3.0% | -8.0% |
| AVY | si | - | - | - | - | 9.6% | -9.6% | -4.9% | -2.1% | -8.0% |
| BRK-B | si | - | - | - | - | 8.1% | -8.1% | -3.0% | -1.5% | -8.0% |
| CCL | si | - | - | - | - | 11.4% | -11.4% | -9.5% | -6.9% | -8.0% |
| DD | si | - | - | - | - | 8.6% | -8.6% | -8.0% | -3.1% | -8.0% |
| DOCU | si | si | - | - | - | 20.0% | -20.0% | -10.1% | -4.4% | -8.0% |
| EBAY | si | si | - | - | - | 12.9% | -12.9% | -4.1% | -4.1% | -8.0% |
| ECL | si | - | - | - | - | 8.6% | -8.6% | -5.6% | -4.7% | -8.0% |
| HMC | si | si | - | - | - | 8.4% | -8.4% | -2.6% | -2.6% | -8.0% |
| LLY | si | si | - | - | - | 19.4% | -19.4% | -12.5% | -9.8% | -8.0% |
| LMT | si | - | - | - | - | 22.4% | -22.4% | -14.8% | -3.2% | -8.0% |
| MMM | si | - | - | - | - | 9.8% | -9.8% | -8.7% | -3.3% | -8.0% |
| MO | si | - | - | - | - | 13.0% | -13.0% | -6.5% | -6.5% | -8.0% |
| MSFT | - | - | si | si | si | 4.1% | -4.1% | -4.1% | -4.0% | -8.0% |
| NUE | si | si | - | - | - | 10.6% | -10.6% | -6.5% | -6.5% | -8.0% |
| RTX | si | - | - | - | - | 9.8% | -9.8% | -4.4% | -2.6% | -8.0% |
| SAP | si | - | - | - | - | 13.7% | -13.7% | -6.1% | -2.7% | -8.0% |
| TMO | si | si | - | - | - | 8.1% | -8.1% | -5.0% | -3.4% | -8.0% |
| URBN | si | si | - | - | - | 13.5% | -13.5% | -6.1% | -3.1% | -8.0% |

## 2. Forma x stop (mismo criterio de ruptura)

| Definicion | n | Riesgo prom % | % toco el stop | Retorno prom % (IC 95%) | Mediana % | % ganadoras | R prom |
|---|---|---|---|---|---|---|---|
| F0 forma actual · stop S20 | 425 | 13.8 | 11.3 | 1.75 [0.75, 2.85] | 1.22 | 55.3 | 0.1 |
| F0 forma actual · stop S10 | 425 | 8.8 | 27.8 | 1.5 [0.5, 2.57] | 0.33 | 51.8 | 0.14 |
| F0 forma actual · stop S5 | 425 | 5.8 | 42.4 | 1.01 [0.06, 2.02] | -1.39 | 45.6 | 0.15 |
| F0 forma actual · stop S8 | 425 | 9.4 | 19.5 | 1.46 [0.54, 2.5] | 0.69 | 53.6 | 0.15 |
| F0T forma actual + plantilla · stop S20 | 243 | 15.6 | 10.7 | 2.34 [0.85, 3.96] | 1.51 | 56.0 | 0.14 |
| F0T forma actual + plantilla · stop S10 | 243 | 9.7 | 25.9 | 1.91 [0.43, 3.54] | 0.57 | 52.3 | 0.21 |
| F0T forma actual + plantilla · stop S5 | 243 | 6.2 | 43.6 | 1.34 [-0.12, 2.88] | -1.98 | 45.3 | 0.26 |
| F0T forma actual + plantilla · stop S8 | 243 | 9.5 | 23.9 | 1.82 [0.36, 3.39] | 1.04 | 53.1 | 0.18 |
| F1 rangos decrecientes · stop S20 | 262 | 7.7 | 26.7 | 0.93 [-0.06, 1.94] | 0.48 | 52.3 | 0.08 |
| F1 rangos decrecientes · stop S10 | 262 | 6.2 | 38.5 | 0.64 [-0.39, 1.62] | -0.81 | 47.3 | 0.04 |
| F1 rangos decrecientes · stop S5 | 262 | 4.8 | 48.9 | 0.46 [-0.53, 1.43] | -1.87 | 42.4 | 0.0 |
| F1 rangos decrecientes · stop S8 | 262 | 9.2 | 17.9 | 1.02 [-0.01, 2.04] | 0.76 | 54.2 | 0.1 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S20 | 174 | 7.4 | 28.2 | 0.47 [-0.7, 1.73] | -0.08 | 50.0 | 0.06 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | 174 | 5.9 | 39.1 | 0.16 [-0.95, 1.36] | -1.46 | 44.3 | 0.01 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S5 | 174 | 4.6 | 48.3 | 0.21 [-0.86, 1.33] | -1.75 | 41.4 | 0.01 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S8 | 174 | 9.1 | 17.2 | 0.66 [-0.5, 1.92] | 0.79 | 52.3 | 0.07 |
| F3 triangulo + plantilla · stop S20 | 93 | 8.2 | 29.0 | 0.72 [-1.15, 2.67] | -0.53 | 49.5 | 0.06 |
| F3 triangulo + plantilla · stop S10 | 93 | 6.3 | 40.9 | 0.58 [-1.27, 2.49] | -1.46 | 45.2 | 0.12 |
| F3 triangulo + plantilla · stop S5 | 93 | 4.9 | 48.4 | 0.55 [-1.23, 2.42] | -2.19 | 40.9 | 0.14 |
| F3 triangulo + plantilla · stop S8 | 93 | 9.1 | 22.6 | 0.89 [-0.99, 2.86] | 0.51 | 51.6 | 0.11 |

## 3. Estabilidad: primera y segunda mitad del periodo (stop 10 y stop 20)

| Definicion | Mitad | n | Retorno prom % | % ganadoras | R prom |
|---|---|---|---|---|---|
| F0 forma actual · stop S10 | primera (corte 2026-04-29) | 214 | 3.38 | 61.2 | 0.36 |
| F0 forma actual · stop S10 | segunda (corte 2026-04-29) | 211 | -0.4 | 42.2 | -0.08 |
| F0 forma actual · stop S20 | primera (corte 2026-04-29) | 214 | 3.87 | 65.0 | 0.26 |
| F0 forma actual · stop S20 | segunda (corte 2026-04-29) | 211 | -0.39 | 45.5 | -0.06 |
| F0T forma actual + plantilla · stop S10 | primera (corte 2026-04-29) | 137 | 2.96 | 55.5 | 0.34 |
| F0T forma actual + plantilla · stop S10 | segunda (corte 2026-04-29) | 106 | 0.55 | 48.1 | 0.03 |
| F0T forma actual + plantilla · stop S20 | primera (corte 2026-04-29) | 137 | 3.82 | 60.6 | 0.26 |
| F0T forma actual + plantilla · stop S20 | segunda (corte 2026-04-29) | 106 | 0.43 | 50.0 | -0.02 |
| F1 rangos decrecientes · stop S10 | primera (corte 2026-04-29) | 132 | 2.02 | 54.5 | 0.3 |
| F1 rangos decrecientes · stop S10 | segunda (corte 2026-04-29) | 130 | -0.76 | 40.0 | -0.23 |
| F1 rangos decrecientes · stop S20 | primera (corte 2026-04-29) | 132 | 2.46 | 61.4 | 0.3 |
| F1 rangos decrecientes · stop S20 | segunda (corte 2026-04-29) | 130 | -0.62 | 43.1 | -0.14 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | primera (corte 2026-04-29) | 91 | 1.79 | 53.8 | 0.37 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | segunda (corte 2026-04-29) | 83 | -1.62 | 33.7 | -0.37 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S20 | primera (corte 2026-04-29) | 91 | 2.45 | 63.7 | 0.38 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S20 | segunda (corte 2026-04-29) | 83 | -1.71 | 34.9 | -0.3 |
| F3 triangulo + plantilla · stop S10 | primera (corte 2026-04-29) | 53 | 2.73 | 54.7 | 0.56 |
| F3 triangulo + plantilla · stop S10 | segunda (corte 2026-04-29) | 40 | -2.28 | 32.5 | -0.45 |
| F3 triangulo + plantilla · stop S20 | primera (corte 2026-04-29) | 53 | 3.3 | 62.3 | 0.43 |
| F3 triangulo + plantilla · stop S20 | segunda (corte 2026-04-29) | 40 | -2.71 | 32.5 | -0.43 |

## 4. Por riesgo inicial (stop 10)

| Definicion | Riesgo | n | % toco el stop | Retorno prom % | % ganadoras | R prom |
|---|---|---|---|---|---|---|
| F0 forma actual · stop S10 | hasta 8% | 240 | 35.4 | 0.86 | 47.9 | 0.08 |
| F0 forma actual · stop S10 | 8 a 10% | 56 | 21.4 | 2.72 | 60.7 | 0.31 |
| F0 forma actual · stop S10 | mas de 10% | 129 | 16.3 | 2.17 | 55.0 | 0.18 |
| F1 rangos decrecientes · stop S10 | hasta 8% | 195 | 42.1 | 0.47 | 44.1 | 0.02 |
| F1 rangos decrecientes · stop S10 | 8 a 10% | 43 | 37.2 | -1.09 | 51.2 | -0.12 |
| F1 rangos decrecientes · stop S10 | mas de 10% | 24 | 12.5 | 5.15 | 66.7 | 0.47 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | hasta 8% | 135 | 41.5 | 0.25 | 42.2 | 0.02 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | 8 a 10% | 28 | 35.7 | -1.12 | 46.4 | -0.12 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | mas de 10% | 11 | 18.2 | 2.35 | 63.6 | 0.22 |

## 5. Umbral de volumen de la ruptura (stop 10)

| Definicion | Condicion | n | Retorno prom % | % ganadoras | R prom |
|---|---|---|---|---|---|
| F0 forma actual · stop S10 | vol>=1.0x | 218 | 1.41 | 52.8 | 0.17 |
| F0 forma actual · stop S10 | vol>=1.5x | 81 | 2.14 | 53.1 | 0.26 |
| F0 forma actual · stop S10 | vol>=2.0x | 32 | 3.88 | 50.0 | 0.23 |
| F0 forma actual · stop S10 | vol>=3.0x | 8 | 7.65 | 62.5 | 0.6 |
| F0 forma actual · stop S10 | vol>=1.5x y volumen previo seco | 19 | 2.21 | 57.9 | 0.34 |
| F1 rangos decrecientes · stop S10 | vol>=1.0x | 115 | 1.18 | 49.6 | 0.13 |
| F1 rangos decrecientes · stop S10 | vol>=1.5x | 25 | 1.0 | 52.0 | 0.19 |
| F1 rangos decrecientes · stop S10 | vol>=2.0x | 13 | 2.52 | 53.8 | 0.4 |
| F1 rangos decrecientes · stop S10 | vol>=3.0x | 3 | 8.69 | 100.0 | 0.72 |
| F1 rangos decrecientes · stop S10 | vol>=1.5x y volumen previo seco | 11 | 5.55 | 72.7 | 0.74 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | vol>=1.0x | 80 | 0.49 | 47.5 | 0.09 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | vol>=1.5x | 16 | 0.16 | 50.0 | 0.12 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | vol>=2.0x | 8 | 2.36 | 50.0 | 0.34 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | vol>=3.0x | 2 | 9.76 | 100.0 | 0.82 |
| F2 rangos decrecientes + minimos que suben (triangulo) · stop S10 | vol>=1.5x y volumen previo seco | 7 | 5.57 | 71.4 | 0.88 |

## Como leerlo

- Un stop mas cercano baja el riesgo pero lo tocan mas seguido: importa el retorno en multiplos del riesgo (R) y que se repita en las dos mitades, no una columna sola.
- Con menos de 30 casos no concluir nada. Las formas estrictas (F2, F3) dan pocos casos. El intervalo del promedio subestima la incertidumbre porque los casos se agrupan en los mismos dias de mercado.
- El retorno simulado no es una recomendacion ni incluye costos; sirve solo para comparar definiciones.
- Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo regimen, RS aproximado con retorno de 126 ruedas, umbrales elegidos por mi.
