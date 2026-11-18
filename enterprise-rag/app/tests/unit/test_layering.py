"""Architectural tests for API-to-service-to-repository boundaries."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).parents[2]


def test_api_handlers_delegate_database_work_to_services() -> None:
    forbidden_calls = {
        "add",
        "add_all",
        "commit",
        "delete",
        "execute",
        "flush",
        "get",
        "refresh",
        "scalar",
        "scalars",
    }
    for path in (APP_ROOT / "api").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if (
                node.func.attr in forbidden_calls
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"db", "session"}
            ):
                raise AssertionError(
                    f"{path.relative_to(APP_ROOT)} accesses the database directly"
                )


def test_services_do_not_depend_on_api_modules_or_execute_queries() -> None:
    forbidden_calls = {
        "add",
        "add_all",
        "commit",
        "delete",
        "execute",
        "flush",
        "get",
        "refresh",
        "scalar",
        "scalars",
    }
    for path in (APP_ROOT / "services").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "app.api"
            ):
                raise AssertionError(
                    f"{path.relative_to(APP_ROOT)} imports the API layer"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_calls
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"db", "session"}
            ):
                raise AssertionError(
                    f"{path.relative_to(APP_ROOT)} executes database operations"
                )
