# =============================================================================
# UI: Retail multi-tienda — Excel staging + estadísticas + reposición
# =============================================================================

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.balance_tiendas_retail import logic as bt
from modules.balance_tiendas_retail.stats_grid import render_retail_aggrid, render_retail_hierarchy_grid
from core.settings import settings


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
        "Ejecutá **030**, luego **031** (si usás RLS) y **033** (FKs marca/género/estilo/tipo_1 + material/color)."
    )
    with st.expander("030 — crear tabla", expanded=True):
        st.code(_read_sql_file("030_retail_multitienda_staging.sql"), language="sql")
    with st.expander("031 — políticas RLS (tras Run and enable RLS)"):
        st.code(_read_sql_file("031_retail_multitienda_staging_rls.sql"), language="sql")
    with st.expander("033 — FKs desde pilares (sin columnas extra en Excel)"):
        st.code(_read_sql_file("033_retail_staging_fk_dims.sql"), language="sql")
    st.caption(f"Detalle: {exc}")


def _list_batches_safe(engine) -> tuple[pd.DataFrame, BaseException | None]:
    try:
        return bt.list_batches(engine), None
    except Exception as e:
        return pd.DataFrame(), e


def _thumb_strip_lr(
    sub_mov: pd.DataFrame,
    lr_df: pd.DataFrame,
    img_idx: dict,
    *,
    n: int = 8,
) -> None:
    """Miniaturas locales para top L+R (usa carpeta de la barra lateral)."""
    if lr_df is None or lr_df.empty:
        return
    if not img_idx:
        st.caption(
            "Sin carpeta de fotos en la **barra lateral** (o ruta vacía): no se muestran miniaturas. "
            "La ruta debe ser accesible desde la misma máquina donde corre Streamlit."
        )
        return
    head = lr_df.head(min(n, len(lr_df)))
    if head.empty:
        return
    st.caption("Fotos (misma carpeta que en la barra lateral) — artículo con más movimiento por L+R")
    cols = st.columns(len(head))
    for i, (_, row) in enumerate(head.iterrows()):
        lc = str(row["linea_code"]).strip()
        rc = str(row["referencia_code"]).strip()
        rep = bt.representative_row_for_linea_ref(sub_mov, lc, rc)
        cap = f"L{lc} R{rc}"
        if "marca" in row and pd.notna(row.get("marca")):
            cap += f" · {row['marca']}"
        with cols[i]:
            if rep is not None:
                path = bt.resolve_image(
                    img_idx,
                    lc,
                    rc,
                    rep.get("material_id"),
                    rep.get("color_id"),
                )
                if path:
                    try:
                        st.image(path, use_container_width=True)
                    except Exception as ex:
                        st.caption(f"No se pudo abrir la imagen: {ex}")
                else:
                    st.caption(
                        "Sin foto — formato proveedor: "
                        "`linea-referencia-material-color.jpg` (ej. `1143-309-5881-47164.jpg`)."
                    )
            else:
                st.caption("Sin fila representativa (L+R) para miniatura.")
            st.caption(cap)


def _render_estadistica_ventas(df: pd.DataFrame, img_idx: dict, *, holding_label: str) -> None:
    v = bt.slice_movimiento(df, "venta")
    if v.empty:
        st.warning("No hay filas **Venta** en este lote.")
        return

    # METRICAS NEXUS
    tot_pares = int(v["cantidad"].sum())
    tot_monto = float(v["monto"].sum())
    n_tiendas = v["origen_tienda"].nunique()
    
    m1, m2, m3 = st.columns(3)
    with m1: card_metric("Pares Vendidos", f"{tot_pares:,}".replace(",", "."))
    with m2: card_metric("Monto Total (Gs)", f"{tot_monto:,.0f}".replace(",", "."))
    with m3: card_metric("Sucursales", str(n_tiendas))

    st.divider()
    st.markdown("### 🏎️ Telemetría de Ventas (F1 Mode)")
    
    # GRAFICOS DE ALTO IMPACTO
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 📈 Ventas por Sucursal")
        r0_chart = bt.resumen_por_tienda(v)
        if not r0_chart.empty:
            st.bar_chart(r0_chart.set_index("origen_tienda")["cantidad"], color="#D4AF37")
            
    with c2:
        st.markdown("#### 🏷️ Top Marcas (Pares)")
        tm_chart = bt.desglose_dim(v, "marca", top=10)
        if tm_chart is not None and not tm_chart.empty:
            st.bar_chart(tm_chart.set_index("marca")["cantidad"], color="#0EA5E9")

    st.markdown("#### 🌍 Resumen Consolidado por Sucursal")
    r0 = bt.resumen_por_tienda(v)
    render_retail_aggrid(r0, key="retail_v_resumen", height=220)

    st.markdown("#### 🌲 Estructura Jerárquica (Holding → Sucursal → Marca → SKU)")
    vtree = v.copy()
    vtree["holding"] = (holding_label or "").strip() or settings.COMPANY_NAME
    vtree["tienda"] = vtree["origen_tienda"].astype(str)
    hcols = ["holding", "tienda", "marca", "linea_code", "referencia_code", "cantidad", "monto"]
    hdf = vtree[[c for c in hcols if c in vtree.columns]].copy()
    req = {"holding", "tienda", "marca", "linea_code", "referencia_code"}
    if req.issubset(hdf.columns):
        render_retail_hierarchy_grid(
            hdf,
            group_cols_en=["holding", "tienda", "marca", "linea_code", "referencia_code"],
            key="retail_v_tree",
            height=520,
        )
    else:
        st.caption("No hay columnas suficientes para la jerarquía.")

    st.markdown("#### 🏷️ Top Marcas (Global)")
    tm = bt.desglose_dim(v, "marca", top=30)
    if tm is not None and not tm.empty:
        render_retail_aggrid(tm, key="retail_v_marcas_global", height=320)
    else:
        st.caption("Sin columna marca o sin datos.")

    st.divider()
    st.markdown("### 🏬 Desglose por Sucursal")
    
    for orig in sorted(v["origen_tienda"].astype(str).unique()):
        st.markdown(f"#### 🏢 Sucursal: {orig}")
        sub = v[v["origen_tienda"].astype(str) == orig]
        
        lr = bt.desglose_linea_referencia(sub, top=40)
        if not lr.empty:
            st.markdown("##### 🔝 Top Artículos")
            render_retail_aggrid(lr, key=f"retail_v_lr_{orig}", height=380)
            _thumb_strip_lr(sub, lr, img_idx)
        
        st.markdown("##### 🔍 Análisis Dimensional")
        dims = st.columns(3)
        with dims[0]:
            t = bt.desglose_dim(sub, "marca", top=15)
            if t is not None and not t.empty:
                st.markdown("**Marcas**")
                render_retail_aggrid(t, key=f"retail_v_marca_{orig}", height=250)
        with dims[1]:
            t = bt.desglose_dim(sub, "genero", top=15)
            if t is not None and not t.empty:
                st.markdown("**Géneros**")
                render_retail_aggrid(t, key=f"retail_v_genero_{orig}", height=250)
        with dims[2]:
            t = bt.desglose_dim(sub, "estilo", top=15)
            if t is not None and not t.empty:
                st.markdown("**Estilos**")
                render_retail_aggrid(t, key=f"retail_v_estilo_{orig}", height=250)
        st.divider()


def _render_estadistica_stock(df: pd.DataFrame, img_idx: dict, *, holding_label: str) -> None:
    s = bt.slice_movimiento(df, "stock")
    if s.empty:
        st.warning("No hay filas **Stock** en este lote.")
        return

    # METRICAS NEXUS
    tot_pares = int(s["cantidad"].sum())
    tot_monto = float(s["monto"].sum())
    
    m1, m2 = st.columns(2)
    with m1: card_metric("Stock Total (Pares)", f"{tot_pares:,}".replace(",", "."))
    with m2: card_metric("Valorización Stock (Gs)", f"{tot_monto:,.0f}".replace(",", "."))

    st.divider()
    st.markdown("### 🏎️ Telemetría de Inventarios")
    
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("#### 📦 Distribución de Stock por Sucursal")
        rs_chart = bt.resumen_por_tienda(s)
        if not rs_chart.empty:
            st.area_chart(rs_chart.set_index("origen_tienda")["cantidad"], color="#10B981")
    
    with sc2:
        st.markdown("#### 💰 Valorización por Marca (Top 10)")
        ts_chart = bt.desglose_dim(s, "marca", top=10)
        if ts_chart is not None and not ts_chart.empty:
            st.bar_chart(ts_chart.set_index("marca")["monto"], color="#F59E0B")

    st.markdown("#### 🌍 Consolidado Stock por Origen")
    render_retail_aggrid(bt.resumen_por_tienda(s), key="retail_s_resumen", height=220)

    st.markdown("#### 🌲 Estructura Stock (Jerarquía)")
    stree = s.copy()
    stree["holding"] = (holding_label or "").strip() or settings.COMPANY_NAME
    stree["tienda"] = stree["origen_tienda"].astype(str)
    hcols = ["holding", "tienda", "marca", "linea_code", "referencia_code", "cantidad", "monto"]
    hdf = stree[[c for c in hcols if c in stree.columns]].copy()
    req = {"holding", "tienda", "marca", "linea_code", "referencia_code"}
    if req.issubset(hdf.columns):
        render_retail_hierarchy_grid(
            hdf,
            group_cols_en=["holding", "tienda", "marca", "linea_code", "referencia_code"],
            key="retail_s_tree",
            height=520,
        )
    else:
        st.caption("No hay columnas suficientes para la jerarquía.")

    st.divider()
    st.markdown("### 🏬 Stock por Sucursal")

    for orig in sorted(s["origen_tienda"].astype(str).unique()):
        st.markdown(f"#### 🏢 Sucursal: {orig}")
        sub = s[s["origen_tienda"].astype(str) == orig]
        
        lr = bt.desglose_linea_referencia(sub, top=40)
        if not lr.empty:
            st.markdown("##### 🔝 Artículos en Stock")
            render_retail_aggrid(lr, key=f"retail_s_lr_{orig}", height=380)
            _thumb_strip_lr(sub, lr, img_idx)

        dims = st.columns(2)
        with dims[0]:
            t = bt.desglose_dim(sub, "marca", top=15)
            if t is not None and not t.empty:
                st.markdown("**Marcas en Stock**")
                render_retail_aggrid(t, key=f"retail_s_marca_{orig}", height=250)
        with dims[1]:
            t = bt.desglose_dim(sub, "genero", top=15)
            if t is not None and not t.empty:
                st.markdown("**Géneros en Stock**")
                render_retail_aggrid(t, key=f"retail_s_genero_{orig}", height=250)
        st.divider()


def _fmt_album_grada_cell(v: float) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or float(v) == 0.0:
        return ""
    fv = float(v)
    if fv == int(fv):
        return str(int(fv))
    return str(fv)


def _album_grada_tables_html(summary: dict) -> str:
    """Tablas estilo mockup: por origen, cabeceras de grada según tienda vs importadora."""
    blocks = summary.get("blocks") or []
    if not blocks:
        return ""

    # Forzar contraste: el tema oscuro de Streamlit hereda color claro sobre nuestro fondo blanco.
    txt = "color:#0f172a !important;"
    bg_w = "background:#ffffff !important;"
    bg_h = "background:#e2e8f0 !important;"
    bg_l = "background:#f1f5f9 !important;"
    bd = "border:1px solid #64748b !important;"
    th_style = f"{bd}{txt}{bg_h}padding:4px 5px;text-align:center;font-weight:600;"
    td_label = f"{bd}{txt}{bg_l}padding:4px 5px;font-weight:700;"
    td_cell = f"{bd}{txt}{bg_w}padding:4px 5px;text-align:center;"
    orig_cell = f"{bd}{txt}{bg_l}padding:6px 5px;text-align:center;vertical-align:middle;font-weight:600;"

    def row_cells(vals: dict, gradas: list[str]) -> str:
        cells: list[str] = []
        for g in gradas:
            t = _fmt_album_grada_cell(float(vals.get(g, 0) or 0))
            cells.append(
                f"<td style='{td_cell}'>{html.escape(t)}</td>" if t else f"<td style='{td_cell}'></td>"
            )
        return "".join(cells)

    parts: list[str] = []
    for blk in blocks:
        gradas = blk.get("gradas") or []
        if not gradas:
            continue
        head_cells = "".join(f"<th style='{th_style}'>{html.escape(str(g))}</th>" for g in gradas)
        orig = html.escape(str(blk.get("origen", "")))
        venta = blk.get("venta") or {}
        stock = blk.get("stock") or {}
        vent_cells = row_cells(venta, gradas)
        stk_cells = row_cells(stock, gradas)
        tbl = f"""<div style="margin-top:10px;overflow-x:auto;padding:4px 2px;border-radius:8px;{bg_w}{txt}">
<table style="width:100%;border-collapse:collapse;font-size:0.74rem;{bg_w}{txt}">
<tr>
<th colspan="2" style="{th_style}"></th>
{head_cells}
</tr>
<tr>
<th rowspan="2" style="{orig_cell}">{orig}</th>
<th style="{td_label}">VENTA</th>
{vent_cells}
</tr>
<tr>
<th style="{td_label}">STOCK</th>
{stk_cells}
</tr>
</table></div>"""
        parts.append(tbl)
    return "".join(parts)


def _render_album(df: pd.DataFrame) -> None:
    idx = st.session_state.get("retail_img_idx") or {}
    if not idx:
        st.info("Definí la carpeta de imágenes en la **barra lateral** para armar el álbum.")
        return
    cand = bt.album_candidates_from_ventas(df, top=24)
    if cand.empty:
        st.warning("No hay ventas para armar el álbum.")
        return
    
    st.markdown("### 🖼️ Vitrina de Éxitos (Álbum)")
    st.caption("Top artículos por venta — Análisis visual de gradas por origen.")
    
    ncols = 4
    for i in range(0, len(cand), ncols):
        cols = st.columns(ncols)
        for j, col in enumerate(cols):
            if i + j >= len(cand):
                break
            row = cand.iloc[i + j]
            with col:
                path = bt.resolve_image(idx, str(row["linea_code"]), str(row["referencia_code"]), row["material_id"], row["color_id"])
                if path: st.image(path, use_container_width=True)
                else: st.caption("Sin foto")
                
                marca = f" · {row['marca']}" if "marca" in row.index and pd.notna(row.get("marca")) else ""
                st.markdown(f"**L{row['linea_code']} R{row['referencia_code']}**{marca}")
                st.caption(f"{int(float(row['venta_pares'])):,} pares".replace(",", "."))
                
                sku_key = row.get("sku_key")
                if sku_key is not None and not pd.isna(sku_key):
                    summ = bt.album_grada_summary_for_sku(df, str(sku_key))
                    if summ:
                        st.markdown(_album_grada_tables_html(summ), unsafe_allow_html=True)


def _render_reposicion(
    engine,
    batches: pd.DataFrame,
    batches_exc: BaseException | None,
    created_by: str,
    df: pd.DataFrame,
    bid: str | None,
) -> None:
    st.markdown("### 📥 Gestión de Datos Excel")
    
    col_up, col_hist = st.columns([1.5, 1])
    
    with col_up:
        st.markdown("#### ⬆️ Importar Nuevo Lote")
        st.caption("Estructura: Tienda | Tipo | Fecha | Linea | Referencia | Material | Color | Grada | Cantidad | Precio Venta | Monto")
        f = st.file_uploader("Archivo Excel", type=["xlsx", "xls"], key="retail_xlsx_up", label_visibility="collapsed")
        batch_label = st.text_input("Etiqueta del lote", placeholder="Ej: Ventas Mayo 2026", key="retail_batch_lbl")
        
        if f:
            name = (getattr(f, "name", None) or "").lower()
            eng = "xlrd" if name.endswith(".xls") and not name.endswith(".xlsx") else "openpyxl"
            try:
                raw, sheet_names, sheet_meta = bt.read_excel_all_sheets(f, engine=eng)
            except Exception as e:
                st.error(f"Error de lectura: {e}")
                raw = None
            
            if raw is not None and not raw.empty:
                norm, errs = bt.normalize_excel_dataframe(raw)
                
                m1, m2, m3 = st.columns(3)
                with m1: card_metric("Filas", str(len(raw)))
                with m2: card_metric("Válidas", str(len(norm)))
                with m3: card_metric("Avisos", str(len(errs)))
                
                st.dataframe(raw.head(100), use_container_width=True, height=250)
                
                for e in errs: st.warning(e)
                
                blocked = len(errs) > 0
                if st.button("🚀 INICIAR IMPORTACIÓN", type="primary", disabled=blocked, key="retail_do_imp", use_container_width=True):
                    with st.spinner("Sincronizando..."):
                        try:
                            nb = bt.insert_batch(engine, norm, batch_label=batch_label or None, archivo_origen=f.name, created_by=created_by)
                            st.success(f"Lote importado con éxito.")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fallo al insertar: {e}")

    with col_hist:
        st.markdown("#### 📜 Historial de Lotes")
        if batches_exc is None and batches is not None and not batches.empty:
            render_retail_aggrid(batches[['batch_id', 'batch_label', 'filas']], key="retail_batches_grid", height=260)
            del_id = st.selectbox("Lote a eliminar", options=[""] + batches["batch_id"].tolist(), key="retail_del_batch")
            if del_id and st.button("⚠️ ELIMINAR", key="retail_del_btn", use_container_width=True):
                n = bt.delete_batch(engine, del_id)
                st.success(f"Purgados {n} registros.")
                st.rerun()
        else:
            st.info("Sin historial.")

    if df.empty or not bid:
        st.divider()
        st.info("Seleccioná un lote activo para ver la vitrina de reposición.")
        return

    st.divider()
    st.markdown("### 🏬 Vitrina de Reposición Inteligente")
    
    idx = st.session_state.get("retail_img_idx") or {}
    top_n = st.slider("Cantidad de SKUs", 4, 48, 12, step=4, key="retail_repo_top")
    
    dff = df.copy()
    top = bt.aggregate_top_skus(dff, top_n=top_n)
    
    if top.empty:
        st.warning("No hay ventas en este lote.")
        return
        
    pivot = bt.pivot_tiendas_stock_venta(dff)
    merged = bt.merge_top_skus_con_pivot(top, pivot)
    
    st.markdown("#### 🏪 Disponibilidad por Origen")
    piv_cols = sorted([c for c in merged.columns if str(c).endswith("_venta") or str(c).endswith("_stock")])
    show_cols = ["sku_key", "linea_code", "referencia_code", "marca", "venta_pares", "venta_gs"]
    disp_cols = [c for c in show_cols + piv_cols if c in merged.columns]
    
    if piv_cols:
        render_retail_aggrid(merged[disp_cols], key="retail_repo_disp_grid", height=400)
    
    st.divider()
    st.markdown("#### 📸 Detalle Visual")
    for _, row in merged.iterrows():
        cimg, ctxt = st.columns([1, 3])
        with cimg:
            path = bt.resolve_image(idx, str(row["linea_code"]), str(row["referencia_code"]), row["material_id"], row["color_id"]) if idx else None
            if path: st.image(path, use_container_width=True)
            else: st.caption("Sin Imagen")
        
        with ctxt:
            marca = f" · **{row['marca']}**" if "marca" in row.index and pd.notna(row.get("marca")) else ""
            st.markdown(f"**L{row['linea_code']} R{row['referencia_code']}**{marca}")
            st.caption(f"SKU: {row['sku_key']}")
            
            m1, m2 = st.columns(2)
            with m1: card_metric("Venta Pares", str(int(row['venta_pares'])))
            with m2: card_metric("Monto (Gs)", f"{float(row['venta_gs']):,.0f}".replace(",", "."))
            
            bits = []
            for k in piv_cols:
                v = row[k]
                v_str = f"{v:,.0f}".replace(",", ".") if isinstance(v, (int, float)) and pd.notna(v) else str(v)
                label = k.replace("_stock", " (📦)").replace("_venta", " (🛒)")
                bits.append(f"**{label}:** {v_str}")
            if bits: st.markdown(" · ".join(bits))
        st.divider()

    with st.expander("📝 Resumen Textual", expanded=False):
        st.text_area("Copy-paste", bt.pivot_resumen_texto(dff, max_skus=30) or "", height=300)


from core.styles import header_section, card_metric, StatusFactory

def render_balance_tiendas_retail(engine, **kwargs):
    if engine is None:
        st.error("Motor de base de datos no disponible.")
        return

    user = st.session_state.get("user") or {}
    created_by = str(user.get("name") or user.get("id") or "nexus")

    header_section("Retail Multi-Tienda", "Inteligencia de Negocio · Nexus Core v100.3.0")

    batches, batches_exc = _list_batches_safe(engine)
    if batches_exc is not None and _staging_table_missing(batches_exc):
        _render_staging_missing_ui(batches_exc)
        return
    if batches_exc is not None:
        st.error(f"No se pudo leer lotes: {batches_exc}")
        return

    holding_label = settings.COMPANY_NAME
    df_work = pd.DataFrame()
    bid_work: str | None = None
    img_idx: dict = st.session_state.get("retail_img_idx") or {}
    if batches is not None and not batches.empty:
        blab = {
            str(r["batch_id"]): (r.get("batch_label") or "", int(r.get("filas") or 0))
            for _, r in batches.iterrows()
        }

        def _fmt_bid(x: str) -> str:
            lab, n = blab.get(x, ("", 0))
            return f"{x[:8]}… — {lab or 'sin etiqueta'} ({n} filas)"

        st.markdown("### 🎯 Selección de Lote")
        bid_work = st.selectbox(
            "Lote activo (todas las pestañas)",
            options=batches["batch_id"].tolist(),
            format_func=_fmt_bid,
            key="retail_global_batch",
            label_visibility="collapsed"
        )
        if bid_work:
            lab, _n = blab.get(str(bid_work), ("", 0))
            if lab and str(lab).strip():
                holding_label = str(lab).strip()
        try:
            df_work = bt.load_batch_df(engine, bid_work)
        except Exception as e:
            st.error(f"No se pudo cargar el lote: {e}")
            if "column" in str(e).lower() and ("does not exist" in str(e).lower() or "undefinedcolumn" in str(e).lower()):
                st.warning("¿Ejecutaste la migración **033** (columnas FK marca_id, …)?")
            df_work = pd.DataFrame()

    if bid_work and not df_work.empty:
        with st.expander("🛠️ Mantenimiento del Lote", expanded=False):
            st.caption(
                "Si las filas quedaron con **Otros (retail staging)** pero el catálogo pilares ya tiene la marca correcta, "
                "recalculá las FK sin volver a subir el Excel."
            )
            if st.button("🔄 Recalcular marcas / FKs desde pilares", key="retail_refresh_fk", use_container_width=True):
                try:
                    n = bt.refresh_batch_fks(engine, str(bid_work))
                    st.success(f"Actualizadas {n} filas de staging.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    t1, t2, t3, t4 = st.tabs(
        [
            "📊 VENTAS",
            "🖼️ ÁLBUM",
            "📦 STOCK",
            "🛒 REPOSICIÓN",
        ]
    )
    with t1:
        if df_work.empty:
            st.info("Importá un lote en **Reposición** o elegí uno del selector.")
        else:
            _render_estadistica_ventas(df_work, img_idx, holding_label=holding_label)
    with t2:
        if df_work.empty:
            st.info("Necesitás un lote con datos para el álbum.")
        else:
            _render_album(df_work)
    with t3:
        if df_work.empty:
            st.info("Importá un lote o elegí uno del selector.")
        else:
            _render_estadistica_stock(df_work, img_idx, holding_label=holding_label)
    with t4:
        _render_reposicion(engine, batches, batches_exc, created_by, df_work, bid_work)
