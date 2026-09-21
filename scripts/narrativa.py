# -*- coding: utf-8 -*-
"""
Narrativa v2.1: cada condición técnica mencionada incluye su valor
numérico exacto entre paréntesis (SMA50, SMA200, AVWAP, precio del
máximo de 52 semanas, ATR_Ratio) -- no solo el nombre de la condición.

CAMBIO v2.1: Distribution Days ya no se describe como "penalización"
del score (porque dejó de serlo, ver radar_score.py) -- se menciona
como contexto de mercado puro, informativo, independiente de si
afecta o no el puntaje.
"""
import pandas as pd


ORDEN_NARRATIVA = [
    "rs_alto",
    "stage2",
    "apoyo_soporte",
    "gap_alcista",
    "cruce_avwap_52w",
    "vcp",
    "atr_contraction",
]


def _fmt(valor):
    """Formatea un precio como $XX.XX, o cadena vacía si no hay dato."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    return f"${valor:.2f}"


def _frase_rs_alto(row: pd.Series) -> str:
    ticker = row.get("Ticker", row.get("ticker", "El ticker"))
    rs = row.get("RS_Score", "?")
    sector = row.get("Sector", row.get("sector", ""))
    if sector:
        return f"{ticker} lidera con fuerza relativa {rs} (destaca en el sector {sector})."
    return f"{ticker} lidera con fuerza relativa {rs}."


def _frase_stage2(row: pd.Series) -> str:
    sma50 = _fmt(row.get("SMA50"))
    sma200 = _fmt(row.get("SMA200"))
    if sma50 and sma200:
        return f"Tendencia alcista confirmada: por encima de su SMA50 ({sma50}) y su SMA200 ({sma200}), ambas con pendiente ascendente."
    return "Tendencia alcista confirmada: SMA50 y SMA200 con pendiente ascendente."


def _frase_apoyo_soporte(row: pd.Series) -> str:
    close = row.get("Close", row.get("Precio"))
    sma50 = row.get("SMA50")
    avwap_ytd = row.get("AVWAP_YTD")
    avwap_gap = row.get("AVWAP_Ultimo_Gap")

    candidatos = []
    if pd.notna(sma50) if sma50 is not None else False:
        candidatos.append(("su SMA50", sma50))
    if avwap_ytd is not None and pd.notna(avwap_ytd):
        candidatos.append(("su AVWAP anclado al inicio del año", avwap_ytd))
    if avwap_gap is not None and pd.notna(avwap_gap):
        candidatos.append(("su AVWAP anclado al último gap relevante", avwap_gap))

    if not candidatos or close is None:
        return "Apoya sobre un nivel de soporte técnico relevante."

    nombre, valor = min(candidatos, key=lambda c: abs(close - c[1]))
    return f"Apoya sobre {nombre} ({_fmt(valor)}), dentro de zona de tolerancia."


def _frase_gap_alcista(row: pd.Series) -> str:
    gap_pct = row.get("Gap_Pct", row.get("Var_dia_%"))
    if gap_pct is not None and pd.notna(gap_pct):
        return f"Salto de {gap_pct:.1f}% con volumen, por encima de su SMA200 -- momentum de corto plazo."
    return "Salto alcista reciente con volumen, por encima de su SMA200 -- momentum de corto plazo."


def _frase_cruce_avwap_52w(row: pd.Series) -> str:
    valor = _fmt(row.get("AVWAP_52W_High"))
    if valor:
        return f"Cruzó al alza su AVWAP anclado al máximo de 52 semanas ({valor}) -- posible absorción de vendedores atrapados en el techo."
    return "Cruzó al alza su AVWAP anclado al máximo de 52 semanas -- posible absorción de vendedores atrapados en el techo."


def _frase_vcp(row: pd.Series) -> str:
    return "Contracción de volatilidad detectada (VCP) -- rango de precio comprimiéndose, posible preparación de ruptura."


def _frase_atr_contraction(row: pd.Series) -> str:
    ratio = row.get("ATR_Ratio")
    if ratio is not None and pd.notna(ratio):
        return f"Volatilidad relativa por debajo del promedio (ATR10/ATR50: {ratio:.2f})."
    return "Volatilidad relativa por debajo del promedio reciente."


_PLANTILLAS = {
    "rs_alto": _frase_rs_alto,
    "stage2": _frase_stage2,
    "apoyo_soporte": _frase_apoyo_soporte,
    "gap_alcista": _frase_gap_alcista,
    "cruce_avwap_52w": _frase_cruce_avwap_52w,
    "vcp": _frase_vcp,
    "atr_contraction": _frase_atr_contraction,
}


def _frase_contexto_mercado(dist_days: int, regimen_sano: bool) -> str:
    """
    v2.1: puramente informativo -- Distribution Days ya no penaliza el
    score, así que esta frase describe el contexto sin decir que el
    puntaje se ajustó por esto.
    """
    partes = []
    if not regimen_sano:
        partes.append("régimen de mercado volátil (VIX elevado)")
    if dist_days is not None and dist_days >= 4:
        partes.append(f"{dist_days} días de distribución institucional en las últimas 5 semanas")
    if not partes:
        return None
    return "Contexto de mercado: " + "; ".join(partes) + "."


def armar_narrativa(
    row: pd.Series,
    dist_days: int = 0,
    mult_dist: float = 1.0,  # se mantiene el parámetro por compatibilidad, ya no se usa
    regimen_sano: bool = True,
) -> str:
    """
    row: el diccionario de la alerta (fila.to_dict() + rec + extras_por_ticker
    en main.py) -- ya trae todas las columnas necesarias, incluidas SMA50,
    SMA200, AVWAP_*, ATR_Ratio, etc.
    """
    señales_activas = row.get("señales_activas")
    if señales_activas is None:
        # Reconstruye la lista de señales activas a partir de los booleanos
        # ya presentes en la fila, por si no viene armada de antes.
        señales_activas = []
        if (row.get("RS_Score") or 0) > 80:
            señales_activas.append("rs_alto")
        if row.get("Sobre_SMA50") and row.get("Pendiente_OK"):
            señales_activas.append("stage2")
        if row.get("Apoyo_AVWAP"):
            señales_activas.append("apoyo_soporte")
        if row.get("Tipo") == "gap_alcista":
            señales_activas.append("gap_alcista")
        if row.get("Cruce_AVWAP_52w"):
            señales_activas.append("cruce_avwap_52w")
        if row.get("VCP_valido"):
            señales_activas.append("vcp")
        if row.get("ATR_Contraction"):
            señales_activas.append("atr_contraction")

    activas_ordenadas = [s for s in ORDEN_NARRATIVA if s in señales_activas]

    frases = []
    for señal in activas_ordenadas:
        funcion_plantilla = _PLANTILLAS.get(señal)
        if funcion_plantilla:
            frases.append(funcion_plantilla(row))

    cuerpo = " ".join(frases) if frases else "Sin señales técnicas adicionales destacadas."

    contexto_mercado = _frase_contexto_mercado(dist_days, regimen_sano)
    if contexto_mercado:
        cuerpo += " " + contexto_mercado

    score = row.get("Radar_Score")
    pie = f"Radar Score: {score:.0f}/100" if score is not None else ""

    return f"{cuerpo}\n{pie}".strip()
