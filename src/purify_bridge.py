"""持久 NDJSON 子进程桥：Python 机器人闭环 ↔ 公开 Go reference core。"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from v4_claims import canonical_json


COMMAND_SCHEMA = "purify.robotics.command.v1"
RESPONSE_SCHEMA = "purify.robotics.response.v1"


class PurifyBridgeError(RuntimeError):
    """桥接层的稳定基类错误。"""


class PurifyBridgeTimeout(PurifyBridgeError):
    pass


class PurifyBridgeProtocolError(PurifyBridgeError):
    pass


class PurifyCoreError(PurifyBridgeError):
    def __init__(self, request_id: str, error: Any) -> None:
        self.request_id = request_id
        self.error = error
        super().__init__(f"Purify core rejected {request_id}: {canonical_json(error)}")


def _to_wire(value: Any) -> Any:
    method = getattr(value, "to_wire", None)
    return method() if callable(method) else value


class PurifyBridge:
    """顺序、持久且 fail-closed 的 NDJSON client。

    一个 bridge 同时只允许一个 in-flight command，避免将响应错误配对。超时、
    非法 JSON 或 request_id 不匹配都会终止子进程；调用方必须显式新建 bridge，
    不会在动作准入期间悄悄重启并丢失故障信息。
    """

    def __init__(
        self,
        command: Sequence[str | os.PathLike[str]] | None = None,
        *,
        timeout_seconds: float = 2.0,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be positive")
        if command is None:
            root = Path(__file__).resolve().parents[1]
            command = (root / "purify_robotics" / "bin" / "purify-robotics-core",)
        if not command:
            raise ValueError("command cannot be empty")
        self._command = tuple(str(item) for item in command)
        self._timeout_seconds = float(timeout_seconds)
        self._cwd = cwd
        self._env = dict(env) if env is not None else None
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=50)
        self._lock = threading.Lock()
        self._counter = 0
        self._closed = False

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr)

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def start(self) -> None:
        if self._closed:
            raise PurifyBridgeError("bridge is closed")
        if self._process is not None:
            if self._process.poll() is None:
                return
            raise PurifyBridgeError(
                f"Purify core already exited with code {self._process.returncode}"
            )
        try:
            self._process = subprocess.Popen(
                self._command,
                cwd=self._cwd,
                env=self._env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="strict",
                bufsize=1,
            )
        except OSError as exc:
            raise PurifyBridgeError(
                f"failed to start Purify core {self._command[0]}: {exc}"
            ) from exc
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._responses.put(("line", line.rstrip("\r\n")))
        finally:
            return_code = self._process.wait()
            self._responses.put(("eof", return_code))

    def _read_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr.append(line.rstrip("\r\n"))

    def _abort(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=0.5)

    def request(self, op: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not op:
            raise ValueError("op must be non-empty")
        with self._lock:
            self.start()
            assert self._process is not None and self._process.stdin is not None
            self._counter += 1
            request_id = f"py-{self._counter:08d}"
            command = {
                "schema_version": COMMAND_SCHEMA,
                "request_id": request_id,
                "op": op,
                "payload": dict(payload),
            }
            try:
                self._process.stdin.write(canonical_json(command) + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._abort()
                raise PurifyBridgeError(
                    f"Purify core pipe failed for {request_id}: {exc}"
                ) from exc

            try:
                kind, item = self._responses.get(timeout=self._timeout_seconds)
            except queue.Empty as exc:
                self._abort()
                raise PurifyBridgeTimeout(
                    f"Purify core timed out for {request_id} after "
                    f"{self._timeout_seconds:.3f}s"
                ) from exc
            if kind == "eof":
                stderr = " | ".join(self.stderr_tail)
                raise PurifyBridgeError(
                    f"Purify core exited before {request_id} with code {item}"
                    + (f": {stderr}" if stderr else "")
                )
            try:
                response = json.loads(item)
            except (TypeError, json.JSONDecodeError) as exc:
                self._abort()
                raise PurifyBridgeProtocolError(
                    f"invalid JSON response for {request_id}"
                ) from exc
            if not isinstance(response, dict):
                self._abort()
                raise PurifyBridgeProtocolError(
                    f"response for {request_id} must be an object"
                )
            if response.get("schema_version") != RESPONSE_SCHEMA:
                self._abort()
                raise PurifyBridgeProtocolError(
                    f"response schema mismatch for {request_id}"
                )
            if response.get("request_id") != request_id:
                self._abort()
                raise PurifyBridgeProtocolError(
                    f"response request_id mismatch for {request_id}"
                )
            if response.get("ok") is not True:
                raise PurifyCoreError(request_id, response.get("error"))
            result = response.get("result")
            if not isinstance(result, dict):
                raise PurifyBridgeProtocolError(
                    f"successful result for {request_id} must be an object"
                )
            return result

    def evaluate_action(
        self,
        *,
        claims: Iterable[Any],
        contract: Any,
        calibration: Any,
        current_step: int,
        profile: str,
        noise_intensity: float,
        sensor_version: str,
    ) -> dict[str, Any]:
        return self.request(
            "evaluate_action",
            {
                "claims": [_to_wire(claim) for claim in claims],
                "contract": _to_wire(contract),
                "calibration": _to_wire(calibration),
                "context": {
                    "current_step": current_step,
                    "profile": profile,
                    "noise_intensity": noise_intensity,
                    "sensor_version": sensor_version,
                },
            },
        )

    def invalidate_plan(
        self,
        *,
        previous_receipt: Any,
        current_step: int,
        triggering_claims: Iterable[Any],
    ) -> dict[str, Any]:
        return self.request(
            "invalidate_plan",
            {
                "previous_receipt": _to_wire(previous_receipt),
                "current_step": current_step,
                "triggering_claims": [_to_wire(claim) for claim in triggering_claims],
            },
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._abort()
        process = self._process
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    def __enter__(self) -> "PurifyBridge":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


__all__ = (
    "PurifyBridge",
    "PurifyBridgeError",
    "PurifyBridgeProtocolError",
    "PurifyBridgeTimeout",
    "PurifyCoreError",
)
