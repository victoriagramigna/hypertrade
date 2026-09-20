# Radar de Mercado

App personal para descubrir oportunidades de inversión (no trackea cartera propia — para eso está MERVALETA, por separado).

**Uso estrictamente personal.** Las señales son reglas técnicas propias, no recomendaciones de inversión.

## Qué hace

1. Trae precios de un universo de ~20 tickers (yfinance), agrupados por sector
2. Calcula RS Score (fuerza relativa vs SPY) y lo agrupa por sector — detecta rotación sectorial
3. Detecta eventos del día: cruce de SMA50 con confirmaciones (volumen, RSI, base previa, sector acompañando) → Score de Confirmación 0-5
4. Ajusta la señal técnica con contexto (noticias sectoriales + riesgo país/brecha cambiaria local)
5. Guarda todo en `data/ultimo.json` para el dashboard
6. (Pendiente de conectar) Notifica por Telegram cuando hay una alerta relevante

## Setup

```bash
pip install -r requirements.txt
```

### Secrets necesarios (GitHub Settings → Secrets and variables → Actions)

| Secret | Para qué |
|---|---|
| `FINNHUB_API_KEY` | Noticias por ticker, calendario de earnings (pendiente de conectar) |
| `TELEGRAM_BOT_TOKEN` | Notificaciones al bot (pendiente de conectar) |
| `TELEGRAM_CHAT_ID` | A quién le llega el mensaje (pendiente de conectar) |

**Nunca poner estos valores directamente en el código**, ni siquiera "para probar rápido".

### Correr localmente

```bash
cd scripts
python main.py
```

### Correr en GitHub Actions

- El workflow (`.github/workflows/radar.yml`) corre solo, en cron
- **Antes de confiar en el cron**: correrlo manualmente una vez desde la pestaña "Actions" → "Run workflow", con `modo=test`, y revisar que `data/ultimo.json` se generó bien
- Los crons automáticos siempre corren en modo `test` (no mandan notificaciones reales) hasta que se decida pasar a `produccion` a mano

## Estructura

```
scripts/
  config.py          -- universo de tickers, sectores, parámetros del score y estados
  datos.py            -- traída de precios (yfinance), con manejo de errores por ticker
  rs_score.py          -- cálculo de RS Score
  alertas.py           -- v2: score 0-7, estados narrativos, confirmación con demora, stop-loss
  vcp.py               -- detección de VCP (Volatility Contraction Pattern, estilo Minervini)
  regimen_mercado.py   -- filtro de régimen de mercado vía VIX
  historial.py         -- persistencia de estado entre corridas (necesario para confirmación con demora)
  contexto.py           -- noticias sectoriales + contexto macro-local
  main.py               -- orquesta todo, guarda data/ultimo.json
data/
  ultimo.json          -- resultado de la última corrida (lo lee el dashboard)
  historial_alertas.json -- estado persistente por ticker, entre corridas
.github/workflows/
  radar.yml            -- automatización (cron diario + intradiario)
```

## Sistema de Score (v2, ampliado a 0-7)

Inspirado parcialmente en el "Warren Score" (Minervini): cruce SMA50, volumen fuerte,
RSI diario sano, base previa ordenada, sector+mercado acompañando, **VCP válido**
(contracciones decrecientes de precio y volumen -- pilar "Setup"), y **RSI semanal
cruzando alcista**.

Cada alerta tiene además un **estado narrativo** (no reemplaza el score, lo acompaña):
- 🔨 Recién cruzó, sin confirmar
- ⚠️ Sacudón, sin definición clara
- ✅ Confirmado (sostuvo 2+ días verdes, o hizo nuevo máximo)
- 💣 Ruptura de máximo con volumen
- 🔻 Rompió piso (SMA200)
- 🛑 Stop-loss sugerido (perdió EMA200 tras venir confirmado)

La confirmación es **con demora** (`DIAS_CONFIRMACION` en `config.py`): una señal
recién detectada no salta a "confirmado" de un día para el otro, necesita
sostenerse. Esto requiere el historial persistente entre corridas -- por eso
`data/historial_alertas.json` se commitea junto con `ultimo.json` en cada corrida.

Además, el **régimen de mercado general (VIX)** ajusta las recomendaciones: si el
VIX está por encima del umbral (`VIX_UMBRAL_ALTO`), cualquier señal de COMPRA se
baja a MANTENER, igual que hace el contexto macro-local de Argentina.

## Ampliar el universo de tickers

Editar `scripts/config.py`, diccionario `TICKERS`. No requiere tocar nada más.

## Pendiente / próximos pasos

- [ ] Conectar Finnhub real (noticias, earnings) — hoy `traer_titulares_ejemplo()` en `main.py` es un placeholder
- [ ] Conectar ArgentinaDatos/BCRA real — hoy `traer_contexto_macro_ejemplo()` es un placeholder
- [ ] Bot de Telegram — disparo real de notificaciones
- [ ] Revisar ToS de Finnhub antes de publicar el dashboard más ampliamente (uso personal por ahora)
- [ ] Backtest con datos reales (ya validado con datos simulados — ver `backtest.py` de la etapa de diseño), ahora también hay que backtestear el score ampliado v2 (VCP, RSI semanal)
- [ ] Deduplicación de alertas (no repetir la misma alerta en cada corrida intradiaria del mismo día)
- [ ] Manejo de feriados de mercado (pandas_market_calendars)
- [ ] Dashboard HTML que lea `data/ultimo.json` (hoy hay un prototipo visual con datos simulados, falta conectarlo a datos reales) -- también falta sumarle el Score v2 (0-7), estados narrativos y el régimen VIX
