# Estudio VCP / retrocesos decrecientes + volumen

Universo: 346 activos. Datos Yahoo del 2024-10-31 al 2026-10-30. Retornos de cierre a cierre desde el dia de la ruptura.

| Categoria | n | Prom 20r % | Mediana 20r % | % positivos 20r | Exceso vs SPY 20r | Prom 5r | Prom 10r | % que toco el stop en 20r |
|---|---|---|---|---|---|---|---|---|
| Forma + ruptura del pivote (cualquier volumen) | 466 | 1.89 | 1.37 | 56.2 | 1.12 | 0.14 | 0.84 | 11.3 |
| Forma + ruptura con volumen >= 1,5x | 153 | 2.49 | 1.25 | 53.2 | 2.27 | 0.65 | 1.08 | 7.8 |
| Forma + ruptura con volumen < 1,5x | 417 | 1.55 | 0.9 | 55.0 | 0.72 | -0.07 | 0.57 | 11.8 |
| Forma + volumen seco previo + ruptura con volumen >= 1,5x | 53 | 3.64 | 2.2 | 62.5 | 3.4 | 1.14 | 1.49 | 6.2 |
| BASE: tendencia fuerte + ruptura de 20 ruedas, SIN la forma | 1148 | 2.01 | 1.01 | 55.1 | 0.83 | 0.35 | 0.95 | 16.0 |
| BASE con volumen >= 1,5x | 431 | 1.86 | 0.33 | 50.4 | 1.2 | 1.1 | 2.02 | 10.6 |

Cumplen la forma HOY (2026-10-30): 19 activos (detalle en data/vcp_forma_hoy.json).

## Como leerlo

- Cualquier categoria con n menor a 30 es muestra chica: no concluir nada.
- Lo que importa es la comparacion contra la BASE (misma tendencia, sin la forma) y el exceso vs SPY, no el promedio solo.
- Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un unico regimen de mercado, RS aproximado con retorno de 126 ruedas, umbral de volumen 1,5x elegido por mi (no validado).
- Los eventos del mismo ticker y categoria se separan >= 20 ruedas solo para no contar dos veces el mismo caso.
