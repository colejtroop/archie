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

    def test_ignores_partial_content_log_record(self) -> None:
        self.assertIsNone(parse_archie_log_line('[ArchieTelemetry] {"event_type":"STATE_UPDATED"'))

    def test_builds_script_command_request(self) -> None:
        value = json.loads(command_request("/scriptevent archie:policy_action {}", "request-1"))
        self.assertEqual(value["header"]["requestId"], "request-1")
        self.assertEqual(value["body"]["commandLine"], "scriptevent archie:policy_action {}")
