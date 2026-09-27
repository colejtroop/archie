import json
import unittest

from archie.bedrock_bridge import command_request, parse_archie_log_line, parse_archie_message
from archie.telemetry import EventType


class BedrockBridgeTests(unittest.TestCase):
    def test_parses_colored_archie_message(self) -> None:
        value = {"event_type": "EPISODE_COMPLETED", "timestamp_ticks": 42, "payload": {"exact_completion": True}}
        parsed = parse_archie_message(f"§5[Archie]§r {json.dumps(value)}")
        self.assertEqual(parsed, (EventType.EPISODE_COMPLETED, {"exact_completion": True, "bedrock_tick": 42}))

    def test_ignores_other_chat(self) -> None:
        self.assertIsNone(parse_archie_message("hello"))

    def test_parses_content_log_telemetry(self) -> None:
        value = {"event_type": "STATE_UPDATED", "timestamp_ticks": 72, "payload": {"correct": 4}}
        parsed = parse_archie_log_line(f"[Scripting][inform]-[ArchieTelemetry] {json.dumps(value)}")
        self.assertEqual(parsed, (EventType.STATE_UPDATED, {"correct": 4, "bedrock_tick": 72}))

    def test_parses_live_model_activation_telemetry(self) -> None:
        payload = {
            "model": "objective-selector-v0",
            "hidden_1": {"active": 61, "peak": 1.25, "top": [[17, 1.25]]},
            "hidden_2": {"active": 29, "peak": 0.75, "top": [[4, 0.75]]},
            "selected_action": 2,
        }
        value = {"event_type": "MODEL_INFERENCE", "timestamp_ticks": 80, "payload": payload}
        parsed = parse_archie_log_line(f"[ArchieTelemetry] {json.dumps(value)}")
        self.assertEqual(parsed, (EventType.MODEL_INFERENCE, {**payload, "bedrock_tick": 80}))

    def test_ignores_partial_content_log_record(self) -> None:
        self.assertIsNone(parse_archie_log_line('[ArchieTelemetry] {"event_type":"STATE_UPDATED"'))

    def test_builds_script_command_request(self) -> None:
        value = json.loads(command_request("/scriptevent archie:policy_action {}", "request-1"))
        self.assertEqual(value["header"]["requestId"], "request-1")
        self.assertEqual(value["body"]["commandLine"], "scriptevent archie:policy_action {}")
