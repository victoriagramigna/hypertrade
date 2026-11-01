# Estudio VCP v3 -- las formas contra el mercado y contra una base

Universo: 346 activos. Yahoo del 2024-10-31 al 2026-10-30. Operacion simulada: entrada al cierre de la ruptura; salida en el primer cierre bajo el stop o a las 20 ruedas. Exceso = retorno de la operacion menos el de SPY durante la misma tenencia. Los intervalos remuestrean DIAS completos.

## 1. Contexto de mercado (retorno medio a 20 ruedas, cualquier dia)

| Periodo | Dias | SPY % | Universo (cualquier activo) % |
|---|---|---|---|
| primera mitad | 114 | 1.51 | 2.45 |
| segunda mitad | 115 | 1.17 | 1.02 |
| 2025-T4 | 40 | 1.47 | 3.95 |
| 2026-T1 | 61 | 0.26 | 0.99 |
| 2026-T2 | 62 | 2.6 | 1.98 |
| 2026-T3 | 64 | 1.14 | 0.9 |
| 2026-T4 | 2 | -0.55 | -1.33 |

Corte de mitades: 2026-04-21 (punto medio de la ventana evaluada).

## 2. Formas y BASE: todo el periodo

| Definicion | Casos | Dias | Riesgo % | % toco stop | Retorno % | Exceso vs SPY % [IC95 por dias] | % ganadoras | R |
|---|---|---|---|---|---|---|---|---|
| F0 forma actual · S20 | 425 | 164 | 13.8 | 11.3 | 1.75 | 1.03 [-0.38, 2.31] | 55.3 | 0.1 |
| F0 forma actual · S10 | 425 | 164 | 8.8 | 27.8 | 1.5 | 0.88 [-0.61, 2.19] | 51.8 | 0.14 |
| F0 forma actual · S8 | 425 | 164 | 9.4 | 19.5 | 1.46 | 0.74 [-0.74, 2.07] | 53.6 | 0.15 |
| F0T actual + plantilla · S20 | 243 | 125 | 15.6 | 10.7 | 2.34 | 1.44 [-0.66, 3.57] | 56.0 | 0.14 |
| F0T actual + plantilla · S10 | 243 | 125 | 9.7 | 25.9 | 1.91 | 1.14 [-1.03, 3.33] | 52.3 | 0.21 |
| F0T actual + plantilla · S8 | 243 | 125 | 9.5 | 23.9 | 1.82 | 0.95 [-1.32, 3.17] | 53.1 | 0.18 |
| F1 rangos decrecientes · S20 | 262 | 127 | 7.7 | 26.7 | 0.93 | -0.01 [-1.39, 1.32] | 52.3 | 0.08 |
| F1 rangos decrecientes · S10 | 262 | 127 | 6.2 | 38.5 | 0.64 | -0.24 [-1.58, 1.05] | 47.3 | 0.04 |
| F1 rangos decrecientes · S8 | 262 | 127 | 9.2 | 17.9 | 1.02 | 0.02 [-1.42, 1.4] | 54.2 | 0.1 |
| F2 triangulo · S20 | 174 | 96 | 7.4 | 28.2 | 0.47 | -0.17 [-1.74, 1.45] | 50.0 | 0.06 |
| F2 triangulo · S10 | 174 | 96 | 5.9 | 39.1 | 0.16 | -0.35 [-1.82, 1.22] | 44.3 | 0.01 |
| F2 triangulo · S8 | 174 | 96 | 9.1 | 17.2 | 0.66 | -0.07 [-1.73, 1.65] | 52.3 | 0.07 |
| F3 triangulo + plantilla · S20 | 93 | 66 | 8.2 | 29.0 | 0.72 | -0.15 [-2.41, 2.3] | 49.5 | 0.06 |
| F3 triangulo + plantilla · S10 | 93 | 66 | 6.3 | 40.9 | 0.58 | -0.2 [-2.33, 2.12] | 45.2 | 0.12 |
| F3 triangulo + plantilla · S8 | 93 | 66 | 9.1 | 22.6 | 0.89 | -0.15 [-2.58, 2.33] | 51.6 | 0.11 |
| BASE tendencia + ruptura, sin forma · S20 | 1053 | 214 | 13.2 | 16.0 | 1.92 | 0.78 [-0.08, 1.72] | 53.8 | 0.15 |
| BASE tendencia + ruptura, sin forma · S10 | 1053 | 214 | 10.4 | 25.2 | 1.75 | 0.69 [-0.13, 1.6] | 51.5 | 0.19 |
| BASE tendencia + ruptura, sin forma · S8 | 1053 | 214 | 9.6 | 22.7 | 1.67 | 0.61 [-0.18, 1.52] | 51.9 | 0.18 |

## 3. Por mitad del periodo (exceso vs SPY %)

| Definicion | primera (casos) | segunda (casos) |
|---|---|---|
| F0 forma actual · S10 | 2.37 (204) | -0.49 (221) |
| F0 forma actual · S20 | 2.72 (204) | -0.52 (221) |
| F0T actual + plantilla · S10 | 1.65 (132) | 0.54 (111) |
| F0T actual + plantilla · S20 | 2.35 (132) | 0.35 (111) |
| F1 rangos decrecientes · S10 | 0.95 (132) | -1.44 (130) |
| F1 rangos decrecientes · S20 | 1.26 (132) | -1.31 (130) |
| F2 triangulo · S10 | 1.5 (90) | -2.32 (84) |
| F2 triangulo · S20 | 1.97 (90) | -2.46 (84) |
| F3 triangulo + plantilla · S10 | 2.12 (53) | -3.26 (40) |
| F3 triangulo + plantilla · S20 | 2.56 (53) | -3.73 (40) |
| BASE tendencia + ruptura, sin forma · S10 | 1.93 (593) | -0.89 (460) |
| BASE tendencia + ruptura, sin forma · S20 | 2.01 (593) | -0.8 (460) |

## 4. Segun el regimen del mercado en el dia de la ruptura (exceso vs SPY %)

| Definicion | SPY sobre su media de 50 (casos) | SPY bajo su media de 50 (casos) |
|---|---|---|
| F0 forma actual · S10 | 0.92 (371) | 0.59 (54) |
| F0 forma actual · S20 | 1.21 (371) | -0.15 (54) |
| F0T actual + plantilla · S10 | 1.39 (208) | -0.32 (35) |
| F0T actual + plantilla · S20 | 1.83 (208) | -0.92 (35) |
| F1 rangos decrecientes · S10 | 0.23 (231) | -3.7 (31) |
| F1 rangos decrecientes · S20 | 0.44 (231) | -3.35 (31) |
| F2 triangulo · S10 | 0.16 (153) | -4.04 (21) |
| F2 triangulo · S20 | 0.29 (153) | -3.55 (21) |
| F3 triangulo + plantilla · S10 | 0.23 (78) | -2.4 (15) |
| F3 triangulo + plantilla · S20 | 0.19 (78) | -1.88 (15) |
| BASE tendencia + ruptura, sin forma · S10 | 0.94 (897) | -0.75 (156) |
| BASE tendencia + ruptura, sin forma · S20 | 0.96 (897) | -0.28 (156) |

## 5. Por trimestre de la ruptura, stop 10 (exceso vs SPY %, casos)

| Definicion | 2025-T4 | 2026-T1 | 2026-T2 | 2026-T3 | 2026-T4 |
|---|---|---|---|---|---|
| F0 forma actual | 2.79 (70) | 2.77 (122) | 1.09 (103) | -2.14 (129) | 4.7 (1) |
| F0T actual + plantilla | 4.13 (43) | 1.21 (80) | 2.46 (59) | -2.45 (60) | 4.7 (1) |
| F1 rangos decrecientes | 2.29 (38) | 1.98 (77) | -2.6 (68) | -1.56 (74) | -1.82 (5) |
| F2 triangulo | 2.83 (24) | 1.26 (64) | -1.69 (37) | -2.94 (45) | -3.46 (4) |
| F3 triangulo + plantilla | 5.34 (13) | 1.47 (39) | -3.8 (14) | -3.42 (24) | -3.34 (3) |
| BASE tendencia + ruptura, sin forma | 2.77 (197) | 1.96 (285) | -0.27 (337) | -1.18 (233) | -6.92 (1) |

## 6. Umbral de volumen de la ruptura, stop 10 (exceso vs SPY %)

| Definicion | Condicion | Casos | Retorno % | Exceso % | % ganadoras |
|---|---|---|---|---|---|
| F0 forma actual · S10 | vol>=1.0x | 218 | 1.41 | 0.86 | 52.8 |
| F0 forma actual · S10 | vol>=1.5x | 81 | 2.14 | 1.65 | 53.1 |
| F0 forma actual · S10 | vol>=2.0x | 32 | 3.88 | 3.16 | 50.0 |
| F0 forma actual · S10 | vol>=3.0x | 8 | 7.65 | 8.32 | 62.5 |
| F0 forma actual · S10 | vol>=1.5x y volumen previo seco | 19 | 2.21 | 2.27 | 57.9 |
| F0T actual + plantilla · S10 | vol>=1.0x | 143 | 1.31 | 0.53 | 50.3 |
| F0T actual + plantilla · S10 | vol>=1.5x | 43 | 1.84 | 1.07 | 48.8 |
| F0T actual + plantilla · S10 | vol>=2.0x | 18 | 5.23 | 4.23 | 50.0 |
| F0T actual + plantilla · S10 | vol>=3.0x | 5 | 6.55 | 8.16 | 60.0 |
| F0T actual + plantilla · S10 | vol>=1.5x y volumen previo seco | 11 | 1.88 | 1.79 | 63.6 |
| F2 triangulo · S10 | vol>=1.0x | 80 | 0.49 | -0.23 | 47.5 |
| F2 triangulo · S10 | vol>=1.5x | 16 | 0.16 | -0.4 | 50.0 |
| F2 triangulo · S10 | vol>=2.0x | 8 | 2.36 | 1.01 | 50.0 |
| F2 triangulo · S10 | vol>=3.0x | 2 | 9.76 | 5.7 | 100.0 |
| F2 triangulo · S10 | vol>=1.5x y volumen previo seco | 7 | 5.57 | 5.15 | 71.4 |
| BASE tendencia + ruptura, sin forma · S10 | vol>=1.0x | 516 | 2.26 | 1.61 | 53.3 |
| BASE tendencia + ruptura, sin forma · S10 | vol>=1.5x | 185 | 1.56 | 0.97 | 50.8 |
| BASE tendencia + ruptura, sin forma · S10 | vol>=2.0x | 69 | 2.53 | 1.96 | 58.0 |
| BASE tendencia + ruptura, sin forma · S10 | vol>=3.0x | 16 | -3.09 | -2.67 | 43.8 |
| BASE tendencia + ruptura, sin forma · S10 | vol>=1.5x y volumen previo seco | 76 | 1.56 | 0.82 | 50.0 |

## Como leerlo

- Una forma aporta algo si su exceso le gana al de la BASE con el mismo stop, se repite en las dos mitades y en distintos regimenes, y su intervalo no incluye el cero.
- Con menos de 30 casos (o menos de 30 dias) no concluir nada.
- El retorno simulado no es una recomendacion ni incluye costos; sirve solo para comparar definiciones.
- Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo regimen, RS y plantilla con proxy propio, solo cierres, umbrales elegidos por mi.
