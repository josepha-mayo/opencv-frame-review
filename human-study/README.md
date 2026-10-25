# Frame Review reading pilot

This is a prospective, invited human preference and reading-feasibility pilot for three real screen-recorded lessons. It is separate from the editor and from its pixel-preservation evidence. The protocol and media catalog are frozen before opening human collection. Actual participant results must come from voluntary people; server-marked software QA is always excluded.

## What is measured

Each adult volunteer watches two silent, manually played 12-second variants of three lessons. The first-exposure reading answer is locked before the second variant. Lesson order and variant order are counterbalanced across 12 allocation cells. The participant may prefer either version, choose no preference or neither, report missing information, or skip. The source/edit mapping is withheld in the interface until submission. Recruitment and analysis are not blinded.

The primary outcome is the number of independent volunteers preferring the edit in at least two of three cases, preferring the source in at least two, or having no majority. All-skip submissions remain no-majority. Project-team responses are separate. Secondary outcomes are descriptive reading accuracy, answer latency after playback, paired distraction ratings, information-loss reports, missingness and playback failures. Three clips from one person are not three independent people.

The initial recruitment target is 8–12 actual adult volunteers; 96 invitation slots are capacity, not achieved enrollment. Collection stops at **2026-10-27 06:00 UTC**, regardless of the result. This small convenience pilot cannot establish learning gain, general efficacy, accessibility certification or editing time saved. Invitations and self-report do not independently authenticate unique people or attention. Browser telemetry demonstrates playback feasibility, not attention.

## Media and provenance

`protocol.json` contains the questions, visually checked ground truth, source credits and licenses. `media.json` identifies all six lossless VP9 study files by SHA-256. Pinned Linux qualification verifies every native sample against its corresponding prepared source/edit, all teaching-region RGB digests, zero audio tracks, and equal study timestamp sequences. WebM timestamp quantization is not a claim of identical MP4 timestamps. The files are private S3 assets delivered through expiring signed URLs. The study contains existing footage; it does not produce a demo or narration.

## Collection and privacy

The isolated AWS collector uses an HTTP API and Lambda, with scoped S3 asset reads and anonymous response writes. It does not alter the ECS editing worker. Invitations, signing secrets, raw responses and deployment environment files stay outside source control. There is no public result reader. The application retains no names, email, voice, camera recordings or IP addresses. Raw structured records have a prefix-scoped 30-day S3 expiration. Withdrawal marks an invitation excluded. One conditional immutable result write per invitation prevents overwrite; duplicate attempts do not add participants.

`study_server.py` assigns QA invitations server-side to separate prefixes. `analyze.py` additionally excludes QA, withdrawals, unrecognized provenance, duplicate records, allocation/binding errors and records after the fixed cutoff. No QA fixture is human evidence. Export raw records only to a private local directory; publish aggregate results and limitations only.

## Reproduction

Run `python -m unittest discover -s human-study/tests` from the repository root. The collector uses the AWS runtime boto3; tests use an in-memory store. `BUILD_HASHES.json` binds the six runtime inputs. The invitation allocation commitment is published separately without the invitation codes. Record the Git revision and protocol/media hashes before opening collection. Changes after the first human enrollment require a new protocol version and separate reporting.

Recruitment text: “Would you volunteer for a 3–4 minute anonymous comparison of short lesson clips? You must be 18 or older. Watch independently, answer what you can read, and give your own preference. Both positive and negative feedback are useful. You can skip or stop. Please use your individual invitation once and do not share it.”

Do not send invitations on the creator's behalf without authorization. A technical or QA pass is not a measured human benefit.
