from pathlib import Path
import json
import zipfile

root = Path("/content/ace_step_output")
manifest_path = root / "ace_step_smoke_result.json"
if not manifest_path.is_file():
    raise SystemExit("Missing ACE-Step manifest; refusing to package incomplete output.")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("status") != "ok":
    raise SystemExit("Generation manifest is not successful.")
required = ["audio_file", "visual_file", "landscape_file"]
for key in required:
    name = manifest.get(key)
    if not name or not (root / name).is_file():
        raise SystemExit(f"Missing generated asset declared by manifest: {key}")
for key, hash_key in [("audio_file", "sha256"), ("visual_file", "visual_sha256"), ("landscape_file", "landscape_sha256")]:
    import hashlib
    p = root / manifest[key]
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != manifest.get(hash_key):
        raise SystemExit(f"SHA-256 mismatch for {p.name}")
archive = Path("/content/tv_off_colab_dry_run.zip")
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for p in root.iterdir():
        if p.is_file():
            z.write(p, arcname=p.name)
print(f"COLAB_OUTPUT_PACKAGE_OK {archive} bytes={archive.stat().st_size}")
