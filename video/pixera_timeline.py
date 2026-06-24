from __future__ import annotations

import asyncio
import json
from typing import Any

from server.drivers.base import BaseDriver
from server.utils.logger import get_logger

log = get_logger(__name__)


class PixeraTimelineDriver(BaseDriver):
    """Medium-scope PIXERA timeline control via JSON/TCP (dl)."""

    DRIVER_INFO = {
        "id": "pixera_timeline",
        "name": "PIXERA Timeline Controller",
        "manufacturer": "AV Stumpfl",
        "category": "video",
        "version": "0.9.0",
        "author": "CuePlot",
        "description": (
            "Medium-scope PIXERA JSON-RPC driver for timeline transport, cue, "
            "time, speed, and opacity control. Uses the JSON/TCP (dl) mode."
        ),
        "source_url": "https://help.pixera.one/api-commands",
        "tags": ["pixera", "timeline", "media-server", "json-rpc"],
        "verified": False,
        "simulated": False,
        "protocols": ["json-rpc", "json/tcp (dl)"],
        "ports": [1400],
        "transport": "tcp",
        "delimiter": "0xPX",
        "help": {
            "overview": (
                "Controls one PIXERA timeline over the official JSON-RPC API. "
                "This medium version covers transport, cue recall, timeline time, "
                "speed factor, opacity, and cue inspection."
            ),
            "setup": (
                "1. Enable the PIXERA API port on the target system\n"
                "2. Set the API mode to JSON/TCP (dl)\n"
                "3. Match the configured port in this driver (default 1400)\n"
                "4. Optionally set a timeline name; otherwise the selected or indexed timeline is used"
            ),
        },
        "default_config": {
            "host": "",
            "port": 1400,
            "timeline_name": "",
            "timeline_index": 0,
            "use_selected_timeline": True,
            "poll_interval": 1,
            "command_timeout": 5.0,
            "verify_timeout": 3.0,
        },
        "config_schema": {
            "host": {"type": "string", "required": True, "label": "IP Address"},
            "port": {"type": "integer", "default": 1400, "label": "API Port"},
            "timeline_name": {
                "type": "string",
                "default": "",
                "label": "Preferred Timeline Name",
            },
            "timeline_index": {
                "type": "integer",
                "default": 0,
                "min": 0,
                "label": "Fallback Timeline Index",
            },
            "use_selected_timeline": {
                "type": "boolean",
                "default": True,
                "label": "Prefer Selected Timeline",
            },
            "poll_interval": {
                "type": "integer",
                "default": 1,
                "min": 0,
                "label": "Poll Interval (sec)",
            },
            "command_timeout": {
                "type": "number",
                "default": 5.0,
                "min": 0.5,
                "label": "Command Timeout (sec)",
            },
            "verify_timeout": {
                "type": "number",
                "default": 3.0,
                "min": 0,
                "label": "Connect Verify Timeout (sec)",
            },
        },
        "state_variables": {
            "connected": {"type": "boolean", "label": "Connected"},
            "api_revision": {"type": "integer", "label": "API Revision"},
            "timeline_handle": {"type": "integer", "label": "Timeline Handle"},
            "timeline_name": {"type": "string", "label": "Timeline Name"},
            "timeline_fps": {"type": "number", "label": "Timeline FPS"},
            "timeline_count": {"type": "integer", "label": "Timeline Count"},
            "transport_mode": {
                "type": "enum",
                "values": ["unknown", "play", "pause", "stop"],
                "label": "Transport Mode",
            },
            "transport_mode_code": {"type": "integer", "label": "Transport Mode Code"},
            "current_time_frames": {"type": "integer", "label": "Current Time (frames)"},
            "current_hmsf": {"type": "string", "label": "Current HMSF"},
            "speed_factor": {"type": "number", "label": "Speed Factor"},
            "opacity": {"type": "number", "label": "Opacity"},
            "cue_count": {"type": "integer", "label": "Cue Count"},
            "active_cue_name": {"type": "string", "label": "Active Cue Name"},
            "active_cue_number": {"type": "string", "label": "Active Cue Number"},
            "next_cue_name": {"type": "string", "label": "Next Cue Name"},
            "next_cue_number": {"type": "string", "label": "Next Cue Number"},
            "previous_cue_name": {"type": "string", "label": "Previous Cue Name"},
            "previous_cue_number": {"type": "string", "label": "Previous Cue Number"},
            "available_timelines": {"type": "string", "label": "Available Timelines"},
            "available_cues": {"type": "string", "label": "Available Cues"},
            "last_error": {"type": "string", "label": "Last Error"},
            "last_rpc_method": {"type": "string", "label": "Last RPC Method"},
        },
        "commands": {
            "play": {"label": "Play", "params": {}},
            "pause": {"label": "Pause", "params": {}},
            "stop": {"label": "Stop", "params": {}},
            "set_transport_mode": {
                "label": "Set Transport Mode",
                "params": {
                    "mode": {
                        "type": "string",
                        "required": True,
                        "help": "play, pause, stop or 1, 2, 3",
                    }
                },
            },
            "set_current_time": {
                "label": "Set Current Time",
                "params": {
                    "time": {"type": "integer", "required": True, "help": "Frame position"}
                },
            },
            "scrub_current_time": {
                "label": "Scrub Current Time",
                "params": {
                    "frames": {"type": "integer", "required": True, "help": "Relative frame delta"}
                },
            },
            "blend_to_time": {
                "label": "Blend To Time",
                "params": {
                    "goal_time": {"type": "number", "required": True, "help": "Target frame position"},
                    "blend_duration": {"type": "number", "required": True, "help": "Blend duration in seconds"},
                    "transport_mode": {"type": "string", "required": False, "help": "Optional: play, pause, stop or 1, 2, 3"},
                },
            },
            "apply_cue_name": {
                "label": "Apply Cue By Name",
                "params": {
                    "name": {"type": "string", "required": True},
                    "blend_duration": {"type": "number", "required": False},
                },
            },
            "apply_cue_number_string": {
                "label": "Apply Cue By Number",
                "params": {
                    "number_string": {"type": "string", "required": True, "help": "Format: Main.Sub.Detail"},
                    "blend_duration": {"type": "number", "required": False},
                },
            },
            "next_cue": {"label": "Move To Next Cue", "params": {}},
            "previous_cue": {"label": "Move To Previous Cue", "params": {}},
            "set_speed_factor": {
                "label": "Set Speed Factor",
                "params": {"factor": {"type": "number", "required": True}},
            },
            "set_opacity": {
                "label": "Set Opacity",
                "params": {"value": {"type": "number", "required": True, "help": "0.0 to 1.0"}},
            },
            "refresh": {"label": "Refresh Status", "params": {}},
            "reload_cue_cache": {"label": "Reload Cue Cache", "params": {}},
        },
    }

    TRANSPORT_MODE_MAP = {1: "play", 2: "pause", 3: "stop"}
    TRANSPORT_MODE_REVERSE = {
        "play": 1,
        "1": 1,
        1: 1,
        "pause": 2,
        "2": 2,
        2: 2,
        "stop": 3,
        "3": 3,
        3: 3,
    }

    def __init__(
        self,
        device_id: str,
        config: dict[str, Any],
        state: "StateStore",
        events: "EventBus",
    ):
        self._request_lock = asyncio.Lock()
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._next_request_id = 1
        self._timeline_handle: int | None = None
        self._cue_cache: list[dict[str, Any]] = []
        super().__init__(device_id, config, state, events)

    async def _post_connect(self) -> None:
        try:
            await self._rpc("Pixera.Utility.setShowContextInReplies", {"doShow": False})
        except Exception:
            log.debug("[%s] setShowContextInReplies not accepted", self.device_id, exc_info=True)
        api_revision = await self._rpc("Pixera.Utility.getApiRevision")
        self.set_state("api_revision", int(api_revision or 0))
        await self._resolve_timeline_context()
        await self._reload_cue_cache()
        await self._refresh_runtime_state()
        self.set_state("last_error", "")

    async def disconnect(self) -> None:
        self._fail_pending_requests(ConnectionError("Driver disconnected"))
        await super().disconnect()

    def _handle_transport_disconnect(self) -> None:
        self._fail_pending_requests(ConnectionError("Transport disconnected"))
        super()._handle_transport_disconnect()

    async def on_data_received(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace").strip()
        if not text:
            return
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            log.warning("[%s] Invalid PIXERA JSON payload: %r", self.device_id, text[:400])
            self.set_state("last_error", "Invalid JSON payload from PIXERA")
            return

        if isinstance(payload, list):
            for item in payload:
                self._handle_rpc_message(item)
            return
        self._handle_rpc_message(payload)

    def _handle_rpc_message(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        msg_id = payload.get("id")
        if isinstance(msg_id, int):
            fut = self._pending_requests.pop(msg_id, None)
            if fut is not None and not fut.done():
                fut.set_result(payload)
                return

    def _fail_pending_requests(self, exc: Exception) -> None:
        for fut in list(self._pending_requests.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending_requests.clear()

    async def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        if not self.transport or not getattr(self.transport, "connected", False):
            raise ConnectionError("PIXERA transport is not connected")

        async with self._request_lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            loop = asyncio.get_running_loop()
            future: asyncio.Future = loop.create_future()
            self._pending_requests[request_id] = future
            request: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }
            if params:
                request["params"] = params
            payload = json.dumps(request, separators=(",", ":")).encode("utf-8") + b"0xPX"
            try:
                await self.transport.send(payload)
                reply = await asyncio.wait_for(
                    future,
                    timeout=float(timeout or self.config.get("command_timeout", 5.0) or 5.0),
                )
            except Exception:
                self._pending_requests.pop(request_id, None)
                raise

        self.set_state("last_rpc_method", method)
        error = reply.get("error")
        if error:
            message = self._format_rpc_error(error)
            self.set_state("last_error", message)
            raise RuntimeError(message)
        return reply.get("result")

    @staticmethod
    def _format_rpc_error(error: Any) -> str:
        if isinstance(error, dict):
            code = error.get("code", "?")
            message = error.get("message", "Unknown PIXERA error")
            return f"PIXERA RPC error {code}: {message}"
        return f"PIXERA RPC error: {error}"

    async def _resolve_timeline_context(self) -> None:
        timeline_names = await self._rpc("Pixera.Timelines.getTimelineNames")
        timeline_names = timeline_names or []
        self.set_state("timeline_count", len(timeline_names))
        self.set_state("available_timelines", json.dumps(timeline_names, ensure_ascii=True))

        handle: int | None = None
        preferred_name = str(self.config.get("timeline_name", "") or "").strip()
        if preferred_name:
            try:
                result = await self._rpc(
                    "Pixera.Timelines.getTimelineFromName",
                    {"name": preferred_name},
                )
                if isinstance(result, int) and result > 0:
                    handle = result
            except Exception:
                log.warning(
                    "[%s] Preferred PIXERA timeline '%s' not resolved",
                    self.device_id,
                    preferred_name,
                    exc_info=True,
                )

        if handle is None and bool(self.config.get("use_selected_timeline", True)):
            try:
                selected = await self._rpc("Pixera.Timelines.getTimelinesSelected")
                if isinstance(selected, list) and selected:
                    first = selected[0]
                    if isinstance(first, int) and first > 0:
                        handle = first
            except Exception:
                log.debug("[%s] No selected PIXERA timeline available", self.device_id, exc_info=True)

        if handle is None:
            timeline_index = int(self.config.get("timeline_index", 0) or 0)
            handle = await self._rpc(
                "Pixera.Timelines.getTimelineAtIndex",
                {"index": timeline_index},
            )

        if not isinstance(handle, int) or handle <= 0:
            raise ConnectionError("No usable PIXERA timeline could be resolved")

        self._timeline_handle = handle
        self.set_state("timeline_handle", handle)
        timeline_name = await self._rpc("Pixera.Timelines.Timeline.getName", {"handle": handle})
        self.set_state("timeline_name", str(timeline_name or preferred_name or ""))

    async def _timeline_call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self._timeline_handle:
            await self._resolve_timeline_context()
        payload = {"handle": self._timeline_handle}
        if params:
            payload.update(params)
        return await self._rpc(method, payload)

    async def _reload_cue_cache(self) -> list[dict[str, Any]]:
        cue_names = await self._timeline_call("Pixera.Timelines.Timeline.getCueNames")
        cue_names = cue_names or []
        cues: list[dict[str, Any]] = []
        for index in range(len(cue_names)):
            handle = await self._timeline_call(
                "Pixera.Timelines.Timeline.getCueAtIndex",
                {"index": index},
            )
            if not isinstance(handle, int) or handle <= 0:
                continue
            attrs = await self._rpc("Pixera.Timelines.Cue.getAttributes", {"handle": handle})
            if not isinstance(attrs, dict):
                attrs = {}
            cue_name = str(attrs.get("name") or cue_names[index] or "")
            number_formatted = str(attrs.get("numberFormatted") or "")
            cue_time = float(attrs.get("time", 0.0) or 0.0)
            cues.append(
                {
                    "handle": handle,
                    "index": int(attrs.get("index", index) or index),
                    "name": cue_name,
                    "number": number_formatted,
                    "time": cue_time,
                }
            )

        cues.sort(key=lambda item: (item["time"], item["index"]))
        self._cue_cache = cues
        self.set_state("cue_count", len(cues))
        self.set_state(
            "available_cues",
            json.dumps(
                [
                    {
                        "index": cue["index"],
                        "name": cue["name"],
                        "number": cue["number"],
                        "time": cue["time"],
                    }
                    for cue in cues
                ],
                ensure_ascii=True,
            ),
        )
        return cues

    def _find_active_cue(self, current_time: int) -> dict[str, Any] | None:
        active: dict[str, Any] | None = None
        for cue in self._cue_cache:
            if cue["time"] <= current_time:
                active = cue
            else:
                break
        return active

    def _find_adjacent_cues(self, current_time: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        previous_cue: dict[str, Any] | None = None
        next_cue: dict[str, Any] | None = None
        for cue in self._cue_cache:
            if cue["time"] <= current_time:
                previous_cue = cue
                continue
            next_cue = cue
            break
        return previous_cue, next_cue

    async def _refresh_runtime_state(self) -> dict[str, Any]:
        timeline_name = await self._timeline_call("Pixera.Timelines.Timeline.getName")
        fps = await self._timeline_call("Pixera.Timelines.Timeline.getFps")
        current_time = await self._timeline_call("Pixera.Timelines.Timeline.getCurrentTime")
        current_hmsf = await self._timeline_call("Pixera.Timelines.Timeline.getCurrentHMSF")
        transport_mode_code = await self._timeline_call("Pixera.Timelines.Timeline.getTransportMode")
        speed_factor = await self._timeline_call("Pixera.Timelines.Timeline.getSpeedFactor")
        opacity = await self._timeline_call("Pixera.Timelines.Timeline.getOpacity")

        current_time_i = int(current_time or 0)
        previous_cue, next_cue = self._find_adjacent_cues(current_time_i)
        active_cue = self._find_active_cue(current_time_i)

        updates = {
            "timeline_name": str(timeline_name or ""),
            "timeline_fps": float(fps or 0.0),
            "current_time_frames": current_time_i,
            "current_hmsf": str(current_hmsf or ""),
            "transport_mode_code": int(transport_mode_code or 0),
            "transport_mode": self.TRANSPORT_MODE_MAP.get(int(transport_mode_code or 0), "unknown"),
            "speed_factor": float(speed_factor or 0.0),
            "opacity": float(opacity or 0.0),
            "active_cue_name": active_cue["name"] if active_cue else "",
            "active_cue_number": active_cue["number"] if active_cue else "",
            "previous_cue_name": previous_cue["name"] if previous_cue else "",
            "previous_cue_number": previous_cue["number"] if previous_cue else "",
            "next_cue_name": next_cue["name"] if next_cue else "",
            "next_cue_number": next_cue["number"] if next_cue else "",
            "last_error": "",
        }
        self.set_states(updates)
        return updates

    def _coerce_transport_mode(self, raw: Any) -> int:
        key = raw
        if isinstance(raw, str):
            key = raw.strip().lower()
        mode = self.TRANSPORT_MODE_REVERSE.get(key)
        if mode is None:
            raise ValueError("mode must be play, pause, stop or 1, 2, 3")
        return mode

    async def send_command(self, command: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        try:
            if command == "play":
                await self._timeline_call("Pixera.Timelines.Timeline.play")
            elif command == "pause":
                await self._timeline_call("Pixera.Timelines.Timeline.pause")
            elif command == "stop":
                await self._timeline_call("Pixera.Timelines.Timeline.stop")
            elif command == "set_transport_mode":
                mode = self._coerce_transport_mode(params.get("mode"))
                await self._timeline_call("Pixera.Timelines.Timeline.setTransportMode", {"mode": mode})
            elif command == "set_current_time":
                await self._timeline_call(
                    "Pixera.Timelines.Timeline.setCurrentTime",
                    {"time": int(params.get("time", 0))},
                )
            elif command == "scrub_current_time":
                await self._timeline_call(
                    "Pixera.Timelines.Timeline.scrubCurrentTime",
                    {"frames": int(params.get("frames", 0))},
                )
            elif command == "blend_to_time":
                goal_time = float(params.get("goal_time", 0.0))
                blend_duration = float(params.get("blend_duration", 0.0))
                raw_mode = params.get("transport_mode")
                if raw_mode not in (None, ""):
                    mode = self._coerce_transport_mode(raw_mode)
                    await self._timeline_call(
                        "Pixera.Timelines.Timeline.blendToTimeWithTransportMode",
                        {
                            "goalTime": goal_time,
                            "blendDuration": blend_duration,
                            "transportMode": mode,
                        },
                    )
                else:
                    await self._timeline_call(
                        "Pixera.Timelines.Timeline.blendToTime",
                        {"goalTime": goal_time, "blendDuration": blend_duration},
                    )
            elif command == "apply_cue_name":
                payload = {"name": str(params.get("name", ""))}
                if params.get("blend_duration") not in (None, ""):
                    payload["blendDuration"] = float(params["blend_duration"])
                await self._timeline_call("Pixera.Timelines.Timeline.applyCueWithName", payload)
            elif command == "apply_cue_number_string":
                payload = {"numberString": str(params.get("number_string", ""))}
                if params.get("blend_duration") not in (None, ""):
                    payload["blendDuration"] = float(params["blend_duration"])
                await self._timeline_call(
                    "Pixera.Timelines.Timeline.applyCueWithNumberString",
                    payload,
                )
            elif command == "next_cue":
                await self._timeline_call("Pixera.Timelines.Timeline.moveToNextCue")
            elif command == "previous_cue":
                await self._timeline_call("Pixera.Timelines.Timeline.moveToPreviousCue")
            elif command == "set_speed_factor":
                await self._timeline_call(
                    "Pixera.Timelines.Timeline.setSpeedFactor",
                    {"factor": float(params.get("factor", 1.0))},
                )
            elif command == "set_opacity":
                value = float(params.get("value", 1.0))
                if value < 0.0 or value > 1.0:
                    raise ValueError("opacity must be between 0.0 and 1.0")
                await self._timeline_call("Pixera.Timelines.Timeline.setOpacity", {"value": value})
            elif command == "reload_cue_cache":
                await self._reload_cue_cache()
            elif command == "refresh":
                pass
            else:
                raise ValueError(f"Unknown PIXERA command: {command}")

            if command in {"reload_cue_cache", "apply_cue_name", "apply_cue_number_string"}:
                await self._reload_cue_cache()
            return await self._refresh_runtime_state()
        except Exception as exc:
            self.set_state("last_error", str(exc))
            raise

    async def poll(self) -> None:
        await self._refresh_runtime_state()
