"""team-helpers.sh runs its JSON/text work on python3, else node.

The agentic-container image ships node (npx skills needs it) but no python3.
When the helper could not run there, the setup agent improvised the MCP merge
and the AGENTS.md injection itself. These tests pin that the node path exists
and produces byte-identical results to the python path, that a missing runtime
fails loudly, and that the script still parses on macOS's stock bash 3.2.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
HELPER = ROOT / "skills/team/team-setup/scripts/bash/team-helpers.sh"

needs_both = pytest.mark.skipif(
    shutil.which("python3") is None or shutil.which("node") is None,
    reason="needs both python3 and node",
)

TEAM_MCP = {
    "mcpServers": {
        "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
        "gitlab": {"command": "npx", "args": ["-y", "@zereight/mcp-gitlab"],
                   "env": {"TOKEN": "${GITLAB_TOKEN}", "URL": "https://g/api/v4"}},
        "docs": {"type": "http", "url": "https://mcp.example/${TENANT}",
                 "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}},
        "off": {"command": "x", "disabled": True},
        # Cases where the two runtimes used to differ.
        "__proto__": {"command": "proto-mcp"},
        "intl": {"command": "x", "env": {"NAME": "é", "D": "${OPT:-fallback}"}},
    }
}


def run(args, cwd, runtime, env_extra=None):
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "TEAM_HELPERS_RUNTIME": runtime}
    if shutil.which("node"):
        env["PATH"] = str(Path(shutil.which("node")).parent) + ":" + env["PATH"]
    env.update(env_extra or {})
    return subprocess.run(["bash", str(HELPER), *args], cwd=cwd, capture_output=True, text=True, env=env)


def project(tmp_path, name, agent="opencode", extra_files=None):
    team = tmp_path / f"{name}-team"
    team.mkdir()
    (team / ".mcp.json").write_text(json.dumps(TEAM_MCP))
    proj = tmp_path / name
    (proj / ".adlc").mkdir(parents=True)
    (proj / ".adlc" / "init-options.json").write_text(json.dumps({"team_ai_directives": str(team), "agent": agent}))
    for rel, content in (extra_files or {}).items():
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(content)
    return proj


def snapshot(proj):
    return {str(p.relative_to(proj)): p.read_bytes() for p in sorted(proj.rglob("*")) if p.is_file()}


@pytest.mark.requires_bash
@needs_both
@pytest.mark.parametrize("agent,files", [
    ("opencode", {}),
    ("opencode", {".opencode/opencode.json": json.dumps({
        "$schema": "https://opencode.ai/config.json", "plugin": ["p@git+https://x/p.git"],
        "mcp": {"context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
                "gitlab": {"enabled": False}}})}),
    ("claude", {".mcp.json": json.dumps({"mcpServers": {"mine": {"command": "m"}}})}),
])
def test_install_mcp_is_identical_on_python_and_node(tmp_path, agent, files):
    outs, snaps = {}, {}
    for rt in ("python3", "node"):
        proj = project(tmp_path, f"p-{rt}", agent, files)
        r = run(["--install-mcp", str(proj)], proj, rt)
        assert r.returncode == 0, r.stderr
        outs[rt] = r.stdout.replace(str(proj), "<P>")
        snaps[rt] = {k: v for k, v in snapshot(proj).items() if k != ".adlc/init-options.json"}
    assert outs["python3"] == outs["node"]
    assert snaps["python3"] == snaps["node"]


@pytest.mark.requires_bash
@needs_both
def test_agents_inject_update_uninstall_identical_on_python_and_node(tmp_path):
    results = {}
    for rt in ("python3", "node"):
        proj = project(tmp_path, f"a-{rt}", extra_files={"AGENTS.md": "# Project\n\nOwn notes.\n"})
        steps = []
        for args in (["--inject-agents", str(proj)], ["--inject-agents", str(proj)],
                     ["--agents-status", str(proj)], ["--agents-uninstall", str(proj)]):
            r = run(args, proj, rt)
            norm = lambda t: t.replace(str(proj), "<P>").replace(f"a-{rt}", "a-RT")
            steps.append((r.returncode, norm(r.stdout)))
            if args[0] == "--inject-agents":
                steps.append(("file", norm((proj / "AGENTS.md").read_text())))
        steps.append(("final", (proj / "AGENTS.md").read_text()))
        results[rt] = steps
    assert results["python3"] == results["node"]
    assert results["node"][-1] == ("final", "# Project\n\nOwn notes.\n"), "uninstall restores the file"


@pytest.mark.requires_bash
@needs_both
def test_json_output_identical_on_python_and_node(tmp_path):
    proj = project(tmp_path, "j")
    outs = {rt: run(["--json"], proj, rt).stdout for rt in ("python3", "node")}
    assert outs["python3"] == outs["node"]
    assert json.loads(outs["node"])["TEAM_AI_DIRECTIVES"].endswith("j-team")


@pytest.mark.requires_bash
def test_missing_runtime_fails_loudly(tmp_path):
    proj = project(tmp_path, "none")
    r = run(["--install-mcp", str(proj)], proj, "none")
    assert r.returncode != 0
    assert "needs python3 or node" in r.stderr
    assert not (proj / "opencode.json").exists()


@pytest.mark.skipif(not Path("/bin/bash").exists(), reason="no /bin/bash")
def test_parses_on_system_bash():
    # macOS ships bash 3.2 as /bin/bash; heredocs inside $(...) break its parser.
    r = subprocess.run(["/bin/bash", "-n", str(HELPER)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
