import argparse

from app.database import Base, engine, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria o banco SQLite do leilao.")
    parser.add_argument("--reset", action="store_true", help="Apaga as tabelas existentes antes de recriar.")
    args = parser.parse_args()
    if args.reset:
        if engine.url.drivername.startswith("sqlite"):
            from sqlalchemy import text

            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                Base.metadata.drop_all(bind=conn)
                conn.execute(text("PRAGMA foreign_keys=ON"))
        else:
            Base.metadata.drop_all(bind=engine)
    init_db()


if __name__ == "__main__":
    main()
