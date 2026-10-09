import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import AppError, ErrorCode, register_exception_handlers


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qty: int = Field(ge=1, le=20)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom-app")
    def boom_app():
        raise AppError(
            ErrorCode.ACTIVE_ORDER_EXISTS,
            409,
            "Active order exists",
            {"order_id": 42, "code": "A-007", "status": "READY"},
        )

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail="I am a teapot")

    @app.get("/gateway")
    def gateway():
        raise HTTPException(status_code=502, detail="bad gateway")

    @app.get("/boom-unexpected")
    def boom_unexpected():
        raise RuntimeError("secret internals")

    @app.post("/items")
    def items(body: Body):
        return body

    return TestClient(app, raise_server_exceptions=False)


def test_app_error_envelope(client):
    r = client.get("/boom-app")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "ACTIVE_ORDER_EXISTS",
            "message": "Active order exists",
            "details": {"order_id": 42, "code": "A-007", "status": "READY"},
        }
    }


def test_details_is_always_an_object(client):
    r = client.get("/nope")
    assert r.json()["error"]["details"] == {}


def test_validation_error_is_400_with_fields(client):
    r = client.post("/items", json={"qty": 99})
    assert r.status_code == 400
    error = r.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"] == {"fields": [{"field": "qty", "issue": "less_than_equal"}]}


def test_extra_field_is_rejected(client):
    r = client.post("/items", json={"qty": 1, "extra": 1})
    assert r.status_code == 400
    assert r.json()["error"]["details"]["fields"] == [
        {"field": "extra", "issue": "extra_forbidden"}
    ]


def test_malformed_json_is_validation_error(client):
    r = client.post("/items", content=b"{oops", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_route_is_404_envelope(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_is_405_envelope(client):
    r = client.delete("/boom-app")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_error_is_500_and_does_not_leak(client):
    r = client.get("/boom-unexpected")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in r.text


def test_other_framework_4xx_becomes_http_error_keeping_the_status(client):
    r = client.get("/teapot")
    assert r.status_code == 418
    assert r.json() == {"error": {"code": "HTTP_ERROR", "message": "Request failed", "details": {}}}
    assert "teapot" not in r.text


def test_framework_5xx_becomes_internal_error(client):
    r = client.get("/gateway")
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
