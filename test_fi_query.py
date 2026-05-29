"""Script temporal para probar la consulta de FI 82"""
from core.database import get_dataframe

query = """
SELECT
    fi.id,
    fi.nro_factura,
    fi.pp_id,
    pp.numero_registro as pp_nro,
    pp.numero_proforma as proforma,
    qa.descripcion as quincena_llegada,
    fi.marca,
    fi.caso,
    fi.total_pares,
    fi.total_monto,
    fi.estado,
    fi.cliente_id,
    c.descp_cliente as cliente_nombre,
    c.codigo_cliente as cliente_codigo,
    fi.vendedor_id,
    v.descp_usuario as vendedor_nombre,
    fi.plazo_id,
    pl.descp_plazo as plazo_nombre,
    fi.lista_precio_id,
    fi.descuento_1,
    fi.descuento_2,
    fi.descuento_3,
    fi.descuento_4,
    fi.created_at
FROM public.factura_interna fi
LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
LEFT JOIN public.quincena_arribo qa ON qa.id = pp.quincena_arribo_id
LEFT JOIN public.cliente_v2 c ON c.id_cliente = fi.cliente_id
LEFT JOIN public.usuario_v2 v ON v.id_usuario = fi.vendedor_id
LEFT JOIN public.plazo_v2 pl ON pl.id_plazo = fi.plazo_id
WHERE fi.id = 82
LIMIT 1
"""

print("Ejecutando consulta para FI 82...")
df = get_dataframe(query)

if df is not None and not df.empty:
    print('✅ Query exitosa')
    print(f'Filas: {len(df)}')
    print(f'\nDatos de la FI:')
    for col in df.columns:
        print(f"  {col}: {df.iloc[0][col]}")
else:
    print('❌ Query falló o retornó vacío')
    print(f'df es None: {df is None}')
    if df is not None:
        print(f'df está vacío: {df.empty}')
