import os
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent

def _db_url() -> str:
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        import tomllib
        with p.open("rb") as f:
            pg = tomllib.load(f).get("postgres")
        if isinstance(pg, dict):
            user = pg.get("user") or pg.get("username")
            pwd = pg.get("password")
            host = pg.get("host", "localhost")
            port = pg.get("port", 5432)
            db = pg.get("database") or pg.get("dbname")
            if user and pwd and db:
                return f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/{db}"
    raise SystemExit(f"Falta secrets.toml at {p}")

def main():
    db_url = _db_url()
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Checking tables:")
        for t in ['maestro_rol_acceso', 'modulo_sistema', 'vendedor_v2', 'vendedor_v2_deprecated']:
            res = conn.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{t}')")).scalar()
            print(f"Table {t} exists: {res}")
            
        print("\nChecking columns in usuario_v2:")
        res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'usuario_v2'")).fetchall()
        for r in res:
            print(f"  {r[0]}: {r[1]}")
            
        print("\nChecking constraints on pedido_venta_rimec:")
        res = conn.execute(text("SELECT constraint_name, constraint_type FROM information_schema.table_constraints WHERE table_name = 'pedido_venta_rimec'")).fetchall()
        for r in res:
            print(f"  {r[0]}: {r[1]}")

if __name__ == "__main__":
    main()
