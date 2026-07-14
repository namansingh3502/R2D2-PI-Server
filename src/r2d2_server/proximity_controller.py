import asyncio
from collections.abc import AsyncIterator
from typing import Literal, Protocol, TypedDict, cast

from r2d2_server.logging_config import configure_logging

logger = configure_logging()


class SensorPins(TypedDict):
    trigger: int
    echo: int


# The physical sensors are mounted opposite the original labels, so expose the
# right-side GPIO pair as logical left and the left-side GPIO pair as logical right.
PROXIMITY_PINS: dict[str, SensorPins] = {
    "left": {"trigger": 13, "echo": 19},
    "right": {"trigger": 5, "echo": 6},
}
_proximity_available = True
_proximity_mode: Literal["gpio", "noop"] = "gpio"
_last_error: str | None = None


class ProximityStatus(TypedDict):
    available: bool
    mode: Literal["gpio", "noop"]
    error: str | None
    pins: dict[str, SensorPins]


class ProximityReading(TypedDict):
    type: Literal["proximity"]
    left_cm: float | None
    right_cm: float | None
    status: ProximityStatus


class DistanceDevice(Protocol):
    @property
    def distance(self) -> float: ...

    def close(self) -> None: ...


class NoOpDistanceDevice:
    def __init__(self, trigger: int, echo: int) -> None:
        self.trigger = trigger
        self.echo = echo

    @property
    def distance(self) -> float:
        return 0.0

    def close(self) -> None:
        logger.info(
            "proximity_noop_closed trigger=%s echo=%s",
            self.trigger,
            self.echo,
        )


def create_distance_device(pins: SensorPins) -> DistanceDevice:
    global _last_error, _proximity_available, _proximity_mode

    try:
        from gpiozero import DistanceSensor

        return cast(
            DistanceDevice,
            DistanceSensor(
                echo=pins["echo"],
                trigger=pins["trigger"],
                max_distance=4.0,
            ),
        )
    except (ImportError, RuntimeError, OSError) as exc:
        _proximity_available = False
        _proximity_mode = "noop"
        _last_error = str(exc)
        logger.warning(
            "proximity_sensor_unavailable trigger=%s echo=%s fallback=noop error=%s",
            pins["trigger"],
            pins["echo"],
            exc,
        )
        return NoOpDistanceDevice(pins["trigger"], pins["echo"])


LEFT_SENSOR = create_distance_device(PROXIMITY_PINS["left"])
RIGHT_SENSOR = create_distance_device(PROXIMITY_PINS["right"])


def is_available() -> bool:
    return _proximity_available


def get_status() -> ProximityStatus:
    return {
        "available": _proximity_available,
        "mode": _proximity_mode,
        "error": _last_error,
        "pins": PROXIMITY_PINS,
    }


def set_proximity_available_for_testing(available: bool) -> None:
    global _last_error, _proximity_available, _proximity_mode

    _proximity_available = available
    _proximity_mode = "gpio" if available else "noop"
    _last_error = None if available else "Proximity sensors unavailable in test"


def _read_cm(sensor: DistanceDevice) -> float | None:
    if not _proximity_available:
        return None

    try:
        return round(sensor.distance * 100, 1)
    except (RuntimeError, OSError) as exc:
        _mark_unavailable(exc)
        logger.exception("proximity_read_failed error=%s", exc)
        return None


def _mark_unavailable(exc: Exception) -> None:
    global _last_error, _proximity_available, _proximity_mode

    _proximity_available = False
    _proximity_mode = "noop"
    _last_error = str(exc)


def read() -> ProximityReading:
    return {
        "type": "proximity",
        "left_cm": _read_cm(LEFT_SENSOR),
        "right_cm": _read_cm(RIGHT_SENSOR),
        "status": get_status(),
    }


async def stream_readings(
    interval_seconds: float = 0.2,
) -> AsyncIterator[ProximityReading]:
    while True:
        yield read()
        await asyncio.sleep(interval_seconds)
