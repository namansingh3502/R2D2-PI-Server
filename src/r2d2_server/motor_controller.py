from typing import Literal, Protocol, TypedDict, cast

from r2d2_server.logging_config import configure_logging

logger = configure_logging()
MOTOR_PINS = {
    "IN1": 17,
    "IN2": 27,
    "IN3": 22,
    "IN4": 23,
}
_motor_available = True
_motor_mode: Literal["gpio", "noop"] = "gpio"
_last_error: str | None = None


class MotorStatus(TypedDict):
    available: bool
    mode: Literal["gpio", "noop"]
    error: str | None
    pins: dict[str, int]


class PinDevice(Protocol):
    def on(self) -> None: ...

    def off(self) -> None: ...


class NoOpOutputDevice:
    def __init__(self, pin: int) -> None:
        self.pin = pin

    def on(self) -> None:
        logger.info("gpio_noop pin=%s state=on", self.pin)

    def off(self) -> None:
        logger.info("gpio_noop pin=%s state=off", self.pin)


class MotorControllerError(RuntimeError):
    pass


def create_output_device(pin: int) -> PinDevice:
    global _last_error, _motor_available, _motor_mode

    try:
        from gpiozero import OutputDevice

        return cast(PinDevice, OutputDevice(pin))
    except (ImportError, RuntimeError, OSError) as exc:
        _motor_available = False
        _motor_mode = "noop"
        _last_error = str(exc)
        logger.warning(
            "gpio_output_unavailable pin=%s fallback=noop error=%s",
            pin,
            exc,
        )
        return NoOpOutputDevice(pin)


IN1 = create_output_device(MOTOR_PINS["IN1"])
IN2 = create_output_device(MOTOR_PINS["IN2"])
IN3 = create_output_device(MOTOR_PINS["IN3"])
IN4 = create_output_device(MOTOR_PINS["IN4"])


def is_available() -> bool:
    return _motor_available


def get_status() -> MotorStatus:
    return {
        "available": _motor_available,
        "mode": _motor_mode,
        "error": _last_error,
        "pins": MOTOR_PINS,
    }


def set_motor_available_for_testing(available: bool) -> None:
    global _last_error, _motor_available, _motor_mode

    _motor_available = available
    _motor_mode = "gpio" if available else "noop"
    _last_error = None if available else "Motor unavailable in test"


def _mark_unavailable(exc: Exception) -> None:
    global _last_error, _motor_available, _motor_mode

    _motor_available = False
    _motor_mode = "noop"
    _last_error = str(exc)


def _set_pin_states(
    in1: bool,
    in2: bool,
    in3: bool,
    in4: bool,
) -> None:
    states = (
        (IN1, in1),
        (IN2, in2),
        (IN3, in3),
        (IN4, in4),
    )
    try:
        for device, enabled in states:
            if enabled:
                device.on()
            else:
                device.off()
    except (RuntimeError, OSError) as exc:
        _mark_unavailable(exc)
        logger.exception("motor_command_failed error=%s", exc)
        raise MotorControllerError(str(exc)) from exc


def stop() -> None:
    _set_pin_states(False, False, False, False)


def forward() -> None:
    _set_pin_states(True, False, True, False)


def backward() -> None:
    _set_pin_states(False, True, False, True)


def left() -> None:
    _set_pin_states(False, True, True, False)


def right() -> None:
    _set_pin_states(True, False, False, True)


def rotate_cw() -> None:
    right()


def rotate_ccw() -> None:
    left()
