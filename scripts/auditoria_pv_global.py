"""Auditoría PV global vs UI Aprobaciones."""
from __future__ import annotations

import json
from modules.aprobacion_pedidos.logic import get_fi_confirmadas, get_fi_anuladas, get_fi_reservadas
from core.database import get_dataframe

SEP = "=" * 72


def q(sql: str):
    df = get_dataframe(sql)
    return df if df is not None else __import__("pandas").DataFrame()


def main() -> None:
    print(SEP)
    print("1. UNIVERSO pv_global (CONFIRMADA + ANULADA)")
    print(SEP)
    df1 = q("""
        SELECT estado, COUNT(*) AS n,
               COUNT(pv_global) AS con_pv,
               MIN(pv_global) AS min_pv,
               MAX(pv_global) AS max_pv
        FROM factura_interna
        WHERE estado IN ('CONFIRMADA', 'ANULADA', 'RESERVADA')
        GROUP BY estado ORDER BY estado
    """)
    print(df1.to_string(index=False))

    print(f"\n{SEP}\n2. SECUENCIA pv_global — huecos y duplicados\n{SEP}")
    df_seq = q("""
        WITH nums AS (
            SELECT pv_global FROM factura_interna
            WHERE pv_global IS NOT NULL
        ),
        bounds AS (SELECT MIN(pv_global) mn, MAX(pv_global) mx FROM nums),
        series AS (
            SELECT generate_series((SELECT mn FROM bounds), (SELECT mx FROM bounds)) AS expected
        )
        SELECT s.expected AS pv_faltante
        FROM series s
        LEFT JOIN nums n ON n.pv_global = s.expected
        WHERE n.pv_global IS NULL
        ORDER BY s.expected
    """)
    if df_seq.empty:
        print("Sin huecos en 1..MAX(pv_global)")
    else:
        print(f"Huecos: {len(df_seq)}")
        print(df_seq.to_string(index=False))

    df_dup = q("""
        SELECT pv_global, COUNT(*) AS n, STRING_AGG(id::text, ', ') AS fi_ids
        FROM factura_interna
        WHERE pv_global IS NOT NULL
        GROUP BY pv_global HAVING COUNT(*) > 1
    """)
    print("\nDuplicados pv_global:", "ninguno" if df_dup.empty else df_dup.to_string(index=False))

    print(f"\n{SEP}\n3. ERRORES DE NUMERACIÓN\n{SEP}")
    df_err = q("""
        SELECT 'CONFIRMADA sin pv_global' AS error, COUNT(*) AS n
        FROM factura_interna WHERE estado = 'CONFIRMADA' AND pv_global IS NULL
        UNION ALL
        SELECT 'ANULADA sin pv_global', COUNT(*)
        FROM factura_interna WHERE estado = 'ANULADA' AND pv_global IS NULL
        UNION ALL
        SELECT 'RESERVADA con pv_global (no debería)', COUNT(*)
        FROM factura_interna WHERE estado = 'RESERVADA' AND pv_global IS NOT NULL
        UNION ALL
        SELECT 'pv_global en filas no finales', COUNT(*)
        FROM factura_interna
        WHERE pv_global IS NOT NULL AND estado NOT IN ('CONFIRMADA', 'ANULADA')
    """)
    print(df_err.to_string(index=False))

    print(f"\n{SEP}\n4. UI vs BD — tab Confirmadas\n{SEP}")
    ui_conf = get_fi_confirmadas()
    db_conf = q("""
        SELECT fi.id, fi.pv_global, fi.nro_factura, fi.estado, fi.pedido_id,
               fi.total_pares, fi.total_monto, fi.marca, fi.caso,
               fi.cliente_id, fi.vendedor_id, fi.pp_id,
               (SELECT COUNT(*) FROM factura_interna_detalle d WHERE d.factura_id = fi.id) AS n_items
        FROM factura_interna fi
        WHERE fi.estado = 'CONFIRMADA'
        ORDER BY fi.pv_global DESC NULLS LAST
    """)
    print(f"UI get_fi_confirmadas(): {len(ui_conf)} filas (LIMIT 200)")
    print(f"BD CONFIRMADA total:     {len(db_conf)} filas")

    ui_ids = {int(x["id"]) for x in ui_conf}
    db_ids = set(db_conf["id"].astype(int).tolist())
    only_ui = ui_ids - db_ids
    only_db = db_ids - ui_ids
    print(f"IDs solo UI: {len(only_ui)} | solo BD: {len(only_db)}")

    # UI field parity for top 5
    mismatches = []
    db_by_id = {int(r.id): r for r in db_conf.itertuples()}
    for fi in ui_conf:
        fid = int(fi["id"])
        if fid not in db_by_id:
            mismatches.append({"fi_id": fid, "campo": "id", "ui": "presente", "bd": "ausente"})
            continue
        row = db_by_id[fid]
        pairs = [
            ("pv_global", fi.get("pv_global"), row.pv_global),
            ("nro_factura", fi.get("nro_factura"), row.nro_factura),
            ("total_monto", fi.get("total_monto"), row.total_monto),
            ("total_pares", fi.get("total_pares"), row.total_pares),
            ("marca", fi.get("marca"), row.marca),
            ("caso", fi.get("caso"), row.caso),
            ("pedido_id", fi.get("pedido_id"), row.pedido_id),
        ]
        for campo, uv, bv in pairs:
            if str(uv) != str(bv) and not (
                campo == "pv_global" and str(uv) in ("None", "nan") and bv is None
            ):
                mismatches.append({"fi_id": fid, "campo": campo, "ui": uv, "bd": bv})

    print(f"Discrepancias UI vs BD (campos): {len(mismatches)}")
    if mismatches[:10]:
        for m in mismatches[:10]:
            print(f"  fi={m['fi_id']} {m['campo']}: UI={m['ui']} BD={m['bd']}")

    print(f"\n{SEP}\n5. INTEGRIDAD POR FI CONFIRMADA\n{SEP}")
    df_int = q("""
        SELECT
            fi.id,
            fi.pv_global,
            fi.nro_factura,
            fi.pedido_id,
            p.nro_pedido,
            p.estado AS pedido_estado,
            fi.cliente_id,
            c.descp_cliente IS NOT NULL AS ok_cliente,
            fi.vendedor_id,
            v.descp_usuario IS NOT NULL AS ok_vendedor,
            fi.pp_id,
            pp.numero_registro IS NOT NULL AS ok_pp,
            (SELECT COUNT(*) FROM factura_interna_detalle d WHERE d.factura_id = fi.id) AS n_items,
            (SELECT COALESCE(SUM(d.pares),0) FROM factura_interna_detalle d WHERE d.factura_id = fi.id) AS sum_pares_det,
            fi.total_pares,
            (SELECT COALESCE(SUM(d.subtotal),0) FROM factura_interna_detalle d WHERE d.factura_id = fi.id) AS sum_monto_det,
            fi.total_monto
        FROM factura_interna fi
        LEFT JOIN pedido_venta_rimec p ON p.id = fi.pedido_id
        LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
        LEFT JOIN usuario_v2 v ON v.id_usuario = fi.vendedor_id
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        WHERE fi.estado = 'CONFIRMADA'
        ORDER BY fi.pv_global
    """)

    issues = []
    for r in df_int.itertuples():
        pv = r.pv_global
        if pv is None:
            issues.append((r.id, "sin pv_global"))
        if not r.ok_cliente:
            issues.append((r.id, "cliente huérfano"))
        if r.vendedor_id and not r.ok_vendedor:
            issues.append((r.id, "vendedor huérfano"))
        if not r.ok_pp:
            issues.append((r.id, "pp huérfano"))
        if r.n_items == 0:
            issues.append((r.id, "sin detalle"))
        if int(r.sum_pares_det or 0) != int(r.total_pares or 0):
            issues.append((r.id, f"pares cabecera {r.total_pares} != detalle {r.sum_pares_det}"))
        if abs(float(r.sum_monto_det or 0) - float(r.total_monto or 0)) > 1:
            issues.append((r.id, f"monto cabecera {r.total_monto} != detalle {r.sum_monto_det}"))
        if r.pedido_id and r.pedido_estado not in ("CONFIRMADO", "EDITADO"):
            issues.append((r.id, f"pedido {r.nro_pedido} estado={r.pedido_estado}"))

    print(f"FIs CONFIRMADA auditadas: {len(df_int)}")
    print(f"Incidencias: {len(issues)}")
    if issues:
        from collections import Counter
        c = Counter(i[1] for i in issues)
        for k, v in c.most_common(15):
            print(f"  {v}x {k}")
        print("\nPrimeras 20 incidencias:")
        for i in issues[:20]:
            print(f"  fi_id={i[0]}: {i[1]}")

    print(f"\n{SEP}\n6. LISTADO PV000001..MAX (resumen)\n{SEP}")
    df_all_pv = q("""
        SELECT pv_global,
               'PV' || LPAD(pv_global::text, 6, '0') AS pv_display,
               id AS fi_id, nro_factura, estado, pedido_id, total_pares, total_monto
        FROM factura_interna
        WHERE pv_global IS NOT NULL
        ORDER BY pv_global
    """)
    print(f"Total numeradas (CONFIRMADA+ANULADA): {len(df_all_pv)}")
    print(f"MAX pv_global: {df_all_pv['pv_global'].max() if not df_all_pv.empty else 'N/A'}")
    print("\nÚltimas 5:")
    print(df_all_pv.tail(5).to_string(index=False))
    print("\nAnuladas numeradas:")
    print(df_all_pv[df_all_pv["estado"] == "ANULADA"].to_string(index=False))

    res = get_fi_reservadas()
    print(f"\nRESERVADA sin pv_global (esperado): {len(res)}")
    for f in res:
        print(f"  fi_id={f['id']} legacy={f.get('nro_factura')} pv_global={f.get('pv_global')}")

    # Export issues summary as JSON line for report
    summary = {
        "confirmadas_bd": len(db_conf),
        "confirmadas_ui": len(ui_conf),
        "numeradas_total": len(df_all_pv),
        "max_pv_global": int(df_all_pv["pv_global"].max()) if not df_all_pv.empty else None,
        "huecos": len(df_seq),
        "duplicados": len(df_dup),
        "incidencias_integridad": len(issues),
        "ui_bd_mismatches": len(mismatches),
    }
    print(f"\n{SEP}\nRESUMEN JSON\n{SEP}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
