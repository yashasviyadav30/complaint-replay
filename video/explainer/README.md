# Narrated explainer (about 6 minutes)

A longer walkthrough of the project with an English voice-over and subtitles, for understanding the project.
It is not the submission video: Devpost allows 3 minutes at most (`../film/` is the short one).

The footage is the same real run as `../film/` (see `../README.md`). The screenshots `shot-*.png` were taken from the
recorded demo site. The voice is Kokoro-82M, a local text-to-speech model run by `hyperframes tts`; nothing is uploaded.

## Rebuild

```bash
# one-time: Kokoro's Python runtime, in its own venv
uv venv kokoro-venv --python 3.12 && VIRTUAL_ENV=kokoro-venv uv pip install kokoro-onnx soundfile
export HYPERFRAMES_PYTHON=kokoro-venv/Scripts/python.exe

# 1. edit narration.json, then write one .txt per scene and voice it
python -c "import json;[open(f'assets/vo/{s[\"id\"]}.txt','w',encoding='utf-8').write(s['text']) for s in json.load(open('narration.json',encoding='utf-8'))]"
for f in assets/vo/*.txt; do npx hyperframes@0.8.152 tts "$f" -v af_heart -s 0.95 -o "${f%.txt}.wav"; done

# 2. lay out scenes from the real voice lengths, check, render
python build.py
npx hyperframes@0.8.152 check
npx hyperframes@0.8.152 render -o ../complaint-replay-explainer.mp4 --quality delivery
```

`build.py` makes each scene as long as its voice-over and slows footage (never speeds it up) to fill it.
Subtitles and on-screen reveals are timed by sentence length, so they are close to the voice, not word-exact.
