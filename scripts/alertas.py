"""
Sistema de alertas técnicas v3.

Cambios sobre v2:
- FIX de un bug real: antes, un ticker que llegaba a "confirmado" (u otro
  estado del flujo cruce/sacudon) se seguía mostrando en "Alertas Activas"
  todos los días indefinidamente, porque la condición de inclusión miraba
  el estado anterior sin límite de tiempo. Ahora cada estado tiene una
  "fecha_evento" (cuándo empezó ESE estado puntual) y solo se muestra en
  el resultado si esa fecha está dentro de VENTANA_ALERTA_HORAS. El
  historial completo se sigue guardando siempre, para no perder datos.
- Nueva señal "Líder apoyando en soporte": RS Score alto (>80) + precio
  descansando cerca de su SMA50 sin haberla roto -- llena el hueco de
  "por qué no me avisa de comprar algo que ya viene ganando".
"""
import pandas as pd
from datetime import datetime, timezone
from config import (VOLUMEN_RELATIVO_MINIMO, RSI_ZONA_SANA, VENTANA_BASE_DIAS,
                     SMA_CORTAS, EMA_LARGA, DIAS_CONFIRMACION, SCORE_TECHO_SIN_CONFIRMAR,
                     ESTADOS, VENTANA_ALERTA_HORAS, UMBRAL_LIDER_RS, UMBRAL_LIDER_DIST_SMA50_PCT,
                     UMBRAL_GAP_ALCISTA_PCT, VENTANA_GAP_MAXIMO_DIAS)
from vcp import detectar_vcp


def rsi(serie, periodo=14):
    delta = serie.diff()
    ganancia = delta.clip(lower=0).rolling(periodo).mean()
    perdida = (-delta.clip(upper=0)).rolling(periodo).mean()
    rs = ganancia / perdida
    return 100 - (100 / (1 + rs))


def rsi_semanal_cruzando(close_diario: pd.Series) -> bool:
    """Resamplea a semanal y chequea si el RSI(14) semanal cruzó su propia
    media móvil de 14 semanas hacia arriba en la última semana cerrada."""
    semanal = close_diario.resample("W").last().dropna()
    if len(semanal) < 30:
        return False
    rsi_sem = rsi(semanal, 14)
    rsi_sem_media = rsi_sem.rolling(14).mean()
    if len(rsi_sem) < 2 or rsi_sem_media.isna().iloc[-2:].any():
        return False
    cruzo = (rsi_sem.iloc[-2] <= rsi_sem_media.iloc[-2]) and (rsi_sem.iloc[-1] > rsi_sem_media.iloc[-1])
    return bool(cruzo)


def _horas_desde(fecha_iso: str, ahora: datetime) -> float:
    """Devuelve cuántas horas pasaron desde fecha_iso hasta ahora. Si la
    fecha viene corrupta/ausente, devuelve infinito (para que NO se muestre
    -- más seguro fallar hacia "ocultar" que hacia "mostrar viejo por error")."""
    if not fecha_iso:
        return float("inf")
    try:
        entonces = datetime.fromisoformat(fecha_iso)
        if entonces.tzinfo is None:
            entonces = entonces.replace(tzinfo=timezone.utc)
        return (ahora - entonces).total_seconds() / 3600
    except Exception:
        return float("inf")


def detectar_alertas(precios: dict, volumenes: dict, tickers_sector: dict, benchmark: str,
                      rs_por_sector: dict, rs_por_ticker: dict, historial: dict, fecha_hoy: str,
                      timestamp_iso: str):
    bench = precios[benchmark].dropna()
    bench_sma50 = bench.rolling(50).mean()
    bench_sobre_sma50 = bool(bench.iloc[-1] > bench_sma50.iloc[-1])
    ahora = datetime.fromisoformat(timestamp_iso)

    alertas = []
    for ticker, sector in tickers_sector.items():
        if ticker not in precios or ticker not in volumenes:
            continue
        close = precios[ticker].dropna()
        vol = volumenes[ticker].dropna()
        if len(close) < 200:
            continue

        sma_cortas = {n: close.rolling(n).mean() for n in SMA_CORTAS}  # SMA10, SMA21, SMA50
        sma50 = sma_cortas[50]
        ema200 = close.ewm(span=EMA_LARGA, adjust=False).mean()
        rsi14 = rsi(close, 14)
        vol_prom20 = vol.rolling(20).mean()
        max_52w = close.iloc[-252:].max() if len(close) >= 252 else close.max()

        precio_hoy, precio_ayer = close.iloc[-1], close.iloc[-2]
        sma50_hoy, sma50_ayer = sma50.iloc[-1], sma50.iloc[-2]
        ema200_hoy = ema200.iloc[-1]
        vol_rel_hoy = vol.iloc[-1] / vol_prom20.iloc[-1] if vol_prom20.iloc[-1] > 0 else 1
        rsi_hoy = rsi14.iloc[-1]

        # --- Señales base ---
        cruzo_sma50_hoy = (precio_ayer <= sma50_ayer) and (precio_hoy > sma50_hoy)
        rompio_piso = (precio_hoy < ema200_hoy) and (precio_ayer >= ema200.iloc[-2])
        volumen_confirma = vol_rel_hoy > VOLUMEN_RELATIVO_MINIMO
        rsi_sano = RSI_ZONA_SANA[0] <= rsi_hoy <= RSI_ZONA_SANA[1]
        vol_reciente = close.iloc[-VENTANA_BASE_DIAS:].pct_change().std()
        vol_historica = close.pct_change().std()
        base_ordenada = vol_reciente < vol_historica * 0.85
        sector_acompana = rs_por_sector.get(sector, 0) > 50 and bench_sobre_sma50

        # --- Señales adicionales ---
        vcp_resultado = detectar_vcp(close, vol)  # pilar "Setup"
        rsi_sem_cruzo = rsi_semanal_cruzando(close)
        nuevo_max_52w = precio_hoy >= max_52w * 0.999  # tolerancia por redondeo

        # --- Stop-loss: independiente del cruce, mira historial previo ---
        estado_previo = historial.get(ticker, {})
        venia_confirmado = estado_previo.get("estado") == "confirmado"
        alerta_stop_loss = venia_confirmado and rompio_piso

        # --- Score (0-7) ---
        score, señales = 0, []
        if cruzo_sma50_hoy:
            score += 1; señales.append("cruce SMA50")
        if volumen_confirma:
            score += 1; señales.append("volumen fuerte")
        if rsi_sano:
            score += 1; señales.append("RSI diario sano")
        if base_ordenada:
            score += 1; señales.append("base ordenada")
        if sector_acompana:
            score += 1; señales.append("sector+mercado ok")
        if vcp_resultado["valido"]:
            score += 1; señales.append(f"VCP válido ({vcp_resultado['contracciones_detectadas']} contracciones)")
        if rsi_sem_cruzo:
            score += 1; señales.append("RSI semanal cruzó alcista")

        # --- Confirmación con demora ---
        dias_verdes = estado_previo.get("dias_verdes_consecutivos", 0)
        if cruzo_sma50_hoy:
            dias_verdes = 1
        elif estado_previo.get("estado") in ("recien_cruzo", "sacudon") and precio_hoy > precio_ayer:
            dias_verdes += 1
        elif estado_previo.get("estado") in ("recien_cruzo", "sacudon") and precio_hoy <= precio_ayer:
            dias_verdes = 0

        confirmado = dias_verdes >= DIAS_CONFIRMACION or nuevo_max_52w

        # --- Determinar estado narrativo del flujo principal (cruce/sacudón/confirmado) ---
        estado_key = None
        if alerta_stop_loss:
            estado_key = "stop_loss"
        elif rompio_piso:
            estado_key = "deterioro"
        elif cruzo_sma50_hoy or estado_previo.get("estado") in ("recien_cruzo", "sacudon", "confirmado"):
            if confirmado and volumen_confirma and nuevo_max_52w:
                estado_key = "ruptura_vol"
            elif confirmado:
                estado_key = "confirmado"
            elif dias_verdes == 0 and not cruzo_sma50_hoy:
                estado_key = "sacudon"
            else:
                estado_key = "recien_cruzo"

        score_mostrado = score
        if estado_key in ("recien_cruzo", "sacudon"):
            score_mostrado = min(score, SCORE_TECHO_SIN_CONFIRMAR)

        # --- fecha_evento: se renueva SOLO si el estado cambió respecto a ayer ---
        estado_anterior_txt = estado_previo.get("estado")
        if estado_key != estado_anterior_txt:
            fecha_evento = timestamp_iso
        else:
            fecha_evento = estado_previo.get("fecha_evento", timestamp_iso)

        # --- Señal "Líder apoyando en soporte" -- independiente del flujo de arriba,
        # solo se evalúa si hoy no hay ya otro evento más urgente para este ticker ---
        rs_ticker = rs_por_ticker.get(ticker)
        lider_soporte_activo = False
        if estado_key is None and rs_ticker is not None and rs_ticker >= UMBRAL_LIDER_RS:
            dist_sma50_pct = (precio_hoy / sma50_hoy - 1) * 100 if sma50_hoy else None
            if dist_sma50_pct is not None and 0 <= dist_sma50_pct <= UMBRAL_LIDER_DIST_SMA50_PCT:
                lider_soporte_activo = True

        lider_previo = estado_previo.get("lider_soporte_activo", False)
        if lider_soporte_activo and not lider_previo:
            fecha_evento_lider = timestamp_iso  # recién arrancó hoy
        else:
            fecha_evento_lider = estado_previo.get("fecha_evento_lider", timestamp_iso)

        # --- Señal "Gap alcista + macrotendencia" -- adaptada de un dossier de bot de
        # trading (ver notas del prompt): el original usa apertura y máximo intradiario
        # de ayer, que no tenemos -- se adapta con lo que sí hay: variación de cierre a
        # cierre, macrotendencia confirmada (ayer por encima de su SMA200), y que hoy
        # sea el cierre más alto de los últimos N días (proxy de "ruptura"). Igual que
        # "líder en soporte", solo se evalúa si hoy no hay ya otro evento más urgente.
        gap_alcista_activo = False
        if estado_key is None and not lider_soporte_activo and len(close) >= 200:
            sma200_local = close.rolling(200).mean()
            variacion_dia_pct = (precio_hoy / precio_ayer - 1) * 100 if precio_ayer else 0
            macrotendencia_ok = precio_ayer > sma200_local.iloc[-2] if pd.notna(sma200_local.iloc[-2]) else False
            ventana_reciente = close.iloc[-VENTANA_GAP_MAXIMO_DIAS:]
            es_maximo_reciente = precio_hoy >= ventana_reciente.max() * 0.999  # tolerancia por redondeo
            if variacion_dia_pct >= UMBRAL_GAP_ALCISTA_PCT and macrotendencia_ok and es_maximo_reciente:
                gap_alcista_activo = True

        gap_previo = estado_previo.get("gap_alcista_activo", False)
        if gap_alcista_activo and not gap_previo:
            fecha_evento_gap = timestamp_iso
        else:
            fecha_evento_gap = estado_previo.get("fecha_evento_gap", timestamp_iso)

        # --- Actualizar historial (SIEMPRE, tenga o no vigencia de display) ---
        historial[ticker] = {
            "ultima_fecha": fecha_hoy,
            "estado": estado_key,
            "fecha_evento": fecha_evento,
            "dias_verdes_consecutivos": dias_verdes,
            "precio": round(float(precio_hoy), 2),
            "lider_soporte_activo": lider_soporte_activo,
            "fecha_evento_lider": fecha_evento_lider,
            "gap_alcista_activo": gap_alcista_activo,
            "fecha_evento_gap": fecha_evento_gap,
        }

        # --- Armar la(s) fila(s) de salida, solo si están dentro de la ventana de vigencia ---
        if estado_key and _horas_desde(fecha_evento, ahora) <= VENTANA_ALERTA_HORAS:
            alertas.append({
                "Ticker": ticker, "Sector": sector,
                "Tipo": "tecnico",
                "Estado": ESTADOS.get(estado_key, estado_key),
                "Score": f"{score_mostrado}/7",
                "Score_num": score_mostrado,
                "Señales": señales,
                "VCP": vcp_resultado,
                "RSI": round(rsi_hoy, 1) if pd.notna(rsi_hoy) else None,
                "Vol_rel": round(vol_rel_hoy, 2),
                "SMA21": round(sma_cortas[21].iloc[-1], 2) if not pd.isna(sma_cortas[21].iloc[-1]) else None,
                "Precio": round(float(precio_hoy), 2),
                "fecha_evento": fecha_evento,
            })

        if lider_soporte_activo and _horas_desde(fecha_evento_lider, ahora) <= VENTANA_ALERTA_HORAS:
            dist_sma50_pct = round((precio_hoy / sma50_hoy - 1) * 100, 2)
            # Stop-loss sugerido: el soporte que está testeando es justamente
            # la SMA50 -- si la pierde, la tesis de "líder apoyándose en
            # soporte" se invalida. Mismo colchón del 1% que usa "Gap
            # alcista", para mantener un único criterio en toda la app.
            stop_sugerido_aprox = round(sma50_hoy * 0.99, 2)
            alertas.append({
                "Ticker": ticker, "Sector": sector,
                "Tipo": "lider_soporte",
                "Estado": ESTADOS.get("lider_soporte", "📈 Líder apoyando en soporte"),
                "Score": f"RS {rs_ticker:.0f}",
                "Score_num": None,
                "Señales": [f"RS {rs_ticker:.0f}", f"a {dist_sma50_pct}% de su SMA50",
                            f"stop sugerido (aprox.): ${stop_sugerido_aprox}"],
                "Stop_sugerido": stop_sugerido_aprox,
                "RSI": round(rsi_hoy, 1) if pd.notna(rsi_hoy) else None,
                "Vol_rel": round(vol_rel_hoy, 2),
                "Precio": round(float(precio_hoy), 2),
                "fecha_evento": fecha_evento_lider,
            })

        if gap_alcista_activo and _horas_desde(fecha_evento_gap, ahora) <= VENTANA_ALERTA_HORAS:
            stop_sugerido_aprox = round(precio_hoy * 0.99, 2)
            alertas.append({
                "Ticker": ticker, "Sector": sector,
                "Tipo": "gap_alcista",
                "Estado": ESTADOS.get("gap_alcista", "🚀 Gap alcista con macrotendencia"),
                "Score": f"+{round(variacion_dia_pct, 1)}%",
                "Score_num": None,
                "Señales": [f"variación del día: +{round(variacion_dia_pct, 1)}%",
                            f"stop sugerido (aprox.): ${stop_sugerido_aprox}"],
                "Stop_sugerido": stop_sugerido_aprox,
                "Var_dia_%": round(variacion_dia_pct, 1),
                "RSI": round(rsi_hoy, 1) if pd.notna(rsi_hoy) else None,
                "Vol_rel": round(vol_rel_hoy, 2),
                "Precio": round(float(precio_hoy), 2),
                "fecha_evento": fecha_evento_gap,
            })

    return pd.DataFrame(alertas), historial
