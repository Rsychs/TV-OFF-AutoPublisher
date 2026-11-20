# TV OFF — ACE-Step on Kaggle (isolated prototype)

This integration is intentionally separate from the production music generator and publishing jobs.

## What it does

- Reuses the existing GitHub Actions `KAGGLE_API_TOKEN` secret.
- Pushes a private Kaggle notebook to a Tesla T4.
- Installs the official ACE-Step 1.5.2 project.
- Initializes the 2B Turbo DiT with CPU offload and INT8 weight-only quantization.
- Generates one 30-second instrumental test track.
- Validates duration, finite samples, peak level and RMS.
- Returns the WAV and JSON manifest as a GitHub Actions artifact.

## What it does not do

- Does not change `generate_original_music.py`.
- Does not change White Noise or Brown Noise.
- Does not access the publishing queue, YouTube credentials, schedule, deduplication ledger, locks or cooldowns.
- Does not publish anything.

## Run

Push a change to this feature branch affecting this workflow or the `kaggle/ace-step-smoke/` folder. GitHub Actions automatically pushes the notebook to Kaggle and returns the audio artifact.

## First-test configuration

The first pass uses DiT-only inference (`thinking=False`, no 5Hz language model) to reduce memory and isolate T4 compatibility. If it passes, the next experiment can add the 0.6B LM via the PyTorch backend and compare composition quality. The first successful smoke test is not by itself approval for production use.

## Upstream

- ACE-Step 1.5: https://github.com/ACE-Step/ACE-Step-1.5
- Inference API: https://github.com/ACE-Step/ACE-Step-1.5/blob/main/docs/en/INFERENCE.md
- GPU compatibility: https://github.com/ACE-Step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md
