"""
Auditoría de HyperTrade -- responde "¿las señales funcionan de verdad?"
con datos reales, y lo deja listo para la solapa Auditoría del dashboard.

Genera data/auditoria.json (se pisa en cada corrida, no es un log) con:

1. RESULTADOS REALES POR SEÑAL: toma cada alerta de la bitácora
   (data/log_alertas.jsonl) y mira cómo terminó a 5, 10 y 20 ruedas:
   retorno, comparación contra SPY en la misma ventana, si "acertó"
   la dirección, y si en el camino hubiera tocado un stop de -8%.

2. TOP 30 SEMANAL: el primer lunes (o primera corrida) de cada semana
   guarda una foto del Top 30 de RS en data/top30_semanal.json, y
   después mide cómo le fue contra SPY y contra el promedio del universo.

3. SIMULACIÓN HACIA ATRÁS (solo orientativa): con el año de precios que
   ya se baja en cada corrida, recalcula cuál HUBIERA sido el Top 30 de
   RS cada lunes y cómo terminó. Va separada y marcada como simulada.

No modifica la bitácora ni ningún otro archivo. Si algo falla, main.py
lo atrapa y la corrida sigue normal.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from statistics import mean

import pandas as pd

log = logging.getLogger("radar.auditoria")

RUTA_LOG = "data/log_alertas.jsonl"
RUTA_TOP30 = "data/top30_semanal.json"
RUTA_SALIDA = "data/auditoria.json"
# Archivo PERMANENTE: cada caso que ya terminó de medirse (tiene sus tres
# horizontes) se graba acá una sola vez y nunca se borra. Así la auditoría
# no depende del año de precios que se baja en cada corrida: un caso de
# hace 3 años sigue contando aunque su precio ya no esté en la descarga.
RUTA_HISTORICO = "data/auditoria_resultados.jsonl"
# Operaciones reales cerradas desde Mi Cartera (las sube el dashboard con
# la misma sincronización de GitHub que la cartera). Es permanente: el
# dashboard solo agrega, nunca borra.
RUTA_OPERACIONES = "data/operaciones_cerradas.json"

HORIZONTES = (5, 10, 20)
STOP_PCT = 8                 # mismo -8% que usa Mi Cartera como techo de pérdida
MUESTRA_MINIMA = 10          # con menos casos no se muestra promedio
MUESTRA_CONFIABLE = 30       # a partir de acá el promedio empieza a significar algo
DIAS_DEDUP = 7               # misma señal en el mismo ticker dentro de 7 días = un solo caso
TOP_N = 30
MAX_DETALLE = 300            # casos individuales que se mandan al dashboard


# ---------------------------------------------------------------- utilidades

def _leer_jsonl(ruta):
    if not os.path.exists(ruta):
        return []
    filas = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                # La bitácora puede traer NaN sin comillas (lo escribe json.dumps
                # de Python) -- json.loads lo acepta por defecto
                filas.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return filas


def _nombre_señal(ev):
    """Nombre legible y estable de la señal, sin emojis."""
    estado = (ev.get("estado") or ev.get("tipo") or "Sin nombre").replace("—", "-")
    limpio = re.sub(r"[^\w\s()áéíóúÁÉÍÓÚñÑ+\-/.,]", "", estado)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio or estado


def _direccion(ev):
    """'alcista' si la señal espera suba, 'bajista' si espera caída."""
    rec = (ev.get("recomendacion") or "").upper()
    estado = (ev.get("estado") or "").lower()
    if rec == "VENTA" or "rompió piso" in estado or "perdió" in estado:
        return "bajista"
    return "alcista"


def _serie_limpia(precios, ticker):
    s = precios.get(ticker)
    if s is None:
        return None
    s = s.dropna()
    if s.empty:
        return None
    # Índice sin zona horaria, para comparar fechas sin sorpresas
    if getattr(s.index, "tz", None) is not None:
        s = s.copy()
        s.index = s.index.tz_localize(None)
    return s


def _ret_pct(a, b):
    return round((b / a - 1) * 100, 2) if a else None


def _sin_nan(obj):
    """NaN/infinito -> None, para que el JSON lo pueda leer el navegador."""
    if isinstance(obj, dict):
        return {k: _sin_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sin_nan(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    if hasattr(obj, "item"):  # tipos de numpy
        return _sin_nan(obj.item())
    return obj


def _prom(valores):
    valores = [v for v in valores if v is not None]
    return round(mean(valores), 2) if valores else None


# ------------------------------------------------ 1. resultados por señal

def _evaluar_evento(ev, serie, serie_spy):
    fecha_ev = datetime.fromisoformat(ev["timestamp"]).date()
    precio_entrada = ev.get("precio")
    if precio_entrada is None or not precio_entrada:
        return None

    posteriores = serie[serie.index.date > fecha_ev]
    direccion = _direccion(ev)
    caso = {
        "ticker": ev["ticker"],
        "fecha": fecha_ev.isoformat(),
        "señal": _nombre_señal(ev),
        "direccion": direccion,
        "recomendacion": ev.get("recomendacion"),
        "precio_entrada": round(float(precio_entrada), 2),
        "radar_score": ev.get("radar_score"),
        "regimen_score": ev.get("regimen_score"),
        "cuidados": ev.get("cuidados"),
        "ruedas_transcurridas": int(len(posteriores)),
    }

    spy_antes = serie_spy[serie_spy.index.date <= fecha_ev] if serie_spy is not None else None
    spy_entrada = float(spy_antes.iloc[-1]) if spy_antes is not None and not spy_antes.empty else None
    spy_post = serie_spy[serie_spy.index.date > fecha_ev] if serie_spy is not None else None

    for h in HORIZONTES:
        if len(posteriores) < h:
            caso[f"r{h}"] = None
            continue
        tramo = posteriores.iloc[:h]
        ret = _ret_pct(precio_entrada, float(tramo.iloc[-1]))
        caso[f"r{h}"] = ret

        spy_ret = None
        if spy_entrada and spy_post is not None and len(spy_post) >= h:
            spy_ret = _ret_pct(spy_entrada, float(spy_post.iloc[h - 1]))
        caso[f"spy{h}"] = spy_ret
        caso[f"vs_spy{h}"] = round(ret - spy_ret, 2) if spy_ret is not None else None

        # ¿Acertó la dirección?
        caso[f"acierto{h}"] = (ret > 0) if direccion == "alcista" else (ret < 0)

        # ¿Hubiera tocado un stop de -8% (en contra) en algún cierre del camino?
        if direccion == "alcista":
            peor = float(tramo.min())
            caso[f"stop{h}"] = peor <= precio_entrada * (1 - STOP_PCT / 100)
        else:
            peor = float(tramo.max())
            caso[f"stop{h}"] = peor >= precio_entrada * (1 + STOP_PCT / 100)
    return caso


def _dedup(eventos):
    """Una misma señal en el mismo ticker se repite en la bitácora día tras
    día mientras sigue activa -- para la auditoría cuenta como UN caso (el
    primero), si no, un ticker que queda 5 días en alerta pesaría 5 veces."""
    eventos = sorted(eventos, key=lambda e: e.get("timestamp", ""))
    ultimo_visto = {}
    resultado = []
    for ev in eventos:
        try:
            fecha = datetime.fromisoformat(ev["timestamp"])
        except (KeyError, ValueError):
            continue
        clave = (ev.get("ticker"), _nombre_señal(ev))
        previo = ultimo_visto.get(clave)
        if previo is None or (fecha - previo).days >= DIAS_DEDUP:
            resultado.append(ev)
            ultimo_visto[clave] = fecha
    return resultado


def _resumir(casos):
    """Agrupa por señal y calcula, para cada horizonte, cuántos casos ya se
    pueden medir, % de aciertos, retorno promedio, vs SPY y % que tocó stop."""
    grupos = {}
    for c in casos:
        grupos.setdefault(c["señal"], []).append(c)

    resumen = []
    for señal, lista in grupos.items():
        fila = {
            "señal": señal,
            "direccion": lista[0]["direccion"],
            "casos_total": len(lista),
            "horizontes": {},
        }
        for h in HORIZONTES:
            medibles = [c for c in lista if c.get(f"r{h}") is not None]
            n = len(medibles)
            datos = {"n": n, "pendientes": len(lista) - n}
            if n > 0:
                aciertos = sum(1 for c in medibles if c[f"acierto{h}"])
                datos["aciertos"] = aciertos
                datos["pct_aciertos"] = round(aciertos / n * 100)
                datos["tocaron_stop"] = sum(1 for c in medibles if c.get(f"stop{h}"))
            if n >= MUESTRA_MINIMA:
                datos["ret_prom"] = _prom([c[f"r{h}"] for c in medibles])
                datos["vs_spy_prom"] = _prom([c.get(f"vs_spy{h}") for c in medibles])
            datos["confiable"] = n >= MUESTRA_CONFIABLE
            fila["horizontes"][str(h)] = datos
        resumen.append(fila)

    resumen.sort(key=lambda f: -f["casos_total"])
    return resumen


def _clave_caso(c):
    return (c.get("ticker"), c.get("fecha"), c.get("señal"))


def auditar_señales(precios):
    # 1. Lo que ya quedó grabado para siempre
    historico = {_clave_caso(c): c for c in _leer_jsonl(RUTA_HISTORICO)}

    # 2. Lo que se puede medir hoy con los precios descargados
    eventos = _dedup(_leer_jsonl(RUTA_LOG))
    serie_spy = _serie_limpia(precios, "SPY")
    nuevos_completos = []
    casos = dict(historico)
    ultimo_h = f"r{max(HORIZONTES)}"
    for ev in eventos:
        serie = _serie_limpia(precios, ev.get("ticker"))
        if serie is None:
            continue
        try:
            caso = _evaluar_evento(ev, serie, serie_spy)
        except Exception as e:
            log.debug(f"Auditoría: no se pudo evaluar {ev.get('ticker')}: {e}")
            continue
        if not caso:
            continue
        clave = _clave_caso(caso)
        if clave in historico:
            continue  # ya está medido y grabado, no se toca
        casos[clave] = caso
        if caso.get(ultimo_h) is not None:
            nuevos_completos.append(caso)

    # 3. Grabar para siempre los que terminaron de medirse hoy
    if nuevos_completos:
        os.makedirs("data", exist_ok=True)
        with open(RUTA_HISTORICO, "a", encoding="utf-8") as f:
            for c in nuevos_completos:
                f.write(json.dumps(_sin_nan(c), ensure_ascii=False, default=str) + "\n")
        log.info(f"Auditoría: {len(nuevos_completos)} caso(s) terminados grabados en {RUTA_HISTORICO}")

    lista = sorted(casos.values(), key=lambda c: c["fecha"], reverse=True)
    return (_resumir(lista), lista[:MAX_DETALLE], len(lista), _por_mes(lista),
            _por_regimen(lista), _por_cuidados(lista))


FRANJAS_REGIMEN = [(80, "80-100 Favorable"), (60, "60-79 Aceptable"), (40, "40-59 Cauteloso"), (0, "0-39 Desfavorable")]


def _por_regimen(casos):
    """¿Las señales ALCISTAS aciertan más cuando el régimen está alto?
    Solo cuenta casos que tienen el régimen grabado (desde que existe)."""
    grupos = {nombre: [] for _, nombre in FRANJAS_REGIMEN}
    for c in casos:
        r = c.get("regimen_score")
        if r is None or c.get("direccion") != "alcista":
            continue
        for piso, nombre in FRANJAS_REGIMEN:
            if r >= piso:
                grupos[nombre].append(c)
                break
    salida = []
    for _, nombre in FRANJAS_REGIMEN:
        lista = grupos[nombre]
        fila = {"franja": nombre, "casos": len(lista)}
        for h in HORIZONTES:
            medibles = [c for c in lista if c.get(f"r{h}") is not None]
            n = len(medibles)
            datos = {"n": n}
            if n:
                datos["pct_aciertos"] = round(sum(1 for c in medibles if c[f"acierto{h}"]) / n * 100)
                datos["ret_prom"] = _prom([c[f"r{h}"] for c in medibles])
                datos["vs_spy_prom"] = _prom([c.get(f"vs_spy{h}") for c in medibles])
            fila[str(h)] = datos
        salida.append(fila)
    return salida


NOMBRES_CUIDADOS = {
    "sma50_bajando": "SMA50 bajando",
    "bajo_sma200": "Debajo de SMA200",
    "techo_avwap_volumen": "Techo AVWAP con volumen",
    "techo_avwap": "Techo AVWAP",
    "extendida": "Extendida sobre SMA50",
    "rsi_alto": "RSI alto",
}


def _por_cuidados(casos):
    """¿Las alertas alcistas CON puntos de cuidado rinden peor que las
    limpias? Solo cuenta casos grabados desde que existen los cuidados."""
    con_dato = [c for c in casos if c.get("direccion") == "alcista" and c.get("cuidados") is not None]
    grupos = [("Sin puntos de cuidado", [c for c in con_dato if not c["cuidados"]]),
              ("Con 1 o más", [c for c in con_dato if c["cuidados"]])]
    for clave, nombre in NOMBRES_CUIDADOS.items():
        grupos.append((f"· {nombre}", [c for c in con_dato if clave in c["cuidados"]]))
    salida = []
    for nombre, lista in grupos:
        fila = {"grupo": nombre, "casos": len(lista)}
        for h in HORIZONTES:
            medibles = [c for c in lista if c.get(f"r{h}") is not None]
            n = len(medibles)
            datos = {"n": n}
            if n:
                datos["pct_aciertos"] = round(sum(1 for c in medibles if c[f"acierto{h}"]) / n * 100)
                datos["ret_prom"] = _prom([c[f"r{h}"] for c in medibles])
                datos["vs_spy_prom"] = _prom([c.get(f"vs_spy{h}") for c in medibles])
            fila[str(h)] = datos
        salida.append(fila)
    return salida


def _por_mes(casos):
    """Evolución mes a mes: ¿la app sirve de forma sostenida, o solo tuvo
    un par de semanas buenas? Agrupa por el mes en que se disparó la señal."""
    meses = {}
    for c in casos:
        meses.setdefault(c["fecha"][:7], []).append(c)
    salida = []
    for mes in sorted(meses, reverse=True):
        lista = meses[mes]
        fila = {"mes": mes, "casos": len(lista)}
        for h in HORIZONTES:
            medibles = [c for c in lista if c.get(f"r{h}") is not None]
            n = len(medibles)
            datos = {"n": n}
            if n:
                datos["pct_aciertos"] = round(sum(1 for c in medibles if c[f"acierto{h}"]) / n * 100)
                # Retorno "a favor de la señal": en las bajistas, que baje es ganar
                a_favor = [c[f"r{h}"] if c["direccion"] == "alcista" else -c[f"r{h}"] for c in medibles]
                datos["ret_a_favor_prom"] = _prom(a_favor)
                vs = [c.get(f"vs_spy{h}") if c["direccion"] == "alcista" else
                      (-c[f"vs_spy{h}"] if c.get(f"vs_spy{h}") is not None else None) for c in medibles]
                datos["vs_spy_prom"] = _prom(vs)
            fila[str(h)] = datos
        salida.append(fila)
    return salida


# ------------------------------------------------- 2. Top 30 semanal real

def _cargar_top30():
    if not os.path.exists(RUTA_TOP30):
        return []
    try:
        with open(RUTA_TOP30, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def guardar_foto_top30(df_rs, ahora):
    """Guarda UNA foto por semana (la primera corrida de la semana en que
    haya datos) del Top 30 de RS, con precios. Devuelve la lista completa."""
    fotos = _cargar_top30()
    if df_rs is None or df_rs.empty:
        return fotos
    año, semana, _ = ahora.isocalendar()
    clave = f"{año}-S{semana:02d}"
    if any(f.get("semana") == clave for f in fotos):
        return fotos

    top = df_rs.sort_values("RS_Score", ascending=False).head(TOP_N)
    fotos.append({
        "semana": clave,
        "fecha": ahora.date().isoformat(),
        "tickers": [
            {"ticker": r["Ticker"], "precio": float(r["Precio"]), "rs": float(r["RS_Score"])}
            for _, r in top.iterrows()
        ],
    })
    os.makedirs("data", exist_ok=True)
    with open(RUTA_TOP30, "w", encoding="utf-8") as f:
        json.dump(fotos, f, ensure_ascii=False, indent=1)
    log.info(f"Auditoría: guardada la foto del Top {TOP_N} de la semana {clave}")
    return fotos


def _ret_desde_fecha(serie, fecha, h, precio_entrada=None):
    """Retorno h ruedas después de 'fecha'. Si no se da precio de entrada,
    usa el cierre de esa fecha (o el último anterior)."""
    if serie is None:
        return None
    if precio_entrada is None:
        antes = serie[serie.index.date <= fecha]
        if antes.empty:
            return None
        precio_entrada = float(antes.iloc[-1])
    post = serie[serie.index.date > fecha]
    if len(post) < h:
        return None
    return _ret_pct(precio_entrada, float(post.iloc[h - 1]))


def evaluar_top30_real(fotos, precios, universo):
    serie_spy = _serie_limpia(precios, "SPY")
    series = {t: _serie_limpia(precios, t) for t in universo}
    salida = []
    hubo_congelados = False
    for foto in sorted(fotos, key=lambda f: f["fecha"], reverse=True):
        # Semana ya medida del todo: se usa el resultado grabado, sin recalcular
        if foto.get("resultado"):
            salida.append(foto["resultado"])
            continue
        fecha = datetime.fromisoformat(foto["fecha"]).date()
        fila = {"semana": foto["semana"], "fecha": foto["fecha"], "n": len(foto["tickers"])}
        for h in HORIZONTES:
            rets = [_ret_desde_fecha(series.get(t["ticker"]), fecha, h, t["precio"]) for t in foto["tickers"]]
            rets = [r for r in rets if r is not None]
            if not rets:
                fila[f"top{h}"] = None
                continue
            fila[f"top{h}"] = _prom(rets)
            fila[f"verdes{h}"] = sum(1 for r in rets if r > 0)
            fila[f"medidos{h}"] = len(rets)
            fila[f"spy{h}"] = _ret_desde_fecha(serie_spy, fecha, h)
            univ = [_ret_desde_fecha(s, fecha, h) for s in series.values()]
            fila[f"univ{h}"] = _prom(univ)
        if fila.get(f"top{max(HORIZONTES)}") is not None:
            foto["resultado"] = _sin_nan(fila)  # se congela para siempre
            hubo_congelados = True
        salida.append(fila)
    if hubo_congelados:
        with open(RUTA_TOP30, "w", encoding="utf-8") as f:
            json.dump(fotos, f, ensure_ascii=False, indent=1)
    return salida


# ------------------------------------------ 3. simulación hacia atrás (RS)

def _rs_raw_en(close, bench, i):
    """Misma fórmula que rs_score.py, pero parada en la rueda i."""
    def rend(s, d):
        return s.iloc[i] / s.iloc[i - d] - 1
    try:
        return ((rend(close, 21) - rend(bench, 21)) * 0.4
                + (rend(close, 63) - rend(bench, 63)) * 0.3
                + (rend(close, 126) - rend(bench, 126)) * 0.3)
    except (IndexError, ZeroDivisionError):
        return None


def simular_top30(precios, universo):
    """Recalcula el Top 30 de RS de cada lunes del último año (lo que dan
    los precios que ya bajamos) y mide cómo terminó. Es ORIENTATIVO: usa
    el universo de hoy (sesgo de supervivencia) y una sola forma de medir."""
    serie_spy = _serie_limpia(precios, "SPY")
    if serie_spy is None:
        return None
    # Todas las series alineadas a las fechas del SPY
    cierres = pd.DataFrame({t: _serie_limpia(precios, t) for t in universo if _serie_limpia(precios, t) is not None})
    cierres = cierres.reindex(serie_spy.index).ffill(limit=3)
    bench = serie_spy

    fechas = list(serie_spy.index)
    semanas = []
    max_h = max(HORIZONTES)
    for i in range(126, len(fechas) - min(HORIZONTES)):
        fecha = fechas[i]
        # Un punto por semana: el primer día hábil de cada semana
        if i > 0 and fechas[i - 1].isocalendar()[1] == fecha.isocalendar()[1]:
            continue
        rs = {}
        for t in cierres.columns:
            col = cierres[t]
            if col.iloc[i - 126:i + 1].isna().any():
                continue
            v = _rs_raw_en(col, bench, i)
            if v is not None and pd.notna(v):
                rs[t] = v
        if len(rs) < TOP_N * 2:
            continue
        ranking = sorted(rs, key=rs.get, reverse=True)
        top = ranking[:TOP_N]

        fila = {"fecha": fecha.date().isoformat()}
        for h in HORIZONTES:
            if i + h >= len(fechas):
                continue
            def ret(t):
                a, b = cierres[t].iloc[i], cierres[t].iloc[i + h]
                return None if pd.isna(a) or pd.isna(b) or a == 0 else (b / a - 1) * 100
            r_top = [x for x in (ret(t) for t in top) if x is not None]
            r_univ = [x for x in (ret(t) for t in ranking) if x is not None]
            if not r_top or not r_univ:
                continue
            fila[f"top{h}"] = mean(r_top)
            fila[f"univ{h}"] = mean(r_univ)
            fila[f"spy{h}"] = (bench.iloc[i + h] / bench.iloc[i] - 1) * 100
        semanas.append(fila)

    if not semanas:
        return None

    resumen = {}
    for h in HORIZONTES:
        validas = [s for s in semanas if f"top{h}" in s]
        if not validas:
            continue
        resumen[str(h)] = {
            "semanas": len(validas),
            "top_prom": _prom([s[f"top{h}"] for s in validas]),
            "univ_prom": _prom([s[f"univ{h}"] for s in validas]),
            "spy_prom": _prom([s[f"spy{h}"] for s in validas]),
            "semanas_top_gana_univ": sum(1 for s in validas if s[f"top{h}"] > s[f"univ{h}"]),
            "semanas_top_gana_spy": sum(1 for s in validas if s[f"top{h}"] > s[f"spy{h}"]),
        }
    return {
        "desde": semanas[0]["fecha"],
        "hasta": semanas[-1]["fecha"],
        "semanas_total": len(semanas),
        "horizontes": resumen,
        "advertencia": ("Simulación hacia atrás con el universo actual: no incluye acciones que "
                        "ya no están (sesgo de supervivencia), ni costos, ni el CCL. Sirve como "
                        "orientación, no como prueba. Lo que vale es la auditoría en vivo."),
    }


# ------------------------------------------- 4. mis operaciones reales

def _spy_en_fecha(serie_spy, fecha_iso):
    if serie_spy is None or not fecha_iso:
        return None
    try:
        fecha = datetime.fromisoformat(fecha_iso).date()
    except ValueError:
        return None
    antes = serie_spy[serie_spy.index.date <= fecha]
    if antes.empty or (fecha - antes.index[-1].date()).days > 7:
        return None  # fuera del año descargado
    return float(antes.iloc[-1])


def evaluar_mis_operaciones(precios):
    """Resultados de las compras y ventas que Victoria anotó en Mi Cartera.
    No dice si una señal funciona, dice si la forma de operar funciona."""
    if not os.path.exists(RUTA_OPERACIONES):
        return None
    try:
        with open(RUTA_OPERACIONES, "r", encoding="utf-8") as f:
            ops = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not ops:
        return None

    serie_spy = _serie_limpia(precios, "SPY")
    filas = []
    for op in ops:
        pc, pv = op.get("precio"), op.get("precioVenta")
        if not pc or not pv:
            continue
        ret = _ret_pct(pc, pv)
        spy_c = op.get("spyCompra") or _spy_en_fecha(serie_spy, op.get("fecha"))
        spy_v = op.get("spyVenta") or _spy_en_fecha(serie_spy, op.get("fechaVenta"))
        spy_ret = _ret_pct(spy_c, spy_v) if spy_c and spy_v else None
        dias = None
        try:
            dias = (datetime.fromisoformat(op["fechaVenta"]) - datetime.fromisoformat(op["fecha"])).days
        except (KeyError, ValueError, TypeError):
            pass
        cantidad = op.get("cantidad")
        try:
            cantidad = float(cantidad) if cantidad not in (None, "") else None
        except ValueError:
            cantidad = None
        # En USD por acción del subyacente; si compró CEDEARs, la cantidad
        # es de CEDEARs y se convierte con el ratio
        ratio = (op.get("origenArs") or {}).get("ratio")
        acciones = (cantidad / ratio) if (cantidad and ratio) else cantidad
        filas.append({
            "ticker": op.get("ticker"),
            "fecha": op.get("fecha"),
            "fechaVenta": op.get("fechaVenta"),
            "dias": dias,
            "precio": pc,
            "precioVenta": pv,
            "ret": ret,
            "spy_ret": spy_ret,
            "vs_spy": round(ret - spy_ret, 2) if spy_ret is not None else None,
            "resultado_usd": round((pv - pc) * acciones, 2) if acciones else None,
            "motivo": op.get("motivoVenta") or "sin motivo",
            "con_alerta": bool(op.get("alertaAlComprar")),
            "alerta": op.get("alertaAlComprar"),
            "radar_compra": op.get("radarScoreCompra"),
        })

    if not filas:
        return None

    def bloque(lista):
        if not lista:
            return {"n": 0}
        gan = [f["ret"] for f in lista if f["ret"] > 0]
        per = [f["ret"] for f in lista if f["ret"] <= 0]
        usd = [f["resultado_usd"] for f in lista if f["resultado_usd"] is not None]
        return {
            "n": len(lista),
            "ganadoras": len(gan),
            "pct_ganadoras": round(len(gan) / len(lista) * 100),
            "ganancia_prom": _prom(gan),
            "perdida_prom": _prom(per),
            # Lo que en promedio deja cada operación, contando ganadoras y perdedoras
            "resultado_prom": _prom([f["ret"] for f in lista]),
            "vs_spy_prom": _prom([f["vs_spy"] for f in lista]),
            "dias_prom": _prom([f["dias"] for f in lista if f["dias"] is not None]),
            "resultado_usd_total": round(sum(usd), 2) if usd else None,
        }

    motivos = {}
    for f in filas:
        motivos.setdefault(f["motivo"], []).append(f)

    filas.sort(key=lambda f: f.get("fechaVenta") or "", reverse=True)
    return {
        "total": bloque(filas),
        "con_alerta": bloque([f for f in filas if f["con_alerta"]]),
        "sin_alerta": bloque([f for f in filas if not f["con_alerta"]]),
        "por_motivo": {m: bloque(l) for m, l in motivos.items()},
        "detalle": filas,
    }


# ----------------------------------------------------------------- general

def correr_auditoria(precios, df_rs, universo, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    resumen, detalle, n_casos, por_mes, por_regimen, por_cuidados = auditar_señales(precios)

    fotos = guardar_foto_top30(df_rs, ahora)
    top30 = evaluar_top30_real(fotos, precios, universo)

    try:
        simulacion = simular_top30(precios, universo)
    except Exception as e:
        log.error(f"Auditoría: la simulación falló (no afecta lo demás): {e}")
        simulacion = None

    try:
        mis_ops = evaluar_mis_operaciones(precios)
    except Exception as e:
        log.error(f"Auditoría: no se pudieron evaluar las operaciones reales: {e}")
        mis_ops = None

    salida = {
        "generado_utc": ahora.isoformat(),
        "mis_operaciones": mis_ops,
        "muestra_minima": MUESTRA_MINIMA,
        "muestra_confiable": MUESTRA_CONFIABLE,
        "stop_pct": STOP_PCT,
        "horizontes": list(HORIZONTES),
        "casos_total": n_casos,
        "resumen_señales": resumen,
        "por_mes": por_mes,
        "por_regimen": por_regimen,
        "por_cuidados": por_cuidados,
        "detalle": detalle,
        "top30_semanal": top30,
        "simulacion_top30": simulacion,
    }
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(_sin_nan(salida), f, ensure_ascii=False, indent=1, default=str)
    log.info(f"Auditoría: {n_casos} caso(s) evaluados, {len(fotos)} foto(s) del Top {TOP_N}, "
             f"simulación {'OK' if simulacion else 'sin datos'} -> {RUTA_SALIDA}")
    return salida
