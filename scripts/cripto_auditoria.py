"""
Auditoría de cripto -- versión recortada de auditoria.py (acciones), sin las
partes que no aplican acá: no hay sectores, ni "régimen de mercado", ni
VCP/cuidados, ni Top 30 semanal (esas son cosas del universo de 268
acciones). Lo que sí tiene sentido con 2-3 monedas: "¿esta señal, en los
casos reales que se dispararon, anticipó algo?" -- retorno a 3/7/14 días.

Genera data/auditoria_cripto.json (se pisa en cada corrida, no es un log).
No modifica la bitácora. Si algo falla, crypto_radar.py lo atrapa y la
corrida sigue normal (no bloquea la generación de cripto.json ni Telegram).
"""
import json
import os
from datetime import datetime, timezone
from statistics import mean

RUTA_LOG = "data/log_alertas_cripto.jsonl"
RUTA_SALIDA = "data/auditoria_cripto.json"
# Igual que en acciones: un archivo PERMANENTE donde cada caso que ya
# terminó de medirse se graba una sola vez y nunca se borra -- así un caso
# de hace meses sigue contando aunque el año de precios que se baja hoy ya
# no llegue tan atrás.
RUTA_HISTORICO = "data/auditoria_cripto_resultados.jsonl"

HORIZONTES = (3, 7, 14)   # días corridos (cripto opera 24/7, no "ruedas")
MUESTRA_MINIMA = 5        # con menos casos no se muestra promedio (universo chico: umbral bajo)
MUESTRA_CONFIABLE = 20
DIAS_DEDUP = 3            # misma señal en la misma moneda dentro de 3 días = un solo caso

# Qué dirección "espera" cada tipo de alerta, para poder medir si acertó.
# None = no direccional (volumen anómalo no predice suba ni baja por sí solo).
DIRECCION_POR_TIPO = {
    "Cruce dorado (SMA50 > SMA200)": "alcista",
    "Cruce de la muerte (SMA50 < SMA200)": "bajista",
    "RSI en sobreventa": "alcista",
    "RSI en sobrecompra": "bajista",
    "Nuevo máximo de 52 semanas": "alcista",
    "Volumen anómalo": None,
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


def _ret_pct(a, b):
    return round((b / a - 1) * 100, 2) if a else None


def _prom(valores):
    valores = [v for v in valores if v is not None]
    return round(mean(valores), 2) if valores else None


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


def _dedup(eventos):
    """Misma señal en la misma moneda repetida día tras día = un solo caso
    (el primero), igual que en acciones -- si no, una racha de varios días
    de RSI sobrecomprado pesaría una vez por día en el promedio."""
    eventos = sorted(eventos, key=lambda e: e.get("timestamp", ""))
    ultimo_visto = {}
    resultado = []
    for ev in eventos:
        try:
            fecha = datetime.fromisoformat(ev["timestamp"])
        except (KeyError, ValueError):
            continue
        clave = (ev.get("ticker"), ev.get("tipo"))
        previo = ultimo_visto.get(clave)
        if previo is None or (fecha - previo).days >= DIAS_DEDUP:
            resultado.append(ev)
            ultimo_visto[clave] = fecha
    return resultado


def _evaluar_evento(ev, serie):
    fecha_ev = datetime.fromisoformat(ev["timestamp"]).date()
    precio_entrada = ev.get("precio")
    if precio_entrada is None or not precio_entrada:
        return None

    posteriores = serie[serie.index.date > fecha_ev]
    direccion = DIRECCION_POR_TIPO.get(ev.get("tipo"))

    caso = {
        "ticker": ev["ticker"],
        "nombre": ev.get("nombre"),
        "fecha": fecha_ev.isoformat(),
        "tipo": ev.get("tipo"),
        "direccion": direccion,
        "precio_entrada": round(float(precio_entrada), 2),
        "score": ev.get("score"),
        "dias_transcurridos": int(len(posteriores)),
    }

    for h in HORIZONTES:
        if len(posteriores) < h:
            caso[f"r{h}"] = None
            continue
        ret = _ret_pct(precio_entrada, float(posteriores.iloc[h - 1]))
        caso[f"r{h}"] = ret
        caso[f"acierto{h}"] = None if direccion is None else (
            (ret > 0) if direccion == "alcista" else (ret < 0)
        )
    return caso


def _clave_caso(c):
    return (c.get("ticker"), c.get("fecha"), c.get("tipo"))


def _resumir(casos):
    grupos = {}
    for c in casos:
        grupos.setdefault(c["tipo"], []).append(c)

    resumen = []
    for tipo, lista in grupos.items():
        fila = {
            "tipo": tipo,
            "direccion": lista[0]["direccion"],
            "casos_total": len(lista),
            "horizontes": {},
        }
        for h in HORIZONTES:
            medibles = [c for c in lista if c.get(f"r{h}") is not None]
            n = len(medibles)
            datos = {"n": n, "pendientes": len(lista) - n}
            if n > 0 and fila["direccion"] is not None:
                aciertos = sum(1 for c in medibles if c[f"acierto{h}"])
                datos["aciertos"] = aciertos
                datos["pct_aciertos"] = round(aciertos / n * 100)
            if n >= MUESTRA_MINIMA:
                datos["ret_prom"] = _prom([c[f"r{h}"] for c in medibles])
            datos["confiable"] = n >= MUESTRA_CONFIABLE
            fila["horizontes"][str(h)] = datos
        resumen.append(fila)

    resumen.sort(key=lambda f: -f["casos_total"])
    return resumen


def correr_auditoria_cripto(precios: dict, ahora=None) -> dict:
    """precios: dict {ticker: pandas.Series de cierres indexada por fecha},
    con los mismos tickers que se acaban de procesar en crypto_radar.py."""
    ahora = ahora or datetime.now(timezone.utc)

    historico = {_clave_caso(c): c for c in _leer_jsonl(RUTA_HISTORICO)}
    eventos = _dedup(_leer_jsonl(RUTA_LOG))

    casos = dict(historico)
    ultimo_h = f"r{max(HORIZONTES)}"
    nuevos_completos = []
    for ev in eventos:
        serie = _serie_limpia(precios, ev.get("ticker"))
        if serie is None:
            continue
        try:
            caso = _evaluar_evento(ev, serie)
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
    resumen = _resumir(todos)

    salida = {
        "generado_utc": ahora.isoformat(),
        "muestra_minima": MUESTRA_MINIMA,
        "muestra_confiable": MUESTRA_CONFIABLE,
        "horizontes": list(HORIZONTES),
        "casos_total": len(todos),
        "resumen_señales": resumen,
        "detalle": sorted(todos, key=lambda c: c.get("fecha", ""), reverse=True)[:200],
    }
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(_sin_nan(salida), f, ensure_ascii=False, indent=1)

    return salida
