// chain.js - Rose-red metal chain: front square-frame links + side vertical bars interlocked alternately
// Even links: facing forward (hollow square frame), odd links: side-twisted (narrow vertical bar, ends protruding through the front frame)
// Each star chain has a different length, the floating end is anchored to the star center

function drawChain(ctx, x, topY, length, linkW, linkH, sway, t, idx, starX, starY) {
  // different idx -> different link spacing -> different link count -> different length
  const s = Math.max(7, linkW * 0.55 + idx * 0.8);
  const n = Math.max(3, Math.round(length / s));
  const rng = chainRng(987654 + idx * 131);
  const links = [];
  for (let i = 0; i < n; i++) {
    links.push({
      phaseOff: rng() * Math.PI * 2,
      tilt: (rng() - 0.5) * 0.10,
      darkAmt: rng() * 0.10
    });
  }
  // pass 1: draw all odd links first (side narrow bars, back layer)
  for (let i = 1; i < n; i += 2) {
    const p = linkPos(x, topY, i, n, s, links, sway, t, idx, starX, starY);
    drawSideRing(ctx, p.cx, p.cy, s, p.rot, links[i]);
  }
  // pass 2: then draw all even links (front square-frame links, front layer)
  for (let i = 0; i < n; i += 2) {
    const p = linkPos(x, topY, i, n, s, links, sway, t, idx, starX, starY);
    drawFrontRing(ctx, p.cx, p.cy, s, p.rot, links[i]);
  }
}

function linkPos(x, topY, i, n, s, links, sway, t, idx, starX, starY) {
  const tRatio = i / n;
  const baseY = topY + i * s;
  const L = links[i];
  const interp = i === n - 1 ? 1 : Math.pow(tRatio, 1.6);
  const offX = (starX - x) * interp;
  const endY = topY + n * s;
  const offY = i === n - 1 ? (starY - baseY) : (starY - endY) * interp;
  const linkOff = Math.sin(t * 0.0023 + L.phaseOff + idx * 3.1) * sway * 0.10 * (0.2 + tRatio);
  const bounceOff = Math.sin(t * 0.0016 + L.phaseOff * 1.3 + idx) * sway * 0.08 * tRatio;
  const rot = Math.sin(t * 0.0018 + L.phaseOff) * 0.05 * (0.3 + tRatio) + L.tilt * 0.05;
  return { cx: x + offX + linkOff, cy: baseY + offY + bounceOff, rot };
}

// square-frame ring path (rounded rectangle)
function squareRing(ctx, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(-w / 2 + r, -h / 2);
  ctx.lineTo(w / 2 - r, -h / 2);
  ctx.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
  ctx.lineTo(w / 2, h / 2 - r);
  ctx.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
  ctx.lineTo(-w / 2 + r, h / 2);
  ctx.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
  ctx.lineTo(-w / 2, -h / 2 + r);
  ctx.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
  ctx.closePath();
}

// front link: hollow square frame (width < height), rose-red metallic look
function drawFrontRing(ctx, cx, cy, s, rot, L) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rot);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  const w = s * 0.58, h = s * 0.92;   // vertical: height > width
  const lw = Math.max(2.0, s * 0.18);
  const r = lw * 0.35;  // small corner radius, keeps the square look
  // dark shadow (offset)
  ctx.strokeStyle = '#50101c';
  ctx.lineWidth = lw + 1;
  squareRing(ctx, w, h, r);
  ctx.stroke();
  // main body (rose red)
  ctx.strokeStyle = '#dc3464';
  ctx.lineWidth = lw;
  squareRing(ctx, w, h, r);
  ctx.stroke();
  // rust texture (dotted darker rose marks)
  ctx.strokeStyle = 'rgba(120,30,50,0.30)';
  ctx.lineWidth = lw * 0.40;
  ctx.setLineDash([3, 8]);
  squareRing(ctx, w, h, r);
  ctx.stroke();
  ctx.setLineDash([]);
  // highlight (bright lines on top and left edge, simulating metal reflection)
  ctx.strokeStyle = 'rgba(255,170,200,0.45)';
  ctx.lineWidth = lw * 0.22;
  // top-edge highlight
  ctx.beginPath();
  ctx.moveTo(-w / 2 + r + 2, -h / 2 + 2);
  ctx.lineTo(w / 2 - r - 2, -h / 2 + 2);
  ctx.stroke();
  // left-edge highlight
  ctx.beginPath();
  ctx.moveTo(-w / 2 + 2, -h / 2 + r + 2);
  ctx.lineTo(-w / 2 + 2, h / 2 - r - 2);
  ctx.stroke();
  ctx.restore();
}

// side link: narrow vertical bar (ring seen from the side, narrow and tall, ends protruding past the front frame's top/bottom edges)
function drawSideRing(ctx, cx, cy, s, rot, L) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rot);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  const w = s * 0.24, h = s * 1.5;   // narrow and tall, protrudes past the front frame to interlock
  const lw = Math.max(1.6, s * 0.16);
  const r = lw * 0.30;
  // dark shadow
  ctx.strokeStyle = '#50101c';
  ctx.lineWidth = lw + 1;
  squareRing(ctx, w, h, r);
  ctx.stroke();
  // main body (darker than the front link; the side gets less light)
  ctx.strokeStyle = '#c02850';
  ctx.lineWidth = lw;
  squareRing(ctx, w, h, r);
  ctx.stroke();
  // rust
  ctx.strokeStyle = 'rgba(120,30,50,0.25)';
  ctx.lineWidth = lw * 0.35;
  ctx.setLineDash([2, 6]);
  squareRing(ctx, w, h, r);
  ctx.stroke();
  ctx.setLineDash([]);
  // highlight (left narrow bar)
  ctx.strokeStyle = 'rgba(255,170,200,0.30)';
  ctx.lineWidth = lw * 0.20;
  ctx.beginPath();
  ctx.moveTo(-w / 2 + 2, -h / 2 + r + 2);
  ctx.lineTo(-w / 2 + 2, h / 2 - r - 2);
  ctx.stroke();
  ctx.restore();
}

function chainRng(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
