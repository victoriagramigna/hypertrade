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
| V4A contracciones decrecientes · SU | 78 | 57 | 8.1 | 17.9 | 2.37 | 1.56 [-0.57, 3.65] | 64.1 | 0.32 |
| V4A contracciones decrecientes · S10L | 78 | 57 | 7.5 | 20.5 | 2.33 | 1.54 [-0.59, 3.63] | 64.1 | 0.35 |
| V4A contracciones decrecientes · F8 | 78 | 57 | 8.0 | 24.4 | 1.95 | 1.28 [-0.93, 3.3] | 60.3 | 0.24 |
| V4B + minimos que no bajan · SU | 64 | 50 | 8.1 | 17.2 | 2.47 | 1.74 [-0.62, 3.95] | 64.1 | 0.33 |
| V4B + minimos que no bajan · S10L | 64 | 50 | 7.5 | 18.8 | 2.48 | 1.76 [-0.65, 3.96] | 64.1 | 0.37 |
| V4B + minimos que no bajan · F8 | 64 | 50 | 8.0 | 25.0 | 1.84 | 1.28 [-1.29, 3.58] | 59.4 | 0.23 |
| V4A + plantilla · SU | 38 | 31 | 8.6 | 21.1 | 2.08 | 1.39 [-2.21, 4.64] | 57.9 | 0.28 |
| V4A + plantilla · S10L | 38 | 31 | 7.8 | 23.7 | 2.03 | 1.37 [-2.2, 4.6] | 57.9 | 0.39 |
| V4A + plantilla · F8 | 38 | 31 | 8.0 | 34.2 | 1.63 | 1.08 [-2.55, 4.43] | 52.6 | 0.2 |
| V4B + plantilla · SU | 32 | 27 | 8.6 | 15.6 | 3.1 | 2.56 [-1.22, 5.8] | 65.6 | 0.42 |
| V4B + plantilla · S10L | 32 | 27 | 7.9 | 15.6 | 3.17 | 2.61 [-1.21, 5.82] | 65.6 | 0.56 |
| V4B + plantilla · F8 | 32 | 27 | 8.0 | 31.2 | 2.31 | 1.95 [-1.92, 5.3] | 59.4 | 0.29 |
| BASE tendencia + ruptura, sin base VCP · S10L | 1172 | 215 | 11.0 | 27.6 | 1.36 | 0.36 [-0.39, 1.1] | 50.2 | 0.13 |
| BASE tendencia + ruptura, sin base VCP · F8 | 1172 | 215 | 8.0 | 35.0 | 1.1 | 0.13 [-0.55, 0.84] | 47.2 | 0.14 |

## 3. Por mitad del periodo (exceso vs SPY %)

| Definicion | primera (casos) | segunda (casos) |
|---|---|---|
| V4A contracciones decrecientes · S10L | 4.24 (31) | -0.23 (47) |
| V4A contracciones decrecientes · SU | 4.14 (31) | -0.14 (47) |
| V4B + minimos que no bajan · S10L | 4.7 (27) | -0.39 (37) |
| V4B + minimos que no bajan · SU | 4.59 (27) | -0.33 (37) |
| V4A + plantilla · S10L | 3.99 (18) | -0.99 (20) |
| V4A + plantilla · SU | 3.89 (18) | -0.86 (20) |
| V4B + plantilla · S10L | 5.18 (15) | 0.35 (17) |
| V4B + plantilla · SU | 5.06 (15) | 0.35 (17) |
| BASE tendencia + ruptura, sin base VCP · S10L | 1.66 (641) | -1.21 (531) |

## 4. Segun el regimen del mercado el dia de la ruptura (exceso vs SPY %)

| Definicion | SPY sobre su media de 50 (casos) | SPY bajo su media de 50 (casos) |
|---|---|---|
| V4A contracciones decrecientes · S10L | 1.41 (74) | 3.92 (4) |
| V4A contracciones decrecientes · SU | 1.43 (74) | 3.92 (4) |
| V4B + minimos que no bajan · S10L | 1.61 (60) | 3.92 (4) |
| V4B + minimos que no bajan · SU | 1.6 (60) | 3.92 (4) |
| V4A + plantilla · S10L | 1.07 (34) | 3.92 (4) |
| V4A + plantilla · SU | 1.09 (34) | 3.92 (4) |
| V4B + plantilla · S10L | 2.43 (28) | 3.92 (4) |
| V4B + plantilla · SU | 2.37 (28) | 3.92 (4) |
| BASE tendencia + ruptura, sin base VCP · S10L | 0.57 (1005) | -0.89 (167) |

## 5. Por trimestre, stop S10L (exceso vs SPY %, casos)

| Definicion | 2025-T4 | 2026-T1 | 2026-T2 | 2026-T3 | 2026-T4 |
|---|---|---|---|---|---|
| V4A contracciones decrecientes | 1.05 (15) | 8.99 (14) | -0.41 (30) | -0.47 (19) | - |
| V4B + minimos que no bajan | 1.27 (13) | 10.06 (12) | -0.79 (20) | -0.47 (19) | - |
| V4A + plantilla | 0.57 (8) | 8.98 (9) | -4.34 (13) | 2.89 (8) | - |
| V4B + plantilla | 0.88 (6) | 10.74 (8) | -3.07 (10) | 2.89 (8) | - |
| BASE tendencia + ruptura, sin base VCP | 2.22 (212) | 1.84 (316) | -0.68 (367) | -1.38 (275) | -1.53 (2) |

## 6. Volumen de la ruptura, stop S10L (exceso vs SPY %)

| Definicion | Condicion | Casos | Retorno % | Exceso % | % ganadoras |
|---|---|---|---|---|---|
| V4A contracciones decrecientes · S10L | vol>=1.0x | 25 | 4.02 | 3.54 | 68.0 |
| V4A contracciones decrecientes · S10L | vol>=1.5x | 9 | -2.16 | -1.75 | 44.4 |
| V4A contracciones decrecientes · S10L | vol>=2.0x | 2 | -0.53 | -0.04 | 50.0 |
| V4A contracciones decrecientes · S10L | vol>=3.0x | 1 | 6.11 | 5.85 | 100.0 |
| V4A contracciones decrecientes · S10L | vol>=1.5x y volumen previo seco | 5 | 5.31 | 4.86 | 60.0 |
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
| riesgo 5-8% | 30 | 6.6 | 20.0 | 2.7 | 1.87 | 0.38 |
| riesgo 8-10% | 28 | 9.0 | 14.3 | 2.99 | 1.79 | 0.34 |
| riesgo >10% | 14 | 11.3 | 21.4 | -0.11 | -0.64 | -0.01 |
| 2 contracciones | 55 | 8.3 | 14.5 | 2.79 | 1.94 | 0.38 |
| 3 contracciones | 17 | 7.7 | 23.5 | 0.76 | -0.43 | 0.13 |
| 4 contracciones | 6 | 7.5 | 33.3 | 3.09 | 3.77 | 0.27 |

## 8. Sensibilidad al largo del giro (exceso vs SPY %, stop S10L, casos)

| Definicion | K=3 | K=5 | K=8 |
|---|---|---|---|
| V4A contracciones decrecientes | 0.01 (81) | 1.54 (78) | 0.74 (70) |
| V4B + minimos que no bajan | 0.36 (65) | 1.76 (64) | 0.13 (57) |
| V4A + plantilla | 0.11 (56) | 1.37 (38) | -0.11 (28) |
| V4B + plantilla | 0.5 (41) | 2.61 (32) | -1.25 (23) |
| BASE tendencia + ruptura, sin base VCP | 0.42 (1175) | 0.36 (1172) | 0.39 (1177) |

## 9. Bases VCP vigentes hoy, sin ruptura (3)

| Ticker | Contracciones | Profundidades % | Minimos suben | Cierre | Pivote | Stop | A pivote % | Riesgo desde pivote % | Tendencia | Plantilla 9/9 |
|---|---|---|---|---|---|---|---|---|---|---|
| ADI | 2 | 12.1 > 9.6 | si | 417.11 | 422.67 | 382.0 | 1.3 | 9.6 | si | no |
| VRSN | 2 | 11.2 > 7.0 | si | 307.21 | 311.61 | 289.66 | 1.4 | 7.0 | si | si |
| JPM | 2 | 10.2 > 4.1 | si | 337.04 | 344.4 | 330.4 | 2.2 | 4.1 | no | no |

## 10. Diagnostico de hoy: cuantos activos pasan cada filtro

- Activos evaluados: 346
- Con al menos 4 giros confirmados: 346
- Cuyo ultimo giro es un minimo: 164
- Con base valida (contracciones decrecientes, ultima <=10%, primera >=10%, recencia): 7
- ... y todavia sin romper pivote ni stop: 3
- ... y ademas en tendencia: 3

## Como leerlo

- Una forma aporta algo si su exceso le gana al de la BASE con el mismo stop (S10L o F8), se repite en las dos mitades y en distintos regimenes, y su intervalo no incluye el cero.
- Con menos de 30 casos (o menos de 30 dias) no concluir nada.
- SU (stop bajo el ultimo minimo) no se puede comparar con la BASE: tiene otro riesgo. Se mira por su R y por tramos de riesgo.
- Riesgos conocidos: ~1 anio de eventos y un solo regimen; universo actual (supervivencia); RS y plantilla con proxy propio; entrada al cierre de la ruptura (en la practica se puede comprar antes, intradia); SPY medido al cierre aunque la salida sea intradia; umbrales de la base (10%, 10%, 95%, 40/60/150 ruedas) elegidos por mi; el giro se confirma K ruedas tarde, asi que las rupturas que ocurren antes de que se confirme el ultimo minimo no cuentan; el retorno simulado no incluye costos ni es una recomendacion.
