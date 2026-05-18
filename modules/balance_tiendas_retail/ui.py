# =============================================================================

# UI: Retail — importación Excel → staging Supabase (único propósito)

# =============================================================================



from __future__ import annotations



from collections.abc import Callable

from pathlib import Path



import pandas as pd

import streamlit as st



from modules.balance_tiendas_retail import logic as bt
from core.ux_celebrate import celebrate_import_done, celebrate_save

from modules.balance_tiendas_retail.stats_grid import render_retail_aggrid





def _migration_sql_path(name: str) -> Path:

    return Path(__file__).resolve().parents[2] / "migrations" / name





def _read_sql_file(name: str) -> str:

    p = _migration_sql_path(name)

    if p.is_file():

        return p.read_text(encoding="utf-8")

    return f"-- Archivo no encontrado: {p}\n"





def _staging_table_missing(exc: BaseException) -> bool:

    s = str(exc).lower()

    return "retail_multitienda_staging" in s and (

        "does not exist" in s or "undefinedtable" in s

    )





def _render_staging_missing_ui(exc: BaseException) -> None:

    st.error(

        "En Supabase falta la tabla `public.retail_multitienda_staging` o políticas RLS. "

        "Ejecutá **030**, luego **031** (si usás RLS), **033** (FKs) y **035** (códigos Excel material/color para fotos)."

    )

    with st.expander("030 — crear tabla", expanded=True):

        st.code(_read_sql_file("030_retail_multitienda_staging.sql"), language="sql")

    with st.expander("031 — políticas RLS (tras Run and enable RLS)"):

        st.code(_read_sql_file("031_retail_multitienda_staging_rls.sql"), language="sql")

    with st.expander("033 — FKs desde pilares (sin columnas extra en Excel)"):

        st.code(_read_sql_file("033_retail_staging_fk_dims.sql"), language="sql")

    with st.expander("035 — columnas excel_material_code / excel_color_code (nombres de foto en Storage)"):

        st.code(_read_sql_file("035_retail_staging_excel_pillar_codes.sql"), language="sql")

    st.caption(f"Detalle: {exc}")





def _list_batches_safe(engine) -> tuple[pd.DataFrame, BaseException | None]:

    try:

        return bt.list_batches(engine), None

    except Exception as e:

        return pd.DataFrame(), e





def _run_with_progress(

    title: str,

    wait_hint: str,

    fn: Callable[[], None],

) -> None:

    """

    Bloque visual de proceso largo: aviso, barra de progreso y estado expandido.

    El usuario no debe cerrar la pestaña hasta que termine.

    """

    st.warning(

        f"**{wait_hint}** No cierres esta pestaña ni cambies de módulo hasta que finalice."

    )

    progress = st.progress(0.0, text="Iniciando…")

    status = st.status(title, expanded=True)



    def _cb(msg: str, pct: float | None) -> None:

        status.update(label=msg)

        if pct is not None:

            progress.progress(min(1.0, max(0.0, pct)), text=msg)



    try:

        fn(_cb)

        status.update(label="Proceso completado.", state="complete")

        progress.progress(1.0, text="Listo")

    except Exception:

        status.update(label="El proceso falló. Revisá el mensaje de error abajo.", state="error")

        progress.empty()

        raise





def _render_excel_import(

    engine,

    batches: pd.DataFrame,

    batches_exc: BaseException | None,

    created_by: str,

) -> None:

    st.markdown("### Importar archivo Excel")

    st.caption(

        "Cada importación **borra todo** `public.retail_multitienda_staging` y deja **solo** "

        "este archivo. Lo permanente es el **catálogo pilares** (línea, referencia, material, color, …) "

        "que se enriquece con combinaciones nuevas al resolver FKs."

    )

    st.info(

        "Al pulsar **Importar**, el sistema enriquece pilares y graba staging. "

        "En archivos grandes puede tardar **varios minutos**; verás una barra de progreso — "

        "**no cierres la página** hasta el mensaje de éxito."

    )

    st.code(

        "Tienda | Tipo | Fecha | Linea | Referencia | Material | Color | Grada | "

        "Cantidad | Precio unitario VENTA | Monto",

        language="text",

    )

    f = st.file_uploader("Archivo Excel (.xlsx / .xls)", type=["xlsx", "xls"], key="retail_xlsx_up")

    batch_label = st.text_input("Etiqueta del lote (opcional)", placeholder="Mayo 2026", key="retail_batch_lbl")



    importing = st.session_state.get("retail_import_running", False)



    if f:

        name = (getattr(f, "name", None) or "").lower()

        eng = "xlrd" if name.endswith(".xls") and not name.endswith(".xlsx") else "openpyxl"

        try:

            raw, sheet_names, sheet_meta = bt.read_excel_all_sheets(f, engine=eng)

        except Exception as e:

            st.error(f"No se pudo leer el Excel: {e}")

            raw, sheet_names, sheet_meta = None, [], []

        if raw is not None and not raw.empty:

            if sheet_names:

                st.caption(

                    f"Hojas detectadas: **{', '.join(sheet_names)}** — **{len(raw)}** filas combinadas."

                )

            norm, errs = bt.normalize_excel_dataframe(raw)

            c1, c2, c3 = st.columns(3)

            c1.metric("Filas leídas", len(raw))

            c2.metric("Filas normalizadas", len(norm))

            c3.metric("Avisos", len(errs))

            with st.expander("Diagnóstico por hoja", expanded=False):

                if sheet_meta:

                    st.dataframe(pd.DataFrame(sheet_meta), hide_index=True, width="stretch")

            with st.expander("Previsualización del Excel crudo (opcional)", expanded=False):

                st.dataframe(raw, height=min(400, 24 * max(8, len(raw))), width="stretch")

            for e in errs:

                st.warning(e)

            blocked = len(errs) > 0

            if st.button(

                "⬆️ Importar a Supabase",

                type="primary",

                disabled=blocked or importing,

                key="retail_do_imp",

            ):

                if not blocked:

                    st.session_state["retail_import_running"] = True

                    result: dict[str, object] = {}



                    def _do_import(progress_cb: Callable[[str, float | None], None]) -> None:

                        result["batch_id"] = bt.insert_batch(

                            engine,

                            norm,

                            batch_label=batch_label or None,

                            archivo_origen=f.name,

                            created_by=created_by,

                            progress_cb=progress_cb,

                        )



                    try:

                        _run_with_progress(

                            title="Importando Excel a Supabase…",

                            wait_hint="Importación en curso.",

                            fn=_do_import,

                        )

                        nb = str(result["batch_id"])

                        n_db = bt.count_batch_rows(engine, nb)

                        celebrate_import_done(
                            f"Lote `{nb[:8]}…` — {n_db} filas en base (DataFrame {len(norm)})",
                            modulo="Retail Staging",
                        )

                        if n_db != len(norm):

                            st.error("Conteo distinto: revisá RLS o ejecutá migraciones 031/033.")

                    except Exception as e:

                        if _staging_table_missing(e):

                            _render_staging_missing_ui(e)

                        else:

                            st.error(f"Fallo al insertar: {e}")

                    finally:

                        st.session_state["retail_import_running"] = False

        elif raw is not None and raw.empty and sheet_meta:

            st.warning("Archivo sin filas de datos útiles.")

            st.dataframe(pd.DataFrame(sheet_meta), hide_index=True, width="stretch")



    st.divider()

    st.markdown("### Lotes importados")

    if batches_exc is None and batches is not None and not batches.empty:

        render_retail_aggrid(batches, key="retail_batches_grid", height=260)

        del_id = st.selectbox(

            "Eliminar lote",

            options=[""] + batches["batch_id"].tolist(),

            format_func=lambda x: "(ninguno)" if x == "" else str(x)[:8] + "…",

            key="retail_del_batch",

        )

        if del_id and st.button("🗑️ Borrar lote", key="retail_del_btn"):

            with st.spinner("Eliminando lote…"):

                n = bt.delete_batch(engine, del_id)

            celebrate_save(
                f"Eliminadas {n} filas del lote",
                modulo="Retail Staging",
                contexto="guardado",
                balloons=False,
            )
            st.rerun()

    elif batches_exc is None:

        st.info("Todavía no hay lotes importados.")





def render_balance_tiendas_retail(engine, **kwargs):

    if engine is None:

        st.error("Motor de base de datos no disponible.")

        return



    user = st.session_state.get("user") or {}

    created_by = str(user.get("name") or user.get("id") or "nexus")



    st.markdown("## 🏪 Retail — importación Excel")

    st.caption(

        "Subí el Excel multi-tienda: se valida, se **reemplaza por completo** el staging y se "

        "enriquecen **pilares** con combinaciones nuevas. No acumula lotes viejos en staging."

    )



    batches, batches_exc = _list_batches_safe(engine)

    if batches_exc is not None and _staging_table_missing(batches_exc):

        _render_staging_missing_ui(batches_exc)

        return

    if batches_exc is not None:

        st.error(f"No se pudo leer lotes: {batches_exc}")

        return



    if batches is not None and not batches.empty:

        with st.expander("Mantenimiento: recalcular marcas / FKs en un lote", expanded=False):

            st.caption(

                "Si las filas quedaron con **Otros (retail staging)** pero el catálogo pilares ya tiene "

                "la marca correcta, recalculá las FK sin volver a subir el Excel."

            )

            bid_maint = st.selectbox(

                "Lote",

                options=batches["batch_id"].tolist(),

                format_func=lambda x: str(x)[:8] + "…",

                key="retail_maint_batch",

            )

            if st.button("Recalcular marcas / FKs desde pilares", key="retail_refresh_fk"):

                try:

                    def _refresh(_cb: Callable[[str, float | None], None]) -> None:

                        _cb("Recalculando FKs en staging…", 0.5)

                        n = bt.refresh_batch_fks(engine, str(bid_maint))

                        _cb(f"Actualizadas {n} filas.", 1.0)



                    _run_with_progress(

                        title="Recalculando FKs…",

                        wait_hint="Mantenimiento en curso.",

                        fn=_refresh,

                    )

                    celebrate_save(
                        "FKs recalculadas desde pilares",
                        modulo="Retail Staging",
                        contexto="guardado",
                        balloons=False,
                    )

                    st.rerun()

                except Exception as e:

                    st.error(str(e))



    with st.expander("⚠️ Mantenimiento: vaciar staging sin importar", expanded=False):

        st.warning(

            "Normalmente **no hace falta**: cada import ya vacía `retail_multitienda_staging` "

            "antes de grabar. Usá esto solo si querés dejar la tabla vacía sin cargar un Excel."

        )

        conf = st.checkbox("Sí: quiero borrar todo el staging.", key="retail_purge_conf")

        token = st.text_input(

            "Para confirmar, escribí en mayúsculas: VACIAR",

            value="",

            key="retail_purge_token",

        )

        if conf and token.strip().upper() == "VACIAR":

            if st.button("Eliminar todos los registros de staging", type="primary", key="retail_purge_btn"):

                try:

                    def _purge(_cb: Callable[[str, float | None], None]) -> None:

                        _cb("Vaciando tabla staging…", 0.5)

                        n = bt.delete_all_retail_staging(engine)

                        _cb(f"Eliminadas {n} filas.", 1.0)



                    _run_with_progress(

                        title="Vaciando staging…",

                        wait_hint="Operación en curso.",

                        fn=_purge,

                    )

                    celebrate_save(
                        "Staging vacío. Ya podés importar el Excel de nuevo",
                        modulo="Retail Staging",
                        contexto="purge_reset",
                        balloons=False,
                    )

                    st.rerun()

                except Exception as e:

                    st.error(str(e))



    _render_excel_import(engine, batches, batches_exc, created_by)


