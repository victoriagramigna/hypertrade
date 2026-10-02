"""
Configuración central del Radar de Mercado.
Cambiar acá el universo de tickers, sectores, y parámetros del sistema
NO requiere tocar el resto del código.
"""

# --- Universo de tickers por sector (ampliable a demanda) ---
TICKERS = {
    "XOM": "Energía", "CVX": "Energía", "VIST": "Energía", "YPF": "Energía",
    "AAPL": "Tecnología", "MSFT": "Tecnología", "NVDA": "Tecnología", "GOOGL": "Tecnología",
    "JPM": "Bancos", "BMA": "Bancos", "GGAL": "Bancos", "WFC": "Bancos",
    "JNJ": "Salud", "PFE": "Salud", "MRK": "Salud",
    "WMT": "Consumo", "KO": "Consumo", "MELI": "Consumo",
    "EWZ": "ETF", "XLE": "ETF", "XLK": "ETF",
    # --- Sumados desde la cartera de CEDEARs de Victoria (versión en USD del activo real) ---
    "TSLA": "Automotriz",
    "QQQ": "ETF",
    "BABA": "Consumo",       # e-commerce, mismo grupo que MELI
    "OKLO": "Energía",       # reactores nucleares modulares
    "JMIA": "Consumo",       # e-commerce africano
    "SATL": "Tecnología",    # imágenes satelitales
    "CRWV": "Tecnología",    # cómputo en la nube para IA
    "TEM": "Salud",          # IA aplicada a diagnóstico/datos de salud
    "LAC": "Materiales",     # litio, insumo para baterías
    # --- Lista ampliada pedida por Victoria (ver notas de ajuste de tickers en el chat) ---
    "AMD": "Tecnología",      # asumido por "AM" -- confirmar si no era esto
    "TSM": "Tecnología",
    "QCOM": "Tecnología",
    "GLOB": "Tecnología",     # Globant, de origen argentino
    "ADBE": "Tecnología",
    "SHOP": "Tecnología",
    "ZM": "Tecnología",
    "AMZN": "Consumo",
    "UBER": "Consumo",
    "NFLX": "Consumo",
    "TGT": "Consumo",
    "ABNB": "Consumo",
    "HOOD": "Fintech",
    "PYPL": "Fintech",
    "V": "Fintech",
    "XYZ": "Fintech",         # antes "Square"
    "SPGI": "Fintech",        # calificadora/datos financieros
    "C": "Bancos",
    "GM": "Automotriz",
    "F": "Automotriz",
    "VALE": "Materiales",
    "B": "Materiales",        # Barrick Gold -- ticker corto, confirmar que no colisione
    "TX": "Materiales",       # Ternium, grupo Techint (argentino) -- el ticker real de NYSE es "TX", no "TXR" (ese es el código interno de BYMA)
    "TEN": "Energía",         # Tenaris, grupo Techint (argentino), caños para petróleo/gas
    "T": "Telecomunicaciones",
    "AAL": "Transporte",
    "BIOX": "Agro",           # Bioceres, agrobiotecnología argentina
    "ARKK": "ETF",
    "BRK-B": "Diversificado", # Berkshire Hathaway -- BYMA lo llama "BRKB", en Yahoo es "BRK-B"
    "DOW": "Materiales",      # Dow Inc., química
    # "NTCO": "Consumo",       # Natura -- sacado del universo: falló 4 corridas
    # seguidas en yfinance a pesar de estar realmente listada en NYSE (parece
    # un problema específico y persistente de Yahoo con este símbolo puntual,
    # no un error nuestro). Si en algún momento se quiere reintentar, solo
    # hay que sacarle el comentario a esta línea.
    "LAR": "Materiales",      # Lithium Americas (Argentina) -- distinto de LAC
    "BBD": "Bancos",          # Banco Bradesco (Brasil)
    "FSLR": "Energía",        # First Solar
    "GPRK": "Energía",        # GeoPark
    "LLY": "Salud",           # Eli Lilly
    "NIO": "Automotriz",      # NIO, autos eléctricos chinos
    "NU": "Fintech",          # Nu Holdings (Nubank)
    "PAGS": "Fintech",        # PagSeguro
    "PEP": "Consumo",         # PepsiCo
    "PLTR": "Tecnología",     # Palantir
    "RIO": "Materiales",      # Rio Tinto
    "SPCE": "Aeroespacial",   # Virgin Galactic
    "SPOT": "Tecnología",     # Spotify
    "SPXL": "ETF",            # Direxion S&P500 Bull 3x -- APALANCADO, más volátil que un ETF normal
    "UNH": "Salud",           # UnitedHealth
    "URA": "Energía",         # Global X Uranium ETF, insumo para nuclear (par de OKLO)
    "TGS": "Energía",         # Transportadora de Gas del Sur -- ADR en NYSE, misma empresa que TGSU2
    "PAM": "Energía",         # Pampa Energía -- generación eléctrica + oil & gas
    "SUPV": "Bancos",         # Grupo Supervielle
    "BBAR": "Bancos",         # Banco BBVA Argentina -- asumí que no era el BBVA español, confirmame
    "BBVA": "Bancos",         # Banco Bilbao Vizcaya Argentaria (España) -- la matriz, distinta de BBAR
    # --- 19 tickers nuevos sumados en sept. 2026 (7 confirmados + 12 de la tanda BYMA/Comafi) ---
    "ARM": "Tecnología",       # ARM Holdings, diseño de chips
    "AVGO": "Tecnología",      # Broadcom
    "IREN": "Tecnología",      # IREN Ltd -- data centers Bitcoin/IA
    "TXN": "Tecnología",       # Texas Instruments
    "AMAT": "Tecnología",      # Applied Materials
    "SNDK": "Tecnología",      # SanDisk, spin-off de Western Digital
    "EDN": "Energía",          # Edenor -- distribución eléctrica AMBA (ADR, sin CEDEAR propio)
    "KLAC": "Tecnología",      # KLA Corp -- equipos de inspección de semiconductores
    "SKHY": "Tecnología",      # SK Hynix -- memorias DRAM/NAND para IA
    "DELL": "Tecnología",      # Dell -- servidores y storage corporativo
    "WDC": "Tecnología",       # Western Digital -- discos rígidos
    "GEV": "Energía",          # GE Vernova -- equipos de generación eléctrica
    "TLN": "Energía",          # Talen Energy -- generadora con exposición a data centers
    "MS": "Bancos",            # Morgan Stanley
    "IBKR": "Fintech",         # Interactive Brokers
    "SPCX": "Aeroespacial",    # SpaceX
    "WELL": "Real Estate",     # Welltower -- REIT de infraestructura de salud
    "PLD": "Real Estate",      # Prologis -- REIT de depósitos y logística
    "LIN": "Materiales",       # Linde -- gases industriales
    "SHW": "Materiales",       # Sherwin-Williams -- pinturas
    # --- Tanda 1 del listado completo de CEDEARs de tu bróker (sept. 2026) ---
    # Sin ratio todavía (las capturas no lo mostraban) -- entran al universo
    # técnico (RS Score, alertas) pero no al panel de CEDEAR caro/barato.
    "BP": "Energía", "CAT": "Materiales", "CL": "Consumo", "COST": "Consumo",
    "CRM": "Tecnología", "CRWD": "Tecnología", "DE": "Materiales", "DHR": "Materiales",
    "DIS": "Tecnología",       # Walt Disney -- ticker real de NYSE, no "DISN" (código interno de BYMA)
    "EBAY": "Consumo", "ETSY": "Consumo", "GS": "Bancos",
    "IBM": "Tecnología", "INTC": "Tecnología", "ISRG": "Salud", "MA": "Fintech",
    "MCD": "Consumo", "MDLZ": "Consumo", "META": "Tecnología", "MMM": "Materiales",
    "MRNA": "Salud", "MRVL": "Tecnología", "MU": "Tecnología", "NKE": "Consumo",
    "NOW": "Tecnología", "ORCL": "Tecnología", "OXY": "Energía", "PANW": "Tecnología",
    "PATH": "Tecnología", "PG": "Consumo", "PINS": "Tecnología", "PSX": "Energía",
    "RBLX": "Tecnología", "ROKU": "Tecnología", "ROST": "Consumo", "SBUX": "Consumo",
    "SHEL": "Energía", "SLB": "Energía", "SNAP": "Tecnología", "SNOW": "Tecnología",
    "TEAM": "Tecnología", "TJX": "Consumo", "TTE": "Energía", "UAL": "Transporte",
    "UNP": "Transporte", "UPST": "Fintech", "USB": "Bancos", "VRTX": "Salud",
    "CVS": "Salud",  # CVS Health Corp -- confirmado por Victoria
    # --- Tanda 2 del listado completo (120 tickers). BAC, BK y NOK usan su
    # ticker real de NYSE/NASDAQ -- BA.C, BNY y NOKA eran códigos internos
    # de BYMA que yfinance no reconoce (mismo problema que tuvo Disney) ---
    "AAP": "Automotriz", "ABBV": "Salud", "ABT": "Salud", "ACN": "Tecnología",
    "AGRO": "Agro",            # Adecoagro -- ticker real de NYSE, no "ADGO" (código interno de BYMA)
    "ADI": "Tecnología", "ADP": "Tecnología", "AEG": "Fintech",
    "AEM": "Materiales", "AI": "Tecnología", "AIG": "Fintech", "ALAB": "Tecnología",
    "ASR": "Transporte", "ASTS": "Tecnología", "AVY": "Materiales", "AXP": "Fintech",
    "AZN": "Salud", "BA": "Aeroespacial", "BAC": "Bancos", "BAK": "Materiales",
    "BB": "Tecnología", "BCS": "Bancos", "BHP": "Materiales", "BIDU": "Tecnología",
    "BIIB": "Salud",
    # "BK": "Bancos",  # Bank of New York Mellon -- sacado del universo: falló
    # 4 corridas seguidas en yfinance (mismo patrón que tuvo NTCO -- ticker
    # real y activamente operado, problema específico y persistente de
    # Yahoo con este símbolo puntual, no un error nuestro). Si en algún
    # momento se quiere reintentar, sacarle el comentario a esta línea Y a
    # las de RATIOS_CEDEAR / ALIAS_CEDEAR_DATA912 más abajo.
    "BKNG": "Consumo", "BKR": "Energía",
    "BMNR": "Tecnología", "BMY": "Salud", "BX": "Fintech", "CAH": "Salud",
    "CAR": "Consumo", "CCJ": "Energía", "CCL": "Consumo", "CDE": "Materiales",
    "CEG": "Energía", "COIN": "Fintech", "COP": "Energía", "DECK": "Consumo",
    "DEO": "Consumo", "DOCU": "Tecnología",
    # "EA": "Tecnología",  # Electronic Arts -- sacado del universo: falló 3
    # corridas seguidas en yfinance (mismo patrón que NTCO y BK -- ticker
    # real y muy líquido, problema puntual y persistente de Yahoo con este
    # símbolo). Si se quiere reintentar, sacarle el comentario a esta línea
    # Y a la de RATIOS_CEDEAR más abajo.
    "ECL": "Materiales",
    "EFX": "Fintech", "EQNR": "Energía", "ERIC": "Tecnología", "GLW": "Tecnología",
    "GRMN": "Tecnología", "GSK": "Salud", "GT": "Automotriz", "HAL": "Energía",
    "HD": "Consumo", "HDB": "Bancos", "HL": "Materiales", "HMC": "Automotriz",
    "HMY": "Materiales", "HOG": "Automotriz", "HON": "Materiales", "HPQ": "Tecnología",
    "HSBC": "Bancos", "HSY": "Consumo", "HUT": "Tecnología", "HWM": "Aeroespacial",
    "IBN": "Bancos", "INFY": "Tecnología", "ING": "Bancos", "IP": "Materiales",
    "JCI": "Materiales", "JD": "Consumo", "KB": "Bancos", "KMB": "Consumo",
    "LMT": "Aeroespacial", "LRCX": "Tecnología", "LVS": "Consumo", "LYG": "Bancos",
    "MDT": "Salud", "MO": "Consumo", "MOS": "Agro", "MP": "Materiales",
    "MSI": "Tecnología", "MSTR": "Fintech", "MUX": "Materiales", "NEE": "Energía",
    "NEM": "Materiales", "NGG": "Energía", "NMR": "Bancos", "NOK": "Tecnología",
    "NUE": "Materiales", "NVO": "Salud", "NVS": "Salud", "NXE": "Energía",
    "O": "Real Estate", "ORLY": "Automotriz", "PAAS": "Materiales", "PBR": "Energía",
    "PCAR": "Automotriz", "PDD": "Consumo", "PM": "Consumo", "RACE": "Automotriz",
    "RGTI": "Tecnología", "RIOT": "Tecnología", "RKLB": "Aeroespacial", "RTX": "Aeroespacial",
    "SAP": "Tecnología", "SCCO": "Materiales", "SE": "Consumo", "SONY": "Tecnología",
    "TM": "Automotriz", "TMO": "Salud", "TMUS": "Telecomunicaciones", "TRIP": "Consumo",
    "TV": "Telecomunicaciones", "TWLO": "Tecnología", "UGP": "Energía", "UL": "Consumo",
    "URBN": "Consumo", "VRSN": "Tecnología", "VST": "Energía", "VZ": "Telecomunicaciones",
    # --- Lista de biotecnología/salud + ETFs pedida por Victoria (sept. 2026).
    # De los 19 tickers pedidos, 9 ya estaban en el universo (VRTX, ABBV, BMY,
    # BIIB, JNJ, NVS, ABT, MDT, BIOX) -- solo se suman los 10 que faltaban.
    # Sin ratio de CEDEAR todavía (ver RATIOS_CEDEAR): entran al universo
    # técnico (RS Score, alertas) pero no al panel de CEDEAR caro/barato.
    "IBB": "ETF",    # iShares Biotechnology ETF
    "GLD": "ETF",    # SPDR Gold Shares
    "XLI": "ETF",    # Industrial Select Sector SPDR
    "GE": "Aeroespacial",   # GE Aerospace tras el spin-off de GE Vernova/GE HealthCare (2024)
    "AMGN": "Salud",  # Amgen
    "XLV": "ETF",    # Health Care Select Sector SPDR
    "GILD": "Salud",  # Gilead Sciences
    "ILMN": "Salud",  # Illumina
    "REGN": "Salud",  # Regeneron
    "CRSP": "Salud",  # CRISPR Therapeutics
    # --- Tickers del listado de CEDEARs de Caja de Valores (sept. 2026) que
    # todavía no estaban en el universo -- solo la parte de renta variable de
    # EE.UU. (mercado de origen NYSE/NASDAQ/CBOE), con ticker real confirmado
    # contra el listado. Quedó afuera de esta tanda SI (Silvergate): quebró y
    # el "SICPQ" que muestra la Caja de Valores es el remanente que cotiza
    # OTC tras la bancarrota, sin datos confiables. También quedaron afuera
    # los ~19 CEDEARs de acciones brasileñas (VALE3, PETR3, BBDC3, etc., que
    # cotizan en B3 en reales, no en NYSE en dólares como VALE y PBR que ya
    # están en el universo) -- a la espera de tu confirmación.
    "IWM": "ETF",    # iShares Russell 2000 -- small caps EE.UU.
    "EEM": "ETF",    # iShares MSCI Emerging Markets
    "XLF": "ETF",    # Financial Select Sector SPDR
    "DIA": "ETF",    # SPDR Dow Jones Industrial Average
    "SH": "ETF",     # ProShares Short S&P500 -- INVERSO: sube cuando el mercado baja, se va a comportar al revés que el resto del universo
    "ETHA": "ETF",   # iShares Ethereum Trust -- ETF spot de Ethereum, cotiza como una acción
    "SMH": "ETF",    # VanEck Semiconductor ETF
    "XLU": "ETF",    # Utilities Select Sector SPDR
    "CIBR": "ETF",   # First Trust NASDAQ Cybersecurity ETF
    "TQQQ": "ETF",   # ProShares UltraPro QQQ -- APALANCADO 3x, mismo tipo de riesgo que SPXL
    "VXX": "ETF",    # iPath Series B S&P 500 VIX -- sigue la volatilidad, no el precio: se comporta muy distinto al resto del universo
    "ITA": "ETF",    # iShares U.S. Aerospace & Defense ETF
    "ICLN": "ETF",   # iShares Global Clean Energy ETF
    "EWY": "ETF",    # iShares MSCI South Korea ETF
    "XME": "ETF",    # SPDR S&P Metals & Mining ETF
    "RSP": "ETF",    # Invesco S&P 500 Equal Weight ETF
    "KEEL": "Tecnología",  # Keel Infrastructure Corp -- nuevo nombre de Bitfarms tras
                            # re-domiciliarse a EE.UU. (abr. 2026), sigue en NASDAQ,
                            # mismo grupo que HUT/IREN/RIOT (mineras BTC / data centers IA)
}

# --- Subcategoría por ticker -- PURAMENTE INFORMATIVA (se muestra chiquita
# al lado del ticker en el dashboard). NO reemplaza ni toca el "Sector" de
# arriba: Rotación Sectorial, RS contra sector y todo lo demás se sigue
# calculando con TICKERS tal cual está. Se agregó a pedido de Victoria
# (1/10) después de preguntar si los semiconductores estaban en el radar --
# estaban, pero agrupados dentro de "Tecnología" sin distinguirse. Solo
# cubre los 4 sectores más heterogéneos (Tecnología, Consumo, Energía,
# Materiales); un ticker sin entrada acá simplemente no muestra
# subcategoría, solo su sector de siempre.
SUBCATEGORIAS = {
    # --- Tecnología ---
    # Semiconductores
    "ADI": "Semiconductores", "ALAB": "Semiconductores", "AMAT": "Semiconductores",
    "AMD": "Semiconductores", "ARM": "Semiconductores", "AVGO": "Semiconductores",
    "INTC": "Semiconductores", "KLAC": "Semiconductores", "LRCX": "Semiconductores",
    "MRVL": "Semiconductores", "MU": "Semiconductores", "NVDA": "Semiconductores",
    "QCOM": "Semiconductores", "SNDK": "Semiconductores", "TSM": "Semiconductores",
    "TXN": "Semiconductores", "WDC": "Semiconductores",
    # Software / Servicios IT
    "ACN": "Software", "ADBE": "Software", "ADP": "Software", "AI": "Software",
    "CRM": "Software", "CRWD": "Software", "DOCU": "Software", "GLOB": "Software",
    "INFY": "Software", "NOW": "Software", "ORCL": "Software", "PANW": "Software",
    "PATH": "Software", "PLTR": "Software", "SAP": "Software", "SNOW": "Software",
    "TEAM": "Software", "TWLO": "Software", "VRSN": "Software", "ZM": "Software",
    # Hardware / Mega Cap
    "AAPL": "Hardware/Mega Cap", "DELL": "Hardware/Mega Cap", "GLW": "Hardware/Mega Cap",
    "GOOGL": "Hardware/Mega Cap", "GRMN": "Hardware/Mega Cap", "HPQ": "Hardware/Mega Cap",
    "IBM": "Hardware/Mega Cap", "META": "Hardware/Mega Cap", "MSFT": "Hardware/Mega Cap",
    "MSI": "Hardware/Mega Cap", "SONY": "Hardware/Mega Cap", "BB": "Hardware/Mega Cap",
    # Internet / Medios digitales
    "BIDU": "Internet/Medios", "DIS": "Internet/Medios", "PINS": "Internet/Medios",
    "RBLX": "Internet/Medios", "ROKU": "Internet/Medios", "SHOP": "Internet/Medios",
    "SNAP": "Internet/Medios", "SPOT": "Internet/Medios",
    # Telecom / Equipos de red
    "ERIC": "Telecom (equipos)", "NOK": "Telecom (equipos)",
    # Minería cripto / Data center IA
    "BMNR": "Minería cripto/Data center", "CRWV": "Minería cripto/Data center",
    "HUT": "Minería cripto/Data center", "IREN": "Minería cripto/Data center",
    "KEEL": "Minería cripto/Data center", "RIOT": "Minería cripto/Data center",
    "SKHY": "Minería cripto/Data center",
    # Espacio / Cuántica (emergente)
    "ASTS": "Espacio/Cuántica", "RGTI": "Espacio/Cuántica", "SATL": "Espacio/Cuántica",

    # --- Consumo ---
    # Consumo Básico (defensivo -- la gente lo sigue comprando en cualquier contexto)
    "CL": "Consumo Básico", "COST": "Consumo Básico", "DEO": "Consumo Básico",
    "HSY": "Consumo Básico", "KMB": "Consumo Básico", "KO": "Consumo Básico",
    "MDLZ": "Consumo Básico", "MO": "Consumo Básico", "PEP": "Consumo Básico",
    "PG": "Consumo Básico", "PM": "Consumo Básico", "UL": "Consumo Básico",
    "WMT": "Consumo Básico",
    # Consumo Discrecional (gasto que se recorta primero si el bolsillo aprieta)
    "ABNB": "Consumo Discrecional", "AMZN": "Consumo Discrecional", "BABA": "Consumo Discrecional",
    "BKNG": "Consumo Discrecional", "CAR": "Consumo Discrecional", "CCL": "Consumo Discrecional",
    "DECK": "Consumo Discrecional", "EBAY": "Consumo Discrecional", "ETSY": "Consumo Discrecional",
    "HD": "Consumo Discrecional", "JD": "Consumo Discrecional", "JMIA": "Consumo Discrecional",
    "LVS": "Consumo Discrecional", "MCD": "Consumo Discrecional", "MELI": "Consumo Discrecional",
    "NFLX": "Consumo Discrecional", "NKE": "Consumo Discrecional", "PDD": "Consumo Discrecional",
    "ROST": "Consumo Discrecional", "SBUX": "Consumo Discrecional", "SE": "Consumo Discrecional",
    "TGT": "Consumo Discrecional", "TJX": "Consumo Discrecional", "TRIP": "Consumo Discrecional",
    "UBER": "Consumo Discrecional", "URBN": "Consumo Discrecional",

    # --- Energía ---
    # Petróleo y Gas
    "BKR": "Petróleo y Gas", "BP": "Petróleo y Gas", "COP": "Petróleo y Gas",
    "CVX": "Petróleo y Gas", "EQNR": "Petróleo y Gas", "GPRK": "Petróleo y Gas",
    "HAL": "Petróleo y Gas", "OXY": "Petróleo y Gas", "PBR": "Petróleo y Gas",
    "PSX": "Petróleo y Gas", "SHEL": "Petróleo y Gas", "SLB": "Petróleo y Gas",
    "TEN": "Petróleo y Gas", "TGS": "Petróleo y Gas", "TTE": "Petróleo y Gas",
    "UGP": "Petróleo y Gas", "VIST": "Petróleo y Gas", "XOM": "Petróleo y Gas",
    "YPF": "Petróleo y Gas",
    # Utilities / Eléctricas reguladas
    "CEG": "Utilities/Eléctricas", "EDN": "Utilities/Eléctricas", "GEV": "Utilities/Eléctricas",
    "NEE": "Utilities/Eléctricas", "NGG": "Utilities/Eléctricas", "PAM": "Utilities/Eléctricas",
    "TLN": "Utilities/Eléctricas", "VST": "Utilities/Eléctricas",
    # Renovables / Uranio
    "CCJ": "Renovables/Uranio", "FSLR": "Renovables/Uranio", "NXE": "Renovables/Uranio",
    "OKLO": "Renovables/Uranio", "URA": "Renovables/Uranio",

    # --- Materiales ---
    # Industriales (maquinaria, conglomerados)
    "CAT": "Industriales", "DE": "Industriales", "DHR": "Industriales",
    "HON": "Industriales", "JCI": "Industriales", "MMM": "Industriales",
    # Minería / Metales
    "AEM": "Minería/Metales", "BHP": "Minería/Metales", "CDE": "Minería/Metales",
    "HL": "Minería/Metales", "HMY": "Minería/Metales", "LAC": "Minería/Metales",
    "LAR": "Minería/Metales", "MP": "Minería/Metales", "MUX": "Minería/Metales",
    "NEM": "Minería/Metales", "PAAS": "Minería/Metales", "RIO": "Minería/Metales",
    "SCCO": "Minería/Metales", "VALE": "Minería/Metales",
    # Químicos / otros materiales
    "AVY": "Químicos/Otros", "B": "Químicos/Otros", "BAK": "Químicos/Otros",
    "DOW": "Químicos/Otros", "ECL": "Químicos/Otros", "IP": "Químicos/Otros",
    "LIN": "Químicos/Otros", "NUE": "Químicos/Otros", "SHW": "Químicos/Otros",
    "TX": "Químicos/Otros",

    # --- Salud --- (sumado 1/10, a pedido de Victoria)
    # Farmacéuticas (labs grandes, tradicionales)
    "ABBV": "Farmacéuticas", "AZN": "Farmacéuticas", "BMY": "Farmacéuticas", "GSK": "Farmacéuticas",
    "JNJ": "Farmacéuticas", "LLY": "Farmacéuticas", "MRK": "Farmacéuticas", "NVO": "Farmacéuticas",
    "NVS": "Farmacéuticas", "PFE": "Farmacéuticas",
    # Biotecnología
    "AMGN": "Biotecnología", "BIIB": "Biotecnología", "CRSP": "Biotecnología", "GILD": "Biotecnología",
    "MRNA": "Biotecnología", "REGN": "Biotecnología", "VRTX": "Biotecnología",
    # Equipos médicos / diagnóstico
    "ABT": "Equipos médicos/diagnóstico", "ILMN": "Equipos médicos/diagnóstico",
    "ISRG": "Equipos médicos/diagnóstico", "MDT": "Equipos médicos/diagnóstico",
    "TEM": "Equipos médicos/diagnóstico", "TMO": "Equipos médicos/diagnóstico",
    # Distribución / servicios de salud
    "CAH": "Distribución/servicios de salud", "CVS": "Distribución/servicios de salud",
    "UNH": "Distribución/servicios de salud",

    # --- Bancos --- (sumado 1/10)
    "BAC": "Banca EE.UU.", "C": "Banca EE.UU.", "GS": "Banca EE.UU.", "JPM": "Banca EE.UU.",
    "MS": "Banca EE.UU.", "USB": "Banca EE.UU.", "WFC": "Banca EE.UU.",
    "BBAR": "Banca LatAm", "BMA": "Banca LatAm", "GGAL": "Banca LatAm", "SUPV": "Banca LatAm",
    "BBD": "Banca LatAm",
    "BBVA": "Banca Europa", "BCS": "Banca Europa", "HSBC": "Banca Europa", "ING": "Banca Europa",
    "LYG": "Banca Europa",
    "HDB": "Banca Asia", "IBN": "Banca Asia", "KB": "Banca Asia", "NMR": "Banca Asia",

    # --- Fintech --- (sumado 1/10)
    "MA": "Pagos", "V": "Pagos", "PYPL": "Pagos", "XYZ": "Pagos", "AXP": "Pagos",
    "NU": "Banca digital/Neobancos", "PAGS": "Banca digital/Neobancos",
    "COIN": "Cripto/Bróker", "HOOD": "Cripto/Bróker", "IBKR": "Cripto/Bróker", "MSTR": "Cripto/Bróker",
    "AEG": "Seguros", "AIG": "Seguros",
    "BX": "Gestión de activos/Datos financieros", "EFX": "Gestión de activos/Datos financieros",
    "SPGI": "Gestión de activos/Datos financieros", "UPST": "Gestión de activos/Datos financieros",

    # --- Automotriz --- (sumado 1/10)
    "F": "Fabricantes tradicionales", "GM": "Fabricantes tradicionales", "HMC": "Fabricantes tradicionales",
    "TM": "Fabricantes tradicionales",
    "TSLA": "Eléctricos/Lujo", "NIO": "Eléctricos/Lujo", "RACE": "Eléctricos/Lujo",
    "AAP": "Repuestos y neumáticos", "ORLY": "Repuestos y neumáticos", "GT": "Repuestos y neumáticos",
    "PCAR": "Camiones y motos", "HOG": "Camiones y motos",

    # --- Aeroespacial --- (sumado 1/10)
    "BA": "Aviación/Defensa", "LMT": "Aviación/Defensa", "RTX": "Aviación/Defensa",
    "GE": "Aviación/Defensa", "HWM": "Aviación/Defensa",
    "RKLB": "Espacio (nuevo)", "SPCE": "Espacio (nuevo)", "SPCX": "Espacio (nuevo)",
}

BENCHMARK = "SPY"

# --- Palabras clave por sector, para detectar eventos geopolíticos/macro en noticias ---
PALABRAS_CLAVE_SECTOR = {
    "Energía": ["ormuz", "opep", "opep+", "sanciones petroleras", "recorte de producción",
                "precio del crudo", "barril", "gasoducto", "refinería"],
    "Tecnología": ["aranceles semiconductores", "controles de exportación china", "chips",
                   "ban tecnológico", "taiwan semiconductor"],
    "Bancos": ["suba de tasas", "fed", "reserva federal", "crisis bancaria", "quiebra banco",
               "tasa de interés"],
    "Salud": ["fda", "retiro de mercado", "juicio farmacéutica", "patente vencida"],
    "Consumo": ["aranceles importación", "guerra comercial", "boicot"],
}

# --- Parámetros del Score de Confirmación (ajustables tras el backtest con datos reales) ---
SCORE_MINIMO_ALERTA = 3       # score a partir del cual se considera señal relevante
VOLUMEN_RELATIVO_MINIMO = 1.5 # volumen de hoy vs promedio 20d, para confirmar

# --- Umbral de "corrida degradada": si falla más de este % del universo,
# el RS Score de los que sí llegaron se calcula sobre un percentil chico y
# no representativo -- se sigue guardando el resultado (los datos que sí
# vinieron son reales), pero se marca la corrida y se salta el envío de
# Telegram esa vez puntual, para no mandar una alerta de compra basada en
# un ranking inflado por matemática de percentil rota, no por el mercado.
UMBRAL_CORRIDA_DEGRADADA_PCT = 25
RSI_ZONA_SANA = (40, 65)      # rango de RSI que suma punto al score
VENTANA_BASE_DIAS = 30        # días recientes para medir si hubo consolidación previa

# --- Confirmación con demora (evita que el score suba/baje de golpe por un solo día) ---
DIAS_CONFIRMACION = 2          # días verdes seguidos (o nuevo máximo) para pasar a "confirmado"
SCORE_TECHO_SIN_CONFIRMAR = 3  # score máximo que puede mostrar una señal recién detectada, sin confirmar aún

# --- Estados narrativos (van junto al score numérico, no lo reemplazan) ---
ESTADOS = {
    "recien_cruzo":  "🔨 Recién cruzó, sin confirmar",
    "confirmado":    "✅ Confirmado",
    "ruptura_vol":   "💣 Ruptura de máximo con volumen",
    "sacudon":       "⚠️ Sacudón, sin definición clara",
    "deterioro":     "🔻 Rompió piso (SMA200)",
    "stop_loss":     "🛑 Perdió EMA200 tras rebote — stop sugerido",
    "lider_soporte": "📈 Líder apoyando en soporte",
    "gap_alcista":   "🚀 Gap alcista con macrotendencia",
    "ruptura_confirmada": "🚀✅ Gap alcista, ahora con volumen",
}

# --- Medias móviles a calcular ---
SMA_CORTAS = (10, 21, 50)   # diario: SMA10, SMA21, SMA50 (setup Minervini)
EMA_LARGA = 200              # diario: EMA200
EMA_SEMANAL = (10, 200)      # semanal: EMA10, EMA200

# --- VCP (Volatility Contraction Pattern) ---
VCP_MIN_CONTRACCIONES = 2     # cantidad mínima de contracciones decrecientes para considerarlo válido
VCP_VENTANA_DIAS = 10         # tamaño de cada "ola" analizada, en días

# --- Régimen de mercado vía VIX (análogo al contexto macro-local, pero para EEUU) ---
VIX_TICKER = "^VIX"
VIX_UMBRAL_ALTO = 25          # VIX > 25 se considera mercado nervioso/volátil

# --- Umbrales de contexto macro-local (Argentina) ---
RIESGO_PAIS_VARIACION_ALERTA = 0.08   # 8% de salto diario dispara "inestable"
# Desde la salida del cepo cambiario (abril 2025), la brecha oficial/blue
# ronda 1-3% en condiciones normales -- un umbral de 30% (pensado para la
# época de controles cambiarios) casi nunca se dispararía. Se baja a 10%
# para que siga siendo una alerta útil si la brecha empieza a ensancharse
# de nuevo (ej. ante una eventual reimposición de controles).
BRECHA_CAMBIARIA_ALERTA_PCT = 10

# --- Historial persistente (necesario para confirmación con demora y stop-loss) ---
ARCHIVO_HISTORIAL = "data/historial_alertas.json"

# --- Ratios de conversión CEDEAR (BYMA, actualizado 3/2/2026 -- fuente oficial).
# Formato "N:1" en BYMA significa N CEDEARs = 1 acción real -> valor teórico ARS
# = (precio_usd * CCL) / ratio. Ninguno de los tuyos usa el formato inverso "1:N".
# IMPORTANTE: los ratios cambian ocasionalmente por decisiones corporativas
# (splits) -- conviene re-chequear contra BYMA cada tanto, no son eternos.
RATIOS_CEDEAR = {
    "SPY": 20, "TSLA": 15, "QQQ": 20, "NVDA": 24, "BABA": 9, "OKLO": 28,
    "AAPL": 20, "JMIA": 1, "SATL": 1, "CRWV": 27, "TEM": 12, "LAC": 1,
    "TSM": 9,  # Taiwan Semiconductor -- faltaba, lo pidió Victoria para Mi Cartera
    "SPCE": 2,  # Virgin Galactic -- ratio 1:2 según Banco Comafi (29/9). Ojo:
    # el "teórico" puede no cerrar del todo contra el precio real (posible
    # precio en USD desactualizado para este ticker en el pipeline) -- no
    # afecta al Balance real de Mi Cartera, que usa el precio real del
    # CEDEAR en vivo, no este teórico.
    # --- 19 tickers nuevos sumados en sept. 2026 (EDN queda afuera: es ADR sin CEDEAR propio) ---
    "ARM": 27, "AVGO": 39, "IREN": 12, "TXN": 5, "AMAT": 5, "SNDK": 170,
    "KLAC": 34, "SKHY": 25, "DELL": 74, "WDC": 92, "GEV": 180, "TLN": 63,
    "MS": 41, "IBKR": 17, "SPCX": 50, "WELL": 48, "PLD": 29, "LIN": 102, "SHW": 69,
    # --- Tanda 1 del listado completo (ratios oficiales BYMA, PDF actualizado 3/2/2026,
    # salvo CRWD que se sumó a BYMA después de esa fecha -- ratio de fuentes cruzadas) ---
    "BP": 5, "CAT": 20, "CL": 3, "COST": 48, "CRM": 18, "CRWD": 79, "DE": 40,
    "DHR": 54, "DIS": 12, "EBAY": 2, "ETSY": 16, "GS": 13, "IBM": 15, "INTC": 5,
    "ISRG": 90, "MA": 33, "MCD": 24, "MDLZ": 15, "META": 24, "MMM": 10, "MRNA": 19,
    "MRVL": 14, "MU": 5, "NKE": 12, "NOW": 172, "ORCL": 3, "OXY": 5, "PANW": 50,
    "PATH": 2, "PG": 15, "PINS": 7, "PSX": 6, "RBLX": 2, "ROKU": 13, "ROST": 4,
    "SBUX": 12, "SHEL": 2, "SLB": 3, "SNAP": 1, "SNOW": 30, "TEAM": 47, "TJX": 22,
    "TTE": 3, "UAL": 5, "UNP": 20, "UPST": 5, "USB": 5, "VRTX": 101, "CVS": 15,
    # --- Tanda 2 (MP, NVO y O quedan afuera: sin ratio confirmado todavía) ---
    "AAP": 14, "ABBV": 10, "ABT": 4, "ACN": 75, "AGRO": 1, "ADI": 15, "ADP": 6, "AEG": 1,
    "AEM": 6, "AI": 5, "AIG": 5, "ALAB": 44, "ASR": 20, "ASTS": 15, "AVY": 18, "AXP": 15,
    "AZN": 4, "BA": 24, "BAC": 4, "BAK": 2, "BB": 3, "BCS": 1, "BHP": 2, "BIDU": 11,
    "BIIB": 13, "BKNG": 700, "BKR": 7, "BMNR": 8, "BMY": 3, "BX": 30, "CAH": 3,
    "CAR": 26, "CCJ": 25, "CCL": 3, "CDE": 1, "CEG": 45, "COIN": 27, "COP": 25, "DECK": 25,
    "DEO": 6, "DOCU": 22, "ECL": 56, "EFX": 16, "EQNR": 6, "ERIC": 2, "GLW": 4,
    "GRMN": 3, "GSK": 4, "GT": 2, "HAL": 2, "HD": 32, "HDB": 2, "HL": 1, "HMC": 1,
    "HMY": 1, "HOG": 3, "HON": 8, "HPQ": 1, "HSBC": 2, "HSY": 21, "HUT": 1, "HWM": 1,
    "IBN": 1, "INFY": 1, "ING": 3, "IP": 4, "JCI": 2, "JD": 4, "KB": 2, "KMB": 6,
    "LMT": 20, "LRCX": 56, "LVS": 2, "LYG": 2, "MDT": 4, "MO": 4, "MOS": 5, "MSI": 20,
    "MSTR": 20, "MUX": 2, "NEE": 19, "NEM": 3, "NGG": 2, "NMR": 1, "NOK": 1, "NUE": 16,
    "NVS": 4, "NXE": 1, "ORLY": 222, "PAAS": 3, "PBR": 1, "PCAR": 3, "PDD": 25, "PM": 18,
    "RACE": 83, "RGTI": 2, "RIOT": 3, "RKLB": 12, "RTX": 5, "SAP": 6, "SCCO": 2, "SE": 32,
    "SONY": 8, "TM": 15, "TMO": 22, "TMUS": 33, "TRIP": 2, "TV": 3, "TWLO": 36, "UGP": 1,
    "UL": 3, "URBN": 2, "VRSN": 6, "VST": 26, "VZ": 4,
    # --- Completado desde el PDF oficial de BYMA (mismo, actualizado 3/2/2026) ---
    "AAL": 2, "ABNB": 15, "ADBE": 44, "AMD": 10, "AMZN": 144, "ARKK": 10,
    "B": 2, "BBD": 1, "BBVA": 1, "BIOX": 1, "BRK-B": 22, "C": 3, "CVX": 16,
    "DOW": 6, "EWZ": 2, "F": 1, "FSLR": 18, "GLOB": 18, "GM": 6, "GOOGL": 58,
    "GPRK": 1, "HOOD": 29, "JNJ": 15, "JPM": 15, "KO": 5, "LAR": 1, "LLY": 56,
    "MELI": 120, "MRK": 5, "MSFT": 30, "NFLX": 48, "NIO": 4, "NU": 2,
    "PAGS": 3, "PEP": 18, "PFE": 4, "PLTR": 3, "PYPL": 8, "QCOM": 11, "RIO": 8,
    "SHOP": 107, "SPGI": 45, "SPOT": 28, "SPXL": 25, "T": 3, "TEN": 1,
    "TGT": 24, "TX": 4, "UBER": 2, "UNH": 33, "URA": 5, "V": 18, "VALE": 2,
    "VIST": 3, "WFC": 5, "WMT": 18, "XLE": 2, "XLK": 46, "XOM": 10, "XYZ": 20,
    "ZM": 47,
    # --- Ratios de ADR (no CEDEAR) para acciones argentinas que cotizan
    # directo en NYSE -- misma lógica de brecha, referencia distinta al
    # dólar CCL en vez del panel de CEDEARs de BYMA.
    "YPF": 1, "GGAL": 10, "BMA": 10, "BBAR": 3, "PAM": 25,
    # SUPV, EDN, TGS: ratio de ADR sin confirmar todavía
}

# --- Casos donde el ticker real (yfinance/NYSE) difiere del código que usa
# data912.com para el panel de CEDEARs (que replica el código interno de
# BYMA) -- sin esto, ese ticker puntual queda sin datos en el panel de
# caro/barato aunque el resto de la app funcione bien. Sin confirmar en vivo
# contra data912 (no accesible desde este entorno de desarrollo); si el
# código real fuera otro, esto simplemente sigue sin encontrar coincidencia,
# no rompe nada.
ALIAS_CEDEAR_DATA912 = {
    "DIS": "DISN",   # Walt Disney
    "BAC": "BA.C",   # Bank of America
    "NOK": "NOKA",   # Nokia
    "AGRO": "ADGO",  # Adecoagro
}

# --- Umbral para marcar un CEDEAR como "caro" o "barato" respecto a su valor teórico ---
BRECHA_CEDEAR_ALERTA_PCT = 3   # +/- 3% de diferencia se considera una distorsión a mirar

# --- Panel de "Movimientos del día" -- tickers que se movieron fuerte HOY (no en meses) ---
UMBRAL_MOVIMIENTO_DIARIO_PCT = 5   # +/- 5% en un solo día entra al panel

# --- Ventana de vigencia de una alerta en el dashboard (ver bug de acumulación infinita) ---
VENTANA_ALERTA_HORAS = 48   # una alerta deja de mostrarse en "Alertas Activas" pasadas estas horas
                             # desde que ese ESTADO empezó (no desde que se detectó por primera vez
                             # el ticker) -- el historial completo se sigue guardando igual

# --- Señal "Líder apoyando en soporte" (RS alto + descansando cerca de su SMA50 sin romperla) ---
UMBRAL_LIDER_RS = 80              # RS Score mínimo para considerarse "líder"
UMBRAL_LIDER_DIST_SMA50_PCT = 2   # como máximo a este % POR ENCIMA de la SMA50 (no por debajo)

# --- Señal "Gap alcista + macrotendencia" (adaptada de un dossier de bot de trading con IA) ---
# Original: precio de HOY > máximo intradiario de AYER + gap de apertura >=3%.
# Adaptada porque el pipeline solo trae precio de cierre (no apertura/máximo/mínimo):
# variación de CIERRE a CIERRE >= umbral, + precio de ayer ya por encima de su SMA200
# (misma idea de "solo operar a favor de la macrotendencia"), + que hoy sea el cierre
# más alto de los últimos 10 días (proxy de "ruptura", ya que no tenemos el máximo real).
UMBRAL_GAP_ALCISTA_PCT = 3       # % mínimo de suba de cierre a cierre para considerarlo "gap"
VENTANA_GAP_MAXIMO_DIAS = 10     # días hacia atrás para chequear que hoy sea el cierre más alto

# --- "Ruptura confirmada" -- avisa por separado (no reemplaza al Gap alcista,
# no le cambia el Score) cuando, DESPUÉS de un Gap alcista, el precio vuelve
# a superar ese mismo nivel pero esta vez con volumen alto de verdad
# (Vol_rel > VOLUMEN_RELATIVO_MINIMO). Agregado 30/9 a pedido de Victoria,
# tras un caso real (SNOW) donde el Gap alcista había salido con volumen
# bajo -- este aviso le da una segunda confirmación más sólida sin obligarla
# a elegir entre "entro ya" o "me quedo afuera".
VENTANA_RUPTURA_CONFIRMADA_DIAS = 10  # días desde el Gap alcista en que todavía
# se considera "el mismo episodio" para buscar la ruptura con volumen

# --- Modo de ejecución: en "test" no se envían notificaciones reales de Telegram ---
import os
MODO = os.environ.get("RADAR_MODO", "test")  # "test" | "produccion"
