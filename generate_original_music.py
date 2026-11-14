import hashlib
import json
import os
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write

SR = 22050
# Shorts workflow exports TARGET_SLOT before invoking this generator. Give Shorts
# a compact arrangement with a chord change every 4.5 seconds; long-form keeps
# the slower 60-second harmonic movement and 32-minute source master.
SHORT_MODE = bool(os.environ.get("TARGET_SLOT", "").strip())
BAR_SECONDS = 4.5 if SHORT_MODE else 60
BARS = 8 if SHORT_MODE else 32
TIME_SCALE = BAR_SECONDS / 60.0
DURATION = BAR_SECONDS * BARS
N = int(SR * DURATION)
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", Path(__file__).resolve().parent / "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)

MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
}
PROGRESSIONS = [
    [0, 4, 1, 5, 3, 6, 2, 4],
    [0, 5, 3, 4, 1, 6, 2, 5],
    [5, 3, 0, 4, 2, 6, 1, 4],
    [0, 3, 5, 1, 4, 2, 6, 3],
    [1, 5, 0, 6, 3, 4, 2, 5],
    [0, 6, 3, 4, 5, 1, 2, 4],
    [2, 5, 1, 4, 0, 3, 6, 5],
    [0, 2, 5, 3, 6, 4, 1, 5],
    [5, 1, 4, 0, 3, 6, 2, 4],
    [0, 4, 2, 5, 1, 6, 3, 4],
    [3, 0, 5, 2, 6, 1, 4, 5],
    [0, 5, 1, 4, 2, 6, 3, 4],
]
PROFILES = {
    "velvet_piano": {"pad_harmonics": 3, "pad_gain": 0.014, "bass_gain": 0.008, "melody_gain": 0.014, "arp_gain": 0.006, "bell_harmonics": 5, "echo": "0.8:0.68:95|190:0.10|0.05"},
    "warm_analog": {"pad_harmonics": 7, "pad_gain": 0.011, "bass_gain": 0.010, "melody_gain": 0.011, "arp_gain": 0.007, "bell_harmonics": 4, "echo": "0.8:0.76:75|150:0.12|0.06"},
    "cinematic_halo": {"pad_harmonics": 9, "pad_gain": 0.009, "bass_gain": 0.009, "melody_gain": 0.016, "arp_gain": 0.005, "bell_harmonics": 7, "echo": "0.8:0.82:125|250:0.15|0.08"},
    "glass_and_felt": {"pad_harmonics": 4, "pad_gain": 0.012, "bass_gain": 0.008, "melody_gain": 0.018, "arp_gain": 0.008, "bell_harmonics": 8, "echo": "0.8:0.72:105|210:0.14|0.07"},
    "deep_drift": {"pad_harmonics": 5, "pad_gain": 0.013, "bass_gain": 0.012, "melody_gain": 0.009, "arp_gain": 0.004, "bell_harmonics": 3, "echo": "0.8:0.70:115|230:0.09|0.04"},
}


MUSIC_STYLES = {
    "deep_ambient": {
        "description": "Deep Ambient — long evolving pads, restrained melody and deep harmonic space",
        "arp_probability": 0.28, "melody_probability": 0.38,
        "pad_scale": 1.18, "bass_scale": 1.12, "arp_scale": 0.62,
        "melody_scale": 0.72, "melody_timbre": "pad",
    },
    "soft_keys": {
        "description": "Soft Keys — gentle felt-like synthetic keys, intimate phrases and warm harmony",
        "arp_probability": 0.58, "melody_probability": 0.82,
        "pad_scale": 0.78, "bass_scale": 0.82, "arp_scale": 0.92,
        "melody_scale": 1.18, "melody_timbre": "pluck",
    },
    "cinematic_ambient": {
        "description": "Cinematic Ambient — wide layered harmony, gradual lifts and expressive counter-lines",
        "arp_probability": 0.72, "melody_probability": 0.76,
        "pad_scale": 1.12, "bass_scale": 1.0, "arp_scale": 0.88,
        "melody_scale": 1.12, "melody_timbre": "bell",
    },
    "warm_analog": {
        "description": "Warm Analog — rounded synth layers, gentle pulse-like movement and soft low end",
        "arp_probability": 0.68, "melody_probability": 0.58,
        "pad_scale": 1.08, "bass_scale": 1.2, "arp_scale": 0.82,
        "melody_scale": 0.88, "melody_timbre": "pad",
    },
    "celestial": {
        "description": "Celestial — airy upper-register tones, delicate bell colours and spacious harmony",
        "arp_probability": 0.76, "melody_probability": 0.68,
        "pad_scale": 0.92, "bass_scale": 0.72, "arp_scale": 1.16,
        "melody_scale": 1.08, "melody_timbre": "bell",
    },
    "minimal_meditation": {
        "description": "Minimal Meditation — sparse notes, slow harmonic breathing and very low melodic density",
        "arp_probability": 0.18, "melody_probability": 0.30,
        "pad_scale": 1.22, "bass_scale": 0.9, "arp_scale": 0.48,
        "melody_scale": 0.62, "melody_timbre": "pad",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def midi_frequency(midi):
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


def add_voice(mix, freq, start, length, gain, pan, rng, harmonics=4,
              brightness=1.8, attack=5.0, release=10.0,
              timbre="pad", vibrato_depth=0.025):
    start_index = max(0, int(start * SR))
    count = min(int(length * SR), N - start_index)
    if count <= 0 or freq <= 0:
        return
    t = np.arange(count, dtype=np.float32) / SR
    attack_env = 1.0 - np.exp(-t / max(0.01, attack))
    release_env = np.clip((length - t) / max(0.01, release), 0.0, 1.0)
    if timbre == "bell":
        envelope = attack_env * np.exp(-t / max(1.0, length * 0.42)) * release_env
    elif timbre == "pluck":
        envelope = attack_env * np.exp(-t / max(1.0, length * 0.58)) * release_env
    else:
        envelope = np.minimum(attack_env, release_env)
    vibrato_rate = rng.uniform(0.025, 0.075)
    vibrato = vibrato_depth * np.sin(2.0 * np.pi * vibrato_rate * t)
    wave = np.zeros(count, dtype=np.float32)
    for h in range(1, harmonics + 1):
        partial = h * (1.0 + 0.0018 * h) if timbre == "bell" else h
        if freq * partial >= SR * 0.47:
            continue
        weight = 1.0 / (h ** brightness)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        wave += np.sin(2.0 * np.pi * freq * partial * t + vibrato + phase).astype(np.float32) * weight
    wave *= envelope.astype(np.float32) * gain
    left = wave * np.sqrt((1.0 - pan) * 0.5)
    right = wave * np.sqrt((1.0 + pan) * 0.5)
    mix[start_index:start_index + count, 0] += left
    mix[start_index:start_index + count, 1] += right


def build_chords(rng, mode_name, root_midi, progression, section_shifts):
    scale = MODES[mode_name]
    chords = []
    for bar in range(BARS):
        degree = progression[bar % len(progression)]
        section = min(3, bar // max(1, BARS // 4))
        root = root_midi + section_shifts[section]
        # Extended voicings: root, third, fifth, seventh, with optional 9th/11th/13th.
        steps = [0, 2, 4, 6]
        if rng.random() < 0.82:
            steps.append(8)
        if rng.random() < 0.46:
            steps.append(10)
        if rng.random() < 0.24:
            steps.append(12)
        tones = []
        for step in steps:
            scale_index = degree + step
            semitone = scale[scale_index % 7] + 12 * (scale_index // 7)
            tones.append(midi_frequency(root + semitone))
        chords.append(tones)
    return chords


def main():
    seed = secrets.randbelow(2**32 - 1) + 1
    rng = np.random.default_rng(seed)
    style_pool = (
        ["soft_keys", "cinematic_ambient", "warm_analog", "celestial"]
        if SHORT_MODE else list(MUSIC_STYLES.keys())
    )
    previous_combo = None
    if SHORT_MODE:
        history_path = ROOT.parent / "shorts_state.json"
        if history_path.is_file():
            history = json.loads(history_path.read_text(encoding="utf-8"))
            records = history.get("_published_music_metadata", [])
            if not isinstance(records, list):
                raise RuntimeError("Invalid Shorts Original Music metadata ledger; refusing an untracked combination.")
            for record in reversed(records):
                if not isinstance(record, dict):
                    continue
                candidate = (
                    str(record.get("music_style", "")).strip(),
                    str(record.get("sound_profile", "")).strip(),
                    str(record.get("musical_mode", "")).strip(),
                )
                if all(candidate):
                    previous_combo = candidate
                    break
    combinations = [
        (mode, style, profile)
        for mode in MODES
        for style in style_pool
        for profile in PROFILES
    ]
    eligible_combinations = [item for item in combinations if item != previous_combo]
    if not eligible_combinations:
        eligible_combinations = combinations
    mode_name, style_name, profile_name = eligible_combinations[
        int(rng.integers(0, len(eligible_combinations)))
    ]
    style = MUSIC_STYLES[style_name]
    profile = PROFILES[profile_name]
    root_midi = int(rng.integers(40, 53))
    progression = list(PROGRESSIONS[int(rng.integers(0, len(PROGRESSIONS)))])
    section_shifts = [0, int(rng.choice([2, 5, 7])), int(rng.choice([-2, 2, 5])), 0]
    chords = build_chords(rng, mode_name, root_midi, progression, section_shifts)
    mix = np.zeros((N, 2), dtype=np.float32)
    melody_state = int(rng.integers(1, 6))

    for bar in range(BARS):
        section = min(3, bar // max(1, BARS // 4))
        chord = chords[bar]
        start = bar * BAR_SECONDS

        # Sustained wide pads carry extended harmony and slowly changing voicings.
        for index, freq in enumerate(chord):
            octave = 1.0 if index < 4 else 2.0
            pan = float(np.clip(-0.52 + index * 0.17 + rng.uniform(-0.09, 0.09), -0.78, 0.78))
            add_voice(
                mix, freq * octave, start + rng.uniform(0.0, 2.8) * TIME_SCALE, BAR_SECONDS * 1.04,
                profile["pad_gain"] * style["pad_scale"] * (1.0 if index == 0 else 0.66 if index < 4 else 0.38),
                pan, rng, harmonics=profile["pad_harmonics"],
                brightness=float(rng.uniform(1.55, 2.45)),
                attack=float(rng.uniform(7.0, 14.0)) * TIME_SCALE,
                release=float(rng.uniform(10.0, 18.0)) * TIME_SCALE,
                timbre="pad", vibrato_depth=float(rng.uniform(0.008, 0.035)),
            )

        # Sub-bass follows the changing harmony; occasional fifths add movement.
        bass_root = chord[0] * 0.5
        add_voice(
            mix, bass_root, start + rng.uniform(0.0, 1.2) * TIME_SCALE, BAR_SECONDS * 0.98,
            profile["bass_gain"] * style["bass_scale"], float(rng.uniform(-0.08, 0.08)), rng,
            harmonics=2, brightness=2.2, attack=5.0 * TIME_SCALE, release=12.0 * TIME_SCALE,
            timbre="pad", vibrato_depth=0.006,
        )
        if rng.random() < 0.55:
            add_voice(
                mix, bass_root * 1.5, start + rng.uniform(8.0, 18.0) * TIME_SCALE, BAR_SECONDS * 0.72,
                profile["bass_gain"] * 0.34, float(rng.uniform(-0.2, 0.2)), rng,
                harmonics=2, brightness=2.0, attack=4.0 * TIME_SCALE, release=9.0 * TIME_SCALE,
                timbre="pad", vibrato_depth=0.008,
            )

        # Slow arpeggiated inner voice appears and disappears between sections.
        if rng.random() < style["arp_probability"] * (1.08 if section in (1, 2) else 0.88):
            arp_count = int(rng.integers(3, 7))
            for note_index in range(arp_count):
                freq = float(rng.choice(chord)) * float(rng.choice([2.0, 4.0]))
                onset = start + 5.0 * TIME_SCALE + note_index * float(rng.uniform(7.0, 11.0)) * TIME_SCALE
                add_voice(
                    mix, freq, onset, float(rng.uniform(7.0, 13.0)) * TIME_SCALE,
                    profile["arp_gain"] * style["arp_scale"] * float(rng.uniform(0.65, 1.15)),
                    float(rng.choice([-0.58, -0.32, 0.24, 0.52])), rng,
                    harmonics=profile["bell_harmonics"],
                    brightness=float(rng.uniform(1.8, 2.8)),
                    attack=0.35 * TIME_SCALE, release=6.0 * TIME_SCALE, timbre="pluck",
                    vibrato_depth=0.012,
                )

        # A phrase-shaped counter-melody moves by nearby scale steps. Each
        # four-bar phrase gets a fresh starting note; intervening notes move
        # mostly by step, with occasional chord-tone landings.
        if bar % 4 == 0:
            melody_state = int(rng.integers(1, 6))
        else:
            melody_state = int(np.clip(
                melody_state + int(rng.choice([-2, -1, 1, 2])), 0, 6
            ))
        melody_probability = max(style["melody_probability"], 0.75) if SHORT_MODE else style["melody_probability"]
        melody_count = int(rng.integers(1, 3)) if rng.random() < melody_probability else 0
        for note_index in range(melody_count):
            if note_index:
                melody_state = int(np.clip(
                    melody_state + int(rng.choice([-1, 1])), 0, 6
                ))
            scale_semitone = MODES[mode_name][melody_state]
            melody_midi = root_midi + section_shifts[section] + scale_semitone + int(rng.choice([24, 36]))
            freq = midi_frequency(melody_midi)
            # The first note of each phrase often lands on a chord tone.
            if bar % 4 == 0 and note_index == 0 and rng.random() < 0.72:
                freq = float(rng.choice(chord)) * 4.0
            onset = start + float(rng.uniform(6.0, 48.0)) * TIME_SCALE
            bell = rng.random() < 0.58
            add_voice(
                mix, freq, onset, float(rng.uniform(8.0, 19.0)) * TIME_SCALE,
                profile["melody_gain"] * style["melody_scale"] * float(rng.uniform(0.55, 1.1)),
                float(rng.choice([-0.62, -0.38, 0.0, 0.34, 0.60])), rng,
                harmonics=profile["bell_harmonics"] if bell else 3,
                brightness=float(rng.uniform(1.5, 2.6)),
                attack=float(rng.uniform(0.5, 2.5)) * TIME_SCALE,
                release=float(rng.uniform(6.0, 12.0)) * TIME_SCALE,
                timbre=style["melody_timbre"] if not bell else "bell",
                vibrato_depth=float(rng.uniform(0.006, 0.025)),
            )

        # A quiet upper colour tone deepens the middle sections without clutter.
        if section in (1, 2) and rng.random() < 0.7:
            upper = float(rng.choice(chord[-2:])) * 2.0
            add_voice(
                mix, upper, start + rng.uniform(2.0, 12.0) * TIME_SCALE, BAR_SECONDS * 0.8,
                profile["pad_gain"] * 0.22, float(rng.uniform(-0.7, 0.7)), rng,
                harmonics=2, brightness=2.0, attack=12.0 * TIME_SCALE, release=15.0 * TIME_SCALE,
                timbre="pad", vibrato_depth=0.018,
            )

    mix -= np.mean(mix, axis=0, keepdims=True)
    peak = float(np.max(np.abs(mix)))
    mix *= 0.74 / max(peak, 1e-9)

    wav_path = ROOT / "original_music_master.wav"
    mp3_path = ROOT / "original_music_master.mp3"
    write(wav_path, SR, np.int16(np.clip(mix, -1.0, 1.0) * 32767))
    del mix
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav_path), "-af", f"aecho={profile['echo']}",
        "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)
    ], check=True, timeout=1800)
    wav_path.unlink(missing_ok=True)

    digest = sha256_file(mp3_path)
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["original_music"] = {
        "file": mp3_path.name,
        "creator": "TV OFF — original multi-layer procedural composition",
        "audio_type": "synthetic",
        "platform": "TV OFF / local synthesis",
        "source_url": "Original composition synthesized locally by TV OFF; no external source.",
        "license": "Original composition synthesized for TV OFF; no third-party samples, recordings, or borrowed melodies used.",
        "duration_seconds": DURATION,
        "composition_mode": "short_form_fast_harmonic_movement" if SHORT_MODE else "long_form_slow_ambient",
        "bar_seconds": BAR_SECONDS,
        "sample_rate": SR,
        "random_seed": seed,
        "musical_mode": mode_name,
        "sound_profile": profile_name,
        "music_style": style_name,
        "music_style_description": style["description"],
        "root_midi": root_midi,
        "progression_degrees": progression,
        "section_key_shifts_semitones": section_shifts,
        "layers": ["extended chord pads", "moving sub-bass", "sparse arpeggios", "counter-melody", "upper harmonic colour"],
        "sha256": digest,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_digest = sha256_file(manifest_path)
    (ROOT / "manifest.sha256").write_text(
        f"{digest}  {mp3_path.name}\n{manifest_digest}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    print(
        f"Generated {'Shorts' if SHORT_MODE else str(DURATION // 60) + '-minute'} original composition: "
        f"style={style_name}, profile={profile_name}, mode={mode_name}, root_midi={root_midi}, "
        f"progression={progression}, section_shifts={section_shifts}, sha256={digest}"
    )


if __name__ == "__main__":
    main()
