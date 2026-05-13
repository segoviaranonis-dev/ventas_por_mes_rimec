"""
RIMEC ENGINE — ui.py
Interfaz del motor de gestión de eventos de precio.
Flujo: Paso 0 (carga) → 1 (memoria) → 2 (casos) → 3 (preview/cálculo) → 4 (validación) → 5 (cierre)
"""

import random
import streamlit as st
import pandas as pd
from datetime import date

from modules.rimec_engine.logic import (
    leer_excel_proveedor,
    calcular_precios_caso,
    get_preview_skus,
    get_proveedores,
    build_pillar_cache,
    get_or_create_linea_cached,
    get_or_create_referencia_cached,
    get_or_create_material_cached,
    crear_evento,
    crear_caso,
    guardar_lineas_excepcion,
    guardar_precio_lista,
    avanzar_estado_evento,
    cerrar_evento_y_activar,
    registrar_auditoria,
    get_ultimo_evento_cerrado,
    get_casos_evento,
    get_lineas_por_evento,
    get_todos_eventos,
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
    get_lineas_proveedor,
    sincronizar_lineas_caso,
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
              "re_plantilla_casos"]:
        if k in st.session_state:
            del st.session_state[k]


# ─────────────────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_rimec_engine():
    st.markdown("## ⚙️ Motor de Precios — RIMEC ENGINE")
    st.markdown("---")

    tab_nuevo, tab_historial, tab_lineas, tab_lr, tab_casos = st.tabs([
        "🆕 Nuevo Evento", "📋 Historial", "🔧 Admin Líneas",
        "🔗 Línea × Referencia", "📦 Casos",
    ])

    with tab_nuevo:
        _render_flujo()

    with tab_historial:
        _render_historial()

    with tab_lineas:
        _render_admin_lineas()

    with tab_lr:
        _render_linea_referencia()

    with tab_casos:
        _render_admin_casos()


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def _render_flujo():
    paso = st.session_state.get("re_paso", 0)

    # Barra de progreso
    pasos_labels = ["Carga", "Memoria", "Casos", "Preview", "Validación", "Cierre"]
    cols_prog = st.columns(len(pasos_labels))
    for i, label in enumerate(pasos_labels):
        color = "#D4AF37" if i == paso else ("#10B981" if i < paso else "#334155")
        cols_prog[i].markdown(
            f"<div style='text-align:center;padding:6px;background:{color};"
            f"border-radius:6px;font-size:0.72rem;color:white;font-weight:600;'>"
            f"{i}. {label}</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

    if paso == 0:
        _paso_0_carga()
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
        with st.spinner("Leyendo archivo..."):
            _hm = st.session_state.get("hiedra_meta", {})
            if _hm.get("reconocido"):
                from modules.rimec_engine.hiedra import leer_excel_hiedra
                resultado = leer_excel_hiedra(archivo, archivo.name)
            else:
                resultado = leer_excel_proveedor(archivo, archivo.name)

        if resultado["error"]:
            st.error(f"Error al leer el archivo: {resultado['error']}")
            return

        skus = resultado["skus"]
        marcas = resultado["marcas"]

        st.success(f"✅ {len(skus)} SKUs detectados en {len(marcas)} marcas: **{', '.join(marcas)}**")

        evento_id = crear_evento(nombre_evento, archivo.name, str(fecha_desde), proveedor_id)
        if not evento_id:
            st.error("Error al crear el evento en la base de datos.")
            return

        st.session_state["re_evento_id"]      = evento_id
        st.session_state["re_proveedor_id"]   = proveedor_id
        st.session_state["re_skus"]           = skus
        st.session_state["re_marcas"]         = marcas
        st.session_state["re_archivo_nombre"] = archivo.name
        st.session_state["re_nombre_evento"]  = nombre_evento
        st.session_state["re_casos"]          = []
        st.session_state["re_skus_por_caso"]  = {}
        st.session_state["re_paso"]           = 1
        st.rerun()


# ── PASO 1 — Memoria del evento anterior ─────────────────────────────────────

def _paso_1_memoria():
    _seccion("Paso 1 — Memoria del evento anterior")

    evento_ant = get_ultimo_evento_cerrado()

    if evento_ant:
        st.info(
            f"📂 Último evento cerrado: **{evento_ant['nombre_evento']}** "
            f"({evento_ant['total_skus']} SKUs — {evento_ant['fecha_vigencia_desde']})"
        )
        casos_ant = get_casos_evento(int(evento_ant["id"]))

        if not casos_ant.empty:
            lineas_map = get_lineas_por_evento(int(evento_ant["id"]))

            st.markdown("**Casos del evento anterior:**")
            df_display = casos_ant.copy()
            df_display["indice"] = (df_display["dolar_politica"] * df_display["factor_conversion"] / 100).round(0).astype(int)

            alcance_col = []
            for _, row in df_display.iterrows():
                marcas = row.get("marcas")
                items = []
                # marcas llega como lista Python, string PG "{A,B}", o None/NaN
                if marcas is not None and marcas == marcas:  # excluye NaN
                    if isinstance(marcas, (list, tuple)):
                        items = [str(m) for m in marcas if m]
                    elif isinstance(marcas, str) and marcas.strip() not in ("", "None", "nan"):
                        items = [m.strip() for m in marcas.strip("{}").split(",") if m.strip()]
                if items:
                    alcance_col.append(", ".join(items))
                else:
                    lins = lineas_map.get(int(row["id"]), [])
                    n = len(lins)
                    if lins:
                        preview = ", ".join(lins[:6])
                        alcance_col.append(f"Líneas ({n}): {preview}{'…' if n > 6 else ''}")
                    else:
                        alcance_col.append("—")
            df_display["alcance"] = alcance_col
            cols_show = [c for c in ["nombre_caso", "dolar_politica", "factor_conversion",
                                     "indice", "descuento_1", "genera_lpc03_lpc04",
                                     "alcance"] if c in df_display.columns]
            st.dataframe(df_display[cols_show].fillna("—"), use_container_width=True, hide_index=True)

        def _build_plantilla():
            lineas_map = get_lineas_por_evento(int(evento_ant["id"]))
            plantilla = casos_ant.to_dict("records")
            for rec in plantilla:
                cid = int(rec.get("id", 0))
                if cid in lineas_map:
                    rec["lineas"] = lineas_map[cid]
            return plantilla

        col1, col2, col3 = st.columns(3)
        if col1.button("📋 Usar como plantilla"):
            st.session_state["re_plantilla_casos"] = _build_plantilla()
            st.session_state["re_paso"] = 2
            st.rerun()
        if col2.button("✏️ Modificar y usar"):
            st.session_state["re_plantilla_casos"] = _build_plantilla()
            st.session_state["re_paso"] = 2
            st.rerun()
        if col3.button("🆕 Empezar desde cero"):
            st.session_state["re_plantilla_casos"] = []
            st.session_state["re_paso"] = 2
            st.rerun()
    else:
        st.info("No hay eventos anteriores cerrados. Se empieza desde cero.")
        if st.button("▶️ Continuar"):
            st.session_state["re_plantilla_casos"] = []
            st.session_state["re_paso"] = 2
            st.rerun()


# ── PASO 2 — Análisis Automático de Líneas y Casos ───────────────────────────

def _paso_2_casos():
    _seccion("Paso 2 — Análisis Automático")

    col_nav, _ = st.columns([1, 4])
    if col_nav.button("← Volver a Memoria"):
        st.session_state["re_paso"] = 1
        st.rerun()

    proveedor_id = st.session_state.get("re_proveedor_id")
    skus_disp    = st.session_state.get("re_skus", pd.DataFrame())

    if skus_disp.empty:
        st.error("No hay SKUs cargados.")
        return

    df_bib = get_biblioteca_casos(proveedor_id)
    if df_bib.empty:
        st.error("La biblioteca de casos está vacía. Debes crear los casos en la pantalla de Administración antes de generar un evento.")
        return

    st.markdown("El sistema ha cruzado los SKUs del archivo con el maestro de líneas para asignar automáticamente el caso aplicable.")
    
    with st.spinner("Resolviendo casos..."):
        skus_resueltos, ready_to_calc = resolver_casos_skus(skus_disp, proveedor_id, df_bib)
    
    st.session_state["re_skus_resueltos"] = skus_resueltos
    st.session_state["re_ready_to_calc"]  = ready_to_calc
    st.session_state["re_df_bib"]         = df_bib

    st.markdown("### Resumen de Asignación")
    
    df_resumen = skus_resueltos.groupby(["caso_asignado", "estado_validacion"]).size().reset_index(name='Cantidad de SKUs')
    st.dataframe(df_resumen, use_container_width=True, hide_index=True)

    if not ready_to_calc:
        st.error("❌ Hay errores en la asignación. Existen casos asignados a líneas (o casos por defecto) que **NO EXISTEN** en la Biblioteca de Casos.")
        st.info("💡 Solución: Ve al menú 'Biblioteca de Casos' en el panel lateral, crea los casos faltantes y luego vuelve a cargar el evento.")
    else:
        st.success("✅ Todos los SKUs tienen un caso válido asignado.")

    col_cont, _ = st.columns([1, 3])
    if col_cont.button("▶️ Continuar al Cálculo", type="primary", disabled=not ready_to_calc):
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
            st.success(f"'{caso['nombre_caso']}' guardado en biblioteca.")
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
    df_bib         = st.session_state.get("re_df_bib", pd.DataFrame())

    if skus_resueltos.empty or df_bib.empty:
        st.error("No hay SKUs resueltos o biblioteca vacía.")
        return

    casos_bib = {row["nombre_caso"]: row.to_dict() for _, row in df_bib.iterrows()}

    st.markdown(f"Se procesarán **{len(skus_resueltos)}** SKUs de forma automatizada.")

    if st.button("✅ Iniciar Cálculo de todos los SKUs", type="primary"):
        with st.spinner("Calculando y guardando precios en base de datos..."):
            cache = build_pillar_cache(proveedor_id)
            grupos = skus_resueltos.groupby("caso_asignado")
            
            casos_procesados = []
            skus_omitidos_total = 0
            confirmados = {}
            
            total_skus = len(skus_resueltos)
            skus_procesados = 0
            progress_bar = st.progress(0, text="Iniciando cálculo de precios...")
            
            for i, (nombre_caso, skus_grupo) in enumerate(grupos):
                print(f"[ENGINE] Iniciando cálculo de caso: '{nombre_caso}' ({len(skus_grupo)} SKUs)")
                if nombre_caso not in casos_bib:
                    st.error(f"Error crítico: Caso '{nombre_caso}' no existe en biblioteca.")
                    continue
                
                caso_params = casos_bib[nombre_caso]
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
                    "marcas":             None,
                    "lineas":             [],
                    "referencias":        [],
                    "alcance_tipo":       "marcas"
                }
                
                caso_id = crear_caso(evento_id, caso_db)
                if not caso_id:
                    st.error(f"Fallo al guardar configuración del caso {nombre_caso}.")
                    continue
                
                casos_procesados.append(caso_db)
                
                dolar_ap  = float(caso_db["dolar_politica"])
                factor_ap = float(caso_db["factor_conversion"])
                indice_ap = (dolar_ap * factor_ap) / 100

                filas = []
                skus_omitidos = 0
                for _, row in skus_grupo.iterrows():
                    fob  = float(row["fob_fabrica"])
                    calc = calcular_precios_caso(fob, caso_db)

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

                    filas.append({
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

                guardar_precio_lista(filas)
                skus_omitidos_total += skus_omitidos
                confirmados[f"caso_{i}"] = len(filas)
                
                skus_procesados += len(skus_grupo)
                pct = int((skus_procesados / total_skus) * 100) if total_skus > 0 else 100
                progress_bar.progress(pct, text=f"Calculado {skus_procesados}/{total_skus} SKUs ({pct}%) — Caso actual: {nombre_caso}")
                print(f"[ENGINE] Completado caso '{nombre_caso}' ({len(skus_grupo)} SKUs procesados). Progreso: {pct}%")

            if skus_omitidos_total:
                st.warning(f"⚠️ {skus_omitidos_total} SKU(s) omitidos por pilares nulos. Revisar Excel.")
            
            # Preparar state para Paso 4
            st.session_state["re_casos"] = casos_procesados
            st.session_state["re_skus_por_caso"] = confirmados
            
            avanzar_estado_evento(evento_id, "validado")
            st.session_state["re_paso"] = 4
            st.rerun()


# ── PASO 4 — Validación final ────────────────────────────────────────────────

def _paso_4_validacion():
    _seccion("Paso 4 — Validación final")

    evento_id      = st.session_state.get("re_evento_id")
    nombre_evento  = st.session_state.get("re_nombre_evento", f"Evento #{evento_id}")
    casos          = st.session_state.get("re_casos", [])

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
           LEFT JOIN linea     l ON l.id  = pl.linea_codigo::bigint
           LEFT JOIN referencia r ON r.id = pl.referencia_codigo::bigint
           LEFT JOIN material   m ON m.id = pl.material_descripcion::bigint
           WHERE pl.evento_id = :eid
           ORDER BY pec.nombre_caso, pl.marca,
                    COALESCE(l.codigo_proveedor, pl.linea_codigo::bigint),
                    COALESCE(r.codigo_proveedor, pl.referencia_codigo::bigint)""",
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
        st.success(f"✅ Todos los casos calculados ({casos_ok} casos). El Director puede validar.")
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

    if st.button("🔒 Cerrar y activar precios", type="primary"):
        cerrar_evento_y_activar(evento_id, str(date.today()))
        if justificacion:
            registrar_auditoria(
                evento_id, "precio_evento", "estado",
                "validado", "cerrado", justificacion
            )
        st.success("🎉 Evento cerrado. Los nuevos precios están activos.")
        _reset_flujo()
        st.balloons()
        st.rerun()

    if st.button("← Volver a revisar"):
        st.session_state["re_paso"] = 4
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HISTORIAL
# ─────────────────────────────────────────────────────────────────────────────

def _render_historial():
    _seccion("Historial de Listas de Precios")

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
                st.warning("🔒 **Este evento no puede editarse ni eliminarse**")
                st.markdown("**Está siendo utilizado por:**")
                for mod in uso["modulos"]:
                    st.markdown(f"&nbsp;&nbsp;· {mod}")
                st.info(
                    "**Para liberar este evento:**\n"
                    "1. Desvinculá las ICs en el módulo de Intención de Compra\n"
                    "2. O creá un nuevo evento de precio con los valores corregidos"
                )

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

            elif estado_real == "en_uso":
                st.button(
                    "🔒 Bloqueado — en uso por otros módulos",
                    key=f"lock_{eid}",
                    disabled=True,
                    use_container_width=True,
                )

            else:
                # borrador o validado → se puede eliminar
                if st.button(
                    "🗑️ Eliminar evento",
                    key=f"del_ev_{eid}",
                    help="Elimina este evento y todos sus datos. Irreversible.",
                ):
                    ok = eliminar_evento(eid)
                    if ok:
                        st.success("Evento eliminado.")
                        st.rerun()
                    else:
                        st.error("No se pudo eliminar. Verificá que no esté en uso.")

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
                       LEFT JOIN linea     l ON l.id  = pl.linea_codigo::bigint
                       LEFT JOIN referencia r ON r.id = pl.referencia_codigo::bigint
                       LEFT JOIN material   m ON m.id = pl.material_descripcion::bigint
                       WHERE pl.evento_id = :eid
                       ORDER BY pec.nombre_caso, pl.marca, pl.linea_codigo, pl.referencia_codigo""",
                    {"eid": eid},
                )
                if df_det is not None and not df_det.empty:
                    st.dataframe(df_det, use_container_width=True, hide_index=True, height=300)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN LÍNEAS — maestro Línea + Marca + Caso + Clasificación
# ─────────────────────────────────────────────────────────────────────────────

def _render_admin_lineas():
    from core.database import get_dataframe
    from modules.intencion_compra.logic import (
        get_lineas_filtradas, get_valores_filtro_lineas,
        update_linea_clasificacion, get_proveedores,
    )

    _seccion("Administración de Líneas", "Línea · Marca · Caso · Clasificación")
    st.caption(
        "Tabla `linea` es la única fuente de verdad. Marca y Caso son asignables. "
        "Caso se autocompleta al cerrar un evento, pero también editable acá."
    )

    df_prov = get_proveedores()
    if df_prov is None or df_prov.empty:
        st.info("No hay proveedores registrados.")
        return

    opts_prov = {r["nombre"]: int(r["id"]) for _, r in df_prov.iterrows()}
    prov_label = st.selectbox("Proveedor", list(opts_prov.keys()), key="al_prov")
    prov_id    = opts_prov[prov_label]

    # ── Catálogo de casos de la biblioteca del proveedor (dropdown editable) ──
    df_casos_bib = get_dataframe(
        "SELECT id, nombre_caso FROM caso_precio_biblioteca "
        "WHERE proveedor_id = :pid AND activo = true ORDER BY nombre_caso",
        {"pid": prov_id},
    )
    casos_bib: dict[int, str] = (
        {int(r["id"]): str(r["nombre_caso"]) for _, r in df_casos_bib.iterrows()}
        if df_casos_bib is not None and not df_casos_bib.empty else {}
    )

    # ── Barra de filtros ──────────────────────────────────────────────────────
    _NULL = "— Vacío —"
    _SIN_CASO = "— Sin caso —"
    marcas_vals  = ["Todas"]  + get_valores_filtro_lineas(prov_id, "marca")
    casos_vals   = ["Todos", _SIN_CASO] + get_valores_filtro_lineas(prov_id, "caso_nombre")
    genero_vals  = ["Todos", _NULL]     + get_valores_filtro_lineas(prov_id, "descp_genero")

    fc1, fc2, fc3 = st.columns(3)
    f_marca  = fc1.selectbox("Marca",  marcas_vals, key="al_f_marca")
    f_caso   = fc2.selectbox("Caso",   casos_vals,  key="al_f_caso")
    f_genero = fc3.selectbox("Género", genero_vals, key="al_f_gen")

    df_lineas = get_lineas_filtradas(
        prov_id,
        marca  = None if f_marca  == "Todas" else f_marca,
        caso   = None if f_caso   == "Todos" else f_caso,
        genero = None if f_genero == "Todos" else f_genero,
    )

    if df_lineas is None or df_lineas.empty:
        st.info("No hay líneas activas para este proveedor con los filtros seleccionados.")
        return

    st.markdown(
        f"**{len(df_lineas)} líneas** &nbsp;·&nbsp; "
        "Caso y Género → editables fila a fila. &nbsp; "
        "Estilo / Tipos → editables en la pestaña Línea × Referencia.",
        unsafe_allow_html=True,
    )

    # ── Editor por rango de código ─────────────────────────────────────────────
    casos_existentes = get_valores_filtro_lineas(prov_id, "caso_nombre")
    generos_maestro  = get_generos()

    with st.expander("✏️ Editar Caso/Género por rango de código"):
        st.caption(
            "Ingresá el rango de códigos de línea y el nuevo Caso y/o Género. "
            "Se actualizan todas las líneas del proveedor en ese rango."
        )
        rc1, rc2 = st.columns(2)
        rango_desde = rc1.number_input("Línea inicial (código)", min_value=0, step=1,
                                       value=0, key="al_rango_desde")
        rango_hasta = rc2.number_input("Línea final (código)", min_value=0, step=1,
                                       value=0, key="al_rango_hasta")

        caso_opciones = ["— No cambiar —"] + sorted(casos_existentes)
        caso_sel = st.selectbox("Caso", caso_opciones, key="al_rango_caso")

        genero_opciones = ["— No cambiar —"] + generos_maestro
        genero_sel = st.selectbox("Género", genero_opciones, key="al_rango_genero")

        if st.button("Aplicar rango", type="primary", key="al_rango_btn"):
            if rango_desde > rango_hasta:
                st.error("Línea inicial debe ser ≤ Línea final.")
            elif caso_sel == "— No cambiar —" and genero_sel == "— No cambiar —":
                st.error("Seleccioná al menos Caso o Género.")
            else:
                caso_val   = None if caso_sel   == "— No cambiar —" else caso_sel
                genero_val = None if genero_sel == "— No cambiar —" else genero_sel
                ok, n = actualizar_lineas_por_rango(
                    prov_id, int(rango_desde), int(rango_hasta), caso_val, genero_val
                )
                if ok:
                    st.success(f"✓ {n} líneas actualizadas (rango {rango_desde}–{rango_hasta}).")
                    st.rerun()
                else:
                    st.error("Error al aplicar el rango.")

    st.markdown("---")

    # ── Tabla editable fila por fila ──────────────────────────────────────────
    def _sv(x) -> str:
        return "" if pd.isna(x) or str(x) in ("None", "nan") else str(x)

    hc = st.columns([1, 2, 3, 2, 1])
    for col, lbl in zip(hc, ["Línea", "Marca", "Caso", "Género", ""]):
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

    casos_opts_ids: list = [None] + list(casos_bib.keys())
    def _caso_label(cid):
        return "— Sin caso —" if cid is None else casos_bib.get(int(cid), f"#{cid}")

    for _, row in df_lineas.iterrows():
        linea_id = int(row["id"])
        cod      = int(row["codigo_proveedor"])
        gen_act  = _sv(row.get("descp_genero"))
        gen_idx  = generos_fila.index(gen_act) if gen_act in generos_fila else 0
        caso_id_act = row.get("caso_id")
        try:
            caso_idx = casos_opts_ids.index(int(caso_id_act)) if caso_id_act else 0
        except (ValueError, TypeError):
            caso_idx = 0

        c0, c1, c2, c3, c4 = st.columns([1, 2, 3, 2, 1])
        c0.markdown(f"**{cod}**")
        c1.markdown(_sv(row.get("marca")) or "—")

        caso_sel = c2.selectbox("Caso", casos_opts_ids, index=caso_idx,
                                 format_func=_caso_label,
                                 key=f"al_caso_{linea_id}",
                                 label_visibility="collapsed")
        gen = c3.selectbox("Gén", generos_fila, index=gen_idx,
                           key=f"al_gen_{linea_id}", label_visibility="collapsed")

        if c4.button("💾", key=f"al_save_{linea_id}", help="Guardar fila"):
            campos: set = set()
            kwargs: dict = {}
            nuevo_caso_id = int(caso_sel) if caso_sel is not None else None
            actual_caso_id = int(caso_id_act) if caso_id_act else None
            if nuevo_caso_id != actual_caso_id:
                campos.add("caso_id")
                kwargs["caso_id"] = nuevo_caso_id
            nuevo_gen_id = gen_map.get(gen) if gen else None
            actual_gen_id = int(row.get("genero_id")) if row.get("genero_id") else None
            if nuevo_gen_id != actual_gen_id:
                campos.add("genero_id")
                kwargs["genero_id"] = nuevo_gen_id

            if not campos:
                st.info(f"Línea {cod}: sin cambios.")
                continue
            ok = update_linea_clasificacion(linea_id, _campos=campos, **kwargs)
            if ok:
                st.success(f"Línea {cod} guardada ({', '.join(sorted(campos))}).")
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
            l.id                    AS linea_id,
            l.codigo_proveedor      AS linea_cod,
            r.codigo_proveedor      AS ref_cod,
            COALESCE(mv.descp_marca, '') AS marca,
            COALESCE(ge.descp_grupo_estilo, lr.descp_grupo_estilo) AS descp_grupo_estilo,
            COALESCE(t1.descp_tipo_1, lr.descp_tipo_1)             AS descp_tipo_1,
            lr.grupo_estilo_id,
            lr.tipo_1_id
        FROM linea_referencia lr
        JOIN linea      l  ON l.id  = lr.linea_id
        JOIN referencia r  ON r.id  = lr.referencia_id
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
            df[["linea_id", "linea_cod", "ref_cod", "marca", "descp_grupo_estilo", "descp_tipo_1"]].rename(columns={
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
                st.success(f"✓ {len(ids)} registros actualizados.")
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
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB: ADMINISTRACIÓN DE CASOS (biblioteca)
# ─────────────────────────────────────────────────────────────────────────────

def _render_admin_casos():
    _seccion("Biblioteca de Casos de Precio", "CRUD completo — independiente de cualquier evento")
    st.caption(
        "Los casos aquí guardados aparecen en el Paso 2 al crear un nuevo evento. "
        "Podés crear, editar y eliminar casos sin afectar los eventos ya procesados."
    )

    df_prov = get_proveedores()
    if df_prov is None or df_prov.empty:
        st.info("No hay proveedores registrados.")
        return

    opts_prov = {r["nombre"]: int(r["id"]) for _, r in df_prov.iterrows()}
    prov_label = st.selectbox("Proveedor", list(opts_prov.keys()), key="ac_prov")
    prov_id    = opts_prov[prov_label]

    df_bib = get_biblioteca_casos(prov_id)

    # ── Tabla de casos existentes ─────────────────────────────────────────────
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
            from core.database import get_dataframe
            df_lc = get_dataframe(
                "SELECT l.codigo_proveedor FROM linea l "
                "JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id "
                "WHERE l.proveedor_id = :pid AND cpb.nombre_caso = :cn AND l.activo = true "
                "ORDER BY l.codigo_proveedor",
                {"pid": prov_id, "cn": nombre}
            )
            lineas = [str(x) for x in df_lc["codigo_proveedor"].tolist()] if df_lc is not None and not df_lc.empty else []
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
                    st.success(f"Caso **{nombre}** eliminado.")
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
                            "lineas":             _parse_marcas(row.get("lineas")) if row.get("lineas") else [],
                        }
                        if update_caso_biblioteca(cid, caso_upd):
                            ok_sync, n_lineas = sincronizar_lineas_caso(prov_id, nuevo_nombre.strip(), lineas_seleccionadas)
                            if ok_sync:
                                st.session_state.pop(f"ac_editing_{cid}", None)
                                st.success(f"Caso **{nuevo_nombre}** actualizado ({n_lineas} líneas asignadas).")
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
        st.info("La biblioteca está vacía. Creá el primer caso usando el formulario.")

    # ── Formulario nuevo caso ─────────────────────────────────────────────────
    with st.expander("➕ Crear nuevo caso en biblioteca"):
        _form_nuevo_caso_biblioteca(prov_id, marcas_disponibles=[], prefix="ac_new")

    # ── Purga de listas de precios ────────────────────────────────────────────
    st.markdown("---")
    _seccion("Zona de Mantenimiento", "Operaciones destructivas — solo Director/Admin")

    with st.expander("🗑️ Purgar TODAS las listas de precios"):
        st.error(
            "**Esta acción elimina todos los eventos de precio, sus casos y todos los SKUs "
            "de precio_lista.** Los pilares (linea con su caso_id, referencia, material, color) "
            "quedan intactos."
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
                st.success(
                    f"✓ Purga completada — "
                    f"{stats['eventos']} eventos, {stats['casos']} casos, "
                    f"{stats['skus']:,} SKUs eliminados. Pilares intactos."
                )
                st.rerun()
            else:
                st.error("Error durante la purga. Revisá los logs del sistema.")
