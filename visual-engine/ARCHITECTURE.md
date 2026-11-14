# TV OFF Visual Engine — Prototype Architecture

Status: isolated research prototype. Nothing in this branch is connected to publishing workflows.

## Goal

Generate original, photorealistic moving interior scenes for TV OFF Shorts using only free cloud compute. The project is an orchestration layer around open-weight models, not a foundation model trained from scratch.

## Architecture

1. **Prompt planner** — creates a scene brief with camera path, lighting, materials, environment motion and negative constraints.
2. **Scene/keyframe stage** — optional image model creates a reference frame. Keep this replaceable; Nano Banana is not an open-weight dependency.
3. **Video backend** — primary candidate Wan 2.2 TI2V-5B (text-to-video and image-to-video, 720p/24fps capability). Backend adapter isolates model-specific CLI/API.
4. **Post-production** — FFmpeg normalizes frame rate, aspect ratio, audio mix, hook and CTA. Blender is optional for deterministic camera/lighting elements, not the core video generator.
5. **Quality gate** — checks dimensions, duration, decode integrity, black frames, duplicate hashes, and metadata.
6. **Artifact output** — exports MP4 + JSON manifest. No YouTube upload in this prototype.

## Model selection

### Primary: Wan 2.2 TI2V-5B
- Official code/weights: https://github.com/Wan-Video/Wan2.2
- Official repository identifies Apache-2.0 code license and TI2V-5B supporting T2V/I2V at up to 720p/24fps.
- The upstream README says the 5B model is intended for consumer GPUs such as RTX 4090. This does **not** mean it will run on every free cloud GPU.
- The exact model-weight license and any usage restrictions must be checked on the model card before commercial use; code license alone is not sufficient.

### Secondary candidates
- LTX-2.5: newer open model with multi-shot and synchronized audio/video; evaluate after first Wan prototype. Check its model-specific license, VRAM, and cloud compatibility before adoption.
- HunyuanVideo: quality candidate, but upstream requirements list 45–60 GB GPU memory for standard inference; not a realistic first target for ordinary free notebooks.

## Free cloud compute strategy

1. Kaggle Notebooks — first runtime to test; GPU allocation and weekly quota are account/availability dependent.
2. Google Colab Free — fallback only. Google explicitly says GPU availability and limits fluctuate and are not guaranteed.
3. Hugging Face ZeroGPU — useful for short interactive experiments; free user quota is 5 GPU minutes/day, so not suitable for batch production.

No provider is treated as guaranteed. The prototype must checkpoint downloads, save outputs to persistent cloud storage, detect preemption, and resume safely. Do not automate account creation, evade quotas, or use multiple accounts to bypass limits.

## First acceptance test

- Input: one TV OFF interior prompt and optionally one reference image.
- Output: 3–5 second 16:9 or 9:16 MP4, first at reduced resolution if necessary.
- Must pass: playable MP4, stable architecture, no severe geometry warping, no flicker that makes the scene unusable, and an auditable model/license record.
- A successful notebook setup is not a successful video generation. Record GPU type, VRAM, peak memory, runtime, model revision, prompt, seed, output dimensions and errors.

## Commercial-use gate

Do not publish model outputs until the exact weights, dependencies, dataset terms where relevant, and hosting service terms have been checked for commercial use. A permissive code license does not automatically grant unrestricted rights to model weights or generated content.

## Safety boundaries

- This branch is separate from `main`.
- No publishing workflow, scheduler, issue trigger, OAuth secret, YouTube token, production state file or existing media is modified.
- Cloud Studio remains frozen.
- No automatic YouTube upload. Prototype outputs are research artifacts only.
