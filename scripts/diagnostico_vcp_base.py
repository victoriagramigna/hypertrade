"""
Diagnostico de UN activo: por que su base VCP "real" (estudio_vcp_v4 / vcp_base_v4) paso o no paso cada dia.

APARTE: no toca el radar, ni la Watchlist VCP, ni "Bases VCP reales", ni la Auditoria. Solo baja ~2 anios de datos
de Yahoo del activo y escribe data/diagnostico_vcp_base.md con los giros (maximos y minimos reales confirmados a 5
ruedas) y, para cada una de las ultimas ruedas, la primera condicion que no se cumplio.

Uso: python scripts/diagnostico_vcp_base.py DD
"""
import logging
import sys

import numpy as np
import pandas as pd

import estudio_vcp_v4 as v4

log = logging.getLogger("diag_vcp")
RUTA_MD = "data/diagnostico_vcp_base.md"
DIAS = 30


def _explicar(zz, t):
    """Replica las condiciones de v4._base y devuelve (ok, motivo)."""
    if len(zz) < 4:
        return False, "menos de 4 giros confirmados"
    if zz[-1][0] != "L":
        return False, "el ultimo giro confirmado es un maximo (la base necesita terminar en un minimo)"
    pares, k = [], len(zz) - 1
    while k >= 1 and zz[k][0] == "L" and zz[k - 1][0] == "H" and len(pares) < v4.MAX_CONTR:
        pares.append((zz[k - 1], zz[k]))
        k -= 2
    pares.reverse()
    prof = [(h[2] - l[2]) / h[2] * 100 for h, l in pares]
    n = 1
    while n < len(pares) and prof[-n - 1] > prof[-n]:
        n += 1
    ptxt = " → ".join(f"{p:.1f}%" for p in prof)
    if n < 2:
        return False, f"contracciones no decrecientes (de la mas vieja a la nueva: {ptxt})"
    pares, prof = pares[-n:], prof[-n:]
    hn, ln = pares[-1]
    if prof[-1] <= 0:
        return False, "ultima contraccion sin profundidad"
    if prof[-1] > v4.MAX_ULT:
        return False, f"la ultima contraccion es de {prof[-1]:.1f}% (maximo {v4.MAX_ULT:.0f}%)"
    if prof[0] < v4.MIN_PRIMERA:
        return False, f"la primera contraccion es de {prof[0]:.1f}% (minimo {v4.MIN_PRIMERA:.0f}%)"
    if t - ln[1] > v4.MAX_EDAD_BAJO:
        return False, f"el ultimo minimo tiene {t - ln[1]} ruedas (maximo {v4.MAX_EDAD_BAJO})"
    if t - hn[1] > v4.MAX_EDAD_PIVOTE:
        return False, f"el pivote tiene {t - hn[1]} ruedas (maximo {v4.MAX_EDAD_PIVOTE})"
    if t - pares[0][0][1] > v4.MAX_BASE:
        return False, f"la base empieza hace {t - pares[0][0][1]} ruedas (maximo {v4.MAX_BASE})"
    top = max(p[0][2] for p in pares)
    if hn[2] < v4.PIVOTE_CERCA * top:
        return False, f"el ultimo maximo ({hn[2]:.2f}) esta a menos de 95% del maximo de la base ({top:.2f})"
    return True, f"BASE VALIDA: {n} contracciones ({' → '.join(f'{p:.1f}%' for p in prof)}), pivote {hn[2]:.2f}, stop {ln[2]:.2f}"


def correr(ticker, datos=None, guardar=True):
    if datos is None:
        O, H, L, C, V = v4.descargar_ohlc([ticker, "SPY"], period="2y")
    else:
        O, H, L, C, V = datos
    if ticker not in C.columns:
        log.error(f"{ticker}: sin datos")
        sys.exit(1)
    idx = C.index
    h, l, c = H[ticker].values, L[ticker].values, C[ticker].values
    n = len(idx)
    giros = v4._giros(h, l, v4.K_PRINCIPAL)
    zz, filas, snaps = [], [], {}
    for j in range(1, n):
        e = giros.get(j - 1)
        if e:
            v4._agregar(zz, e)
        if j >= n - DIAS:
            ok, motivo = _explicar(zz, j - 1)
            filas.append((idx[j].strftime("%Y-%m-%d"), c[j], ok, motivo))
    e = giros.get(n - 1)
    if e:
        v4._agregar(zz, e)
    ok_hoy, motivo_hoy = _explicar(zz, n - 1)

    L_ = [f"# Diagnostico de base VCP real: {ticker}", "",
          f"Datos hasta {idx[-1].strftime('%Y-%m-%d')} (Yahoo, ajustados). Giros confirmados a {v4.K_PRINCIPAL} ruedas, sin mirar el futuro. Mismas condiciones que 'Bases VCP reales'.", "",
          f"**Hoy:** {'SI' if ok_hoy else 'NO'} -- {motivo_hoy}", "",
          f"## Giros confirmados (ultimos 12)", "", "| Tipo | Fecha | Precio | Contraccion (maximo -> minimo) |", "|---|---|---|---|"]
    for i, g in enumerate(zz[-12:]):
        k = len(zz) - 12 + i if len(zz) >= 12 else i
        pr = ""
        if g[0] == "L" and k >= 1 and zz[k - 1][0] == "H":
            pr = f"{(zz[k - 1][2] - g[2]) / zz[k - 1][2] * 100:.1f}%"
        L_.append(f"| {'maximo' if g[0] == 'H' else 'minimo'} | {idx[g[1]].strftime('%Y-%m-%d')} | {g[2]:.2f} | {pr} |")
    L_ += ["", f"## Ultimas {DIAS} ruedas: por que si o no", "", "| Fecha | Cierre | Base | Motivo |", "|---|---|---|---|"]
    for f, cc, ok, m in filas:
        L_.append(f"| {f} | {cc:.2f} | {'si' if ok else 'no'} | {m} |")
    L_ += ["", "Nota: es una lectura de las mismas reglas que usa la app, no una opinion sobre el activo.", ""]
    txt = "\n".join(L_)
    if guardar:
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(txt)
    return txt


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr((sys.argv[1] if len(sys.argv) > 1 else "DD").upper())
