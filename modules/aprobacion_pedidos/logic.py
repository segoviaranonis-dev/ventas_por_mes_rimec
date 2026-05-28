# =============================================================================
# MÓDULO: Aprobación de Pedidos RIMEC
# ARCHIVO: modules/aprobacion_pedidos/logic.py
# DESCRIPCIÓN: Autorización de pedidos mayoristas recibidos desde rimec-web.
#   Divide por PP + Marca + Caso y genera Preventas (PV-YYYY-XXXX).
# =============================================================================

import ast
import json
from datetime import date
from sqlalchemy import text as sqlt

from core.database import get_dataframe, engine, DBInspector
from core.auditoria import log_flujo


def _safe_json(val) -> str:
    """Convierte cualquier formato (dict, str Python, JSON) a JSON string válido para JSONB."""
    if val is None:
        return "{}"
    if isinstance(val, dict):
        return json.dumps(val)
    try:
        return json.dumps(json.loads(val))
    except Exception:
        try:
            return json.dumps(ast.literal_eval(val))
        except Exception:
            return "{}"


def _si(val) -> int | None:
    """Conversión segura a int — devuelve None si el valor es None/'None'/NaN/vacío."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        if s in ("", "None", "nan", "NaN"):
            return None
        return int(float(s))
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP: código de línea → nombre de caso (desde pilar `linea` + biblioteca)
# ─────────────────────────────────────────────────────────────────────────────

def validar_saldo_pp(pp_id: int, pares_requeridos: int) -> tuple[bool, int]:
    """
    Valida que el PP tenga suficientes pares disponibles en tránsito.
    Retorna (tiene_saldo, saldo_actual).
    """
    df = get_dataframe("""
        SELECT 
            COALESCE(SUM(ppd.cantidad_pares), 0) AS total_pares,
            COALESCE(SUM(ppd.pares_vendidos), 0) AS vendidos
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = :pp_id
    """, {"pp_id": pp_id})
    
    if df is None or df.empty:
        return False, 0
    
    total = int(df["total_pares"].iloc[0] or 0)
    vendidos = int(df["vendidos"].iloc[0] or 0)
    saldo = total - vendidos
    
    return saldo >= pares_requeridos, saldo


def get_saldo_detallado_pp(pp_id: int) -> dict:
    """
    Retorna el saldo detallado de un PP para diagnóstico.
    """
    df = get_dataframe("""
        SELECT 
            ppd.linea,
            ppd.referencia,
            ppd.cantidad_pares,
            COALESCE(ppd.pares_vendidos, 0) AS vendidos,
            ppd.cantidad_pares - COALESCE(ppd.pares_vendidos, 0) AS saldo
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = :pp_id
        ORDER BY ppd.linea, ppd.referencia
    """, {"pp_id": pp_id})
    
    if df is None or df.empty:
        return {"items": [], "total": 0, "vendidos": 0, "saldo": 0}
    
    return {
        "items": df.to_dict("records"),
        "total": int(df["cantidad_pares"].sum()),
        "vendidos": int(df["vendidos"].sum()),
        "saldo": int(df["saldo"].sum()),
    }


def get_linea_caso_map(pp_ids: list[int] | None = None) -> dict[str, str]:
    """
    Retorna {codigo_proveedor_linea: caso_nombre} desde la tabla `linea`
    (fuente única de verdad) JOIN `caso_precio_biblioteca`.
    Si se pasan pp_ids, filtra por el proveedor de esos PPs.
    Sin pp_ids, devuelve el mapa completo (todos los proveedores).
    """
    base = """
        SELECT DISTINCT l.codigo_proveedor::text AS linea_cod,
                        cpb.nombre_caso          AS caso_nombre
        FROM linea l
        JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id
        WHERE l.activo = true
          AND l.caso_id IS NOT NULL
    """
    if pp_ids:
        df = get_dataframe(base + """
              AND l.proveedor_id IN (
                  SELECT DISTINCT pp.proveedor_importacion_id
                  FROM pedido_proveedor pp
                  WHERE pp.id = ANY(:ids)
              )
        """, {"ids": pp_ids})
    else:
        df = get_dataframe(base)
    if df is None or df.empty:
        return {}
    # Si hay duplicados (mismo código en varios proveedores), el primero gana
    result = {}
    for _, row in df.iterrows():
        cod = str(row["linea_cod"]).strip()
        if cod not in result:
            result[cod] = str(row["caso_nombre"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def get_fis_de_pedido(pedido_id: int) -> list[dict]:
    """
    Trae las facturas internas asociadas a un pedido_venta_rimec.

    Estrategia híbrida:
      1. Si `factura_interna.pedido_id` (FK formal, mig 029) está poblada → la usa.
      2. Si no, cae a matching por timestamp (±10s) — para FIs creadas por el
         RPC 028 antes de aplicar la 029, o para entornos pre-029.

    Devuelve cada FI con sus totales y el numero_registro del PP origen.
    """
    df = get_dataframe("""
        SELECT
          fi.id, fi.nro_factura,
          fi.pp_id, fi.pedido_id,
          fi.marca, fi.marca_id, fi.caso, fi.caso_id,
          fi.total_pares, fi.total_monto, fi.estado,
          fi.cliente_id, fi.vendedor_id, fi.plazo_id, fi.lista_precio_id,
          fi.descuento_1, fi.descuento_2, fi.descuento_3, fi.descuento_4,
          fi.created_at,
          pp.numero_registro AS nro_pp,
          pp.numero_proforma AS proforma
        FROM public.factura_interna fi
        LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
        WHERE
              fi.pedido_id = :pid
           OR (
                fi.pedido_id IS NULL
                AND ABS(EXTRACT(EPOCH FROM (
                  fi.created_at -
                  (SELECT created_at FROM public.pedido_venta_rimec WHERE id = :pid)
                ))) < 10
              )
        ORDER BY fi.pp_id, fi.marca, fi.caso
    """, {"pid": pedido_id})
    return df.to_dict("records") if df is not None and not df.empty else []


def get_fi_detalles_lite(fi_id: int) -> list[dict]:
    """Variante simplificada para mostrar items dentro de la tarjeta de pedido pendiente."""
    df = get_dataframe("""
        SELECT pares, cajas, precio_neto, subtotal, linea_snapshot
        FROM public.factura_interna_detalle
        WHERE factura_id = :fi
        ORDER BY id
    """, {"fi": fi_id})
    if df is None or df.empty:
        return []
    rows = df.to_dict("records")
    for r in rows:
        snap = r.get("linea_snapshot")
        if isinstance(snap, str):
            try:
                r["linea_snapshot"] = json.loads(snap)
            except Exception:
                try:
                    r["linea_snapshot"] = ast.literal_eval(snap)
                except Exception:
                    r["linea_snapshot"] = {}
        elif not isinstance(snap, dict):
            r["linea_snapshot"] = {}
    return rows


def get_pedidos_pendientes() -> list[dict]:
    df = get_dataframe("""
        SELECT
            pvr.id,
            pvr.nro_pedido,
            pvr.cliente_id,
            c.descp_cliente   AS cliente_nombre,
            pvr.vendedor_id,
            v.descp_usuario  AS vendedor_nombre,
            pvr.plazo_id,
            p.descp_plazo     AS plazo_nombre,
            pvr.lista_precio_id,
            pvr.descuento_1, pvr.descuento_2, pvr.descuento_3, pvr.descuento_4,
            pvr.total_pares,
            pvr.total_monto,
            pvr.payload_json,
            pvr.created_at
        FROM pedido_venta_rimec pvr
        JOIN cliente_v2 c ON c.id_cliente = pvr.cliente_id
        LEFT JOIN usuario_v2 v ON v.id_usuario = pvr.vendedor_id
        LEFT JOIN plazo_v2 p ON p.id_plazo = pvr.plazo_id
        WHERE pvr.estado = 'PENDIENTE'
        ORDER BY pvr.created_at DESC
    """)
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def get_pedidos_autorizados() -> list[dict]:
    df = get_dataframe("""
        SELECT pvr.id, pvr.nro_pedido,
               pvr.cliente_id,
               c.descp_cliente AS cliente_nombre,
               pvr.total_pares, pvr.total_monto,
               pvr.estado, pvr.created_at
        FROM pedido_venta_rimec pvr
        LEFT JOIN cliente_v2 c ON c.id_cliente = pvr.cliente_id
        WHERE pvr.estado = 'AUTORIZADO'
        ORDER BY pvr.created_at DESC
        LIMIT 50
    """)
    return df.to_dict("records") if df is not None and not df.empty else []


def get_pedidos_rechazados() -> list[dict]:
    df = get_dataframe("""
        SELECT pvr.id, pvr.nro_pedido, c.descp_cliente AS cliente_nombre,
               pvr.total_pares, pvr.total_monto, pvr.motivo_rechazo, pvr.created_at
        FROM pedido_venta_rimec pvr
        JOIN cliente_v2 c ON c.id_cliente = pvr.cliente_id
        WHERE pvr.estado = 'RECHAZADO'
        ORDER BY pvr.created_at DESC
        LIMIT 50
    """)
    return df.to_dict("records") if df is not None and not df.empty else []


# ─────────────────────────────────────────────────────────────────────────────
# NUMERACIÓN PV-YYYY-XXXX
# ─────────────────────────────────────────────────────────────────────────────

def _get_next_nro_pv(pp_id: int) -> str:
    """
    Genera número de Factura Interna/Preventa con nomenclatura [PP_ID]-PV[NNN].
    El correlativo se resetea por cada Pedido Proveedor.
    Ejemplo: 15-PV001, 15-PV002, 16-PV001...
    """
    df = get_dataframe("""
        SELECT COALESCE(
            MAX(
                CAST(
                    REGEXP_REPLACE(nro_factura, '^[0-9]+-PV', '')
                    AS INTEGER
                )
            ),
            0
        ) + 1 AS correlativo
        FROM factura_interna
        WHERE pp_id = :pp_id
          AND nro_factura ~ '^[0-9]+-PV[0-9]+$'
    """, {"pp_id": pp_id})
    correlativo = int(df["correlativo"].iloc[0]) if df is not None and not df.empty else 1
    return f"{pp_id}-PV{correlativo:03d}"


def _generar_nros_pv_por_pp(grupos: dict) -> dict[str, str]:
    """
    Pre-genera números PV para cada grupo (clave → nro_pv).
    La nomenclatura es [PP_ID]-PV[NNN], correlativo reseteado por PP.
    """
    # Agrupar por pp_id para calcular correlativos
    pp_counts: dict[int, int] = {}
    pp_bases: dict[int, int] = {}
    
    for clave, grupo in grupos.items():
        pp_id = grupo["pp_id"]
        if pp_id not in pp_counts:
            pp_counts[pp_id] = 0
            # Obtener base actual de BD
            df = get_dataframe("""
                SELECT COALESCE(
                    MAX(
                        CAST(
                            REGEXP_REPLACE(nro_factura, '^[0-9]+-PV', '')
                            AS INTEGER
                        )
                    ),
                    0
                ) AS ultimo
                FROM factura_interna
                WHERE pp_id = :pp_id
                  AND nro_factura ~ '^[0-9]+-PV[0-9]+$'
            """, {"pp_id": pp_id})
            pp_bases[pp_id] = int(df["ultimo"].iloc[0]) if df is not None and not df.empty else 0
        pp_counts[pp_id] += 1
    
    # Generar números
    result: dict[str, str] = {}
    pp_current: dict[int, int] = {pp_id: base for pp_id, base in pp_bases.items()}
    
    for clave, grupo in grupos.items():
        pp_id = grupo["pp_id"]
        pp_current[pp_id] += 1
        result[clave] = f"{pp_id}-PV{pp_current[pp_id]:03d}"
    
    return result


def get_preventa_de_celula(pp_id: int, marca: str, caso: str) -> dict | None:
    """Retorna la factura_interna de una célula si ya fue aprobada, o None."""
    df = get_dataframe("""
        SELECT id, nro_factura, total_pares, total_monto, estado
        FROM factura_interna
        WHERE pp_id = :pp_id AND marca = :marca AND caso = :caso
        LIMIT 1
    """, {"pp_id": pp_id, "marca": marca, "caso": caso})
    if df is None or df.empty:
        return None
    row = df.iloc[0]
    return {"id": row["id"], "nro_factura": row["nro_factura"],
            "total_pares": row["total_pares"], "total_monto": row["total_monto"],
            "estado": row["estado"]}


def _cerrar_pedido_si_completo(pedido_id: int) -> bool:
    """
    Cierra el pedido (estado=AUTORIZADO) solo si TODOS los pp_id del payload
    tienen al menos una factura_interna aprobada. Retorna True si se cerró.
    """
    df = get_dataframe(
        "SELECT payload_json FROM pedido_venta_rimec WHERE id=:pid",
        {"pid": pedido_id},
    )
    if df is None or df.empty:
        return False
    raw = df.iloc[0]["payload_json"]
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            try:
                payload = ast.literal_eval(raw)
            except Exception:
                payload = {}
    else:
        payload = raw or {}
    lotes = payload.get("lotes", [])
    pp_ids_esperados = {int(l["pp_id"]) for l in lotes if l.get("pp_id")}
    if not pp_ids_esperados:
        return False

    for pp_id in pp_ids_esperados:
        df2 = get_dataframe(
            "SELECT COUNT(*) AS n FROM factura_interna WHERE pp_id=:pp_id",
            {"pp_id": pp_id},
        )
        if df2 is None or df2.empty or int(df2.iloc[0]["n"]) == 0:
            return False  # aún falta al menos un PP

    with engine.begin() as conn:
        conn.execute(sqlt(
            "UPDATE pedido_venta_rimec SET estado='AUTORIZADO' WHERE id=:pid"
        ), {"pid": pedido_id})
    print(f"[CERRAR] Pedido {pedido_id} → AUTORIZADO (todas las células aprobadas)")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# AUTORIZACIÓN — División PP + Marca + Caso
# ─────────────────────────────────────────────────────────────────────────────

def autorizar_pedido(pedido_id: int) -> tuple[bool, str, list[str]]:
    """
    Divide el pedido por clave PP|Marca|Caso (caso = linea_codigo).
    Genera una Preventa (PV-YYYY-XXXX) por cada grupo.
    Hereda todo el ADN. Descuenta pares_vendidos en PPD.
    Retorna (ok, mensaje, lista_preventas).
    """
    df = get_dataframe("""
        SELECT pvr.*, c.descp_cliente
        FROM pedido_venta_rimec pvr
        JOIN cliente_v2 c ON c.id_cliente = pvr.cliente_id
        WHERE pvr.id = :pid AND pvr.estado = 'PENDIENTE'
    """, {"pid": pedido_id})

    if df is None or df.empty:
        return False, "Pedido no encontrado o ya procesado.", []

    pedido = df.iloc[0]
    raw     = pedido["payload_json"]
    if isinstance(raw, dict):
        payload = raw
    else:
        try:
            payload = json.loads(raw or '{}')
        except (json.JSONDecodeError, ValueError):
            import ast
            try:
                payload = ast.literal_eval(raw)
            except Exception:
                payload = {}
    lotes = payload.get("lotes", [])

    # Cargar mapa linea_codigo → caso_nombre desde pilar `linea` + caso_precio_biblioteca
    pp_ids_lotes = list({int(l["pp_id"]) for l in lotes if l.get("pp_id")})
    linea_caso_map = get_linea_caso_map(pp_ids_lotes)

    # ── Construir grupos PP|Marca|Caso ────────────────────────────────────────
    grupos: dict[str, dict] = {}
    for lote in lotes:
        pp_id  = lote["pp_id"]
        pp_nro = lote.get("pp_nro", str(pp_id))
        for marca_block in lote.get("marcas", []):
            marca = marca_block.get("marca", "SIN_MARCA")
            for item in marca_block.get("items", []):
                linea_cod = str(item.get("linea_codigo", "")).strip()
                caso      = linea_caso_map.get(linea_cod) or linea_cod or "SIN_CASO"
                clave = f"{pp_id}|{marca}|{caso}"
                if clave not in grupos:
                    grupos[clave] = {
                        "pp_id":  pp_id,
                        "pp_nro": pp_nro,
                        "marca":  marca,
                        "caso":   caso,
                        "items":  [],
                    }
                grupos[clave]["items"].append(item)

    if not grupos:
        return False, "El pedido no tiene ítems.", []

    # ── VALIDACIÓN DE SALDO por cada PP ───────────────────────────────────
    # Agrupar pares requeridos por PP
    pares_por_pp: dict[int, int] = {}
    for clave, grupo in grupos.items():
        pp_id = grupo["pp_id"]
        pares = sum(i.get("pares", 0) for i in grupo["items"])
        pares_por_pp[pp_id] = pares_por_pp.get(pp_id, 0) + pares
    
    # Validar cada PP
    for pp_id, pares_req in pares_por_pp.items():
        tiene_saldo, saldo_actual = validar_saldo_pp(pp_id, pares_req)
        if not tiene_saldo:
            return False, (
                f"Stock insuficiente en PP {pp_id}: "
                f"disponible={saldo_actual:,} pares, requerido={pares_req:,} pares"
            ), []

    # Pre-generar todos los números PV antes de abrir la transacción
    # Nomenclatura: [PP_ID]-PV[NNN] — correlativo reseteado por cada PP
    nros_pv_map = _generar_nros_pv_por_pp(grupos)
    preventas_generadas: list[str] = []

    # Cable de acero: pre-cargar quincenas de cada PP
    quincenas_por_pp: dict[int, int | None] = {}
    for pp_id in {g["pp_id"] for g in grupos.values()}:
        df_pp = get_dataframe("""
            SELECT quincena_arribo_id
            FROM pedido_proveedor
            WHERE id = :pp_id
        """, {"pp_id": pp_id})
        if df_pp is not None and not df_pp.empty:
            quincenas_por_pp[pp_id] = _si(df_pp.iloc[0]["quincena_arribo_id"])
        else:
            quincenas_por_pp[pp_id] = None

    try:
        with engine.begin() as conn:
            for clave, grupo in grupos.items():
                items       = grupo["items"]
                total_pares = sum(i.get("pares", 0) for i in items)
                total_neto  = sum(i.get("subtotal", 0) for i in items)
                nro_pv      = nros_pv_map[clave]

                # ── Crear Preventa (factura_interna) ──────────────────────────
                res = conn.execute(sqlt("""
                    INSERT INTO factura_interna
                        (nro_factura, pp_id, marca, caso,
                         cliente_id, vendedor_id, plazo_id, lista_precio_id,
                         descuento_1, descuento_2, descuento_3, descuento_4,
                         total_pares, total_monto, estado, quincena_arribo_id)
                    VALUES
                        (:nro, :pp_id, :marca, :caso,
                         :cli, :vend, :plazo, :lista,
                         :d1, :d2, :d3, :d4,
                         :tp, :tn, 'RESERVADA', :qid)
                    RETURNING id
                """), {
                    "nro":   nro_pv,
                    "pp_id": grupo["pp_id"],
                    "marca": grupo["marca"],
                    "caso":  grupo["caso"],
                    "cli":   _si(pedido["cliente_id"]),
                    "vend":  _si(pedido.get("vendedor_id")),
                    "plazo": _si(pedido.get("plazo_id")),
                    "lista": _si(pedido["lista_precio_id"]),
                    "d1": float(pedido.get("descuento_1") or 0),
                    "d2": float(pedido.get("descuento_2") or 0),
                    "d3": float(pedido.get("descuento_3") or 0),
                    "d4": float(pedido.get("descuento_4") or 0),
                    "tp":    total_pares,
                    "tn":    total_neto,
                    "qid":   quincenas_por_pp.get(grupo["pp_id"]),  # Cable de acero reforzado
                })
                fi_id = res.fetchone()[0]

                # ── Detalle + descuento stock ─────────────────────────────────
                for item in items:
                    det_id = item.get("det_id")
                    pares  = int(item.get("pares", 0))
                    cajas  = int(item.get("cajas", 0))

                    conn.execute(sqlt("""
                        INSERT INTO factura_interna_detalle
                            (factura_id, ppd_id, pares, cajas, precio_unit, subtotal,
                             precio_neto, linea_snapshot)
                        VALUES
                            (:fi, :ppd, :pares, :cajas, :pu, :sub, :pn, :snap)
                    """), {
                        "fi":    fi_id,
                        "ppd":   det_id,
                        "pares": pares,
                        "cajas": cajas,
                        "pu":    float(item.get("precio_neto", 0)),
                        "sub":   float(item.get("subtotal",   0)),
                        "pn":    float(item.get("precio_neto", 0)),
                        "snap":  _safe_json({
                            "linea_codigo": item.get("linea_codigo"),
                            "ref_codigo":   item.get("ref_codigo"),
                            "material_nombre": item.get("material_nombre") or item.get("descp_material") or item.get("material", ""),  # OT-2026-031: fallback
                            "color_nombre": item.get("color_nombre"),
                            "gradas_fmt":   item.get("gradas_fmt"),
                            "imagen_url":   item.get("imagen_url"),
                        }),
                    })

                    if det_id and pares > 0:
                        conn.execute(sqlt("""
                            SELECT descontar_stock_pp(:det_id, :pares)
                        """), {"det_id": det_id, "pares": pares})

                preventas_generadas.append(nro_pv)
                DBInspector.log(f"[APROBACION] {nro_pv} creada — PP{grupo['pp_id']} {grupo['marca']} {grupo['caso']}", "SUCCESS")

            # ── Cerrar pedido ─────────────────────────────────────────────────
            conn.execute(sqlt("""
                UPDATE pedido_venta_rimec SET estado='AUTORIZADO' WHERE id=:pid
            """), {"pid": pedido_id})

        log_flujo(
            entidad="pedido_venta_rimec", entidad_id=pedido_id,
            nro_registro=str(pedido["nro_pedido"]),
            accion="PVR_AUTORIZADO",
            estado_antes="PENDIENTE", estado_despues="AUTORIZADO",
            snap={"preventas": preventas_generadas},
        )
        msg = f"{len(preventas_generadas)} preventa(s) generada(s): {', '.join(preventas_generadas)}"
        return True, msg, preventas_generadas

    except Exception as e:
        DBInspector.log(f"[APROBACION] Error autorizando {pedido_id}: {e}", "ERROR")
        return False, str(e), []


def _descontar_stock_por_texto(conn, pp_id: int, items: list):
    """
    Descuenta pares_vendidos en PPD usando linea/referencia TEXT.
    El det_id del payload es externo — no sirve como FK.
    Si no encuentra match, loguea y continúa sin bloquear.
    """
    for item in items:
        linea_cod = str(item.get("linea_codigo", "")).strip()
        ref_cod   = str(item.get("ref_codigo",   "")).strip()
        pares     = int(item.get("pares", 0))
        if not linea_cod or not ref_cod or pares <= 0:
            continue
        # leer saldo antes
        antes = conn.execute(sqlt("""
            SELECT id, cantidad_pares, COALESCE(pares_vendidos,0)
            FROM pedido_proveedor_detalle
            WHERE pedido_proveedor_id=:pp_id
              AND linea::text=:linea AND referencia::text=:ref
            LIMIT 1
        """), {"pp_id": pp_id, "linea": linea_cod, "ref": ref_cod}).fetchone()

        if antes:
            saldo_antes = antes[1] - antes[2]
            print(f"  [STOCK] L{linea_cod}/R{ref_cod} — "
                  f"inicial={antes[1]} vendidos={antes[2]} disponible={saldo_antes} venta={pares}")

        result = conn.execute(sqlt("""
            UPDATE pedido_proveedor_detalle
            SET pares_vendidos = COALESCE(pares_vendidos, 0) + :pares
            WHERE id = (
                SELECT id FROM pedido_proveedor_detalle
                WHERE pedido_proveedor_id = :pp_id
                  AND linea::text      = :linea
                  AND referencia::text = :ref
                  AND (cantidad_pares - COALESCE(pares_vendidos, 0)) >= :pares
                ORDER BY (cantidad_pares - COALESCE(pares_vendidos, 0)) DESC
                LIMIT 1
            )
            RETURNING id, cantidad_pares, pares_vendidos
        """), {"pp_id": pp_id, "linea": linea_cod, "ref": ref_cod, "pares": pares})
        hit = result.fetchone()
        if hit:
            saldo_final = hit[1] - hit[2]
            print(f"  [STOCK OK] PPD id={hit[0]} L{linea_cod}/R{ref_cod} "
                  f"saldo_final={saldo_final}")
            DBInspector.log(f"[STOCK] PPD id={hit[0]} L{linea_cod}/R{ref_cod} -{pares}p saldo={saldo_final}", "SUCCESS")
        else:
            print(f"  [STOCK WARN] Sin match/stock insuficiente: pp={pp_id} L{linea_cod}/R{ref_cod} pares={pares}")
            DBInspector.log(f"[STOCK WARN] Sin match en PPD: pp={pp_id} L{linea_cod}/R{ref_cod} {pares}p", "WARNING")


def crear_preventa_desde_celula(pedido_id: int, celula: dict) -> tuple[bool, str]:
    """
    Aprueba UNA célula (PP+Marca+Caso). Genera exactamente una Preventa.
    Stock se descuenta por linea/referencia TEXT.
    
    VALIDACIÓN: Verifica saldo disponible en tránsito antes de reservar.
    """
    print(f"\n{'='*60}")
    print(f"[APROBACION] pedido_id={pedido_id} PP={celula.get('pp_id')} "
          f"marca={celula.get('marca')} caso={celula.get('caso')}")
    print(f"[APROBACION] items={len(celula.get('items', []))} "
          f"pares={celula.get('total_pares',0)} monto={celula.get('total_neto',0)}")
    for i, item in enumerate(celula.get("items", [])):
        print(f"  item[{i}] linea={item.get('linea_codigo')} ref={item.get('ref_codigo')} "
              f"pares={item.get('pares')} cajas={item.get('cajas')} "
              f"precio={item.get('precio_neto')} sub={item.get('subtotal')}")
    
    # ── VALIDACIÓN DE SALDO ───────────────────────────────────────────────
    pp_id_val = _si(celula.get("pp_id"))
    pares_requeridos = sum(i.get("pares", 0) for i in celula.get("items", []))
    
    if pp_id_val:
        tiene_saldo, saldo_actual = validar_saldo_pp(pp_id_val, pares_requeridos)
        print(f"[VALIDACION] PP {pp_id_val}: saldo={saldo_actual}, requerido={pares_requeridos}, ok={tiene_saldo}")
        
        if not tiene_saldo:
            msg = (f"Stock insuficiente en PP {pp_id_val}: "
                   f"disponible={saldo_actual:,} pares, requerido={pares_requeridos:,} pares")
            DBInspector.log(f"[CELULA] {msg}", "ERROR")
            return False, msg
    
    df = get_dataframe("""
        SELECT cliente_id, vendedor_id, plazo_id, lista_precio_id,
               descuento_1, descuento_2, descuento_3, descuento_4, nro_pedido
        FROM pedido_venta_rimec WHERE id = :pid
    """, {"pid": pedido_id})
    if df is None or df.empty:
        return False, "Pedido no encontrado."

    p           = df.iloc[0]
    items       = celula.get("items", [])
    pp_id       = _si(celula["pp_id"])
    total_pares = sum(i.get("pares", 0) for i in items)
    total_monto = sum(i.get("subtotal", 0) for i in items)
    nro_pv      = _get_next_nro_pv(pp_id)  # genera el número ANTES de abrir la tx

    # Cable de acero: leer quincena del PP para propagarla a FI
    quincena_id = None
    if pp_id:
        df_pp = get_dataframe("""
            SELECT quincena_arribo_id
            FROM pedido_proveedor
            WHERE id = :pp_id
        """, {"pp_id": pp_id})
        if df_pp is not None and not df_pp.empty:
            quincena_id = _si(df_pp.iloc[0]["quincena_arribo_id"])

    try:
        with engine.begin() as conn:
            # ── Crear Preventa ────────────────────────────────────────────────
            res = conn.execute(sqlt("""
                INSERT INTO factura_interna
                    (nro_factura, pp_id, marca, caso,
                     cliente_id, vendedor_id, plazo_id, lista_precio_id,
                     descuento_1, descuento_2, descuento_3, descuento_4,
                     total_pares, total_monto, estado, quincena_arribo_id)
                VALUES
                    (:nro, :pp_id, :marca, :caso,
                     :cli, :vend, :plazo, :lista,
                     :d1, :d2, :d3, :d4,
                     :tp, :tn, 'RESERVADA', :qid)
                RETURNING id
            """), {
                "nro":   nro_pv,
                "pp_id": pp_id,
                "marca": celula.get("marca", ""),
                "caso":  celula.get("caso", "SIN_CASO"),
                "cli":   _si(p["cliente_id"]),
                "vend":  _si(p.get("vendedor_id")),
                "plazo": _si(p.get("plazo_id")),
                "lista": _si(p["lista_precio_id"]),
                "d1": float(p.get("descuento_1") or 0),
                "d2": float(p.get("descuento_2") or 0),
                "d3": float(p.get("descuento_3") or 0),
                "d4": float(p.get("descuento_4") or 0),
                "tp": total_pares, "tn": total_monto,
                "qid": quincena_id,  # Cable de acero reforzado
            })
            fi_id = res.fetchone()[0]

            # ── Detalle ───────────────────────────────────────────────────────
            for item in items:
                pares = int(item.get("pares", 0))
                conn.execute(sqlt("""
                    INSERT INTO factura_interna_detalle
                        (factura_id, ppd_id, pares, cajas,
                         precio_unit, subtotal, precio_neto, linea_snapshot)
                    VALUES
                        (:fi, NULL, :pares, :cajas,
                         :pu, :sub, :pn, :snap)
                """), {
                    "fi":    fi_id,
                    "pares": pares,
                    "cajas": int(item.get("cajas", 0)),
                    "pu":    float(item.get("precio_neto", 0)),
                    "sub":   float(item.get("subtotal",   0)),
                    "pn":    float(item.get("precio_neto", 0)),
                    "snap":  _safe_json({
                        "linea_codigo": item.get("linea_codigo"),
                        "ref_codigo":   item.get("ref_codigo"),
                        "material_nombre": item.get("material_nombre") or item.get("descp_material") or item.get("material", ""),  # OT-2026-031: fallback
                        "color_nombre": item.get("color_nombre"),
                        "gradas_fmt":   item.get("gradas_fmt"),
                        "imagen_url":   item.get("imagen_url"),
                    }),
                })

            # ── Descuento stock por texto (no bloquea si PPD vacío) ───────────
            if pp_id:
                _descontar_stock_por_texto(conn, pp_id, items)

        # ── Cerrar pedido si TODAS las células tienen preventa ───────────────
        _cerrar_pedido_si_completo(pedido_id)

        log_flujo(
            entidad="pedido_venta_rimec", entidad_id=pedido_id,
            accion="CELULA_APROBADA",
            snap={"nro_pv": nro_pv, "pp_id": celula["pp_id"],
                  "marca": celula.get("marca"), "caso": celula.get("caso")},
        )
        print(f"[FACTURA] {nro_pv} generada — fi_id={fi_id} "
              f"cliente={_si(p['cliente_id'])} pares={total_pares} monto={total_monto}")
        print(f"{'='*60}\n")
        DBInspector.log(f"[CELULA] {nro_pv} — {celula.get('marca')} {celula.get('caso')}", "SUCCESS")
        return True, nro_pv

    except Exception as e:
        print(f"[ERROR] crear_preventa_desde_celula: {e}")
        import traceback; traceback.print_exc()
        DBInspector.log(f"[CELULA] Error: {e}", "ERROR")
        return False, str(e)


def rechazar_pedido(pedido_id: int, motivo: str) -> tuple[bool, str]:
    """
    Rechaza un pedido COMPLETO.

    CRÍTICO: Anula TODAS las FIs asociadas (revirtiendo stock) antes de
    marcar el pedido como rechazado. Esto evita FIs huérfanas en estado RESERVADA.
    """
    try:
        # 1. Buscar todas las FIs asociadas a este pedido
        df_fis = get_dataframe("""
            SELECT id, nro_factura, estado
            FROM factura_interna
            WHERE pedido_id = :pid AND estado = 'RESERVADA'
        """, {"pid": pedido_id})

        fis_anuladas = []
        fis_errores = []

        # 2. Anular cada FI RESERVADA (esto revierte el stock automáticamente)
        if df_fis is not None and not df_fis.empty:
            for _, fi_row in df_fis.iterrows():
                fi_id = int(fi_row['id'])
                nro_fi = fi_row['nro_factura']
                ok, msg = anular_fi(fi_id, motivo=f"Pedido rechazado: {motivo}")
                if ok:
                    fis_anuladas.append(nro_fi)
                    DBInspector.log(f"[RECHAZO] FI {nro_fi} anulada automáticamente", "SUCCESS")
                else:
                    fis_errores.append(f"{nro_fi}: {msg}")
                    DBInspector.log(f"[RECHAZO] Error anulando FI {nro_fi}: {msg}", "ERROR")

        # 3. Cambiar estado del pedido a RECHAZADO
        with engine.begin() as conn:
            conn.execute(sqlt("""
                UPDATE pedido_venta_rimec
                SET estado='RECHAZADO', motivo_rechazo=:motivo
                WHERE id=:pid AND estado='PENDIENTE'
            """), {"pid": pedido_id, "motivo": motivo.strip()})

        log_flujo(
            entidad="pedido_venta_rimec", entidad_id=pedido_id,
            accion="PVR_RECHAZADO",
            estado_antes="PENDIENTE", estado_despues="RECHAZADO",
            snap={
                "motivo": motivo,
                "fis_anuladas": fis_anuladas,
                "fis_errores": fis_errores,
            },
        )

        msg_base = "Pedido rechazado."
        if fis_anuladas:
            msg_base += f" {len(fis_anuladas)} FI(s) anulada(s): {', '.join(fis_anuladas)}"
        if fis_errores:
            msg_base += f" ADVERTENCIA: Errores anulando algunas FIs: {'; '.join(fis_errores)}"

        return True, msg_base
    except Exception as e:
        DBInspector.log(f"[RECHAZO] Error rechazando pedido {pedido_id}: {e}", "ERROR")
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO RESERVA → LIBERACIÓN (Paradigma: BD como único canal)
# ─────────────────────────────────────────────────────────────────────────────

def get_fi_reservadas() -> list[dict]:
    """Lee FIs con estado RESERVADA directamente de BD.
    El módulo de Aprobación las encuentra por estado — no recibe objetos."""
    df = get_dataframe("""
        SELECT fi.id, fi.nro_factura, fi.pp_id, fi.pedido_id, fi.marca, fi.caso,
               fi.total_pares, fi.total_monto,
               fi.cliente_id, fi.vendedor_id, fi.plazo_id,
               fi.lista_precio_id,
               fi.descuento_1, fi.descuento_2, fi.descuento_3, fi.descuento_4,
               fi.created_at,
               c.descp_cliente AS cliente_nombre,
               v.descp_usuario AS vendedor_nombre,
               pp.numero_registro AS nro_pp,
               pp.numero_proforma AS proforma,
               qa.descripcion AS quincena_llegada
        FROM factura_interna fi
        LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
        LEFT JOIN usuario_v2 v ON v.id_usuario = fi.vendedor_id
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
        WHERE fi.estado = 'RESERVADA'
        ORDER BY fi.created_at DESC
    """)
    return df.to_dict("records") if df is not None and not df.empty else []


def get_fi_confirmadas() -> list[dict]:
    """Lee FIs confirmadas (aprobadas) para el historial con detalle."""
    df = get_dataframe("""
        SELECT fi.id, fi.nro_factura, fi.pp_id, fi.pedido_id, fi.marca, fi.caso,
               fi.total_pares, fi.total_monto,
               fi.cliente_id, fi.vendedor_id,
               fi.descuento_1, fi.descuento_2, fi.descuento_3, fi.descuento_4,
               c.descp_cliente AS cliente_nombre,
               v.descp_usuario AS vendedor_nombre,
               pp.numero_registro AS nro_pp,
               pp.numero_proforma AS proforma,
               qa.descripcion AS quincena_llegada,
               fi.created_at
        FROM factura_interna fi
        LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
        LEFT JOIN usuario_v2 v ON v.id_usuario = fi.vendedor_id
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
        WHERE fi.estado = 'CONFIRMADA'
        ORDER BY fi.created_at DESC
        LIMIT 50
    """)
    return df.to_dict("records") if df is not None and not df.empty else []


def get_fi_detalles(fi_id: int) -> list[dict]:
    """Retorna los detalles (items) de una FI con su linea_snapshot."""
    df = get_dataframe("""
        SELECT fid.id, fid.pares, fid.cajas, fid.precio_unit,
               fid.subtotal, fid.precio_neto, fid.linea_snapshot
        FROM factura_interna_detalle fid
        WHERE fid.factura_id = :fi_id
        ORDER BY fid.id
    """, {"fi_id": fi_id})
    if df is None or df.empty:
        return []
    rows = df.to_dict("records")
    # Parsear linea_snapshot
    for row in rows:
        snap = row.get("linea_snapshot")
        if isinstance(snap, str):
            try:
                row["linea_snapshot"] = json.loads(snap)
            except Exception:
                try:
                    row["linea_snapshot"] = ast.literal_eval(snap)
                except Exception:
                    row["linea_snapshot"] = {}
        elif not isinstance(snap, dict):
            row["linea_snapshot"] = {}
    return rows


def get_fi_anuladas() -> list[dict]:
    """Lee FIs anuladas (rechazadas) para el historial."""
    df = get_dataframe("""
        SELECT fi.id, fi.nro_factura, fi.pp_id, fi.marca, fi.caso,
               fi.total_pares, fi.total_monto, fi.notas,
               c.descp_cliente AS cliente_nombre,
               pp.numero_registro AS nro_pp,
               pp.numero_proforma AS proforma,
               fi.created_at
        FROM factura_interna fi
        LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        WHERE fi.estado = 'ANULADA'
        ORDER BY fi.created_at DESC
        LIMIT 50
    """)
    return df.to_dict("records") if df is not None and not df.empty else []


def _get_pedido_id_from_fi(fi_id: int) -> int | None:
    """Obtiene el pedido_id asociado a una factura interna."""
    df = get_dataframe("""
        SELECT pedido_id
        FROM public.factura_interna
        WHERE id = :fi_id
        LIMIT 1
    """, {"fi_id": fi_id})
    if df is None or df.empty or df.iloc[0]["pedido_id"] is None:
        return None
    return int(df.iloc[0]["pedido_id"])


def _verificar_todas_fis_confirmadas(pedido_id: int) -> bool:
    """Verifica si TODAS las FIs de un pedido están CONFIRMADAS."""
    df = get_dataframe("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN estado = 'CONFIRMADA' THEN 1 ELSE 0 END) as confirmadas
        FROM public.factura_interna
        WHERE pedido_id = :pedido_id
    """, {"pedido_id": pedido_id})

    if df is None or df.empty:
        return False

    total = int(df.iloc[0]["total"])
    confirmadas = int(df.iloc[0]["confirmadas"])

    return total > 0 and total == confirmadas


def _confirmar_pedido_web(pedido_id: int, conn) -> None:
    """Cambia el estado del pedido_venta_rimec de PENDIENTE → CONFIRMADO."""
    conn.execute(sqlt("""
        UPDATE public.pedido_venta_rimec
        SET estado = 'CONFIRMADO'
        WHERE id = :pedido_id AND estado = 'PENDIENTE'
    """), {"pedido_id": pedido_id})


def _enviar_email_confirmacion(pedido_id: int) -> tuple[bool, str]:
    """
    Genera PDF y envía email de confirmación con todas las FIs del pedido.

    Returns:
        (success, message)
    """
    try:
        from core.pdf_factura_interna import generar_pdf_factura_interna, obtener_metadata_para_email
        from core.email_service import send_factura_interna_confirmation

        # 1. Obtener metadata para email
        metadata = obtener_metadata_para_email(pedido_id)
        if not metadata:
            return False, "No se pudo obtener metadata del pedido"

        # 2. Validar que haya emails configurados
        if not metadata.get("vendedor_email"):
            DBInspector.log(f"[EMAIL] Pedido {pedido_id}: vendedor sin email configurado", "WARNING")
            return False, "Vendedor no tiene email configurado"

        # 3. Generar PDF
        pdf_bytes = generar_pdf_factura_interna(pedido_id)
        if not pdf_bytes:
            return False, "Error al generar PDF"

        # 4. Enviar email
        pdf_filename = f"Factura_Interna_{metadata['nro_pedido']}.pdf"

        email_ok = send_factura_interna_confirmation(
            vendedor_email=metadata["vendedor_email"],
            supervisor_email=metadata.get("supervisor_email"),
            nro_pedido=metadata["nro_pedido"],
            cliente_nombre=metadata["cliente_nombre"],
            total_general=metadata["total_general"],
            total_pares=metadata["total_pares"],
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename
        )

        if email_ok:
            DBInspector.log(
                f"[EMAIL] Confirmación enviada: {metadata['nro_pedido']} → {metadata['vendedor_email']}",
                "SUCCESS"
            )
            return True, f"Email enviado a {metadata['vendedor_email']}"
        else:
            return False, "Error al enviar email (revisar logs)"

    except Exception as e:
        DBInspector.log(f"[EMAIL] Error enviando confirmación pedido {pedido_id}: {e}", "ERROR")
        return False, f"Error al enviar email: {str(e)}"


def confirmar_fi(fi_id: int) -> tuple[bool, str]:
    """
    APROBAR: RESERVADA → CONFIRMADA.

    Flujo completo:
    1. Cambiar FI: RESERVADA → CONFIRMADA
    2. Verificar si TODAS las FIs del pedido están CONFIRMADAS
    3. Si todas confirmadas:
       - Cambiar PVR: PENDIENTE → CONFIRMADO
       - Generar PDF multi-factura
       - Enviar email automático al vendedor y supervisor

    El descuento de stock ya fue hecho en el soft-discount al crear la FI.
    """
    fi_id = int(fi_id)

    try:
        # 1. Obtener pedido_id asociado (antes de la transacción)
        pedido_id = _get_pedido_id_from_fi(fi_id)
        if not pedido_id:
            DBInspector.log(f"[FI] fi_id={fi_id} no tiene pedido_venta_rimec asociado", "WARNING")
            # Continuar con confirmación simple (sin email/PDF)

        # 2. Confirmar la FI
        with engine.begin() as conn:
            result = conn.execute(sqlt("""
                UPDATE public.factura_interna
                SET estado = 'CONFIRMADA'
                WHERE id = :id AND estado = 'RESERVADA'
            """), {"id": fi_id})

            if result.rowcount == 0:
                return False, "FI no encontrada o ya no está en estado RESERVADA."

            # 3. Verificar si todas las FIs están confirmadas
            if pedido_id:
                todas_confirmadas = _verificar_todas_fis_confirmadas(pedido_id)

                if todas_confirmadas:
                    # 4. Confirmar el pedido web
                    _confirmar_pedido_web(pedido_id, conn)
                    DBInspector.log(
                        f"[PEDIDO] pedido_id={pedido_id} CONFIRMADO (todas las FIs aprobadas)",
                        "SUCCESS"
                    )

        # 5. Log de auditoría
        log_flujo(
            entidad="factura_interna", entidad_id=fi_id,
            accion="FI_CONFIRMADA",
            estado_antes="RESERVADA", estado_despues="CONFIRMADA",
            snap={"fi_id": fi_id, "pedido_id": pedido_id},
        )

        # 6. Enviar email si el pedido está completo
        email_msg = ""
        if pedido_id and todas_confirmadas:
            email_ok, email_result = _enviar_email_confirmacion(pedido_id)
            if email_ok:
                email_msg = f" | Email enviado: {email_result}"
            else:
                email_msg = f" | Email fallido: {email_result}"

        DBInspector.log(f"[FI] Confirmada fi_id={fi_id}{email_msg}", "SUCCESS")

        # Mensaje al usuario
        msg = "FI confirmada exitosamente."
        if pedido_id and todas_confirmadas:
            msg += " El pedido ha sido CONFIRMADO y se envió email con el PDF."

        return True, msg

    except Exception as e:
        DBInspector.log(f"[FI] Error confirmando {fi_id}: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False, str(e)


def anular_fi(fi_id: int, motivo: str = "") -> tuple[bool, str]:
    """RECHAZAR: RESERVADA → ANULADA + reversión automática de stock.
    Llama a revertir_stock_fi() en BD para restaurar pares_vendidos."""
    fi_id = int(fi_id)
    try:
        with engine.begin() as conn:
            # Revertir stock primero
            conn.execute(sqlt("SELECT revertir_stock_fi(:id)"), {"id": fi_id})
            # Cambiar estado
            result = conn.execute(sqlt("""
                UPDATE factura_interna
                SET estado = 'ANULADA', notas = :motivo
                WHERE id = :id AND estado = 'RESERVADA'
            """), {"id": fi_id, "motivo": motivo.strip() or "Sin motivo"})
            if result.rowcount == 0:
                return False, "FI no encontrada o ya no está en estado RESERVADA."
        log_flujo(
            entidad="factura_interna", entidad_id=fi_id,
            accion="FI_ANULADA",
            estado_antes="RESERVADA", estado_despues="ANULADA",
            snap={"motivo": motivo},
        )
        DBInspector.log(f"[FI] Anulada fi_id={fi_id} motivo={motivo}", "SUCCESS")
        return True, "FI anulada y stock revertido."
    except Exception as e:
        DBInspector.log(f"[FI] Error anulando {fi_id}: {e}", "ERROR")
        return False, str(e)


def actualizar_fi_encabezado(
    fi_id: int,
    lista_precio_id: int,
    descuento_1: float,
    descuento_2: float,
    descuento_3: float,
    descuento_4: float,
    plazo_id: int
) -> tuple[bool, str]:
    """Actualiza encabezado de FI (lista_precio, descuentos, plazo) y recalcula precios.

    Flujo:
    1. Obtener detalles actuales de FI
    2. Para cada detalle, buscar nuevo precio en v_stock_rimec según lista
    3. Recalcular precio_neto aplicando descuentos en cascada
    4. Actualizar factura_interna_detalle con nuevos precios
    5. Actualizar factura_interna con nuevo encabezado y total_monto
    """
    fi_id = int(fi_id)
    lista_precio_id = int(lista_precio_id)
    plazo_id = int(plazo_id)

    # Mapeo de lista_precio_id a columna en v_stock_rimec
    LP_COL_MAP = {1: "lpn", 2: "lpc02", 3: "lpc03", 4: "lpc04"}
    lp_col = LP_COL_MAP.get(lista_precio_id, "lpn")

    try:
        with engine.begin() as conn:
            # 1. Verificar que FI existe y está RESERVADA
            fi_check = conn.execute(sqlt("""
                SELECT id, estado FROM factura_interna WHERE id = :id
            """), {"id": fi_id}).fetchone()

            if not fi_check:
                return False, f"FI ID {fi_id} no encontrada."

            if fi_check.estado != "RESERVADA":
                return False, f"Solo se pueden editar FIs en estado RESERVADA (actual: {fi_check.estado})."

            # 2. Obtener detalles actuales
            detalles = conn.execute(sqlt("""
                SELECT
                    id,
                    cajas,
                    pares,
                    linea_snapshot
                FROM factura_interna_detalle
                WHERE factura_id = :fi_id
            """), {"fi_id": fi_id}).fetchall()

            if not detalles:
                return False, "FI no tiene detalles."

            total_monto_nuevo = 0

            # 3. Para cada detalle, obtener nuevo precio y recalcular
            for det in detalles:
                # Parsear snapshot para obtener identificadores
                snapshot = {}
                if det.linea_snapshot:
                    try:
                        if isinstance(det.linea_snapshot, dict):
                            snapshot = det.linea_snapshot
                        elif isinstance(det.linea_snapshot, str):
                            try:
                                snapshot = json.loads(det.linea_snapshot)
                            except:
                                snapshot = ast.literal_eval(det.linea_snapshot)
                    except:
                        snapshot = {}

                linea_codigo = snapshot.get("linea_codigo")
                ref_codigo = snapshot.get("ref_codigo")
                color_nombre = snapshot.get("color_nombre", "")

                if not all([linea_codigo, ref_codigo]):
                    DBInspector.log(f"[FI] Detalle {det.id} sin códigos completos en snapshot", "WARNING")
                    continue

                # Buscar precio en v_stock_rimec usando códigos
                # Nota: color_code puede no coincidir exactamente con color_nombre,
                # así que buscamos por linea_codigo y referencia_codigo solamente
                precio_query = sqlt(f"""
                    SELECT {lp_col} as precio_base
                    FROM v_stock_rimec
                    WHERE linea_codigo = :linea_codigo
                      AND referencia_codigo = :ref_codigo
                    LIMIT 1
                """)

                precio_row = conn.execute(precio_query, {
                    "linea_codigo": str(linea_codigo),
                    "ref_codigo": str(ref_codigo)
                }).fetchone()

                if not precio_row or not precio_row.precio_base:
                    DBInspector.log(f"[FI] No se encontró precio para detalle {det.id}", "WARNING")
                    continue

                precio_base = float(precio_row.precio_base)

                # Aplicar descuentos en cascada
                precio_con_desc = precio_base
                for desc in [descuento_1, descuento_2, descuento_3, descuento_4]:
                    if desc > 0:
                        precio_con_desc = precio_con_desc * (1 - desc / 100)

                # Redondear a entero
                precio_neto = round(precio_con_desc)
                subtotal = precio_neto * det.pares
                total_monto_nuevo += subtotal

                # Actualizar detalle
                conn.execute(sqlt("""
                    UPDATE factura_interna_detalle
                    SET precio_unit = :precio_base,
                        precio_neto = :precio_neto,
                        subtotal = :subtotal
                    WHERE id = :id
                """), {
                    "id": det.id,
                    "precio_base": precio_base,
                    "precio_neto": precio_neto,
                    "subtotal": subtotal
                })

            # 4. Actualizar encabezado de FI
            conn.execute(sqlt("""
                UPDATE factura_interna
                SET lista_precio_id = :lista,
                    descuento_1 = :d1,
                    descuento_2 = :d2,
                    descuento_3 = :d3,
                    descuento_4 = :d4,
                    plazo_id = :plazo,
                    total_monto = :total
                WHERE id = :id
            """), {
                "id": fi_id,
                "lista": lista_precio_id,
                "d1": descuento_1,
                "d2": descuento_2,
                "d3": descuento_3,
                "d4": descuento_4,
                "plazo": plazo_id,
                "total": round(total_monto_nuevo)
            })

        # Log de auditoría
        log_flujo(
            entidad="factura_interna", entidad_id=fi_id,
            accion="FI_ENCABEZADO_ACTUALIZADO",
            snap={
                "lista_precio_id": lista_precio_id,
                "descuentos": [descuento_1, descuento_2, descuento_3, descuento_4],
                "plazo_id": plazo_id,
                "total_monto_nuevo": round(total_monto_nuevo)
            }
        )

        DBInspector.log(f"[FI] Encabezado actualizado fi_id={fi_id} LP={lista_precio_id}", "SUCCESS")
        return True, f"Encabezado actualizado. Nuevo total: Gs. {round(total_monto_nuevo):,}".replace(",", ".")

    except Exception as e:
        DBInspector.log(f"[FI] Error actualizando encabezado {fi_id}: {e}", "ERROR")
        return False, f"Error: {str(e)}"


def editar_descuentos_fi_confirmada(
    fi_id: int,
    lista_precio_id: int,
    descuento_1: float,
    descuento_2: float,
    descuento_3: float,
    descuento_4: float,
    plazo_id: int
) -> tuple[bool, str]:
    """Permite editar descuentos de una FI CONFIRMADA.

    Flujo:
    1. Verificar que FI está CONFIRMADA
    2. Cambiar temporalmente a RESERVADA
    3. Aplicar actualizar_fi_encabezado()
    4. Volver a CONFIRMADA

    USO: Corregir descuentos mal aplicados en FIs ya confirmadas.
    """
    fi_id = int(fi_id)

    try:
        # 1. Verificar estado actual
        fi_data = get_dataframe("""
            SELECT id, nro_factura, estado, pedido_id
            FROM factura_interna
            WHERE id = :id
        """, {"id": fi_id})

        if fi_data is None or fi_data.empty:
            return False, f"FI ID {fi_id} no encontrada."

        estado_original = fi_data.iloc[0]['estado']
        nro_factura = fi_data.iloc[0]['nro_factura']
        pedido_id = fi_data.iloc[0].get('pedido_id')

        if estado_original != "CONFIRMADA":
            return False, f"Esta función solo edita FIs CONFIRMADAS (actual: {estado_original})."

        # 2. Cambiar temporalmente a RESERVADA
        with engine.begin() as conn:
            conn.execute(sqlt("""
                UPDATE factura_interna
                SET estado = 'RESERVADA'
                WHERE id = :id AND estado = 'CONFIRMADA'
            """), {"id": fi_id})

        DBInspector.log(f"[FI] {nro_factura} temporalmente RESERVADA para edición", "INFO")

        # 3. Aplicar actualización de encabezado
        ok, msg = actualizar_fi_encabezado(
            fi_id=fi_id,
            lista_precio_id=lista_precio_id,
            descuento_1=descuento_1,
            descuento_2=descuento_2,
            descuento_3=descuento_3,
            descuento_4=descuento_4,
            plazo_id=plazo_id
        )

        if not ok:
            # Si falla, intentar revertir a CONFIRMADA
            with engine.begin() as conn:
                conn.execute(sqlt("""
                    UPDATE factura_interna
                    SET estado = 'CONFIRMADA'
                    WHERE id = :id
                """), {"id": fi_id})
            return False, f"Error al actualizar encabezado: {msg}"

        # 4. Volver a CONFIRMADA
        with engine.begin() as conn:
            conn.execute(sqlt("""
                UPDATE factura_interna
                SET estado = 'CONFIRMADA'
                WHERE id = :id AND estado = 'RESERVADA'
            """), {"id": fi_id})

        # 5. Log de auditoría
        log_flujo(
            entidad="factura_interna", entidad_id=fi_id,
            nro_registro=nro_factura,
            accion="FI_DESCUENTOS_EDITADOS_POST_CONFIRMACION",
            estado_antes="CONFIRMADA", estado_despues="CONFIRMADA",
            snap={
                "lista_precio_id": lista_precio_id,
                "descuentos": [descuento_1, descuento_2, descuento_3, descuento_4],
                "plazo_id": plazo_id,
                "pedido_id": pedido_id
            }
        )

        DBInspector.log(f"[FI] {nro_factura} descuentos editados y vuelta a CONFIRMADA", "SUCCESS")
        return True, f"Descuentos actualizados exitosamente. {msg}"

    except Exception as e:
        # Intentar revertir a CONFIRMADA en caso de error
        try:
            with engine.begin() as conn:
                conn.execute(sqlt("""
                    UPDATE factura_interna
                    SET estado = 'CONFIRMADA'
                    WHERE id = :id AND estado = 'RESERVADA'
                """), {"id": fi_id})
        except:
            pass

        DBInspector.log(f"[FI] Error editando descuentos de FI confirmada {fi_id}: {e}", "ERROR")
        return False, f"Error: {str(e)}"
