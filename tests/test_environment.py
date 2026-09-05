"""Real Docker acceptance seam. Only this project's disposable database is reset."""
import json
import subprocess

from test_seed import REPO_ROOT as ROOT


def docker(*args: str) -> str:
    return subprocess.run(["docker", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True, timeout=180).stdout.strip()


def sql(statement: str) -> str:
    return docker("compose", "exec", "-T", "postgres", "psql", "-U", "lab",
                  "-d", "lab", "-At", "-c", statement)


def test_postgres_localhost_only_and_scratch_reset() -> None:
    config = json.loads(docker("compose", "config", "--format", "json"))
    assert set(config["services"]) == {"postgres"}
    service = config["services"]["postgres"]
    assert service["image"].startswith("postgres:15")
    assert service.get("network_mode") != "host"
    assert len(service["ports"]) == 1
    assert service["ports"][0]["host_ip"] == "127.0.0.1"
    assert service["ports"][0]["target"] == 5432
    assert not any(v.get("external") for v in config["volumes"].values())
    volume_name = config["volumes"]["pgdata"]["name"]
    try:
        docker("compose", "up", "-d", "--wait", "--wait-timeout", "90")
        container_id = docker("compose", "ps", "-q", "postgres")
        info = json.loads(docker("inspect", container_id))[0]
        bindings = info["NetworkSettings"]["Ports"]["5432/tcp"]
        assert bindings == [{"HostIp": "127.0.0.1", "HostPort": "55432"}]
        assert sql("SHOW server_version").startswith("15.")
        sql("CREATE TABLE reset_probe (value text); INSERT INTO reset_probe VALUES ('persisted');")
        assert sql("SELECT value FROM reset_probe") == "persisted"
        docker("compose", "down", "-v")
        assert volume_name not in docker("volume", "ls", "--format", "{{.Name}}").splitlines()
        assert docker("compose", "ps", "-aq") == ""
        docker("compose", "up", "-d", "--wait", "--wait-timeout", "90")
        assert sql("SELECT to_regclass('public.reset_probe') IS NULL") == "t"
        assert sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'") == "0"
    finally:
        docker("compose", "down", "-v")
