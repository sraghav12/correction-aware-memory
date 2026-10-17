"""Shared action validation and conservative deterministic proposals."""

from dataclasses import asdict

from cam.contracts import ContractError, DecisionRequest, Proposal, parse_observation, parse_proposal


def heads(versions):
    replaced = {version.parent_version_id for version in versions if version.parent_version_id}
    return {version.effective_at: version for version in versions if version.version_id not in replaced}


def validate(request: DecisionRequest, proposal: Proposal) -> list[str]:
    try:
        observation = parse_observation(asdict(request.observation))
        proposal = parse_proposal(asdict(proposal))
    except (ContractError, TypeError, AttributeError):
        return ["INVALID_SCHEMA"]
    errors = []
    if len(request.candidate_versions) > 16:
        errors.append("CONTEXT_LIMIT")
    if (proposal.source_id, proposal.evidence_start, proposal.evidence_end) != (
        observation.source_id, observation.evidence_start, observation.evidence_end
    ):
        errors.append("EVIDENCE_MISMATCH")
    if proposal.action == "no_op":
        return errors
    if proposal.review_required:
        errors.append("REVIEW_REQUIRED")
    if observation.authority != "official":
        errors.append("UNTRUSTED_SOURCE")
    if proposal.value != observation.value:
        errors.append("VALUE_MISMATCH")
    if proposal.effective_at != observation.effective_at or observation.effective_at is None:
        errors.append("DATE_MISMATCH")
    by_id = {version.version_id: version for version in request.candidate_versions}
    timeline = heads(request.candidate_versions)
    latest = timeline[max(timeline)] if timeline else None
    target = by_id.get(proposal.target_version_id)
    if proposal.action == "create":
        if timeline or proposal.target_version_id is not None or observation.value is None or observation.corrects_observation_id:
            errors.append("INVALID_CREATE")
    elif target is None:
        errors.append("UNKNOWN_TARGET")
    elif proposal.action == "reinforce":
        if target != latest or observation.effective_at != target.effective_at or observation.value != target.value or observation.corrects_observation_id:
            errors.append("INVALID_REINFORCE")
    elif proposal.action == "supersede":
        if target != latest or observation.effective_at is None or observation.effective_at <= target.effective_at or observation.value == target.value or observation.corrects_observation_id:
            errors.append("INVALID_SUPERSEDE")
    elif proposal.action == "update":
        referenced = next((version for version in by_id.values()
                           if observation.corrects_observation_id in version.observation_ids), None)
        if (not observation.correction_authorized or referenced is None
                or target != timeline.get(target.effective_at)
                or observation.effective_at != target.effective_at
                or (referenced and referenced.effective_at != target.effective_at)):
            errors.append("UNAUTHORIZED_CORRECTION")
    if observation.value is None and proposal.reason_code != "retraction":
        errors.append("RETRACTION_REASON_REQUIRED")
    return errors


def propose_rule(request: DecisionRequest) -> Proposal:
    observation = request.observation

    def proposal(action, target=None, reason="initial_fact", review=False):
        return Proposal(action, target, None if action == "no_op" else observation.value,
                        None if action == "no_op" else observation.effective_at,
                        observation.source_id, observation.evidence_start, observation.evidence_end,
                        reason, review)

    def ignore(reason, review=False):
        return proposal("no_op", reason=reason, review=review)

    if len(request.candidate_versions) > 16:
        raise ContractError("CONTEXT_LIMIT")
    if any(observation.observation_id in version.observation_ids for version in request.candidate_versions):
        return ignore("duplicate")
    if observation.authority != "official":
        return ignore("untrusted", True)
    if observation.effective_at is None:
        return ignore("ambiguous", True)
    timeline = heads(request.candidate_versions)
    if observation.corrects_observation_id:
        referenced = next((version for version in request.candidate_versions
                           if observation.corrects_observation_id in version.observation_ids), None)
        if not observation.correction_authorized:
            return ignore("untrusted", True)
        if referenced is None or referenced.effective_at != observation.effective_at:
            return ignore("ambiguous", True)
        target = timeline[observation.effective_at]
        return proposal("update", target.version_id, "retraction" if observation.value is None else "authorized_correction")
    if not timeline:
        return ignore("retraction_unsupported", True) if observation.value is None else proposal("create")
    latest = timeline[max(timeline)]
    if observation.effective_at < latest.effective_at:
        return ignore("stale") if observation.effective_at in timeline else ignore("ambiguous", True)
    if observation.effective_at == latest.effective_at:
        if observation.value == latest.value:
            return proposal("reinforce", latest.version_id, "retraction" if observation.value is None else "same_fact")
        return ignore("ambiguous", True)
    if observation.value == latest.value:
        return ignore("ambiguous", True)
    return proposal("supersede", latest.version_id, "retraction" if observation.value is None else "new_effective_state")
