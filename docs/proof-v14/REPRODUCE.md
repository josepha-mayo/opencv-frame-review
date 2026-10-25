# Full-size proof inspection, v14

The review cards shrink source-bound PNG crops to fit their columns. This can make teaching text hard to inspect even when pixel preservation passes. V14 gives each valid boundary and teaching crop an **Open full-size PNG in a new tab** link. It retains the owned, same-origin PNG URL; the browser can inspect it without the review-card width constraint. It does not reconstruct text or increase source resolution.

The link starts hidden. Image load must report the expected natural dimensions before it is offered. A dimension mismatch or load error hides both the image and its link, preserving the incomplete-comparison warning. Links use `noopener noreferrer`; no new media endpoint or permission is introduced. An added executable DOM regression exercises success, dimensions, error and link attributes. Actual browser checks are separate.

This is an engineering usability improvement, not a result from a participant. The human pilot protocol, stimulus files, question order/allocation, cutoff and analysis are unchanged. QA never enters human counts. The independent-viewer and creator groups stay separate.

## Verification and reproduction

Freeze the studio manifest using `python studio/build_manifest.py --write --build lesson-rescue-proof-inspection-2026-10-25-v14`. The frozen manifest covers 119 files; only `studio/static/app.js` and `studio/tests/test_studio_ui.py` differ from v12. The encoder, detector and preservation/cut thresholds are unchanged.

The qualification image layers those two files and the manifest onto the exact qualified v12 image. Run `python studio/run.py --check`, then `python studio/run.py --verify /evidence/gate` with one vCPU, 2 GiB and no container network. Run the source-bound qualifier on the untouched French upload-assistant original at seconds140–152 and Joomla original at60–72, using the unchanged declared teaching areas. Verify all ZIP hashes, pinned native samples, teaching sequences, audio/timestamps and transition gates. Run the current HTTPS upload/plan/explicit-approval/download path separately, and compare every media/PNG byte to the native qualification. These are regression repeats, not new discoveries.

Build preparation and qualification scripts are retained in this folder. Scoped temporary CodeBuild access is removed after artifact collection. Deployment retains the existing ECS worker CPU/memory, processing bounds, ownership and origin checks. The app release must be verified from the live deployment manifest and real Brave review; a build alone is not delivery.

## Human measurement and recruitment

The prospective protocol is under `human-study/`. A neutral volunteer request was published to the official competition discussion board: https://opencv26.devpost.com/forum_topics/45681-3-4-minute-lesson-clip-study-looking-for-adult-volunteers . The project page also requests volunteers. These are recruitment actions, not evidence that anyone enrolled. Results are published only from actual submitted records, with QA excluded, and with failures, skips, ties and neither choices retained. A creator-only pilot cannot establish independent preference or learning benefit.

No demo/voice recording, PR or cron is part of this release.

## Retained browser failure and correction

The first v13 build passed 14 Linux stages and two real-source native/API checks, but actual Brave review found all 18 teaching images stuck loading. Hidden images using native lazy loading never reached the callback that would reveal them. V14 makes this bounded set eager while keeping the image and full-size link withheld until its dimension check passes. A new regression rejects hidden+lazy proof rendering; a recorded real-PNG browser harness verifies native loading and full-size opening before live promotion. Local rendering is reported separately from live encoding. Top-level viewport emulation did not take effect in this Brave session; contained 375/890px rendering and actual desktop live checks are explicitly separate from physical-phone qualification.
