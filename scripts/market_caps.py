"""
Baja la capitalizacion de mercado (en USD) de cada papel del universo para que el
cuadrante de rotacion dibuje burbujas de distinto tamano. Dato informativo, aparte:
no toca el radar ni la Auditoria. Escribe data/market_caps.json. Si un papel falla
se conserva el valor anterior. Se corre a mano junto con rs_backfill.
"""
import json, logging, os, sys
from datetime import datetime, timezone

sys.path.insert(0, "scripts")
from config import TICKERS

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("market_caps")
SALIDA = "data/market_caps.json"


def main():
    import yfinance as yf
    previo = {}
    if os.path.exists(SALIDA):
        try:
            previo = json.load(open(SALIDA, encoding="utf-8")).get("caps", {})
        except Exception:
            previo = {}
    caps, ok, fallo = dict(previo), 0, 0
    for t in TICKERS:
        try:
            c = yf.Ticker(t).fast_info["market_cap"]
            if c and c > 0:
                caps[t] = int(c); ok += 1
            else:
                fallo += 1
        except Exception:
            fallo += 1
    log.info(f"{ok} capitalizaciones nuevas, {fallo} sin dato (se conserva el valor anterior si lo habia)")
    if ok < 50:
        log.error("Muy pocos datos -- no se guarda"); sys.exit(1)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({"generado_utc": datetime.now(timezone.utc).isoformat(), "caps": caps}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
