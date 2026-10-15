# Demo video

Everything in the video comes from one real, unscripted run of the product. Nothing on screen is mocked.

1. `uv run python scripts/record_demo.py` starts the service, presses Break It, shops and complains like a
   customer, and films both browser tabs to `video/raw/board.webm` and `video/raw/shop.webm`.
2. The waiting is cut out and the busy screens are cropped so text is readable (ffmpeg, H.264):

| Clip | Source | Start | Length | Crop (w:h:x:y) |
|---|---|---|---|---|
| `s-break.mp4` | board | 0.5 s | 8 s | full frame |
| `s-shopA.mp4` | shop | 0 s | 11 s | 1067:600:267:60 |
| `s-shopB.mp4` | shop | 11 s | 6.5 s | 800:450:800:450 |
| `s-heard.mp4` | board | 23 s | 8 s | 1036:583:112:150 |
| `s-repro.mp4` | board | 46.5 s | 8 s | 1036:583:112:150 |
| `s-fixed.mp4` | board | 84 s | 5 s | 1036:583:112:150 |
| `s-detail.mp4` | board | 89.5 s | 16.5 s | 960:540:640:0 |

   Each clip: `ffmpeg -ss <start> -t <length> -i raw/<source>.webm -vf "crop=<crop>,scale=1600:900,fps=30" -an -c:v libx264 -crf 18 -pix_fmt yuv420p film/assets/<clip>`

   `s-detail.mp4` then has 10.3-12.1 s cut out: the dashboard briefly showed a wrong red "problem still showed up"
   line once a case reached Guarded (a display bug, fixed in `CaseDetail.tsx` on Oct 15). The last frame is held 1.8 s
   so the clip keeps its 16.5 s length.
3. The before/after screenshots are the real ones the engine saved for bugs 4, 7 and 10 (`results/cases/shots/`).
4. `film/` is a HyperFrames composition. `npx hyperframes check` then `npx hyperframes render -o ../complaint-replay-demo.mp4 --quality delivery`.
