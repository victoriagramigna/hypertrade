"""
Zonas de oferta/demanda (Order Blocks) y Fair Value Gaps (FVG) -- a pedido
de Victoria (6/10): replica en Python la lógica del indicador "All-in-One
Pro v3" que ella usa en TradingView, para que el radar calcule solo, para
todo el universo, DÓNDE están los pisos y techos donde un retroceso podría
frenar (en vez de mirarlos a mano ticker por ticker).

IMPORTANTE -- qué es y qué NO es:
  * Es un módulo ADITIVO, igual que bollinger_squeeze.py: no toca el Radar
    Score, ni las alertas, ni la Auditoría de siempre. Tiene su propio
    estado (data/zonas_estado.json) y su propia bitácora de solo agregado
    (data/log_zonas.jsonl).
  * Las zonas son DATOS, no señales de compra ni de venta. La "zona de
    interés" es solo un aviso de que se juntaron varias condiciones (ver
    abajo); la bitácora guarda la foto para poder medir MÁS ADELANTE, con
    resultados reales, si sirve o no.
  * No usa datos nuevos: trabaja sobre el OHLC diario (~1 año) que
    datos.py ya baja para cada ticker.

Lógica (copiada del Pine Script; parámetros iguales):
  FVG de 3 velas. Alcista: mínimo de la vela actual > máximo de la vela de
  hace 2, y la vela del medio cierra por encima de ese máximo; el hueco
  (techo = mínimo actual, piso = máximo de hace 2) debe medir >= 0,25 ATR.
  Bajista: espejo. Máximo 3 activos por lado.
  Order Block: pivote de OB_LEFT=10 velas a la izquierda y OB_RIGHT=5 a la
  derecha, seguido de un desplazamiento >= 1,5 ATR en sentido contrario
  dentro de esas 5 velas. Oferta (pivote alto): techo = máximo de la vela,
  piso = menor entre apertura y cierre. Demanda (pivote bajo): piso =
  mínimo, techo = mayor entre apertura y cierre. Tamaño >= 0,1 ATR. Máx. 3
  por lado.
  Invalidación ("mitigación"): un CIERRE por debajo del piso de una zona
  alcista/de demanda, o por encima del techo de una bajista/de oferta,
  la elimina. Por eso toda zona activa es una zona que ningún cierre rompió.
  ATR = ATR(14) con suavizado RMA (igual que ta.atr de Pine).

Diferencias conocidas respecto a TradingView (por eso hay que validar):
  * Yahoo y TradingView pueden diferir en algún dato; una vela distinta
    puede mover una zona.
  * El ATR arranca con ~1 año de historia en vez de la historia completa.
  * Pine define pivotes con su propio criterio de empates; acá, un pivote
    alto debe ser >= todos los de la izquierda y > todos los de la derecha
    (y el espejo para los bajos).

"Zona de interés" (aviso informativo): el precio de hoy está TOCANDO una
zona de demanda o FVG alcista activo (mínimo del día <= techo y cierre >=
piso) Y además: precio sobre SMA50 y SMA200, RS_Score >= RS_MIN, volumen
relativo < VOL_REL_MAX (los vendedores no empujan) y RSI < RSI_MAX (no
sobrecomprado). Se registra UNA vez cuando se cumple (no cada corrida).
"""
import json
import logging
import os

import numpy as np

log = logging.getLogger("radar.zonas_smc")

RUTA_ESTADO = "data/zonas_estado.json"
RUTA_LOG = "data/log_zonas.jsonl"

# --- Parámetros del indicador (iguales a los del Pine Script) ---
ATR_LEN = 14
FVG_MIN_ATR = 0.25
FVG_MAX = 3
OB_LEFT = 10
OB_RIGHT = 5
OB_DISP_ATR = 1.5
OB_MIN_ATR = 0.1
OB_MAX = 3

# --- Condiciones de la "zona de interés" (informativas) ---
RS_MIN = 70
VOL_REL_MAX = 1.0
RSI_MAX = 70


def _atr_rma(h, l, c, n):
    """ATR con suavizado RMA (como ta.atr de Pine). NaN hasta tener n velas."""
    total = len(c)
    atr = np.full(total, np.nan)
    if total < n:
        return atr
    tr = np.empty(total)
    tr[0] = h[0] - l[0]
    for i in range(1, total):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr[n - 1] = tr[:n].mean()
    for i in range(n, total):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def calcular_zonas(ohlc):
    """
    ohlc: DataFrame con Open/High/Low/Close (índice = fechas, ordenado).
    Devuelve una lista de zonas ACTIVAS al último cierre:
      {"tipo": "FVG alcista"|"FVG bajista"|"OB demanda"|"OB oferta",
       "techo": float, "piso": float, "desde": "YYYY-MM-DD"}
    """
    o = ohlc["Open"].to_numpy(dtype=float)
    h = ohlc["High"].to_numpy(dtype=float)
    l = ohlc["Low"].to_numpy(dtype=float)
    c = ohlc["Close"].to_numpy(dtype=float)
    fechas = [str(ix)[:10] for ix in ohlc.index]
    total = len(c)
    atr = _atr_rma(h, l, c, ATR_LEN)

    fvg_alc, fvg_baj, ob_dem, ob_ofe = [], [], [], []   # cada zona: [techo, piso, idx_desde]

    for i in range(total):
        # 1) invalidación por cierre (se procesa ANTES de crear zonas nuevas,
        #    igual que en el Pine)
        fvg_alc[:] = [z for z in fvg_alc if not c[i] < z[1]]
        ob_dem[:] = [z for z in ob_dem if not c[i] < z[1]]
        fvg_baj[:] = [z for z in fvg_baj if not c[i] > z[0]]
        ob_ofe[:] = [z for z in ob_ofe if not c[i] > z[0]]

        a = atr[i]
        if np.isnan(a):
            continue

        # 2) FVG nuevos
        if i >= 2:
            if l[i] > h[i - 2] and c[i - 1] > h[i - 2] and (l[i] - h[i - 2]) >= FVG_MIN_ATR * a:
                fvg_alc.append([l[i], h[i - 2], i - 2])
                if len(fvg_alc) > FVG_MAX:
                    fvg_alc.pop(0)
            if h[i] < l[i - 2] and c[i - 1] < l[i - 2] and (l[i - 2] - h[i]) >= FVG_MIN_ATR * a:
                fvg_baj.append([l[i - 2], h[i], i - 2])
                if len(fvg_baj) > FVG_MAX:
                    fvg_baj.pop(0)

        # 3) Order Blocks nuevos (el pivote se confirma OB_RIGHT velas después)
        p = i - OB_RIGHT
        if p >= OB_LEFT:
            izq_h = h[p - OB_LEFT:p]
            der_h = h[p + 1:i + 1]
            izq_l = l[p - OB_LEFT:p]
            der_l = l[p + 1:i + 1]
            ventana_l = l[i - OB_RIGHT + 1:i + 1]
            ventana_h = h[i - OB_RIGHT + 1:i + 1]

            if h[p] >= izq_h.max() and h[p] > der_h.max():          # pivote alto -> oferta
                top, bot = h[p], min(o[p], c[p])
                if (top - bot) >= OB_MIN_ATR * a and (h[p] - ventana_l.min()) >= OB_DISP_ATR * a:
                    ob_ofe.append([top, bot, p])
                    if len(ob_ofe) > OB_MAX:
                        ob_ofe.pop(0)
            if l[p] <= izq_l.min() and l[p] < der_l.min():          # pivote bajo -> demanda
                top, bot = max(o[p], c[p]), l[p]
                if (top - bot) >= OB_MIN_ATR * a and (ventana_h.max() - l[p]) >= OB_DISP_ATR * a:
                    ob_dem.append([top, bot, p])
                    if len(ob_dem) > OB_MAX:
                        ob_dem.pop(0)

    zonas = []
    for tipo, lista in (("FVG alcista", fvg_alc), ("FVG bajista", fvg_baj),
                        ("OB demanda", ob_dem), ("OB oferta", ob_ofe)):
        for techo, piso, idx in lista:
            zonas.append({"tipo": tipo, "techo": round(float(techo), 4),
                          "piso": round(float(piso), 4), "desde": fechas[idx]})
    return zonas


def _es_demanda(z):
    return z["tipo"] in ("FVG alcista", "OB demanda")


def _es_oferta(z):
    return z["tipo"] in ("FVG bajista", "OB oferta")


def resumen_ticker(zonas, ohlc):
    """Zona de demanda/oferta más cercana y si el precio de hoy la está tocando."""
    precio = float(ohlc["Close"].iloc[-1])
    minimo = float(ohlc["Low"].iloc[-1])
    maximo = float(ohlc["High"].iloc[-1])

    dem = [z for z in zonas if _es_demanda(z) and z["piso"] <= precio]
    ofe = [z for z in zonas if _es_oferta(z) and z["techo"] >= precio]
    dem_cerca = max(dem, key=lambda z: z["techo"]) if dem else None
    ofe_cerca = min(ofe, key=lambda z: z["piso"]) if ofe else None

    def _dist(z, hacia_abajo):
        if z is None:
            return None
        if z["piso"] <= precio <= z["techo"]:
            return 0.0
        borde = z["techo"] if hacia_abajo else z["piso"]
        return round(abs(precio - borde) / precio * 100, 2)

    toca_dem = any(_es_demanda(z) and minimo <= z["techo"] and precio >= z["piso"] for z in zonas)
    toca_ofe = any(_es_oferta(z) and maximo >= z["piso"] and precio <= z["techo"] for z in zonas)
    return {
        "zona_demanda_cercana": dem_cerca,
        "dist_demanda_pct": _dist(dem_cerca, True),
        "zona_oferta_cercana": ofe_cerca,
        "dist_oferta_pct": _dist(ofe_cerca, False),
        "toca_demanda": bool(toca_dem),
        "toca_oferta": bool(toca_ofe),
    }


def _cargar_estado():
    if not os.path.exists(RUTA_ESTADO):
        return {}
    try:
        with open(RUTA_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"No se pudo leer {RUTA_ESTADO} ({e}) -- se arranca vacío")
        return {}


def actualizar_zonas(df_rs, precios_ohlc, ahora):
    """
    df_rs: necesita Ticker, Precio, SMA50, SMA200, RS_Score, Vol_rel, RSI.
    precios_ohlc: dict {ticker: DataFrame OHLCV} de datos.py.
    NO escribe nada en disco (ver guardar_zonas): devuelve
      {"puntos": [...], "eventos": [...], "estado": {...}}.
    """
    vacio = {"puntos": [], "eventos": [], "estado": {}}
    if df_rs is None or df_rs.empty:
        return vacio

    estado_previo = _cargar_estado()
    estado_nuevo = {}
    puntos, eventos = [], []
    hoy_iso = ahora.isoformat()

    for _, fila in df_rs.iterrows():
        ticker = fila.get("Ticker")
        ohlc = precios_ohlc.get(ticker)
        if ticker is None or ohlc is None or len(ohlc) < ATR_LEN + OB_LEFT + OB_RIGHT + 5:
            continue
        try:
            zonas = calcular_zonas(ohlc)
            res = resumen_ticker(zonas, ohlc)
        except Exception as e:
            log.warning(f"Zonas: falló el cálculo de {ticker} ({e}) -- se omite")
            continue

        precio, sma50, sma200 = fila.get("Precio"), fila.get("SMA50"), fila.get("SMA200")
        rs, vol_rel, rsi = fila.get("RS_Score"), fila.get("Vol_rel"), fila.get("RSI")

        def _ok(x):
            return x is not None and x == x   # no None ni NaN

        cond = {
            "toca_demanda": res["toca_demanda"],
            "sobre_sma50_y_sma200": bool(_ok(precio) and _ok(sma50) and _ok(sma200) and precio > sma50 and precio > sma200),
            "rs_alto": bool(_ok(rs) and rs >= RS_MIN),
            "volumen_bajo": bool(_ok(vol_rel) and vol_rel < VOL_REL_MAX),
            "rsi_no_sobrecomprado": bool(_ok(rsi) and rsi < RSI_MAX),
        }
        interes = all(cond.values())
        estaba = bool(estado_previo.get(ticker, {}).get("en_interes"))

        if interes and not estaba:
            eventos.append({
                "timestamp": hoy_iso, "ticker": ticker, "sector": fila.get("Sector"),
                "evento": "zona_de_interes", "precio": precio,
                "zona": res["zona_demanda_cercana"], "rs_score": rs, "vol_rel": vol_rel,
                "rsi": rsi, "sma50": sma50, "sma200": sma200,
                "zona_oferta_arriba": res["zona_oferta_cercana"],
            })
        estado_nuevo[ticker] = {"en_interes": interes, "fecha_actualizado": ahora.date().isoformat()}

        puntos.append({
            "Ticker": ticker, "Sector": fila.get("Sector"),
            "Zona_Demanda": res["zona_demanda_cercana"], "Dist_Demanda_%": res["dist_demanda_pct"],
            "Zona_Oferta": res["zona_oferta_cercana"], "Dist_Oferta_%": res["dist_oferta_pct"],
            "Toca_Demanda": res["toca_demanda"], "Toca_Oferta": res["toca_oferta"],
            "En_Zona_De_Interes": interes, "Condiciones": cond,
            "Zonas_Activas": zonas,
        })
    return {"puntos": puntos, "eventos": eventos, "estado": estado_nuevo}


def guardar_zonas(resultado):
    """Persiste el estado y agrega los eventos a la bitácora (solo agregado)."""
    os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
    if resultado.get("estado"):
        with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
            json.dump(resultado["estado"], f, ensure_ascii=False, indent=2)
    if resultado.get("eventos"):
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            for ev in resultado["eventos"]:
                f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
