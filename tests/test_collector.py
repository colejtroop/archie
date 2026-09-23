import json
import tempfile
import unittest
from pathlib import Path

from archie.collector import TrajectoryWriter, import_episode, latest_complete_episode
from archie.telemetry import EventType, Telemetry


class TrajectoryWriterTests(unittest.TestCase):
    def test_writes_sequenced_episode_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.jsonl"
            telemetry = Telemetry(sink=TrajectoryWriter(path))
            telemetry.publish(EventType.EPISODE_STARTED, blueprint="3x3-wall")
            telemetry.publish(EventType.OBJECTIVE_SELECTED, target={"x": 1, "y": 2, "z": 3})
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["sequence"] for record in records], [1, 2])
            self.assertEqual({record["episode"] for record in records}, {1})
            self.assertEqual(records[0]["schema_version"], 1)

    def test_imports_latest_complete_content_log_episode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "ContentLog.txt"
            log.write_text(
                '\n'.join((
                    '00:00[Scripting][inform]-[ArchieTelemetry] {"event_type":"EPISODE_STARTED","payload":{"run":1}}',
                    '00:01[Scripting][inform]-[ArchieTelemetry] {"event_type":"EPISODE_FAILED","payload":{}}',
                    '00:02[Scripting][inform]-[ArchieTelemetry] {"event_type":"EPISODE_STARTED","payload":{"run":2}}',
                    '00:03[Scripting][inform]-[ArchieTelemetry] {"event_type":"OBJECTIVE_SELECTED","payload":{"policy_action":0}}',
                    '00:04[Scripting][inform]-[ArchieTelemetry] {"event_type":"EPISODE_COMPLETED","payload":{"correct_blocks":9}}',
                )),
                encoding="utf-8",
            )
            episode = latest_complete_episode(log)
            self.assertEqual(episode[0][1]["run"], 2)
            output = root / "episode.jsonl"
            self.assertEqual(import_episode(log, output), 3)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[-1]["event_type"], "EPISODE_COMPLETED")
            self.assertEqual(records[-1]["payload"]["correct_blocks"], 9)
