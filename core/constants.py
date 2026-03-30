# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# UBICACIÓN: core/constants.py
# VERSION: 104.2.4 (PROTOCOL OLYMPUS - SOBERANÍA DEL DATO)
# AUTOR: Héctor & Gemini AI
# DESCRIPCIÓN: Piedra Rosetta del Sistema. Centraliza el ADN de Tipado,
#              Metadatos de Seguridad y Contratos de Interfaz.
#              v104.2.4: REQ-01 - Consolidación de Punteros ADN y Alias Críticos.
#              Garantiza que la UI aplique correctamente el formato de miles.
# =============================================================================

# 1. ADN DEL DATO (Identificadores de Renderizado)
# -----------------------------------------------------------------------------
# Estos punteros permiten que el ThemeManager distinga el tratamiento visual
# sin que el motor matemático tenga que intervenir.
DNA_MONEY = 0x01  # Identificador para Montos: Fuerza 0 decimales y sep. de miles.
DNA_RATIO = 0x02  # Identificador para Ratios: Fuerza 2 decimales, % y símbolos especiales.
DNA_INT   = 0x03  # Identificador para Cantidades Enteras y Conteos.
DNA_TEXT  = 0x04  # Identificador para Cadenas de Texto y Etiquetas.

# 2. SEGURIDAD Y PRESTIGIO (Zona de Purga)
# -----------------------------------------------------------------------------
# Prefijo Dunder para metadatos internos que NO deben salir al usuario final.
META_PREFIX = "__NEXUS_"

# Llave Primaria Universal para el Metadata Store (Sincronía de ID)
# Se utiliza para vincular el Estilo con el Dato sin importar el Sorting/Filtering.
PK_SOURCE = "id"

# Canales de Salida que requieren Purga de Metadatos
PURGE_CHANNELS = ['EXCEL', 'CLIPBOARD', 'PDF', 'CSV']

# 3. CONTRATOS DE INTERFAZ (Protocolo de Hierro)
# -----------------------------------------------------------------------------
# Alias Estándar Sincronizados con QueryCenter y Logic.
# Estos nombres garantizan la integridad de la "Tubería de Datos" en la UI.
ALIAS_CURRENT_VALUE  = "Monto 26"
ALIAS_TARGET_VALUE   = "Monto Obj"
ALIAS_VARIATION      = "Variación %"
ALIAS_ACTIVE_CLIENTS = "Clientes Activos"

# Mapeo de ADN por Columna (Soberanía de la Apariencia)
# Este mapa le dice a la UI qué traje ponerle a cada columna (Fase 1: Anclaje ADN).
DNA_MAP = {
    # Alias Globales (Vínculo Directo con UI - Strict Piano Ready)
    ALIAS_CURRENT_VALUE: DNA_MONEY,
    ALIAS_TARGET_VALUE:  DNA_MONEY,
    ALIAS_VARIATION:     DNA_RATIO,
    ALIAS_ACTIVE_CLIENTS: DNA_INT,

    # Columnas de Reporte de Ventas (Mapeo Específico de Operación)
    "Monto":             DNA_MONEY,
    "Objetivo":          DNA_MONEY,
    "Variación":         DNA_RATIO,
    "Obj Monto":         DNA_MONEY,
    "Mont 26":           DNA_MONEY,
    "Var % Monto":       DNA_RATIO,
    "Obj Cant":          DNA_INT,
    "Cant 26":           DNA_INT,
    "Var % Cant":        DNA_RATIO,

    # Mapeo de Entidades Gerenciales (KPIs Superiores)
    "venta_total":       DNA_MONEY,
    "variacion_total":   DNA_RATIO,

    # Mapeo Preventivo Módulo 5000 (Contabilidad)
    "Saldo":             DNA_MONEY,
    "Débito":            DNA_MONEY,
    "Crédito":           DNA_MONEY,
    "Margen %":          DNA_RATIO
}

# 4. CONFIGURACIÓN DE TELEMETRÍA (IronConfig)
# -----------------------------------------------------------------------------
# Tiempo límite para la validación de la tubería de datos (Supabase Contract)
IRON_CONFIG_TIMEOUT = 1.5  # Segundos

# 5. WHITELIST DE EXPORTACIÓN
# -----------------------------------------------------------------------------
# Solo lo que no contenga el META_PREFIX y esté en esta lógica será visible.
WHITELIST_EXPORT = True

# -----------------------------------------------------------------------------
# [EXECUTION-CONFIRMED] Se han aplicado los cambios de la TABLA DE EJECUCIÓN QUIRÚRGICA sobre el script core/constants.py
# -----------------------------------------------------------------------------