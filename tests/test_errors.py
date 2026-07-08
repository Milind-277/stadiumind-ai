import json

import pytest
from flask import Flask

from app.middleware.error_handler import register_error_handlers


@pytest.fixture
def error_app():
    app = Flask(__name__)
    register_error_handlers(app)

    @app.route("/api/400")
    def raise_400():
        from werkzeug.exceptions import BadRequest

        raise BadRequest("Bad Request")

    @app.route("/api/403")
    def raise_403():
        from werkzeug.exceptions import Forbidden

        raise Forbidden("Forbidden")

    @app.route("/api/404")
    def raise_api_404():
        from werkzeug.exceptions import NotFound

        raise NotFound("Not Found")

    @app.route("/page/404")
    def raise_page_404():
        from werkzeug.exceptions import NotFound

        raise NotFound("Not Found")

    @app.route("/api/405", methods=["POST"])
    def raise_405():
        return "OK"

    @app.route("/api/500")
    def raise_500():
        from werkzeug.exceptions import InternalServerError

        raise InternalServerError("Internal")

    @app.route("/api/exception")
    def raise_exception():
        raise ValueError("Generic Error")

    return app


def test_400_error(error_app):
    client = error_app.test_client()
    response = client.get("/api/400")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["errors"][0]["code"] == "BAD_REQUEST"


def test_403_error(error_app):
    client = error_app.test_client()
    response = client.get("/api/403")
    assert response.status_code == 403
    data = json.loads(response.data)
    assert data["errors"][0]["code"] == "FORBIDDEN"


def test_api_404_error(error_app):
    client = error_app.test_client()
    response = client.get("/api/404")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data["errors"][0]["code"] == "NOT_FOUND"


def test_api_405_error(error_app):
    client = error_app.test_client()
    response = client.get("/api/405")  # GET instead of POST
    assert response.status_code == 405
    data = json.loads(response.data)
    assert data["errors"][0]["code"] == "METHOD_NOT_ALLOWED"


def test_api_500_error(error_app):
    client = error_app.test_client()
    response = client.get("/api/500")
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["errors"][0]["code"] == "INTERNAL_ERROR"


def test_api_generic_exception(error_app):
    client = error_app.test_client()
    response = client.get("/api/exception")
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["errors"][0]["code"] == "INTERNAL_ERROR"
