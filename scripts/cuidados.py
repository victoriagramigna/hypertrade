"""
Puntos de cuidado -- la otra cara de la narrativa.

La narrativa cuenta lo que está a favor de una alerta. Esto cuenta lo que
está EN CONTRA, como el análisis de Warren Bife sobre MRVL ("SMA50 con
pendiente negativa", "llegó al AVWAP del último máximo con pico de
volumen"). Solo se evalúa en alertas alcistas: en una de venta, estas
cosas no son un riesgo sino parte de la razón de la señal.

No cambia la recomendación ni el Radar Score. Se muestra en la tarjeta,
se guarda en la bitácora y la Auditoría compara si las alertas CON puntos
de cuidado rinden peor que las que no tienen -- si no rinden peor, estas
reglas no están sirviendo y habría que revisarlas.
"""
import pandas as pd

VENTANA_PENDIENTE = 10       # ruedas para medir si la SMA50 sube o baja
AVWAP_CERCA_PCT = 3          # "llegó al AVWAP" = a no más de 3% por debajo
VOL_ALTO = 1.5               # volumen relativo que cuenta como pico
EXTENSION_SMA50_PCT = 20     # más de 20% sobre la SMA50 = extendida
RSI_SOBRECOMPRA = 75


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def es_alerta_alcista(fila: dict) -> bool:
    rec = (fila.get("Recomendación final") or "").upper()
    estado = (fila.get("Estado") or "").lower()
    if rec == "VENTA" or "rompió piso" in estado or "perdió" in estado:
        return False
    return True


def puntos_de_cuidado(fila: dict, close: pd.Series | None) -> list[dict]:
    """Devuelve una lista de {'clave', 'texto'}; vacía si no hay nada que advertir."""
    if not es_alerta_alcista(fila):
        return []

    cuidados = []
    precio = _num(fila.get("Precio"))

    # 1. SMA50 con pendiente negativa
    if close is not None:
        c = close.dropna()
        if len(c) >= 50 + VENTANA_PENDIENTE:
            sma50 = c.rolling(50).mean()
            hoy, antes = float(sma50.iloc[-1]), float(sma50.iloc[-1 - VENTANA_PENDIENTE])
            if hoy < antes:
                cuidados.append({
                    "clave": "sma50_bajando",
                    "texto": f"SMA50 con pendiente negativa (${hoy:.2f}, bajando): la tendencia de mediano plazo todavía no acompaña.",
                })

    # 2. Debajo de la SMA200
    dist200 = _num(fila.get("Dist_SMA200_%"))
    sma200 = _num(fila.get("SMA200"))
    if dist200 is not None and dist200 < 0:
        valor = f" (${sma200:.2f})" if sma200 else ""
        cuidados.append({
            "clave": "bajo_sma200",
            "texto": f"Debajo de su SMA200{valor}, a {dist200:.1f}%: la tendencia de largo plazo está en contra.",
        })

    # 3. Llegó al AVWAP del máximo de 52 semanas (desde abajo)
    avwap = _num(fila.get("AVWAP_52W_High"))
    vol = _num(fila.get("Vol_rel"))
    if avwap and precio and precio <= avwap and (avwap - precio) / avwap * 100 <= AVWAP_CERCA_PCT:
        if vol is not None and vol >= VOL_ALTO:
            cuidados.append({
                "clave": "techo_avwap_volumen",
                "texto": (f"Llegó al AVWAP del máximo de 52 semanas (${avwap:.2f}) con volumen alto ({vol:.1f}x): "
                          "ahí suelen vender los que compraron arriba -- podría ser toma de ganancias."),
            })
        else:
            cuidados.append({
                "clave": "techo_avwap",
                "texto": (f"Justo debajo del AVWAP del máximo de 52 semanas (${avwap:.2f}): "
                          "resistencia probable hasta que logre superarlo."),
            })

    # 4. Muy extendida sobre la SMA50
    dist50 = _num(fila.get("Dist_SMA50_%"))
    if dist50 is not None and dist50 > EXTENSION_SMA50_PCT:
        cuidados.append({
            "clave": "extendida",
            "texto": (f"Muy extendida: {dist50:.1f}% sobre su SMA50. Comprar acá deja el stop lejos "
                      "y una corrección hacia la media es más probable."),
        })

    # 5. Sobrecompra de corto plazo
    rsi = _num(fila.get("RSI"))
    if rsi is not None and rsi >= RSI_SOBRECOMPRA:
        cuidados.append({
            "clave": "rsi_alto",
            "texto": f"RSI en {rsi:.0f}: sobrecompra de corto plazo, suele haber pausas o retrocesos.",
        })

    return cuidados
