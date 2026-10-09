"""GET/PUT /api/me."""

import pytest

from tests.integration.api_helpers import device, error_of

ARMENIAN = "".join(chr(c) for c in (0x531, 0x576, 0x56B))
RUSSIAN = "".join(chr(c) for c in (0x418, 0x432, 0x430, 0x43D))


def test_new_customer_has_no_name(client):
    response = client.get("/api/me", headers=device())
    assert response.status_code == 200
    assert response.json() == {"name": None}


def test_put_sets_and_get_returns_the_name(client):
    response = client.put("/api/me", json={"name": "Ani"}, headers=device())
    assert response.status_code == 200
    assert response.json() == {"name": "Ani"}
    assert client.get("/api/me", headers=device()).json() == {"name": "Ani"}


def test_name_is_trimmed(client):
    response = client.put("/api/me", json={"name": "  Ani \t"}, headers=device())
    assert response.json() == {"name": "Ani"}


@pytest.mark.parametrize("blank", [None, "", "    "])
def test_null_or_blank_clears_the_name(client, blank):
    client.put("/api/me", json={"name": "Ani"}, headers=device())
    response = client.put("/api/me", json={"name": blank}, headers=device())
    assert response.status_code == 200
    assert response.json() == {"name": None}
    assert client.get("/api/me", headers=device()).json() == {"name": None}


def test_armenian_russian_and_emoji_names_round_trip(client):
    for name in (ARMENIAN, RUSSIAN, "Ani " + chr(0x1F600)):
        assert client.put("/api/me", json={"name": name}, headers=device()).json() == {"name": name}
        assert client.get("/api/me", headers=device()).json() == {"name": name}


def test_forty_characters_fit_and_forty_one_do_not(client):
    ok = client.put("/api/me", json={"name": ARMENIAN[0] * 40}, headers=device())
    assert ok.status_code == 200
    response = client.put("/api/me", json={"name": ARMENIAN[0] * 41}, headers=device())
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"][0]["field"] == "name"


@pytest.mark.parametrize("bad", ["A\u0000B", "A\nB", "A" + chr(0x2028) + "B"])
def test_control_characters_are_rejected(client, bad):
    response = client.put("/api/me", json={"name": bad}, headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "body",
    [{}, {"name": 5}, {"name": ["x"]}, {"name": "Ani", "extra": 1}, []],
)
def test_invalid_bodies_are_400(client, body):
    response = client.put("/api/me", json=body, headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_a_failed_update_keeps_the_old_name(client):
    client.put("/api/me", json={"name": "Ani"}, headers=device())
    client.put("/api/me", json={"name": "x" * 41}, headers=device())
    assert client.get("/api/me", headers=device()).json() == {"name": "Ani"}
