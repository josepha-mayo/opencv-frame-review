# Real lesson evaluation, 22–23 October 2026

Two independently published lessons were tested, using seconds 40–52 of their original files. This is a functional evaluation of selected excerpts, not a representative benchmark or a teacher-benefit study.

| Original | Attribution and license | Input |
|---|---|---|
| [Present Simple — Teaching Ideas — 1](https://commons.wikimedia.org/wiki/File:English_Grammar_%E2%80%94_Present_Simple_%E2%80%94_Teaching_Ideas_%E2%80%94_1.webm) | TEFL & TESOL Courses – ITTT, 9 April 2013; [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); [original video](https://www.youtube.com/watch?v=jAcNhNCQKuo) | 854×480, 30000/1001 fps, VP8/Vorbis stereo, 218.154 s, 6,934,862 bytes |
| [8.2 Adding citations](https://commons.wikimedia.org/wiki/File:8.2_Adding_citations.webm) | Jimmyjrg (James Gaunt), 2024; [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); embedded Wikimedia material credited to Wikimedia Foundation under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). No endorsement. | 1920×1080, 60 fps, AV1/Vorbis stereo, 358.202 s, 25,655,057 bytes |

The classroom original is included unchanged in `studio/fixtures/real-teacher.webm`. The screencast original can be fetched with the hash-checking script alongside this document. Media licenses are separate from the project's source-code notice. Preserve these credits with copies. Prepared/edited classroom derivatives retain CC BY 3.0 attribution; distribute any adapted Wikimedia lesson media under CC BY-SA 4.0, retaining both Jimmyjrg and Wikimedia Foundation credits and this change description.

Preparation selects an excerpt, scales/letterboxes to 640×360, converts to 30 fps and encodes an AAC-LC mono/48 kHz track once. This changes picture and audio. Exact edit preservation is subsequently measured against that prepared source. Original uploads remain downloadable with their original SHA-256 in a separate receipt. No claim of lossless normalization is made.

The tested unmodified excerpts produced no candidate. Both were explicitly left unchanged, with the original upload downloadable byte-for-byte. Source-to-prepared narration correlations after independent mono/48 kHz decoding were 0.99604 and 0.99975, with best measured lag zero over a ±10 ms search. These are lossy-preparation checks, not original-packet identity claims.

The positive edit challenge uses the real classroom footage and human narration, plus a deliberately added flashing 32×32 square at [588,260] in its existing black margin. The defect is authored; this is **augmented real footage, not a naturally defective lesson**. A creator protects the teacher/whiteboard rectangle [80,0,480,360] and approves the detected corner. Independent checks cover all 360 protected RGB frames, outside native samples, the intended native mapping, audio PCM and all twelve response-PNG hashes. The editor also checks packet/timing/skip metadata. The original lesson's teacher is never described as a user or endorser.

The integration script generates the controlled challenge from the prepared classroom source, rather than hiding the added defect in a natural-video claim. To reproduce the wider two-source evaluation, fetch the originals, place them in the pinned Docker runtime's native Linux storage, and run:

```sh
python studio/tests/integration_real_lessons.py /tmp/real-evaluation /path/to/evaluation-originals
```

The offline `studio/run.py --verify` includes classroom preparation and the augmented challenge among its ten stages. The external screencast is additional evaluation. Both the ten-stage gate and the separate two-source evaluation passed in the final rebuilt image on 23 October. Actual local browser checks covered the original screencast, no-edit recovery, the classroom challenge, all twelve loaded crops, report/output/independent hash agreement, owning-session download checks and error-free playback through 12 seconds. The new real-intake release has not yet replaced the earlier public AWS app; that upgrade awaits the existing-account credential refresh.

Negative checks include unsupported playlist/URL containers, malformed WebM, invalid excerpt lengths and changed source identities. Existing codec/audio/pixel/refusal checks remain unchanged. Fixed rectangles, tiny selected excerpts, periodicity assumptions and known package-scan findings remain material limits. The service runs as an unprivileged UID, with isolated bounded preparation subprocesses, file/pipe-only demuxing and existing cookie/origin/token controls. This is not a security certification.
