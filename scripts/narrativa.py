# -*- coding: utf-8 -*-
"""
Narrativa por tarjeta — HyperTrade
=====================================

Arma el texto explicativo que va al pie de cada tarjeta de alerta,
usando SOLO las señales que ya calculó radar_score_v2.py — nada de
IA ni llamadas externas, 100% determinístico y gratis.

Cada plantilla recibe la fila del ticker para insertar valores
concretos (precio, RS Score, sector, etc.) donde haga falta.
"""

import pandas as pd


# Orden de prioridad para la narrativa: de mayor a menor peso, así la
# frase más importante siempre aparece primero
ORDEN_NARRATIVA = [
    "rs_alto",
    "stage2",
    "apoyo_soporte",
    "gap_alcista",
    "cruce_avwap_52w",
    "vcp",
    "atr_contraction",
]


def _frase_rs_alto(row: pd.Series) -> str:
    ticker = row.get("Ticker", row.get("ticker", "El ticker"))
    rs = row.get("RS_Score", "?")
    sector = row.get("Sector", row.get("sector", ""))
    if sector:
        return f"{ticker} lidera con fuerza relativa {rs} (destaca en el sector {sector})."
    return f"{ticker} lidera con fuerza relativa {rs}."


def _frase_stage2(row: pd.Series) -> str:
    return "Tendencia alcista confirmada: precio por encima de SMA50 y SMA200, ambas con pendiente positiva."


def _frase_apoyo_soporte(row: pd.Series) -> str:
    close = row.get("Close")
    sma50 = row.get("SMA50")
    avwap_ytd = row.get("AVWAP_YTD")
    avwap_gap = row.get("AVWAP_Ultimo_Gap")

    # Determina cuál de los tres soportes es el más cercano al precio,
    # para nombrarlo específicamente en la frase
    candidatos = []
    if pd.notna(sma50):
        candidatos.append(("su SMA50", sma50))
    if pd.notna(avwap_ytd):
        candidatos.append(("su AVWAP anclado al inicio del año", avwap_ytd))
    if pd.notna(avwap_gap):
        candidatos.append(("su AVWAP anclado al último gap relevante", avwap_gap))

    if not candidatos or pd.isna(close):
        return "Apoya sobre un nivel de soporte técnico relevante."

    nombre, valor = min(candidatos, key=lambda c: abs(close - c[1]))
    return f"Apoya sobre {nombre} (${valor:.2f}), dentro de zona de tolerancia."


def _frase_gap_alcista(row: pd.Series) -> str:
    gap_pct = row.get("Gap_Pct", row.get("gap_pct"))
    if pd.notna(gap_pct):
        return f"Salto de {gap_pct:.1f}% con volumen, por encima de su SMA200 — momentum de corto plazo."
    return "Salto alcista reciente con volumen, por encima de su SMA200 — momentum de corto plazo."


def _frase_cruce_avwap_52w(row: pd.Series) -> str:
    return "Cruzó al alza su AVWAP anclado al máximo de 52 semanas — posible absorción de vendedores atrapados en el techo."


def _frase_vcp(row: pd.Series) -> str:
    return "Contracción de volatilidad detectada (VCP) — rango de precio comprimiéndose, posible preparación de ruptura."


def _frase_atr_contraction(row: pd.Series) -> str:
    ratio = row.get("ATR_Ratio")
    if pd.notna(ratio):
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


def _frase_contexto_mercado(distribution_days: int, penalizacion_mercado: int) -> str:
    if penalizacion_mercado == 0:
        return ""
    elif penalizacion_mercado == -1:
        return f"⚠️ Contexto de mercado con presión de venta institucional inicial: {distribution_days} días de distribución en las últimas 5 semanas."
    else:
        return f"⚠️ Contexto de mercado adverso: {distribution_days} días de distribución institucional en las últimas 5 semanas — señal a tomar con cautela."


def armar_narrativa(
    row: pd.Series,
    señales_activas: list,
    distribution_days: int = 0,
    penalizacion_mercado: int = 0,
    regimen_sano: bool = True,
    riesgo_pais: float = None,
) -> str:
    """
    Arma el texto completo para el pie de la tarjeta.

    row: fila de hoy del ticker (para valores concretos)
    señales_activas: la lista que devuelve calcular_score_compuesto()
        en radar_score_v2.py
    distribution_days, penalizacion_mercado: el contexto global de
        esa corrida (mismos valores para todos los tickers)
    regimen_sano: si el régimen de mercado general está sano (ya lo
        calculás en el pipeline actual)
    riesgo_pais: valor de riesgo país de esa corrida, si lo tenés
        disponible a mano

    Devuelve el texto final, listo para mostrar en la tarjeta.
    """
    frases = []

    # Ordena las señales activas según la prioridad definida arriba,
    # ignorando las que no tienen plantilla
    activas_ordenadas = [s for s in ORDEN_NARRATIVA if s in señales_activas]

    for señal in activas_ordenadas:
        funcion_plantilla = _PLANTILLAS.get(señal)
        if funcion_plantilla:
            frases.append(funcion_plantilla(row))

    cuerpo = " ".join(frases) if frases else "Sin señales técnicas destacadas más allá del disparo base."

    contexto_mercado = _frase_contexto_mercado(distribution_days, penalizacion_mercado)
    if contexto_mercado:
        cuerpo += " " + contexto_mercado

    # Línea de pie con el resumen numérico
    regimen_texto = "sano" if regimen_sano else "no sano"
    pie = f"Régimen de mercado: {regimen_texto}"
    if riesgo_pais is not None:
        pie += f" · Riesgo país: {riesgo_pais:.0f}"

    return f"{cuerpo}\n{pie}"


# ---------------------------------------------------------------------------
# EJEMPLO DE USO (después de calcular_score_compuesto en radar_score_v2.py)
# ---------------------------------------------------------------------------
#
#   resultado_score = calcular_score_compuesto(fila_hoy, señales, penalizacion_mercado)
#
#   texto_tarjeta = armar_narrativa(
#       row=fila_hoy,
#       señales_activas=resultado_score["señales_activas"],
#       distribution_days=dist_days,
#       penalizacion_mercado=penalizacion_mercado,
#       regimen_sano=regimen_mercado["sano"],      # ya lo tenés en el pipeline
#       riesgo_pais=contexto_macro["riesgo_pais"], # ya lo tenés en el pipeline
#   )
#
#   # texto_tarjeta va directo al JSON, en un campo nuevo como
#   # "narrativa" dentro de cada alerta, para que el dashboard lo
#   # muestre al pie de la tarjeta
#
# ---------------------------------------------------------------------------
