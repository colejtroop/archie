import json
import tempfile
import unittest
from pathlib import Path

from archie.vision import FrameLabels, RecordingPolicy, VisionRecorder


class VisionTests(unittest.TestCase):
    def test_recording_is_sampled_and_bounded(self) -> None:
        labels = FrameLabels({}, {}, {}, {}, None, "MOVE", None)
        with tempfile.TemporaryDirectory() as directory:
            recorder = VisionRecorder(RecordingPolicy(True, sample_every=2, max_frames=2), Path(directory))
            for _ in range(6):
                recorder.receive(b"jpeg", labels)
            rows = (Path(directory) / "samples.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(recorder.recorded, 2)
            self.assertEqual(len(rows), 2)
            self.assertEqual(json.loads(rows[0])["labels"]["current_action"], "MOVE")
            self.assertFalse(any(Path(directory).glob("*.jpg")))


if __name__ == "__main__":
    unittest.main()
