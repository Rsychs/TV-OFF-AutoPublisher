import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.io.wavfile import write

SR = 22050
DURATION = 120
N = SR * DURATION
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", Path(__file__).resolve().parent / "audio"))
ROOT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20261108)
t = np.arange(N) / SR

def filt(x, low=None, high=None):
    if low and high:
        sos = butter(4, [low, high], btype="bandpass", fs=SR, output="sos")
    elif low:
        sos = butter(4, low, btype="highpass", fs=SR, output="sos")
    else:
        sos = butter(4, high, btype="lowpass", fs=SR, output="sos")
    return sosfiltfilt(sos, x)

def modulation(points=160):
    return np.interp(np.arange(N), np.linspace(0, N-1, points),
                     rng.uniform(0.65, 1.15, points))

def stereo(x, width=0.12):
    return np.column_stack((x + np.roll(x, int(SR*0.013))*width,
                            x - np.roll(x, int(SR*0.017))*width))

def seam(x, seconds=6):
    k = int(SR*seconds)
    a = np.linspace(0, 1, k)[:, None]
    blend = (1-a)*x[-k:] + a*x[:k]
    y = x.copy()
    y[:k] = blend
    y[-k:] = blend
    return y

def save(name, audio):
    audio = seam(stereo(audio))
    audio -= np.mean(audio, axis=0, keepdims=True)
    audio *= 0.78 / (np.max(np.abs(audio)) + 1e-12)
    write(ROOT / (name + ".wav"), SR,
          np.int16(np.clip(audio, -1, 1) * 32767))

# Fireplace: warm low-frequency bed, irregular crackles and occasional pops.
white = rng.normal(0, 1, N)
fire = 0.58*filt(white, high=850) + 0.20*filt(rng.normal(0,1,N), low=850, high=4200)
fire *= modulation(180)
crackle = np.zeros(N)
for _ in range(520):
    p = rng.integers(0, N-1800); length = rng.integers(80, 1200)
    burst = rng.normal(0,1,length) * np.exp(-np.linspace(0, rng.uniform(3,8), length))
    crackle[p:p+length] += rng.uniform(0.08,0.55)*burst
for _ in range(42):
    p = rng.integers(0, N-5000); length = rng.integers(500,4000)
    burst = filt(rng.normal(0,1,length), high=500)
    burst *= np.exp(-np.linspace(0, rng.uniform(4,9), length))
    crackle[p:p+length] += rng.uniform(0.25,0.8)*burst
save("fireplace", 0.55*fire + 0.42*crackle)

# Rain: dense broadband wash, changing intensity and individual droplets.
noise = rng.normal(0,1,N)
rain = 0.58*filt(noise, high=7200)*(0.78+0.18*np.sin(2*np.pi*t/37)+0.08*np.sin(2*np.pi*t/11.3))
rain += 0.26*filt(rng.normal(0,1,N), low=900, high=6500)*modulation(220)
drops = np.zeros(N)
for _ in range(1800):
    p = rng.integers(0,N-500); length = rng.integers(30,350)
    burst = rng.normal(0,1,length)*np.exp(-np.linspace(0,rng.uniform(5,12),length))
    drops[p:p+length] += rng.uniform(0.015,0.11)*burst
save("rain", rain + drops)

# Thunderstorm: rain bed with distant, rolling low-frequency thunder swells.
storm = 0.72*rain
for center in [8,23,41,58,77,96,113]:
    center += rng.uniform(-2.5,2.5)
    start=max(0,int((center-7)*SR)); end=min(N,int((center+15)*SR)); L=end-start
    local=np.arange(L)/SR
    rumble=filt(rng.normal(0,1,L), high=95)
    env=np.where(local<1.8, local/1.8, np.exp(-(local-1.8)/14.0))
    env *= 0.55+0.45*np.sin(np.pi*np.clip(local/17,0,1))
    storm[start:end] += rumble*env*rng.uniform(0.5,1.25)
    storm[start:end] += 0.12*filt(rng.normal(0,1,L), low=90, high=420)*env
save("thunderstorm", storm)

# Wind: slow gusts, airy broadband movement and subtle drifting tones.
gust=np.clip(0.42+0.34*np.sin(2*np.pi*t/29+0.7)+0.18*np.sin(2*np.pi*t/13.7),0.08,1.0)
wind=0.76*filt(rng.normal(0,1,N), high=420)*gust
wind+=0.20*filt(rng.normal(0,1,N), low=350, high=1800)*(0.5+0.5*gust)
for f0,amp,phase in [(390,0.045,0.2),(560,0.025,1.7),(740,0.018,2.4)]:
    drift=f0+22*np.sin(2*np.pi*t/31+phase)
    wind += amp*np.sin(2*np.pi*drift*t)*gust
save("wind", wind)

# WAV masters are retained; FFmpeg makes compact MP3s for the video builder.
import subprocess
for name in ["fireplace","rain","thunderstorm","wind"]:
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(ROOT/(name+".wav")),
                    "-codec:a","libmp3lame","-b:a","192k",str(ROOT/(name+".mp3"))],check=True)

manifest = {}
for name in ["fireplace","rain","thunderstorm","wind"]:
    manifest[name] = {
        "file": name+".mp3",
        "creator": "TV OFF — original generated audio",
        "source_url": "https://github.com/Rsychs/TV-OFF-AutoPublisher/blob/main/generate_original_ambience.py",
        "license": "Original audio created for TV OFF; no third-party recording used.",
        "downloaded_at": datetime.now(timezone.utc).isoformat()
    }
(ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("Generated four original two-minute ambience loops and manifest.")
