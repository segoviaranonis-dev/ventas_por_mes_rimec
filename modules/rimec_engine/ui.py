"""
RIMEC ENGINE — ui.py
Interfaz del motor de gestión de eventos de precio.
Flujo: Paso 0 (carga) → 1 (memoria) → 2 (casos) → 3 (preview/cálculo) → 4 (validación) → 5 (cierre)
"""

import streamlit as st
import pandas as pd
from datetime import date

from modules.rimec_engine.logic import (
    leer_excel_proveedor,
    calcular_precios_caso,
    get_preview_skus,
    crear_evento,
    crear_caso,
    guardar_lineas_excepcion,
    guardar_precio_lista,
    avanzar_estado_evento,
    cerrar_evento_y_activar,
    registrar_auditoria,
    get_ultimo_evento_cerrado,
    get_casos_evento,
    get_todos_eventos,
    eliminar_evento,
    generar_zip_pdfs_evento,
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
              "re_casos", "re_paso", "re_archivo_nombre", "re_nombre_evento", "re_skus_por_caso"]:
        if k in st.session_state:
            del st.session_state[k]


# ─────────────────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_rimec_engine():
    st.markdown("## ⚙️ Motor de Precios — RIMEC ENGINE")
    st.markdown("---")

    tab_nuevo, tab_historial = st.tabs(["🆕 Nuevo Evento", "📋 Historial"])

    with tab_nuevo:
        _render_flujo()

    with tab_historial:
        _render_historial()


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

    archivo = st.file_uploader("Archivo del proveedor (.xls / .xlsx)", type=["xls", "xlsx"])
    nombre_sugerido = archivo.name.replace(".xls", "").replace(".xlsx", "") if archivo else ""
    nombre_evento = st.text_input("Nombre del evento", value=nombre_sugerido,
                                  placeholder="Ej: TEMPORADA_INVIERNO_2026")
    fecha_desde = st.date_input("Precios vigentes desde", value=date.today())

    if archivo and nombre_evento and st.button("🚀 Cargar y analizar", type="primary"):
        with st.spinner("Leyendo archivo..."):
            resultado = leer_excel_proveedor(archivo, archivo.name)

        if resultado["error"]:
            st.error(f"Error al leer el archivo: {resultado['error']}")
            return

        skus = resultado["skus"]
        marcas = resultado["marcas"]

        st.success(f"✅ {len(skus)} SKUs detectados en {len(marcas)} marcas: **{', '.join(marcas)}**")

        evento_id = crear_evento(nombre_evento, archivo.name, str(fecha_desde))
        if not evento_id:
            st.error("Error al crear el evento en la base de datos.")
            return

        st.session_state["re_evento_id"]      = evento_id
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
            st.markdown("**Casos del evento anterior:**")
            st.dataframe(
                casos_ant[["nombre_caso", "dolar_politica", "factor_conversion",
                           "indice_calculado", "descuento_1", "descuento_2",
                           "genera_lpc03_lpc04"]].fillna("—"),
                use_container_width=True, hide_index=True
            )

        col1, col2, col3 = st.columns(3)
        if col1.button("📋 Usar como plantilla"):
            st.session_state["re_plantilla_casos"] = casos_ant.to_dict("records")
            st.session_state["re_paso"] = 2
            st.rerun()
        if col2.button("✏️ Modificar y usar"):
            st.session_state["re_plantilla_casos"] = casos_ant.to_dict("records")
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


# ── PASO 2 — Configuración de casos ──────────────────────────────────────────

def _paso_2_casos():
    _seccion("Paso 2 — Configuración de casos")

    col_nav, _ = st.columns([1, 4])
    if col_nav.button("← Volver a Memoria"):
        st.session_state["re_paso"] = 1
        st.rerun()

    marcas_disponibles = st.session_state.get("re_marcas", [])
    casos_guardados    = st.session_state.get("re_casos", [])
    plantilla          = st.session_state.get("re_plantilla_casos", [])

    if casos_guardados:
        st.markdown("**Casos configurados:**")
        for i, c in enumerate(casos_guardados):
            if c.get("marcas"):
                mc = "Marcas: " + ", ".join(c["marcas"])
            elif c.get("lineas"):
                mc = "Líneas: " + ", ".join(c["lineas"])
            else:
                mc = "— sin filtro"
            col_desc, col_del = st.columns([5, 1])
            col_desc.markdown(
                f"✅ **{c['nombre_caso']}** | "
                f"USD {c['dolar_politica']} × {c['factor_conversion']} → "
                f"índice {round((c['dolar_politica']*c['factor_conversion'])/100, 2)} | "
                f"{mc}"
            )
            if col_del.button("🗑️", key=f"del_caso_{i}", help="Eliminar este caso"):
                st.session_state["re_casos"].pop(i)
                st.rerun()
        st.markdown("---")

    st.markdown("**Agregar caso:**")

    nombre_default = ""
    if plantilla and len(casos_guardados) < len(plantilla):
        p = plantilla[len(casos_guardados)]
        nombre_default = p.get("nombre_caso", "")

    nombre_caso = st.text_input("Nombre del caso", value=nombre_default,
                                placeholder="Ej: NORMAL, CHINELO, PROMOCIONAL...")

    col3, col4 = st.columns(2)
    dolar   = col3.number_input("Dólar de política (Gs)", min_value=1.0, step=100.0,
                                 value=float(plantilla[len(casos_guardados)]["dolar_politica"])
                                 if plantilla and len(casos_guardados) < len(plantilla) else 8000.0)
    factor  = col4.number_input("Factor (Ej: 160, 180)", min_value=1.0, step=1.0, format="%.0f",
                                 value=float(plantilla[len(casos_guardados)]["factor_conversion"])
                                 if plantilla and len(casos_guardados) < len(plantilla) else 180.0)

    indice_preview = (dolar * factor) / 100
    st.caption(
        f"📐 {int(dolar):,} × {int(factor)} / 100 = "
        f"**{indice_preview:,.0f} Gs** por USD de FOB"
    )

    st.markdown("**Descuentos en cascada — ingresar como número entero (Ej: 15 = 15%):**")
    cd1, cd2, cd3, cd4 = st.columns(4)
    d1 = cd1.number_input("D1 %", min_value=0.0, max_value=99.0, step=1.0, value=0.0, format="%.1f")
    d2 = cd2.number_input("D2 %", min_value=0.0, max_value=99.0, step=1.0, value=0.0, format="%.1f")
    d3 = cd3.number_input("D3 %", min_value=0.0, max_value=99.0, step=1.0, value=0.0, format="%.1f")
    d4 = cd4.number_input("D4 %", min_value=0.0, max_value=99.0, step=1.0, value=0.0, format="%.1f")

    genera_derivados = st.toggle("Genera LPC03 (+12%) y LPC04 (+20%)", value=True)

    st.markdown("**Alcance del caso:**")
    skus_disp = st.session_state.get("re_skus", pd.DataFrame())

    # Calcular qué marcas y líneas ya están asignadas a casos anteriores
    marcas_ya_asignadas = set()
    lineas_ya_asignadas = set()
    for c in casos_guardados:
        marcas_ya_asignadas.update(c.get("marcas") or [])
        lineas_ya_asignadas.update(c.get("lineas") or [])

    marcas_libres = [m for m in marcas_disponibles if m not in marcas_ya_asignadas]

    alcance = st.radio(
        "Aplica por:",
        ["Marcas", "Líneas específicas"],
        horizontal=True,
        help="'Marcas' = hojas del Excel (VIZZANO, BEIRA RIO…). 'Líneas' = código numérico de línea.",
    )

    marcas_caso   = []
    linea_codigos = []

    if alcance == "Marcas":
        if not marcas_libres:
            st.info("✅ Todas las marcas ya están asignadas a un caso.")
        else:
            marcas_caso = st.multiselect(
                f"Seleccionar marcas — {len(marcas_libres)} disponibles",
                marcas_libres,
            )

    elif alcance == "Líneas específicas":
        lineas_str = st.text_input(
            "Códigos de línea (separados por coma)",
            placeholder="Ej: 8224, 8395, 8449, 8557",
        )
        linea_codigos = [c.strip() for c in lineas_str.split(",") if c.strip()]
        if linea_codigos:
            st.caption(f"📋 {len(linea_codigos)} líneas ingresadas: {', '.join(linea_codigos)}")

    if st.button("➕ Agregar este caso"):
        if not nombre_caso:
            st.error("El nombre del caso es obligatorio.")
        elif alcance == "Marcas" and not marcas_caso:
            st.error("Seleccioná al menos una marca.")
        elif alcance == "Líneas específicas" and not linea_codigos:
            st.error("Seleccioná al menos una línea.")
        else:
            caso = {
                "nombre_caso":        nombre_caso,
                "dolar_politica":     dolar,
                "factor_conversion":  factor,
                "descuento_1":        round(d1 / 100, 6) if d1 > 0 else None,
                "descuento_2":        round(d2 / 100, 6) if d2 > 0 else None,
                "descuento_3":        round(d3 / 100, 6) if d3 > 0 else None,
                "descuento_4":        round(d4 / 100, 6) if d4 > 0 else None,
                "genera_lpc03_lpc04": genera_derivados,
                "regla_redondeo":     "centena",
                "marcas":             marcas_caso if alcance == "Marcas" else None,
                "lineas":             linea_codigos if alcance == "Líneas específicas" else [],
                "referencias":        [],
            }
            st.session_state["re_casos"].append(caso)
            st.rerun()

    st.markdown("---")

    if not skus_disp.empty and casos_guardados:
        # Calcular SKUs ya cubiertos
        skus_cubiertos = set()
        for c in casos_guardados:
            if c.get("marcas"):
                mask = skus_disp["marca"].isin(c["marcas"])
            elif c.get("referencias"):
                mask = skus_disp["referencia"].isin(c["referencias"])
            elif c.get("lineas"):
                mask = skus_disp["linea"].isin(c["lineas"])
            else:
                mask = pd.Series(False, index=skus_disp.index)
            skus_cubiertos.update(skus_disp[mask].index.tolist())

        total = len(skus_disp)
        cubiertos = len(skus_cubiertos)
        pct = int(cubiertos / total * 100) if total else 0

        if pct < 100:
            st.warning(
                f"⚠️ {cubiertos}/{total} SKUs cubiertos ({pct}%). "
                f"Podés continuar de todas formas o agregar más casos."
            )
        else:
            st.success(f"✅ 100% de SKUs cubiertos ({total} SKUs).")

        col_cont, _ = st.columns([1, 3])
        if col_cont.button("▶️ Ir al Preview y Cálculo", type="primary", disabled=(cubiertos == 0)):
            st.session_state["re_paso"] = 3
            st.rerun()


# ── PASO 3 — Preview y cálculo ───────────────────────────────────────────────

def _paso_3_preview():
    _seccion("Paso 3 — Preview y cálculo")

    col_nav, _ = st.columns([1, 4])
    if col_nav.button("← Volver a Casos"):
        st.session_state["re_paso"] = 2
        st.rerun()

    skus        = st.session_state.get("re_skus", pd.DataFrame())
    casos       = st.session_state.get("re_casos", [])
    evento_id   = st.session_state.get("re_evento_id")
    confirmados = st.session_state.get("re_skus_por_caso", {})

    for i, caso in enumerate(casos):
        caso_key = f"caso_{i}"
        if caso_key in confirmados:
            st.markdown(f"✅ **{caso['nombre_caso']}** — confirmado ({confirmados[caso_key]} SKUs)")
            continue

        _seccion(f"Caso: {caso['nombre_caso']}")

        # Filtrar SKUs de este caso
        if caso.get("marcas"):
            skus_caso = skus[skus["marca"].isin(caso["marcas"])].copy()
        elif caso.get("referencias"):
            skus_caso = skus[skus["referencia"].isin(caso["referencias"])].copy()
        else:
            lineas_filtro = caso.get("lineas", [])
            skus_caso = skus[skus["linea"].isin(lineas_filtro)].copy() if lineas_filtro else pd.DataFrame()

        if skus_caso.empty:
            st.warning(f"Sin SKUs para el caso **{caso['nombre_caso']}**.")
            continue

        indice = (caso["dolar_politica"] * caso["factor_conversion"]) / 100
        st.caption(
            f"📐 {caso['dolar_politica']} × {caso['factor_conversion']} / 100 = **{indice:.4f}** | "
            f"{len(skus_caso)} SKUs"
        )

        preview = get_preview_skus(skus_caso, caso, n=5)
        st.dataframe(preview, use_container_width=True, hide_index=True)

        col_a, col_b = st.columns([3, 1])
        col_b.caption(f"Mostrando 5 de {len(skus_caso)}")

        if col_a.button(f"✅ Confirmar y calcular todo — {caso['nombre_caso']}", key=f"confirmar_{i}"):
            with st.spinner(f"Calculando {len(skus_caso)} SKUs..."):
                # Crear caso en BD
                caso_id = crear_caso(evento_id, caso)
                if not caso_id:
                    st.error("Error al guardar el caso en la BD.")
                    continue

                # Guardar líneas excepción si aplica
                if caso.get("lineas"):
                    guardar_lineas_excepcion(caso_id, caso["lineas"])

                # Calcular y guardar todos los SKUs
                filas = []
                for _, row in skus_caso.iterrows():
                    fob  = float(row["fob_fabrica"])
                    calc = calcular_precios_caso(fob, caso)
                    filas.append({
                        "eid":   evento_id,
                        "cid":   caso_id,
                        "marca": str(row["marca"]),
                        "lc":    str(row.get("linea", "—")),
                        "rc":    str(row["referencia"]),
                        "md":    str(row.get("material", "STANDARD")),
                        "fob":   fob,
                        "foba":  calc["fob_ajustado"],
                        "lpn":   calc["lpn"],
                        "lpc03": calc["lpc03"],
                        "lpc04": calc["lpc04"],
                    })

                guardar_precio_lista(filas)
                confirmados[caso_key] = len(filas)
                st.session_state["re_skus_por_caso"] = confirmados
                st.rerun()

    # Verificar si todos los casos están confirmados
    if len(confirmados) == len(casos):
        avanzar_estado_evento(evento_id, "validado")
        if st.button("▶️ Ir a Validación Final", type="primary"):
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

    # ── Resumen por caso ──────────────────────────────────────────────────────
    for i, caso in enumerate(casos):
        clave = f"caso_{i}"
        n_skus = confirmados.get(clave)
        if n_skus is not None:
            idx = (caso["dolar_politica"] * caso["factor_conversion"]) / 100
            st.markdown(
                f"✅ **{caso['nombre_caso']}** — "
                f"índice {idx:,.0f} — **{n_skus:,} SKUs** calculados"
            )
        else:
            st.markdown(f"⏳ **{caso['nombre_caso']}** — pendiente de confirmar")

    st.markdown("---")

    # ── Tabla de resultados agrupada por caso ─────────────────────────────────
    df_resultado = get_dataframe(
        """SELECT pec.nombre_caso AS "Caso",
                  pl.marca        AS "Marca",
                  pl.linea_codigo      AS "Línea",
                  pl.referencia_codigo AS "Referencia",
                  COALESCE(m.descripcion, pl.material_descripcion) AS "Material",
                  pl.fob_fabrica  AS "FOB",
                  pl.fob_ajustado AS "FOB Ajustado",
                  pl.lpn          AS "LPN",
                  pl.lpc03        AS "LPC03",
                  pl.lpc04        AS "LPC04"
           FROM precio_lista pl
           JOIN precio_evento_caso pec ON pec.id = pl.caso_id
           LEFT JOIN material m ON m.codigo = pl.material_descripcion
           WHERE pl.evento_id = :eid
           ORDER BY pec.nombre_caso, pl.marca, pl.linea_codigo, pl.referencia_codigo""",
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

    estado_icon = {"cerrado": "🟢", "validado": "🔵", "borrador": "⚪"}

    for _, ev in df.iterrows():
        icon  = estado_icon.get(ev["estado"], "⚪")
        label = (
            f"{icon} **{ev['nombre_evento']}** "
            f"— {ev['estado'].upper()} "
            f"— {int(ev['total_skus']):,} SKUs "
            f"— vigente desde {str(ev['fecha_vigencia_desde'])[:10]}"
        )
        with st.expander(label):
            # ── Cabecera del evento (lista de precios) ──────────────────────
            st.markdown(
                f"""<div style="background:#1e293b;border-left:4px solid #D4AF37;
                                padding:12px 18px;border-radius:6px;margin-bottom:12px;">
                    <div style="color:#94a3b8;font-size:0.7rem;text-transform:uppercase;">
                        Lista de Precios</div>
                    <div style="color:#f1f5f9;font-size:1.05rem;font-weight:700;">
                        {ev['nombre_evento']}</div>
                    <div style="color:#64748b;font-size:0.75rem;margin-top:2px;">
                        Archivo: {ev['nombre_archivo']} &nbsp;·&nbsp;
                        Creado: {str(ev['created_at'])[:16]}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

            # ── Casos del evento ────────────────────────────────────────────
            df_casos = get_casos_evento(int(ev["id"]))
            if not df_casos.empty:
                st.markdown("**Casos de esta lista:**")
                for _, caso in df_casos.iterrows():
                    idx = (caso['dolar_politica'] * caso['factor_conversion']) / 100
                    st.markdown(
                        f"&nbsp;&nbsp;• **{caso['nombre_caso']}** — "
                        f"Gs {int(caso['dolar_politica']):,} × {int(caso['factor_conversion'])} / 100 "
                        f"= índice **{idx:,.0f}**"
                    )

            # ── Acciones: PDF ZIP (cerrado) o Eliminar (no-cerrado) ────────────
            eid = int(ev["id"])
            if ev["estado"] == "cerrado":
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
            else:
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
                        st.error("No se pudo eliminar.")

            # ── Tabla de precios ────────────────────────────────────────────
            if ev["estado"] in ("cerrado", "validado"):
                df_det = get_dataframe(
                    """SELECT pec.nombre_caso AS "Caso",
                              pl.marca        AS "Marca",
                              pl.linea_codigo      AS "Línea",
                              pl.referencia_codigo AS "Referencia",
                              COALESCE(m.descripcion, pl.material_descripcion) AS "Material",
                              pl.fob_fabrica AS "FOB",
                              pl.lpn  AS "LPN",
                              pl.lpc03 AS "LPC03",
                              pl.lpc04 AS "LPC04",
                              pl.vigente AS "Vigente"
                       FROM precio_lista pl
                       JOIN precio_evento_caso pec ON pec.id = pl.caso_id
                       LEFT JOIN material m ON m.codigo = pl.material_descripcion
                       WHERE pl.evento_id = :eid
                       ORDER BY pec.nombre_caso, pl.marca, pl.linea_codigo, pl.referencia_codigo""",
                    {"eid": eid},
                )
                if df_det is not None and not df_det.empty:
                    st.dataframe(df_det, use_container_width=True, hide_index=True, height=300)
