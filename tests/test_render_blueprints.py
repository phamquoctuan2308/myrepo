from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _blueprint(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def _group_environment(blueprint: dict) -> dict[str, str]:
    return {
        item["key"]: item.get("value", "")
        for item in blueprint["envVarGroups"][0]["envVars"]
    }


def test_default_render_blueprint_uses_only_free_demo_resources():
    blueprint = _blueprint("render.yaml")
    services = blueprint["services"]
    environment = _group_environment(blueprint)

    assert len(blueprint["databases"]) == 1
    assert blueprint["databases"][0]["plan"] == "free"
    assert len(services) == 1
    assert services[0]["type"] == "web"
    assert services[0]["plan"] == "free"
    assert "preDeployCommand" not in services[0]
    assert "maxShutdownDelaySeconds" not in services[0]
    assert "dockerCommand" not in services[0]
    start_script = (ROOT / "scripts" / "start_web.sh").read_text(encoding="utf-8")
    assert "alembic upgrade head" in start_script
    assert 'exec uvicorn src.main:app' in start_script
    assert '--port "${PORT:-8000}"' in start_script
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["/bin/sh", "scripts/start_web.sh"]' in dockerfile
    assert "WORKSPACE_AGENT_RUNTIME_WORKSPACE_ID" in dockerfile
    assert environment["WORKSPACE_AGENT_RUNTIME_MODE"] == "embedded"
    assert environment["ALLOW_EMBEDDED_WORKSPACE_AGENTS_IN_PRODUCTION"] == "true"
    assert environment["WORKSPACE_AGENT_MAX_CONCURRENCY"] == "1"
    assert environment["DEMO_LOGIN_ENABLED"] == "true"
    assert environment["ALLOW_DEMO_LOGIN_IN_PRODUCTION"] == "true"


def test_paid_render_blueprint_preserves_isolated_agent_topology():
    blueprint = _blueprint("render.production.yaml")
    services = blueprint["services"]
    environment = _group_environment(blueprint)

    assert blueprint["databases"][0]["plan"] != "free"
    assert [service["type"] for service in services] == ["web", "pserv", "pserv"]
    assert "dockerCommand" not in services[0]
    assert environment["WORKSPACE_AGENT_RUNTIME_MODE"] == "remote"
    assert environment["DEMO_LOGIN_ENABLED"] == "false"
    assert environment["ALLOW_DEMO_LOGIN_IN_PRODUCTION"] == "false"
