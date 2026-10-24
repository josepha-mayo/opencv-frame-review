FROM opencv-creator:area-editor-v8-layer
COPY --chown=10001:10001 ["studio/lesson_intake.py", "/app/studio/lesson_intake.py"]
COPY --chown=10001:10001 ["studio/prepare_worker.py", "/app/studio/prepare_worker.py"]
COPY --chown=10001:10001 ["studio/static/app.js", "/app/studio/static/app.js"]
COPY --chown=10001:10001 ["studio/static/index.html", "/app/studio/static/index.html"]
COPY --chown=10001:10001 ["studio/static/styles.css", "/app/studio/static/styles.css"]
COPY --chown=10001:10001 ["studio/tests/test_lesson_intake.py", "/app/studio/tests/test_lesson_intake.py"]
COPY --chown=10001:10001 ["studio/tests/test_studio_ui.py", "/app/studio/tests/test_studio_ui.py"]
COPY --chown=10001:10001 ["studio/BUILD_HASHES.json", "/app/studio/BUILD_HASHES.json"]
RUN python studio/run.py --check
