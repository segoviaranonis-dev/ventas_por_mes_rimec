import os
import sys
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent

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
    raise SystemExit("Falta secrets.toml")

def main():
    migration_file = ROOT / "migrations" / "066_rbac_unificacion_usuarios.sql"
    if not migration_file.is_file():
        print(f"Error: No se encontró el archivo de migración en {migration_file}")
        sys.exit(1)

    print(f"Leyendo migración desde: {migration_file.name}")
    sql_content = migration_file.read_text(encoding="utf-8")

    # Connect to the DB
    db_url = _db_url()
    print("Conectando a la base de datos...")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("Ejecutando migración 066...")
        # Since SQL contains multiple statements, we run it as text.
        # SQLAlchemy connection.execute doesn't support running multiple statements block-by-block easily 
        # unless wrapped in a single text block, which connection.execute(text(...)) can do.
        # But Postgres drivers support multi-statement execution in a single query.
        # Let's execute the raw connection cursor for security.
        raw_conn = conn.connection
        with raw_conn.cursor() as cur:
            cur.execute(sql_content)
        raw_conn.commit()
        print("¡Migración 066 ejecutada exitosamente!")

if __name__ == "__main__":
    main()
