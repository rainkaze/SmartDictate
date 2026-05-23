from backend.app.core.middleware import RequestContextMiddleware
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_request_context_middleware_adds_trace_headers() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/ping", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0
