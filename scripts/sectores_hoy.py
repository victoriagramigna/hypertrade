"""
Cuadro "Sectores hoy" (Inicio): los 11 ETFs sectoriales SPDR con su rendimiento del dia, de 5 ruedas y de 1 mes.
Solo informativo: no entra en ningun calculo, alerta ni registro de la Auditoria. Usa los cierres que el radar
ya trae en memoria (precios), asi que no agrega ninguna descarga.
"""
import logging

log = logging.getLogger("radar.sectores_hoy")

SECTORES = {
    "XLK": "Tecnología", "XLC": "Comunicaciones", "XLY": "Consumo discrecional", "XLP": "Consumo básico",
    "XLV": "Salud", "XLF": "Financiero", "XLE": "Energía", "XLI": "Industriales",
    "XLB": "Materiales", "XLU": "Servicios públicos", "XLRE": "Inmobiliario",
}


def _ret(s, n):
    s = s.dropna()
    if len(s) <= n or float(s.iloc[-n - 1]) <= 0:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[-n - 1]) - 1) * 100, 2)


def calcular(precios: dict, benchmark: str):
    try:
        spy = precios.get(benchmark)
        spy_dia = _ret(spy, 1) if spy is not None else None
        out = []
        for t, nombre in SECTORES.items():
            s = precios.get(t)
            if s is None or s.dropna().empty:
                continue
            dia = _ret(s, 1)
            out.append({
                "Ticker": t, "Sector": nombre, "Precio": round(float(s.dropna().iloc[-1]), 2),
                "Var_dia_%": dia, "Ret_5d_%": _ret(s, 5), "Ret_1m_%": _ret(s, 21),
                "Vs_SPY_dia_pp": round(dia - spy_dia, 2) if dia is not None and spy_dia is not None else None,
            })
        return {"spy_dia_%": spy_dia, "sectores": out}
    except Exception as e:
        log.error(f"Sectores hoy fallo, no afecta al resto de la corrida: {e}")
        return None
