"""
Auditoría de Rotación Sectorial -- responde la pregunta de Victoria: ¿el
cuadrante en el que está un sector predice algo, o es solo un gráfico
lindo de datos que ya teníamos?

Toma cada transición de cuadrante logueada por rotacion_sectorial.py
(data/log_rotacion_sectorial.jsonl) y mide cómo le fue a la CANASTA de
tickers de ese sector (promedio simple de sus retornos) contra el SPY, a
10 y 20 ruedas desde la transición. "Líder"/"Mejorando" esperan que el
sector le gane al mercado después; "Debilitándose"/"Rezagado" esperan que
le pierda -- si no es así, el cuadrante no está anticipando nada real.

Versión recortada del mismo patrón que auditoria.py/cripto_auditoria.py:
histórico permanente (un caso medido no se vuelve a perder), muestra
mínima antes de mostrar promedios, no modifica la bitácora. Si falla, no
bloquea el resto de la corrida.
"""
import json
import logging
import os
from datetime import datetime, timezone
from statistics import mean

log = logging.getLogger("radar.auditoria_rotacion")

RUTA_LOG = "data/log_rotacion_sectorial.jsonl"
RUTA_SALIDA = "data/auditoria_rotacion.json"
RUTA_HISTORICO = "data/auditoria_rotacion_resultados.jsonl"

HORIZONTES = (10, 20)   # ruedas -- mismo espíritu que acciones (5/10/20), sin el más corto porque un cambio de fase sectorial es más lento que una señal individual
MUESTRA_MINIMA = 5       # universo chico (una decena de sectores) -- umbral bajo, como en cripto
MUESTRA_CONFIABLE = 15

# Qué dirección "espera" cada cuadrante, para poder medir si acertó.
DIRECCION_POR_CUADRANTE = {
    "Líder": "alcista",
    "Mejorando": "alcista",
    "Debilitándose": "bajista",
    "Rezagado": "bajista",
}


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
                filas.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return filas


def _sin_nan(obj):
    if isinstance(obj, dict):
        return {k: _sin_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sin_nan(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    if hasattr(obj, "item"):
        return _sin_nan(obj.item())
    return obj


def _serie_limpia(precios, ticker):
    s = precios.get(ticker)
    if s is None:
        return None
    s = s.dropna()
    if s.empty:
        return None
    if getattr(s.index, "tz", None) is not None:
        s = s.copy()
        s.index = s.index.tz_localize(None)
    return s


def _clave_caso(c):
    return (c.get("sector"), c.get("fecha"), c.get("cuadrante_nuevo"))


def _evaluar_evento(ev, precios, tickers_del_sector, spy_serie):
    fecha_ev = datetime.fromisoformat(ev["timestamp"]).date()
    sector = ev["sector"]
    cuadrante = ev["cuadrante_nuevo"]
    direccion = DIRECCION_POR_CUADRANTE.get(cuadrante)

    series_sector = [s for s in (_serie_limpia(precios, t) for t in tickers_del_sector) if s is not None]
    if not series_sector or spy_serie is None:
        return None

    caso = {
        "sector": sector, "fecha": fecha_ev.isoformat(), "cuadrante_nuevo": cuadrante,
        "cuadrante_anterior": ev.get("cuadrante_anterior"), "direccion": direccion,
        "rs_sector": ev.get("rs_sector"), "delta_7d": ev.get("delta_7d"),
        "n_tickers_medidos": len(series_sector),
    }

    for h in HORIZONTES:
        retornos_sector = []
        for serie in series_sector:
            posteriores = serie[serie.index.date > fecha_ev]
            anteriores = serie[serie.index.date <= fecha_ev]
            if len(posteriores) < h or anteriores.empty:
                continue
            precio_entrada = float(anteriores.iloc[-1])
            if not precio_entrada:
                continue
            retornos_sector.append((float(posteriores.iloc[h - 1]) / precio_entrada - 1) * 100)

        spy_post = spy_serie[spy_serie.index.date > fecha_ev]
        spy_ant = spy_serie[spy_serie.index.date <= fecha_ev]
        ret_spy = None
        if len(spy_post) >= h and not spy_ant.empty and float(spy_ant.iloc[-1]):
            ret_spy = (float(spy_post.iloc[h - 1]) / float(spy_ant.iloc[-1]) - 1) * 100

        if not retornos_sector or ret_spy is None:
            caso[f"r{h}"] = None
            continue

        ret_sector = round(mean(retornos_sector), 2)
        caso[f"r{h}"] = ret_sector
        caso[f"vs_spy{h}"] = round(ret_sector - ret_spy, 2)
        caso[f"acierto{h}"] = None if direccion is None else (
            (ret_sector > ret_spy) if direccion == "alcista" else (ret_sector < ret_spy)
        )

    return caso


def _resumir(casos):
    grupos = {}
    for c in casos:
        grupos.setdefault(c["cuadrante_nuevo"], []).append(c)

    resumen = []
    for cuadrante, lista in grupos.items():
        fila = {
            "cuadrante": cuadrante, "direccion": DIRECCION_POR_CUADRANTE.get(cuadrante),
            "casos_total": len(lista), "horizontes": {},
        }
        for h in HORIZONTES:
            medibles = [c for c in lista if c.get(f"r{h}") is not None]
            n = len(medibles)
            datos = {"n": n, "pendientes": len(lista) - n}
            if n > 0:
                aciertos = sum(1 for c in medibles if c.get(f"acierto{h}"))
                datos["aciertos"] = aciertos
                datos["pct_aciertos"] = round(aciertos / n * 100)
            if n >= MUESTRA_MINIMA:
                datos["vs_spy_prom"] = round(mean(c[f"vs_spy{h}"] for c in medibles), 2)
            datos["confiable"] = n >= MUESTRA_CONFIABLE
            fila["horizontes"][str(h)] = datos
        resumen.append(fila)

    orden = {"Líder": 0, "Mejorando": 1, "Debilitándose": 2, "Rezagado": 3}
    resumen.sort(key=lambda f: orden.get(f["cuadrante"], 9))
    return resumen


def correr_auditoria_rotacion(precios: dict, tickers_sector: dict, benchmark: str, ahora=None) -> dict:
    ahora = ahora or datetime.now(timezone.utc)

    historico = {_clave_caso(c): c for c in _leer_jsonl(RUTA_HISTORICO)}
    eventos = _leer_jsonl(RUTA_LOG)  # ya vienen deduplicados por construcción (un evento = un cambio real de cuadrante)

    spy_serie = _serie_limpia(precios, benchmark)
    sectores_a_tickers = {}
    for ticker, sector in tickers_sector.items():
        sectores_a_tickers.setdefault(sector, []).append(ticker)

    casos = dict(historico)
    ultimo_h = f"r{max(HORIZONTES)}"
    nuevos_completos = []
    for ev in eventos:
        tickers_del_sector = sectores_a_tickers.get(ev.get("sector"), [])
        try:
            caso = _evaluar_evento(ev, precios, tickers_del_sector, spy_serie)
        except Exception:
            continue
        if caso is None:
            continue
        clave = _clave_caso(caso)
        casos[clave] = caso
        if clave not in historico and caso.get(ultimo_h) is not None:
            nuevos_completos.append(caso)

    if nuevos_completos:
        os.makedirs("data", exist_ok=True)
        with open(RUTA_HISTORICO, "a", encoding="utf-8") as f:
            for c in nuevos_completos:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    todos = list(casos.values())
    salida = {
        "generado_utc": ahora.isoformat(),
        "muestra_minima": MUESTRA_MINIMA,
        "muestra_confiable": MUESTRA_CONFIABLE,
        "horizontes": list(HORIZONTES),
        "casos_total": len(todos),
        "resumen_cuadrantes": _resumir(todos),
        "detalle": sorted(todos, key=lambda c: c.get("fecha", ""), reverse=True)[:200],
    }
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(_sin_nan(salida), f, ensure_ascii=False, indent=1)

    return salida
