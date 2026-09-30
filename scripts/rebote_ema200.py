"""
Rebote en EMA200 -- señal EXPERIMENTAL, en modo "solo medir" (ver charla
con Victoria, 30/9/2026): comprar la corrección contra el soporte de
LARGO plazo (EMA200), no solo esperar el cruce de SMA50 como hace el
flujo principal.

Condiciones (todas, sobre un ticker LÍDER -- RS Score >= UMBRAL_LIDER_RS,
mismo umbral que "Líder apoyando en soporte"):
  1. La EMA200 tiene pendiente ascendente (tendencia de fondo sana).
  2. En los últimos VENTANA_TOQUE_DIAS el precio se acercó a la EMA200
     (a menos de UMBRAL_CERCA_PCT%) sin romperla de forma decisiva (nunca
     cerró más de UMBRAL_RUPTURA_PCT% por debajo).
  3. Hoy rebota: cierra por encima de la EMA200 y por encima del cierre
     de ayer.

A DIFERENCIA de todas las demás señales del sistema, esta todavía NO se
muestra como alerta -- ni tarjeta en el dashboard, ni aviso de Telegram.
Solo queda registrada en la bitácora (log_alertas.jsonl) con la misma
"foto" que cualquier otra señal, para que dentro de un tiempo la
Auditoría pueda medir si de verdad anticipa un movimiento rentable antes
de usarla para decidir una compra real. Es 100% aditiva: no toca ni un
solo cálculo de ninguna otra señal ni del Radar Score.
"""
import logging
from config import UMBRAL_LIDER_RS

log = logging.getLogger("radar.rebote_ema200")

VENTANA_TOQUE_DIAS = 5       # días hacia atrás en los que se busca el "toque" a la EMA200
UMBRAL_CERCA_PCT = 3         # a cuántos % (por encima o por debajo) de la EMA200 se considera "la tocó"
UMBRAL_RUPTURA_PCT = 6       # si cerró más de esto por debajo de la EMA200, ya es ruptura real, no rebote
# La pendiente de la EMA200 se mide en una ventana MÁS LARGA (30 ruedas)
# que la del toque (5 ruedas) a propósito: mirar solo los últimos 5 días
# para juzgar "tendencia de fondo" confunde el ruido del propio pullback
# (que por definición empuja a la EMA200 hacia abajo esos días) con la
# tendencia real de más largo plazo -- un ticker en una suba sostenida de
# meses puede tener la EMA200 momentáneamente plana en una ventana de 5
# días just cuando está tocándola, sin que eso signifique que la
# tendencia de fondo se dio vuelta.
VENTANA_PENDIENTE_DIAS = 30


def detectar_rebote_ema200(precios: dict, tickers_sector: dict, rs_por_ticker: dict, historial: dict):
    """
    Devuelve (candidatos, historial) -- candidatos son dicts con forma de
    alerta (Ticker, Sector, Tipo, Estado, etc.), listos para pasarle
    directo a bitacora.registrar_eventos(). Solo incluye episodios NUEVOS
    (si el rebote sigue "activo" en corridas sucesivas del mismo pullback,
    no se vuelve a registrar cada día -- mismo criterio que el resto del
    sistema).
    """
    candidatos = []
    for ticker, sector in tickers_sector.items():
        if ticker not in precios:
            continue
        close = precios[ticker].dropna()
        if len(close) < 200 + VENTANA_PENDIENTE_DIAS:
            continue

        rs_ticker = rs_por_ticker.get(ticker)
        ticker_hist = historial.setdefault(ticker, {})

        if rs_ticker is None or rs_ticker < UMBRAL_LIDER_RS:
            ticker_hist["rebote_ema200_activo"] = False
            continue

        ema200 = close.ewm(span=200, adjust=False).mean()
        ema200_pendiente_ok = bool(ema200.iloc[-1] > ema200.iloc[-1 - VENTANA_PENDIENTE_DIAS])

        precio_hoy, precio_ayer = close.iloc[-1], close.iloc[-2]
        ema200_hoy = ema200.iloc[-1]

        ventana_close = close.iloc[-VENTANA_TOQUE_DIAS:-1]
        ventana_ema = ema200.iloc[-VENTANA_TOQUE_DIAS:-1]
        distancias_pct = (ventana_close / ventana_ema - 1) * 100

        toco = bool((distancias_pct <= UMBRAL_CERCA_PCT).any())
        no_rompio = bool((distancias_pct >= -UMBRAL_RUPTURA_PCT).all())
        rebotando_hoy = bool(precio_hoy > ema200_hoy and precio_hoy > precio_ayer)

        activo = ema200_pendiente_ok and toco and no_rompio and rebotando_hoy
        activo_previo = ticker_hist.get("rebote_ema200_activo", False)
        ticker_hist["rebote_ema200_activo"] = activo

        if activo and not activo_previo:
            candidatos.append({
                "Ticker": ticker,
                "Sector": sector,
                "Tipo": "rebote_ema200",
                "Estado": "🧪 Rebote en EMA200 (experimental, solo en medición)",
                "Score_num": None,
                "Recomendación final": None,
                "Precio": round(float(precio_hoy), 2),
                "Vol_rel": None,
                "RSI": None,
                "Regimen_Score": None,
                "Cuidados_claves": [],
            })

    return candidatos, historial
