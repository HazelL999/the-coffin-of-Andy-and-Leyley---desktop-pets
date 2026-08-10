// road.js - Broken road: dark cracked stone slabs horizontally and evenly spaced from left to right
// Style: consistent with the Realm red-black hand-drawn dark style (dark gray slabs + crack texture + dark red edges)
// Structure: the whole road is paved with slabs (first + last + GAP_COUNT+1 total), no longer only the two ends.
//       Arrangement like a checkerboard: all segments on the same horizontal line, evenly spaced, not rotated.
// Collapse mechanic (2026-08-09 Hazel instruction #15):
//   - Each slab can be in normal / collapsed state
//   - After Ashley fully steps across a slab, the slab to its left collapses and disappears (no mark drawn at all)
//   - If Ashley's step speed is not enough to fully cross a slab, that slab is kept until she fully steps over it
//   - Collapsed slabs are no longer drawn (skipped entirely, no pit/mark), the "gap click" mechanic stays the same
// Gaps: after fully collapsing, no mark is drawn (both covered and uncovered are blank), but still clickable.

const ROAD_SEGMENTS = 17;      // segment count (including first/last slabs)
const GAP_COUNT = 16;          // gap count = clickable points (>=10 steps)

let roadLayout = null;

// generate one road layout (called when the chase starts)
function buildRoad(w, h) {
  const rng = mulberry32(90210);
  const segs = [];
  const gapCount = GAP_COUNT;
  const roadW = Math.min(w * 0.042, 56);  // slightly narrower slabs (longer road, saves width)

  // path vertical position: tilts from lower-right to upper-left (stretching upward), simulating the chase heading higher
  // start y = h*0.78 (slightly lower), end y = h*0.42 (stretching upward, roughly the upper-middle of the screen)
  const yStart = h * 0.78;
  const yEnd = h * 0.42;

  // generate GAP_COUNT+1 path points: x evenly spaced left to right, y rises linearly from yStart to yEnd (diagonal up)
  const pts = [];
  for (let i = 0; i <= gapCount; i++) {
    const t = i / gapCount;
    const x = w * (0.08 + t * 0.82);
    const y = yStart + (yEnd - yStart) * t;
    pts.push({ x, y });
  }

  // generate slab segments from the path points: the whole road is paved with slabs (one per segment), all equal width, equal spacing, horizontal
  for (let i = 0; i <= gapCount; i++) {
    const p = pts[i];
    const next = i < gapCount ? pts[i + 1] : null;
    const spacing = next ? (next.x - p.x) : roadW * 1.4;
    // every segment is a full slab: width fills the segment (wide=1.0), height varies (hand-drawn feel)
    segs.push({
      x: p.x,
      y: p.y,
      w: spacing,
      h: roadW * (0.45 + rng() * 0.14),
      rot: 0,
      plankSeed: i * 131 + 7,
      isPlatform: (i === 0 || i === gapCount),
      collapsed: false,   // normal by default; the left slab collapses after Ashley steps over
    });
  }

  roadLayout = {
    segs,
    pts,
    gapCount,
    x0: pts[0].x,
    x1: pts[gapCount].x,
    yBase: yStart,
    yEnd: yEnd,
    roadW,
  };
  return roadLayout;
}

// center and hit radius of the i-th gap (0-based)
function gapCenter(layout, i) {
  const a = layout.segs[i];
  const b = layout.segs[i + 1];
  return {
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
    r: layout.roadW * 0.85,
  };
}

// hit test: returns the hit gap index (0..gapCount-1), otherwise -1
function hitTestRoadGap(layout, mx, my) {
  if (!layout) return -1;
  for (let i = 0; i < layout.gapCount; i++) {
    const g = gapCenter(layout, i);
    const dx = mx - g.x;
    const dy = my - g.y;
    if (dx * dx + dy * dy <= g.r * g.r) return i;
  }
  return -1;
}

// draw one hand-drawn wobbly line (cracks, fissures)
function handLine(ctx, x1, y1, x2, y2, jitter, steps) {
  const n = steps || 4;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  for (let s = 1; s < n; s++) {
    const t = s / n;
    const px = x1 + (x2 - x1) * t + (Math.random() - 0.5) * jitter;
    const py = y1 + (y2 - y1) * t + (Math.random() - 0.5) * jitter;
    ctx.lineTo(px, py);
  }
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

// draw a single slab segment (dark slab + crack texture + dark red edges)
function drawRoadSegment(ctx, seg) {
  const rng = mulberry32(seg.plankSeed);
  const w = seg.w;
  const h = seg.h;
  ctx.save();
  ctx.translate(seg.x, seg.y);
  ctx.rotate(seg.rot);

  // shadow
  ctx.fillStyle = 'rgba(0,0,0,0.45)';
  roundRectPath2(ctx, -w / 2 + 2, -h / 2 + 3, w, h, 6);
  ctx.fill();

  // main body: old slab color - gray with dirty yellow (yellowed and dull, like very old slabs; was #2b2f3a blue -> #8a8376 gray -> now #8f8260 dirty yellow old feel)
  ctx.fillStyle = '#8f8260';
  roundRectPath2(ctx, -w / 2, -h / 2, w, h, 5);
  ctx.fill();
  ctx.strokeStyle = '#0d0f14';
  ctx.lineWidth = 2;
  ctx.stroke();

  // top face light
  ctx.fillStyle = 'rgba(255,255,255,0.05)';
  roundRectPath2(ctx, -w / 2 + 3, -h / 2 + 3, w - 6, h * 0.28, 4);
  ctx.fill();

  // crack texture (hand-drawn short lines)
  ctx.strokeStyle = '#10131a';
  ctx.lineWidth = 1.4;
  for (let k = 0; k < 3; k++) {
    const sx = (rng() - 0.5) * w * 0.7;
    const sy = (rng() - 0.5) * h * 0.7;
    handLine(ctx, sx, sy, sx + (rng() - 0.5) * w * 0.4, sy + (rng() - 0.5) * h * 0.4, 2);
  }

  // dark red edge (echoing the blood-red mood)
  ctx.strokeStyle = 'rgba(120,30,30,0.35)';
  ctx.lineWidth = 1.2;
  roundRectPath2(ctx, -w / 2 + 1.5, -h / 2 + 1.5, w - 3, h - 3, 4);
  ctx.stroke();

  ctx.restore();
}

// gap: no mark is drawn at all (both covered and uncovered are blank)
// the clickable area is kept unchanged by hitTestRoadGap
function drawRoadGap(ctx, layout, i, covered) {
  // draw nothing - completely blank
}

// draw the whole road: draw all slabs in order (collapsed ones are skipped entirely, no mark)
function drawRoad(ctx, layout) {
  if (!layout) return;
  layout.segs.forEach((seg, i) => {
    if (seg.collapsed) return; // collapsed slab completely gone, no mark drawn
    drawRoadSegment(ctx, seg);
  });
}

// rounded rectangle path (used by road.js itself)
function roundRectPath2(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.lineTo(x + w - rr, y);
  ctx.arcTo(x + w, y, x + w, y + rr, rr);
  ctx.lineTo(x + w, y + h - rr);
  ctx.arcTo(x + w, y + h, x + w - rr, y + h, rr);
  ctx.lineTo(x + rr, y + h);
  ctx.arcTo(x, y + h, x, y + rr, rr);
  ctx.lineTo(x, y + rr);
  ctx.arcTo(x, y, x + rr, y, rr);
  ctx.closePath();
}
