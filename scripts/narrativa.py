# -*- coding: utf-8 -*-
"""
Arma el texto explicativo al pie de cada tarjeta de alerta, a partir de
las columnas que ya trae cada fila (df_rs + las agregadas por
radar_score.py v2). No hace ningún cálculo nuevo -- solo interpreta lo
que el score ya evaluó. Se llama por cada alerta, justo antes de
guardar data/ultimo.json.
"""
import pandas as pd


def _frase_rs(fila: dict) -> str:
    rs = fila.get("RS_Score")
    sector = fila.get("Sector")
    if rs is None:
        return None
    if rs > 80:
        return f"Lidera con fuerza relativa {rs:.0f}" + (f" (sector {sector})." if sector else ".")
    return None


def _frase_contraccion(fila: dict) -> str:
    vcp = fila.get("VCP_valido")
    atr = fila.get("ATR_Contraction")
    if vcp and atr:
        return "Contracción de volatilidad confirmada por VCP y por ATR -- doble señal de compresión previa a ruptura."
    if vcp:
        return "Patrón VCP activo -- rango de precio comprimiéndose."
    if atr:
        return "Volatilidad reciente por debajo de su promedio (ATR) -- posible compresión previa a ruptura."
    return None


def _frase_tendencia(fila: dict) -> str:
    if fila.get("Sobre_SMA50") and fila.get("Pendiente_OK"):
        return "Tendencia alcista confirmada, con SMA50 y SMA200 en pendiente ascendente."
    if fila.get("Sobre_SMA50"):
        return "Precio por encima de su SMA50."
    return None


def _frase_avwap(fila: dict) -> str:
    if not fila.get("Apoyo_AVWAP"):
        return None
    precio = fila.get("Precio")
    candidatos = [
        ("su AVWAP anclado al inicio del año", fila.get("AVWAP_YTD")),
        ("su AVWAP anclado al último gap relevante", fila.get("AVWAP_Ultimo_Gap")),
    ]
    candidatos = [(n, v) for n, v in candidatos if v is not None and pd.notna(v)]
    if candidatos and precio is not None:
        nombre, valor = min(candidatos, key=lambda c: abs(precio - c[1]))
        return f"Apoya sobre {nombre} (${valor:.2f}) -- zona de costo promedio institucional."
    return "Apoya sobre un nivel de soporte técnico relevante (SMA50/AVWAP)."


def _frase_cruce_52w(fila: dict) -> str:
    if fila.get("Cruce_AVWAP_52w"):
        return "Cruzó al alza su AVWAP anclado al máximo de 52 semanas -- posible absorción de vendedores atrapados en el techo."
    return None


def _frase_52w(fila: dict) -> str:
    dist = fila.get("Dist_Max52w_%")
    if dist is not None and pd.notna(dist) and dist > -5:
        return "Operando cerca de su máximo de 52 semanas."
    return None


def _frase_contexto(dist_days: int, mult_dist: float, regimen_sano: bool) -> str:
    partes = []
    if not regimen_sano:
        partes.append("⚠️ régimen de mercado volátil (VIX elevado)")
    if mult_dist < 1.0:
        partes.append(f"⚠️ {dist_days} días de distribución institucional en las últimas 5 semanas")
    if not partes:
        return None
    return "Contexto de mercado: " + "; ".join(partes) + "."


_GENERADORES = [_frase_rs, _frase_tendencia, _frase_avwap, _frase_contraccion, _frase_cruce_52w, _frase_52w]


def armar_narrativa(fila: dict, dist_days: int = 0, mult_dist: float = 1.0, regimen_sano: bool = True) -> str:
    """
    fila: el diccionario de la alerta (ya trae todas las columnas de
    df_rs, incluidas las nuevas de radar_score.py v2 -- en main.py esto
    es {**fila.to_dict(), **rec} dentro del loop de recomendaciones).
    """
    frases = [f for f in (gen(fila) for gen in _GENERADORES) if f]
    cuerpo = " ".join(frases) if frases else "Sin señales técnicas adicionales destacadas."

    contexto = _frase_contexto(dist_days, mult_dist, regimen_sano)
    if contexto:
        cuerpo += " " + contexto

    score = fila.get("Radar_Score")
    pie = f"Radar Score: {score:.0f}/100" if score is not None else ""

    return f"{cuerpo}\n{pie}".strip()
