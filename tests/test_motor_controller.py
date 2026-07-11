from collections.abc import Callable

from r2d2_server import motor_controller


class FakeOutputDevice:
    def __init__(self) -> None:
        self.enabled = False

    def on(self) -> None:
        self.enabled = True

    def off(self) -> None:
        self.enabled = False


def set_fake_outputs() -> list[FakeOutputDevice]:
    devices = [FakeOutputDevice() for _ in range(4)]
    motor_controller.IN1 = devices[0]
    motor_controller.IN2 = devices[1]
    motor_controller.IN3 = devices[2]
    motor_controller.IN4 = devices[3]
    return devices


def assert_pin_state(
    action: Callable[[], None],
    expected: tuple[bool, bool, bool, bool],
) -> None:
    devices = set_fake_outputs()

    action()

    assert tuple(device.enabled for device in devices) == expected


def test_forward_pin_state() -> None:
    assert_pin_state(motor_controller.forward, (True, False, True, False))


def test_backward_pin_state() -> None:
    assert_pin_state(motor_controller.backward, (False, True, False, True))


def test_left_pin_state() -> None:
    assert_pin_state(motor_controller.left, (False, True, True, False))


def test_right_pin_state() -> None:
    assert_pin_state(motor_controller.right, (True, False, False, True))


def test_stop_pin_state() -> None:
    assert_pin_state(motor_controller.stop, (False, False, False, False))
