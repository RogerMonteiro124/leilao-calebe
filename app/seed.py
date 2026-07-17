from app.database import SessionLocal, init_db
from app.models import Item, Participant


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        participants = [
            ("Joao", "12345", 10000),
            ("Maria", "23456", 15000),
            ("Pedro", "34567", 8000),
            ("Ana", "45678", 12000),
        ]
        for name, code, value in participants:
            if not db.query(Participant).filter_by(access_code=code).first():
                db.add(Participant(name=name, access_code=code, fixed_value=value))

        items = [
            ("Cesta gourmet", "Produtos especiais para compartilhar.", 1),
            ("Kit tecnologia", "Acessorios uteis para o dia a dia.", 2),
            ("Experiencia surpresa", "Um premio ficticio para animar o evento.", 3),
            ("Vale jantar", "Jantar simbolico para duas pessoas.", 4),
            ("Trofeu colecionavel", "Item decorativo exclusivo do leilao.", 5),
        ]
        for name, description, order in items:
            if not db.query(Item).filter_by(name=name).first():
                db.add(Item(name=name, description=description, display_order=order))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
