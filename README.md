# Frame Review: Keep the Lesson

**Keep the equation. Slow the distraction.**

A creator has a flattened lesson and no editable timeline. Frame Review proposes a local 5x slowdown for a repeated decoration, lets the creator name up to four areas that must remain unchanged, and checks the encoded comparison against the original source. Supported audio stays on its original timeline and is copied byte-for-byte at packet level.

## Try the AWS judge demo

Open https://le-d72c965de52749b08fd72a2513bccce1.ecs.us-east-1.on.aws and choose **Analyze the demo lesson on AWS**. Analysis does not approve an edit. The public endpoint accepts only bundled synthetic fixtures. It runs the actual OpenCV/FFmpeg worker on ECS, with one replica and one serial worker.

For the authored math lesson, protect these four rectangles (x, y, width, height):

| Area | Rectangle |
|---|---|
| Equation | 20, 55, 245, 52 |
| Explanation | 20, 112, 255, 105 |
| Graph | 300, 45, 330, 200 |
| Step counter | 20, 250, 205, 36 |

Add each area, check the edit plan, then explicitly approve generation. Inspect all twelve original/control/edited boundary crops and the actual protected-content/audio measurements. Download the edited comparison, report and recipe. A refused preservation check withholds the edited download. Declining retains the original. Reloading reopens the same job without repeating its decision; unsubmitted areas and consent clear.

## Reproduce on Linux

The Dockerfile uses Python 3.12.14, exact wheel hashes for OpenCV 5.0.0.93 and NumPy 2.3.5, and verifies the historical FFmpeg/ffprobe binary hashes.

```sh
docker build -t frame-review .
docker run --rm --network none frame-review python studio/run.py --check
docker run --name frame-review-check --network none frame-review python studio/run.py --verify /tmp/qualification
docker cp frame-review-check:/tmp/qualification ./qualification
docker run --rm --network host frame-review python studio/run.py --serve --port 8877
```

Open http://127.0.0.1:8877 for the local Linux workflow. The host-network command assumes a Linux Docker host; Docker Desktop's default bridge does not expose a server bound to the container's loopback. The web demo requires no Docker installation or AWS account.

Keep media work on native Linux storage. An earlier Windows bind mount caused a real worker timeout; unchanged source and limits passed on native Linux storage. Copy verification receipts out after the run.

## Evidence and scope

`evidence/verification.json` records all nine stages: backend units, six duration exports, duration refusals, original audio, original silent media, audio refusals, pixel refusals, the authored math lesson, and studio UI/HTTP checks. The lesson was independently decoded to check all 360 frames of the equation, explanation, changing graph and changing counter. Native outside pixels, the retime mapping, video timestamps, audio packets and decoded audio, and all twelve PNG hashes passed. See `evidence/lesson.json` and `evidence/release-binding.json`.

Inputs remain narrowly bounded: 320x180 or 640x360, 30 fps, 1-12 seconds in 0.1-second steps, limited-range BT.709 H.264/YUV420, and optional canonical AAC-LC mono/48 kHz. Many normal playable videos are refused. Fixed rectangles do not track moving objects or establish readability. The retime repeats an observed cycle, can discard variations and can retain abrupt transitions. Adjacent decoded RGB pixels may change because of chroma interpolation; declared protected areas must remain exact. No creator-benefit, medical, safety or publishing-clearance claim is made.

The frozen multimedia stack has package-scan findings. The public service checks exact bundled fixture hashes before spawning any media worker. It is an intentionally bounded demonstration, not an arbitrary public upload service. Jobs are isolated by Secure/HttpOnly/SameSite cookies, constrained by origin/host/request-token checks and resource caps, and expire after 24 hours; task replacement can clear them sooner.

`studio/BUILD_HASHES.json` identifies the active runtime source. This curated snapshot excludes the historical private archive, its missing historical screenshot and old handoff notes. It does not repair or certify that archive. No historical manifest was weakened.

The source and fixture were developed with AI assistance. The authored lesson uses disclosed neural narration. Real teacher trials, comparison with competent manual editing, ordinary-video intake and broader browser compatibility remain future evaluation.
