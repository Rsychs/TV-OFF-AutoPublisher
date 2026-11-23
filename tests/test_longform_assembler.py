import importlib.util
import tempfile
import unittest
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
