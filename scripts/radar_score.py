"""
Radar Score (v1): puntaje compuesto 0-100 pensado para "¿esto es una buena
OPORTUNIDAD DE COMPRA ahora?", no "¿es una buena empresa?". Por eso el
timing de entrada (VCP + volumen) pesa tanto como la fuerza relativa sola,
en vez de dejar que un RS altísimo domine todo el puntaje (el clásico
error de "comprar en la punta").

Componentes (definidos en la charla con Victoria, sept. 2026):
  - RS Score:                        30 pts  (RS_Score/100 * 30)
  - VCP / Contracción:               30 pts  (30 si VCP_valido, si no 0)
  - Volumen de confirmación:         15 pts  (escala con Vol_rel, tope en 1.5x)
  - Tendencia (SMA50+SMA200+sector+mercado): 15 pts  (4 sub-condiciones, 3.75c/u)
  - Posición en 52 semanas:          10 pts  (0% del máx=10pts, -30% o peor=0pts)

Régimen de mercado (VIX): NO es un componente más, es un MULTIPLICADOR
sobre el score final -- un setup perfecto en un mercado nervioso vale
menos que el mismo setup en un mercado sano (regla de que ~3 de cada 4
acciones se mueven en la dirección del mercado general).

IMPORTANTE: esta distribución de pesos es un punto de partida razonable,
NO algo todavía validado con datos reales -- eso es justamente lo que va
a permitir ajustar el backtest sobre la bitácora de eventos, más adelante.
"""
import pandas as pd

TOPE_VOL_REL = 1.5        # Vol_rel a partir del cual el componente de volumen ya vale los 15 pts completos
TOPE_DIST_52W_PCT = -30   # Dist_Max52w_% a partir del cual el componente de 52 semanas vale 0 pts
MULTIPLICADOR_VIX_VOLATIL = 0.7


def _componente_volumen(vol_rel):
    if vol_rel is None or pd.isna(vol_rel):
        return 0
    return round(min(15, max(0, vol_rel / TOPE_VOL_REL * 15)), 2)


def _componente_52_semanas(dist_max52w_pct):
    if dist_max52w_pct is None or pd.isna(dist_max52w_pct):
        return 0
    # 0% (en el máximo) -> 10 pts ; TOPE_DIST_52W_PCT (-30%) o peor -> 0 pts
    return round(min(10, max(0, (dist_max52w_pct - TOPE_DIST_52W_PCT) / (-TOPE_DIST_52W_PCT) * 10)), 2)


def _componente_tendencia(sobre_sma50, dist_sma200_pct, rs_sector, spy_sobre_sma50):
    sub_puntos = 15 / 4  # 4 sub-condiciones, 3.75 c/u
    total = 0
    if sobre_sma50:
        total += sub_puntos
    if dist_sma200_pct is not None and not pd.isna(dist_sma200_pct) and dist_sma200_pct > 0:
        total += sub_puntos
    if rs_sector is not None and rs_sector > 50:
        total += sub_puntos
    if spy_sobre_sma50:
        total += sub_puntos
    return round(total, 2)


def calcular_radar_score(df_rs: pd.DataFrame, rs_por_sector: dict, spy_sobre_sma50: bool, regimen: dict) -> pd.DataFrame:
    """
    Agrega la columna "Radar_Score" a df_rs (una fila por ticker del
    universo). No modifica ninguna columna existente.
    """
    if df_rs.empty:
        df_rs["Radar_Score"] = []
        return df_rs

    multiplicador = 1.0
    if not regimen.get("sin_datos") and not regimen.get("sano", True):
        multiplicador = MULTIPLICADOR_VIX_VOLATIL

    scores = []
    for _, fila in df_rs.iterrows():
        comp_rs = round((fila.get("RS_Score") or 0) / 100 * 30, 2)
        comp_vcp = 30 if fila.get("VCP_valido") else 0
        comp_vol = _componente_volumen(fila.get("Vol_rel"))
        comp_tendencia = _componente_tendencia(
            fila.get("Sobre_SMA50"), fila.get("Dist_SMA200_%"),
            rs_por_sector.get(fila.get("Sector")), spy_sobre_sma50,
        )
        comp_52w = _componente_52_semanas(fila.get("Dist_Max52w_%"))

        bruto = comp_rs + comp_vcp + comp_vol + comp_tendencia + comp_52w
        scores.append(round(min(100, bruto) * multiplicador, 1))

    df_rs = df_rs.copy()
    df_rs["Radar_Score"] = scores
    return df_rs
