import pandas as pd
from core.queries import get_dataframe

df = get_dataframe("SELECT pg_get_viewdef('v_stock_web', true)")
print(df.iloc[0, 0])
