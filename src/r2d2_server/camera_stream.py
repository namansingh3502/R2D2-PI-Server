import asyncio
import os
import shlex
from collections.abc import AsyncIterator, Sequence

DEFAULT_CAMERA_COMMAND = (
    "libcamera-vid",
    "--codec",
    "mjpeg",
    "--timeout",
    "0",
    "--width",
    "640",
    "--height",
    "480",
    "--framerate",
    "15",
    "--output",
    "-",
)
JPEG_END = b"\xff\xd9"
JPEG_START = b"\xff\xd8"


class CameraStreamError(Exception):
    """Raised when the Pi camera stream cannot be started or read."""


def camera_command() -> Sequence[str]:
    configured = os.getenv("R2D2_CAMERA_COMMAND")
    if configured:
        return shlex.split(configured)
    return DEFAULT_CAMERA_COMMAND


def extract_jpeg_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    start = buffer.find(JPEG_START)
    if start == -1:
        return None, b""

    end = buffer.find(JPEG_END, start + len(JPEG_START))
    if end == -1:
        return None, buffer[start:]

    frame_end = end + len(JPEG_END)
    return buffer[start:frame_end], buffer[frame_end:]


async def stream_camera_frames(
    command: Sequence[str] | None = None,
) -> AsyncIterator[bytes]:
    resolved_command = command or camera_command()
    if not resolved_command:
        raise CameraStreamError("Camera command is empty")

    try:
        process = await asyncio.create_subprocess_exec(
            *resolved_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        message = f"Camera command not found: {resolved_command[0]}"
        raise CameraStreamError(message) from exc

    if process.stdout is None:
        raise CameraStreamError("Camera process did not expose stdout")

    buffer = b""
    stopped_by_server = False
    try:
        while True:
            chunk = await process.stdout.read(8192)
            if not chunk:
                break

            buffer += chunk
            while True:
                frame, buffer = extract_jpeg_frame(buffer)
                if frame is None:
                    break
                yield frame
    finally:
        if process.returncode is None:
            stopped_by_server = True
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except TimeoutError:
                process.kill()
                await process.wait()

    if stopped_by_server:
        return

    stderr = b""
    if process.stderr is not None:
        stderr = await process.stderr.read()
    message = stderr.decode(errors="replace").strip()
    if process.returncode not in (0, None):
        raise CameraStreamError(message or f"Camera exited with {process.returncode}")
