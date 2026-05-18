"""
UI — Maestro Biblioteca de Casos (glassmorphism, acordeón, descarte en vivo).
"""
from __future__ import annotations

import streamlit as st

from core.ux_celebrate import celebrate_save, celebrate_step
from modules.rimec_engine.biblioteca_maestro import (
    BibliotecaEditorState,
    agregar_lineas_a_casos_biblioteca,
    aplicar_biblioteca_a_evento,
    cargar_biblioteca_editor_state,
    crear_biblioteca,
    duplicar_biblioteca,
    guardar_estado_biblioteca,
    listar_bibliotecas,
    mensaje_si_falta_migracion_biblioteca,
    cargar_catalogo_marcas_pilar,
    cargar_pilar_datos,
    parse_codigos_linea_texto,
    parse_lineas_texto_pilar,
    actualizar_nombre_biblioteca,
    guardar_lineas_caso_directo,
    recargar_lineas_caso_desde_bd,
    persistir_un_caso_biblioteca,
    vincular_biblioteca_a_evento,
)
from modules.rimec_engine.pillar_fk import (
    provisionar_linea_pilar_clonando_inferior,
    provisionar_lineas_faltantes_en_pilar,
)
from modules.rimec_engine.biblioteca_compare import (
    comparar_excel_vs_biblioteca,
    get_casos_biblioteca,
)
from modules.rimec_engine.logic import (
    hydrate_casos_evento_desde_db,
    preparar_evento_para_preview,
)
from modules.rimec_engine.ui_proceso import proceso_largo


def inject_glass_styles() -> None:
    st.markdown(
        """
    <style>
    .rimec-glass-panel {
        background: rgba(15, 23, 42, 0.72);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(212, 175, 55, 0.35);
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        margin: 0.5rem 0 1.25rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    }
    .rimec-glass-title {
        color: #D4AF37;
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .rimec-glass-sub {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _abrir_editor_catalogo(proveedor_id: int, biblioteca_id: int) -> bool:
    state = cargar_biblioteca_editor_state(proveedor_id, biblioteca_id)
    if not state:
        st.error(
            f"No se pudo cargar la biblioteca id {biblioteca_id}. "
            "Verificá que exista en biblioteca_precio y que la migración 044 esté aplicada."
        )
        return False
    st.session_state["bib_editor_state"] = state
    st.session_state["bib_editor_en_catalogo"] = True
    st.session_state["bib_editor_evento_id"] = None
    st.session_state.pop("bib_pending_save", None)
    st.session_state.pop(f"_bib_list_cache_{proveedor_id}", None)
    return True


def render_seleccion_biblioteca_post_carga(
    proveedor_id: int,
    evento_id: int,
    nombre_evento: str,
) -> None:
    """
    OT-519: Flujo simplificado Biblioteca.
    Select → Compare → if OK → Preview; if gaps → Resolve.
    """
    inject_glass_styles()
    mig = mensaje_si_falta_migracion_biblioteca()
    if mig:
        st.error(mig)
        if st.button("▶️ Continuar sin biblioteca (solo matriz manual)", key="bib_skip_no_mig"):
            vincular_biblioteca_a_evento(evento_id, None)
            _ir_a_paso_1()
        return

    # Cargar bibliotecas disponibles
    cache_key = f"_bib_list_cache_{proveedor_id}"
    if cache_key not in st.session_state:
        with proceso_largo("Cargando bibliotecas", "Consultando plantillas del proveedor…") as avanzar:
            avanzar(0.3, "Conectando…")
            st.session_state[cache_key] = listar_bibliotecas(proveedor_id)
            avanzar(1.0, "Listo")
    df_bib = st.session_state[cache_key]

    st.markdown(
        f'<div class="rimec-glass-panel">'
        f'<div class="rimec-glass-title">Paso 1 — Biblioteca de Casos</div>'
        f'<div class="rimec-glass-sub">Listado: <b>{nombre_evento}</b></div>'
        f'<p style="color:#e2e8f0;margin:0;">Seleccioná biblioteca para comparar con el Excel cargado</p></div>',
        unsafe_allow_html=True,
    )

    # Selectbox biblioteca
    opciones: list[tuple[str, int | None]] = [("— Sin biblioteca (armar manualmente) —", None)]
    if df_bib is not None and not df_bib.empty:
        for _, row in df_bib.iterrows():
            opciones.append((str(row["nombre"]), int(row["id"])))

    labels = [o[0] for o in opciones]
    sel_label = st.selectbox(
        "Bibliotecas disponibles",
        labels,
        key="bib_sel_post_carga",
        label_visibility="collapsed",
    )
    biblioteca_id = next((o[1] for o in opciones if o[0] == sel_label), None)

    # Botones principales
    col_skip, col_compare = st.columns([1, 2])

    if col_skip.button("▶️ Sin biblioteca", key="bib_skip"):
        vincular_biblioteca_a_evento(evento_id, None)
        st.session_state["re_biblioteca_ok"] = False
        _ir_a_paso_1()
        return

    if biblioteca_id and col_compare.button("🔍 Comparar con Excel", type="primary", key="bib_compare"):
        st.session_state["re_biblioteca_comparando_id"] = biblioteca_id
        st.session_state["re_biblioteca_comparando_nombre"] = sel_label
        st.rerun()

    # Si ya se inició comparación, mostrar resultado
    if st.session_state.get("re_biblioteca_comparando_id") == biblioteca_id:
        _render_comparacion_y_resolucion(
            proveedor_id, evento_id, biblioteca_id, sel_label, nombre_evento
        )

    st.caption(
        "💡 **Consejo:** Si no tenés biblioteca, crealá en **Catálogo de casos** y volvé acá."
    )


def _render_comparacion_y_resolucion(
    proveedor_id: int,
    evento_id: int,
    biblioteca_id: int,
    biblioteca_nombre: str,
    nombre_evento: str,
) -> None:
    """OT-519: Muestra resultado comparación + resolución de gaps si es necesario."""

    # Obtener SKUs cargados del Excel
    re_skus = st.session_state.get("re_skus")
    if re_skus is None or re_skus.empty:
        st.error("No hay SKUs cargados del Excel.")
        return

    # Ejecutar comparación (caché en session_state para evitar re-cálculo)
    comp_key = f"_comp_{biblioteca_id}_{evento_id}"
    if comp_key not in st.session_state:
        with proceso_largo("Comparando", "Excel vs Biblioteca vs Pilar…") as avanzar:
            avanzar(0.5, "Analizando...")
            comp = comparar_excel_vs_biblioteca(re_skus, proveedor_id, biblioteca_id)
            st.session_state[comp_key] = comp
            avanzar(1.0, "Listo")

    comp = st.session_state[comp_key]

    st.markdown("---")
    st.markdown(f"### 📊 Resultado: **{biblioteca_nombre}**")

    # Semáforo verde o ámbar
    if comp.ok:
        st.success(comp.resumen_texto())
        st.markdown(f"**{len(comp.cubiertas)} líneas** del Excel están cubiertas por los casos de la biblioteca.")

        if st.button("✅ Continuar a Preview", type="primary", key="bib_go_preview"):
            ok, msg, n = False, "", 0
            prep_ok, prep_msg = False, ""
            skus_r, df_ev, ready = None, None, False
            conflictos: list = []
            re_skus = st.session_state.get("re_skus")

            with proceso_largo(
                "Aplicando biblioteca",
                f"Copiando «{biblioteca_nombre}» al evento…",
            ) as avanzar:
                avanzar(0.2, "Copiando casos al listado…")
                ok, msg, n = aplicar_biblioteca_a_evento(
                    evento_id, proveedor_id, biblioteca_id
                )
                if not ok:
                    avanzar(1.0, "Error al aplicar")
                else:
                    avanzar(0.55, "Hidratando matriz…")
                    casos_ev = hydrate_casos_evento_desde_db(evento_id)
                    st.session_state["re_casos_evento"] = casos_ev
                    st.session_state["re_casos_evento_hydrated"] = evento_id
                    avanzar(0.75, "Asignando SKUs a casos…")
                    prep_ok, prep_msg, skus_r, df_ev, ready, conflictos = (
                        preparar_evento_para_preview(
                            evento_id,
                            proveedor_id,
                            re_skus,
                            casos_evento=casos_ev,
                        )
                    )
                    avanzar(1.0, "Listo")

            if not ok:
                st.error(msg)
                return
            if not prep_ok:
                st.error(prep_msg)
                if conflictos:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(conflictos), use_container_width=True)
                return

            st.session_state["re_skus_resueltos"] = skus_r
            st.session_state["re_df_evento"] = df_ev
            st.session_state["re_ready_to_calc"] = ready
            st.session_state["re_conflictos"] = conflictos
            st.session_state["re_biblioteca_ok"] = True
            st.session_state["re_biblioteca_aplicada_id"] = biblioteca_id
            st.session_state["re_paso"] = 3
            celebrate_step(
                "Biblioteca",
                f"«{biblioteca_nombre}» — {n} caso(s), {len(skus_r)} SKUs listos",
                modulo="Motor de Precios",
                handoff="Cálculo de precios",
            )
            st.rerun()

    else:
        # Hay gaps - mostrar tabla para resolución
        st.warning(comp.resumen_texto())

        st.markdown("#### 🔧 Resolver excepciones")

        # Cargar casos disponibles de la biblioteca
        casos_map = get_casos_biblioteca(biblioteca_id)
        casos_opciones = list(casos_map.keys())

        if not casos_opciones:
            st.error("La biblioteca no tiene casos definidos. Editá la biblioteca primero.")
            return

        # Tabla: líneas sin caso
        if comp.sin_caso:
            st.markdown(f"**Sin caso ({len(comp.sin_caso)}):** líneas en pilar, en Excel, NO en biblioteca")

            asignaciones = {}  # {linea: [caso_ids]}

            for linea in comp.sin_caso:
                col_linea, col_casos = st.columns([1, 3])
                col_linea.code(linea)
                selected = col_casos.multiselect(
                    f"Casos para línea {linea}",
                    casos_opciones,
                    key=f"caso_asig_{linea}",
                    label_visibility="collapsed"
                )
                if selected:
                    asignaciones[linea] = [casos_map[c] for c in selected]

            if asignaciones and st.button("💾 Agregar a biblioteca", key="add_to_bib"):
                # Invertir: {caso_id: [lineas]}
                caso_lineas = {}
                for linea, caso_ids in asignaciones.items():
                    for cid in caso_ids:
                        caso_lineas.setdefault(cid, []).append(linea)

                with proceso_largo("Guardando", "Agregando líneas a casos...") as avanzar:
                    avanzar(0.5, "Actualizando biblioteca...")
                    ok, n_agregadas = agregar_lineas_a_casos_biblioteca(caso_lineas)
                    avanzar(1.0, "Listo")

                if ok:
                    st.success(f"✅ {n_agregadas} líneas agregadas a {len(caso_lineas)} caso(s)")
                    # Limpiar caché y re-comparar
                    st.session_state.pop(comp_key, None)
                    st.rerun()
                else:
                    st.error("Error al agregar líneas a biblioteca")

        # Tabla: líneas no en pilar
        if comp.no_en_pilar:
            st.markdown(f"**No en pilar ({len(comp.no_en_pilar)}):** líneas del Excel que aún no existen")

            for linea in comp.no_en_pilar[:10]:  # Mostrar primeras 10
                st.code(linea)

            if len(comp.no_en_pilar) > 10:
                st.caption(f"...y {len(comp.no_en_pilar) - 10} más")

            if st.button("🔨 Crear en pilar (batch)", key="create_pilar"):
                with proceso_largo("Creando líneas", f"Provisionando {len(comp.no_en_pilar)} líneas...") as avanzar:
                    avanzar(0.3, "Iniciando...")
                    codigos = [int(c) if c.isdigit() else 0 for c in comp.no_en_pilar]
                    codigos = [c for c in codigos if c > 0]
                    ok_list, err_list = provisionar_lineas_faltantes_en_pilar(
                        proveedor_id, [str(c) for c in codigos]
                    )
                    avanzar(1.0, f"Creadas: {len(ok_list)}")

                st.success(f"✅ {len(ok_list)} líneas creadas en pilar")
                if err_list:
                    st.warning("Algunas líneas no se crearon: " + "; ".join(err_list[:5]))
                # Limpiar caché y re-comparar
                st.session_state.pop(comp_key, None)
                st.rerun()

        # Link a catálogo (casos complejos)
        st.caption("💡 **¿Casos complejos?** Ir a **Catálogo de casos** para armar y volver.")


def _ir_a_paso_1() -> None:
    st.session_state.pop("re_pending_biblioteca", None)
    st.session_state["re_paso"] = 1
    st.rerun()


def _render_modal_guardar_bifurcacion(state: BibliotecaEditorState) -> None:
    st.warning(
        "¿**Sustituir** la biblioteca actual (impacto global) o **crear una copia** nueva?"
    )
    modo = st.radio(
        "Modo de guardado",
        [
            "Sustituir biblioteca actual",
            "Crear biblioteca nueva (copia independiente)",
        ],
        key="bib_guardar_modo",
    )
    nuevo_nombre = ""
    if modo.startswith("Crear"):
        nuevo_nombre = st.text_input(
            "Nombre de la nueva biblioteca",
            value=f"{state.nombre} — copia",
            key="bib_guardar_nombre_nuevo",
        )
    if st.button("💾 Confirmar guardado", type="primary", key="bib_guardar_ok"):
        m = "nueva" if modo.startswith("Crear") else "sustituir"
        bid, err = None, ""
        with proceso_largo("Guardando biblioteca", "Persistiendo casos y líneas…") as avanzar:
            avanzar(0.2, "Validando…")
            bid, err = guardar_estado_biblioteca(
                state, modo=m, nuevo_nombre=nuevo_nombre if m == "nueva" else None
            )
            avanzar(0.85, "Recargando…")
            if not err and bid:
                st.session_state["bib_editor_state"] = cargar_biblioteca_editor_state(
                    state.proveedor_id, bid
                )
            avanzar(1.0, "Guardado")
        if err:
            st.error(f"No se guardó la biblioteca: {err}")
            return
        st.session_state.pop("bib_pending_save", None)
        celebrate_save(f"Biblioteca guardada (id {bid})", modulo="Motor de Precios")
        st.rerun()
    if st.button("Cancelar y seguir editando casos", key="bib_guardar_cancel"):
        st.session_state.pop("bib_pending_save", None)
        st.rerun()


def _pct_desde_decimal(val: object) -> float:
    if val is None:
        return 0.0
    try:
        return round(float(val) * 100, 2)
    except (TypeError, ValueError):
        return 0.0


def _descuentos_desde_inputs(d1: float, d2: float, d3: float, d4: float) -> dict:
    return {
        "descuento_1": round(d1 / 100, 6) if d1 > 0 else None,
        "descuento_2": round(d2 / 100, 6) if d2 > 0 else None,
        "descuento_3": round(d3 / 100, 6) if d3 > 0 else None,
        "descuento_4": round(d4 / 100, 6) if d4 > 0 else None,
    }


def _render_fila_descuentos(
    data: dict,
    key_prefix: str,
) -> None:
    cd1, cd2, cd3, cd4 = st.columns(4)
    d1 = cd1.number_input(
        "D1 % s/ USD",
        0.0,
        99.0,
        _pct_desde_decimal(data.get("descuento_1")),
        1.0,
        key=f"{key_prefix}_d1",
        help="Descuento aplicado sobre el precio en dólares",
    )
    d2 = cd2.number_input(
        "D2 % s/ USD",
        0.0,
        99.0,
        _pct_desde_decimal(data.get("descuento_2")),
        1.0,
        key=f"{key_prefix}_d2",
    )
    d3 = cd3.number_input(
        "D3 % s/ USD",
        0.0,
        99.0,
        _pct_desde_decimal(data.get("descuento_3")),
        1.0,
        key=f"{key_prefix}_d3",
    )
    d4 = cd4.number_input(
        "D4 % s/ USD",
        0.0,
        99.0,
        _pct_desde_decimal(data.get("descuento_4")),
        1.0,
        key=f"{key_prefix}_d4",
    )
    data.update(_descuentos_desde_inputs(d1, d2, d3, d4))


def _aplicar_filtros_lineas_pilar(
    state: BibliotecaEditorState,
    codigos: list[str],
    marca_fk_sel: list[int],
    filtro_codigo: str,
) -> list[str]:
    out = state.filtrar_codigos_por_marca_fk(codigos, marca_fk_sel)
    if filtro_codigo.strip():
        f = filtro_codigo.strip()
        out = [c for c in out if f in c]
    return out


def _render_selector_marca_pilar(
    state: BibliotecaEditorState,
    key_prefix: str,
    *,
    lineas_disponibles: list[str],
) -> list[int]:
    """Multiselect por marca: solo marcas con líneas aún libres (no en otros casos)."""
    if not state.pilar_marcas and not state.pilar_tiene_sin_marca:
        extra = cargar_catalogo_marcas_pilar(state.proveedor_id)
        if extra:
            state.pilar_marcas = extra
            st.session_state["bib_editor_state"] = state
    opciones = state.marcas_en_lineas(lineas_disponibles)
    if not opciones:
        if not lineas_disponibles:
            st.caption("No hay líneas del pilar para agregar a este caso.")
        else:
            st.warning(
                "No hay marcas con líneas libres. Revisá **marca_id** en el pilar "
                "o liberá líneas de otro caso."
            )
        return []
    ids = [o[0] for o in opciones]
    labels = {o[0]: o[1] for o in opciones}
    sel = st.multiselect(
        "Marca (solo con líneas libres en esta biblioteca)",
        options=ids,
        format_func=lambda mid: labels.get(mid, str(mid)),
        key=f"{key_prefix}_marca_fk",
        help="Solo marcas con líneas libres (no usadas en otros casos de esta biblioteca).",
    )
    return [x for x in sel if x in ids]


def _lineas_a_texto_lista(codigos: list[str]) -> str:
    return ", ".join(codigos)


def _parse_lista_lineas_texto(
    texto: str,
    pilar_lineas: list[str],
) -> tuple[set[str], list[str]]:
    """Convierte texto (comas, saltos de línea, rangos) en set de códigos del pilar."""
    raw = str(texto or "").replace("\n", ",").replace(";", ",")
    codigos, errs = parse_lineas_texto_pilar(raw, pilar_lineas, set())
    return set(codigos), errs


def _parse_lista_lineas_desde_editor(texto: str) -> tuple[set[str], list[str]]:
    """Todo código del texto (rangos incluidos); el pilar se completa al guardar."""
    codigos, errs = parse_codigos_linea_texto(str(texto or ""))
    return set(codigos), errs


def _evento_id_para_alta_pilar() -> int | None:
    """Evento activo para nutrir referencias al crear líneas nuevas en el pilar."""
    for key in ("bib_editor_evento_id", "re_evento_id"):
        raw = st.session_state.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return None


def _sort_key_linea(c: str) -> tuple:
    try:
        return (0, int(c))
    except ValueError:
        return (1, len(c), c)


def _render_editar_nombre_biblioteca(state: BibliotecaEditorState) -> None:
    """Nombre editable en cabecera del editor."""
    if not state.biblioteca_id:
        st.markdown(f"### {state.nombre}")
        return
    st.markdown("### Nombre de la biblioteca")
    c_nom, c_btn = st.columns([4, 1])
    with c_nom:
        nom = st.text_input(
            "Nombre",
            value=state.nombre,
            key="bib_editor_nombre",
            label_visibility="collapsed",
            placeholder="Ej: CP 7447-4083",
        )
    with c_btn:
        st.write("")
        if st.button(
            "💾 Guardar nombre",
            type="primary",
            key="bib_guardar_nombre_btn",
            use_container_width=True,
        ):
            nuevo = str(st.session_state.get("bib_editor_nombre", nom) or "").strip()
            if not nuevo:
                st.error("Escribí un nombre.")
            else:
                ok, err = actualizar_nombre_biblioteca(int(state.biblioteca_id), nuevo)
                if err:
                    st.error(err)
                else:
                    state.nombre = nuevo
                    st.session_state["bib_editor_state"] = state
                    st.session_state.pop(f"_bib_list_cache_{state.proveedor_id}", None)
                    celebrate_save("Nombre actualizado", modulo="Motor de Precios", balloons=False)
                    st.rerun()


def _render_alta_linea_pilar(state: BibliotecaEditorState) -> None:
    """Alta rápida de una línea nueva en el pilar (herencia desde inferior)."""
    with st.expander("➕ Agregar línea al pilar", expanded=True):
        st.caption(
            "Crea la línea en el **pilar del proveedor** (copia marca/género/estilo y referencias "
            "de la línea inmediata inferior). Después asignala a un caso con **Editar lista**."
        )
        c1, c2, c3 = st.columns([2, 2, 1])
        cod_txt = c1.text_input(
            "Código de línea nueva",
            key="bib_alta_linea_cod",
            placeholder="Ej: 1492",
        )
        c2.caption("También podés pegar varias: 1492, 1493 o 1490-1495")
        if c3.button(
            "Crear en pilar",
            type="primary",
            key="bib_alta_linea_btn",
            use_container_width=True,
        ):
            raw = str(st.session_state.get("bib_alta_linea_cod", cod_txt) or "").strip()
            if not raw:
                st.warning("Indicá al menos un código de línea.")
            else:
                codigos, errs = parse_codigos_linea_texto(raw)
                if errs:
                    st.warning("; ".join(errs[:6]))
                nuevos = sorted(
                    {c for c in codigos if c not in set(state.pilar_lineas)},
                    key=_sort_key_linea,
                )
                if not nuevos and codigos:
                    st.info("Esas líneas ya están en el pilar.")
                elif nuevos:
                    eid = _evento_id_para_alta_pilar()
                    with st.spinner(f"Creando {len(nuevos)} línea(s) en el pilar…"):
                        ok_list, err_list = provisionar_lineas_faltantes_en_pilar(
                            state.proveedor_id,
                            nuevos,
                            evento_id=eid,
                        )
                    if err_list:
                        st.error("; ".join(err_list[:6]))
                    if ok_list:
                        _refrescar_pilar_en_estado(state)
                        st.success(
                            f"Pilar actualizado: {len(ok_list)} línea(s) creada(s) "
                            f"({', '.join(ok_list[:8])}"
                            f"{', …' if len(ok_list) > 8 else ''}). "
                            "Asignalas a un caso abajo."
                        )
                        if "bib_alta_linea_cod" in st.session_state:
                            del st.session_state["bib_alta_linea_cod"]
                        st.rerun()


def _refrescar_pilar_en_estado(state: BibliotecaEditorState) -> None:
    codigos, cod_marca, marcas, sin_marca = cargar_pilar_datos(
        state.proveedor_id, usar_cache=False
    )
    state.pilar_lineas = codigos
    state.pilar_marca_por_codigo = cod_marca
    state.pilar_marcas = marcas
    state.pilar_tiene_sin_marca = sin_marca
    st.session_state["bib_editor_state"] = state
    st.session_state.pop(f"_cache_pilar_datos_{state.proveedor_id}", None)
    st.session_state.pop(f"_cache_pilar_cod_{state.proveedor_id}", None)


def _aplicar_lista_lineas_editada(
    state: BibliotecaEditorState,
    caso_nombre: str,
    caso_key: str,
    nueva_lista: set[str],
    *,
    evento_id: int | None = None,
) -> tuple[int, int, str]:
    """Reemplaza el contenedor en memoria y persiste con asignación directa en BD."""
    actual = state.lineas_en_caso(caso_nombre)
    pilar_set = set(state.pilar_lineas)
    faltantes = sorted(c for c in nueva_lista if c not in pilar_set)
    if faltantes:
        altas_ok, altas_err = provisionar_lineas_faltantes_en_pilar(
            state.proveedor_id,
            faltantes,
            evento_id=evento_id,
        )
        if altas_err:
            return 0, 0, "; ".join(altas_err[:6])
        if altas_ok:
            _refrescar_pilar_en_estado(state)
            pilar_set = set(state.pilar_lineas)
    invalidas = sorted(c for c in nueva_lista if c not in pilar_set)
    if invalidas:
        return 0, 0, f"Códigos fuera del pilar: {', '.join(invalidas[:8])}"
    en_otros = state.lineas_ocupadas_en_otros_casos(caso_nombre)
    conflictos = sorted(nueva_lista & en_otros)
    if conflictos:
        return (
            0,
            0,
            "Ya están en otro caso de la biblioteca: "
            + ", ".join(conflictos[:8]),
        )
    n_quitar = len(actual - nueva_lista)
    n_agregar = len(nueva_lista - actual)
    data = state.casos.get(caso_key)
    if not data:
        return 0, 0, "Caso no encontrado."
    data["lineas"] = set(nueva_lista)
    state.dirty = True
    st.session_state["bib_editor_state"] = state
    with st.spinner("Asignando líneas en base de datos…"):
        n_bd, err = guardar_lineas_caso_directo(state, caso_key)
    if err:
        recargar_lineas_caso_desde_bd(state, caso_key)
        st.session_state["bib_editor_state"] = state
        return n_quitar, n_agregar, err
    st.session_state["bib_editor_state"] = state
    return n_quitar, n_agregar, ""


def _texto_lineas_widget(buffer_key: str, widget_key: str | None) -> str:
    """Texto actual del editor: prioriza el widget ya renderizado en este run."""
    wkey = widget_key or buffer_key
    return str(st.session_state.get(wkey) or st.session_state.get(buffer_key) or "").strip()


def _volvercar_texto_lineas(
    buffer_key: str,
    merged: str,
    widget_key: str | None,
) -> None:
    """
    Actualiza el buffer y borra el estado del text_area para que el próximo rerun
    lo reinicialice (Streamlit no permite asignar al key del widget tras crearlo).
    """
    st.session_state[buffer_key] = merged
    wkey = widget_key or buffer_key
    if wkey in st.session_state:
        del st.session_state[wkey]
    st.rerun()


def _anexar_lineas_al_editor(
    state: BibliotecaEditorState,
    buffer_key: str,
    widget_key: str | None,
    codigos: list[str],
) -> None:
    """Agrega códigos al texto del editor (sin duplicar) y refresca el text_area."""
    if not codigos:
        return
    prev = _texto_lineas_widget(buffer_key, widget_key)
    actual, _ = (
        _parse_lista_lineas_texto(prev, state.pilar_lineas)
        if prev
        else (set(), [])
    )
    actual |= set(codigos)
    merged = _lineas_a_texto_lista(sorted(actual, key=_sort_key_linea))
    _volvercar_texto_lineas(buffer_key, merged, widget_key)


def _render_ayuda_marca_opcional(
    state: BibliotecaEditorState,
    key_prefix: str,
    lineas_disponibles: list[str],
    *,
    buffer_key: str,
    widget_key: str | None = None,
    editando: bool = False,
) -> None:
    """Selector de líneas libres en la biblioteca (multiselect + filtros)."""
    if not editando:
        return
    with st.expander(
        "Elegir líneas libres en esta biblioteca (opcional)",
        expanded=False,
    ):
        st.caption(
            f"**{len(lineas_disponibles):,}** línea(s) del pilar **sin asignar** "
            f"a ningún caso de esta biblioteca. Filtrá y elegí las que quieras agregar."
        )
        marca_fk = _render_selector_marca_pilar(
            state, key_prefix, lineas_disponibles=lineas_disponibles
        )
        filtro = st.text_input(
            "Filtrar por código",
            key=f"{key_prefix}_filtro_marca",
            placeholder="Ej: 11 — muestra 1184, 1185…",
        )
        opts = _aplicar_filtros_lineas_pilar(
            state, lineas_disponibles, marca_fk, filtro
        )
        if marca_fk or filtro.strip():
            st.caption(
                f"**{len(opts):,}** línea(s) libres coinciden "
                f"(de {len(lineas_disponibles):,} sin asignar en la biblioteca)"
            )

        max_ms = 600
        opts_ms = opts[:max_ms]
        if len(opts) > max_ms:
            st.caption(
                f"Lista desplegable: primeras **{max_ms}** de **{len(opts):,}**. "
                f"Afiná marca o código, o usá «Añadir todas las filtradas»."
            )
        elegidas = st.multiselect(
            "Líneas libres (elegí una o varias)",
            options=opts_ms,
            key=f"{key_prefix}_libres_ms",
            help="Solo líneas que no están en otro caso de esta biblioteca.",
        )

        c_sel, c_todas = st.columns(2)
        if c_sel.button(
            "➕ Añadir seleccionadas al listado",
            key=f"{key_prefix}_libres_sel",
            use_container_width=True,
            disabled=not elegidas,
        ):
            _anexar_lineas_al_editor(state, buffer_key, widget_key, elegidas)
        if c_todas.button(
            f"➕ Añadir todas las filtradas ({len(opts):,})",
            key=f"{key_prefix}_libres_todas",
            use_container_width=True,
            disabled=not opts,
        ):
            _anexar_lineas_al_editor(state, buffer_key, widget_key, opts)


def _render_contenedor_lineas_simple(
    state: BibliotecaEditorState,
    caso_nombre: str,
    caso_key: str,
) -> None:
    """Líneas visibles como texto; edición y persistencia directa al guardar."""
    data = state.casos.get(caso_key, {})
    lineas = data.get("lineas") or set()
    if isinstance(lineas, list):
        lineas = set(lineas)
    n_lin = len(lineas)
    disponibles = state.lineas_disponibles_para(caso_nombre)
    n_otros = len(state.lineas_ocupadas_en_otros_casos(caso_nombre))

    st.markdown(f"**Líneas del caso** — {n_lin:,} asignada(s)")
    st.caption(
        f"Editá la lista como texto (comas o una por línea, rangos 520-530). "
        f"**{len(disponibles):,}** libres · **{n_otros:,}** en otros casos. "
        f"Si pegás una línea **nueva** (ej. 1492), al guardar se crea en el pilar "
        f"copiando la línea inferior (1490) y sus referencias."
    )

    sk_edit = f"bib_edit_lista_{caso_key}"
    sk_text = f"bib_lista_text_{caso_key}"
    editando = bool(st.session_state.get(sk_edit, False))

    sorted_lines = sorted(lineas, key=_sort_key_linea)
    texto_actual = _lineas_a_texto_lista(sorted_lines)
    altura = min(520, 140 + max(n_lin, 1) // 2)

    if editando:
        st.caption(
            "Al **Guardar lista** se reemplaza el contenedor en la base de datos "
            "(asignación directa)."
        )
        ta_key = f"bib_lista_ta_{caso_key}"
        if ta_key not in st.session_state:
            st.session_state[ta_key] = st.session_state.get(sk_text, texto_actual)
        st.text_area(
            "Líneas",
            height=altura,
            key=ta_key,
            label_visibility="collapsed",
        )
        _render_ayuda_marca_opcional(
            state,
            f"bib_{caso_key}",
            disponibles,
            buffer_key=sk_text,
            widget_key=ta_key,
            editando=True,
        )
    else:
        ver_key = f"bib_lista_ver_{caso_key}"
        if ver_key in st.session_state:
            del st.session_state[ver_key]
        placeholder = (
            "(sin líneas — pulsá Editar lista para pegar códigos o rangos)"
            if not texto_actual
            else texto_actual
        )
        st.text_area(
            "Líneas",
            value=placeholder,
            height=max(140, altura),
            disabled=True,
            key=ver_key,
            label_visibility="collapsed",
        )

    c_edit, c_ref = st.columns(2)
    if not editando:
        if c_edit.button(
            "✏️ Editar lista",
            type="primary",
            key=f"bib_edit_lista_btn_{caso_key}",
            use_container_width=True,
        ):
            st.session_state[sk_edit] = True
            st.session_state[sk_text] = texto_actual
            st.rerun()
        if c_ref.button(
            "↻ Actualizar vista",
            key=f"bib_refresh_lista_{caso_key}",
            use_container_width=True,
        ):
            st.session_state[sk_text] = texto_actual
            st.rerun()
    else:
        if c_edit.button(
            "💾 Guardar lista",
            type="primary",
            key=f"bib_save_lista_{caso_key}",
            use_container_width=True,
        ):
            texto = _texto_lineas_widget(sk_text, ta_key)
            nueva, errs = _parse_lista_lineas_desde_editor(texto)
            if errs:
                st.warning("; ".join(errs[:8]))
            if not nueva and texto.strip():
                st.error("No se reconoció ningún código de línea en el texto.")
            else:
                nq, na, err = _aplicar_lista_lineas_editada(
                    state,
                    caso_nombre,
                    caso_key,
                    nueva,
                    evento_id=_evento_id_para_alta_pilar(),
                )
                if err:
                    st.error(err)
                else:
                    en_bd = recargar_lineas_caso_desde_bd(state, caso_key)
                    st.session_state["bib_editor_state"] = state
                    st.success(
                        f"Guardado: **{len(en_bd):,}** línea(s) en BD "
                        f"({nq:,} quitadas, {na:,} agregadas)."
                    )
                    st.session_state[sk_edit] = False
                    merged = _lineas_a_texto_lista(sorted(en_bd, key=_sort_key_linea))
                    st.session_state[sk_text] = merged
                    for k in (ta_key, f"bib_lista_ver_{caso_key}"):
                        if k in st.session_state:
                            del st.session_state[k]
            st.rerun()
        if c_ref.button(
            "Cancelar",
            key=f"bib_cancel_lista_{caso_key}",
            use_container_width=True,
        ):
            st.session_state[sk_edit] = False
            st.session_state[sk_text] = texto_actual
            st.rerun()


def render_editor_biblioteca(
    proveedor_id: int,
    evento_id: int | None = None,
) -> None:
    state: BibliotecaEditorState | None = st.session_state.get("bib_editor_state")
    if state is not None and state.pilar_lineas and not state.pilar_marca_por_codigo:
        _cod, cod_marca, marcas, sin_marca = cargar_pilar_datos(state.proveedor_id)
        state.pilar_marca_por_codigo = cod_marca
        state.pilar_marcas = marcas
        state.pilar_tiene_sin_marca = sin_marca
        st.session_state["bib_editor_state"] = state
    if state is None:
        st.error("No hay biblioteca en edición.")
        if st.button("← Volver"):
            st.session_state.pop("bib_editor_en_catalogo", None)
            st.session_state["re_paso"] = 0
            st.rerun()
        return

    inject_glass_styles()
    _render_editar_nombre_biblioteca(state)
    n_pilar, n_asig, n_libres = state.resumen_lineas_biblioteca()
    pct_asig = round(100.0 * n_asig / n_pilar, 1) if n_pilar else 0.0
    st.caption(
        f"ID biblioteca **{state.biblioteca_id}** · "
        f"Pilar **{n_pilar:,}** · Asignadas **{n_asig:,}** ({pct_asig}%) · "
        f"Libres **{n_libres:,}** · **{len(state.casos)}** caso(s)"
    )
    _render_alta_linea_pilar(state)
    st.info(
        "**Dentro de esta biblioteca van los casos comerciales** (NORMAL, PROMOCIONALES, índices). "
        "Cada caso tiene **fórmula de precio** + **contenedor de líneas** exclusivo "
        "(una línea del pilar solo en un caso por biblioteca). "
        "Al pulsar **Crear caso** o **Guardar lista** se persisten líneas por caso; "
        "**Guardar biblioteca** (arriba) es el paso final que sincroniza toda la biblioteca en BD."
    )
    if not state.biblioteca_id:
        st.error(
            "Esta sesión no tiene biblioteca en BD. Volvé al catálogo y usá "
            "**Crear biblioteca y abrir editor**."
        )

    conflictos = state.validar_exclusividad_global()
    if conflictos:
        st.error(
            "Hay líneas en más de un caso: " + "; ".join(conflictos[:6])
        )

    if evento_id:
        nav1, nav_cnt, nav2, nav3 = st.columns([1, 3, 1, 1])
    else:
        nav1, nav_cnt, nav2 = st.columns([1, 3, 1])
        nav3 = None

    with nav_cnt:
        c_p, c_a, c_l = st.columns(3)
        c_p.metric("Líneas pilar", f"{n_pilar:,}")
        c_a.metric(
            "Asignadas",
            f"{n_asig:,}",
            help=f"{pct_asig}% de las líneas del pilar",
        )
        c_l.metric("Sin asignar", f"{n_libres:,}")
        st.caption(
            "Los cambios de líneas por caso se guardan con **Guardar lista**. "
            "**Guardar biblioteca** confirma toda la biblioteca (parámetros + líneas)."
        )

    if nav1.button("← Volver"):
        desde_catalogo = bool(st.session_state.get("bib_editor_en_catalogo"))
        st.session_state.pop("bib_editor_state", None)
        st.session_state.pop("bib_editor_en_catalogo", None)
        if desde_catalogo:
            st.rerun()
        elif evento_id:
            st.session_state["re_paso"] = "bib_select"
            st.rerun()
        else:
            st.session_state["re_paso"] = 0
            st.rerun()
    if nav2.button("💾 Guardar biblioteca", type="primary"):
        nom_w = str(st.session_state.get("bib_editor_nombre", state.nombre) or "").strip()
        if nom_w and nom_w != state.nombre:
            state.nombre = nom_w
            st.session_state["bib_editor_state"] = state
        if not state.casos:
            st.warning(
                "Primero creá al menos **un caso comercial** abajo "
                "(ej. NORMAL, PROMOCIONALES) y asignale líneas."
            )
        else:
            st.session_state["bib_pending_save"] = True
            st.rerun()
    if nav3 is not None and evento_id and nav3.button("✅ Aplicar al listado y continuar"):
        bid, err, ok, msg, n = None, "", False, "", 0
        with proceso_largo("Aplicando al listado", "Guardando y copiando…") as avanzar:
            avanzar(0.15, "Guardando biblioteca…")
            bid, err = guardar_estado_biblioteca(state, modo="sustituir")
            if not err:
                avanzar(0.5, "Copiando al evento…")
                ok, msg, n = aplicar_biblioteca_a_evento(
                    evento_id, proveedor_id, bid or state.biblioteca_id
                )
                if ok:
                    st.session_state["re_casos_evento"] = hydrate_casos_evento_desde_db(
                        evento_id
                    )
            avanzar(1.0, "Listo")
        if err:
            st.error(err)
            return
        if not ok:
            st.error(msg)
            return
        st.session_state["re_casos_evento_hydrated"] = evento_id
        celebrate_step("Biblioteca", f"{n} caso(s) al listado", modulo="Motor de Precios")
        st.session_state.pop("bib_editor_state", None)
        _ir_a_paso_1()

    st.markdown("### 1. Casos comerciales (obligatorio)")
    if not state.casos:
        st.warning(
            "Esta biblioteca está **vacía** (0 casos). Usá el formulario de abajo para crear "
            "el primer caso y luego asigná sus líneas."
        )

    solo_un_caso = len(state.casos) == 1
    for idx, (caso_key, data) in enumerate(list(state.casos.items())):
        nombre = str(data.get("nombre_caso", caso_key))
        lineas = data.get("lineas") or set()
        n_lin = len(lineas) if isinstance(lineas, (set, list)) else 0
        expandir = solo_un_caso or idx == 0
        with st.expander(
            f"📂 {nombre} — {n_lin} línea(s) · "
            f"índice {int((float(data.get('dolar_politica') or 8000) * float(data.get('factor_conversion') or 180)) / 100):,} Gs",
            expanded=expandir,
        ):
            c1, c2 = st.columns(2)
            data["dolar_politica"] = c1.number_input(
                "Dólar de política (Gs)",
                value=float(data.get("dolar_politica") or 8000),
                min_value=1.0,
                step=100.0,
                key=f"bib_d_{caso_key}",
            )
            data["factor_conversion"] = c2.number_input(
                "Factor",
                value=float(data.get("factor_conversion") or 180),
                min_value=1.0,
                step=1.0,
                key=f"bib_f_{caso_key}",
            )
            st.caption(
                f"índice = {int((data['dolar_politica'] * data['factor_conversion']) / 100):,} "
                "Gs / USD FOB"
            )
            _render_fila_descuentos(data, f"bib_{caso_key}")
            data["genera_lpc03_lpc04"] = st.toggle(
                "Genera LPC03 y LPC04",
                value=bool(data.get("genera_lpc03_lpc04", True)),
                key=f"bib_lpc_{caso_key}",
            )
            state.dirty = True
            st.markdown("---")
            _render_contenedor_lineas_simple(state, nombre, caso_key)

    with st.expander("➕ Agregar caso comercial", expanded=not bool(state.casos)):
        st.caption("Ej: NORMAL · PROMOCIONALES · indices16-05-2026")
        nuevo = st.text_input("Nombre del caso", key="bib_nuevo_caso_nombre")
        c1, c2 = st.columns(2)
        dolar_n = c1.number_input(
            "Dólar de política (Gs)",
            value=8000.0,
            min_value=1.0,
            step=100.0,
            key="bib_new_d",
        )
        factor_n = c2.number_input(
            "Factor",
            value=180.0,
            min_value=1.0,
            step=1.0,
            key="bib_new_f",
        )
        st.caption(f"índice = {int((dolar_n * factor_n) / 100):,} Gs / USD FOB")
        draft: dict = {}
        _render_fila_descuentos(draft, "bib_new")
        genera_lpc = st.toggle("Genera LPC03 y LPC04", value=True, key="bib_new_lpc")

        libres_nuevo = state.lineas_huerfanas_nuevo_caso()
        ocupadas_bib = state.todas_lineas_ocupadas()
        st.markdown("**Líneas del caso (texto, opcional)**")
        st.caption(
            f"Pegá códigos separados por coma o uno por línea. "
            f"**{len(libres_nuevo):,}** libres · "
            f"**{len(ocupadas_bib):,}** ya en otros casos."
        )
        buf_nuevo = "bib_new_lineas_buf"
        ta_nuevo = "bib_new_lineas_ta"
        st.text_area(
            "Líneas iniciales",
            value=st.session_state.get(buf_nuevo, ""),
            height=160,
            key=ta_nuevo,
            label_visibility="collapsed",
            placeholder="Ej: 1122, 1123 o 520-600",
        )
        _render_ayuda_marca_opcional(
            state,
            "bib_new",
            libres_nuevo,
            buffer_key=buf_nuevo,
            widget_key=ta_nuevo,
            editando=True,
        )

        if st.button("Crear caso en esta biblioteca", type="primary", key="bib_nuevo_caso_btn"):
            if not nuevo.strip():
                st.error("Nombre obligatorio.")
            else:
                texto_ini = _texto_lineas_widget(buf_nuevo, ta_nuevo)
                lineas_set, errs_parse = _parse_lista_lineas_desde_editor(texto_ini)
                if errs_parse:
                    st.warning("; ".join(errs_parse[:8]))
                faltan_pilar = sorted(c for c in lineas_set if c not in set(state.pilar_lineas))
                if faltan_pilar:
                    _, altas_err = provisionar_lineas_faltantes_en_pilar(
                        state.proveedor_id,
                        faltan_pilar,
                        evento_id=_evento_id_para_alta_pilar(),
                    )
                    if altas_err:
                        st.error("; ".join(altas_err[:6]))
                        return
                    _refrescar_pilar_en_estado(state)
                    lineas_set = {c for c in lineas_set if c in set(state.pilar_lineas)}
                en_otros = state.todas_lineas_ocupadas()
                conflictos = sorted(lineas_set & en_otros)
                if conflictos:
                    st.error(
                        "Líneas ya en otro caso: "
                        + ", ".join(conflictos[:8])
                    )
                    return
                params = {
                    "nombre_caso": nuevo.strip(),
                    "dolar_politica": float(dolar_n),
                    "factor_conversion": float(factor_n),
                    "genera_lpc03_lpc04": genera_lpc,
                    "lineas": lineas_set,
                    **{k: draft.get(k) for k in (
                        "descuento_1", "descuento_2", "descuento_3", "descuento_4"
                    )},
                }
                clave = state.ensure_caso(nuevo.strip(), params)
                st.session_state["bib_editor_state"] = state
                caso_id, err_persist = persistir_un_caso_biblioteca(state, clave)
                if err_persist:
                    st.error(f"No se guardó en base de datos: {err_persist}")
                    st.info(
                        "El caso quedó en memoria. Revisá la migración 044 o pulsá "
                        "**Guardar biblioteca** arriba."
                    )
                    return
                n_asig = len(lineas_set)
                st.success(
                    f"Caso «{nuevo.strip()}» guardado en la biblioteca (id caso {caso_id})"
                    + (f" con {n_asig} línea(s)." if n_asig else ". Asigná líneas en el acordeón.")
                )
                st.session_state[buf_nuevo] = ""
                st.session_state.pop(ta_nuevo, None)
                st.session_state.pop(f"_bib_list_cache_{proveedor_id}", None)
                st.rerun()

    st.markdown("---")
    st.markdown("### 2. Persistir en base de datos")
    if st.session_state.get("bib_pending_save"):
        _render_modal_guardar_bifurcacion(state)
    else:
        st.caption(
            "Cuando los casos y líneas estén listos, pulsá **Guardar biblioteca** arriba."
        )


def render_maestro_bibliotecas_tab(proveedor_id: int) -> None:
    """Paso 1 del proceso: crear biblioteca → casos → líneas (sin tocar re_paso del flujo Excel)."""
    mig = mensaje_si_falta_migracion_biblioteca()
    if mig:
        st.error(mig)
        return

    if st.session_state.get("bib_editor_state") and st.session_state.get(
        "bib_editor_en_catalogo"
    ):
        if st.button("← Volver al listado de bibliotecas", key="bib_back_cat"):
            st.session_state.pop("bib_editor_state", None)
            st.session_state.pop("bib_editor_en_catalogo", None)
            st.rerun()
        render_editor_biblioteca(proveedor_id, None)
        return

    st.info(
        "**Paso 1 — Maestro de bibliotecas:** creá la biblioteca, agregá casos comerciales "
        "y asigná líneas por caso. Después importá el Excel en **Nuevo Evento**."
    )

    df = listar_bibliotecas(proveedor_id)
    nombre = st.text_input(
        "Nueva biblioteca",
        key="bib_tab_new",
        placeholder="Ej: Biblioteca Temporada Invierno 2026",
    )
    if st.button("➕ Crear biblioteca y abrir editor", type="primary", key="bib_tab_create"):
        if not nombre.strip():
            st.warning("Escribí un nombre.")
        else:
            bid, err = crear_biblioteca(proveedor_id, nombre.strip())
            if err:
                st.error(err)
            elif bid:
                st.session_state.pop(f"_bib_list_cache_{proveedor_id}", None)
                with proceso_largo("Abriendo editor", "Cargando pilar de líneas…") as avanzar:
                    avanzar(0.5, "Cargando…")
                    _abrir_editor_catalogo(proveedor_id, bid)
                    avanzar(1.0, "Listo")
                if not st.session_state.get("bib_editor_state"):
                    st.error(
                        "La biblioteca se creó en BD pero no se pudo abrir el editor. "
                        f"ID biblioteca: {bid}. Probá **Abrir editor** en la lista."
                    )
                else:
                    celebrate_save(
                        f"Biblioteca «{nombre.strip()}» creada (id {bid})",
                        modulo="Motor de Precios",
                    )
                    st.rerun()
            else:
                st.error("No se pudo crear la biblioteca (sin ID). Revisá la consola [BIB].")

    if df is None or df.empty:
        return

    st.markdown("---")
    opts = {str(r["nombre"]): int(r["id"]) for _, r in df.iterrows()}
    label = st.selectbox("Biblioteca existente", list(opts.keys()), key="bib_tab_sel")
    bid = opts[label]
    c1, c2 = st.columns(2)
    if c1.button("✏️ Abrir editor", key="bib_tab_open"):
        with proceso_largo("Abriendo editor", label) as avanzar:
            avanzar(0.5, "Cargando…")
            _abrir_editor_catalogo(proveedor_id, bid)
            avanzar(1.0, "Listo")
        st.rerun()
    if c2.button("📋 Duplicar", key="bib_tab_dup"):
        nuevo = st.text_input("Nombre copia", value=f"{label} — copia", key="bib_tab_dup_name")
        if nuevo.strip():
            nid, err = duplicar_biblioteca(proveedor_id, bid, nuevo.strip())
            if err:
                st.error(err)
            else:
                celebrate_save(f"Copia creada (id {nid})", modulo="Motor de Precios")
                st.rerun()
