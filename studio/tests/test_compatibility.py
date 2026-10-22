"""Run existing UI contract and recovery tests against the studio interface."""
import importlib
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent / 'opencv-ready/candidate/app/tests'))


def load_tests(loader, tests, pattern):
    for name in ('test_ui_static', 'test_boundary_ui_static', 'test_protection_ui_static', 'test_recovery_ui'):
        module = importlib.import_module(name)
        module.APP = STUDIO
        module.SCRIPT = STUDIO / 'static/app.js'
        tests.addTests(loader.loadTestsFromModule(module))
    return tests
