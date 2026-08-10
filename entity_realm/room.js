// room.js - Red-black fantasy background
// Red-black starry sky (no mountains, no waves)
// Hand-drawn feel: fixed seed + wobble, stable every frame

function drawRoom(ctx, w, h) {
  const rng = bgRng(20260808);

  // === red-black starry sky gradient (red deeper toward black, slight transparency; red only takes the upper ~1/5; multi-color stops blend softly into pure black) ===
  const sky = ctx.createLinearGradient(0, 0, 0, h * 0.42);
  sky.addColorStop(0, 'rgba(58,8,8,0.86)');
  sky.addColorStop(0.2, 'rgba(46,7,7,0.90)');
  sky.addColorStop(0.4, 'rgba(32,5,5,0.94)');
  sky.addColorStop(0.6, 'rgba(20,3,3,0.97)');
  sky.addColorStop(0.8, 'rgba(10,2,2,0.99)');
  sky.addColorStop(1, '#000000');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, w, h);

  // === small stars (sparse, varying sizes) ===
  const nStars = 70;
  for (let i = 0; i < nStars; i++) {
    const sx = rng() * w;
    const sy = rng() * h * 0.82;
    const sR = 0.6 + rng() * 1.8;
    const a = 0.25 + rng() * 0.5;
    ctx.fillStyle = `rgba(255,240,220,${a.toFixed(2)})`;
    ctx.beginPath();
    ctx.arc(sx, sy, sR, 0, Math.PI * 2);
    ctx.fill();
  }
}

// simple seeded random number generator
function mulberry32Bg(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function bgRng(a) { return mulberry32Bg(a); }
