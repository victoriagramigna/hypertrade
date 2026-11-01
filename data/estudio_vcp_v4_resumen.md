# Estudio VCP v4 -- contracciones reales (maximos/minimos del dia)

Universo: 346 activos. Yahoo del 2024-10-31 al 2026-10-30. Giros confirmados a 5 ruedas (sin mirar el futuro). Operacion simulada: entrada al cierre de la ruptura; salida al tocar el stop con el MINIMO del dia (al stop, o a la apertura si abrio por debajo) o a las 20 ruedas. Exceso = retorno menos el de SPY (cierre) en la misma tenencia. Intervalos remuestreando DIAS completos.

## 1. Contexto de mercado (retorno medio a 20 ruedas, cualquier dia)

| Periodo | Dias | SPY % | Universo % |
|---|---|---|---|
| primera mitad | 114 | 1.51 | 2.45 |
| segunda mitad | 115 | 1.17 | 1.02 |
| 2025-T4 | 40 | 1.47 | 3.95 |
| 2026-T1 | 61 | 0.26 | 0.99 |
| 2026-T2 | 62 | 2.6 | 1.98 |
| 2026-T3 | 64 | 1.14 | 0.9 |
| 2026-T4 | 2 | -0.55 | -1.33 |

Corte de mitades: 2026-04-21.

## 2. Formas y BASE: todo el periodo

| Definicion | Casos | Dias | Riesgo % | % toco stop | Retorno % | Exceso vs SPY % [IC95 por dias] | % ganadoras | R |
|---|---|---|---|---|---|---|---|---|
| V4A contracciones decrecientes · SU | 81 | 59 | 8.2 | 19.8 | 2.25 | 1.49 [-0.7, 3.43] | 63.0 | 0.3 |
| V4A contracciones decrecientes · S10L | 81 | 59 | 7.6 | 21.0 | 2.25 | 1.5 [-0.68, 3.44] | 63.0 | 0.33 |
| V4A contracciones decrecientes · F8 | 81 | 59 | 8.0 | 25.9 | 1.85 | 1.22 [-1.06, 3.22] | 59.3 | 0.23 |
| V4B + minimos que no bajan · SU | 66 | 51 | 8.2 | 18.2 | 2.48 | 1.77 [-0.65, 4.06] | 63.6 | 0.32 |
| V4B + minimos que no bajan · S10L | 66 | 51 | 7.6 | 19.7 | 2.49 | 1.78 [-0.64, 4.06] | 63.6 | 0.36 |
| V4B + minimos que no bajan · F8 | 66 | 51 | 8.0 | 25.8 | 1.87 | 1.32 [-1.09, 3.62] | 59.1 | 0.23 |
| V4A + plantilla · SU | 39 | 32 | 8.6 | 23.1 | 1.81 | 1.15 [-2.26, 4.26] | 56.4 | 0.25 |
| V4A + plantilla · S10L | 39 | 32 | 7.8 | 25.6 | 1.77 | 1.13 [-2.33, 4.2] | 56.4 | 0.35 |
| V4A + plantilla · F8 | 39 | 32 | 8.0 | 35.9 | 1.38 | 0.85 [-2.53, 3.98] | 51.3 | 0.17 |
| V4B + plantilla · SU | 33 | 28 | 8.6 | 18.2 | 2.76 | 2.24 [-1.54, 5.68] | 63.6 | 0.38 |
| V4B + plantilla · S10L | 33 | 28 | 7.9 | 18.2 | 2.82 | 2.29 [-1.49, 5.68] | 63.6 | 0.52 |
| V4B + plantilla · F8 | 33 | 28 | 8.0 | 33.3 | 1.99 | 1.66 [-2.06, 5.03] | 57.6 | 0.25 |
| BASE tendencia + ruptura, sin base VCP · S10L | 1172 | 215 | 11.0 | 27.6 | 1.36 | 0.36 [-0.39, 1.1] | 50.2 | 0.13 |
| BASE tendencia + ruptura, sin base VCP · F8 | 1172 | 215 | 8.0 | 35.0 | 1.1 | 0.13 [-0.55, 0.84] | 47.2 | 0.14 |

## 3. Por mitad del periodo (exceso vs SPY %)

| Definicion | primera (casos) | segunda (casos) |
|---|---|---|
| V4A contracciones decrecientes · S10L | 4.25 (33) | -0.4 (48) |
| V4A contracciones decrecientes · SU | 4.1 (33) | -0.3 (48) |
| V4B + minimos que no bajan · S10L | 5.01 (28) | -0.59 (38) |
| V4B + minimos que no bajan · SU | 4.9 (28) | -0.54 (38) |
| V4A + plantilla · S10L | 3.99 (18) | -1.33 (21) |
| V4A + plantilla · SU | 3.89 (18) | -1.21 (21) |
| V4B + plantilla · S10L | 5.18 (15) | -0.12 (18) |
| V4B + plantilla · SU | 5.06 (15) | -0.12 (18) |
| BASE tendencia + ruptura, sin base VCP · S10L | 1.66 (641) | -1.21 (531) |

## 4. Segun el regimen del mercado el dia de la ruptura (exceso vs SPY %)

| Definicion | SPY sobre su media de 50 (casos) | SPY bajo su media de 50 (casos) |
|---|---|---|
| V4A contracciones decrecientes · S10L | 1.37 (77) | 3.92 (4) |
| V4A contracciones decrecientes · SU | 1.37 (77) | 3.92 (4) |
| V4B + minimos que no bajan · S10L | 1.65 (62) | 3.92 (4) |
| V4B + minimos que no bajan · SU | 1.63 (62) | 3.92 (4) |
| V4A + plantilla · S10L | 0.81 (35) | 3.92 (4) |
| V4A + plantilla · SU | 0.83 (35) | 3.92 (4) |
| V4B + plantilla · S10L | 2.06 (29) | 3.92 (4) |
| V4B + plantilla · SU | 2.0 (29) | 3.92 (4) |
| BASE tendencia + ruptura, sin base VCP · S10L | 0.57 (1005) | -0.89 (167) |

## 5. Por trimestre, stop S10L (exceso vs SPY %, casos)

| Definicion | 2025-T4 | 2026-T1 | 2026-T2 | 2026-T3 | 2026-T4 |
|---|---|---|---|---|---|
| V4A contracciones decrecientes | 1.05 (15) | 8.43 (16) | -0.66 (31) | -0.47 (19) | - |
| V4B + minimos que no bajan | 1.27 (13) | 10.32 (13) | -1.14 (21) | -0.47 (19) | - |
| V4A + plantilla | 0.57 (8) | 8.98 (9) | -4.61 (14) | 2.89 (8) | - |
| V4B + plantilla | 0.88 (6) | 10.74 (8) | -3.53 (11) | 2.89 (8) | - |
| BASE tendencia + ruptura, sin base VCP | 2.22 (212) | 1.84 (316) | -0.68 (367) | -1.38 (275) | -1.53 (2) |

## 6. Volumen de la ruptura, stop S10L (exceso vs SPY %)

| Definicion | Condicion | Casos | Retorno % | Exceso % | % ganadoras |
|---|---|---|---|---|---|
| V4A contracciones decrecientes · S10L | vol>=1.0x | 27 | 4.07 | 3.61 | 66.7 |
| V4A contracciones decrecientes · S10L | vol>=1.5x | 11 | -0.91 | -0.61 | 45.5 |
| V4A contracciones decrecientes · S10L | vol>=2.0x | 4 | 2.1 | 2.23 | 50.0 |
| V4A contracciones decrecientes · S10L | vol>=3.0x | 2 | 9.86 | 9.59 | 100.0 |
| V4A contracciones decrecientes · S10L | vol>=1.5x y volumen previo seco | 7 | 5.14 | 4.76 | 57.1 |
| V4A + plantilla · S10L | vol>=1.0x | 12 | 5.03 | 4.77 | 66.7 |
| V4A + plantilla · S10L | vol>=1.5x | 4 | -2.19 | -2.76 | 25.0 |
| V4A + plantilla · S10L | vol>=2.0x | 1 | 6.11 | 5.85 | 100.0 |
| V4A + plantilla · S10L | vol>=3.0x | 1 | 6.11 | 5.85 | 100.0 |
| V4A + plantilla · S10L | vol>=1.5x y volumen previo seco | 3 | 1.67 | 0.44 | 33.3 |
| BASE tendencia + ruptura, sin base VCP · S10L | vol>=1.0x | 565 | 1.91 | 1.15 | 52.9 |
| BASE tendencia + ruptura, sin base VCP · S10L | vol>=1.5x | 207 | 1.59 | 0.78 | 51.2 |
| BASE tendencia + ruptura, sin base VCP · S10L | vol>=2.0x | 76 | 2.08 | 1.35 | 56.6 |
| BASE tendencia + ruptura, sin base VCP · S10L | vol>=3.0x | 20 | -1.11 | -1.0 | 45.0 |
| BASE tendencia + ruptura, sin base VCP · S10L | vol>=1.5x y volumen previo seco | 75 | 2.86 | 1.99 | 54.7 |

## 7. V4A con su stop de manual (SU): por riesgo al stop y por cantidad de contracciones

| Grupo | Casos | Riesgo % | % toco stop | Retorno % | Exceso % | R |
|---|---|---|---|---|---|---|
| riesgo <=5% | 6 | 4.5 | 16.7 | 3.61 | 4.1 | 0.72 |
| riesgo 5-8% | 31 | 6.6 | 22.6 | 2.36 | 1.61 | 0.33 |
| riesgo 8-10% | 29 | 8.9 | 17.2 | 2.6 | 1.44 | 0.29 |
| riesgo >10% | 15 | 11.5 | 20.0 | 0.8 | 0.29 | 0.05 |
| 2 contracciones | 56 | 8.3 | 16.1 | 2.59 | 1.76 | 0.36 |
| 3 contracciones | 18 | 8.1 | 22.2 | 1.47 | 0.34 | 0.18 |
| 4 contracciones | 7 | 7.6 | 42.9 | 1.51 | 2.34 | 0.09 |

## 8. Sensibilidad al largo del giro (exceso vs SPY %, stop S10L, casos)

| Definicion | K=3 | K=5 | K=8 |
|---|---|---|---|
| V4A contracciones decrecientes | -0.08 (82) | 1.5 (81) | 0.85 (71) |
| V4B + minimos que no bajan | 0.24 (66) | 1.78 (66) | 0.27 (58) |
| V4A + plantilla | -0.02 (57) | 1.13 (39) | -0.11 (28) |
| V4B + plantilla | 0.31 (42) | 2.29 (33) | -1.25 (23) |
| BASE tendencia + ruptura, sin base VCP | 0.42 (1175) | 0.36 (1172) | 0.39 (1176) |

## 9. Bases VCP vigentes hoy, sin ruptura (0)

| Ticker | Contracciones | Profundidades % | Minimos suben | Cierre | Pivote | Stop | A pivote % | Riesgo desde pivote % | Tendencia | Plantilla 9/9 |
|---|---|---|---|---|---|---|---|---|---|---|

## Como leerlo

- Una forma aporta algo si su exceso le gana al de la BASE con el mismo stop (S10L o F8), se repite en las dos mitades y en distintos regimenes, y su intervalo no incluye el cero.
- Con menos de 30 casos (o menos de 30 dias) no concluir nada.
- SU (stop bajo el ultimo minimo) no se puede comparar con la BASE: tiene otro riesgo. Se mira por su R y por tramos de riesgo.
- Riesgos conocidos: ~1 anio de eventos y un solo regimen; universo actual (supervivencia); RS y plantilla con proxy propio; entrada al cierre de la ruptura (en la practica se puede comprar antes, intradia); SPY medido al cierre aunque la salida sea intradia; umbrales de la base (10%, 10%, 95%, 40/60/150 ruedas) elegidos por mi; el giro se confirma K ruedas tarde, asi que las rupturas que ocurren antes de que se confirme el ultimo minimo no cuentan; el retorno simulado no incluye costos ni es una recomendacion.
