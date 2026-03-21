from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def workspace_tmp_path() -> Path:
    base_dir = Path(__file__).resolve().parent / ".tmp"
    base_dir.mkdir(exist_ok=True)

    temp_dir = base_dir / uuid.uuid4().hex
    temp_dir.mkdir()

    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
