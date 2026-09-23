from __future__ import annotations

import base64
import hashlib
import json
import re
import socket
import struct
from pathlib import Path
from threading import Event as ThreadEvent, Thread
from time import sleep
from typing import Any
from uuid import uuid4

from .telemetry import EventType, Telemetry


ARCHIE_MESSAGE = re.compile(r"(?:§[0-9a-fk-or])*\[Archie\](?:§[0-9a-fk-or])*\s*(\{.*\})", re.IGNORECASE)
ARCHIE_LOG = re.compile(r"\[ArchieTelemetry\]\s*(\{.*\})")
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _parse_match(match: re.Match[str] | None) -> tuple[EventType, dict[str, Any]] | None:
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
        event_type = EventType(value["event_type"])
        payload = dict(value.get("payload", {}))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if "timestamp_ticks" in value:
        payload["bedrock_tick"] = value["timestamp_ticks"]
    return event_type, payload


def parse_archie_message(message: str) -> tuple[EventType, dict[str, Any]] | None:
    return _parse_match(ARCHIE_MESSAGE.search(message))


def parse_archie_log_line(line: str) -> tuple[EventType, dict[str, Any]] | None:
    return _parse_match(ARCHIE_LOG.search(line))


class ContentLogBridge:
    """Tails Preview's content log without exposing telemetry in player chat."""

    def __init__(self, telemetry: Telemetry, directory: Path, poll_seconds: float = 0.1) -> None:
        self.telemetry = telemetry
        self.directory = directory
        self.poll_seconds = poll_seconds
        self._stop = ThreadEvent()

    def start(self) -> None:
        Thread(target=self._run, daemon=True, name="archie-content-log-bridge").start()

    def stop(self) -> None:
        self._stop.set()

    def _latest(self) -> Path | None:
        files = list(self.directory.glob("ContentLog*.txt"))
        return max(files, key=lambda path: path.stat().st_mtime_ns) if files else None

    def _run(self) -> None:
        current: Path | None = None
        position = 0
        pending = ""
        while not self._stop.is_set():
            latest = self._latest()
            if latest is None:
                sleep(self.poll_seconds)
                continue
            if latest != current:
                current = latest
                position = current.stat().st_size
                pending = ""
            with current.open("rb") as stream:
                stream.seek(position)
                chunk = stream.read()
                position = stream.tell()
            if chunk:
                text = pending + chunk.decode("utf-8", errors="replace")
                lines = text.split("\n")
                pending = lines.pop()
                for line in lines:
                    parsed = parse_archie_log_line(line)
                    if parsed:
                        self.telemetry.publish(parsed[0], **parsed[1])
            sleep(self.poll_seconds)


def _read_exact(connection: socket.socket, length: int) -> bytes:
    data = bytearray()
    while len(data) < length:
        chunk = connection.recv(length - len(data))
        if not chunk:
            raise ConnectionError("WebSocket closed")
        data.extend(chunk)
    return bytes(data)


def _send_frame(connection: socket.socket, payload: bytes, opcode: int = 1) -> None:
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65_536:
        header.extend((126, *struct.pack("!H", length)))
    else:
        header.extend((127, *struct.pack("!Q", length)))
    connection.sendall(header + payload)


def _receive_frame(connection: socket.socket) -> tuple[int, bytes]:
    first, second = _read_exact(connection, 2)
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _read_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _read_exact(connection, 8))[0]
    mask = _read_exact(connection, 4) if second & 0x80 else None
    payload = bytearray(_read_exact(connection, length))
    if mask:
        for index in range(length):
            payload[index] ^= mask[index % 4]
    return opcode, bytes(payload)


class BedrockBridge:
    """Receives Bedrock PlayerMessage events through the local /connect channel."""

    def __init__(self, telemetry: Telemetry, host: str = "127.0.0.1", port: int = 19131) -> None:
        self.telemetry = telemetry
        self.host = host
        self.port = port
        self.connected = False
        self._stop = ThreadEvent()
        self._socket: socket.socket | None = None

    def start(self) -> None:
        Thread(target=self._serve, daemon=True, name="archie-bedrock-bridge").start()

    def stop(self) -> None:
        self._stop.set()
        if self._socket:
            self._socket.close()

    def _serve(self) -> None:
        with socket.socket() as server:
            self._socket = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(1)
            while not self._stop.is_set():
                try:
                    connection, _ = server.accept()
                    with connection:
                        self._handle(connection)
                except (ConnectionError, OSError, ValueError, json.JSONDecodeError):
                    self.connected = False

    def _handle(self, connection: socket.socket) -> None:
        request = bytearray()
        while b"\r\n\r\n" not in request:
            request.extend(connection.recv(4096))
        headers = request.decode("latin-1").split("\r\n")
        key = next(line.split(":", 1)[1].strip() for line in headers if line.lower().startswith("sec-websocket-key:"))
        accept = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode()).digest()).decode()
        connection.sendall(
            ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode()
        )
        self.connected = True
        subscription = {
            "header": {
                "version": 1,
                "requestId": str(uuid4()),
                "messageType": "commandRequest",
                "messagePurpose": "subscribe",
            },
            "body": {"eventName": "PlayerMessage"},
        }
        _send_frame(connection, json.dumps(subscription).encode())
        while not self._stop.is_set():
            opcode, payload = _receive_frame(connection)
            if opcode == 8:
                _send_frame(connection, payload, opcode=8)
                return
            if opcode == 9:
                _send_frame(connection, payload, opcode=10)
                continue
            if opcode != 1:
                continue
            message = json.loads(payload)
            if message.get("header", {}).get("messagePurpose") != "event":
                continue
            parsed = parse_archie_message(str(message.get("body", {}).get("message", "")))
            if parsed:
                self.telemetry.publish(parsed[0], **parsed[1])
