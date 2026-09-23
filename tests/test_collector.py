import json
import tempfile
import unittest
from pathlib import Path

from archie.collector import TrajectoryWriter
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
