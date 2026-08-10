// chase_bg.js - Chase scene background drawing (red-black nightmare abyss, continuing the Realm red-black style)
// Elements: dark red-black gradient sky, blood-red horizon, ground crack glow
// Called by ChaseUI.draw; does not modify Realm's existing scene files

function drawChaseBackground(ctx, w, h, t) {
  // dark red-black gradient sky (brightened; top slightly pinker to echo the moon)
  const sky = ctx.createLinearGradient(0, 0, 0, h);
  sky.addColorStop(0, '#17070d');
  sky.addColorStop(0.45, '#280d11');
  sky.addColorStop(0.72, '#3a1416');
  sky.addColorStop(1, '#1c0909');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, w, h);

  // tiny scattered stars (fixed random positions, seeded so every frame is consistent)
  const rng = mulberry32(20260809);
  ctx.fillStyle = 'rgba(255,255,255,0.70)';
  for (let i = 0; i < 46; i++) {
    const sx = rng() * w;
    const sy = rng() * h * 0.55;
    const sr = 0.6 + rng() * 1.4;
    ctx.globalAlpha = 0.65 + rng() * 0.35;
    ctx.beginPath();
    ctx.arc(sx, sy, sr, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  // moon (upper right) - warm salmon-pink core fading to deep rose-red, soft hazy edge
  // reference look: bright warm pink-orange center -> rich dark magenta edge, halo bleeds pink-purple into a dark wine-red sky
  const moonX = w * 0.82;
  const moonY = h * 0.20;
  const moonR = Math.min(w, h) * 0.085;
  // outer halo: moonlight illuminating the surrounding sky - a broad diffuse glow
  // keeps a soft lift near the moon and fades very gradually into the dark sky
  const moonGlow = ctx.createRadialGradient(moonX, moonY, moonR * 0.3, moonX, moonY, moonR * 5.2);
  moonGlow.addColorStop(0, 'rgba(255,150,150,0.40)');
  moonGlow.addColorStop(0.2, 'rgba(245,110,130,0.24)');
  moonGlow.addColorStop(0.45, 'rgba(210,80,140,0.09)');
  moonGlow.addColorStop(0.7, 'rgba(155,50,110,0.05)');
  moonGlow.addColorStop(0.88, 'rgba(130,38,85,0.022)');
  moonGlow.addColorStop(1, 'rgba(110,30,70,0)');
  ctx.fillStyle = moonGlow;
  ctx.beginPath();
  ctx.arc(moonX, moonY, moonR * 5.2, 0, Math.PI * 2);
  ctx.fill();
  // moon surface: warm orange-yellow core -> fluorescent rose-red edge
  // slightly desaturated so it looks natural, then irregular highlight patches add the organic yellow core
  const moonGrad = ctx.createRadialGradient(moonX, moonY, moonR * 0.05, moonX, moonY, moonR);
  moonGrad.addColorStop(0, 'rgba(252,205,162,1)');   // soft warm orange-yellow (desaturated)
  moonGrad.addColorStop(0.22, 'rgba(250,193,144,1)'); // warm orange
  moonGrad.addColorStop(0.42, 'rgba(246,165,126,1)'); // coral orange
  moonGrad.addColorStop(0.58, 'rgba(240,142,122,1)'); // coral (warmest)
  moonGrad.addColorStop(0.7, 'rgba(235,118,128,1)');  // rose
  moonGrad.addColorStop(0.8, 'rgba(230,98,132,1)');   // rose-red
  moonGrad.addColorStop(0.9, 'rgba(226,84,140,1)');   // fluorescent rose peak
  moonGrad.addColorStop(1, 'rgba(223,94,147,1)');     // eased back so the rim melts
  ctx.fillStyle = moonGrad;
  ctx.beginPath();
  ctx.arc(moonX, moonY, moonR, 0, Math.PI * 2);
  ctx.fill();
  // irregular warm highlight patches - organic yellow core instead of a perfect round gradient
  // several soft blobs at seeded random positions/sizes overlap to make the bright area's edge uneven
  const hlSeed = mulberry32(20260811);
  for (let i = 0; i < 4; i++) {
    const a = hlSeed() * Math.PI * 2;
    const d = moonR * (0.05 + hlSeed() * 0.22);
    const r = moonR * (0.16 + hlSeed() * 0.20);
    const px = moonX + Math.cos(a) * d;
    const py = moonY + Math.sin(a) * d;
    const hg = ctx.createRadialGradient(px, py, r * 0.1, px, py, r);
    hg.addColorStop(0, 'rgba(255,216,168,0.45)');
    hg.addColorStop(1, 'rgba(255,205,150,0)');
    ctx.fillStyle = hg;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fill();
  }
  // soft inner haze: melts the moon rim outward - fluorescent rose edge bleeds softly into the sky (NOT purple)
  const moonHaze = ctx.createRadialGradient(moonX, moonY, moonR * 0.55, moonX, moonY, moonR * 1.22);
  moonHaze.addColorStop(0, 'rgba(255,170,140,0)');
  moonHaze.addColorStop(0.6, 'rgba(255,140,120,0.14)');
  moonHaze.addColorStop(1, 'rgba(255,110,110,0.26)');
  ctx.fillStyle = moonHaze;
  ctx.beginPath();
  ctx.arc(moonX, moonY, moonR * 1.22, 0, Math.PI * 2);
  ctx.fill();
  // moon surface shadow spots (hand-drawn dark "craters"/maria; Hazel asked for more: 5 -> 9)
  // uniform random distribution inside the circle (sqrt keeps the ring area uniform), contrast tuned back (0.50 -> 0.32), larger sizes kept
  ctx.fillStyle = 'rgba(150,45,95,0.30)';
  const spotSeed = mulberry32(20260810);
  for (let i = 0; i < 9; i++) {
    const a = spotSeed() * Math.PI * 2;
    const d = moonR * 0.82 * Math.sqrt(spotSeed());
    const r = moonR * (0.13 + spotSeed() * 0.28); // 0.13~0.41x moon radius
    const px = moonX + Math.cos(a) * d;
    const py = moonY + Math.sin(a) * d;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fill();
  }

  // blood-red horizon (distant rift)
  const hor = ctx.createLinearGradient(0, h * 0.76, 0, h * 0.84);
  hor.addColorStop(0, 'rgba(140,20,20,0.0)');
  hor.addColorStop(0.5, 'rgba(140,20,20,0.35)');
  hor.addColorStop(1, 'rgba(60,8,8,0.0)');
  ctx.fillStyle = hor;
  ctx.fillRect(0, h * 0.76, w, h * 0.08);

  // ground (bottom abyss platform)
  const groundY = h * 0.76;
  ctx.fillStyle = '#0d0506';
  ctx.fillRect(0, groundY, w, h - groundY);
  // ground crack glow
  ctx.strokeStyle = 'rgba(200,40,40,0.18)';
  ctx.lineWidth = 1.2;
  for (let i = 0; i < 14; i++) {
    const gx = (i / 14) * w + (rng() - 0.5) * w * 0.05;
    ctx.beginPath();
    ctx.moveTo(gx, groundY + 6);
    ctx.lineTo(gx + (rng() - 0.5) * 20, groundY + 18 + rng() * 24);
    ctx.stroke();
  }

  // vignette
  const vg = ctx.createRadialGradient(w / 2, h / 2, w * 0.35, w / 2, h / 2, w * 0.85);
  vg.addColorStop(0, 'rgba(0,0,0,0)');
  vg.addColorStop(1, 'rgba(0,0,0,0.55)');
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, w, h);
}
