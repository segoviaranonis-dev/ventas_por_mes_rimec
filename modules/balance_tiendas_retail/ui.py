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


def _render_excel_import(engine, created_by: str) -> None:
    st.markdown("### Importar Excel Retail (VTA SM)")
    st.warning(
        "Cada importación **borra todo** lo que había en `registro_st_vt_rc_reposicion` "
        "y deja **solo** este archivo (hoja `st+vt+RC`). Sales Report no se toca."
    )
    st.caption(
        f"Hoja operativa: **`{retail.EXCEL_SHEET_RETAIL}`**. "
        "Otras hojas del libro no se importan. Pilares: filtros e imágenes."
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
        st.error(f"No se encontró la hoja `{retail.EXCEL_SHEET_RETAIL}`.")
        st.dataframe(pd.DataFrame(meta), hide_index=True, width="stretch")
        return

    norm, errs = retail.normalize_retail_dataframe(raw)
    diag = retail.diagnose_retail_import(raw, norm)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hoja", sheet_name)
    c2.metric("Filas", len(norm))
    c3.metric("Calzado OK", diag["filas_ok"])
    c4.metric("Sin L+R (calzado)", diag["filas_sin_lr"])
    if diag.get("filas_confecciones"):
        st.caption(f"Confecciones Kyly (638 / tipo_v2=2): **{diag['filas_confecciones']}** filas — no exigen línea+referencia.")

    with st.expander("Hojas del libro"):
        st.dataframe(pd.DataFrame(meta), hide_index=True, width="stretch")
    with st.expander("Vista previa"):
        st.dataframe(norm.head(150), height=360, width="stretch")

    if errs:
        st.error("**Import bloqueado** — hay filas sin línea o referencia. Corregí el Excel o revisá el diagnóstico abajo.")
        with st.expander("Diagnóstico — qué columnas leyó Nexus", expanded=True):
            st.caption(
                "**Tipo_v2:** `654` o `1` = calzado Beira Rio (LINEA+REFERENCIA obligatorios). "
                "`638` o `2` = confecciones Kyly (se importa tal cual, sin pilares L+R)."
            )
            st.markdown("**Mapeo columnas Excel → sistema**")
            st.dataframe(pd.DataFrame(diag["columnas_mapeadas"]), hide_index=True, width="stretch")
            if not diag["tiene_columnas_lr"]:
                st.warning(
                    f"No se detectó columna LINEA/REFERENCIA/LINE-REF. "
                    f"Columnas con «line/ref/style» en el Excel: {diag['columnas_lr_en_excel'] or '(ninguna)'}"
                )
            if diag["muestra_ok"]:
                st.markdown("**Ejemplo filas OK**")
                st.json(diag["muestra_ok"])
            if diag["muestra_mala"]:
                st.markdown("**Ejemplo filas bloqueadas**")
                st.json(diag["muestra_mala"])

    for e in errs:
        st.warning(e)

    if st.button("⬆️ Importar", type="primary", disabled=bool(errs) or norm.empty, key="retail_do_imp"):
        result: dict[str, object] = {}

        def _do(progress_cb: Callable[[str, float | None], None]) -> None:
            bid, n_del, n_ins = retail.insert_batch(
                engine, norm,
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
            bid = str(result["batch_id"])
            n_del = int(result.get("n_deleted", 0))
            n_ins = int(result.get("n_ins", 0))
            total = retail.count_all_rows(engine)
            celebrate_import_done(
                f"Reemplazo total: −{n_del} / +{n_ins} filas · total tabla {total}",
                modulo="Retail",
            )
        except Exception as e:
            if retail.table_missing(e):
                _render_table_missing(e)
            else:
                st.error(str(e))


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
