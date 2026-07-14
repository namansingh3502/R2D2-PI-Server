import pytest

from r2d2_server import proximity_controller


class FakeDistanceDevice:
    def __init__(self, distance: float) -> None:
        self._distance = distance

    @property
    def distance(self) -> float:
        return self._distance

    def close(self) -> None:
        pass


def test_proximity_pins_are_logically_swapped() -> None:
    assert proximity_controller.PROXIMITY_PINS == {
        "left": {"trigger": 13, "echo": 19},
        "right": {"trigger": 5, "echo": 6},
    }


def test_read_returns_centimeters(monkeypatch: pytest.MonkeyPatch) -> None:
    proximity_controller.set_proximity_available_for_testing(True)
    monkeypatch.setattr(
        proximity_controller,
        "LEFT_SENSOR",
        FakeDistanceDevice(0.321),
    )
    monkeypatch.setattr(
        proximity_controller,
        "RIGHT_SENSOR",
        FakeDistanceDevice(1.234),
    )

    reading = proximity_controller.read()

    assert reading["type"] == "proximity"
    assert reading["left_cm"] == 32.1
    assert reading["right_cm"] == 123.4
