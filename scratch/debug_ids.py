from core.database import get_dataframe
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print("--- LINEA 2126 ---")
df_l = get_dataframe("SELECT id, codigo_proveedor FROM linea WHERE codigo_proveedor ~ '2126'")
print(df_l)

if not df_l.empty:
    l_ids = df_l['id'].tolist()
    print("\n--- REFERENCIA 526 ---")
    df_r = get_dataframe(f"SELECT id, linea_id, codigo_proveedor FROM referencia WHERE codigo_proveedor ~ '526' AND linea_id IN ({','.join(map(str, l_ids))})")
    print(df_r)

    if not df_r.empty:
        r_ids = df_r['id'].tolist()
        print("\n--- LINEA_REFERENCIA ---")
        df_lr = get_dataframe(f"SELECT * FROM linea_referencia WHERE linea_id IN ({','.join(map(str, l_ids))}) AND referencia_id IN ({','.join(map(str, r_ids))})")
        print(df_lr)

print("\n--- V_STOCK_RIMEC (Check 2126/526) ---")
df_v = get_dataframe("SELECT det_id, pp_nro, linea_codigo, referencia_codigo, linea_id, referencia_id, grupo_estilo_id, estilo FROM v_stock_rimec WHERE linea_codigo ~ '2126' AND referencia_codigo ~ '526'")
print(df_v)
