# Authored math lesson

`lesson.mp4` is a 12-second, 640x360, 30 fps synthetic lesson about the line `y = -2x + 1`. Its equation and explanatory text stay visible; its graph marker and step counter change on the original timeline. A separate decoration repeats every six frames inside a bounded interval. It is deliberately unsuitable as a lesson-design recommendation: its purpose is to expose the tradeoff that the retiming experiment must measure.

All lesson graphics and text were authored for this project with Python/OpenCV. `narration.mp3` uses Microsoft Aria neural speech via edge-tts 7.3.1, at +10% rate, from this script:

> To graph y equals negative two x plus one, start at one on the vertical axis. Move one step right, and two steps down. The slope is negative two.

The generator refuses narration longer than 12 seconds. It prepares a canonical AAC-LC mono/48 kHz source, padding its endpoint to 12 seconds before the editing experiment starts. The editor then copies that source track; it does not stretch, trim or re-encode it. Keep source preparation separate from the editor's preservation result.

The script is reproduced by running `make_lesson.py narration.mp3 lesson.mp4` inside the pinned runtime. It refuses to overwrite an output. Neither these authored graphics nor their neural narration is a real teacher trial or evidence of learning benefit. This document describes the authored math fixture only. The separate real classroom WebM and augmented challenge use ITTT footage and human narration under CC BY 3.0; see `fixtures/REAL_LESSON_CREDIT.json` and `../docs/real-lesson-evaluation.md` for credits, changes and limits.
