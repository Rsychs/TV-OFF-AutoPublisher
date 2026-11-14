# TV OFF Visual Engine — Prototype Architecture

Status: isolated research prototype. Nothing in this branch is connected to publishing workflows.

## Goal

Generate original, realistic moving interior scenes for TV OFF Shorts using free cloud compute where available. This is an orchestration layer around existing models, not a model trained from scratch.

## Architecture

1. **Prompt planner** — creates a scene brief with camera path, lighting, materials, environmental motion and negative constraints.
2. **Scene/keyframe stage** — optional image generation for image-to-video backends. Text-to-video backends must not require a still image.
3. **Video backend adapter** — supports multiple providers/models without coupling production to one service.
4. **Post-production** — FFmpeg normalizes frame rate, aspect ratio, audio mix, hook and CTA. Blender is optional for deterministic camera/lighting elements, not the core video generator.
5. **Quality gate** — checks dimensions, duration, decode integrity, black frames, duplicate hashes, flicker/scene stability where measurable, and metadata.
6. **Artifact output** — exports MP4 + JSON manifest. No YouTube upload in this prototype.

## Model and provider findings

### Candidate A: LTX-2.5 on Hugging Face ZeroGPU — first T2V API experiment

- Model page: https://huggingface.co/Lightricks/LTX-2.5
- Public backend Space: https://huggingface.co/spaces/Lightricks/LTX-2.5
- A public client page documents text-to-video with an optional starting image, and says requests are sent to the official Lightricks Space: https://arpitkgoyal-ltx-2-5-demo.static.hf.space/
- The public client defaults to a 2-second clip. Higher resolution and longer duration increase GPU time and may exceed the backend reservation limit.
- The model is large (the public client describes 70 GB+ weights), so this is a hosted-inference candidate, not a practical free local/Kaggle download.
- Hugging Face documents Gradio Spaces as callable APIs. The actual endpoint schema and unauthenticated access must be queried from the official Space before writing a production adapter.
- Anonymous ZeroGPU allowance is very small (documented as 2 GPU minutes/day); a free authenticated account has a documented 5 GPU minutes/day. Shared queue availability and quota can still block calls. Treat these as current documented limits, not guaranteed service levels.
- Do not send an HF token to third-party frontends. If authentication is needed, call the official backend directly and keep the token in a user-controlled secret store.
- **Not yet tested from this repository:** API endpoint schema, a successful anonymous inference, output download, commercial rights for the exact model revision, and quality on TV OFF interior prompts.

### Candidate B: Wan 2.2 I2V on Hugging Face ZeroGPU

- Public Space: https://huggingface.co/spaces/zerogpu-aoti/wan2-2-fp8da-aoti-faster
- Its current app source requires an input image; it is image-to-video, not text-to-video.
- The source describes 8–81 frames at 16 FPS (about 0.5–5.1 seconds). This is suitable for animating a prepared keyframe, not a standalone long video.
- Gradio API route documented in a recent public test: `/generate_video`; inputs include image, prompt, steps, negative prompt, duration, guidance scales, seed and randomize flag.
- Anonymous ZeroGPU quota is limited; repeated batch production is not a safe assumption.
- This is a secondary I2V backend, only after a separate still-image stage exists.

### Candidate C: Wan2GP on Kaggle

- Notebook: `TV_OFF_Wan2GP_Kaggle.ipynb`
- Target is a Kaggle T4/P100 class runtime with low-VRAM settings and reduced 480p output.
- Kaggle GPU availability and weekly quotas depend on account eligibility and availability.
- No successful Kaggle execution has been performed from this repository yet.

### Not selected for first test

- Standard HunyuanVideo requirements are too high for typical free notebook GPUs.
- A model's open code license does not automatically grant commercial rights to its weights or outputs.

## Free cloud compute strategy

1. Try the official LTX-2.5 Space API for one very short text-to-video acceptance test, after verifying its exact API schema.
2. Use Wan2.2 I2V ZeroGPU only when a reference frame is available and its API is confirmed.
3. Keep Kaggle + Wan2GP as the self-hosted fallback; verify GPU availability at runtime.
4. Google Colab Free is a last-resort fallback; GPU availability and limits fluctuate and are not guaranteed.

No provider is treated as guaranteed. The prototype must checkpoint downloads, save outputs to persistent cloud storage, detect preemption, and resume safely. Do not automate account creation, evade quotas, or use multiple accounts to bypass limits.

## First acceptance test

- Prompt: cinematic luxury bedroom at midnight, floor-to-ceiling windows, rain outside, warm amber lamps, deep navy shadows, slow camera dolly, subtle curtain/rain movement, realistic reflections, no people, no text, no logos.
- Output: 2–5 second 16:9 MP4 initially, then test vertical framing.
- Must pass: playable MP4, stable architecture, no severe geometry warping, no unusable flicker, and an auditable model/license record.
- Record GPU/provider, queue wait, runtime, model revision, prompt, seed, output dimensions, quota/error response and output checksum.
- A notebook setup or API connection is not a successful video generation. Only a downloaded and inspected MP4 passes.

## Commercial-use gate

Do not publish model outputs until the exact weights, dependencies, dataset terms where relevant, and hosting service terms have been checked for commercial use. A permissive code license does not automatically grant unrestricted rights to model weights.

## Safety boundaries

- This branch is separate from `main`.
- No publishing workflow, scheduler, issue trigger, OAuth secret, YouTube token, production state file or existing media is modified.
- Cloud Studio remains frozen.
- No automatic YouTube upload. Prototype outputs are research artifacts only.


## 20-second Shorts feasibility — verified from the live Space source

The official LTX-2.5 ZeroGPU Space UI slider is capped at 5 seconds, but its public `/run` handler accepts `duration_s` and calls `frames_from_duration(duration_s)`; the underlying `generate()` function accepts an explicit frame count. The same source caps *automatic* duration at 15 seconds for quota reservation, not because the model itself is limited to 15 seconds. The model's official API supports up to 20 seconds at selected resolutions/FPS.

A 20-second direct API request is therefore a technically grounded experiment, not a proven successful free run. ZeroGPU estimates reservation from pixel count and doubles it for the xlarge slice; the free daily quota may reject the request, and queue/runtime are not guaranteed. The 20-second test script now requests 481 frames at 24 fps and 512x640, then center-crops/upscales to a 720x1280 Shorts master. This keeps the request smaller than a native 9:16 render in the hope of fitting the free reservation while preserving 20 seconds.

**Important:** the API may reject the out-of-slider duration, the quota may be insufficient, or the output may not sustain coherent motion for 20 seconds. The acceptance test must inspect actual MP4 duration and quality; no successful generation is claimed yet. If it fails, next options are two or more overlapping clips with matched keyframes (if I2V is available), or a self-hosted Kaggle HunyuanVideo-1.5/Wan2GP run with the relevant GPU quota. Concatenating unrelated clips without continuity control is not an acceptable final solution.
