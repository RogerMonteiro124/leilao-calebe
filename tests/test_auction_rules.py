from sqlalchemy import select

from app.database import SessionLocal
from app.models import Bid, Item, Participant, ParticipantStatus, Round, RoundStatus
from tests.conftest import admin_login, login


def start_first(client):
    admin_login(client)
    return client.post("/admin/round/start/1", follow_redirects=False)


def test_participacao_em_rodada_aberta(client):
    start_first(client)
    login(client, "12345")
    res = client.post("/api/bid")
    assert res.status_code == 200
    assert res.json()["bid"]["value"] == 10000


def test_tentativa_de_participar_duas_vezes(client):
    start_first(client)
    login(client, "12345")
    assert client.post("/api/bid").status_code == 200
    assert client.post("/api/bid").status_code == 409


def test_participante_bloqueado(client):
    db = SessionLocal()
    p = db.scalar(select(Participant).where(Participant.access_code == "12345"))
    p.status = ParticipantStatus.BLOCKED
    db.commit()
    db.close()
    start_first(client)
    login(client, "12345")
    assert client.post("/api/bid").status_code == 403


def test_participante_que_ja_ganhou(client):
    db = SessionLocal()
    p = db.scalar(select(Participant).where(Participant.access_code == "12345"))
    p.status = ParticipantStatus.WINNER
    db.commit()
    db.close()
    start_first(client)
    login(client, "12345")
    assert client.post("/api/bid").status_code == 403


def test_encerramento_com_maior_valor(client):
    start_first(client)
    login(client, "12345")
    client.post("/api/bid")
    client.post("/logout")
    login(client, "23456")
    client.post("/api/bid")
    admin_login(client)
    assert client.post("/admin/round/close", follow_redirects=False).status_code == 303
    db = SessionLocal()
    item = db.get(Item, 1)
    winner = db.get(Participant, item.winner_id)
    assert winner.name == "Maria"
    assert item.winning_value == 15000
    db.close()


def test_desempate_pelo_horario(client):
    db = SessionLocal()
    db.scalar(select(Participant).where(Participant.access_code == "12345")).fixed_value = 10000
    db.scalar(select(Participant).where(Participant.access_code == "45678")).fixed_value = 10000
    db.commit()
    db.close()
    start_first(client)
    login(client, "45678")
    client.post("/api/bid")
    client.post("/logout")
    login(client, "12345")
    client.post("/api/bid")
    admin_login(client)
    client.post("/admin/round/close", follow_redirects=False)
    db = SessionLocal()
    item = db.get(Item, 1)
    assert db.get(Participant, item.winner_id).name == "Ana"
    db.close()


def test_rodada_sem_participantes(client):
    start_first(client)
    admin_login(client)
    client.post("/admin/round/close", follow_redirects=False)
    db = SessionLocal()
    item = db.get(Item, 1)
    assert item.winner_id is None
    assert item.status == "closed"
    db.close()


def test_impedir_duas_rodadas_ativas(client):
    assert start_first(client).status_code == 303
    res = client.post("/admin/round/start/2", follow_redirects=False)
    assert res.status_code == 409


def test_cancelamento_de_participacao(client):
    start_first(client)
    login(client, "12345")
    client.post("/api/bid")
    assert client.delete("/api/bid").status_code == 200
    assert client.post("/api/bid").status_code == 200
    assert client.delete("/api/bid").status_code == 200
    db = SessionLocal()
    bids = db.scalars(select(Bid).order_by(Bid.id)).all()
    assert [bid.active for bid in bids] == [False, False]
    assert all(bid.canceled_at is not None for bid in bids)
    db.close()


def test_persistencia_no_sqlite(client):
    start_first(client)
    db = SessionLocal()
    assert db.scalar(select(Round).where(Round.status == RoundStatus.ACTIVE)) is not None
    db.close()


def test_valor_ficticio_decimal_com_virgula(client):
    admin_login(client)
    res = client.post(
        "/admin/participants",
        data={
            "name": "Decimal",
            "access_code": "56789",
            "fixed_value": "12345,67",
            "status_value": "available",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
    start_first(client)
    client.post("/logout")
    login(client, "56789")
    bid_res = client.post("/api/bid")
    assert bid_res.status_code == 200
    assert bid_res.json()["bid"]["value"] == 12345.67
    assert bid_res.json()["bid"]["value_label"] == "T$ 12.345,67"
