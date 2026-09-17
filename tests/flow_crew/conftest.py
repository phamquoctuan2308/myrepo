from __future__ import annotations

import pytest

from src.flow_crew.clock import SimClock, at
from src.flow_crew.engine import FlowCrewEngine
from src.flow_crew.mock_park import MockPark


@pytest.fixture
def park() -> MockPark:
    return MockPark()


@pytest.fixture
def engine() -> FlowCrewEngine:
    """Engine đứng đúng 14:05 — mốc mở đầu hero flow ở mục 7."""

    return FlowCrewEngine(clock=SimClock(at(14, 5)))
