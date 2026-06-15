# UI: Retail — Excel VTA SM (hoja st+vt+RC) → registro_st_vt_rc_reposicion

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from core.ux_celebrate import celebrate_import_done, celebrate_save
from modules.balance_tiendas_retail import st_vt_rc_import as retail
from modules.balance_tiendas_retail.stats_grid import render_retail_aggrid


def _run_with_progress(title: str, wait_hint: str, fn: Callable[[], None]) -> None:
    st.warning(f"**{wait_hint}** No cierres esta pestaña hasta que finalice.")
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
        status.update(label="El proceso falló.", state="error")
        progress.empty()
        raise


def _list_batches_safe(engine) -> tuple[pd.DataFrame, BaseException | None]:
    try:
        return retail.list_batches(engine), None
    except Exception as e:
        return pd.DataFrame(), e


def _render_table_missing(exc: BaseException) -> None:
    st.error(f"Falta la tabla `public.{retail.TABLE_RETAIL}`. Ejecutá la migración 060 en Supabase.")
    p = retail.migration_sql_path()
    if p.is_file():
        with st.expander("SQL migración 060", expanded=True):
            st.code(p.read_text(encoding="utf-8"), language="sql")
    st.caption(f"Detalle: {exc}")


def _render_import_gate(ok: bool, reasons: list[str], diag: dict) -> None:
    """Siempre visible encima del botón Importar — el operador remoto ve el porqué."""
    st.caption(f"Motor import Retail · build `{retail.RETAIL_IMPORT_BUILD}`")
    if ok:
        st.success(
            f"**Listo para importar** — {len(diag.get('columnas_mapeadas', []))} columnas mapeadas · "
            f"{diag.get('filas_calzado', 0)} calzado · {diag.get('filas_confecciones', 0)} confecciones Kyly. "
            "Al importar se **borra** el Retail anterior y queda solo este Excel."
        )
        return
    st.error("**Importar bloqueado** — corregí lo siguiente y volvé a subir el archivo:")
    for i, r in enumerate(reasons, 1):
        st.markdown(f"{i}. {r}")
    st.info(
        "Si no ves build `2026-06-15-b5` arriba: en la PC ejecutá `git pull origin main` en control_central "
        "y reiniciá Streamlit."
    )


def _render_excel_import(engine, created_by: str) -> None:
    st.markdown("### Importar Excel Retail (VTA SM)")
    st.warning(
        "Cada importación **borra todo** lo que había en `registro_st_vt_rc_reposicion` "
        "y deja **solo** este archivo (hoja `st+vt+RC`). Sales Report no se toca."
    )
    if retail.RETAIL_IMPORT_SKIP_CONFECCIONES:
        st.info(
            "**Hotfix activo:** se importa solo **calzado** (TIPO_V2=1/654). "
            "Confecciones Kyly (tipo 2/638) quedan **fuera** hasta nueva OT."
        )
    st.caption(
        f"Hoja: **`{retail.EXCEL_SHEET_RETAIL}`** · build `{retail.RETAIL_IMPORT_BUILD}` · "
        "modo rápido (sin alta automática de pilares en este import)."
    )

    f = st.file_uploader("Archivo .xlsx", type=["xlsx", "xls"], key="retail_xlsx_up")
    batch_label = st.text_input("Etiqueta del lote", key="retail_batch_lbl")

    if not f:
        return

    name = (getattr(f, "name", None) or "").lower()
    eng = "xlrd" if name.endswith(".xls") and not name.endswith(".xlsx") else "openpyxl"
    try:
        raw, sheet_name, meta = retail.read_excel_retail_sheet(f, engine=eng)
    except Exception as e:
        st.error(f"No se pudo leer el Excel: {e}")
        return

    if sheet_name is None:
        st.error(f"No se encontró la hoja `{retail.EXCEL_SHEET_RETAIL}`. Hojas: {[m['hoja'] for m in meta]}")
        st.dataframe(pd.DataFrame(meta), hide_index=True, width="stretch")
        return

    try:
        norm, errs = retail.normalize_retail_dataframe(raw)
    except Exception as e:
        st.error(f"**Error al procesar el Excel:** {type(e).__name__}: {e}")
        st.caption("Si el mensaje es solo un número (ej. 5844), había filas vacías en el Excel — hacé git pull y reiniciá Streamlit.")
        return
    diag = retail.diagnose_retail_import(raw, norm)
    can_import, block_reasons = retail.assess_import_gate(norm, errs, diag)
    _, filter_preview = retail.apply_import_row_filters(norm)
    n_import = filter_preview.get("filas_a_importar", len(norm))
    n_skip_kyly = filter_preview.get("excluidas_confecciones", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hoja", sheet_name)
    c2.metric("Filas Excel", len(norm))
    c3.metric("A importar (calzado)", n_import)
    c4.metric("Kyly excluidas", n_skip_kyly)

    with st.expander("Diagnóstico — columnas que leyó Nexus", expanded=not can_import):
        st.dataframe(pd.DataFrame(diag["columnas_mapeadas"]), hide_index=True, width="stretch")
        if diag.get("muestra_mala"):
            st.markdown("**Ejemplo filas bloqueadas (calzado sin L+R)**")
            st.json(diag["muestra_mala"])
        if diag.get("muestra_ok"):
            st.markdown("**Ejemplo filas OK**")
            st.json(diag["muestra_ok"])

    with st.expander("Hojas del libro"):
        st.dataframe(pd.DataFrame(meta), hide_index=True, width="stretch")
    with st.expander("Vista previa"):
        st.dataframe(norm.head(150), height=360, width="stretch")

    _render_import_gate(can_import, block_reasons, diag)

    if st.button(
        "⬆️ Importar",
        type="primary",
        disabled=not can_import,
        key="retail_do_imp",
        help="Deshabilitado mientras haya errores arriba en rojo." if not can_import else "Reemplazo total Retail",
    ):
        result: dict[str, object] = {}

        def _do(progress_cb: Callable[[str, float | None], None]) -> None:
            bid, n_del, n_ins = retail.insert_batch(
                engine,
                norm,
                batch_label=batch_label or None,
                archivo_origen=f.name,
                excel_sheet=sheet_name,
                created_by=created_by,
                progress_cb=progress_cb,
                replace_all=True,
            )
            result["batch_id"] = bid
            result["n_deleted"] = n_del
            result["n_ins"] = n_ins

        try:
            _run_with_progress("Importando Retail…", "Importación en curso.", _do)
            n_del = int(result.get("n_deleted", 0))
            n_ins = int(result.get("n_ins", 0))
            total = retail.count_all_rows(engine)
            celebrate_import_done(
                f"Reemplazo total: −{n_del} / +{n_ins} filas calzado · total tabla {total}"
                + (f" · Kyly excluidas: {n_skip_kyly}" if n_skip_kyly else ""),
                modulo="Retail",
            )
        except Exception as e:
            if retail.table_missing(e):
                _render_table_missing(e)
            else:
                st.error(f"**Error al importar:** {e}")


def render_balance_tiendas_retail(engine, **kwargs) -> None:
    if engine is None:
        st.error("Motor de base de datos no disponible.")
        return

    user = st.session_state.get("user") or {}
    created_by = str(user.get("name") or user.get("id") or "nexus")

    st.markdown("## 🏪 Retail")
    st.caption(
        "**Retail** = Excel VTA SM, hoja `st+vt+RC`, tabla `registro_st_vt_rc_reposicion`. "
        "**Sales Report** = otro Excel → `registro_ventas_general_v2`."
    )

    batches, batches_exc = _list_batches_safe(engine)
    if batches_exc is not None and retail.table_missing(batches_exc):
        _render_table_missing(batches_exc)
        return
    if batches_exc is not None:
        st.error(str(batches_exc))

    _render_excel_import(engine, created_by)

    st.divider()
    st.markdown("### Lotes importados")
    if batches is not None and not batches.empty:
        render_retail_aggrid(batches, key="retail_batches_grid", height=260)
        del_id = st.selectbox(
            "Eliminar lote",
            options=[""] + batches["batch_id"].tolist(),
            format_func=lambda x: "(ninguno)" if x == "" else str(x)[:8] + "…",
            key="retail_del_batch",
        )
        if del_id and st.button("🗑️ Borrar lote", key="retail_del_btn"):
            n = retail.delete_batch(engine, del_id)
            celebrate_save(f"Eliminadas {n} filas", modulo="Retail", balloons=False)
            st.rerun()
    else:
        st.info("Sin lotes todavía.")
