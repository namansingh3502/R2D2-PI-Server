from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from r2d2_server import motor_controller
from r2d2_server.logging_config import configure_logging

Direction = Literal[
    "forward",
    "backward",
    "left",
    "right",
    "rotate_cw",
    "rotate_ccw",
    "stop",
]

logger = configure_logging()
MovementResponse = dict[str, str | bool | None]


@dataclass
class RobotController:
    current_direction: Direction = "stop"
    command_history: list[dict[str, str]] = field(default_factory=list)

    def forward(self) -> MovementResponse:
        return self._execute_motor("forward", motor_controller.forward)

    def backward(self) -> MovementResponse:
        return self._execute_motor("backward", motor_controller.backward)

    def left(self) -> MovementResponse:
        return self._execute_motor("left", motor_controller.left)

    def right(self) -> MovementResponse:
        return self._execute_motor("right", motor_controller.right)

    def rotate_cw(self) -> MovementResponse:
        return self._execute_motor("rotate_cw", motor_controller.rotate_cw)

    def rotate_ccw(self) -> MovementResponse:
        return self._execute_motor("rotate_ccw", motor_controller.rotate_ccw)

    def stop(self) -> MovementResponse:
        return self._execute_motor("stop", motor_controller.stop)

    def execute(self, direction: Direction) -> MovementResponse:
        handlers = {
            "forward": self.forward,
            "backward": self.backward,
            "left": self.left,
            "right": self.right,
            "rotate_cw": self.rotate_cw,
            "rotate_ccw": self.rotate_ccw,
            "stop": self.stop,
        }
        return handlers[direction]()

    def _execute_motor(
        self,
        direction: Direction,
        action: Callable[[], None],
    ) -> MovementResponse:
        try:
            action()
        except motor_controller.MotorControllerError as exc:
            logger.error(
                "movement_command direction=%s status=error error=%s",
                direction,
                exc,
            )
            return self._record(direction, "error", str(exc))

        if not motor_controller.is_available():
            logger.warning(
                "movement_command direction=%s status=inactive "
                "reason=motor_unavailable",
                direction,
            )
            return self._record(
                direction,
                "inactive",
                motor_controller.get_status()["error"],
            )

        return self._record(direction, "accepted", None)

    def _record(
        self,
        direction: Direction,
        status: str,
        error: str | None,
    ) -> MovementResponse:
        self.current_direction = direction if status == "accepted" else "stop"
        entry = {
            "direction": direction,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.command_history.append(entry)
        logger.info("movement_command direction=%s status=%s", direction, status)
        return {
            "direction": direction,
            "status": status,
            "timestamp": entry["timestamp"],
            "motor_available": motor_controller.is_available(),
            "motor_error": error,
        }
