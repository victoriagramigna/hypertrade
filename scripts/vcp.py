"""
Detección de VCP (Volatility Contraction Pattern), estilo Minervini.
Busca "olas" de consolidación sucesivas donde tanto el rango de precio
como el volumen promedio van DISMINUYENDO -- señal de que la oferta se
está agotando antes de un posible quiebre al alza.

Es una aproximación simplificada (ventanas fijas de N días) -- no un
detector de patrones gráficos con visión por computadora, pero captura
la idea central: contracción sucesiva y decreciente.
"""
import pandas as pd
from config import VCP_MIN_CONTRACCIONES, VCP_VENTANA_DIAS


def detectar_vcp(close: pd.Series, volumen: pd.Series, n_olas: int = 4) -> dict:
    """
    Divide los últimos (n_olas * VCP_VENTANA_DIAS) días en `n_olas` ventanas
    consecutivas y mide, para cada una, el rango de precio (%) y el volumen
    promedio. Si al menos VCP_MIN_CONTRACCIONES ventanas consecutivas muestran
    rango Y volumen decrecientes, se considera un VCP válido.
    """
    total_dias = n_olas * VCP_VENTANA_DIAS
    if len(close) < total_dias:
        return {"valido": False, "motivo": "historia insuficiente", "olas": []}

    close_reciente = close.iloc[-total_dias:]
    vol_reciente = volumen.iloc[-total_dias:]

    olas = []
    for i in range(n_olas):
        inicio = i * VCP_VENTANA_DIAS
        fin = inicio + VCP_VENTANA_DIAS
        ventana_precio = close_reciente.iloc[inicio:fin]
        ventana_vol = vol_reciente.iloc[inicio:fin]

        rango_pct = (ventana_precio.max() - ventana_precio.min()) / ventana_precio.min() * 100
        vol_prom = ventana_vol.mean()
        olas.append({"ola": i + 1, "rango_%": round(rango_pct, 2), "vol_prom": round(vol_prom, 0)})

    # Contar contracciones consecutivas: rango Y volumen bajan respecto a la ola anterior
    contracciones = 0
    for i in range(1, len(olas)):
        rango_baja = olas[i]["rango_%"] < olas[i - 1]["rango_%"]
        vol_baja = olas[i]["vol_prom"] < olas[i - 1]["vol_prom"]
        if rango_baja and vol_baja:
            contracciones += 1

    valido = contracciones >= VCP_MIN_CONTRACCIONES
    return {
        "valido": valido,
        "contracciones_detectadas": contracciones,
        "olas": olas,  # de la más vieja a la más reciente
        "motivo": None if valido else f"solo {contracciones} contracción(es), se necesitan {VCP_MIN_CONTRACCIONES}",
    }
