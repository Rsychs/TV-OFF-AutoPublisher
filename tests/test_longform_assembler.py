import importlib.util
import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).parents[1] / "longform" / "assemble_longform.py"
spec = importlib.util.spec_from_file_location("assemble_longform", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class LongformValidationTests(unittest.TestCase):
    def make_section(self, root, name, seed, sha):
        folder = root / name
        folder.mkdir()
        audio = folder / "section.wav"
        audio.write_bytes(b"fake audio")
        (folder / "ace_step_smoke_result.json").write_text(
            __import__("json").dumps({
                "status":"ok","provider":"ACE-Step-1.5","publishing_enabled":True,
                "instrumental":True,"audio_file":"section.wav","sha256":sha,
                "duration_seconds":180,"seed":seed,"title":name,"style":"Jazz"
            }), encoding="utf-8")
        return audio

    @patch.object(mod, "duration", return_value=180.0)
    @patch.object(mod, "digest", return_value="a"*64)
    def test_rejects_duplicate_audio_hash(self, _digest, _duration):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_section(root,"section-01","101","a"*64)
            self.make_section(root,"section-02","202","a"*64)
            with self.assertRaisesRegex(RuntimeError,"Duplicate section"):
                mod.read_sections(root)

    @patch.object(mod, "duration", return_value=180.0)
    @patch.object(mod, "digest", side_effect=["a"*64,"b"*64])
    def test_rejects_reused_seed(self, _digest, _duration):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_section(root,"section-01","101","a"*64)
            self.make_section(root,"section-02","101","b"*64)
            with self.assertRaisesRegex(RuntimeError,"Repeated ACE-Step seed"):
                mod.read_sections(root)

    def test_duration_choices_are_restricted(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                mod.assemble(Path(d),Path(d)/"out.m4a",2)

if __name__=="__main__":
    unittest.main()

PLAN = Path(__file__).parents[1] / "longform" / "section_plan.py"
plan_spec = importlib.util.spec_from_file_location("section_plan", PLAN)
plan = importlib.util.module_from_spec(plan_spec)
plan_spec.loader.exec_module(plan)

class SectionPlanTests(unittest.TestCase):
    def test_required_section_counts_cover_each_target(self):
        expected = {1: 18, 3: 54, 8: 143, 10: 179}
        for hours, count in expected.items():
            self.assertEqual(plan.required_sections(hours), count)

    def test_title_labels_remain_unique_for_ten_hour_mix(self):
        titles = {"Jazz": [f"Jazz {i}" for i in range(12)]}
        used = set()
        generated = [plan.unique_title("Jazz", used, i, titles) for i in range(60)]
        self.assertEqual(len(generated), len(set(generated)))

    def test_rejects_unsupported_duration(self):
        with self.assertRaises(ValueError):
            plan.required_sections(2)
