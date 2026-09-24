"""
crypto_radar.py
Módulo independiente de HyperTrade para monitorear criptomonedas (BTC, ETH, ...).

No depende de main.py ni config.py del universo de acciones/CEDEARs.
Pensado para correr en un workflow de GitHub Actions aparte, con su propio
cron (cripto cotiza 24/7, no tiene sentido atarlo al horario de mercado).

Salida: data/cripto.json

Para sumar una moneda nueva, agregala a CRYPTO_TICKERS. Nada más del código
necesita tocarse.
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from telegram_bot import enviar_mensaje, DISCLAIMER

# ---------------------------------------------------------------------------
# CONFIG — acá se suman/sacan monedas. El símbolo es el ticker de yfinance.
# ---------------------------------------------------------------------------
CRYPTO_TICKERS = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    # "SOL-USD": "Solana",   # ejemplo de cómo sumar una nueva
}

OUTPUT_PATH = "data/cripto.json"
NOTIFICACIONES_PATH = "data/cripto_notificaciones.json"

# Pesos del Score v1 (0-100). Es una primera aproximación pensada para la
# volatilidad de cripto; fácil de recalibrar más adelante con datos reales.
SCORE_WEIGHTS = {
    "tendencia": 35,   # relación SMA50 vs SMA200 y pendiente
    "momentum": 25,    # zona de RSI
    "volumen": 20,     # volumen relativo a su propio promedio
    "distancia_max52w": 20,  # qué tan cerca/lejos está del máximo de 52 semanas
}

RSI_PERIOD = 14
SMA_CORTA = 50
SMA_LARGA = 200
VOL_LOOKBACK = 20

# ---------------------------------------------------------------------------
# INDICADORES
# ---------------------------------------------------------------------------

def calcular_rsi(precios: pd.Series, periodo: int = RSI_PERIOD) -> pd.Series:
    delta = precios.diff()
    ganancia = delta.clip(lower=0)
    perdida = -delta.clip(upper=0)
    avg_ganancia = ganancia.rolling(periodo).mean()
    avg_perdida = perdida.rolling(periodo).mean()
    rs = avg_ganancia / avg_perdida.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calcular_indicadores(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["SMA50"] = df["Close"].rolling(SMA_CORTA).mean()
    df["SMA200"] = df["Close"].rolling(SMA_LARGA).mean()
    df["RSI"] = calcular_rsi(df["Close"])
    df["VolAvg20"] = df["Volume"].rolling(VOL_LOOKBACK).mean()

    ultimo = df.iloc[-1]
    previo = df.iloc[-2] if len(df) > 1 else ultimo

    precio = float(ultimo["Close"])
    sma50 = float(ultimo["SMA50"]) if not pd.isna(ultimo["SMA50"]) else None
    sma200 = float(ultimo["SMA200"]) if not pd.isna(ultimo["SMA200"]) else None
    rsi = float(ultimo["RSI"]) if not pd.isna(ultimo["RSI"]) else None
    vol_rel = (
        float(ultimo["Volume"] / ultimo["VolAvg20"])
        if not pd.isna(ultimo["VolAvg20"]) and ultimo["VolAvg20"] > 0
        else None
    )

    max_52w = float(df["Close"].tail(365).max())
    dist_max52w_pct = round((precio / max_52w - 1) * 100, 2) if max_52w else None

    # Detección de cruce dorado/muerte (comparando el estado de ayer vs hoy)
    cruce = None
    if not pd.isna(ultimo["SMA50"]) and not pd.isna(ultimo["SMA200"]) \
            and not pd.isna(previo["SMA50"]) and not pd.isna(previo["SMA200"]):
        hoy_arriba = ultimo["SMA50"] > ultimo["SMA200"]
        ayer_arriba = previo["SMA50"] > previo["SMA200"]
        if hoy_arriba and not ayer_arriba:
            cruce = "cruce_dorado"
        elif not hoy_arriba and ayer_arriba:
            cruce = "cruce_muerte"

    return {
        "precio": round(precio, 2),
        "sma50": round(sma50, 2) if sma50 else None,
        "sma200": round(sma200, 2) if sma200 else None,
        "rsi": round(rsi, 1) if rsi else None,
        "vol_rel": round(vol_rel, 2) if vol_rel else None,
        "max_52w": round(max_52w, 2),
        "dist_max52w_pct": dist_max52w_pct,
        "tendencia_alcista": bool(sma50 and sma200 and sma50 > sma200),
        "cruce": cruce,
    }


def calcular_score(ind: dict) -> dict:
    """Score compuesto 0-100 + detalle de sub-puntajes, para poder auditar
    por qué dio ese número."""
    detalle = {}

    # Tendencia: SMA50 sobre SMA200 = full puntaje; si está por debajo, 0
    if ind["sma50"] is not None and ind["sma200"] is not None:
        detalle["tendencia"] = SCORE_WEIGHTS["tendencia"] if ind["tendencia_alcista"] else 0
    else:
        detalle["tendencia"] = 0

    # Momentum vía RSI: mejor puntaje en zona 45-65 (tendencia sana, sin
    # sobrecompra extrema); penaliza sobrecompra >75 y sobreventa <30
    rsi = ind["rsi"]
    if rsi is None:
        detalle["momentum"] = 0
    elif 45 <= rsi <= 65:
        detalle["momentum"] = SCORE_WEIGHTS["momentum"]
    elif 30 < rsi < 45 or 65 < rsi <= 75:
        detalle["momentum"] = round(SCORE_WEIGHTS["momentum"] * 0.6)
    else:
        detalle["momentum"] = round(SCORE_WEIGHTS["momentum"] * 0.2)

    # Volumen: >1.5x su promedio suma completo, entre 1-1.5x parcial
    vol_rel = ind["vol_rel"]
    if vol_rel is None:
        detalle["volumen"] = 0
    elif vol_rel >= 1.5:
        detalle["volumen"] = SCORE_WEIGHTS["volumen"]
    elif vol_rel >= 1.0:
        detalle["volumen"] = round(SCORE_WEIGHTS["volumen"] * 0.5)
    else:
        detalle["volumen"] = 0

    # Distancia a máximo 52w: cerca del máximo (0 a -10%) puntúa alto;
    # muy lejos (<-30%) puntúa bajo
    dist = ind["dist_max52w_pct"]
    if dist is None:
        detalle["distancia_max52w"] = 0
    elif dist >= -10:
        detalle["distancia_max52w"] = SCORE_WEIGHTS["distancia_max52w"]
    elif dist >= -30:
        detalle["distancia_max52w"] = round(SCORE_WEIGHTS["distancia_max52w"] * 0.5)
    else:
        detalle["distancia_max52w"] = 0

    total = sum(detalle.values())
    return {"score_total": total, "detalle": detalle}


def generar_alertas(nombre: str, ind: dict, score: dict) -> list:
    alertas = []

    if ind["cruce"] == "cruce_dorado":
        alertas.append({
            "tipo": "Cruce dorado (SMA50 > SMA200)",
            "narrativa": f"{nombre} cruzó su media de 50 ruedas por encima de la de 200: "
                         f"señal clásica de cambio a tendencia alcista de mediano plazo.",
        })
    elif ind["cruce"] == "cruce_muerte":
        alertas.append({
            "tipo": "Cruce de la muerte (SMA50 < SMA200)",
            "narrativa": f"{nombre} perdió su media de 50 ruedas por debajo de la de 200: "
                         f"señal de deterioro de tendencia de mediano plazo.",
        })

    if ind["rsi"] is not None:
        if ind["rsi"] >= 75:
            alertas.append({
                "tipo": "RSI en sobrecompra",
                "narrativa": f"{nombre} tiene RSI de {ind['rsi']}, zona de sobrecompra: "
                             f"posible descanso o corrección de corto plazo.",
            })
        elif ind["rsi"] <= 30:
            alertas.append({
                "tipo": "RSI en sobreventa",
                "narrativa": f"{nombre} tiene RSI de {ind['rsi']}, zona de sobreventa: "
                             f"posible rebote técnico de corto plazo.",
            })

    if ind["dist_max52w_pct"] is not None and ind["dist_max52w_pct"] >= -0.5:
        alertas.append({
            "tipo": "Nuevo máximo de 52 semanas",
            "narrativa": f"{nombre} está haciendo nuevo máximo de 52 semanas "
                         f"(${ind['max_52w']}).",
        })

    if ind["vol_rel"] is not None and ind["vol_rel"] >= 2:
        alertas.append({
            "tipo": "Volumen anómalo",
            "narrativa": f"{nombre} opera con volumen {round(ind['vol_rel'], 1)}x su "
                         f"promedio de {VOL_LOOKBACK} ruedas.",
        })

    return alertas


# ---------------------------------------------------------------------------
# TELEGRAM -- reutiliza el mismo bot que las alertas de acciones, con su
# propio archivo de deduplicación (una alerta por moneda+tipo se notifica
# como máximo una vez por día UTC, aunque el script corra cada 4hs).
# ---------------------------------------------------------------------------

def cargar_notificaciones() -> dict:
    try:
        with open(NOTIFICACIONES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_notificaciones(notificaciones: dict) -> None:
    os.makedirs(os.path.dirname(NOTIFICACIONES_PATH), exist_ok=True)
    with open(NOTIFICACIONES_PATH, "w", encoding="utf-8") as f:
        json.dump(notificaciones, f, ensure_ascii=False, indent=2)


def formatear_alerta_cripto(nombre: str, ticker: str, alerta: dict) -> str:
    return (
        f"🪙 <b>{nombre}</b> ({ticker})\n"
        f"{alerta['tipo']}\n"
        f"{alerta['narrativa']}"
    )


def notificar_alertas_cripto(resultados: list, modo: str) -> None:
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notificaciones = cargar_notificaciones()

    # Junta todas las alertas de hoy que todavía no se notificaron
    pendientes = []
    for r in resultados:
        if r.get("error"):
            continue
        for alerta in r.get("alertas", []):
            clave = f"{r['ticker']}|{alerta['tipo']}"
            if notificaciones.get(clave) != hoy:
                pendientes.append((clave, r, alerta))

    if not pendientes:
        print("Cripto: sin alertas nuevas para notificar hoy.")
        return

    if modo != "produccion":
        print(f"MODO=test -- NO se envían notificaciones reales de cripto ({len(pendientes)} pendiente(s)):")
        for _, r, alerta in pendientes:
            print(f"  [TEST] {r['nombre']}: {alerta['tipo']}")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    enviados = 0
    for clave, r, alerta in pendientes:
        texto = formatear_alerta_cripto(r["nombre"], r["ticker"], alerta) + DISCLAIMER
        if enviar_mensaje(token, chat_id, texto):
            enviados += 1
            notificaciones[clave] = hoy

    guardar_notificaciones(notificaciones)
    print(f"Cripto: {enviados}/{len(pendientes)} alerta(s) enviada(s) a Telegram.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def procesar_ticker(ticker: str, nombre: str) -> dict:
    df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
    if df.empty or len(df) < 60:
        return {
            "ticker": ticker,
            "nombre": nombre,
            "error": "datos insuficientes o falla de descarga",
        }

    # yfinance a veces devuelve columnas MultiIndex si se pide más de un ticker;
    # acá siempre es uno solo, pero por las dudas se aplana.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    ind = calcular_indicadores(df)
    score = calcular_score(ind)
    alertas = generar_alertas(nombre, ind, score)

    return {
        "ticker": ticker,
        "nombre": nombre,
        **ind,
        "score": score["score_total"],
        "score_detalle": score["detalle"],
        "alertas": alertas,
    }


def main():
    resultados = []
    for ticker, nombre in CRYPTO_TICKERS.items():
        try:
            resultados.append(procesar_ticker(ticker, nombre))
        except Exception as e:
            resultados.append({"ticker": ticker, "nombre": nombre, "error": str(e)})

    salida = {
        "actualizado_utc": datetime.now(timezone.utc).isoformat(),
        "criptomonedas": resultados,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH} con {len(resultados)} criptomonedas.")

    modo = os.environ.get("RADAR_MODO", "test")
    notificar_alertas_cripto(resultados, modo)


if __name__ == "__main__":
    main()
