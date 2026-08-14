import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT


@pytest.fixture()
def tmp_path_fix(tmp_path):
    return tmp_path
