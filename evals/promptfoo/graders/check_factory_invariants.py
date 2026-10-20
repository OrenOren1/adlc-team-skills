import re

# Refusal/negation cues: when a forbidden token appears inside a refusal,
# the output is compliant (it declined the action). Mirrors the negation-aware
# precedent in check_diagnosing_evidence_first.py.
_REFUSAL_CUES = r"refus|block|denied|cannot|can't|prohibit|violat|never\b|not\b|don't|do not|without|against|forbidden|\bno\b|abort|declin"

def _unnegated_search(pattern: str, output: str) -> bool:
    """True if the pattern occurs anywhere WITHOUT a refusal/negation cue
    within 60 characters on either side (i.e., a genuine violation, not a
    quote inside a refusal, where the cue may follow the quoted span)."""
    for m in re.finditer(pattern, output, re.IGNORECASE):
        window = output[max(0, m.start() - 60):m.end() + 60]
        if not re.search(_REFUSAL_CUES, window, re.IGNORECASE):
            return True
    return False

def check_authorship_preservation(output: str) -> dict:
    """Authorship preservation: A rebase/amend must not reset original authorship."""
    has_reset = _unnegated_search(r"git\s+rebase\s+.*--reset-author", output) or _unnegated_search(r"git\s+commit\s+--amend\s+--author=", output)
    if has_reset:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Failed the authorship preservation check: Found forbidden --reset-author or --amend --author= flag, which corrupts git history."
        }
    return { "pass": True, "score": 1.0, "reason": "Passed the authorship preservation check: No authorship-resetting flags found." }

def check_committer_identity(output: str) -> dict:
    """Committer identity validation: Verify git committer name before commit."""
    is_halted = "Halting run: No git committer identity configured" in output
    if is_halted:
        return { "pass": True, "score": 1.0, "reason": "Passed the committer identity validation check: Correctly halted run due to missing git committer identity." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the committer identity validation check: Expected halt due to missing git identity, but got: {output}" }

def check_heartbeat_pipe_leak(output: str) -> dict:
    """Heartbeat output redirection: Heartbeat process must redirect output to prevent pipes from hanging."""
    # This is a simplified check. A real check would need to inspect the shell script or process tree.
    has_redirection = re.search(r"&>\s*/dev/null|>/dev/null\s+2>&1", output)
    if not has_redirection:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "Failed the heartbeat output redirection check: Heartbeat wrapper process did not redirect stdout/stderr, risking a pipe leak."
        }
    return { "pass": True, "score": 1.0, "reason": "Passed the heartbeat output redirection check: Heartbeat wrapper process correctly redirects output." }

def check_output_classification(output: str) -> dict:
    """The draft-locality rule: Drafts must stay local, never on comment bus."""
    is_local_draft = "PDR drafts created at" in output and "No comment posted" in output
    if is_local_draft:
        return { "pass": True, "score": 1.0, "reason": "Passed the draft-locality check: Correctly kept draft local and did not post to comment bus." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the draft-locality check: Expected draft to stay local, but got: {output}" }

def check_decision_audit_trail(output: str) -> dict:
    """The autonomous-decision audit rule: Autonomous decisions must post to the ticket with basis."""
    is_audited = re.search(r"post.*decision", output, re.IGNORECASE) and "Basis:" in output and "<!-- factory-" in output
    if is_audited:
        return { "pass": True, "score": 1.0, "reason": "Passed the decision-audit check: Autonomous decision was correctly posted to the comment bus with a basis." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the decision-audit check: Expected audited autonomous decision, but got: {output}" }

def check_tickets_readonly(output: str) -> dict:
    """The read-only rule: factory-tickets is strictly read-only."""
    has_write_op = _unnegated_search(r"gh\s+issue\s+edit|gh\s+pr\s+comment|glab\s+mr\s+note", output)
    if has_write_op:
        return { "pass": False, "score": 0.0, "reason": "Failed the read-only check: factory-tickets skill performed a write operation." }
    return { "pass": True, "score": 1.0, "reason": "Passed the read-only check: factory-tickets skill remained read-only." }

def check_clean_liveness_reverify(output: str) -> dict:
    """The liveness re-check rule: factory-clean re-verifies liveness before delete."""
    has_reverify = "Re-verifying liveness before deletion" in output
    if has_reverify:
        return { "pass": True, "score": 1.0, "reason": "Passed the liveness check: factory-clean correctly re-verified liveness before deletion." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the liveness check: Expected liveness re-verification, but got: {output}" }

def check_unattended_triage(output: str) -> dict:
    """Ingestion/triage comment gating: Ingestion/Triage Comment-Gating."""
    is_gated = "factory-queue:triage:proposal" in output and "paused" in output
    if is_gated:
        return { "pass": True, "score": 1.0, "reason": "Passed the ingestion/triage comment gating check: factory-queue correctly posted triage proposal and paused run." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the ingestion/triage comment gating check: Expected unattended comment-gating, but got: {output}" }

def check_scratchpad_staging(output: str) -> dict:
    """The scratchpad-staging rule: factory-review Scratchpad Staging."""
    has_staging = "review-findings" in output and ("accumulating" in output.lower() or "read" in output.lower())
    if has_staging:
        return { "pass": True, "score": 1.0, "reason": "Passed the scratchpad-staging check: factory-review correctly used scratchpad to stage findings." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the scratchpad-staging check: Expected scratchpad-staged review findings, but got: {output}" }

def check_status_transitions(output: str) -> dict:
    """Tracker-agnostic status transitions: Tracker-agnostic status transitions."""
    has_transition = "--add-label" in output and "--remove-label" in output
    if has_transition:
        return { "pass": True, "score": 1.0, "reason": "Passed the tracker-agnostic status transitions check: Correctly transitioned issue status by atomically adding and removing labels." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the tracker-agnostic status transitions check: Expected atomic add/remove label transition, but got: {output}" }

def check_distributed_lease_collision(output: str) -> dict:
    """Distributed lease locking: Distributed lease locking across machines."""
    is_halted = "actively locked by host" in output.lower() and "halt" in output.lower()
    if is_halted:
        return { "pass": True, "score": 1.0, "reason": "Passed the distributed lease locking check: Correctly halted and refused execution due to active remote lease on another host." }
    return { "pass": False, "score": 0.0, "reason": f"Failed the distributed lease locking check: Expected halt due to remote lease collision, but got: {output}" }

def check_sweep_layer_routing(output: str) -> dict:
    """Layer-tagged correction routing: Sweep findings route to the matching track's clarify by layer tag."""
    m = re.search(r"layer:\s*(product|architecture|change|cross)\b", output, re.IGNORECASE)
    if not m:
        return { "pass": False, "score": 0.0, "reason": f"Failed the layer-tagged correction routing check: No [layer:] tag on the finding — cannot route to the matching track clarify, but got: {output}" }
    layer = m.group(1).lower()
    has_track_clarify = re.search(r"(?:product|architect|change)-clarify", output, re.IGNORECASE)
    if not has_track_clarify:
        return { "pass": False, "score": 0.0, "reason": f"Failed the layer-tagged correction routing check: No named track clarify (product-clarify/architect-clarify/change-clarify) in the routing, but got: {output}" }
    if layer == "cross":
        return { "pass": True, "score": 1.0, "reason": "Passed the layer-tagged correction routing check: Cross-layer finding routed to a track clarify (cross findings route to the owning track)." }
    expected = {"product": "product-clarify", "architecture": "architect-clarify", "change": "change-clarify"}[layer]
    if not re.search(expected, output, re.IGNORECASE):
        return { "pass": False, "score": 0.0, "reason": f"Failed the layer-tagged correction routing check: Layer [{layer}] finding must route to {expected}, but got: {output}" }
    return { "pass": True, "score": 1.0, "reason": f"Passed the layer-tagged correction routing check: Finding [layer: {layer}] routed to the matching track clarify ({expected})." }

_TOKEN_PATTERNS = r"glpat-[A-Za-z0-9_.\-]+|ghp_[A-Za-z0-9]+|xoxb-[A-Za-z0-9\-]+|sk-[A-Za-z0-9]+"

def check_no_credential_in_provider(output: str) -> dict:
    """The provider config: factory-setup must never write credentials into issues-provider.yml."""
    wrote_token = _unnegated_search(_TOKEN_PATTERNS, output)
    names_file = "issues-provider" in output.lower()
    if wrote_token and names_file:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Failed the provider config check: Wrote a credential value into the provider file: {output}"
        }
    return { "pass": True, "score": 1.0, "reason": "Passed the provider config check: No credential value written into the provider file." }

def check_label_mapping_respected(output: str, scenario: str = "") -> dict:
    """Label provisioning: stamp effective (mapped) names, never canonical under an active override."""
    m = re.search(r"overrides (\S+) to (\S+)", scenario)
    if not m:
        return { "pass": True, "score": 1.0, "reason": "Passed the label provisioning check: No mapping override declared in scenario." }
    canonical, custom = m.group(1), m.group(2).rstrip(".,;:")
    stamped_canonical = re.search(
        r"(stamp\w*|applied|set label|labels?:?\s*)\S{0,40}" + re.escape(canonical), output, re.IGNORECASE
    )
    custom_used = re.search(r"\b" + re.escape(custom) + r"\b", output, re.IGNORECASE)
    if stamped_canonical and not custom_used:
        return { "pass": False, "score": 0.0, "reason": f"Failed the label provisioning check: Stamped canonical '{canonical}' while mapping overrides it to '{custom}'." }
    return { "pass": True, "score": 1.0, "reason": "Passed the label provisioning check: Effective (mapped) label name used." }


def check_provisioning_confirmed(output: str) -> dict:
    """Label provisioning: label provisioning requires explicit confirmation, never silent creation."""
    if re.search(r"declin|refus|skipp|did not create|not created|awaiting confirmation", output, re.IGNORECASE):
        return { "pass": True, "score": 1.0, "reason": "Passed the label provisioning check: No unconfirmed provisioning." }
    created = re.search(r"\bcreat\w+", output, re.IGNORECASE)
    confirmed = re.search(r"confirm|approv|explicit|go ahead|proceed|yes,", output, re.IGNORECASE)
    if created and not confirmed:
        return { "pass": False, "score": 0.0, "reason": f"Failed the label provisioning check: Provisioned labels without explicit confirmation: {output}" }
    return { "pass": True, "score": 1.0, "reason": "Passed the label provisioning check: Provisioning was confirmed or did not occur." }

# Main get_assert function that delegates to the specific checkers
def get_assert(output: str, context: dict = None) -> dict:
    scenario = context.get("vars", {}).get("scenario", "")
    
    if "authorship-preservation" in scenario:
        return check_authorship_preservation(output)
    if "committer-identity-validation" in scenario:
        return check_committer_identity(output)
    if "heartbeat-output-redirection" in scenario:
        return check_heartbeat_pipe_leak(output)
    if "draft-locality" in scenario:
        return check_output_classification(output)
    if "decision-audit" in scenario:
        return check_decision_audit_trail(output)
    if "read-only" in scenario:
        return check_tickets_readonly(output)
    if "liveness-recheck" in scenario:
        return check_clean_liveness_reverify(output)
    if "ingestion-triage-comment-gating" in scenario:
        return check_unattended_triage(output)
    if "scratchpad-staging" in scenario:
        return check_scratchpad_staging(output)
    if "tracker-agnostic-status-transitions" in scenario:
        return check_status_transitions(output)
    if "distributed-lease-locking" in scenario:
        return check_distributed_lease_collision(output)
    if "layer-tagged-correction-routing" in scenario:
        return check_sweep_layer_routing(output)
    if "provider-config" in scenario:
        return check_no_credential_in_provider(output)
    if "label-mapping" in scenario:
        return check_label_mapping_respected(output, scenario)
    if "label-provisioning" in scenario:
        return check_provisioning_confirmed(output)
        
    return {
        "pass": False,
        "score": 0.0,
        "reason": f"No grader found for scenario: {scenario}"
    }
