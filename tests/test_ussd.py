
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_server():
    response = client.get("/")
    assert response.status_code == 200


def test_balance():
    response = client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": "test_balance",
        "input": "*100#"
    })

    assert response.status_code == 200
    assert response.json()["text"] == "Ваш баланс: 1000 сом"
    assert response.json()["end"] is True


def test_packages():
    response = client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": "test_packages",
        "input": "*102#"
    })

    assert response.status_code == 200
    assert "Интернет" in response.json()["text"]
    assert "Минуты" in response.json()["text"]


def test_unknown_user():
    response = client.post("/ussd", json={
        "msisdn": "996999999999",
        "session_id": "test_unknown",
        "input": "*100#"
    })

    assert response.json()["end"] is True
    assert response.json()["text"] == "Абонент не найден"


def test_unknown_command():
    response = client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": "test_command",
        "input": "*999#"
    })

    assert response.json()["end"] is True
    assert response.json()["text"] == "Неизвестная команда"


def test_menu_opens():
    response = client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": "menu_test",
        "input": "*111#"
    })

    assert response.status_code == 200
    assert response.json()["end"] is False
    assert "Интернет" in response.json()["text"]


def test_menu_back():
    session = "back_test"

    client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": session,
        "input": "*111#"
    })

    response = client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": session,
        "input": "0"
    })

    assert response.status_code == 200
    assert response.json()["end"] is False
    assert "меню" in response.json()["text"].lower()


def test_invalid_menu_option():
    session = "invalid_test"

    client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": session,
        "input": "*111#"
    })

    response = client.post("/ussd", json={
        "msisdn": "996770123456",
        "session_id": session,
        "input": "99"
    })

    assert response.status_code == 200
    assert "неверн" in response.json()["text"].lower()
