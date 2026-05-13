# =============================================================================
# MÓDULO: Compra Legal
# ARCHIVO: modules/compra_legal/logic.py
# DESCRIPCIÓN: Capa de datos del módulo.
#
#  Entidades principales:
#    compra_legal          → consolidador de múltiples PPs
#    compra_legal_pedido   → join table PP ↔ CL
#    traspaso              → espejo RIMEC→Bazar (auto-generado por FAC-INT)
#    traspaso_detalle      → líneas resueltas via combinacion_id
#    movimiento            → ingreso real al almacén (crea stock en v_stock_actual)
#
#  Almacenes:
#    id=1  ALM_WEB_01       (destino Web Bazar)
#    id=3  ALM_TRANSITO_01  (origen traspasos desde RIMEC)
#    id=4  ALM_DEPOSITO_RIMEC
# =============================================================================

import json
from datetime import date

import pandas as pd
from sqlalchemy import text as sqlt

from core.database import get_dataframe, engine

ALM_TRANSITO  = 3
ALM_WEB_BAZAR = 1


# ─────────────────────────────────────────────────────────────────────────────
# NUMERACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def get_next_numero_cl(anio: int | None = None) -> str:
    if anio is None:
        anio = date.today().year
    df = get_dataframe("""
        SELECT COALESCE(
            MAX(CAST(SPLIT_PART(numero_registro, '-', 3) AS INTEGER)), 0
        ) AS ultimo
        FROM compra_legal
        WHERE numero_registro ~ '^CL-[0-9]{4}-[0-9]+$'
          AND numero_registro LIKE :patron
    """, {"patron": f"CL-{anio}-%"})
    ultimo = int(df["ultimo"].iloc[0]) if not df.empty else 0
    return f"CL-{anio}-{ultimo + 1:04d}"


def _get_next_traspaso_num_conn(conn, anio: int) -> str:
    """Genera TRP-YYYY-XXXX dentro de una conexión activa (para usar en TX)."""
    result = conn.execute(sqlt("""
        SELECT COALESCE(
            MAX(CAST(SPLIT_PART(numero_registro, '-', 3) AS INTEGER)), 0
        ) AS ultimo
        FROM traspaso
        WHERE numero_registro ~ '^TRP-[0-9]{4}-[0-9]+$'
          AND numero_registro LIKE :patron
    """), {"patron": f"TRP-{anio}-%"}).fetchone()
    ultimo = int(result[0]) if result and result[0] is not None else 0
    return f"TRP-{anio}-{ultimo + 1:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# COMBINACION_ID — puente entre el mundo PP y el mundo Bazar
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_combinacion_id(
    conn,
    linea_cod:    str,
    ref_cod:      str,
    descp_material: str,
    descp_color:    str,
    talla_cod:    str,       # "33", "34", …, "40"
) -> int | None:
    """
    Lookup: (linea.codigo, referencia.codigo, material.descripcion, color.nombre, talla.codigo)
            → combinacion.id
    OT-2026-023: Si no existe, la CREA automáticamente (activo_web=false, sin proveedor_id).
    OT-2026-027: Combinaciones de stock interno no requieren proveedor_web.
    Usa descripción en vez de ID porque ppd.id_material/id_color son IDs del F9
    (espacio distinto al de las tablas material/color internas).
    Retorna combinacion_id (existente o recién creado), o None si faltan entidades base.
    """
    # OT-2026-020: Usar nombres correctos post-migración 004
    row = conn.execute(sqlt("""
        SELECT c.id
        FROM combinacion c
        JOIN linea      l   ON l.id  = c.linea_id      AND l.codigo_proveedor = :linea
        JOIN referencia r   ON r.id  = c.referencia_id AND r.codigo_proveedor = :ref
        JOIN talla      tl  ON tl.id = c.talla_id      AND tl.talla_etiqueta  = :talla
        JOIN material   mat ON mat.id = c.material_id  AND mat.descripcion    = :mat
        JOIN color      col ON col.id = c.color_id     AND col.nombre         = :col
        LIMIT 1
    """), {
        "linea": str(linea_cod).strip(),
        "ref":   str(ref_cod).strip(),
        "talla": str(talla_cod).strip(),
        "mat":   str(descp_material).strip(),
        "col":   str(descp_color).strip(),
    }).fetchone()

    if row:
        return int(row[0])

    # ═══════════════════════════════════════════════════════════════════════════
    # OT-2026-023: CREAR COMBINACIÓN AUTOMÁTICAMENTE si no existe
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. Buscar IDs de las entidades base
    # OT-2026-027: NO incluir proveedor_id - combinacion.proveedor_id es FK a proveedor_web
    #              (distinto de linea.proveedor_id que es FK a proveedor_importacion)
    ids_row = conn.execute(sqlt("""
        SELECT l.id, r.id, mat.id, col.id, tl.id
        FROM linea l
        CROSS JOIN referencia r
        CROSS JOIN material mat
        CROSS JOIN color col
        CROSS JOIN talla tl
        WHERE l.codigo_proveedor = :linea
          AND r.codigo_proveedor = :ref
          AND mat.descripcion    = :mat
          AND col.nombre         = :col
          AND tl.talla_etiqueta  = :talla
        LIMIT 1
    """), {
        "linea": str(linea_cod).strip(),
        "ref":   str(ref_cod).strip(),
        "mat":   str(descp_material).strip(),
        "col":   str(descp_color).strip(),
        "talla": str(talla_cod).strip(),
    }).fetchone()

    if not ids_row:
        # Entidades base no existen → no se puede crear combinación
        return None

    linea_id, ref_id, mat_id, col_id, talla_id = ids_row

    # 2. Crear combinación SIN proveedor_id (para stock interno, no catálogo web)
    # OT-2026-027: proveedor_id requiere FK a proveedor_web (distinto de proveedor_importacion)
    #              Las combinaciones de stock interno no necesitan proveedor_id
    #              Solo las combinaciones activo_web=true necesitan proveedor_web válido
    new_row = conn.execute(sqlt("""
        INSERT INTO combinacion (linea_id, referencia_id, material_id, color_id, talla_id, activo_web)
        VALUES (:linea_id, :ref_id, :mat_id, :col_id, :talla_id, false)
        RETURNING id
    """), {
        "linea_id": linea_id,
        "ref_id":   ref_id,
        "mat_id":   mat_id,
        "col_id":   col_id,
        "talla_id": talla_id,
    }).fetchone()

    return int(new_row[0]) if new_row else None


# ─────────────────────────────────────────────────────────────────────────────
# TRASPASO — espejo automático de FAC-INT para el panel Bazar
# ─────────────────────────────────────────────────────────────────────────────

def crear_traspaso_por_factura(
    conn,                   # conexión activa (dentro de TX de save_factura_manual)
    id_pp:         int,
    id_marca:      int,
    numero_factura: str,
    items_tallas:  list[dict],  # [{linea, referencia, id_material, id_color,
                                #   tallas: {t33:N, t34:N, …}}]
) -> int:
    """
    Crea un registro traspaso (BORRADOR) y sus líneas de detalle.
    OT-2026-023: Crea automáticamente combinaciones faltantes.
    Usa snapshot_json como fallback si entidades base no existen.
    Retorna el id del traspaso creado.
    """
    anio  = date.today().year
    trp_n = _get_next_traspaso_num_conn(conn, anio)

    # OT-2026-026: proveedor_id se obtiene de linea en _resolve_combinacion_id(), no de PP

    snapshot = {
        "numero_factura": numero_factura,
        "id_pp":          id_pp,
        "id_marca":       id_marca,
        "items":          items_tallas,
    }

    row = conn.execute(sqlt("""
        INSERT INTO traspaso (
            numero_registro, anio_fiscal,
            almacen_origen_id, almacen_destino_id,
            estado, snapshot_json, documento_ref
        ) VALUES (
            :num, :anio, :orig, :dest, 'BORRADOR', CAST(:snap AS jsonb), :ref
        )
        RETURNING id
    """), {
        "num":  trp_n,
        "anio": anio,
        "orig": ALM_TRANSITO,
        "dest": ALM_WEB_BAZAR,
        "snap": json.dumps(snapshot),
        "ref":  numero_factura,
    }).fetchone()
    trp_id = int(row[0])

    # Insertar traspaso_detalle para cada (artículo, talla) con qty > 0
    for rec in items_tallas:
        for col, qty_val in rec.get("tallas", {}).items():
            qty = int(qty_val or 0)
            if qty <= 0:
                continue
            t = col.replace("t", "")
            comb_id = _resolve_combinacion_id(
                conn,
                rec.get("linea", ""),
                rec.get("referencia", ""),
                rec.get("material", ""),
                rec.get("color", ""),
                str(t),
                # OT-2026-026: proveedor_id se obtiene internamente de linea
            )
            if comb_id is None:
                continue  # OT-2026-023: entidades base no existen (linea/ref/mat/col/talla) → snapshot como fallback
            conn.execute(sqlt("""
                INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
                VALUES (:trp_id, :comb_id, :qty)
            """), {"trp_id": trp_id, "comb_id": comb_id, "qty": qty})

    return trp_id


# ─────────────────────────────────────────────────────────────────────────────
# TRASPASO MANUAL — crea traspasos desde FAC-INTs existentes al asignar a CL
# ─────────────────────────────────────────────────────────────────────────────

def _crear_traspasos_para_pp(conn, id_pp: int, cl_id: int) -> int:
    """
    Para un PP dado:
      1. Crea traspasos (BORRADOR) para cada FAC-INT que aún no tenga traspaso.
      2. Vincula todos los traspasos del PP a la Compra Legal (cl_id).
    Retorna la cantidad de traspasos nuevos creados.

    OT-2026-017: Ahora procesa AMBAS tablas: venta_transito (legacy) y factura_interna (nuevo flujo).
    """
    creados = 0

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOQUE 1: FAC-INTs de venta_transito (legacy) sin traspaso
    # ═══════════════════════════════════════════════════════════════════════════
    facturas_legacy = conn.execute(sqlt("""
        SELECT DISTINCT vt.numero_factura_interna
        FROM venta_transito vt
        WHERE vt.pedido_proveedor_id = :id_pp
          AND NOT EXISTS (
              SELECT 1 FROM traspaso t WHERE t.documento_ref = vt.numero_factura_interna
          )
    """), {"id_pp": id_pp}).fetchall()

    for (factura,) in facturas_legacy:
        # Extraer id_marca del nombre: FAC-INT-{id_pp}-{id_marca}-NNNN
        partes = factura.split("-")
        try:
            id_marca = int(partes[3])
        except (IndexError, ValueError):
            id_marca = 0

        # Leer filas de detalle (una fila por SKU de venta_transito)
        rows = conn.execute(sqlt("""
            SELECT
                ppd.linea, ppd.referencia,
                ppd.id_material, ppd.id_color,
                ppd.descp_material,  ppd.descp_color,
                vt.t33, vt.t34, vt.t35, vt.t36,
                vt.t37, vt.t38, vt.t39, vt.t40
            FROM venta_transito vt
            JOIN pedido_proveedor_detalle ppd
              ON ppd.id = vt.pedido_proveedor_detalle_id
            WHERE vt.numero_factura_interna = :factura
              AND vt.pedido_proveedor_id    = :id_pp
        """), {"factura": factura, "id_pp": id_pp}).fetchall()

        items_tallas = []
        for r in rows:
            tallas = {
                f"t{t}": int(r[6 + (t - 33)] or 0)
                for t in range(33, 41)
            }
            items_tallas.append({
                "linea":       r[0] or "",
                "referencia":  r[1] or "",
                "id_material": int(r[2] or 0),
                "id_color":    int(r[3] or 0),
                "material":    r[4] or "",
                "color":       r[5] or "",
                "tallas":      {k: v for k, v in tallas.items() if v > 0},
            })

        if not items_tallas:
            continue

        trp_id = crear_traspaso_por_factura(conn, id_pp, id_marca, factura, items_tallas)
        conn.execute(sqlt("""
            UPDATE traspaso SET compra_legal_id = :cl_id WHERE id = :trp_id
        """), {"cl_id": cl_id, "trp_id": trp_id})
        creados += 1

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOQUE 2: FAC-INTs de factura_interna (nuevo flujo) sin traspaso
    # OT-2026-017: Agrega soporte para tabla factura_interna
    # ═══════════════════════════════════════════════════════════════════════════
    facturas_nuevas = conn.execute(sqlt("""
        SELECT DISTINCT fi.id, fi.nro_factura AS numero_factura,
               COALESCE(MIN(ppd.id_marca), 0) AS id_marca
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
        WHERE fi.pp_id = :id_pp
          AND fi.estado IN ('CONFIRMADA', 'RESERVADA')
          AND NOT EXISTS (
              SELECT 1 FROM traspaso t WHERE t.documento_ref = fi.nro_factura
          )
        GROUP BY fi.id, fi.nro_factura
    """), {"id_pp": id_pp}).fetchall()

    for (fi_id, nro_factura, id_marca) in facturas_nuevas:

        # Leer detalles de FI con grades_json + fallback linea_snapshot
        # OT-2026-019: Agregar fallbacks para tallas
        # OT-2026-025: fid.pares debe contener el saldo correcto (lo facturado)
        #              El problema estaría upstream si contiene cantidad_pares (total F9)
        rows = conn.execute(sqlt("""
            SELECT
                ppd.linea, ppd.referencia,
                ppd.id_material, ppd.id_color,
                ppd.descp_material, ppd.descp_color,
                ppd.grades_json,
                fid.linea_snapshot,
                fid.pares
            FROM factura_interna_detalle fid
            JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
            WHERE fid.factura_id = :fi_id
        """), {"fi_id": fi_id}).fetchall()

        items_tallas = []
        for r in rows:
            linea, ref, id_mat, id_col, mat, col, grades_json, linea_snapshot, pares = r

            tallas = {}

            # ══════════════════════════════════════════════════════════════
            # INTENTO 1: Parsear grades_json (desde ppd)
            # ══════════════════════════════════════════════════════════════
            if grades_json:
                try:
                    grades = json.loads(grades_json) if isinstance(grades_json, str) else grades_json
                    for talla_str, qty in (grades or {}).items():
                        talla_num = int(talla_str)
                        tallas[f"t{talla_num}"] = int(qty)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

            # ══════════════════════════════════════════════════════════════
            # INTENTO 2 (fallback): Parsear gradas_fmt desde linea_snapshot
            # OT-2026-019: Agregar fallback para casos donde grades_json es null
            # ══════════════════════════════════════════════════════════════
            if not tallas and linea_snapshot:
                try:
                    try:
                        snapshot = json.loads(linea_snapshot) if isinstance(linea_snapshot, str) else linea_snapshot
                    except json.JSONDecodeError:
                        import ast
                        snapshot = ast.literal_eval(linea_snapshot) if isinstance(linea_snapshot, str) else linea_snapshot
                    gradas_fmt = snapshot.get("gradas_fmt", "") if snapshot else ""

                    # Parsear formato "17(1-1-2-2-2-1-1)25" → {t17:1, t18:1, t19:2, ...}
                    if gradas_fmt and "(" in gradas_fmt and ")" in gradas_fmt:
                        inicio_str, resto = gradas_fmt.split("(", 1)
                        cantidades_str, fin_str = resto.split(")", 1)

                        talla_inicio = int(inicio_str.strip())
                        cantidades = [int(x.strip()) for x in cantidades_str.split("-") if x.strip()]

                        for idx, qty in enumerate(cantidades):
                            talla_num = talla_inicio + idx
                            if qty > 0:
                                tallas[f"t{talla_num}"] = qty
                except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                    pass

            # ══════════════════════════════════════════════════════════════
            # INTENTO 3 (último fallback): Distribuir pares uniformemente
            # OT-2026-019: En lugar de fallar, distribuir en talla 37 (genérica)
            # ══════════════════════════════════════════════════════════════
            if not tallas and pares and pares > 0:
                tallas["t37"] = int(pares)  # Talla genérica 37

            # Si después de todos los intentos no hay tallas, skip este item
            if not tallas:
                continue

            items_tallas.append({
                "linea":       linea or "",
                "referencia":  ref or "",
                "id_material": int(id_mat or 0),
                "id_color":    int(id_col or 0),
                "material":    mat or "",
                "color":       col or "",
                "tallas":      tallas,
            })

        if not items_tallas:
            continue  # Sin distribución de tallas válida, pasar a siguiente FI

        trp_id = crear_traspaso_por_factura(conn, id_pp, id_marca, nro_factura, items_tallas)
        conn.execute(sqlt("""
            UPDATE traspaso SET compra_legal_id = :cl_id WHERE id = :trp_id
        """), {"cl_id": cl_id, "trp_id": trp_id})
        creados += 1

    # ═══════════════════════════════════════════════════════════════════════════
    # VINCULAR traspasos preexistentes de AMBAS tablas
    # ═══════════════════════════════════════════════════════════════════════════
    conn.execute(sqlt("""
        UPDATE traspaso
        SET compra_legal_id = :cl_id
        WHERE compra_legal_id IS NULL
          AND (
              documento_ref IN (
                  SELECT DISTINCT vt.numero_factura_interna
                  FROM venta_transito vt
                  WHERE vt.pedido_proveedor_id = :id_pp
              )
              OR documento_ref IN (
                  SELECT fi.nro_factura
                  FROM factura_interna fi
                  WHERE fi.pp_id = :id_pp
              )
          )
    """), {"cl_id": cl_id, "id_pp": id_pp})

    return creados


# ─────────────────────────────────────────────────────────────────────────────
# COMPRA LEGAL — lista y creación
# ─────────────────────────────────────────────────────────────────────────────

def get_compras_legales() -> pd.DataFrame:
    """Lista de Compras Legales con KPIs básicos."""
    return get_dataframe("""
        SELECT
            cl.id,
            cl.numero_registro,
            cl.numero_factura_proveedor         AS proforma_referencia,
            cl.fecha_factura,
            cl.estado,
            cl.created_at,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT pp.numero_registro, ' / '
                                   ORDER BY pp.numero_registro)
                 FROM compra_legal_pedido clp
                 JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
                 WHERE clp.compra_legal_id = cl.id),
                '—'
            )                                   AS pps_vinculados,
            COALESCE(
                (SELECT SUM(pp2.pares_comprometidos)
                 FROM compra_legal_pedido clp2
                 JOIN pedido_proveedor pp2 ON pp2.id = clp2.pedido_proveedor_id
                 WHERE clp2.compra_legal_id = cl.id),
                0
            )                                   AS total_pares,
            (SELECT COUNT(*)
             FROM traspaso t
             WHERE t.compra_legal_id = cl.id)   AS n_traspasos,
            (SELECT COUNT(*)
             FROM traspaso t
             WHERE t.compra_legal_id = cl.id
               AND t.estado = 'CONFIRMADO')     AS n_confirmados
        FROM compra_legal cl
        ORDER BY cl.fecha_factura DESC, cl.id DESC
    """)


def get_compras_por_proforma(numero_proforma: str) -> pd.DataFrame:
    """
    Compras PENDIENTES disponibles para recibir un PP de esta proforma.
    Muestra todas las compras cuya numero_factura_proveedor coincide,
    independientemente de si ya tienen PPs vinculados o no.
    Solo muestra compras en estado PENDIENTE (aún abiertas para recibir PPs).
    """
    return get_dataframe("""
        SELECT
            cl.id,
            cl.numero_registro,
            cl.estado,
            COALESCE(
                (SELECT STRING_AGG(pp.numero_registro, ', ')
                 FROM compra_legal_pedido clp
                 JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
                 WHERE clp.compra_legal_id = cl.id),
                'Sin PPs aún'
            ) AS pps_vinculados
        FROM compra_legal cl
        WHERE cl.numero_factura_proveedor = :proforma
          AND cl.estado = 'PENDIENTE'
        ORDER BY cl.id DESC
    """, {"proforma": str(numero_proforma).strip()})


def pp_ya_en_compra(id_pp: int) -> int | None:
    """Retorna el compra_legal_id si el PP ya está en alguna Compra, o None."""
    df = get_dataframe("""
        SELECT compra_legal_id FROM compra_legal_pedido
        WHERE pedido_proveedor_id = :id_pp
        LIMIT 1
    """, {"id_pp": id_pp})
    if df.empty:
        return None
    return int(df["compra_legal_id"].iloc[0])


def _marcar_pp_enviado(conn, id_pp: int) -> None:
    """Cambia pedido_proveedor.estado = 'ENVIADO' dentro de una TX abierta."""
    conn.execute(sqlt("""
        UPDATE pedido_proveedor SET estado = 'ENVIADO'
        WHERE id = :id_pp AND estado != 'ENVIADO'
    """), {"id_pp": id_pp})


def create_compra_legal(id_pp: int, numero_proforma: str) -> tuple[bool, str]:
    """Crea una Compra Legal nueva y vincula el PP. Cambia PP a estado ENVIADO."""
    try:
        with engine.begin() as conn:
            numero = get_next_numero_cl()
            row = conn.execute(sqlt("""
                INSERT INTO compra_legal (
                    numero_registro, anio_fiscal,
                    numero_factura_proveedor,
                    fecha_factura, moneda, estado
                ) VALUES (
                    :num, :anio, :proforma, CURRENT_DATE, 'USD', 'PENDIENTE'
                )
                RETURNING id
            """), {
                "num":      numero,
                "anio":     date.today().year,
                "proforma": str(numero_proforma).strip(),
            }).fetchone()
            cl_id = int(row[0])

            conn.execute(sqlt("""
                INSERT INTO compra_legal_pedido (compra_legal_id, pedido_proveedor_id)
                VALUES (:cl_id, :pp_id)
            """), {"cl_id": cl_id, "pp_id": id_pp})

            _marcar_pp_enviado(conn, id_pp)

        return True, numero
    except Exception as e:
        return False, str(e)


def add_pp_to_compra(compra_id: int, id_pp: int) -> tuple[bool, str]:
    """Agrega un PP a una Compra Legal existente. Cambia PP a estado ENVIADO."""
    try:
        with engine.begin() as conn:
            exists = conn.execute(sqlt("""
                SELECT 1 FROM compra_legal_pedido
                WHERE compra_legal_id = :cl_id AND pedido_proveedor_id = :pp_id
            """), {"cl_id": compra_id, "pp_id": id_pp}).fetchone()

            if exists:
                return True, "El PP ya estaba vinculado a esta compra."

            conn.execute(sqlt("""
                INSERT INTO compra_legal_pedido (compra_legal_id, pedido_proveedor_id)
                VALUES (:cl_id, :pp_id)
            """), {"cl_id": compra_id, "pp_id": id_pp})

            _marcar_pp_enviado(conn, id_pp)

        return True, "PP agregado a la compra."
    except Exception as e:
        return False, str(e)


def get_pps_de_compra(id_cl: int) -> pd.DataFrame:
    """Lista de PPs vinculados a una Compra con sus KPIs."""
    return get_dataframe("""
        SELECT
            pp.id,
            pp.numero_registro,
            pp.numero_proforma,
            pp.estado,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT mv.descp_marca, ' / ')
                 FROM pedido_proveedor_detalle ppd2
                 JOIN marca_v2 mv ON mv.id_marca = ppd2.id_marca
                 WHERE ppd2.pedido_proveedor_id = pp.id),
                '—'
            )                                   AS marcas,
            COALESCE(SUM(ppd.cantidad_pares), 0) AS total_pares,
            COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_id = pp.id),
                0
            )                                   AS total_vendido
        FROM compra_legal_pedido clp
        JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
        LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
        WHERE clp.compra_legal_id = :id_cl
        GROUP BY pp.id, pp.numero_registro, pp.numero_proforma, pp.estado
        ORDER BY pp.numero_registro
    """, {"id_cl": id_cl})


def rechazar_pp_de_compra(id_cl: int, id_pp: int) -> tuple[bool, str]:
    """
    Rechaza un PP desde COMPRA:
      1. Elimina de compra_legal_pedido.
      2. Limpia traspasos BORRADOR del PP en esta compra.
      3. Devuelve el PP a estado 'ABIERTO'.
    """
    try:
        with engine.begin() as conn:
            # Limpiar traspasos BORRADOR vinculados a FAC-INTs del PP en esta compra
            conn.execute(sqlt("""
                UPDATE traspaso
                SET compra_legal_id = NULL
                WHERE compra_legal_id = :id_cl
                  AND estado = 'BORRADOR'
                  AND documento_ref IN (
                      SELECT vt.numero_factura_interna
                      FROM venta_transito vt
                      WHERE vt.pedido_proveedor_id = :id_pp
                  )
            """), {"id_cl": id_cl, "id_pp": id_pp})

            conn.execute(sqlt("""
                DELETE FROM compra_legal_pedido
                WHERE compra_legal_id = :id_cl AND pedido_proveedor_id = :id_pp
            """), {"id_cl": id_cl, "id_pp": id_pp})

            conn.execute(sqlt("""
                UPDATE pedido_proveedor SET estado = 'ABIERTO'
                WHERE id = :id_pp
            """), {"id_pp": id_pp})

        return True, "PP rechazado y devuelto a estado ABIERTO."
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# COMPRA LEGAL — detalle (Hija Depósito + Hija Facturación)
# ─────────────────────────────────────────────────────────────────────────────

def get_compra_header(id_cl: int) -> dict:
    df = get_dataframe("""
        SELECT
            cl.id,
            cl.numero_registro,
            cl.numero_factura_proveedor  AS proforma,
            cl.fecha_factura,
            cl.estado,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT pp.numero_registro, ' / '
                                   ORDER BY pp.numero_registro)
                 FROM compra_legal_pedido clp
                 JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
                 WHERE clp.compra_legal_id = cl.id),
                '—'
            ) AS pps_vinculados,
            COALESCE(
                (SELECT SUM(pp2.pares_comprometidos)
                 FROM compra_legal_pedido clp2
                 JOIN pedido_proveedor pp2 ON pp2.id = clp2.pedido_proveedor_id
                 WHERE clp2.compra_legal_id = cl.id),
                0
            ) AS total_pares_f9,
            COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_id IN (
                     SELECT pedido_proveedor_id FROM compra_legal_pedido
                     WHERE compra_legal_id = cl.id
                 )),
                0
            ) +
            COALESCE(
                (SELECT SUM(fid.pares)
                 FROM factura_interna fi
                 JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
                 WHERE fi.pp_id IN (
                     SELECT pedido_proveedor_id FROM compra_legal_pedido
                     WHERE compra_legal_id = cl.id
                 )
                 AND fi.estado IN ('CONFIRMADA', 'RESERVADA')),
                0
            ) AS pares_facturados
        FROM compra_legal cl
        WHERE cl.id = :id_cl
    """, {"id_cl": id_cl})
    if df.empty:
        return {}
    r = df.iloc[0]
    return {
        "id":               int(r["id"]),
        "numero_registro":  str(r["numero_registro"]),
        "proforma":         str(r["proforma"] or "—"),
        "fecha_factura":    r["fecha_factura"],
        "estado":           str(r["estado"]),
        "pps_vinculados":   str(r["pps_vinculados"]),
        "total_pares_f9":   int(r["total_pares_f9"] or 0),
        "pares_facturados": int(r["pares_facturados"] or 0),
    }


def get_compra_hija_deposito(id_cl: int) -> pd.DataFrame:
    """
    Hija Depósito: stock no vendido de los PPs de esta compra.
    Columnas: marca, linea, referencia, material, color, cantidad_inicial, vendido, saldo
    """
    return get_dataframe("""
        SELECT
            COALESCE(mv.descp_marca, '—')                               AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                                           AS material,
            ppd.descp_color                                              AS color,
            ppd.cantidad_pares                                           AS cantidad_inicial,
            COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_detalle_id = ppd.id),
                0
            )                                                            AS vendido,
            ppd.cantidad_pares - COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_detalle_id = ppd.id),
                0
            )                                                            AS saldo
        FROM compra_legal_pedido clp
        JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = clp.pedido_proveedor_id
        LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE clp.compra_legal_id = :id_cl
          AND ppd.linea IS NOT NULL
        ORDER BY mv.descp_marca, ppd.linea, ppd.referencia
    """, {"id_cl": id_cl})


def get_compra_hija_facturacion(id_cl: int) -> pd.DataFrame:
    """
    Hija Facturación: ventas internas (FAC-INT) de los PPs de esta compra.
    Columnas: marca, factura, fecha, cliente, linea, referencia, material, color,
              grada, t33-t40, pares, traspaso_estado

    MODIFICADO (OT-2026-011/OT-2026-015): Busca en factura_interna (RIMEC) y venta_transito (legacy).
    """
    return get_dataframe("""
        -- Nueva tabla factura_interna (flujo RIMEC)
        SELECT
            COALESCE(fi.marca, '—')                     AS marca,
            fi.nro_factura                              AS factura,
            fi.created_at::date                         AS fecha,
            COALESCE(cv.descp_cliente, fi.cliente_id::text) AS cliente,
            (fid.linea_snapshot->>'linea_codigo')       AS linea,
            (fid.linea_snapshot->>'ref_codigo')         AS referencia,
            COALESCE(
                (fid.linea_snapshot->>'material_nombre'),
                ppd.descp_material,
                '—'
            )                                           AS material,
            (fid.linea_snapshot->>'color_nombre')       AS color,
            (fid.linea_snapshot->>'gradas_fmt')         AS grada,
            0 AS t33, 0 AS t34, 0 AS t35, 0 AS t36,
            0 AS t37, 0 AS t38, 0 AS t39, 0 AS t40,
            SUM(fid.pares)                              AS pares,
            COALESCE(
                (SELECT t.estado FROM traspaso t
                 WHERE t.documento_ref = fi.nro_factura
                 LIMIT 1),
                'SIN_TRASPASO'
            )                                           AS traspaso_estado
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        LEFT JOIN cliente_v2 cv ON cv.id_cliente = fi.cliente_id
        LEFT JOIN pedido_proveedor_detalle ppd
            ON ppd.pedido_proveedor_id = fi.pp_id
            AND ppd.linea = (fid.linea_snapshot->>'linea_codigo')
            AND ppd.referencia = (fid.linea_snapshot->>'ref_codigo')
        WHERE fi.pp_id IN (
            SELECT pedido_proveedor_id FROM compra_legal_pedido
            WHERE compra_legal_id = :id_cl
        )
        AND fi.estado IN ('CONFIRMADA', 'RESERVADA')
        GROUP BY fi.marca, fi.nro_factura, fi.created_at, cv.descp_cliente,
                 fi.cliente_id, fid.linea_snapshot, ppd.descp_material

        UNION ALL

        -- Legacy tabla venta_transito
        SELECT
            COALESCE(mv.descp_marca, '—')               AS marca,
            vt.numero_factura_interna                   AS factura,
            MIN(vt.fecha_operacion)                     AS fecha,
            COALESCE(cv.descp_cliente, vt.codigo_cliente) AS cliente,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                          AS material,
            ppd.descp_color                             AS color,
            ppd.grada,
            SUM(vt.t33) AS t33, SUM(vt.t34) AS t34,
            SUM(vt.t35) AS t35, SUM(vt.t36) AS t36,
            SUM(vt.t37) AS t37, SUM(vt.t38) AS t38,
            SUM(vt.t39) AS t39, SUM(vt.t40) AS t40,
            SUM(vt.cantidad_vendida)                    AS pares,
            COALESCE(
                (SELECT t.estado FROM traspaso t
                 WHERE t.documento_ref = vt.numero_factura_interna
                 LIMIT 1),
                'SIN_TRASPASO'
            )                                           AS traspaso_estado
        FROM venta_transito vt
        JOIN pedido_proveedor_detalle ppd ON ppd.id = vt.pedido_proveedor_detalle_id
        LEFT JOIN marca_v2   mv ON mv.id_marca   = ppd.id_marca
        LEFT JOIN cliente_v2 cv ON cv.id_cliente::text = vt.codigo_cliente
        WHERE vt.pedido_proveedor_id IN (
            SELECT pedido_proveedor_id FROM compra_legal_pedido
            WHERE compra_legal_id = :id_cl
        )
        GROUP BY mv.descp_marca, vt.numero_factura_interna, vt.codigo_cliente,
                 cv.descp_cliente, ppd.linea, ppd.referencia,
                 ppd.descp_material, ppd.descp_color, ppd.grada

        ORDER BY marca, factura, linea
    """, {"id_cl": id_cl})


# ─────────────────────────────────────────────────────────────────────────────
# FINALIZAR COMPRA — crea traspasos y marca la compra como DISTRIBUIDA
# ─────────────────────────────────────────────────────────────────────────────

def finalizar_compra(id_cl: int) -> tuple[bool, str]:
    """
    Acción manual "Finalizar y Distribuir":
      1. Para cada PP vinculado, crea traspasos (BORRADOR) por cada FAC-INT.
      2. Marca compra_legal.estado = 'DISTRIBUIDA'.
    Después de esto, FACTURACIÓN ve las facturas y puede enviarlas a Bazar.
    """
    try:
        with engine.begin() as conn:
            pps = conn.execute(sqlt("""
                SELECT pedido_proveedor_id FROM compra_legal_pedido
                WHERE compra_legal_id = :id_cl
            """), {"id_cl": id_cl}).fetchall()

            total_nuevos = 0
            for (id_pp,) in pps:
                total_nuevos += _crear_traspasos_para_pp(conn, id_pp, id_cl)

            conn.execute(sqlt("""
                UPDATE compra_legal SET estado = 'DISTRIBUIDA'
                WHERE id = :id_cl
            """), {"id_cl": id_cl})

        return True, f"Compra distribuida. {total_nuevos} traspaso(s) nuevo(s) creado(s)."
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# ENVIAR A WEB — cambia traspaso BORRADOR → ENVIADO
# ─────────────────────────────────────────────────────────────────────────────

def enviar_compra_a_web(id_cl: int) -> tuple[bool, str]:
    """
    Marca todos los traspasos BORRADOR de esta compra como ENVIADO.
    Bazar ahora puede ver el botón 'Procesar Ingreso'.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(sqlt("""
                UPDATE traspaso
                SET estado = 'ENVIADO'
                WHERE compra_legal_id = :id_cl
                  AND estado = 'BORRADOR'
                RETURNING id
            """), {"id_cl": id_cl})
            n = len(result.fetchall())

            conn.execute(sqlt("""
                UPDATE compra_legal SET estado = 'ENVIADO'
                WHERE id = :id_cl
            """), {"id_cl": id_cl})

        return True, f"{n} traspaso(s) marcados como ENVIADO."
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# VISTA BAZAR — lista y detalle de traspasos
# ─────────────────────────────────────────────────────────────────────────────

def get_traspasos(estado: str | None = None) -> pd.DataFrame:
    """Lista de traspasos para el panel Bazar.
    OT-2026-029: Filtrar por almacen_destino_id=1 (ALM_WEB_01) para Compra Web.
    """
    where = "WHERE t.almacen_destino_id = :alm"
    params: dict = {"alm": ALM_WEB_BAZAR}  # = 1

    if estado:
        where += " AND t.estado = :estado"
        params["estado"] = estado

    return get_dataframe(f"""
        SELECT
            t.id,
            t.numero_registro,
            t.fecha_traspaso,
            t.estado,
            t.documento_ref                      AS factura,
            t.compra_legal_id,
            COALESCE(cl.numero_registro, '—')    AS compra,
            COALESCE(
                (SELECT SUM(td.cantidad)
                 FROM traspaso_detalle td WHERE td.traspaso_id = t.id),
                0
            )                                    AS pares_detalle,
            t.snapshot_json
        FROM traspaso t
        LEFT JOIN compra_legal cl ON cl.id = t.compra_legal_id
        {where}
        ORDER BY t.fecha_traspaso DESC, t.id DESC
    """, params)


def get_traspaso_detail(id_trp: int) -> dict:
    df = get_dataframe("""
        SELECT
            t.id, t.numero_registro, t.fecha_traspaso, t.estado,
            t.documento_ref AS factura, t.snapshot_json,
            COALESCE(cl.numero_registro, '—') AS compra
        FROM traspaso t
        LEFT JOIN compra_legal cl ON cl.id = t.compra_legal_id
        WHERE t.id = :id_trp
    """, {"id_trp": id_trp})
    if df.empty:
        return {}
    r = df.iloc[0]
    snap = r["snapshot_json"] if isinstance(r["snapshot_json"], dict) else {}
    return {
        "id":              int(r["id"]),
        "numero_registro": str(r["numero_registro"]),
        "fecha_traspaso":  r["fecha_traspaso"],
        "estado":          str(r["estado"]),
        "factura":         str(r["factura"] or "—"),
        "compra":          str(r["compra"]),
        "snapshot":        snap,
    }


def get_traspaso_detalle_lines(id_trp: int) -> pd.DataFrame:
    """
    Líneas del traspaso con 5 pilares + talla + precio + caso.
    OT-2026-021: Si traspaso_detalle está vacío, lee desde snapshot_json como fallback.
    """
    print(f"DEBUG get_traspaso_detalle_lines id_trp={id_trp}")

    # Intentar leer líneas resueltas desde traspaso_detalle
    df = get_dataframe("""
        SELECT
            td.id,
            td.combinacion_id,
            l.codigo_proveedor   AS linea,
            r.codigo_proveedor   AS referencia,
            mat.descripcion      AS material,
            col.nombre           AS color,
            tl.talla_etiqueta    AS talla,
            td.cantidad,
            COALESCE(pl.nombre_caso_aplicado, '—') AS caso_nombre
        FROM traspaso_detalle td
        JOIN combinacion c  ON c.id  = td.combinacion_id
        JOIN linea       l  ON l.id  = c.linea_id
        JOIN referencia  r  ON r.id  = c.referencia_id
        LEFT JOIN material   mat ON mat.id = c.material_id
        LEFT JOIN color      col ON col.id = c.color_id
        JOIN talla       tl ON tl.id = c.talla_id
        LEFT JOIN traspaso t ON t.id = td.traspaso_id
        LEFT JOIN factura_interna fi ON fi.nro_factura = t.documento_ref
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
        LEFT JOIN precio_lista pl ON pl.evento_id = icp.precio_evento_id
            AND pl.linea_codigo = l.codigo_proveedor::text
            AND pl.referencia_codigo = r.codigo_proveedor::text
        WHERE td.traspaso_id = :id_trp
        ORDER BY l.codigo_proveedor, r.codigo_proveedor, tl.talla_etiqueta
    """, {"id_trp": id_trp})

    print(f"DEBUG df.shape={df.shape} df.empty={df.empty}")

    # OT-2026-021: FALLBACK - Si está vacío, leer desde snapshot_json
    if df.empty:
        snap_df = get_dataframe("""
            SELECT
                t.snapshot_json,
                MAX(pl.nombre_caso_aplicado) AS caso_nombre
            FROM traspaso t
            LEFT JOIN factura_interna fi ON fi.nro_factura = t.documento_ref
            LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
            LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
            LEFT JOIN precio_lista pl ON pl.evento_id = icp.precio_evento_id
            WHERE t.id = :id_trp
            GROUP BY t.id, t.snapshot_json
        """, {"id_trp": id_trp})

        if not snap_df.empty and snap_df["snapshot_json"].iloc[0]:
            try:
                import json
                import ast
                snapshot = snap_df["snapshot_json"].iloc[0]
                if isinstance(snapshot, str):
                    try:
                        snapshot = json.loads(snapshot)
                    except json.JSONDecodeError:
                        snapshot = ast.literal_eval(snapshot)

                caso_nombre = snap_df["caso_nombre"].iloc[0] or "—"
                items = snapshot.get("items", [])

                # Expandir tallas de cada item
                rows = []
                for item in items:
                    linea = item.get("linea", "")
                    ref = item.get("referencia", "")
                    mat = item.get("material", "")
                    col = item.get("color", "")
                    tallas = item.get("tallas", {})

                    for talla_key, qty in tallas.items():
                        if qty > 0:
                            talla_num = talla_key.replace("t", "")
                            rows.append({
                                "id": None,
                                "combinacion_id": None,
                                "linea": linea,
                                "referencia": ref,
                                "material": mat,
                                "color": col,
                                "talla": talla_num,
                                "cantidad": qty,
                                "caso_nombre": caso_nombre
                            })

                if rows:
                    df = pd.DataFrame(rows)
            except (json.JSONDecodeError, KeyError, AttributeError):
                pass

    return df


# ─────────────────────────────────────────────────────────────────────────────
# PROCESAR INGRESO — crea movimiento + inyecta stock en ALM_WEB_01
# ─────────────────────────────────────────────────────────────────────────────

def procesar_ingreso_bazar(id_trp: int) -> tuple[bool, str]:
    """
    Procesa el ingreso del traspaso al depósito Web Bazar:
      1. Valida que estado = ENVIADO
      2. Crea un movimiento de tipo INGRESO_COMPRA → ALM_WEB_01
      3. Inserta movimiento_detalle por cada línea de traspaso_detalle
      4. Marca traspaso.estado = CONFIRMADO
    Stock resulta disponible en v_stock_actual para ALM_WEB_01.
    """
    try:
        with engine.begin() as conn:
            # Verificar estado
            row = conn.execute(sqlt("""
                SELECT estado, numero_registro, documento_ref
                FROM traspaso WHERE id = :id_trp FOR UPDATE
            """), {"id_trp": id_trp}).fetchone()

            if not row:
                return False, "Traspaso no encontrado."
            if row[0] not in ("ENVIADO", "BORRADOR"):
                return False, f"Traspaso en estado '{row[0]}' — no se puede procesar."

            trp_num = str(row[1])

            # Crear movimiento
            mov_row = conn.execute(sqlt("""
                INSERT INTO movimiento (
                    tipo, fecha,
                    almacen_origen_id, almacen_destino_id,
                    documento_ref, estado
                ) VALUES (
                    'INGRESO_COMPRA', CURRENT_DATE,
                    :orig, :dest, :doc, 'CONFIRMADO'
                )
                RETURNING id
            """), {
                "orig": ALM_TRANSITO,
                "dest": ALM_WEB_BAZAR,
                "doc":  trp_num,
            }).fetchone()
            mov_id = int(mov_row[0])

            # Insertar movimiento_detalle desde traspaso_detalle
            lines = conn.execute(sqlt("""
                SELECT combinacion_id, cantidad
                FROM traspaso_detalle
                WHERE traspaso_id = :id_trp
            """), {"id_trp": id_trp}).fetchall()

            n_lines = 0
            for comb_id, qty in lines:
                conn.execute(sqlt("""
                    INSERT INTO movimiento_detalle
                        (movimiento_id, combinacion_id, cantidad, signo)
                    VALUES (:mov_id, :comb_id, :qty, 1)
                """), {"mov_id": mov_id, "comb_id": comb_id, "qty": int(qty)})
                n_lines += 1

            # Confirmar traspaso
            conn.execute(sqlt("""
                UPDATE traspaso
                SET estado        = 'CONFIRMADO',
                    confirmado_en = NOW()
                WHERE id = :id_trp
            """), {"id_trp": id_trp})

        return True, f"Ingreso procesado: {n_lines} línea(s) en depósito Web Bazar."
    except Exception as e:
        return False, str(e)
