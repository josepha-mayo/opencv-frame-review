"""Explain the current evidence-driven route without inventing an event history."""
import hashlib
import json


def snapshot(job, approval=None):
    """Read-only explanation. Never authorizes an action or calls a media tool."""
    status = job['status']
    candidates = job.get('candidates', [])
    approved = False
    if approval is not None:
        recipe = approval.get('recipe', {})
        raw = json.dumps(recipe, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if (approval.get('approve') is not True
                or hashlib.sha256(raw).hexdigest() != approval.get('recipe_sha256')
                or approval.get('prediction_sha256') != job.get('prediction_sha256')
                or recipe.get('prediction_sha256') != job.get('prediction_sha256')
                or recipe.get('candidate_id') != approval.get('candidate_id')
                or not any(c['id'] == approval.get('candidate_id') for c in candidates)
                or recipe.get('input_sha256') != job.get('input_sha256')):
            raise ValueError('Workflow approval/source binding changed.')
        approved = True
    summary = job.get('summary') or {}
    checks = summary.get('checks') or {}
    failed_checks = [name for name, value in checks.items() if value is not True]
    proof_errors = [name for name in ('frame_review_error', 'teaching_review_error') if job.get(name)]
    if status in ('queued', 'analyzing', 'exporting'):
        route, next_action = 'wait_for_tools', 'Wait for bounded media processing. No new approval is requested.'
    elif status == 'review' and not candidates:
        route, next_action = 'keep_source', 'No supported proposal. Keep the lesson unchanged; this does not mean distraction-free.'
    elif status == 'review':
        route, next_action = 'request_human_review', 'Inspect both source states and mark teaching areas. Check a fresh plan before explicitly generating a comparison, or leave unchanged.'
    elif status == 'declined':
        route, next_action = 'keep_source', 'You chose to leave the lesson unchanged. Keep the retained source and decision record.'
    elif status == 'cancelled':
        route, next_action = 'cancelled', 'Processing was cancelled. No result is accepted by this workflow.'
    elif status == 'complete' and approved and checks and not failed_checks and not proof_errors:
        route, next_action = 'inspect_comparison', 'Encoded checks passed. Inspect the comparison and proofs, then decide whether to use it. Generating it did not accept it for use.'
    else:
        route, next_action = 'withhold_recommendation', 'A complete, source-bound comparison is unavailable. Keep the source; inspect the failure before trying another plan.'
    selected = next((c for c in candidates if approval and c['id'] == approval.get('candidate_id')), None)
    return {
        'schema': 'frame-review-workflow-v1', 'job_id': job['id'], 'status': status,
        'kind': 'Deterministic vision workflow; no language model or autonomous creator acceptance.',
        'scope': 'Current evidence snapshot, not a chronological event log, agent reasoning transcript or independent media verification. Existing server gates alone authorize actions.',
        'input_sha256': job.get('input_sha256'), 'prediction_sha256': job.get('prediction_sha256'),
        'observation': {'supported_proposals': len(candidates),
                        'candidate_ids': [c['id'] for c in candidates],
                        'meaning': 'OpenCV proposals are measured activity, not semantic distraction labels.'},
        'human_control': {'source_bound_generation_approval': approved,
                          'creator_acceptance_for_use': 'not_recorded',
                          'recipe_sha256': approval['recipe_sha256'] if approved else None},
        'selected_proposal': {k: selected[k] for k in ('id', 'bbox', 'interval_frames', 'reference_frame') if k in selected} if selected else None,
        'verification': {'reported_checks': checks, 'failed_checks': failed_checks,
                         'proof_errors': proof_errors, 'failure_reason': job.get('error')},
        'route': route, 'next_action': next_action,
        'impact_scope': 'No measured teacher preference, learning, attention, accessibility or time saved.'
    }
