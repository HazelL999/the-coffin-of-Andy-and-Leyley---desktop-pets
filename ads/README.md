# Ads folder — each SUBFOLDER here is one TV ad.

Drop your ads in like this:

```
ads/
  ad_cereal/        # a single static image ad
    01.png
  ad_shampoo/       # a .gif ad (PIL reads each frame at the gif's own speed)
    clip.gif
  ad_juice/         # a looping frame sequence (multiple PNGs)
    01.png
    02.png
    03.png
  couch.png         # NOT an ad — the "pets on the couch watching" image
```

Rules:
- One ad = one subfolder. The subfolder name is the ad's label (not shown).
- A subfolder with a single `.png`/`.jpg` → shown for ~5 s (`config.TV_AD_HOLD_S`).
- A subfolder with a single `.gif` → played frame-by-frame at the gif's own
  per-frame durations. This is how you play "video": convert your clip to gif.
- A subfolder with multiple `.png`s → played as a looping sequence
  (`config.ANIM_FRAME_DEFAULT_MS` per frame).
- `couch.png` (top level, not in a subfolder) is the couch image shown to
  the right of the screen. Replace it with your "two of them on the couch
  watching TV" image. If absent, a placeholder is shown.

The folder ships with a few placeholder ads so the TV works out of the box —
delete or replace them with your real ad art.
