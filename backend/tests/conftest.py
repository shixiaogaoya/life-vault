import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def sample_data_dir() -> Path:
    """Sample data directory"""
    return Path(__file__).parent.parent.parent / "sample_data"


@pytest.fixture(scope="session")
def demo_json_path(sample_data_dir: Path) -> Path:
    """Demo JSON file path"""
    return sample_data_dir / "demo.json"


@pytest.fixture(autouse=True)
def set_test_db_path(tmp_path: Path) -> None:
    """Set temporary database path for all tests"""
    db_path = tmp_path / "test_archive.db"
    os.environ["LIFEVAULT_DB_PATH"] = str(db_path)
