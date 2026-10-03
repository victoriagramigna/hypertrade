"""
Auditoría de Golden Cross / Death Cross -- misma pregunta que
auditoria_rotacion.py pero para la señal de golden_cross.py: cuando un
ticker tiene un Golden Cross CONFIRMADO, ¿de verdad le fue mejor que al
SPY en las semanas siguientes? Y lo simétrico para Death Cross (¿le fue
peor?). Si no, la señal no está anticipando nada real, por más que
"suene" a clásico del análisis técnico.

Mide el ticker individual (no una canasta de sector, como en la rotación
sectorial) contra el SPY, a 10 y 20 ruedas desde el cruce CONFIRMADO.

Mismo patrón recortado que auditoria_rotacion.py: histórico permanente
(un caso medido no se vuelve a perder), muestra mínima antes de mostrar
promedios, no modifica la bitácora de golden_cross.py. Si falla, no
bloquea el resto de la corrida.
"""
import json
import logging
import os
from datetime import datetime, timezone
from statistics import mean

log = logging.getLogger("radar.auditoria_golden_cross")

RUTA_LOG = "data/log_golden_cross.jsonl"
RUTA_SALIDA = "data/auditoria_golden_cross.json"
RUTA_HISTORICO = "data/auditoria_golden_cross_resultados.jsonl"

HORIZONTES = (10, 20)   # ruedas -- mismo horizonte que auditoria_rotacion.py
MUESTRA_MINIMA = 5
MUESTRA_CONFIABLE = 15

DIRECCION_POR_TIPO = {
    "Golden Cross": "alcista",
    "Death Cross": "bajista",
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
    return (c.get("ticker"), c.get("fecha"), c.get("tipo"))


def _evaluar_evento(ev, precios, spy_serie):
    fecha_ev = datetime.fromisoformat(ev["timestamp"]).date()
    ticker = ev["ticker"]
    tipo = ev["tipo"]
    direccion = DIRECCION_POR_TIPO.get(tipo)

    serie = _serie_limpia(precios, ticker)
    if serie is None or spy_serie is None:
        return None

    caso = {
        "ticker": ticker, "sector": ev.get("sector"), "fecha": fecha_ev.isoformat(),
        "tipo": tipo, "direccion": direccion,
        "sma50": ev.get("sma50"), "sma200": ev.get("sma200"),
    }

    posteriores = serie[serie.index.date > fecha_ev]
    anteriores = serie[serie.index.date <= fecha_ev]
    if anteriores.empty:
        return None
    precio_entrada = float(anteriores.iloc[-1])
    if not precio_entrada:
        return None

    spy_post = spy_serie[spy_serie.index.date > fecha_ev]
    spy_ant = spy_serie[spy_serie.index.date <= fecha_ev]

    for h in HORIZONTES:
        if len(posteriores) < h or len(spy_post) < h or spy_ant.empty or not float(spy_ant.iloc[-1]):
            caso[f"r{h}"] = None
            continue
        ret_ticker = (float(posteriores.iloc[h - 1]) / precio_entrada - 1) * 100
        ret_spy = (float(spy_post.iloc[h - 1]) / float(spy_ant.iloc[-1]) - 1) * 100
        caso[f"r{h}"] = round(ret_ticker, 2)
        caso[f"vs_spy{h}"] = round(ret_ticker - ret_spy, 2)
        caso[f"acierto{h}"] = None if direccion is None else (
            (ret_ticker > ret_spy) if direccion == "alcista" else (ret_ticker < ret_spy)
        )

    return caso


def _resumir(casos):
    grupos = {}
    for c in casos:
        grupos.setdefault(c["tipo"], []).append(c)

    resumen = []
    for tipo, lista in grupos.items():
        fila = {
            "tipo": tipo, "direccion": DIRECCION_POR_TIPO.get(tipo),
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

    orden = {"Golden Cross": 0, "Death Cross": 1}
    resumen.sort(key=lambda f: orden.get(f["tipo"], 9))
    return resumen


def correr_auditoria_golden_cross(precios: dict, benchmark: str, ahora=None) -> dict:
    ahora = ahora or datetime.now(timezone.utc)

    historico = {_clave_caso(c): c for c in _leer_jsonl(RUTA_HISTORICO)}
    eventos = _leer_jsonl(RUTA_LOG)

    spy_serie = _serie_limpia(precios, benchmark)

    casos = dict(historico)
    ultimo_h = f"r{max(HORIZONTES)}"
    nuevos_completos = []
    for ev in eventos:
        try:
            caso = _evaluar_evento(ev, precios, spy_serie)
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
        "resumen_tipos": _resumir(todos),
        "detalle": sorted(todos, key=lambda c: c.get("fecha", ""), reverse=True)[:200],
    }
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(_sin_nan(salida), f, ensure_ascii=False, indent=1)

    return salida
