# Reproduce the natural-source qualification

The full `studio/run.py --verify` gate is described in the root README. The original-upload source experiments are separate and need the credited originals. All selected source URLs, SHA-256, listed rights and adaptations are in `evidence/natural-v6/sources.json` (private mirror: `research/natural-v6/`). Do not author or inject a visual defect. Use a fresh output directory for every experiment; retain failed outcomes.

On a Linux Docker host, obtain the untouched Writer and Portuguese user-page originals from those pinned records into an `originals/` directory, named `libreoffice-writer.webm` and `wiki-userpage.webm`. Verify their SHA-256 against the recorded values. From the source root, after building `frame-review`:

```
docker run --name writer-check --network none --cpus 1 -v "$PWD/docs/natural-v6:/audit:ro" -v "$PWD/originals:/new:ro" frame-review python /audit/qualify-natural-v6.py /tmp/writer /new/libreoffice-writer.webm 150 /audit/natural-v6-writer-case.json
docker cp writer-check:/tmp/writer ./writer-check-evidence
docker run --name caption-check --network none --cpus 1 -v "$PWD/docs/natural-v6:/audit:ro" -v "$PWD/originals:/new:ro" frame-review python /audit/qualify-natural-v6.py /tmp/caption /new/wiki-userpage.webm 236 /audit/natural-v6-userpage-case.json
docker cp caption-check:/tmp/caption ./caption-check-evidence
```

The harness operates the actual HTTP import, review/plan, stale-approval refusal, explicit approval, export and downloads. It independently decodes original/edit samples, verifies boundary metrics, exact native/RGB/audio/timing/source recovery and every downloaded boundary and teaching PNG. It mutates only generated proof artifacts to test tamper refusal, restores them, and records recovery. It does not modify lesson footage.

For the 21-window first screen, fetch the seven `natural-v6-sources.json` originals with exact filenames and hashes into `originals/`; invoke `/audit/natural-v6-cohort.py /tmp/cohort` with the same mounts. For the 12-window second screen, use `natural-v6b-sources.json` and `natural-v6b-cohort.py`. Their exact selection plans are alongside the harnesses. The first historical screen used `a900...` v5; rerunning on current v6 is a reproduction of the identical detector/cut policy, not the original historical execution. The existing first- and second-cohort JSON records identify their exact manifests. Keep all source outcomes, including zero proposals and declined rapid candidates.

For the three teaching-content refusals, provide `toybox-implementation.webm`, `libreoffice-writer.webm` and `libreoffice-import.webm`, then invoke `/audit/qualify-natural-v6-protections.py /tmp/protections`. The archived first Calc attempt used an overlong label; current harness has the corrected label. Reruns must not erase that negative.

The seven previous original-source regressions require the originals/starts/rectangles in `natural-v4-cases.json` and `natural-v5-gentoo-case.json`. Their filenames are historical, while `qualify-natural-v6.py` recomputes the current proposal and requires the v6 teaching proof. The delivered nine receipts identify each actual source hash, output hash and checked plan. Cloud/browser/playback receipts are distinct from this local HTTP qualification. No creator preference or human-benefit study is implied.
