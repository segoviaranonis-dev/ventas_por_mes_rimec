import pandas as pd
from core.queries import get_dataframe
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

old_viewdef = get_dataframe("SELECT pg_get_viewdef('v_stock_web', true)").iloc[0, 0]

# old_viewdef ends with `LEFT JOIN marca_v2 mv ON mv.id_marca = agg.id_marca_ref;`
# the SELECT part is: `SELECT c.id AS combinacion_id, ...`
# Let's string replace to add the two columns.
new_viewdef = old_viewdef.replace(
    "ge.id_grupo_estilo AS estilo_id",
    "ge.id_grupo_estilo AS estilo_id,\n    mat.codigo_proveedor AS material_code,\n    col.codigo_proveedor AS color_code"
)

with engine.begin() as conn:
    conn.execute(text("CREATE OR REPLACE VIEW v_stock_web AS\n" + new_viewdef))

print("v_stock_web updated successfully with material_code and color_code")
