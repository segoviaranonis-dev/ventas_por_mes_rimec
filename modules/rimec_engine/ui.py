"""
RIMEC ENGINE — ui.py
Interfaz del motor de gestión de eventos de precio.
Flujo: Paso 0 (carga) → 1 (memoria) → 2 (casos) → 3 (preview/cálculo) → 4 (validación) → 5 (cierre)
"""

import random
import time

# ─────────────────────────────────────────────────────────────────────────────
# OT-520: Flag cálculo SQL masivo
# ─────────────────────────────────────────────────────────────────────────────
USE_CALCULO_SQL = True  # False = fallback Python (fila a fila)

import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text

from core.ux_celebrate import celebrate_save, celebrate_step
from modules.rimec_engine.ui_proceso import proceso_largo, cache_lineas_proveedor
from modules.rimec_engine.biblioteca_ui import (
    render_editor_biblioteca,
    render_maestro_bibliotecas_tab,
    render_seleccion_biblioteca_post_carga,
)
from modules.rimec_engine.biblioteca_maestro import (
    listar_bibliotecas,
    mensaje_si_falta_migracion_biblioteca,
    plantilla_casos_desde_biblioteca,
)
from modules.rimec_engine.logic import (
    leer_excel_proveedor,
    calcular_precios_caso,
    get_preview_skus,
    get_proveedores,
    build_pillar_cache,
    resolver_pilares_evento_sql,
    prefetch_materiales_para_listado,
    get_or_create_linea_cached,
    get_or_create_referencia_cached,
    get_or_create_material_cached,
    crear_evento,
    crear_caso,
    guardar_lineas_excepcion,
    reemplazar_lineas_excepcion,
    parse_lineas_array,
    parse_marcas_array,
    guardar_precio_lista,
    cargar_staging_precio_lista,
    calcular_precio_lista_sql,
    limpiar_staging_precio_lista,
    avanzar_estado_evento,
    resumen_paso3_evento,
    hidratar_paso4_desde_bd,
    ir_a_paso4_validacion,
    contar_skus_procesados,
    cerrar_evento_y_activar,
    registrar_auditoria,
    get_ultimo_evento_cerrado,
    get_casos_evento,
    get_lineas_por_evento,
    get_todos_eventos,
    get_eventos_proveedor,
    excepciones_lineas_por_caso,
    eliminar_evento,
    generar_zip_pdfs_evento,
    evento_esta_en_uso,
    get_estado_real_evento,
    get_biblioteca_casos,
    save_caso_biblioteca,
    eliminar_caso_biblioteca,
    update_caso_biblioteca,
    actualizar_lineas_por_rango,
    purgar_todas_las_listas,
    get_generos,
    resolver_casos_skus,
    normalizar_caso_evento,
    casos_evento_to_dataframe,
    parse_marcas_array,
    parse_lineas_array,
    get_lineas_proveedor,
    get_ultimo_evento_cerrado,
    sincronizar_lineas_caso,
    persistir_caso_matriz_evento,
    eliminar_caso_matriz_evento,
    vaciar_matriz_evento,
    hydrate_casos_evento_desde_db,
    get_contenedor_lineas_resumen,
    validar_barrera_contenedor_excel,
    importar_caso_catalogo_a_evento,
    actualizar_caso_evento,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE UI
# ─────────────────────────────────────────────────────────────────────────────

def _badge(texto: str, color: str) -> str:
    colores = {
        "borrador":  "#475569",
        "validado":  "#0284C7",
        "cerrado":   "#059669",
        "amarillo":  "#D97706",
    }
    bg = colores.get(color, colores.get(texto.lower(), "#475569"))
    return (
        f"<span style='background:{bg};color:white;padding:2px 10px;"
        f"border-radius:99px;font-size:0.72rem;font-weight:600;'>{texto.upper()}</span>"
    )


def _seccion(titulo: str, subtitulo: str = ""):
    st.markdown(
        f"<div style='margin-top:28px;margin-bottom:6px;'>"
        f"<span style='color:#D4AF37;font-weight:700;font-size:1rem;'>{titulo}</span>"
        f"<span style='color:#64748B;font-size:0.8rem;margin-left:8px;'>{subtitulo}</span>"
        f"</div>",
        unsafe_allow_html=True
    )


def _reset_flujo():
    for k in ["re_evento_id", "re_skus", "re_maestros", "re_marcas",
              "re_casos", "re_paso", "re_archivo_nombre", "re_nombre_evento",
              "re_skus_por_caso", "re_proveedor_id", "re_editando_caso",
              "re_plantilla_casos", "re_casos_evento", "re_df_evento",
              "re_casos_evento_hydrated"]:
        if k in st.session_state:
            del st.session_state[k]


# ─────────────────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_rimec_engine():
    st.markdown("## ⚙️ Motor de Precios — RIMEC ENGINE")
    st.markdown("---")

    # Solo renderizar la pestaña activa (evita ~30 s cargando las 5 a la vez).
    opciones_tab = [
        "🆕 Nuevo Evento",
        "📋 Historial",
        "🔧 Admin Líneas",
        "🔗 Línea × Referencia",
        "📦 Contenedor / Catálogo",
    ]
    tab_activa = st.radio(
        "Sección",
        opciones_tab,
        horizontal=True,
        key="motor_tab_activa",
        label_visibility="collapsed",
    )

    if tab_activa == opciones_tab[0]:
        _render_flujo()
    elif tab_activa == opciones_tab[1]:
        _render_historial()
    elif tab_activa == opciones_tab[2]:
        with proceso_largo(
            "Cargando administración de líneas",
            "Consultando pilar de líneas del proveedor…",
        ) as avanzar:
            avanzar(0.5, "Base de datos…")
            _render_admin_lineas()
            avanzar(1.0, "Listo")
    elif tab_activa == opciones_tab[3]:
        with proceso_largo(
            "Cargando Línea × Referencia",
            "Preparando grilla de edición…",
        ) as avanzar:
            avanzar(0.5, "Consultando…")
            _render_linea_referencia()
            avanzar(1.0, "Listo")
    elif tab_activa == opciones_tab[4]:
        _render_admin_casos()


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def _indice_paso_barra(paso) -> int:
    """Convierte re_paso (int o pasos biblioteca str) al índice de la barra 0–5."""
    if isinstance(paso, int):
        return max(0, min(paso, 5))
    if paso in ("bib_select", "bib_editor"):
        return 0
    try:
        return max(0, min(int(paso), 5))
    except (TypeError, ValueError):
        return 0


def _render_flujo():
    paso = st.session_state.get("re_paso", 0)
    paso_idx = _indice_paso_barra(paso)

    # Barra de progreso
    pasos_labels = ["Carga", "Memoria", "Casos", "Preview", "Validación", "Cierre"]
    cols_prog = st.columns(len(pasos_labels))
    for i, label in enumerate(pasos_labels):
        color = "#D4AF37" if i == paso_idx else ("#10B981" if i < paso_idx else "#334155")
        cols_prog[i].markdown(
            f"<div style='text-align:center;padding:6px;background:{color};"
            f"border-radius:6px;font-size:0.72rem;color:white;font-weight:600;'>"
            f"{i}. {label}</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

    if paso == 0:
        _paso_0_carga()
    elif paso == "bib_select":
        _paso_biblioteca_seleccion()
    elif paso == "bib_editor":
        _paso_biblioteca_editor()
    elif paso == 1:
        _paso_1_memoria()
    elif paso == 2:
        _paso_2_casos()
    elif paso == 3:
        _paso_3_preview()
    elif paso == 4:
        _paso_4_validacion()
    elif paso == 5:
        _paso_5_cierre()


# ── PASO 0 — Carga e inicialización ──────────────────────────────────────────

def _paso_0_carga():
    _seccion("Paso 0 — Carga del archivo")
    from modules.rimec_engine.ley_genero import texto_ley_genero_resumen

    with st.expander("Ley de género (obligatoria en cada importación)", expanded=False):
        st.markdown(texto_ley_genero_resumen())

    df_prov = get_proveedores()
    if df_prov.empty:
        st.error("No hay proveedores registrados en la base de datos.")
        return

    opciones = {f"{row['nombre']} ({row['codigo']})": int(row["id"]) for _, row in df_prov.iterrows()}
    proveedor_label = st.selectbox("Proveedor", list(opciones.keys()))
    proveedor_id = opciones[proveedor_label]

    archivo = st.file_uploader("Archivo del proveedor (.xls / .xlsx)", type=["xls", "xlsx"])
    nombre_sugerido = archivo.name.replace(".xls", "").replace(".xlsx", "") if archivo else ""
    nombre_evento = st.text_input("Nombre del evento", value=nombre_sugerido,
                                  placeholder="Ej: TEMPORADA_INVIERNO_2026")
    fecha_desde = st.date_input("Precios vigentes desde", value=date.today())

    # ── HIEDRA: detección automática por nombre de archivo ────────────────────
    if archivo:
        from modules.rimec_engine.hiedra import parsear_nombre_hiedra
        _h = parsear_nombre_hiedra(archivo.name)
        if _h["reconocido"]:
            cat_label = "COMPRA PREVIA" if _h["categoria_codigo"] == "CP" else "PROGRAMADO"
            st.success(
                f"🌿 **Hiedra detectó** — Categoría: **{cat_label}** · "
                f"Proforma fábrica: **{_h['nro_proforma_fabrica']}** · "
                f"PP externo: **{_h['nro_pp_externo']}**"
            )
            st.session_state["hiedra_meta"] = _h
        else:
            st.session_state.pop("hiedra_meta", None)

    if archivo and nombre_evento and st.button("🚀 Cargar y analizar", type="primary"):
        from modules.rimec_engine.ley_genero import (
            validar_ley_genero_importacion,
            texto_ley_genero_resumen,
        )

        load_err: str | None = None
        evento_id = None
        skus = marcas = None
        ley = None

        with proceso_largo(
            "Leyendo archivo Excel",
            f"Analizando **{archivo.name}** — marcas, SKUs y ley de género…",
        ) as avanzar:
            avanzar(0.1, "Abriendo hojas del proveedor…")
            _hm = st.session_state.get("hiedra_meta", {})
            if _hm.get("reconocido"):
                from modules.rimec_engine.hiedra import leer_excel_hiedra
                resultado = leer_excel_hiedra(archivo, archivo.name)
            else:
                resultado = leer_excel_proveedor(archivo, archivo.name)
            avanzar(0.45, "Validando estructura…")

            if resultado["error"]:
                load_err = resultado["error"]
                avanzar(1.0, "Error en archivo")
            else:
                skus = resultado["skus"]
                marcas = resultado["marcas"]
                avanzar(0.6, "Ley de género…")
                ley = validar_ley_genero_importacion(marcas)
                if not ley["ok"]:
                    load_err = "ley_genero"
                    avanzar(1.0, "Validación detenida")
                else:
                    avanzar(0.8, "Creando listado en base de datos…")
                    evento_id = crear_evento(
                        nombre_evento, archivo.name, str(fecha_desde), proveedor_id
                    )
                    avanzar(1.0, "Listo")

        if load_err == "ley_genero":
            if ley and ley.get("marcas_rechazadas"):
                st.error(
                    "**Ley de género:** marcas no reconocidas: "
                    + ", ".join(ley["marcas_rechazadas"])
                )
            if ley and ley.get("generos_faltantes_bd"):
                st.error(
                    "Faltan códigos en maestro **genero**: "
                    + ", ".join(ley["generos_faltantes_bd"])
                )
            with st.expander("Ley de género vigente"):
                st.markdown(texto_ley_genero_resumen())
            return
        if load_err:
            st.error(f"Error al leer el archivo: {load_err}")
            return
        if not evento_id:
            st.error("Error al crear el evento en la base de datos.")
            return

        asig = ", ".join(f"{m}→{g}" for m, g in ley["asignaciones"].items())

        celebrate_step(
            "Paso 0",
            f"{len(skus)} SKUs · {len(marcas)} marcas · Ley de género: {asig}",
            modulo="Motor de Precios",
        )

        st.session_state["re_evento_id"]      = evento_id
        st.session_state["re_proveedor_id"]   = proveedor_id
        st.session_state["re_skus"]           = skus
        st.session_state["re_marcas"]         = marcas
        st.session_state["re_archivo_nombre"] = archivo.name
        st.session_state["re_nombre_evento"]  = nombre_evento
        st.session_state["re_casos"]          = []
        st.session_state["re_casos_evento"]   = []
        st.session_state["re_plantilla_casos"]  = []
        st.session_state["re_df_evento"]        = pd.DataFrame()
        st.session_state["re_skus_por_caso"]  = {}
        st.session_state.pop("re_casos_evento_hydrated", None)
        st.session_state.pop("re_skus_resueltos", None)
        st.session_state.pop("re_ready_to_calc", None)
        st.session_state["re_pending_biblioteca"] = True
        st.session_state["re_paso"] = "bib_select"
        st.rerun()


def _paso_biblioteca_seleccion():
    _seccion("Biblioteca de Casos", "Paso tras carga del Excel")
    evento_id = st.session_state.get("re_evento_id")
    proveedor_id = st.session_state.get("re_proveedor_id")
    nombre = st.session_state.get("re_nombre_evento", "")
    if not evento_id or not proveedor_id:
        st.error("Falta evento o proveedor. Volvé al Paso 0.")
        return
    render_seleccion_biblioteca_post_carga(proveedor_id, evento_id, nombre)


def _paso_biblioteca_editor():
    _seccion("Editor de biblioteca")
    proveedor_id = st.session_state.get("re_proveedor_id")
    evento_id = st.session_state.get("bib_editor_evento_id")
    if not proveedor_id:
        st.error("Proveedor no definido.")
        return
    render_editor_biblioteca(proveedor_id, evento_id)


# ── PASO 1 — Memoria del evento anterior ─────────────────────────────────────

def _alcance_columna_casos(df_display: pd.DataFrame, lineas_map: dict[int, list]) -> list[str]:
    alcance_col = []
    for _, row in df_display.iterrows():
        marcas = row.get("marcas")
        items = []
        if marcas is not None and marcas == marcas:
            if isinstance(marcas, (list, tuple)):
                items = [str(m) for m in marcas if m]
            elif isinstance(marcas, str) and marcas.strip() not in ("", "None", "nan"):
                items = [m.strip() for m in marcas.strip("{}").split(",") if m.strip()]
        if items:
            alcance_col.append(", ".join(items))
        else:
            cid = row.get("id") or row.get("caso_biblioteca_id")
            lins = lineas_map.get(int(cid), []) if cid is not None and cid == cid else []
            if not lins and isinstance(row.get("lineas"), (list, tuple)):
                lins = [str(x) for x in row["lineas"]]
            n = len(lins)
            if lins:
                preview = ", ".join(lins[:6])
                alcance_col.append(f"Líneas ({n}): {preview}{'…' if n > 6 else ''}")
            else:
                alcance_col.append("—")
    return alcance_col


def _celda_display_streamlit(val: object) -> str:
    if val is None:
        return "—"
    try:
        if pd.isna(val):
            return "—"
    except (TypeError, ValueError):
        pass
    if isinstance(val, bool):
        return "Sí" if val else "No"
    if isinstance(val, float) and 0 <= val <= 1:
        return f"{val * 100:.2f}%"
    return str(val)


def _df_arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Evita ArrowTypeError en st.dataframe (columnas object mixtas)."""
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(_celda_display_streamlit)
    return out


def _mostrar_tabla_casos_plantilla(df_display: pd.DataFrame, lineas_map: dict[int, list]) -> None:
    if df_display is None or df_display.empty:
        st.caption("Sin casos en este origen.")
        return
    df_display = df_display.copy()
    if "dolar_politica" in df_display.columns and "factor_conversion" in df_display.columns:
        df_display["indice"] = (
            pd.to_numeric(df_display["dolar_politica"], errors="coerce")
            * pd.to_numeric(df_display["factor_conversion"], errors="coerce")
            / 100
        ).round(0).astype("Int64")
    df_display["alcance"] = _alcance_columna_casos(df_display, lineas_map)
    cols_show = [
        c
        for c in [
            "nombre_caso",
            "dolar_politica",
            "factor_conversion",
            "indice",
            "descuento_1",
            "genera_lpc03_lpc04",
            "alcance",
        ]
        if c in df_display.columns
    ]
    st.dataframe(_df_arrow_safe(df_display[cols_show]), width="stretch", hide_index=True)


def _paso_1_memoria():
    _seccion("Paso 1 — Memoria del evento anterior")

    proveedor_id = st.session_state.get("re_proveedor_id")
    evento_ant = get_ultimo_evento_cerrado()
    mig = mensaje_si_falta_migracion_biblioteca()
    df_bib = (
        listar_bibliotecas(int(proveedor_id))
        if proveedor_id and not mig
        else pd.DataFrame()
    )

    origenes: list[tuple[str, int, str]] = []
    if evento_ant:
        origenes.append(
            (
                "evento",
                int(evento_ant["id"]),
                f"📅 Último evento cerrado: {evento_ant['nombre_evento']} "
                f"({evento_ant['total_skus']} SKUs — {evento_ant['fecha_vigencia_desde']})",
            )
        )
    if df_bib is not None and not df_bib.empty:
        for _, row in df_bib.iterrows():
            origenes.append(
                (
                    "bib",
                    int(row["id"]),
                    f"📚 Biblioteca: {row['nombre']}",
                )
            )

    if not origenes:
        st.info("No hay eventos cerrados ni bibliotecas de precios. Se empieza desde cero.")
        if mig:
            st.warning(mig)
        if st.button("▶️ Continuar"):
            st.session_state["re_plantilla_casos"] = []
            st.session_state["re_paso"] = 2
            st.rerun()
        return

    labels = [o[2] for o in origenes]
    idx_prev = int(st.session_state.get("re_memoria_origen_idx", 0))
    if idx_prev >= len(labels):
        idx_prev = 0
    sel_idx = st.selectbox(
        "Origen de la plantilla (evento cerrado o biblioteca de precios)",
        range(len(labels)),
        format_func=lambda i: labels[i],
        index=idx_prev,
        key="re_memoria_origen_idx",
    )
    tipo, origen_id, _label = origenes[sel_idx]

    plantilla: list[dict] = []
    lineas_map: dict[int, list] = {}
    df_display = pd.DataFrame()

    if tipo == "evento":
        casos_ant = get_casos_evento(origen_id)
        if not casos_ant.empty:
            lineas_map = get_lineas_por_evento(origen_id)
            df_display = casos_ant.copy()
            plantilla = casos_ant.to_dict("records")
            for rec in plantilla:
                cid = int(rec.get("id", 0))
                if cid in lineas_map:
                    rec["lineas"] = lineas_map[cid]
    else:
        if not proveedor_id:
            st.error("Falta proveedor del listado (Paso 0). No se puede cargar la biblioteca.")
            return
        plantilla = plantilla_casos_desde_biblioteca(int(proveedor_id), origen_id)
        if plantilla:
            df_display = pd.DataFrame(plantilla)
            for i, rec in enumerate(plantilla):
                lineas_map[i] = list(rec.get("lineas") or [])

    st.markdown("**Casos de la plantilla elegida:**")
    _mostrar_tabla_casos_plantilla(df_display, lineas_map)

    def _plantilla_actual() -> list[dict]:
        if tipo == "evento":
            casos = get_casos_evento(origen_id)
            if casos.empty:
                return []
            lm = get_lineas_por_evento(origen_id)
            out = casos.to_dict("records")
            for rec in out:
                cid = int(rec.get("id", 0))
                if cid in lm:
                    rec["lineas"] = lm[cid]
            return out
        if proveedor_id:
            return plantilla_casos_desde_biblioteca(int(proveedor_id), origen_id)
        return []

    col1, col2, col3 = st.columns(3)
    if col1.button("📋 Usar como plantilla", type="primary"):
        st.session_state["re_plantilla_casos"] = _plantilla_actual()
        st.session_state["re_biblioteca_plantilla_id"] = (
            origen_id if tipo == "bib" else None
        )
        st.session_state["re_paso"] = 2
        st.rerun()
    if col2.button("✏️ Modificar y usar"):
        st.session_state["re_plantilla_casos"] = _plantilla_actual()
        st.session_state["re_biblioteca_plantilla_id"] = (
            origen_id if tipo == "bib" else None
        )
        st.session_state["re_paso"] = 2
        st.rerun()
    if col3.button("🆕 Empezar desde cero"):
        st.session_state["re_plantilla_casos"] = []
        st.session_state.pop("re_biblioteca_plantilla_id", None)
        st.session_state["re_paso"] = 2
        st.rerun()


# ── PASO 2 — Matriz del listado + análisis ───────────────────────────────────

def _form_caso_listado(
    marcas_disponibles: list,
    prefix: str = "ev",
    evento_id: int | None = None,
    proveedor_id: int | None = None,
) -> None:
    """Agrega un caso a la matriz del listado y persiste contenedor de líneas en BD."""
    nombre_caso = st.text_input("Nombre del caso", key=f"{prefix}_nombre",
                                placeholder="Ej: PROMOCIONALES, NORMAL…")
    col3, col4 = st.columns(2)
    dolar  = col3.number_input("Dólar de política (Gs)", min_value=1.0, step=100.0,
                                value=8000.0, key=f"{prefix}_dolar")
    factor = col4.number_input("Factor", min_value=1.0, step=1.0, format="%.0f",
                                value=180.0, key=f"{prefix}_factor")
    st.caption(f"índice = {int((dolar * factor) / 100):,} Gs / USD FOB")

    cd1, cd2, cd3, cd4 = st.columns(4)
    d1 = cd1.number_input("D1 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d1")
    d2 = cd2.number_input("D2 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d2")
    d3 = cd3.number_input("D3 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d3")
    d4 = cd4.number_input("D4 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d4")
    genera_lpc = st.toggle("Genera LPC03 y LPC04", value=True, key=f"{prefix}_lpc")

    alcance = st.radio("Alcance", ["Marcas", "Líneas específicas"],
                       horizontal=True, key=f"{prefix}_alcance")
    marcas_caso: list = []
    linea_codigos: list = []
    if alcance == "Marcas":
        marcas_caso = st.multiselect("Marcas", marcas_disponibles, key=f"{prefix}_marcas")
    else:
        lineas_str = st.text_input("Líneas (separadas por coma)", key=f"{prefix}_lineas")
        linea_codigos = [c.strip() for c in lineas_str.split(",") if c.strip()]

    if st.button("➕ Agregar a este listado", type="primary", key=f"{prefix}_add"):
        if not nombre_caso:
            st.error("Nombre obligatorio.")
            return
        if alcance == "Marcas" and not marcas_caso:
            st.error("Seleccioná al menos una marca.")
            return
        if alcance == "Líneas específicas" and not linea_codigos:
            st.error("Ingresá al menos una línea.")
            return
        caso = normalizar_caso_evento({
            "nombre_caso":        nombre_caso,
            "dolar_politica":     dolar,
            "factor_conversion":  factor,
            "descuento_1":        round(d1 / 100, 6) if d1 > 0 else None,
            "descuento_2":        round(d2 / 100, 6) if d2 > 0 else None,
            "descuento_3":        round(d3 / 100, 6) if d3 > 0 else None,
            "descuento_4":        round(d4 / 100, 6) if d4 > 0 else None,
            "genera_lpc03_lpc04": genera_lpc,
            "marcas":             marcas_caso if alcance == "Marcas" else None,
            "lineas":             linea_codigos if alcance == "Líneas específicas" else [],
            "alcance_tipo":       "marcas" if alcance == "Marcas" else "lineas",
        })
        nombres = {c["nombre_caso"].upper() for c in st.session_state.get("re_casos_evento", [])}
        if caso["nombre_caso"].upper() in nombres:
            st.error(f"Ya existe el caso «{caso['nombre_caso']}» en este listado.")
            return
        if evento_id and proveedor_id:
            caso_db_id, err = persistir_caso_matriz_evento(
                int(evento_id), int(proveedor_id), caso
            )
            if err:
                st.error(err)
                return
            caso["caso_db_id"] = caso_db_id
        st.session_state.setdefault("re_casos_evento", []).append(caso)
        celebrate_save(
            f"Caso «{caso['nombre_caso']}» + contenedor de líneas guardado",
            modulo="Motor de Precios",
            contexto="guardado",
            balloons=False,
        )
        st.rerun()


def _paso_2_casos():
    _seccion("Paso 2 — Matriz de casos del listado")

    col_nav, _ = st.columns([1, 4])
    if col_nav.button("← Volver a Memoria"):
        st.session_state["re_paso"] = 1
        st.rerun()

    proveedor_id = st.session_state.get("re_proveedor_id")
    evento_id    = st.session_state.get("re_evento_id")
    skus_disp    = st.session_state.get("re_skus", pd.DataFrame())
    nombre_ev    = st.session_state.get("re_nombre_evento", f"Evento #{evento_id}")

    if skus_disp.empty:
        st.error("No hay SKUs cargados.")
        return

    hydrated_for = st.session_state.get("re_casos_evento_hydrated")
    if hydrated_for != evento_id:
        db_casos = []
        with proceso_largo(
            "Cargando matriz del listado",
            "Sincronizando casos y contenedor de líneas desde base de datos…",
        ) as avanzar:
            avanzar(0.4, "Leyendo casos del evento…")
            db_casos = hydrate_casos_evento_desde_db(evento_id)
            avanzar(1.0, "Matriz lista")
        if db_casos:
            st.session_state["re_casos_evento"] = db_casos
        elif "re_casos_evento" not in st.session_state:
            plantilla = st.session_state.get("re_plantilla_casos", [])
            st.session_state["re_casos_evento"] = [
                normalizar_caso_evento(r) for r in plantilla
            ]
        st.session_state["re_casos_evento_hydrated"] = evento_id

    st.caption(
        f"Listado **{nombre_ev}** (id {evento_id}). "
        "Cada caso guarda su **contenedor de líneas** (FK) en base de datos — barrera 1 del import."
    )

    resumen_cont = get_contenedor_lineas_resumen(evento_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("Líneas en contenedor", f"{resumen_cont['total_lineas']:,}")
    c2.metric("Casos con líneas", resumen_cont["n_casos_con_lineas"])
    c3.metric("SKUs en Excel", f"{len(skus_disp):,}")

    if st.button("🔄 Vaciar matriz y empezar de nuevo", key="p2_reset_matriz"):
        ok, msg = vaciar_matriz_evento(evento_id)
        if not ok:
            st.error(msg or "No se pudo vaciar la matriz.")
        else:
            st.session_state["re_casos_evento"] = []
            st.session_state["re_casos_evento_hydrated"] = evento_id
            for k in ("re_skus_resueltos", "re_ready_to_calc", "re_df_evento", "re_conflictos"):
                st.session_state.pop(k, None)
            st.rerun()

    df_cat = get_biblioteca_casos(proveedor_id)
    if df_cat is not None and not df_cat.empty:
        with st.expander("📚 Importar caso desde catálogo", expanded=False):
            nombres_cat = sorted(df_cat["nombre_caso"].astype(str).tolist())
            caso_cat = st.selectbox("Caso del catálogo", nombres_cat, key="p2_caso_catalogo")
            if st.button("➕ Añadir catálogo al listado", key="p2_import_cat"):
                cid, err = importar_caso_catalogo_a_evento(
                    evento_id, proveedor_id, caso_cat
                )
                if err:
                    st.error(err)
                else:
                    st.session_state["re_casos_evento"] = hydrate_casos_evento_desde_db(
                        evento_id
                    )
                    st.session_state["re_casos_evento_hydrated"] = evento_id
                    celebrate_save(
                        f"«{caso_cat}» importado (contenedor {cid})",
                        modulo="Motor de Precios",
                        contexto="guardado",
                        balloons=False,
                    )
                    st.rerun()

    marcas_disp = sorted(
        {str(m).strip() for m in skus_disp.get("marca", pd.Series(dtype=object)).dropna() if str(m).strip()}
    )

    casos_ev: list = st.session_state.get("re_casos_evento", [])
    if casos_ev:
        rows_show = []
        for c in casos_ev:
            lins = parse_lineas_array(c.get("lineas"))
            mars = parse_marcas_array(c.get("marcas"))
            alcance = ", ".join(lins[:8]) + ("…" if len(lins) > 8 else "") if lins else (
                ", ".join(mars) if mars else "—"
            )
            rows_show.append({
                "Caso": c["nombre_caso"],
                "Índice": int((c["dolar_politica"] * c["factor_conversion"]) / 100),
                "Alcance": alcance,
            })
        st.dataframe(pd.DataFrame(rows_show), use_container_width=True, hide_index=True)
        for i, c in enumerate(casos_ev):
            if st.button(f"🗑️ Quitar «{c['nombre_caso']}»", key=f"rm_caso_{i}"):
                caso_db_id = c.get("caso_db_id")
                if caso_db_id:
                    ok, msg = eliminar_caso_matriz_evento(int(caso_db_id), evento_id)
                    if not ok:
                        st.error(msg or "No se pudo eliminar el caso.")
                        st.stop()
                casos_ev.pop(i)
                st.session_state["re_casos_evento"] = casos_ev
                st.session_state.pop("re_skus_resueltos", None)
                st.rerun()
    else:
        st.warning("Agregá al menos un caso a este listado (abajo).")

    with st.expander("➕ Agregar caso a este listado", expanded=not bool(casos_ev)):
        _form_caso_listado(
            marcas_disp, prefix="ev_add",
            evento_id=evento_id, proveedor_id=proveedor_id,
        )

    st.markdown("---")

    if not casos_ev:
        return

    if st.button("🛡️ Barrera 1 — Validar líneas del Excel", key="p2_barrera"):
        df_ev_tmp = casos_evento_to_dataframe(casos_ev)
        barrera = validar_barrera_contenedor_excel(evento_id, skus_disp, df_ev_tmp)
        if barrera:
            st.error(f"**{len(barrera)} línea(s)** del Excel no están en el contenedor del listado.")
            st.dataframe(pd.DataFrame(barrera), use_container_width=True, hide_index=True)
        else:
            st.success("Todas las líneas del Excel están cubiertas por el contenedor.")

    if st.button("🔍 Analizar asignación de SKUs", type="primary"):
        df_evento = casos_evento_to_dataframe(casos_ev)
        skus_resueltos = ready_to_calc = None
        conflictos = []
        with proceso_largo(
            "Analizando SKUs",
            "Barrera de líneas + asignación de casos…",
        ) as avanzar:
            from modules.rimec_engine.logic import asegurar_contenedor_lineas_excel
            from modules.rimec_engine.pillar_fk import asegurar_pilares_para_listado

            avanzar(0.1, "Alta automática en pilar (líneas del Excel)…")
            asegurar_pilares_para_listado(
                proveedor_id, skus_disp, evento_id=evento_id
            )
            df_evento = casos_evento_to_dataframe(casos_ev)
            n_auto_cont = asegurar_contenedor_lineas_excel(
                evento_id, proveedor_id, skus_disp, df_evento
            )
            if n_auto_cont:
                st.session_state["_re_auto_contenedor_n"] = n_auto_cont
            avanzar(0.2, "Barrera 1 — contenedor de líneas…")
            barrera = validar_barrera_contenedor_excel(evento_id, skus_disp, df_evento)
            if barrera:
                st.session_state["_re_barrera_fail"] = barrera
                avanzar(1.0, "Bloqueado por barrera")
            else:
                avanzar(0.5, "Resolviendo casos por línea/marca…")
                skus_resueltos, ready_to_calc, conflictos = resolver_casos_skus(
                    skus_disp, proveedor_id, df_evento, evento_id=evento_id
                )
                avanzar(1.0, "Análisis completo")
        n_auto_cont = st.session_state.pop("_re_auto_contenedor_n", 0)
        if n_auto_cont:
            st.info(
                f"Se inscribieron **{n_auto_cont}** línea(s) nuevas en el contenedor "
                f"del listado (por marca), automáticamente."
            )
        barrera = st.session_state.pop("_re_barrera_fail", None)
        if barrera:
            st.error(
                f"Barrera 1: **{len(barrera)}** línea(s) del Excel fuera del contenedor. "
                "Corregí los casos antes de continuar."
            )
            st.dataframe(pd.DataFrame(barrera), use_container_width=True, hide_index=True)
            return
        if skus_resueltos is None:
            return
        st.session_state["re_skus_resueltos"] = skus_resueltos
        st.session_state["re_ready_to_calc"]  = ready_to_calc
        st.session_state["re_df_evento"]      = df_evento
        st.session_state["re_conflictos"]   = conflictos

    skus_resueltos = st.session_state.get("re_skus_resueltos")
    if skus_resueltos is None or (isinstance(skus_resueltos, pd.DataFrame) and skus_resueltos.empty):
        st.info("Pulsá **Analizar asignación de SKUs** cuando la matriz esté lista.")
        return

    ready_to_calc = st.session_state.get("re_ready_to_calc", False)
    conflictos    = st.session_state.get("re_conflictos", [])

    if conflictos:
        st.error(
            f"**Bloqueo:** esta matriz tiene **{len(conflictos)}** conflicto(s) — "
            "la misma línea o marca en dos casos."
        )
        st.dataframe(pd.DataFrame(conflictos), use_container_width=True, hide_index=True)
        st.info("Corregí la matriz arriba (quitar o reasignar líneas/marcas) y volvé a analizar.")

    st.markdown("### Resumen de asignación")
    df_resumen = skus_resueltos.groupby(["caso_asignado", "estado_validacion"]).size().reset_index(
        name="Cantidad de SKUs"
    )
    st.dataframe(df_resumen, use_container_width=True, hide_index=True)

    if ready_to_calc:
        st.success("✅ Todos los SKUs tienen un caso válido en esta matriz.")
    elif not conflictos:
        st.error("❌ Hay errores en la asignación (revisá estado_validacion).")

    if st.button("▶️ Continuar al Cálculo", type="primary", disabled=not ready_to_calc):
        st.session_state["re_paso"] = 3
        st.rerun()
def _to_float(v) -> float | None:
    """Convierte valor pandas a float. Devuelve None si es nulo, vacío o 'None' string."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    if s in ("", "None", "nan", "NaN", "NULL"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_marcas(marcas_raw) -> list:
    """Convierte el array PostgreSQL o lista Python a lista Python limpia."""
    import ast
    if marcas_raw is None or (isinstance(marcas_raw, float) and pd.isna(marcas_raw)):
        return []
    if isinstance(marcas_raw, (list, tuple)):
        return [str(m).strip() for m in marcas_raw if m]
    if isinstance(marcas_raw, str):
        s = marcas_raw.strip()
        if s in ("", "None", "nan"):
            return []
        if s.startswith("["):
            try:
                parsed = ast.literal_eval(s)
                return [str(m).strip() for m in parsed if m]
            except Exception:
                pass
        return [m.strip().strip("'\"") for m in s.strip("{}").split(",") if m.strip()]
    return []


def _form_nuevo_caso_biblioteca(proveedor_id: int, marcas_disponibles: list,
                                prefix: str = "nb"):
    """Formulario para crear un caso nuevo y persistirlo en la biblioteca."""
    nombre_caso = st.text_input("Nombre del caso", key=f"{prefix}_nombre",
                                placeholder="Ej: NORMAL, CHINELO, CARTERAS…")
    col3, col4 = st.columns(2)
    dolar  = col3.number_input("Dólar de política (Gs)", min_value=1.0, step=100.0,
                                value=8000.0, key=f"{prefix}_dolar")
    factor = col4.number_input("Factor", min_value=1.0, step=1.0, format="%.0f",
                                value=180.0, key=f"{prefix}_factor")

    st.caption(f"📐 índice = {int((dolar*factor)/100):,} Gs / USD FOB")

    cd1, cd2, cd3, cd4 = st.columns(4)
    d1 = cd1.number_input("D1 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d1")
    d2 = cd2.number_input("D2 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d2")
    d3 = cd3.number_input("D3 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d3")
    d4 = cd4.number_input("D4 %", 0.0, 99.0, 0.0, 1.0, key=f"{prefix}_d4")

    genera_lpc = st.toggle("Genera LPC03 y LPC04", value=True, key=f"{prefix}_lpc")

    alcance = st.radio("Alcance", ["Marcas", "Líneas específicas"],
                       horizontal=True, key=f"{prefix}_alcance")
    marcas_caso   = []
    linea_codigos = []
    if alcance == "Marcas":
        marcas_caso = st.multiselect("Marcas", marcas_disponibles, key=f"{prefix}_marcas")
    else:
        lineas_str    = st.text_input("Líneas (separadas por coma)", key=f"{prefix}_lineas")
        linea_codigos = [c.strip() for c in lineas_str.split(",") if c.strip()]

    if st.button("💾 Guardar en biblioteca y agregar al evento", type="primary",
                 key=f"{prefix}_save_btn"):
        if not nombre_caso:
            st.error("Nombre obligatorio.")
            return
        if alcance == "Marcas" and not marcas_caso:
            st.error("Seleccioná al menos una marca.")
            return
        if alcance == "Líneas específicas" and not linea_codigos:
            st.error("Ingresá al menos una línea.")
            return

        caso = {
            "nombre_caso":        nombre_caso.replace("*", "").strip(),
            "dolar_politica":     dolar,
            "factor_conversion":  factor,
            "descuento_1":        round(d1/100, 6) if d1 > 0 else None,
            "descuento_2":        round(d2/100, 6) if d2 > 0 else None,
            "descuento_3":        round(d3/100, 6) if d3 > 0 else None,
            "descuento_4":        round(d4/100, 6) if d4 > 0 else None,
            "genera_lpc03_lpc04": genera_lpc,
            "regla_redondeo":     "centena",
            "marcas":             marcas_caso if alcance == "Marcas" else None,
            "lineas":             linea_codigos if alcance == "Líneas específicas" else [],
            "referencias":        [],
            "alcance_tipo":       "marcas" if alcance == "Marcas" else "lineas",
        }
        ok = save_caso_biblioteca(proveedor_id, caso)
        if ok:
            celebrate_save(
                f"'{caso['nombre_caso']}' guardado en biblioteca",
                modulo="Motor de Precios",
                contexto="guardado",
                balloons=False,
            )
            st.rerun()
        else:
            st.error("Error al guardar en biblioteca.")


# ── PASO 3 — Preview y cálculo ───────────────────────────────────────────────

def _paso_3_preview():
    _seccion("Paso 3 — Cálculo Automático")

    col_nav, _ = st.columns([1, 4])
    if col_nav.button("← Volver a Análisis"):
        st.session_state["re_paso"] = 2
        st.rerun()

    skus_resueltos = st.session_state.get("re_skus_resueltos", pd.DataFrame())
    proveedor_id   = st.session_state.get("re_proveedor_id")
    evento_id      = st.session_state.get("re_evento_id")
    df_evento      = st.session_state.get("re_df_evento", pd.DataFrame())
    if df_evento is None or df_evento.empty:
        df_evento = casos_evento_to_dataframe(st.session_state.get("re_casos_evento", []))

    if (skus_resueltos is None or skus_resueltos.empty or df_evento.empty) and evento_id and proveedor_id:
        re_skus = st.session_state.get("re_skus")
        casos_ev = st.session_state.get("re_casos_evento", [])
        if re_skus is not None and not re_skus.empty and casos_ev:
            from modules.rimec_engine.logic import preparar_evento_para_preview

            with proceso_largo(
                "Recuperando asignación",
                "Preparando SKUs tras aplicar biblioteca…",
            ) as avanzar:
                avanzar(0.5, "Resolviendo casos…")
                prep_ok, prep_msg, skus_r, df_ev, ready, conflictos = preparar_evento_para_preview(
                    evento_id, proveedor_id, re_skus, casos_evento=casos_ev
                )
                avanzar(1.0, "Listo")
            if prep_ok:
                st.session_state["re_skus_resueltos"] = skus_r
                st.session_state["re_df_evento"] = df_ev
                st.session_state["re_ready_to_calc"] = ready
                st.session_state["re_conflictos"] = conflictos
                st.rerun()
            st.error(prep_msg)
            if conflictos:
                st.dataframe(pd.DataFrame(conflictos), use_container_width=True)
            return

    if skus_resueltos is None or skus_resueltos.empty or df_evento.empty:
        st.error(
            "No hay SKUs resueltos o matriz del listado vacía. "
            "Volvé a **Biblioteca** y pulsá **Continuar a Preview** de nuevo."
        )
        return

    casos_bib = {row["nombre_caso"]: row.to_dict() for _, row in df_evento.iterrows()}

    if evento_id:
        res_bd = resumen_paso3_evento(evento_id)
        n_bd = int(res_bd.get("n_precio_lista") or 0)
        if n_bd > 0:
            st.success(
                f"**Cálculo ya guardado en base de datos:** {n_bd:,} filas en `precio_lista` "
                f"(estado evento: **{res_bd.get('estado') or '—'}**). "
                "Si el paso no avanzó solo tras muchos minutos en Streamlit Cloud, usá el botón de abajo."
            )
            if st.button(
                "➡ Continuar al Paso 4 — Validación",
                type="primary",
                key="motor_paso3_ir_paso4",
            ):
                pack = ir_a_paso4_validacion(evento_id)
                if pack:
                    st.session_state["re_casos"] = pack["casos"]
                    st.session_state["re_skus_por_caso"] = pack["confirmados"]
                    st.session_state["re_paso"] = 4
                    celebrate_step(
                        "Paso 3 (recuperado)",
                        f"{pack['total_skus']:,} precios ya en BD",
                        modulo="Motor de Precios",
                        handoff="Validación (Paso 4)",
                    )
                    st.rerun()
                else:
                    st.error("No se pudo reconstruir el resumen desde la base de datos.")

    st.markdown(f"Se procesarán **{len(skus_resueltos)}** SKUs de forma automatizada.")

    # OT-FINAL-001 Fase D: Insignia motor + UX
    if USE_CALCULO_SQL:
        st.info("⚡ **MOTOR ULTRA-RÁPIDO** (SQL en Postgres) — Rendimiento optimizado")
    else:
        st.warning("🐢 **MOTOR TRADICIONAL** (Python) — Considerar actualizar a SQL")

    # Warning anti-recarga
    st.warning("⚠️ **IMPORTANTE**: No recargar la pestaña durante el cálculo (puede causar inconsistencias en Cloud)")

    # Verificar si ya hay precios calculados
    n_bd = 0
    try:
        from core.database import get_dataframe
        df_count = get_dataframe(
            "SELECT COUNT(*) as n FROM precio_lista WHERE evento_id = :eid",
            {"eid": evento_id}
        )
        if df_count is not None and not df_count.empty:
            n_bd = int(df_count.iloc[0]["n"])
    except:
        pass

    calc_ok = False
    total_guardados = 0

    # Si ya hay precios, destacar Paso 4
    if n_bd > 0:
        st.success(f"✓ Ya existen **{n_bd}** precios calculados para este evento")
        st.markdown("### 👉 Continuar al Paso 4")
        with st.expander("⚙️ Recalcular (sobrescribirá precios existentes)", expanded=False):
            if st.button("🔄 Recalcular todos los SKUs", type="secondary"):
                pass  # El código del cálculo va aquí abajo
            else:
                return
    else:
        if not st.button("✅ Iniciar Cálculo de todos los SKUs", type="primary"):
            return

    # Bloque de cálculo (ejecuta siempre si llegó aquí)
    total_skus_btn = len(skus_resueltos)
    with proceso_largo(
            "Cálculo de precios",
            f"Procesando **{total_skus_btn}** SKUs (pilares + precio_lista).",
            aviso_espera=(
                "Pilares y caché van por códigos del listado (no todo el catálogo). "
                "Verás el avance **1/N, 2/N…** abajo. No recargues la pestaña."
            ),
        ) as avanzar:
            from core.database import engine
            from modules.rimec_engine.ley_genero import (
                validar_ley_genero_importacion,
                texto_ley_genero_resumen,
            )
            from modules.rimec_engine.logic import asegurar_contenedor_lineas_excel
            from modules.rimec_engine.lr_schema import mensaje_si_falta_migracion_042
            from modules.rimec_engine.pillar_fk import asegurar_pilares_para_listado

            # Fase 1: Validación políticas
            avanzar(0.02, "Fase 1/5: Validación de políticas comerciales…")
            t_db = time.perf_counter()
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                ms_db = int((time.perf_counter() - t_db) * 1000)
                avanzar(0.05, f"Fase 1/5: Conexión servidor validada ({ms_db} ms)")
            except Exception as exc:
                st.error(f"No se pudo conectar a Supabase: {exc}")
                return

            avanzar(0.08, "Fase 1/5: Preparando estructura de precios…")
            mig42 = mensaje_si_falta_migracion_042()
            if mig42:
                st.warning(mig42 + " El listado puede continuar; los códigos denormalizados en linea_referencia quedarán pendientes.")

            stats_pilar = asegurar_pilares_para_listado(
                proveedor_id, skus_resueltos, evento_id=evento_id
            )
            if stats_pilar.get("error_deadlock"):
                st.error(
                    "El pilar se está actualizando en otra operación (deadlock). "
                    "Cerrá otras pestañas de la app, esperá 5 s y pulsá de nuevo."
                )
                return
            n_auto_cont = asegurar_contenedor_lineas_excel(
                evento_id, proveedor_id, skus_resueltos, df_evento
            )
            if n_auto_cont:
                st.info(
                    f"Alta automática: **{n_auto_cont}** línea(s) agregadas al contenedor del listado."
                )
            if stats_pilar.get("lineas_alta_automatica"):
                st.info(
                    f"Pilar: **{stats_pilar['lineas_alta_automatica']}** línea(s) creadas "
                    f"por herencia desde línea inferior."
                )
            if stats_pilar.get("lineas_alta_errores"):
                st.warning(
                    "Algunas líneas no se pudieron crear en pilar: "
                    + "; ".join(stats_pilar["lineas_alta_errores"][:4])
                )

            marcas_imp = skus_resueltos["marca"].dropna().unique().tolist()
            ley = validar_ley_genero_importacion(marcas_imp)
            if not ley["ok"]:
                st.error("**Ley de género:** importación bloqueada.")
                if ley["marcas_rechazadas"]:
                    st.error("Marcas no permitidas: " + ", ".join(ley["marcas_rechazadas"]))
                if ley["generos_faltantes_bd"]:
                    st.error("Géneros faltantes en BD: " + ", ".join(ley["generos_faltantes_bd"]))
                st.markdown(texto_ley_genero_resumen())
                return

            if stats_pilar.get("ley_genero_rechazadas") or stats_pilar.get("genero_bd_faltante"):
                st.warning(
                    "Ley de género (algunas filas del Excel): "
                    + ", ".join(stats_pilar.get("ley_genero_rechazadas", []))
                    + " ".join(stats_pilar.get("genero_bd_faltante", []))
                    + " — se intentó alta por herencia de línea inferior."
                )
            if stats_pilar.get("marcas_no_encontradas"):
                st.error(
                    "Marcas sin FK en **marca_v2** (nombre de hoja Excel): "
                    + ", ".join(stats_pilar["marcas_no_encontradas"])
                    + ". Corregí el catálogo o el nombre de la hoja antes de continuar."
                )
                return
            if stats_pilar.get("lineas_marca_conflicto"):
                st.error(
                    "La misma línea aparece en hojas con marcas distintas: "
                    + ", ".join(str(x) for x in stats_pilar["lineas_marca_conflicto"][:20])
                )
                return

            # Fase 2: Sincronización catálogo
            # OT-FINAL-001: Resolver pilares SQL si está activo y disponible
            if USE_CALCULO_SQL:
                avanzar(0.12, f"Fase 2/5: Sincronización de catálogo ({total_skus_btn} SKUs)…")
                cache = resolver_pilares_evento_sql(proveedor_id, skus_resueltos)

                if cache is None:
                    # Fallback a método tradicional si SQL falla
                    st.warning("[WARN] SQL pilares no disponible, usando método tradicional")
                    avanzar(0.12, f"Fase 2/5: Sincronización catálogo (modo tradicional)…")
                    cache = build_pillar_cache(proveedor_id, skus_resueltos)
                    avanzar(0.14, "Fase 2/5: Verificación de materiales…")
                    prefetch_materiales_para_listado(cache, proveedor_id, skus_resueltos)
            else:
                # Método tradicional (hotfix 522)
                avanzar(0.12, f"Fase 2/5: Sincronización catálogo ({total_skus_btn} SKUs)…")
                cache = build_pillar_cache(proveedor_id, skus_resueltos)
                avanzar(0.14, "Fase 2/5: Verificación de materiales…")
                prefetch_materiales_para_listado(cache, proveedor_id, skus_resueltos)

            grupos = skus_resueltos.groupby("caso_asignado")

            casos_procesados = []
            skus_omitidos_total = 0
            confirmados = {}

            total_skus = len(skus_resueltos)
            skus_procesados = 0
            pct_base = 0.15
            pct_span = 0.80

            n_grupos = max(len(grupos), 1)
            for i, (nombre_caso, skus_grupo) in enumerate(grupos):
                avanzar(
                    0.15 + (i / n_grupos) * 0.02,
                    f"Fase 3/5: Configurando caso «{nombre_caso}» ({len(skus_grupo)} SKUs)…",
                )
                print(f"[ENGINE] Iniciando cálculo de caso: '{nombre_caso}' ({len(skus_grupo)} SKUs)")
                if nombre_caso not in casos_bib:
                    st.error(f"Error crítico: Caso '{nombre_caso}' no está en la matriz del listado.")
                    continue
                
                caso_params = casos_bib[nombre_caso]
                marcas_ev = parse_marcas_array(caso_params.get("marcas"))
                lineas_ev = parse_lineas_array(caso_params.get("lineas"))
                caso_db = {
                    "nombre_caso":        caso_params["nombre_caso"],
                    "dolar_politica":     _to_float(caso_params.get("dolar_politica")) or 8000.0,
                    "factor_conversion":  _to_float(caso_params.get("factor_conversion")) or 180.0,
                    "descuento_1":        _to_float(caso_params.get("descuento_1")),
                    "descuento_2":        _to_float(caso_params.get("descuento_2")),
                    "descuento_3":        _to_float(caso_params.get("descuento_3")),
                    "descuento_4":        _to_float(caso_params.get("descuento_4")),
                    "genera_lpc03_lpc04": bool(caso_params.get("genera_lpc03_lpc04", True)),
                    "regla_redondeo":     "centena",
                    "marcas":             marcas_ev if marcas_ev else None,
                    "lineas":             lineas_ev,
                    "referencias":        [],
                    "alcance_tipo":       str(caso_params.get("alcance_tipo") or "marcas"),
                }

                caso_db_id = caso_params.get("caso_db_id")
                if caso_db_id is not None and not (
                    isinstance(caso_db_id, float) and pd.isna(caso_db_id)
                ):
                    caso_id = int(caso_db_id)
                    if not actualizar_caso_evento(caso_id, caso_db):
                        st.error(f"Fallo al actualizar caso {nombre_caso}.")
                        continue
                else:
                    caso_id = crear_caso(evento_id, caso_db)
                    if not caso_id:
                        st.error(f"Fallo al guardar configuración del caso {nombre_caso}.")
                        continue

                if lineas_ev:
                    n_exc = reemplazar_lineas_excepcion(
                        caso_id, lineas_ev, proveedor_id, evento_id
                    )
                    print(f"[ENGINE] Contenedor línea→caso '{nombre_caso}': {n_exc} filas")

                casos_procesados.append(caso_db)
                
                dolar_ap  = float(caso_db["dolar_politica"])
                factor_ap = float(caso_db["factor_conversion"])
                indice_ap = (dolar_ap * factor_ap) / 100

                filas = []
                skus_omitidos = 0

                # OT-520: Resolver pilares FK (obligatorio para ambos métodos)
                for _, row in skus_grupo.iterrows():
                    skus_procesados += 1
                    pct = pct_base + (skus_procesados / total_skus) * pct_span
                    avanzar(
                        pct,
                        f"Fase 3/5: Cálculo SKU {skus_procesados}/{total_skus} — caso {nombre_caso}",
                    )

                    fob  = float(row["fob_fabrica"])

                    try:
                        cod_linea = int(float(str(row.get("linea", 0)).strip() or 0))
                        cod_ref   = int(float(str(row["referencia"]).strip()))
                        cod_mat   = int(float(str(row.get("material", 0)).strip() or 0))
                    except (ValueError, TypeError):
                        cod_linea = cod_ref = cod_mat = 0

                    descp = str(row.get("descripcion", "")).strip()

                    if not cod_linea or not cod_ref or not cod_mat:
                        skus_omitidos += 1
                        continue

                    linea_id = get_or_create_linea_cached(cache, proveedor_id, cod_linea)
                    ref_id   = get_or_create_referencia_cached(cache, proveedor_id, linea_id, cod_ref) if linea_id else None
                    mat_id   = get_or_create_material_cached(cache, proveedor_id, cod_mat, descp)

                    if not linea_id or not ref_id or not mat_id:
                        skus_omitidos += 1
                        continue

                    # Preparar fila base con pilares FK
                    fila_base = {
                        "eid":      evento_id,
                        "cid":      caso_id,
                        "marca":    str(row["marca"]),
                        "lc":       str(cod_linea),
                        "rc":       str(cod_ref),
                        "md":       descp or str(cod_mat),
                        "linea_id_fk": linea_id,
                        "ref_id_fk":   ref_id,
                        "mat_id_fk":   mat_id,
                        "fob":   fob,
                    }

                    if USE_CALCULO_SQL:
                        # SQL masivo: solo guardar pilares + fob
                        filas.append(fila_base)
                    else:
                        # Python fila a fila: calcular precio por SKU
                        calc = calcular_precios_caso(fob, caso_db)
                        filas.append({
                            **fila_base,
                            "foba":  calc["fob_ajustado"],
                            "lpn":   calc["lpn"],
                            "lpc03": calc["lpc03"],
                            "lpc04": calc["lpc04"],
                            "dolar_ap":      dolar_ap,
                            "factor_ap":     factor_ap,
                            "indice_ap":     round(indice_ap, 6),
                            "d1_ap":         caso_db.get("descuento_1"),
                            "d2_ap":         caso_db.get("descuento_2"),
                            "d3_ap":         caso_db.get("descuento_3"),
                            "d4_ap":         caso_db.get("descuento_4"),
                            "nombre_caso_ap": caso_db["nombre_caso"],
                        })

                # Guardar en BD
                if USE_CALCULO_SQL:
                    # OT-520: Cálculo SQL masivo
                    avanzar(
                        min(0.98, pct_base + (skus_procesados / total_skus) * pct_span + 0.01),
                        f"Fase 4/5: Resguardo servidor — cargando {len(filas)} SKUs (caso {nombre_caso})",
                    )
                    cargar_staging_precio_lista(filas)
                else:
                    # Python: INSERT tradicional
                    avanzar(
                        min(0.98, pct_base + (skus_procesados / total_skus) * pct_span + 0.01),
                        f"Fase 4/5: Resguardo servidor — guardando {len(filas)} precios (caso {nombre_caso})",
                    )
                    guardar_precio_lista(filas)
                skus_omitidos_total += skus_omitidos
                confirmados[f"caso_{i}"] = len(filas)
                print(
                    f"[ENGINE] Completado caso '{nombre_caso}' "
                    f"({len(skus_grupo)} SKUs, {len(filas)} guardados)."
                )

            # OT-520: Si usamos SQL, ejecutar cálculo masivo al final
            if USE_CALCULO_SQL:
                total_staging = sum(confirmados.values()) if confirmados else 0
                if total_staging > 0:
                    avanzar(0.98, f"Fase 4/5: Ejecución cálculo masivo en servidor ({total_staging} SKUs)…")
                    resultado_sql = calcular_precio_lista_sql(evento_id)

                    if resultado_sql.get("error"):
                        st.error(f"❌ Cálculo SQL falló: {resultado_sql['error']}")
                        st.warning("⚠️ Intentando fallback Python…")
                        # TODO: Implementar fallback si es crítico
                        calc_ok = False
                    else:
                        duracion_s = resultado_sql["duracion_ms"] / 1000
                        st.success(
                            f"✅ Cálculo SQL completado: {resultado_sql['total']} precios en {duracion_s:.1f}s"
                        )
                        # Actualizar confirmados con total real desde SQL
                        total_guardados = resultado_sql['total']
                        calc_ok = True

                    # Limpiar staging
                    limpiar_staging_precio_lista(evento_id)
                else:
                    calc_ok = False
            else:
                # Python: ya guardado en el loop
                total_guardados = sum(confirmados.values()) if confirmados else 0
                calc_ok = total_guardados > 0

            if stats_pilar.get("ley_genero_lineas"):
                st.info(
                    f"Ley de género: **{stats_pilar['ley_genero_lineas']}** líneas con "
                    f"`genero_id` FK en el pilar."
                )

            if skus_omitidos_total:
                st.warning(f"⚠️ {skus_omitidos_total} SKU(s) omitidos por pilares nulos. Revisar Excel.")

        if calc_ok:
            avanzar(0.99, f"Fase 5/5: Consolidación — finalizando {total_guardados:,} precios calculados…")
            st.session_state["re_casos"] = casos_procesados
            st.session_state["re_skus_por_caso"] = confirmados
            avanzar_estado_evento(evento_id, "validado")
            st.session_state["re_paso"] = 4
            st.session_state["re_paso3_evento_listo"] = evento_id
            celebrate_step(
                "Paso 3",
                f"{total_guardados:,} precios guardados en precio_lista",
                modulo="Motor de Precios",
                handoff="Validación (Paso 4)",
            )
            st.rerun()
        elif evento_id and contar_skus_procesados(evento_id) > 0:
            st.warning(
                "El cálculo parece haber guardado datos en BD pero no se pudo cerrar el paso. "
                "Usá **Continuar al Paso 4** arriba."
            )


# ── PASO 4 — Validación final ────────────────────────────────────────────────

def _paso_4_validacion():
    _seccion("Paso 4 — Validación final")

    evento_id      = st.session_state.get("re_evento_id")
    nombre_evento  = st.session_state.get("re_nombre_evento", f"Evento #{evento_id}")
    casos          = st.session_state.get("re_casos", [])
    if evento_id and not casos:
        pack = hidratar_paso4_desde_bd(evento_id)
        if pack.get("casos"):
            st.session_state["re_casos"] = pack["casos"]
            st.session_state["re_skus_por_caso"] = pack["confirmados"]
            casos = pack["casos"]

    # ── Encabezado del evento (lista de precios) ──────────────────────────────
    st.markdown(
        f"""<div style="background:#1e293b;border-left:4px solid #D4AF37;
                        padding:14px 20px;border-radius:6px;margin-bottom:16px;">
            <div style="color:#94a3b8;font-size:0.72rem;text-transform:uppercase;
                        letter-spacing:.08em;">Lista de Precios</div>
            <div style="color:#f1f5f9;font-size:1.15rem;font-weight:700;margin-top:2px;">
                {nombre_evento}
            </div>
            <div style="color:#64748b;font-size:0.78rem;margin-top:4px;">
                {len(casos)} caso(s): {' · '.join(c['nombre_caso'] for c in casos)}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    from core.database import get_dataframe

    # ── Estado de confirmación por caso (fuente de verdad) ────────────────────
    confirmados  = st.session_state.get("re_skus_por_caso", {})
    total_casos  = len(casos)
    casos_ok     = sum(1 for i in range(total_casos) if f"caso_{i}" in confirmados)
    todos_ok     = casos_ok == total_casos and total_casos > 0

    # ── Barra de progreso: casos confirmados ──────────────────────────────────
    st.progress(
        casos_ok / total_casos if total_casos else 0,
        text=f"{casos_ok} de {total_casos} casos calculados "
             f"({'✅ listo para validar' if todos_ok else 'pendiente'})",
    )

    # ── Tabla resumen por caso ────────────────────────────────────────────────
    total_skus_global = sum(v for v in confirmados.values() if isinstance(v, int))
    resumen_rows = []
    for i, caso in enumerate(casos):
        clave  = f"caso_{i}"
        n_skus = confirmados.get(clave)
        idx    = (caso["dolar_politica"] * caso["factor_conversion"]) / 100
        resumen_rows.append({
            "Estado":    "✅ Calculado" if n_skus is not None else "⏳ Pendiente",
            "Caso":      caso["nombre_caso"].replace("*", "").strip(),
            "Índice":    int(idx),
            "SKUs":      n_skus if n_skus is not None else 0,
            "% del total": (
                round(n_skus / total_skus_global * 100, 1)
                if n_skus and total_skus_global else 0.0
            ),
        })
    st.dataframe(
        pd.DataFrame(resumen_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "SKUs":        st.column_config.NumberColumn(format="%d"),
            "% del total": st.column_config.NumberColumn(format="%.1f %%"),
            "Índice":      st.column_config.NumberColumn(format="%d"),
        },
    )

    st.markdown("---")

    # ── Tabla de resultados agrupada por caso ─────────────────────────────────
    df_resultado = get_dataframe(
        """SELECT pec.nombre_caso AS "Caso",
                  pl.marca        AS "Marca",
                  COALESCE(l.codigo_proveedor::text, pl.linea_codigo)      AS "Línea",
                  COALESCE(r.codigo_proveedor::text, pl.referencia_codigo) AS "Referencia",
                  COALESCE(m.descripcion, pl.material_descripcion)         AS "Material",
                  pl.fob_fabrica  AS "FOB",
                  pl.fob_ajustado AS "FOB Ajustado",
                  pl.lpn          AS "LPN",
                  pl.lpc03        AS "LPC03",
                  pl.lpc04        AS "LPC04"
           FROM precio_lista pl
           JOIN precio_evento_caso pec ON pec.id = pl.caso_id
           LEFT JOIN linea     l ON l.id  = pl.linea_id
           LEFT JOIN referencia r ON r.id = pl.referencia_id
           LEFT JOIN material   m ON m.id = pl.material_id
           WHERE pl.evento_id = :eid
           ORDER BY pec.nombre_caso, pl.marca,
                    COALESCE(l.codigo_proveedor, 0),
                    COALESCE(r.codigo_proveedor, 0)""",
        {"eid": evento_id},
    )

    if df_resultado is not None and not df_resultado.empty:
        st.dataframe(df_resultado, use_container_width=True, hide_index=True, height=420)

    col_val, col_volver = st.columns([2, 1])
    if col_volver.button("← Volver a Preview"):
        st.session_state["re_paso"] = 3
        st.rerun()

    if not todos_ok:
        st.warning(
            f"⚠️ Faltan {total_casos - casos_ok} caso(s) por confirmar. "
            "Volvé al Paso 3 y confirmá todos los casos."
        )
    else:
        celebrate_step(
            "Paso 4",
            f"Todos los casos calculados ({casos_ok} casos). Listo para el Director.",
            modulo="Motor de Precios",
        )
        if col_val.button("✅ Validar evento", type="primary"):
            st.session_state["re_paso"] = 5
            st.rerun()


# ── PASO 5 — Cierre ──────────────────────────────────────────────────────────

def _paso_5_cierre():
    _seccion("Paso 5 — Cierre y activación")

    evento_id = st.session_state.get("re_evento_id")

    st.warning(
        "⚠️ Al cerrar este evento:\n"
        "- Los precios vigentes anteriores se desactivan\n"
        "- Los precios de este evento quedan activos\n"
        "- El evento queda en estado **CERRADO** — inalterable\n\n"
        "Esta acción no se puede deshacer."
    )

    justificacion = st.text_area(
        "Observaciones del Director (opcional)",
        placeholder="Ej: Precios ajustados por nueva temporada de invierno 2026"
    )

    sync_pilares = st.checkbox(
        "Re-sincronizar pilares al cerrar (lento en Streamlit Cloud; "
        "dejar desmarcado si ya calculaste en Paso 3)",
        value=False,
        key="re_cerrar_sync_pilar",
    )

    if st.button("🔒 Cerrar y activar precios", type="primary"):
        with proceso_largo(
            "Cierre del listado",
            "Activando precios vigentes y marcando evento CERRADO.",
            aviso_espera="El cierre SQL suele tardar unos segundos. No recargues la pestaña.",
        ) as avanzar:
            from modules.rimec_engine.logic import (
                cerrar_evento_sql,
                sincronizar_marca_linea_desde_evento,
            )

            avanzar(0.15, "Desactivando listados anteriores…")
            avanzar(0.35, "Activando precios de este evento…")
            cerrar_evento_sql(evento_id, str(date.today()))
            avanzar(0.55, "Evento marcado CERRADO en base de datos…")

            n_m = 0
            if sync_pilares:
                avanzar(0.65, "Sincronizando pilares (puede tardar varios minutos)…")
                n_m = sincronizar_marca_linea_desde_evento(evento_id)
            else:
                avanzar(0.85, "Pilares: sin re-sync (ya provisionados en Paso 3)")
            avanzar(1.0, "Cierre completado")

        if justificacion:
            registrar_auditoria(
                evento_id, "precio_evento", "estado",
                "validado", "cerrado", justificacion
            )
        extra = f" Pilares FK: {n_m} pares línea+referencia." if n_m else ""
        celebrate_save(
            f"Evento cerrado. Los nuevos precios están activos.{extra}",
            modulo="Motor de Precios",
            contexto="evento_cerrado",
            toast=True,
            balloons=True,
        )
        st.session_state["re_paso"] = 0
        _reset_flujo()
        st.rerun()

    if st.button("← Volver a revisar"):
        st.session_state["re_paso"] = 4
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HISTORIAL
# ─────────────────────────────────────────────────────────────────────────────

def _ui_eliminar_listado(eid: int, nombre: str, key_prefix: str) -> None:
    """Confirmación simple: escribir ELIMINAR + botón."""
    st.markdown("**¿Eliminar este listado?** (error humano, volver a cargar el Excel)")
    confirm = st.text_input(
        f'Escribí **ELIMINAR** para borrar «{nombre}»',
        key=f"{key_prefix}_confirm_{eid}",
        placeholder="ELIMINAR",
    )
    if st.button(
        "🗑️ Eliminar listado definitivamente",
        key=f"{key_prefix}_btn_{eid}",
        type="primary",
        disabled=(confirm.strip().upper() != "ELIMINAR"),
    ):
        ok, msg = eliminar_evento(eid)
        if ok:
            celebrate_save(msg, modulo="Motor de Precios", contexto="guardado", balloons=False)
            st.session_state.pop(f"{key_prefix}_confirm_del_{eid}", None)
            st.rerun()
        else:
            st.error(msg)


def _render_historial():
    _seccion("Historial de Listas de Precios")
    st.info(
        "**Si te equivocaste:**\n"
        "- **Listado mal cargado o cerrado por error** → expandí el listado abajo → escribí `ELIMINAR` → "
        "Eliminar listado → volvé a **Nuevo Evento**.\n"
        "- **Casos / líneas mal definidos** (antes de cerrar) → abrí el flujo del listado en borrador "
        "o eliminá el listado y repetí **Paso 2** (matriz de casos de ese listado).\n"
        "- La pestaña **Casos (legacy)** ya no define precios; cada listado lleva su propia matriz."
    )

    from core.database import get_dataframe

    df = get_todos_eventos()
    if df is None or df.empty:
        st.info("No hay listas de precios registradas aún.")
        return

    col_busq, _ = st.columns([2, 3])
    busqueda = col_busq.text_input("🔍 Buscar", placeholder="INVIERNO, cerrado...")
    if busqueda:
        mask = df.apply(
            lambda r: busqueda.lower() in str(r["nombre_evento"]).lower()
                      or busqueda.lower() in str(r["estado"]).lower(),
            axis=1,
        )
        df = df[mask]

    _ESTADO_ICON = {
        "cerrado":  "🟢",
        "en_uso":   "🔒",
        "validado": "🔵",
        "borrador": "⚪",
    }

    for _, ev in df.iterrows():
        eid         = int(ev["id"])
        estado_real = get_estado_real_evento(eid, ev["estado"])
        icon        = _ESTADO_ICON.get(estado_real, "⚪")

        label = (
            f"{icon} **{ev['nombre_evento']}** "
            f"— {estado_real.upper()} "
            f"— {int(ev['total_skus']):,} SKUs "
            f"— vigente desde {str(ev['fecha_vigencia_desde'])[:10]}"
        )
        with st.expander(label):
            # ── Cabecera del evento ─────────────────────────────────────────
            borde = {"cerrado": "#059669", "en_uso": "#D97706",
                     "validado": "#0284C7", "borrador": "#475569"}.get(estado_real, "#475569")
            st.markdown(
                f"""<div style="background:#1e293b;border-left:4px solid {borde};
                                padding:12px 18px;border-radius:6px;margin-bottom:12px;">
                    <div style="color:#94a3b8;font-size:0.7rem;text-transform:uppercase;">
                        Lista de Precios &nbsp;·&nbsp; {estado_real.upper()}</div>
                    <div style="color:#f1f5f9;font-size:1.05rem;font-weight:700;">
                        {ev['nombre_evento']}</div>
                    <div style="color:#64748b;font-size:0.75rem;margin-top:2px;">
                        Archivo: {ev['nombre_archivo']} &nbsp;·&nbsp;
                        Creado: {str(ev['created_at'])[:16]}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

            # ── Candado — mensaje de bloqueo ────────────────────────────────
            if estado_real == "en_uso":
                uso = evento_esta_en_uso(eid)
                st.warning("🔒 **Vinculado a Compras** (abajo podés eliminar el listado; se desvincula solo).")
                for mod in uso["modulos"]:
                    st.markdown(f"&nbsp;&nbsp;· {mod}")

            # ── Casos del evento ────────────────────────────────────────────
            df_casos = get_casos_evento(eid)
            if not df_casos.empty:
                st.markdown("**Casos de esta lista:**")
                for _, caso in df_casos.iterrows():
                    idx = (caso['dolar_politica'] * caso['factor_conversion']) / 100
                    st.markdown(
                        f"&nbsp;&nbsp;• **{caso['nombre_caso']}** — "
                        f"Gs {int(caso['dolar_politica']):,} × {int(caso['factor_conversion'])} / 100 "
                        f"= índice **{idx:,.0f}**"
                    )

            # ── Acciones ────────────────────────────────────────────────────
            if estado_real == "cerrado":
                zip_key = f"_zip_cache_{eid}"
                col_gen, col_dl = st.columns([1, 1])

                if col_gen.button("📦 Generar PDFs (ZIP)", key=f"zip_{eid}", type="primary"):
                    with st.spinner("Generando PDFs..."):
                        st.session_state[zip_key] = generar_zip_pdfs_evento(eid).getvalue()
                    st.rerun()

                if zip_key in st.session_state:
                    col_dl.download_button(
                        "⬇️ Descargar ZIP",
                        data=st.session_state[zip_key],
                        file_name=f"{ev['nombre_evento']}_precios.zip",
                        mime="application/zip",
                        key=f"dl_zip_{eid}",
                    )

                st.divider()
                if st.session_state.get(f"hist_confirm_del_{eid}"):
                    _ui_eliminar_listado(eid, ev["nombre_evento"], "hist")
                elif st.button(
                    "🗑️ Eliminar este listado…",
                    key=f"del_cerrado_{eid}",
                    help="Si cerraste por error: se borra el listado; las IC quedan sin precio_evento.",
                ):
                    st.session_state[f"hist_confirm_del_{eid}"] = True
                    st.rerun()

            elif estado_real == "en_uso":
                uso = evento_esta_en_uso(eid)
                st.warning(
                    "Este listado está vinculado a Compras. Al **eliminar**, se desvincula "
                    "automáticamente de las IC (podés asignar otro listado después)."
                )
                for mod in uso["modulos"]:
                    st.markdown(f"&nbsp;&nbsp;· {mod}")
                if st.session_state.get(f"hist_confirm_del_{eid}"):
                    _ui_eliminar_listado(eid, ev["nombre_evento"], "hist")
                elif st.button("🗑️ Eliminar este listado…", key=f"hist_try_del_{eid}"):
                    st.session_state[f"hist_confirm_del_{eid}"] = True
                    st.rerun()

            else:
                if st.session_state.get(f"hist_confirm_del_{eid}"):
                    _ui_eliminar_listado(eid, ev["nombre_evento"], "hist")
                elif st.button(
                    "🗑️ Eliminar este listado…",
                    key=f"del_ev_{eid}",
                    help="Borra precios, casos del evento y excepciones. No toca pilares.",
                ):
                    st.session_state[f"hist_confirm_del_{eid}"] = True
                    st.rerun()

            # ── Tabla de precios (solo eventos con precios calculados) ──────
            if ev["estado"] in ("cerrado", "validado"):
                df_det = get_dataframe(
                    """SELECT pec.nombre_caso AS "Caso",
                              pl.marca        AS "Marca",
                              COALESCE(l.codigo_proveedor::text, pl.linea_codigo)      AS "Línea",
                              COALESCE(r.codigo_proveedor::text, pl.referencia_codigo) AS "Referencia",
                              COALESCE(m.descripcion, pl.material_descripcion)         AS "Material",
                              pl.fob_fabrica AS "FOB",
                              pl.lpn  AS "LPN",
                              pl.lpc03 AS "LPC03",
                              pl.lpc04 AS "LPC04",
                              pl.vigente AS "Vigente"
                       FROM precio_lista pl
                       JOIN precio_evento_caso pec ON pec.id = pl.caso_id
                       LEFT JOIN linea     l ON l.id  = pl.linea_id
                       LEFT JOIN referencia r ON r.id = pl.referencia_id
                       LEFT JOIN material   m ON m.id = pl.material_id
                       WHERE pl.evento_id = :eid
                       ORDER BY pec.nombre_caso, pl.marca, pl.linea_codigo, pl.referencia_codigo""",
                    {"eid": eid},
                )
                if df_det is not None and not df_det.empty:
                    st.dataframe(df_det, use_container_width=True, hide_index=True, height=300)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN LÍNEAS — maestro Línea + Marca + Caso + Clasificación
# ─────────────────────────────────────────────────────────────────────────────

def _render_import_pilares_excel(proveedor_id: int) -> None:
    """Import masivo linea + linea_referencia (más líneas = mejores filtros web)."""
    import tempfile
    from pathlib import Path

    from scripts.import_pilares_linea_lr_excel import run_import_pilares

    with st.expander("📥 Importar pilares desde Excel (linea + linea_referencia)", expanded=False):
        st.markdown(
            "Subí **linea.xlsx** y **linea_referencia.xlsx**. No se escribe `linea.caso_id`. "
            "**Estilo / Tipo 1** quedan en `linea_referencia` (línea + referencia)."
        )
        st.caption(
            "Más líneas en el pilar → filtros de cabecera del catálogo web más completos."
        )
        c1, c2 = st.columns(2)
        f_linea = c1.file_uploader("linea.xlsx", type=["xlsx", "xls"], key="imp_pilar_linea")
        f_lr = c2.file_uploader(
            "linea_referencia.xlsx", type=["xlsx", "xls"], key="imp_pilar_lr"
        )
        prev = st.checkbox("Solo vista previa (dry-run)", key="imp_pilar_dry")
        if st.button("Ejecutar import de pilares", type="primary", key="imp_pilar_btn"):
            if f_linea is None or f_lr is None:
                st.warning("Subí ambos archivos.")
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    p_linea = Path(tmp) / "linea.xlsx"
                    p_lr = Path(tmp) / "linea_referencia.xlsx"
                    p_linea.write_bytes(f_linea.getvalue())
                    p_lr.write_bytes(f_lr.getvalue())
                    log_box = st.empty()
                    lines: list[str] = []

                    def _log(msg: str = "") -> None:
                        if msg:
                            lines.append(str(msg))
                        log_box.code("\n".join(lines[-40:]) or "…")

                    try:
                        with st.spinner("Importando pilares…"):
                            out = run_import_pilares(
                                p_linea,
                                p_lr,
                                int(proveedor_id),
                                dry_run=prev,
                                log=_log,
                            )
                        if out.get("dry_run"):
                            st.info(
                                f"Vista previa: {out.get('linea_filas', 0):,} filas linea · "
                                f"{out.get('lr_filas', 0):,} L+R."
                            )
                        else:
                            st.success(
                                f"**{out.get('lineas', 0):,}** líneas · "
                                f"**{out.get('lr', 0):,}** pares linea_referencia."
                            )
                    except Exception as e:
                        st.error(f"Import falló: {e}")


def _render_admin_lineas():
    from core.database import get_dataframe
    from modules.intencion_compra.logic import (
        get_lineas_filtradas, get_valores_filtro_lineas,
        update_linea_clasificacion, get_proveedores,
    )

    _seccion("Administración de Líneas", "Pilar catálogo — FK desde listado y maestras")
    st.caption(
        "**Marca / Género:** en `linea` (marca_id, genero_id). "
        "**Estilo / Tipo 1:** en `linea_referencia` (por línea + referencia) — alimenta filtros del catálogo web. "
        "**Caso comercial:** en listado/biblioteca (`precio_evento_caso`), **no** en `linea.caso_id`."
    )

    df_prov = get_proveedores()
    if df_prov is None or df_prov.empty:
        st.info("No hay proveedores registrados.")
        return

    opts_prov = {r["nombre"]: int(r["id"]) for _, r in df_prov.iterrows()}
    prov_label = st.selectbox("Proveedor", list(opts_prov.keys()), key="al_prov")
    prov_id    = opts_prov[prov_label]

    _render_import_pilares_excel(prov_id)

    # ── Barra de filtros ──────────────────────────────────────────────────────
    _NULL = "— Vacío —"
    marcas_vals = ["Todas"] + get_valores_filtro_lineas(prov_id, "marca")
    genero_vals  = ["Todos", _NULL] + get_valores_filtro_lineas(prov_id, "descp_genero")

    fc1, fc2 = st.columns(2)
    f_marca  = fc1.selectbox("Marca",  marcas_vals, key="al_f_marca")
    f_genero = fc2.selectbox("Género", genero_vals, key="al_f_gen")

    df_lineas = get_lineas_filtradas(
        prov_id,
        marca  = None if f_marca  == "Todas" else f_marca,
        genero = None if f_genero == "Todos" else f_genero,
    )

    if df_lineas is None or df_lineas.empty:
        st.info("No hay líneas activas para este proveedor con los filtros seleccionados.")
        return

    ult_cerrado = get_ultimo_evento_cerrado()
    if ult_cerrado and int(ult_cerrado.get("proveedor_id", 0)) == prov_id:
        with st.expander("Reaplicar FK de pilares desde listado cerrado", expanded=False):
            st.caption(
                f"Último listado: **{ult_cerrado.get('nombre_evento')}** — "
                "marca, **Ley de género → linea.genero_id**, L+R, estilo y tipo_1."
            )
            bc1, bc2 = st.columns(2)
            if bc1.button("Reaplicar FK pilares", key="al_sync_marca", type="primary"):
                from modules.rimec_engine.pillar_fk import provisionar_pilares_desde_evento

                stats = provisionar_pilares_desde_evento(int(ult_cerrado["id"]))
                if stats.get("marcas_no_encontradas"):
                    st.error(
                        "Sin FK en marca_v2: "
                        + ", ".join(stats["marcas_no_encontradas"])
                    )
                elif stats.get("ley_genero_rechazadas"):
                    st.error(
                        "Ley de género sin FK: "
                        + ", ".join(stats["ley_genero_rechazadas"])
                    )
                else:
                    celebrate_step(
                        "Pilares",
                        f"{stats.get('lr', 0)} pares L+R · "
                        f"{stats.get('ley_genero_lineas', 0)} líneas con genero_id",
                        modulo="Motor de Precios",
                    )
                st.rerun()
            if bc2.button("Solo Ley de género → linea", key="al_sync_genero"):
                from modules.rimec_engine.ley_genero import aplicar_ley_genero_desde_evento

                gen = aplicar_ley_genero_desde_evento(int(ult_cerrado["id"]))
                if gen.get("sin_fk"):
                    st.error("Sin FK genero: " + ", ".join(gen["sin_fk"]))
                else:
                    celebrate_save(
                        f"{gen.get('lineas', 0)} líneas con genero_id "
                        f"(de {gen.get('total', 0)} del listado)",
                        modulo="Motor de Precios",
                        contexto="guardado",
                        balloons=False,
                    )
                st.rerun()

    st.markdown(
        f"**{len(df_lineas)} líneas** &nbsp;·&nbsp; "
        "Marca = `marca_v2` vía FK. Solo **Género** se edita manualmente aquí.",
        unsafe_allow_html=True,
    )

    generos_maestro = get_generos()

    with st.expander("✏️ Editar Género por rango de código"):
        st.caption("Actualiza genero_id en el pilar linea para el rango indicado.")
        rc1, rc2 = st.columns(2)
        rango_desde = rc1.number_input("Línea inicial (código)", min_value=0, step=1,
                                       value=0, key="al_rango_desde")
        rango_hasta = rc2.number_input("Línea final (código)", min_value=0, step=1,
                                       value=0, key="al_rango_hasta")

        genero_opciones = ["— No cambiar —"] + generos_maestro
        genero_sel = st.selectbox("Género", genero_opciones, key="al_rango_genero")

        if st.button("Aplicar rango", type="primary", key="al_rango_btn"):
            if rango_desde > rango_hasta:
                st.error("Línea inicial debe ser ≤ Línea final.")
            elif genero_sel == "— No cambiar —":
                st.error("Seleccioná un género.")
            else:
                genero_val = None if genero_sel == "— No cambiar —" else genero_sel
                ok, n = actualizar_lineas_por_rango(
                    prov_id, int(rango_desde), int(rango_hasta), None, genero_val
                )
                if ok:
                    celebrate_save(
                        f"{n} líneas actualizadas (rango {rango_desde}–{rango_hasta})",
                        modulo="Motor de Precios",
                        contexto="guardado",
                        balloons=False,
                    )
                    st.rerun()
                else:
                    st.error("Error al aplicar el rango.")

    st.markdown("---")

    # ── Tabla editable fila por fila ──────────────────────────────────────────
    def _sv(x) -> str:
        return "" if pd.isna(x) or str(x) in ("None", "nan") else str(x)

    hc = st.columns([1, 2, 2, 1])
    for col, lbl in zip(hc, ["Línea", "Marca", "Género", ""]):
        col.markdown(f"**{lbl}**")
    st.markdown("---")

    df_gen_master = get_dataframe(
        "SELECT id, COALESCE(descripcion, codigo) AS nombre FROM genero "
        "WHERE activo = true ORDER BY id"
    )
    gen_map: dict[str, int] = {}
    if df_gen_master is not None and not df_gen_master.empty:
        gen_map = {str(r["nombre"]): int(r["id"]) for _, r in df_gen_master.iterrows()}
    generos_fila = [""] + list(gen_map.keys())

    for _, row in df_lineas.iterrows():
        linea_id = int(row["id"])
        cod      = int(row["codigo_proveedor"])
        gen_act  = _sv(row.get("descp_genero"))
        gen_idx  = generos_fila.index(gen_act) if gen_act in generos_fila else 0

        c0, c1, c2, c3 = st.columns([1, 2, 2, 1])
        c0.markdown(f"**{cod}**")
        c1.markdown(_sv(row.get("marca")) or "—")
        gen = c2.selectbox("Gén", generos_fila, index=gen_idx,
                           key=f"al_gen_{linea_id}", label_visibility="collapsed")

        if c3.button("💾", key=f"al_save_{linea_id}", help="Guardar fila"):
            nuevo_gen_id = gen_map.get(gen) if gen else None
            actual_gen_id = int(row.get("genero_id")) if row.get("genero_id") else None
            if nuevo_gen_id == actual_gen_id:
                st.info(f"Línea {cod}: sin cambios.")
                continue
            ok = update_linea_clasificacion(
                linea_id, genero_id=nuevo_gen_id, _campos={"genero_id"}
            )
            if ok:
                celebrate_save(
                    f"Línea {cod} guardada (género)",
                    modulo="Motor de Precios",
                    contexto="guardado",
                    balloons=False,
                )
                st.rerun()
            else:
                st.error(f"Error al guardar línea {cod}.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB: LÍNEA × REFERENCIA
# ─────────────────────────────────────────────────────────────────────────────

def _render_linea_referencia():
    from core.database import get_dataframe, engine
    from sqlalchemy import text as sqlt

    _seccion("Relación Línea × Referencia", "Estilo y Tipo pertenecen a la combinación, no a la línea sola")
    st.caption("Editá Estilo y Tipo 1 por lotes o fila a fila. Usá los filtros para acotar — se muestran máximo 200 filas.")

    # ── Filtros ───────────────────────────────────────────────────────────────
    df_marcas = get_dataframe("""
        SELECT DISTINCT mv.descp_marca AS marca
        FROM linea l
        JOIN marca_v2 mv ON mv.id_marca = l.marca_id
        WHERE l.proveedor_id = 654 AND l.activo = true
          AND mv.descp_marca IS NOT NULL
        ORDER BY marca
    """)
    marcas = ["Todas"] + (df_marcas["marca"].tolist() if df_marcas is not None and not df_marcas.empty else [])

    df_estilos = get_dataframe("""
        SELECT id_grupo_estilo, descp_grupo_estilo FROM grupo_estilo_v2 ORDER BY descp_grupo_estilo
    """)
    estilo_opts = {"Todos": None, "— Sin estilo —": -1}
    if df_estilos is not None and not df_estilos.empty:
        for _, row in df_estilos.iterrows():
            estilo_opts[row["descp_grupo_estilo"]] = int(row["id_grupo_estilo"])

    df_tipos = get_dataframe("SELECT id_tipo_1, descp_tipo_1 FROM tipo_1 ORDER BY id_tipo_1")
    tipo_opts = {"Todos": None, "— Sin tipo —": -1}
    if df_tipos is not None and not df_tipos.empty:
        for _, row in df_tipos.iterrows():
            tipo_opts[row["descp_tipo_1"]] = int(row["id_tipo_1"])

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_marca  = col1.selectbox("Marca",   marcas,              key="lr_marca")
    with col2:
        filtro_estilo = col2.selectbox("Estilo",  list(estilo_opts),   key="lr_estilo")
    with col3:
        filtro_tipo   = col3.selectbox("Tipo 1",  list(tipo_opts),     key="lr_tipo")

    # ── Query principal ───────────────────────────────────────────────────────
    conditions = ["lr.proveedor_id = 654"]
    params: dict = {}

    if filtro_marca != "Todas":
        conditions.append("mv.descp_marca = :marca")
        params["marca"] = filtro_marca

    ge_val = estilo_opts.get(filtro_estilo)
    if ge_val == -1:
        conditions.append("lr.grupo_estilo_id IS NULL")
    elif ge_val is not None:
        conditions.append("lr.grupo_estilo_id = :ge_id")
        params["ge_id"] = ge_val

    t1_val = tipo_opts.get(filtro_tipo)
    if t1_val == -1:
        conditions.append("lr.tipo_1_id IS NULL")
    elif t1_val is not None:
        conditions.append("lr.tipo_1_id = :t1_id")
        params["t1_id"] = t1_val

    where = " AND ".join(conditions)

    # Contar total sin LIMIT
    df_total = get_dataframe(f"""
        SELECT COUNT(*) AS total
        FROM linea_referencia lr
        JOIN linea      l  ON l.id  = lr.linea_id
        JOIN referencia r  ON r.id  = lr.referencia_id
        LEFT JOIN marca_v2  mv ON mv.id_marca = l.marca_id
        WHERE {where}
    """, params if params else None)
    total = int(df_total["total"].iloc[0]) if df_total is not None and not df_total.empty else 0

    df = get_dataframe(f"""
        SELECT
            lr.id,
            lr.proveedor_id,
            pi.codigo::text                 AS proveedor_cod,
            l.id                            AS linea_id,
            l.codigo_proveedor              AS linea_cod,
            r.codigo_proveedor              AS ref_cod,
            COALESCE(mv.descp_marca, '') AS marca,
            COALESCE(ge.descp_grupo_estilo, lr.descp_grupo_estilo) AS descp_grupo_estilo,
            COALESCE(t1.descp_tipo_1, lr.descp_tipo_1)             AS descp_tipo_1,
            lr.grupo_estilo_id,
            lr.tipo_1_id
        FROM linea_referencia lr
        JOIN linea      l  ON l.id  = lr.linea_id
        JOIN referencia r  ON r.id  = lr.referencia_id
        JOIN proveedor_importacion pi ON pi.id = lr.proveedor_id
        LEFT JOIN marca_v2  mv ON mv.id_marca = l.marca_id
        LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
        LEFT JOIN tipo_1          t1 ON t1.id_tipo_1       = lr.tipo_1_id
        WHERE {where}
        ORDER BY l.codigo_proveedor, r.codigo_proveedor
        LIMIT 200
    """, params if params else None)

    if df is None or df.empty:
        st.info("No hay combinaciones para los filtros seleccionados.")
        return

    filtros_activos = filtro_marca != "Todas" or filtro_estilo != "Todos"

    if total > 50 and not filtros_activos:
        st.info(f"**{total:,} combinaciones en total.** Aplicá un filtro de Marca o Estilo para editar fila a fila.")
        st.divider()
        # Vista rápida de solo lectura — sin widgets, carga instantánea
        st.dataframe(
            df[[
                "proveedor_id", "proveedor_cod", "linea_id", "linea_cod", "ref_cod",
                "marca", "descp_grupo_estilo", "descp_tipo_1",
            ]].rename(columns={
                "proveedor_id": "prov_id",
                "proveedor_cod": "Cód. prov.",
                "linea_id": "linea_id",
                "linea_cod": "Línea", "ref_cod": "Ref.", "marca": "Marca",
                "descp_grupo_estilo": "Estilo", "descp_tipo_1": "Tipo 1",
            }),
            use_container_width=True,
            hide_index=True,
        )
        return

    if total > 50:
        st.warning(f"Mostrando {len(df)} de {total:,} combinaciones.")
    else:
        st.caption(f"{total} combinaciones")
    st.divider()

    # ── Edición por lotes ─────────────────────────────────────────────────────
    with st.expander(f"✏️ Editar por lotes — {len(df)} combinaciones seleccionadas"):
        st.caption("Aplicar un valor a TODAS las filas del filtro actual.")
        lc1, lc2, lc3 = st.columns([2, 3, 1])
        campo_lote = lc1.selectbox("Campo", ["grupo_estilo_id", "tipo_1_id"],
                                   format_func=lambda x: {"grupo_estilo_id": "Estilo", "tipo_1_id": "Tipo 1"}[x],
                                   key="lr_lote_campo")
        if campo_lote == "grupo_estilo_id":
            opts_lote = {v: k for k, v in estilo_opts.items() if v and v > 0}
            lote_label = lc2.selectbox("Estilo", list(opts_lote), key="lr_lote_ge",
                                       format_func=lambda x: opts_lote[x])
            val_lote = lote_label
        else:
            opts_lote = {v: k for k, v in tipo_opts.items() if v and v > 0}
            lote_label = lc2.selectbox("Tipo 1", list(opts_lote), key="lr_lote_t1",
                                       format_func=lambda x: opts_lote[x])
            val_lote = lote_label

        lc3.markdown("<br>", unsafe_allow_html=True)
        if lc3.button("Aplicar", type="primary", key="lr_lote_btn"):
            ids = df["id"].astype(int).tolist()
            try:
                with engine.begin() as conn:
                    for i in range(0, len(ids), 100):
                        batch = ids[i:i + 100]
                        conn.execute(sqlt(
                            f"UPDATE linea_referencia SET {campo_lote} = :val WHERE id = ANY(:ids)"
                        ), {"val": int(val_lote), "ids": batch})
                celebrate_save(
                    f"{len(ids)} registros L+R actualizados",
                    modulo="Motor de Precios",
                    contexto="guardado",
                    balloons=False,
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    # ── Tabla fila por fila (solo cuando hay filtro activo) ───────────────────
    def _sv(x) -> str:
        return "" if pd.isna(x) or str(x) in ("None", "nan") else str(x)

    hcols = st.columns([1, 1, 2, 2, 2, 1])
    for col, lbl in zip(hcols, ["Línea", "Ref.", "Marca", "Estilo", "Tipo 1", ""]):
        col.markdown(f"**{lbl}**")
    st.markdown("---")

    # Mapas inversos para los selectbox de fila
    ge_inv = {v: k for k, v in estilo_opts.items() if v and v > 0}
    t1_inv = {v: k for k, v in tipo_opts.items()   if v and v > 0}
    ge_keys = list(ge_inv.keys())
    t1_keys = list(t1_inv.keys())

    for _, row in df.iterrows():
        lr_id   = int(row["id"])
        cur_ge  = row.get("grupo_estilo_id")
        cur_t1  = row.get("tipo_1_id")

        c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 2, 2, 2, 1])
        c1.write(int(row["linea_cod"]))
        c2.write(int(row["ref_cod"]))
        c3.write(_sv(row.get("marca")) or "—")

        ge_idx = ge_keys.index(int(cur_ge)) if cur_ge and int(cur_ge) in ge_keys else 0
        t1_idx = t1_keys.index(int(cur_t1)) if cur_t1 and int(cur_t1) in t1_keys else 0

        ge_nuevo = c4.selectbox("", ge_keys, index=ge_idx,
                                format_func=lambda x: ge_inv[x],
                                key=f"lr_ge_{lr_id}", label_visibility="collapsed")
        t1_nuevo = c5.selectbox("", t1_keys, index=t1_idx,
                                format_func=lambda x: t1_inv[x],
                                key=f"lr_t1_{lr_id}", label_visibility="collapsed")

        if c6.button("💾", key=f"lr_save_{lr_id}"):
            try:
                with engine.begin() as conn:
                    conn.execute(sqlt("""
                        UPDATE linea_referencia
                        SET grupo_estilo_id = :ge, tipo_1_id = :t1
                        WHERE id = :id
                    """), {"ge": int(ge_nuevo), "t1": int(t1_nuevo), "id": lr_id})
                celebrate_save(
                    f"L+R línea {int(row['linea_cod'])} ref {int(row['ref_cod'])} guardado",
                    modulo="Motor de Precios",
                    contexto="guardado",
                    balloons=False,
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB: ADMINISTRACIÓN DE CASOS (biblioteca)
# ─────────────────────────────────────────────────────────────────────────────

def _render_admin_casos():
    _seccion(
        "Contenedor de líneas y catálogo",
        "FK línea→caso por listado · plantillas reutilizables por proveedor",
    )

    df_prov = get_proveedores()
    if df_prov is None or df_prov.empty:
        st.info("No hay proveedores registrados.")
        return

    opts_prov = {r["nombre"]: int(r["id"]) for _, r in df_prov.iterrows()}
    prov_label = st.selectbox("Proveedor", list(opts_prov.keys()), key="ac_prov")
    prov_id    = opts_prov[prov_label]

    tab_listado, tab_catalogo = st.tabs(["Listado activo", "Catálogo de casos"])

    with tab_listado:
        df_ev = get_eventos_proveedor(prov_id)
        if df_ev is None or df_ev.empty:
            st.info(
                "Todavía no hay listados. Creá uno en **Nuevo Evento**; "
                "el contenedor de líneas se guarda en **Paso 2**."
            )
        else:
            opts_ev = {
                f"{r['nombre_evento']} — {str(r['estado']).upper()} — "
                f"{int(r['total_skus']):,} SKUs": int(r["id"])
                for _, r in df_ev.iterrows()
            }
            ev_label = st.selectbox("Listado de precios", list(opts_ev.keys()), key="ac_listado")
            eid = opts_ev[ev_label]
            estado_ev = ev_label.split(" — ")[1].strip().upper()

            resumen = get_contenedor_lineas_resumen(eid)
            st.metric("Total líneas en contenedor (FK)", resumen["total_lineas"])

            df_casos = get_casos_evento(eid)
            if df_casos is None or df_casos.empty:
                st.warning("Sin casos en este listado. Definilos en **Nuevo Evento → Paso 2**.")
            else:
                exc_por_caso = excepciones_lineas_por_caso(eid)
                editable = estado_ev not in ("CERRADO",)
                alguna_edicion = any(
                    st.session_state.get(f"ac_edit_cont_{int(row['id'])}")
                    for _, row in df_casos.iterrows()
                )
                lineas_disp: list[str] = []
                if alguna_edicion:
                    with proceso_largo(
                        "Cargando pilar de líneas",
                        "Preparando selector (~1.500 líneas)…",
                    ) as avanzar:
                        avanzar(0.5, "Consultando base de datos…")
                        lineas_disp = [c for c, _ in cache_lineas_proveedor(prov_id)]
                        avanzar(1.0, "Listo")

                for _, row in df_casos.iterrows():
                    cid = int(row["id"])
                    nombre = str(row["nombre_caso"])
                    dolar = _to_float(row.get("dolar_politica")) or 0.0
                    factor = _to_float(row.get("factor_conversion")) or 0.0
                    indice = (dolar * factor) / 100
                    lineas_exc = exc_por_caso.get(nombre.replace("*", "").strip(), [])
                    lpc_icon = "✓" if row.get("genera_lpc03_lpc04") else "✗"
                    st.markdown(
                        f"**{nombre}** · índice **{indice:,.0f}** · LPC {lpc_icon} · "
                        f"**{len(lineas_exc)}** líneas en contenedor"
                    )
                    if lineas_exc:
                        prev = ", ".join(lineas_exc[:12])
                        st.caption(f"{prev}{'…' if len(lineas_exc) > 12 else ''}")

                    if editable and st.session_state.get(f"ac_edit_cont_{cid}"):
                        sel = st.multiselect(
                            f"Líneas — {nombre}",
                            options=lineas_disp,
                            default=lineas_exc,
                            key=f"ac_cont_ms_{cid}",
                        )
                        b1, b2 = st.columns(2)
                        if b1.button("💾 Guardar contenedor", key=f"ac_cont_save_{cid}"):
                            n = reemplazar_lineas_excepcion(
                                cid, sel, prov_id, eid
                            )
                            st.session_state.pop(f"ac_edit_cont_{cid}", None)
                            celebrate_save(
                                f"{n} líneas en contenedor «{nombre}»",
                                modulo="Motor de Precios",
                                contexto="guardado",
                                balloons=False,
                            )
                            st.rerun()
                        if b2.button("Cancelar", key=f"ac_cont_cancel_{cid}"):
                            st.session_state.pop(f"ac_edit_cont_{cid}", None)
                            st.rerun()
                    elif editable:
                        if st.button(f"✏️ Editar líneas — {nombre}", key=f"ac_cont_edit_{cid}"):
                            st.session_state[f"ac_edit_cont_{cid}"] = True
                            with st.spinner("Preparando líneas del proveedor…"):
                                cache_lineas_proveedor(prov_id)
                            st.rerun()

                if estado_ev == "CERRADO":
                    st.caption("Listado cerrado: contenedor solo lectura.")

    with tab_catalogo:
        if st.session_state.get("bib_editor_state") and st.session_state.get(
            "bib_editor_en_catalogo"
        ):
            if st.button("← Volver al listado de bibliotecas", key="ac_bib_back"):
                st.session_state.pop("bib_editor_state", None)
                st.session_state.pop("bib_editor_en_catalogo", None)
                st.rerun()
            render_editor_biblioteca(prov_id, None)
        else:
            render_maestro_bibliotecas_tab(prov_id)


def _render_biblioteca_legacy(prov_id: int):
    df_bib = get_biblioteca_casos(prov_id)

    if df_bib is not None and not df_bib.empty:
        st.markdown(f"**{len(df_bib)} casos en biblioteca**")
        st.markdown("---")

        for _, row in df_bib.iterrows():
            cid      = int(row["id"])
            nombre   = str(row["nombre_caso"])
            dolar    = _to_float(row.get("dolar_politica")) or 0.0
            factor   = _to_float(row.get("factor_conversion")) or 0.0
            indice   = (dolar * factor) / 100
            lpc_icon = "✓" if row.get("genera_lpc03_lpc04") else "✗"
            marcas   = _parse_marcas(row.get("marcas"))
            marcas_s = ", ".join(marcas) if marcas else "—"
            lineas = parse_lineas_array(row.get("lineas"))
            lineas_s = ", ".join(lineas) if lineas else "—"

            col_info, col_edit, col_del = st.columns([5, 1, 1])
            col_info.markdown(
                f"**{nombre}** &nbsp;·&nbsp; "
                f"Gs {int(dolar):,} × {int(factor)} / 100 = índice **{indice:,.0f}** &nbsp;·&nbsp; "
                f"LPC {lpc_icon} &nbsp;·&nbsp; Marcas: {marcas_s} &nbsp;·&nbsp; Líneas: {lineas_s}"
            )

            # ── Editar ─────────────────────────────────────────────────────────
            if col_edit.button("✏️", key=f"ac_edit_{cid}", help="Editar"):
                st.session_state[f"ac_editing_{cid}"] = True

            if col_del.button("🗑️", key=f"ac_del_{cid}", help="Eliminar"):
                st.session_state[f"ac_confirm_del_{cid}"] = True

            # Confirmación de borrado
            if st.session_state.get(f"ac_confirm_del_{cid}"):
                st.warning(f"¿Eliminar **{nombre}**? Esta acción no afecta eventos ya procesados.")
                cc1, cc2 = st.columns([1, 4])
                if cc1.button("Sí, eliminar", type="primary", key=f"ac_del_ok_{cid}"):
                    eliminar_caso_biblioteca(cid)
                    for k in [f"ac_confirm_del_{cid}", f"ac_editing_{cid}"]:
                        st.session_state.pop(k, None)
                    celebrate_save(
                        f"Caso **{nombre}** eliminado",
                        modulo="Motor de Precios",
                        contexto="guardado",
                        balloons=False,
                    )
                    st.rerun()
                if cc2.button("Cancelar", key=f"ac_del_cancel_{cid}"):
                    st.session_state.pop(f"ac_confirm_del_{cid}", None)
                    st.rerun()

            # Formulario de edición inline
            if st.session_state.get(f"ac_editing_{cid}"):
                with st.container():
                    st.markdown(f"**Editando: {nombre}**")
                    e1, e2 = st.columns(2)
                    nuevo_nombre = st.text_input("Nombre", value=nombre, key=f"ac_en_{cid}")
                    ed = e1.number_input("Dólar política", value=dolar, step=100.0,
                                        min_value=1.0, key=f"ac_ed_{cid}")
                    ef = e2.number_input("Factor", value=factor, step=1.0, format="%.0f",
                                        min_value=1.0, key=f"ac_ef_{cid}")
                    st.caption(f"índice = {int((ed * ef) / 100):,}")
                    elpc = st.toggle("Genera LPC03/LPC04", value=bool(row.get("genera_lpc03_lpc04")),
                                     key=f"ac_elpc_{cid}")

                    d1_v = (_to_float(row.get("descuento_1")) or 0.0) * 100
                    d2_v = (_to_float(row.get("descuento_2")) or 0.0) * 100
                    d3_v = (_to_float(row.get("descuento_3")) or 0.0) * 100
                    d4_v = (_to_float(row.get("descuento_4")) or 0.0) * 100
                    ed1, ed2, ed3, ed4 = st.columns(4)
                    nd1 = ed1.number_input("D1 %", 0.0, 99.0, d1_v, 1.0, key=f"ac_d1_{cid}")
                    nd2 = ed2.number_input("D2 %", 0.0, 99.0, d2_v, 1.0, key=f"ac_d2_{cid}")
                    nd3 = ed3.number_input("D3 %", 0.0, 99.0, d3_v, 1.0, key=f"ac_d3_{cid}")
                    nd4 = ed4.number_input("D4 %", 0.0, 99.0, d4_v, 1.0, key=f"ac_d4_{cid}")

                    lineas_disponibles = get_lineas_proveedor(prov_id)
                    lineas_opciones = [cod for cod, _ in lineas_disponibles]
                    lineas_seleccionadas = st.multiselect(
                        "Líneas asignadas a este caso",
                        options=lineas_opciones,
                        default=lineas,
                        key=f"ac_lineas_{cid}",
                        help="Seleccioná las líneas que pertenecen a este caso de precio"
                    )

                    sb1, sb2 = st.columns([1, 4])
                    if sb1.button("💾 Guardar", type="primary", key=f"ac_save_{cid}"):
                        caso_upd = {
                            "nombre_caso":        nuevo_nombre.strip(),
                            "dolar_politica":     ed,
                            "factor_conversion":  ef,
                            "descuento_1":        round(nd1 / 100, 6) if nd1 > 0 else None,
                            "descuento_2":        round(nd2 / 100, 6) if nd2 > 0 else None,
                            "descuento_3":        round(nd3 / 100, 6) if nd3 > 0 else None,
                            "descuento_4":        round(nd4 / 100, 6) if nd4 > 0 else None,
                            "genera_lpc03_lpc04": elpc,
                            "alcance_tipo":       str(row.get("alcance_tipo", "marcas")),
                            "marcas":             marcas if marcas else None,
                            "lineas":             lineas_seleccionadas,
                        }
                        if update_caso_biblioteca(cid, caso_upd):
                            ok_sync, n_lineas = sincronizar_lineas_caso(prov_id, nuevo_nombre.strip(), lineas_seleccionadas)
                            if ok_sync:
                                st.session_state.pop(f"ac_editing_{cid}", None)
                                celebrate_save(
                                    f"Caso **{nuevo_nombre}** actualizado "
                                    f"({n_lineas} líneas en plantilla biblioteca)",
                                    modulo="Motor de Precios",
                                    contexto="guardado",
                                    balloons=False,
                                )
                                st.rerun()
                            else:
                                st.warning(f"Caso actualizado pero error al sincronizar líneas.")
                        else:
                            st.error("Error al guardar.")
                    if sb2.button("Cancelar", key=f"ac_edit_cancel_{cid}"):
                        st.session_state.pop(f"ac_editing_{cid}", None)
                        st.rerun()

            st.markdown("---")
    else:
        st.caption("Biblioteca vacía (esperado con el modelo por listado).")

    with st.expander("➕ Crear caso en biblioteca (solo legacy)"):
        _form_nuevo_caso_biblioteca(prov_id, marcas_disponibles=[], prefix="ac_new")

    st.markdown("---")
    _seccion("Zona de Mantenimiento", "Operaciones destructivas — solo Director/Admin")

    with st.expander("🗑️ Purgar TODAS las listas de precios"):
        st.error(
            "**Esta acción elimina todos los eventos de precio, sus casos y todos los SKUs "
            "de precio_lista.** Los pilares (linea, referencia, material, color) quedan intactos."
        )

        confirmar_texto = st.text_input(
            "Escribí CONFIRMAR para habilitar el botón",
            key="ac_purge_confirm",
            placeholder="CONFIRMAR"
        )

        if st.button(
            "🗑️ Purgar todas las listas ahora",
            type="primary",
            key="ac_purge_btn",
            disabled=(confirmar_texto.strip() != "CONFIRMAR"),
        ):
            ok, stats = purgar_todas_las_listas()
            if ok:
                bib = stats.get("biblioteca", 0)
                celebrate_save(
                    f"Purga completada — "
                    f"{stats['eventos']} eventos, {stats['casos']} casos, "
                    f"{stats['skus']:,} SKUs, {bib} plantillas. Pilares intactos.",
                    modulo="Motor de Precios",
                    contexto="purge_reset",
                    balloons=True,
                )
                st.rerun()
            else:
                st.error("Error durante la purga. Revisá los logs del sistema.")
