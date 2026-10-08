# Estudio Gap alcista (CEDEARs)

Generado: 2026-10-08T22:02 UTC · Regla: suba >= 3% de cierre a cierre, ayer sobre SMA200, hoy máximo de 10 ruedas (igual que el radar), sin otro gap en las 5 ruedas previas.
Volatilidad: baja <= 30.0% anual, media <= 50.0%, alta > 50.0% (desvío de 60 ruedas anualizado, mediana del papel).
Papeles analizados: 300 {'alta': 64, 'baja': 127, 'media': 109}. Eventos: 5540.
Entrenamiento hasta 2024-10-08, prueba después.

## Qué pasó después del gap — volatilidad baja o media (n=3971)
- +1 ruedas: mediana 0.02% (50.2% positivos), contra SPY -0.07 pts
- +5 ruedas: mediana 0.25% (52.6% positivos), contra SPY -0.16 pts
- +10 ruedas: mediana 0.66% (54.5% positivos), contra SPY -0.15 pts
- +20 ruedas: mediana 1.26% (55.5% positivos), contra SPY -0.34 pts
- Peor caída en las 10 ruedas siguientes (mediana): -3.74%

## Qué pasó después del gap — volatilidad alta (n=1569)
- +1 ruedas: mediana 0.07% (50.7% positivos), contra SPY -0.05 pts
- +5 ruedas: mediana 0.03% (50.0% positivos), contra SPY -0.34 pts
- +10 ruedas: mediana 1.08% (53.7% positivos), contra SPY 0.18 pts
- +20 ruedas: mediana 0.96% (51.9% positivos), contra SPY -0.08 pts
- Peor caída en las 10 ruedas siguientes (mediana): -7.22%

## ¿Depende del año o del mercado? (volatilidad baja o media, +5 ruedas)
- 2022: 269 gaps, mediana -0.84% (40.1% positivos), peor caída 10 ruedas -4.68%
- 2023: 847 gaps, mediana 0.33% (53.6% positivos), peor caída 10 ruedas -3.33%
- 2024: 926 gaps, mediana 0.12% (51.3% positivos), peor caída 10 ruedas -3.57%
- 2025: 930 gaps, mediana 0.47% (55.8% positivos), peor caída 10 ruedas -3.53%
- 2026: 999 gaps, mediana 0.43% (53.3% positivos), peor caída 10 ruedas -4.18%
- SPY sobre su SMA200: 3509 gaps, mediana 0.18% (51.9% positivos)
- SPY bajo su SMA200: 462 gaps, mediana 1.07% (57.6% positivos)

## Señales de la previa con lift ≥1,3 en entrenamiento y prueba — baja o media
- ATR 14 (% del precio): quintil 5 -> lift 1.85 (entrenamiento) y 1.43 (prueba); tasa de gap pronto 18.27% vs 12.74% base.
- Distancia al máximo de 52 semanas (%): quintil 1 -> lift 1.5 (entrenamiento) y 1.34 (prueba); tasa de gap pronto 17.08% vs 12.74% base.
