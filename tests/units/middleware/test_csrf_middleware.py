import pytest
from starlette.testclient import TestClient
from starlette.middleware import Middleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from app.middleware.csrf_middleware import CSRFMiddleware

async def homepage(request):
    return JSONResponse({"message": "Success"})

async def protected_post(request):
    return JSONResponse({"message": "Protected Resource Accessed"})

def test_csrf_middleware_protection():
    """
    Test that CSRF middleware blocks requests without valid token.
    """
    middleware = [
        Middleware(CSRFMiddleware, exempt_paths=["/exempt"])
    ]
    routes = [
        Route("/", homepage, methods=["GET"]),
        Route("/protected", protected_post, methods=["POST"]),
        Route("/exempt", protected_post, methods=["POST"])
    ]
    app = Starlette(routes=routes, middleware=middleware)
    client = TestClient(app)

    # 1. GET requests should be allowed (safe method)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Success"}

    # 2. POST without CSRF token and cookie should be forbidden
    response = client.post("/protected")
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token mismatch or missing"}

    # 3. POST with cookie but missing header should be forbidden
    client.cookies.set("csrf_token", "valid_token")
    response = client.post("/protected")
    assert response.status_code == 403

    # 4. POST with header but missing cookie should be forbidden
    client.cookies.clear()
    response = client.post("/protected", headers={"X-CSRF-Token": "valid_token"})
    assert response.status_code == 403

    # 5. POST with mismatching tokens should be forbidden
    client.cookies.set("csrf_token", "token_a")
    response = client.post("/protected", headers={"X-CSRF-Token": "token_b"})
    assert response.status_code == 403

    # 6. POST with matching tokens should be allowed
    client.cookies.set("csrf_token", "valid_token")
    response = client.post("/protected", headers={"X-CSRF-Token": "valid_token"})
    assert response.status_code == 200
    assert response.json() == {"message": "Protected Resource Accessed"}

    # 7. POST to exempt path should be allowed without tokens
    client.cookies.clear()
    response = client.post("/exempt")
    assert response.status_code == 200
    assert response.json() == {"message": "Protected Resource Accessed"}
