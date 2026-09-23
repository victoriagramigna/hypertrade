"""
Régimen de mercado 0-100 -- "¿está el clima para comprar acciones?"

No mira ninguna acción en particular: mira el mercado en general y
devuelve un puntaje con una guía de cuánto arriesgar. NO modifica el
Radar Score de cada ticker (decisión tomada: el Radar Score mide la
acción; el régimen mide el mercado). Se muestra aparte en el dashboard,
se agrega como aviso en las alertas de compra y se guarda en la
bitácora para que la Auditoría pueda comparar aciertos según el régimen.

Cuatro partes (suman 100):
  1. Índices SPY y QQQ ................. 40 pts
  2. Amplitud del universo ............. 25 pts
  3. Breakouts recientes que aguantaron  15 pts
  4. Sentimiento (VIX + Distribution Days) 20 pts
"""
import logging

import pandas as pd

log = logging.getLogger("radar.regimen_score")

INDICES = ("SPY", "QQQ")
PTS_INDICES = 40
PTS_AMPLITUD = 25
PTS_BREAKOUTS = 15
PTS_SENTIMIENTO = 20

BREAKOUT_LOOKBACK = 126      # "rompió su máximo de 6 meses"
BREAKOUT_VENTANA = 20        # breakouts de las últimas 20 ruedas...
BREAKOUT_MADURACION = 3      # ...que tengan al menos 3 ruedas de vida
BREAKOUT_TOLERANCIA = 0.98   # "aguantó" = sigue a no más de 2% bajo el precio de ruptura
BREAKOUT_MINIMO = 8          # con menos breakouts no hay feedback confiable

BANDAS = [
    (80, "Favorable", "Exposición plena: se puede ser activa con breakouts", "pos"),
    (60, "Aceptable", "50-75% de exposición: solo las mejores oportunidades", "pos"),
    (40, "Cauteloso", "25-50%: posiciones chicas y stops cortos", "accent"),
    (0, "Desfavorable", "Cash es posición: mejor no abrir compras nuevas", "neg"),
]


def _lineal(valor, cero, lleno, puntos):
    """0 puntos en 'cero', puntaje completo en 'lleno', lineal en el medio."""
    if valor is None:
        return 0.0
    frac = (valor - cero) / (lleno - cero)
    return max(0.0, min(1.0, frac)) * puntos


def _parte_indices(precios):
    por_indice = PTS_INDICES / len(INDICES)
    pts = 0.0
    detalles = []
    for t in INDICES:
        s = precios.get(t)
        if s is None:
            detalles.append(f"{t}: sin datos")
            continue
        s = s.dropna()
        if len(s) < 200:
            detalles.append(f"{t}: historia corta")
            continue
        precio = float(s.iloc[-1])
        sma50 = s.rolling(50).mean()
        sma200 = float(s.rolling(200).mean().iloc[-1])
        sma50_hoy = float(sma50.iloc[-1])
        sma50_antes = float(sma50.iloc[-11])
        checks = [
            (precio > sma50_hoy, 0.3, "sobre SMA50"),
            (precio > sma200, 0.3, "sobre SMA200"),
            (sma50_hoy > sma50_antes, 0.2, "SMA50 subiendo"),
            (sma50_hoy > sma200, 0.2, "SMA50 sobre SMA200"),
        ]
        cumple = [txt for ok, _, txt in checks if ok]
        pts += sum(peso for ok, peso, _ in checks if ok) * por_indice
        detalles.append(f"{t}: {len(cumple)}/4 ({', '.join(cumple) if cumple else 'nada a favor'})")
    return round(pts, 1), " · ".join(detalles)


def _parte_amplitud(precios, universo):
    sobre50 = sobre200 = total50 = total200 = 0
    for t in universo:
        s = precios.get(t)
        if s is None:
            continue
        s = s.dropna()
        if len(s) >= 50:
            total50 += 1
            sobre50 += s.iloc[-1] > s.iloc[-50:].mean()
        if len(s) >= 200:
            total200 += 1
            sobre200 += s.iloc[-1] > s.iloc[-200:].mean()
    pct50 = sobre50 / total50 * 100 if total50 else None
    pct200 = sobre200 / total200 * 100 if total200 else None
    # 30% de las acciones sobre su media = 0 puntos; 70% o más = puntaje completo
    pts = _lineal(pct50, 30, 70, PTS_AMPLITUD / 2) + _lineal(pct200, 30, 70, PTS_AMPLITUD / 2)
    detalle = (f"{pct50:.0f}% sobre su SMA50 · {pct200:.0f}% sobre su SMA200"
               if pct50 is not None and pct200 is not None else "sin datos")
    return round(pts, 1), detalle, (round(pct50, 1) if pct50 is not None else None), \
        (round(pct200, 1) if pct200 is not None else None)


def _parte_breakouts(precios, universo):
    rupturas = aguantaron = 0
    for t in universo:
        s = precios.get(t)
        if s is None:
            continue
        s = s.dropna()
        n = len(s)
        if n < BREAKOUT_LOOKBACK + BREAKOUT_VENTANA + 1:
            continue
        maximo_previo = s.shift(1).rolling(BREAKOUT_LOOKBACK).max()
        desde = n - BREAKOUT_VENTANA
        hasta = n - BREAKOUT_MADURACION
        for j in range(desde, hasta):
            if s.iloc[j] > maximo_previo.iloc[j]:
                rupturas += 1
                if s.iloc[-1] >= s.iloc[j] * BREAKOUT_TOLERANCIA:
                    aguantaron += 1
                break  # solo la primera ruptura de cada ticker en la ventana
    if rupturas < BREAKOUT_MINIMO:
        # Pocas rupturas ya es un dato: el mercado no está empujando.
        pts = PTS_BREAKOUTS * 0.33
        detalle = f"solo {rupturas} ruptura(s) de máximos de 6 meses en 20 ruedas -- poco impulso"
        return round(pts, 1), detalle, rupturas, None
    pct = aguantaron / rupturas * 100
    pts = _lineal(pct, 30, 70, PTS_BREAKOUTS)
    detalle = f"{aguantaron} de {rupturas} rupturas recientes aguantaron ({pct:.0f}%)"
    return round(pts, 1), detalle, rupturas, round(pct, 1)


def _parte_sentimiento(vix, dist_days):
    mitad = PTS_SENTIMIENTO / 2
    if vix is None:
        pts_vix, txt_vix = mitad / 2, "VIX sin datos"
    else:
        if vix < 15:
            f = 1.0
        elif vix < 20:
            f = 0.7
        elif vix < 25:
            f = 0.4
        elif vix < 30:
            f = 0.2
        else:
            f = 0.0
        pts_vix, txt_vix = f * mitad, f"VIX {vix:.1f}"
    if dist_days is None:
        pts_dd, txt_dd = mitad / 2, "Distribution Days sin datos"
    else:
        if dist_days <= 2:
            f = 1.0
        elif dist_days <= 4:
            f = 0.6
        elif dist_days == 5:
            f = 0.3
        else:
            f = 0.0
        pts_dd, txt_dd = f * mitad, f"{dist_days} Distribution Days"
    return round(pts_vix + pts_dd, 1), f"{txt_vix} · {txt_dd}"


def banda_de(score):
    for piso, nombre, guia, color in BANDAS:
        if score >= piso:
            return nombre, guia, color
    return BANDAS[-1][1:]


def calcular_regimen_score(precios: dict, universo: list, vix, dist_days) -> dict:
    p_ind, d_ind = _parte_indices(precios)
    p_amp, d_amp, pct50, pct200 = _parte_amplitud(precios, universo)
    p_brk, d_brk, n_brk, pct_brk = _parte_breakouts(precios, universo)
    p_sen, d_sen = _parte_sentimiento(vix, dist_days)
    score = int(round(p_ind + p_amp + p_brk + p_sen))
    nombre, guia, color = banda_de(score)
    resultado = {
        "score": score,
        "banda": nombre,
        "guia": guia,
        "color": color,
        "partes": [
            {"nombre": "Índices SPY / QQQ", "pts": p_ind, "max": PTS_INDICES, "detalle": d_ind},
            {"nombre": "Amplitud del universo", "pts": p_amp, "max": PTS_AMPLITUD, "detalle": d_amp},
            {"nombre": "Breakouts que aguantaron", "pts": p_brk, "max": PTS_BREAKOUTS, "detalle": d_brk},
            {"nombre": "Sentimiento", "pts": p_sen, "max": PTS_SENTIMIENTO, "detalle": d_sen},
        ],
        "amplitud_sma50_pct": pct50,
        "amplitud_sma200_pct": pct200,
        "breakouts_n": n_brk,
        "breakouts_aguantaron_pct": pct_brk,
    }
    log.info(f"Régimen de mercado: {score}/100 ({nombre}) -- "
             + " | ".join(f"{p['nombre']} {p['pts']}/{p['max']}" for p in resultado["partes"]))
    return resultado
