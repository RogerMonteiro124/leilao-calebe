import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.NamedTemporaryFile(delete=False).name}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "password"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Item, Participant


@pytest.fixture(autouse=True)
def reset_db():
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        Base.metadata.drop_all(bind=conn)
        conn.execute(text("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(bind=conn)
    db = SessionLocal()
    db.add_all(
        [
            Participant(name="Joao", access_code="12345", fixed_value=10000),
            Participant(name="Maria", access_code="23456", fixed_value=15000),
            Participant(name="Pedro", access_code="34567", fixed_value=8000),
            Participant(name="Ana", access_code="45678", fixed_value=12000),
            Item(name="Item A", display_order=1),
            Item(name="Item B", display_order=2),
        ]
    )
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, code="12345"):
    return client.post("/login", data={"code": code}, follow_redirects=False)


def admin_login(client):
    return client.post("/admin/login", data={"username": "admin", "password": "password"}, follow_redirects=False)
