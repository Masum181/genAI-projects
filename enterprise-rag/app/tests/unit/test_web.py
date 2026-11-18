"""Browser template and endpoint wiring tests."""

from app.main import app
from app.web import templates


def test_login_template_renders_outside_project_working_directory(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)

    page = templates.get_template("login.html").render(error=None, principal=None)

    assert "<title>Sign in - Enterprise RAG</title>" in page
    assert 'action="/login"' in page


def test_api_routes_are_mounted() -> None:
    mounted_routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }

    assert ("/api/v1/auth/login", "POST") in mounted_routes
    assert ("/api/v1/documents/upload", "POST") in mounted_routes
    assert ("/api/v1/chat", "POST") in mounted_routes
    assert ("/ui/", "GET") in mounted_routes
    assert ("/ui/documents", "GET") in mounted_routes
