"""Fail-closed experiment acceptance, not publication or artistic approval."""
import json


def acceptance_checks(data):
    count = len(data['recipe']['mapping'])
    regions = data['protected']['regions']
    intended_regions = data['recipe']['protected_regions']
    protected_exact = (data['protected']['frames'] == count and len(regions) == len(intended_regions)
        and all(r['label'] == expected['label'] and r['xywh'] == expected['xywh']
                and all(r['measurements'][k] == 0 for k in ('mean_rgb_code_error','p99_rgb_code_error','max_rgb_code_error'))
                for r,expected in zip(regions,intended_regions)))
    return {
        'audio_exact': not data.get('audio_preservation',{}).get('present',False) or (set(data['audio_preservation']['checks'])=={'control','edited'} and all(set(c)=={'stream_exact','packet_payload_timing_skip_exact','decoded_pcm_exact'} and all(v is True for v in c.values()) for c in data['audio_preservation']['checks'].values())),
        'fresh_source_bound_detection': data['fresh_pixel_detection_matches'] is True,
        'native_output_exact': data['native_output_exact'] is True,
        'timestamps_exact': data['timing_exact'] is True,
        'original_masters_unchanged': data['masters_unchanged'] is True,
        'outside_interval_frames_exact': data['outside_interval_frames_exact'] is True,
        'protected_regions_exact_vs_source': protected_exact,
        'outside_budget': data['outside_rgb']['mean_rgb_code_error'] <= 1 and data['outside_rgb']['p99_rgb_code_error'] <= 3,
        # The no-declared-region development case must preserve all outside RGB.
        'unprotected_profile_outside_exact': bool(intended_regions) or data['outside_rgb']['max_rgb_code_error'] == 0,
        'all_cycle_phases_retained': data['retained_cycle_phases'] == list(range(data['detection']['period_frames'])),
    }


def finalize_candidate(data, pending_path, output_directory, accepted_name="retimed-master.mp4"):
    """Keep rejected bytes diagnostic-only; accepted filename appears after checks."""
    checks = acceptance_checks(data)
    accepted = all(checks.values())
    name = accepted_name if accepted else 'rejected-candidate.mp4'
    destination = output_directory / name
    if destination.exists():
        raise FileExistsError('Refusing to replace an existing candidate artifact.')
    pending_path.rename(destination)
    data['acceptance'] = {'status': 'accepted_experiment' if accepted else 'rejected_experiment',
                          'checks': checks,
                          'meaning': 'Mechanical preservation checks only; creator review remains required.'}
    data['output_artifact'] = {'filename': name, 'download_recommended': False,
                              'role': 'measured_candidate_for_creator_review' if accepted else 'rejected_diagnostic_only'}
    (output_directory / 'result.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    return accepted
