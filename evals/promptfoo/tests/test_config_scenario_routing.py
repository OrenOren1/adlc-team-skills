"""The live eval config must route every factory-invariant case to a grader.

The dispatcher in ``check_factory_invariants.py`` routes on the criterion
slug that PREFIXES the scenario string (``"<slug>: <prose>"``) — the form
the published goldset already uses. The live config (the file CI runs) must
carry the same form: a scenario that lost its slug falls through to the
dispatcher's default branch, and every such case scores 0 with
"No grader found for scenario" — a silent, whole-suite failure.

The config is a JS object literal, so it is parsed here as text: no JS
runtime is needed and the check runs wherever pytest runs.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
CONFIG = ROOT / "evals/promptfoo/config.js"
GOLDSET = ROOT / "evals/promptfoo/goldset-factory.json"
INVARIANTS_GRADER = "check_factory_invariants.py"

sys.path.insert(0, str(Path(__file__).parent.parent / "graders"))

from check_factory_invariants import get_assert as get_assert_invariants


# ── the live config, parsed as text ─────────────────────────────────────────

SCENARIO_RE = re.compile(
    r'''["']?scenario["']?\s*:\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')'''
)
GRADER_RE = re.compile(
    r'''["']?value["']?\s*:\s*(?:"file://([^"]+)"|'file://([^']+)')'''
)


def config_cases():
    """Every case of the live config as (scenario, grader path) pairs."""
    text = CONFIG.read_text(encoding="utf-8")
    body = text[text.index("tests: ["):text.index("outputPath")]
    cases = []
    for block in re.split(r"^    \{$", body, flags=re.M)[1:]:
        scenario = SCENARIO_RE.search(block)
        grader = GRADER_RE.search(block)
        assert scenario, f"a config case declares no scenario:\n{block}"
        assert grader, f"a config case declares no grader:\n{block}"
        cases.append(
            (
                scenario.group(1) if scenario.group(1) is not None else scenario.group(2),
                grader.group(1) if grader.group(1) is not None else grader.group(2),
            )
        )
    return cases


def factory_invariant_scenarios():
    """The scenarios of the cases the factory-invariants dispatcher serves."""
    return [
        scenario
        for scenario, grader in config_cases()
        if grader.endswith(INVARIANTS_GRADER)
    ]


# ── the live config reaches a real grader ───────────────────────────────────

def test_the_live_config_carries_the_factory_invariant_cases():
    scenarios = factory_invariant_scenarios()
    assert len(scenarios) >= 12, (
        f"expected the factory-invariant cases in the live config, found {len(scenarios)}"
    )


def test_every_factory_invariant_scenario_resolves_to_a_grader():
    for scenario in factory_invariant_scenarios():
        result = get_assert_invariants("", {"vars": {"scenario": scenario}})
        assert "No grader found" not in result["reason"], (
            f"scenario {scenario!r} falls through to the dispatcher's default branch"
        )


def test_the_factory_invariant_scenarios_carry_their_slug():
    """A routed scenario is "<slug>: <prose>" — the slug prefixes the prose."""
    for scenario in factory_invariant_scenarios():
        slug, separator, prose = scenario.partition(":")
        assert separator, f"scenario {scenario!r} carries no slug"
        assert " " not in slug, f"scenario {scenario!r} has a malformed slug {slug!r}"
        assert prose.strip(), f"scenario {scenario!r} carries no prose"


def test_the_factory_invariant_scenarios_are_the_published_goldset_ones():
    """The live config and the published goldset describe the same cases."""
    goldset = json.loads(GOLDSET.read_text(encoding="utf-8"))
    published = {case["scenario"] for case in goldset["cases"]}
    for scenario in factory_invariant_scenarios():
        assert scenario in published, (
            f"scenario {scenario!r} is not the published goldset form"
        )


# ── the dispatcher routes on the slug prefix, never on a substring ──────────

def test_a_slug_prefixed_scenario_still_routes():
    result = get_assert_invariants(
        "", {"vars": {"scenario": "read-only: factory-tickets must be read-only"}}
    )
    assert "No grader found" not in result["reason"], (
        "a slug-prefixed scenario must reach its grader"
    )


def test_a_slug_mentioned_in_prose_does_not_route():
    """The slug is a prefix, not a substring — prose cannot mis-route."""
    result = get_assert_invariants(
        "", {"vars": {"scenario": "a prose sentence mentioning label-mapping in passing"}}
    )
    assert "No grader found" in result["reason"], (
        "the dispatcher must route on the slug prefix, not on a substring"
    )
