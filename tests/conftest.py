from datetime import datetime
from pathlib import Path

import pytest

from emporio_agent.config import STORE_TZ, Clock
from emporio_agent.data.repository import StoreRepository

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="session")
def repo() -> StoreRepository:
    return StoreRepository.from_csv(DATA_DIR)


@pytest.fixture
def clock() -> Clock:
    return Clock(datetime(2026, 3, 25, 10, 30, tzinfo=STORE_TZ))
