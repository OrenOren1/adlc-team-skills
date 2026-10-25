"""team-setup Post-Setup step 5: `team-helpers.sh --install-mcp`.

Team directives declare MCP servers in the `.mcp.json` shape
(`{"command": "npx", "args": [...], "env": {"K": "${VAR}"}}`). OpenCode rejects
that shape under `mcp` in opencode.json and refuses to start, which failed
every headless review/mission pod whose setup copied it verbatim. The helper
must translate it for OpenCode (`type`/`command[]`/`environment`/`enabled`,
`{env:VAR}`), repair entries an earlier verbatim merge broke, keep valid entries
and unrelated keys, and pass `.mcp.json` through verbatim for other agents.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
HELPER = ROOT / "skills/team/team-setup/scripts/bash/team-helpers.sh"

TEAM_MCP = {
    "mcpServers": {
        "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
        "gitlab": {
            "command": "npx",
            "args": ["-y", "@zereight/mcp-gitlab"],
            "env": {"GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_TOKEN}", "GITLAB_API_URL": "https://g/api/v4"},
        },
        "docs": {"type": "http", "url": "https://mcp.example/${TENANT}", "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}},
    },
    "tools": {"github": {"type": "github"}},
}


def make_project(tmp_path, agent, team_mcp=TEAM_MCP):
    team = tmp_path / "team"
    team.mkdir()
    if team_mcp is not None:
        (team / ".mcp.json").write_text(json.dumps(team_mcp))
    project = tmp_path / "project"
    (project / ".adlc").mkdir(parents=True)
    opts = {"team_ai_directives": str(team)}
    if agent:
        opts["agent"] = agent
    (project / ".adlc" / "init-options.json").write_text(json.dumps(opts))
    return project


RUNTIMES = [r for r in ("python3", "node")]


@pytest.fixture(autouse=True, params=RUNTIMES)
def runtime(request, monkeypatch):
    # Every case runs on both JSON runtimes: python3 where it exists, node where
    # it does not (the agentic-container image ships node but no python3).
    if shutil.which(request.param) is None:
        pytest.skip(f"{request.param} not installed")
    monkeypatch.setenv("TEAM_HELPERS_RUNTIME", request.param)
    return request.param


def install(project, *extra, env=None):
    if env is not None:
        env = {**env, "TEAM_HELPERS_RUNTIME": os.environ["TEAM_HELPERS_RUNTIME"]}
    result = subprocess.run(
        ["bash", str(HELPER), "--install-mcp", str(project), *extra],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.requires_bash
def test_opencode_entries_are_translated(tmp_path):
    project = make_project(tmp_path, "opencode")
    out = install(project)
    cfg = json.loads((project / "opencode.json").read_text())
    assert cfg["$schema"] == "https://opencode.ai/config.json"
    assert cfg["mcp"]["context7"] == {
        "type": "local", "command": ["npx", "-y", "@upstash/context7-mcp"], "enabled": True,
    }
    gl = cfg["mcp"]["gitlab"]
    assert gl["type"] == "local" and gl["enabled"] is True
    assert gl["command"] == ["npx", "-y", "@zereight/mcp-gitlab"]
    # OpenCode substitutes {env:VAR}; a literal ${VAR} would reach the server as-is.
    assert gl["environment"]["GITLAB_PERSONAL_ACCESS_TOKEN"] == "{env:GITLAB_TOKEN}"
    assert "args" not in gl and "env" not in gl
    docs = cfg["mcp"]["docs"]
    assert docs == {
        "type": "remote", "url": "https://mcp.example/{env:TENANT}", "enabled": True,
        "headers": {"Authorization": "Bearer {env:DOCS_TOKEN}"},
    }
    assert "merged context7 -> opencode.json" in out


@pytest.mark.requires_bash
def test_opencode_repairs_verbatim_entries_and_keeps_other_keys(tmp_path):
    # The exact file a verbatim merge left in a review pod (.opencode/opencode.json).
    project = make_project(tmp_path, "opencode")
    target = project / ".opencode" / "opencode.json"
    target.parent.mkdir()
    target.write_text(json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"],
        "mcp": {
            "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
            "mine": {"type": "local", "command": ["my-mcp"], "enabled": False},
        },
    }))
    out = install(project)
    cfg = json.loads(target.read_text())
    assert not (project / "opencode.json").exists(), "writes the config file that exists"
    assert cfg["plugin"] == ["superpowers@git+https://github.com/obra/superpowers.git"]
    assert cfg["mcp"]["context7"]["type"] == "local"
    assert cfg["mcp"]["mine"] == {"type": "local", "command": ["my-mcp"], "enabled": False}
    assert "repaired context7" in out


@pytest.mark.requires_bash
def test_opencode_rerun_is_idempotent(tmp_path):
    project = make_project(tmp_path, "opencode")
    install(project)
    first = (project / "opencode.json").read_text()
    out = install(project)
    assert (project / "opencode.json").read_text() == first
    assert "kept context7" in out and "MCP: merged" not in out


@pytest.mark.requires_bash
def test_opencode_enabled_override_is_kept(tmp_path):
    # {"enabled": false} alone is OpenCode's switch-off for a server defined in the
    # global config. Replacing it would turn the server back on.
    project = make_project(tmp_path, "opencode")
    target = project / "opencode.json"
    target.write_text(json.dumps({"mcp": {"context7": {"enabled": False}}}))
    out = install(project)
    cfg = json.loads(target.read_text())
    assert cfg["mcp"]["context7"] == {"enabled": False}
    assert "kept context7" in out and "repaired context7" not in out
    assert cfg["mcp"]["gitlab"]["type"] == "local", "other servers still merged"


@pytest.mark.requires_bash
def test_opt_out_marker_installs_nothing(tmp_path):
    # `"team_ai_directives": null` is the opt-out marker. It must not fall back to
    # TEAM_AI_DIRECTIVES or ./team-ai-directives and install servers anyway.
    project = make_project(tmp_path, "opencode")
    fallback = project / "team-ai-directives"
    fallback.mkdir()
    (fallback / ".mcp.json").write_text(json.dumps(TEAM_MCP))
    (project / ".adlc" / "init-options.json").write_text(
        json.dumps({"team_ai_directives": None, "agent": "opencode"}))
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "TEAM_AI_DIRECTIVES": str(fallback)}
    out = install(project, env=env)
    assert "opted out" in out
    assert not (project / "opencode.json").exists()


@pytest.mark.requires_bash
def test_other_agents_get_mcp_json_verbatim(tmp_path):
    project = make_project(tmp_path, "claude")
    install(project)
    cfg = json.loads((project / ".mcp.json").read_text())
    assert cfg["mcpServers"] == TEAM_MCP["mcpServers"]
    assert not (project / "opencode.json").exists()


@pytest.mark.requires_bash
def test_agent_flag_overrides_init_options(tmp_path):
    project = make_project(tmp_path, "claude")
    install(project, "--agent", "opencode")
    assert (project / "opencode.json").exists()
    assert not (project / ".mcp.json").exists()


@pytest.mark.requires_bash
def test_missing_team_mcp_is_a_noop(tmp_path):
    project = make_project(tmp_path, "opencode", team_mcp=None)
    out = install(project)
    assert "nothing to install" in out
    assert not (project / "opencode.json").exists()


@pytest.mark.requires_bash
def test_reports_unset_env_vars(tmp_path):
    project = make_project(tmp_path, "opencode")
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "GITLAB_TOKEN": "set"}
    out = install(project, env=env)
    assert "set these env vars for the merged servers: DOCS_TOKEN, TENANT" in out


@pytest.mark.requires_bash
@pytest.mark.skipif(shutil.which("opencode") is None, reason="opencode CLI not installed")
def test_opencode_accepts_the_written_config(tmp_path):
    # The real acceptance check: opencode's own config validation.
    project = make_project(tmp_path, "opencode")
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    install(project)
    result = subprocess.run(
        ["opencode", "debug", "config"], cwd=project, capture_output=True, text=True, timeout=120,
    )
    assert "Configuration is invalid" not in result.stderr, result.stderr
    assert result.returncode == 0
