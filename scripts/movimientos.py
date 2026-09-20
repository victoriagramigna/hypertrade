"""
Panel de "Movimientos del día": detecta tickers que subieron o bajaron fuerte
HOY (variación de un solo día), a diferencia del RS Score que mide fuerza
relativa en plazos de 1-6 meses. Es información complementaria, no reemplaza
nada de lo demás -- sirve para ver de un vistazo qué se movió fuerte hoy,
sea porque confirma una tendencia o porque es puro ruido/noticia puntual.
"""
import logging
from config import UMBRAL_MOVIMIENTO_DIARIO_PCT

log = logging.getLogger("radar.movimientos")


def detectar_movimientos_diarios(precios: dict, tickers_sector: dict):
    """
    precios: dict {ticker: pd.Series de precios de cierre}
    Devuelve una lista de dicts, uno por ticker que se movió más que el
    umbral hoy, ordenada de mayor a menor movimiento absoluto.
    """
    movimientos = []

    for ticker, sector in tickers_sector.items():
        if ticker not in precios:
            continue
        close = precios[ticker].dropna()
        if len(close) < 2:
            continue

        precio_hoy, precio_ayer = close.iloc[-1], close.iloc[-2]
        if precio_ayer == 0:
            continue

        variacion_pct = round((precio_hoy / precio_ayer - 1) * 100, 2)

        if abs(variacion_pct) >= UMBRAL_MOVIMIENTO_DIARIO_PCT:
            movimientos.append({
                "Ticker": ticker,
                "Sector": sector,
                "Variacion_dia_%": variacion_pct,
                "Precio": round(float(precio_hoy), 2),
                "Direccion": "sube" if variacion_pct > 0 else "baja",
            })

    movimientos.sort(key=lambda m: abs(m["Variacion_dia_%"]), reverse=True)
    return movimientos
