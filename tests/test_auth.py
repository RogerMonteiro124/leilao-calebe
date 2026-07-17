from tests.conftest import login


def test_login_por_codigo_valido(client):
    res = login(client, "12345")
    assert res.status_code == 303
    assert res.headers["location"] == "/participant"


def test_codigo_invalido(client):
    res = login(client, "99999")
    assert res.status_code == 400
    assert "Codigo invalido" in res.text
