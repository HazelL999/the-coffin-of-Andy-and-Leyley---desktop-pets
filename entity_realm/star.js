// star.js - Hand-drawn colorful star lamps (strong asymmetry, broken strokes, random rotation, natural hand-drawn feel)
// Layers: white thin star inside colored star (=dark star scaled down proportionally) inside dark star, never intersects

function drawStarLamp(ctx, cx, cy, size, outerColor, innerColor, glowColor, pulse, seed) {
  const rng = mulberry32(seed);

  // each star rotates randomly as a whole (hand-drawn stars don't all face up)
  const rot = (rng() - 0.5) * 0.7;

  // size float reduced (0.03 -> 0.012): weaker, steadier breathing
  const outerR = size * (0.46 + pulse * 0.012);
  const innerR = outerR * 0.36;
  const thickness = outerR * 0.13;

  // strongly asymmetric rays: each length varies a lot (0.8~1.2), angles uneven
  const rayLens = [];
  const angleOffs = [];
  for (let i = 0; i < 5; i++) {
    rayLens.push(0.80 + rng() * 0.42);
    angleOffs.push((rng() - 0.5) * 0.16);
  }
  // corner points also wobble slightly
  const innerLens = [];
  for (let i = 0; i < 5; i++) innerLens.push(0.78 + rng() * 0.44);

  // generate vertices: outer points (ray tips) use rayLens, inner points use innerLens
  const topPts = [];
  for (let i = 0; i < 10; i++) {
    const isOuter = i % 2 === 0;
    const k = Math.floor(i / 2);
    const baseAngle = (i * Math.PI) / 5 - Math.PI / 2 + rot;
    const angle = baseAngle + (isOuter ? angleOffs[k] : (rng() - 0.5) * 0.08);
    const r = outerR * (isOuter ? rayLens[k] : 0.36 * innerLens[k]);
    const jitter = 1 + (rng() - 0.5) * 0.03;
    topPts.push({ x: cx + r * Math.cos(angle) * jitter, y: cy + r * Math.sin(angle) * jitter });
  }
  const sidePts = topPts.map(p => ({ x: p.x, y: p.y + thickness }));

  // === colored star = dark star scaled down proportionally (same shape, same orientation, mathematically guaranteed inside) ===
  const innerScale = 0.82;
  const innerPts = scalePoints(topPts, cx, cy, innerScale);

  // 1. glow (brightness breathes slightly with pulse: glow alpha 0.55~0.85)
  const glowAlpha = 0.55 + pulse * 0.30;
  const glowGrad = ctx.createRadialGradient(cx, cy, outerR * 0.4, cx, cy, outerR * 2.0);
  glowGrad.addColorStop(0, glowColor.replace(/[\d.]+\)$/, glowAlpha.toFixed(2) + ')'));
  glowGrad.addColorStop(0.4, glowColor.replace(/[\d.]+\)$/, (glowAlpha * 0.22).toFixed(2) + ')'));
  glowGrad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glowGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, outerR * 2.0, 0, Math.PI * 2);
  ctx.fill();

  // 2. 3D side
  const sideColor = darkenColor(outerColor, 0.42);
  for (let i = 0; i < 10; i++) {
    const j = (i + 1) % 10;
    const t0 = topPts[i], t1 = topPts[j];
    const s0 = sidePts[i], s1 = sidePts[j];
    if (t0.y > cy || t1.y > cy || s0.y > cy + thickness || s1.y > cy + thickness) {
      ctx.fillStyle = sideColor;
      ctx.beginPath();
      ctx.moveTo(t0.x, t0.y);
      bezierEdge(ctx, t0, t1, rng, 0.05);
      ctx.lineTo(s1.x, s1.y);
      bezierEdge(ctx, s1, s0, rng, 0.05);
      ctx.closePath();
      ctx.fill();
    }
  }

  // 3. bottom star of the side
  ctx.fillStyle = sideColor;
  ctx.beginPath();
  drawHandPolygon(ctx, sidePts, rng, 0.05);
  ctx.fill();

  // 4. outer main star (solid fill, hand-drawn edges + broken-stroke outline)
  ctx.fillStyle = outerColor;
  ctx.beginPath();
  drawHandPolygon(ctx, topPts, rng, 0.05);
  ctx.fill();

  // hand-drawn outline: can't be done in one stroke, split into two segments with gaps
  ctx.strokeStyle = darkenColor(outerColor, 0.18);
  ctx.lineWidth = outerR * 0.030;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  const outline = buildWobblyPath(topPts, rng, 0.06);
  // broken stroke: two segments from different starts create a hand-drawn gap
  const seg1 = outline.slice(0, Math.floor(outline.length * 0.62));
  const seg2 = outline.slice(Math.floor(outline.length * 0.45));
  strokeSegments(ctx, seg1);
  strokeSegments(ctx, seg2);

  // 5. inner colored star: the dark star scaled down proportionally, naturally fully inside the dark star (brightness varies slightly with pulse)
  ctx.fillStyle = lightenColor(innerColor, pulse * 0.10);
  ctx.beginPath();
  drawHandPolygon(ctx, innerPts, rng, 0.05);
  ctx.fill();

  // 6. inner white thin-line star (same outline as the colored star, scaled down proportionally, naturally inside the colored star)
  //    white ring scales randomly 0.6~1.0x relative to the colored star (3/5~1x varies per star, hand-drawn feel)
  const minInnerRay = Math.min(...innerPts.map(p => Math.hypot(p.x - cx, p.y - cy)));
  const fineScale = 0.6 + rng() * 0.4;
  const finePts = scalePoints(innerPts, cx, cy, fineScale);
  // purple/green stars: white ring uses dashes (hand-drawn feel), other stars keep solid lines
  const isPurple = innerColor === '#c88cdc';
  const isGreen = innerColor === '#82e696';
  const useDashLine = isPurple || isGreen;
  ctx.strokeStyle = `rgba(255,255,255,${(0.72 + pulse * 0.28).toFixed(2)})`;
  ctx.lineWidth = outerR * 0.035;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  if (useDashLine) ctx.setLineDash([outerR * 0.09, outerR * 0.07]);
  const fineOutline = buildWobblyPath(finePts, rng, 0.09);
  strokeSegments(ctx, fineOutline.slice(0, Math.floor(fineOutline.length * 0.75)));
  strokeSegments(ctx, fineOutline.slice(Math.floor(fineOutline.length * 0.5)));
  if (useDashLine) ctx.setLineDash([]);

  // 7. inner small decorative lines (hand-drawn short strokes, varying lengths, endpoints clamped inside the colored star)
  ctx.strokeStyle = 'rgba(255,255,255,0.32)';
  ctx.lineWidth = outerR * 0.022;
  for (let i = 0; i < 5; i++) {
    const angle = (i * Math.PI * 2) / 5 - Math.PI / 2 + rot + (rng() - 0.5) * 0.4;
    const len = minInnerRay * (0.12 + rng() * 0.18);
    const startK = 0.20 + rng() * 0.28;
    const startR = minInnerRay * startK;
    const endR = Math.min(startR + len, minInnerRay * 0.80);
    if (endR <= startR) continue;
    const sx = cx + Math.cos(angle) * startR;
    const sy = cy + Math.sin(angle) * startR;
    const ex = cx + Math.cos(angle) * endR;
    const ey = cy + Math.sin(angle) * endR;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    // slightly curved
    const mx = (sx + ex) / 2 + (rng() - 0.5) * len * 0.3;
    const my = (sy + ey) / 2 + (rng() - 0.5) * len * 0.3;
    ctx.quadraticCurveTo(mx, my, ex, ey);
    ctx.stroke();
  }
}

// scale polygon vertices proportionally (around the center)
function scalePoints(pts, cx, cy, scale) {
  return pts.map(p => ({
    x: cx + (p.x - cx) * scale,
    y: cy + (p.y - cy) * scale
  }));
}

// generate asymmetric star vertices (lengths vary a lot, angles uneven) - deprecated (replaced by proportional scaling), kept as backup
function handStarPoints2(cx, cy, outerR, innerR, rng, rot, wobble, maxR, polyCx, polyCy, polyPts) {
  const pts = [];
  const lens = [];
  for (let i = 0; i < 5; i++) lens.push(0.80 + rng() * 0.42);
  const innerLens = [];
  for (let i = 0; i < 5; i++) innerLens.push(0.80 + rng() * 0.40);
  for (let i = 0; i < 10; i++) {
    const isOuter = i % 2 === 0;
    const k = Math.floor(i / 2);
    const baseAngle = (i * Math.PI) / 5 - Math.PI / 2 + rot;
    const angle = baseAngle + (isOuter ? (rng() - 0.5) * 0.16 : (rng() - 0.5) * 0.10);
    let r = (isOuter ? outerR * lens[k] : innerR * innerLens[k]) * (1 + (rng() - 0.5) * wobble);
    // absolute upper clamp
    if (maxR !== undefined && r > maxR) r = maxR;
    // dynamic clamp by direction: compute the max safe distance to the outer star outline along this direction
    if (polyPts) {
      const safe = rayPolygonDist(polyCx, polyCy, angle, polyPts);
      // 0.88 leaves room for hand-drawn outline/bezier protrusion
      r = Math.min(r, safe * 0.88);
    }
    pts.push({ x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) });
  }
  return pts;
}

// distance from the polygon center along angle to the polygon boundary intersection
function rayPolygonDist(cx, cy, angle, poly) {
  const dx = Math.cos(angle);
  const dy = Math.sin(angle);
  let best = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const ax = poly[i].x, ay = poly[i].y;
    const bx = poly[j].x, by = poly[j].y;
    // solve: cx + t*dx = ax + u*(bx-ax); cy + t*dy = ay + u*(by-ay)
    // matrix [[dx, -(bx-ax)], [dy, -(by-ay)]] * [t, u] = [ax-cx, ay-cy]
    const ex = bx - ax, ey = by - ay;
    const det = dx * (-ey) - dy * (-ex);
    if (Math.abs(det) < 1e-9) continue; // parallel
    const t = ((ax - cx) * (-ey) - (ay - cy) * (-ex)) / det;
    if (t < 0) continue;
    const u = (dx * (ay - cy) - dy * (ax - cx)) / det;
    if (u >= 0 && u <= 1) best = Math.min(best, t);
  }
  return best === Infinity ? Math.hypot(poly[0].x - cx, poly[0].y - cy) : best;
}

// draw a hand-drawn polygon with bezier curves
function drawHandPolygon(ctx, pts, rng, curveAmt) {
  for (let i = 0; i < pts.length; i++) {
    const p0 = pts[i];
    const p1 = pts[(i + 1) % pts.length];
    if (i === 0) ctx.moveTo(p0.x, p0.y);
    bezierEdge(ctx, p0, p1, rng, curveAmt);
  }
  ctx.closePath();
}

// build a bent polyline point set (including intermediate control points)
function buildWobblyPath(pts, rng, curveAmt) {
  const out = [];
  for (let i = 0; i < pts.length; i++) {
    const p0 = pts[i];
    const p1 = pts[(i + 1) % pts.length];
    const mx = (p0.x + p1.x) / 2;
    const my = (p0.y + p1.y) / 2;
    const dx = p1.x - p0.x;
    const dy = p1.y - p0.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const nx = -dy / len * len * curveAmt * (rng() - 0.5) * 2;
    const ny = dx / len * len * curveAmt * (rng() - 0.5) * 2;
    out.push({ x: p0.x, y: p0.y });
    out.push({ x: mx + nx, y: my + ny, ctrl: true });
    out.push({ x: p1.x, y: p1.y });
  }
  return out;
}

// segmented stroke (hand-drawn broken-stroke effect)
function strokeSegments(ctx, segs) {
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < segs.length; i++) {
    const p = segs[i];
    if (p.ctrl) {
      const next = segs[i + 1];
      if (next) ctx.quadraticCurveTo(p.x, p.y, next.x, next.y);
    } else {
      if (!started) { ctx.moveTo(p.x, p.y); started = true; }
      else ctx.lineTo(p.x, p.y);
    }
  }
  ctx.stroke();
}

// draw a slightly curved bezier between two points
function bezierEdge(ctx, p0, p1, rng, curveAmt) {
  const mx = (p0.x + p1.x) / 2;
  const my = (p0.y + p1.y) / 2;
  const dx = p1.x - p0.x;
  const dy = p1.y - p0.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / len * len * curveAmt * (rng() - 0.5) * 2;
  const ny = dx / len * len * curveAmt * (rng() - 0.5) * 2;
  ctx.quadraticCurveTo(mx + nx, my + ny, p1.x, p1.y);
}

function darkenColor(rgba, factor) {
  const m = rgba.match(/[\d.]+/g);
  if (!m || m.length < 3) return rgba;
  const r = Math.round(parseFloat(m[0]) * (1 - factor));
  const g = Math.round(parseFloat(m[1]) * (1 - factor));
  const b = Math.round(parseFloat(m[2]) * (1 - factor));
  return `rgb(${r},${g},${b})`;
}

// brighten a color (clamped to 255), used for the star's subtle brightness change while breathing
function lightenColor(rgba, factor) {
  const m = rgba.match(/[\d.]+/g);
  if (!m || m.length < 3) return rgba;
  const r = Math.min(255, Math.round(parseFloat(m[0]) * (1 + factor)));
  const g = Math.min(255, Math.round(parseFloat(m[1]) * (1 + factor)));
  const b = Math.min(255, Math.round(parseFloat(m[2]) * (1 + factor)));
  return `rgb(${r},${g},${b})`;
}

// simple seeded random number generator
function mulberry32(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
