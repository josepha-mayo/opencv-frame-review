# Reproduce the natural lesson development audit

Build the root Dockerfile and run `python studio/run.py --verify /tmp/NEW_GATE_DIRECTORY` in its Linux image. The full thirteen-stage suite includes the three bundled prepared natural lessons; that suite does not replace untouched-original qualification.

The scripts in this directory are the actual external audit harnesses. They are mounted into the image as `/audit`, not installed as application runtime. Fetch originals from `evidence/natural-v4/sources.json` and verify each SHA-256 before processing. Keep source filenames as recorded; originals are not bundled here. Preserve source licenses and credits. For the new four-source cohort, `natural-v4-sources.json` contains only those four sources and the original timing rule is in `natural-v4-selection-plan.json`.

Example from the repository root on Linux (replace the local original paths and use new container/output names):

```sh
docker run --name jupyter-original-check --network none -v "$PWD/docs/natural-v4:/audit:ro" -v "$PWD/originals:/originals:ro" frame-review python /audit/qualify-natural-v4.py /tmp/jupyter-check /originals/jupyter.webm 301 /audit/jupyter-case.json
docker cp jupyter-original-check:/tmp/jupyter-check ./jupyter-evidence
docker run --name new-cohort-check --network none -v "$PWD/docs/natural-v4:/audit:ro" -v "$PWD/originals:/new:ro" frame-review python /audit/natural-v4-cohort.py /tmp/cohort-check
docker cp new-cohort-check:/tmp/cohort-check ./cohort-evidence
```

The published case configuration files contain the named teaching areas actually used. The original qualification harness tests missing teaching protection and stale plans, performs approved HTTP export, downloads exact original/prepared/output/crops, and independently decodes native mapping, outside samples, teaching RGB and prepared PCM. Failed assertions mean the case is not qualified.

For the recorded six-case blur references and trace collector, use the same `/evidence/originals/CASE/results.json` directory layout as the qualification. `natural-v4-blur-reference.py QUALIFICATION_JSON NEW_OUTPUT` encodes and checks the fixed Gaussian reference. `compare-natural-v4.py` reads `/evidence/originals` and `/evidence/blur-references`, then decodes all three actual encoded methods. Its output directory must be new. Keep evidence in native Linux storage; bind mounts of Windows NTFS do not reproduce all worker filesystem assumptions.

All results are development evidence. The selection plan preceded the new cohort outcomes, but final code was revised afterward using development cases. The cohort is a convenience sample without exhaustive distraction annotation; it does not estimate detector recall or creator benefit. The two earlier browser-caret sources are development repairs, and Tamil is a prior-source regression. Presets and cloud runs do not add independent sources.
