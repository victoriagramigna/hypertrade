# Integración de los módulos nuevos a HyperTrade

Este archivo explica cómo conectar los 4 módulos nuevos
(`avwap.py`, `senales_nuevas.py`, `radar_score_v2.py`, `narrativa.py`)
con el pipeline existente en `scripts/main.py`, sin romper nada de lo
que ya funciona.

## 1. Dónde van los archivos

Subí los 4 archivos a la carpeta `scripts/` de `hypertrade`, junto a
los que ya existen (`main.py`, `radar_score.py`, `vcp.py`, etc.).

## 2. Cambios en `main.py`

### 2.1. Al principio del archivo, sumar los imports

```python
from avwap import agregar_avwaps, evaluar_lider_soporte, detectar_cruce_avwap_52w
from senales_nuevas import (
    agregar_columnas_pendiente, evaluar_stage2,
    agregar_atr_contraction, evaluar_atr_contraction,
    calcular_distribution_days, evaluar_penalizacion_distribution,
)
from radar_score_v2 import calcular_score_compuesto
from narrativa import armar_narrativa
```

### 2.2. Una sola vez por corrida (antes del loop de tickers)

Justo donde ya calculás el régimen de mercado (VIX, riesgo país,
etc.), agregar:

```python
df_spy = descargar_datos_yfinance("SPY")  # o como se llame tu función actual
dist_days = calcular_distribution_days(df_spy)
penalizacion_mercado = evaluar_penalizacion_distribution(dist_days)
```

### 2.3. Dentro del loop de cada ticker

Después de tener el DataFrame del ticker ya descargado (`df`), antes
de armar la alerta:

```python
df = agregar_avwaps(df)
df = agregar_columnas_pendiente(df)
df = agregar_atr_contraction(df)

fila_hoy = df.iloc[-1]

señales = {
    "rs_alto": fila_hoy.get("RS_Score", 0) > 80,
    "stage2": evaluar_stage2(fila_hoy),
    "apoyo_soporte": evaluar_lider_soporte(fila_hoy),
    "vcp": tu_funcion_vcp_existente(fila_hoy),           # la que ya tenés en vcp.py
    "gap_alcista": tu_funcion_gap_existente(fila_hoy),   # la que ya tenés
    "cruce_avwap_52w": detectar_cruce_avwap_52w(df),
    "atr_contraction": evaluar_atr_contraction(fila_hoy),
}

resultado_score = calcular_score_compuesto(fila_hoy, señales, penalizacion_mercado)

narrativa_texto = armar_narrativa(
    row=fila_hoy,
    señales_activas=resultado_score["señales_activas"],
    distribution_days=dist_days,
    penalizacion_mercado=penalizacion_mercado,
    regimen_sano=regimen_mercado["sano"],       # ya existe en tu pipeline
    riesgo_pais=contexto_macro.get("riesgo_pais"),  # ya existe en tu pipeline
)
```

### 2.4. Al armar el diccionario de la alerta para el JSON

Donde ya construís el diccionario que se guarda en `data/ultimo.json`
para cada ticker, sumar dos campos nuevos:

```python
alerta = {
    # ... todos los campos que ya tenés (ticker, precio, RS_Score, etc.) ...
    "score_tecnico": resultado_score["score_tecnico"],
    "score_compuesto": resultado_score["score_compuesto"],
    "señales_activas": resultado_score["señales_activas"],
    "narrativa": narrativa_texto,
}
```

**Importante:** esto NO reemplaza ningún campo existente, solo agrega
4 campos nuevos. El dashboard actual (si no lo tocás) va a seguir
funcionando exactamente igual, ignorando los campos nuevos que no
conoce — es decir, es un cambio seguro y reversible.

## 3. Qué falta para el dashboard

Con esto, `data/ultimo.json` ya va a traer todo lo necesario para
mostrar la narrativa al pie de cada tarjeta y el nuevo score. El
rediseño visual del dashboard (pestañas, la tarjeta con el texto
abajo, colores según score_compuesto positivo/negativo) es un paso
aparte, una vez que confirmemos que el JSON se genera bien con estos
campos nuevos.

## 4. Orden sugerido para probar

1. Subir los 4 archivos a `scripts/`
2. Hacer los 4 cambios de arriba en `main.py`
3. Correr el workflow manualmente en modo "test" (como ya hicimos)
4. Revisar en los logs o en `data/ultimo.json` que aparezcan los
   campos `score_compuesto` y `narrativa` con valores que tengan
   sentido para algunos tickers conocidos
5. Recién ahí, pasar al rediseño visual del dashboard
