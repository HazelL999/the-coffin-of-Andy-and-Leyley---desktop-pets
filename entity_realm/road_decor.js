// road_decor.js - Chase road roadside decor: dead trees
// Hand-drawn horizontal dark style: dead black trees (fences/eye signs removed per request, well-grid fences no longer drawn)
// Depends on road.js's handLine / roundRectPath2 (load order: after road.js)

// Tree positions use fixed seeds (consistent every frame), distributed above and below the road by screen width
function buildTreeSpots(w, h, count) {
  const rng = mulberry32(5551212);
  const spots = [];
  for (let i = 0; i < count; i++) {
    const t = i / count;
    const x = w * (0.06 + t * 0.88 + (rng() - 0.5) * 0.04);
    const side = rng() < 0.55 ? -1 : 1; // -1 above the road, 1 below the road
    // tree roots connect to the ground (chase_bg.js ground starts at h*0.76), and trees above the road don't block it
    const baseY = h * 0.76;
    // taller trees: upper offset increased 1.5x (was 0.16+0.12 / 0.05+0.08)
    const up = baseY - (side === -1 ? h * (0.24 + rng() * 0.18) : h * (0.07 + rng() * 0.12));
    // some trees (about half) have branches facing right: mirror=true flips the branch angles
    const mirror = rng() < 0.5;
    // pick one or two (5th and 7th) as symmetric trees with branches on both sides
    const bothSides = i === 4 || i === 6;
    spots.push({
      x,
      baseY,
      topY: up,
      scale: 0.7 + rng() * 0.7,
      lean: (rng() - 0.5) * 0.12,
      mirror: mirror,
      bothSides: bothSides,
      seed: Math.floor(rng() * 100000),
    });
  }
  return spots;
}

// draw one dead tree: black trunk + forked dead branches, hand-drawn wobbly outline
function drawDeadTree(ctx, spot) {
  const rng = mulberry32(spot.seed);
  const s = spot.scale;
  const baseY = spot.baseY;
  const x = spot.x;
  const m = spot.mirror ? -1 : 1;  // mirror=true flips the initial branch angle (facing right)
  ctx.save();
  ctx.translate(x, baseY);
  ctx.rotate(spot.lean);

  // pure black dead tree silhouette (Hazel asked for all black, consistent with the Realm silhouette style)
  ctx.strokeStyle = '#000000';
  ctx.lineCap = 'round';

  // trunk (thick at bottom, thin at top)
  ctx.lineWidth = 9 * s;
  handLine(ctx, 0, 0, 0, -(baseY - spot.topY) * 0.75, 2.5 * s, 6);

  // branch forks (mirror swaps left/right branches, long branch faces right)
  const branch = (bx, by, ang, len, lw, depth) => {
    const ex = bx + Math.cos(ang) * len;
    const ey = by + Math.sin(ang) * len;
    ctx.lineWidth = lw;
    handLine(ctx, bx, by, ex, ey, 2.2 * s, 4);
    if (depth > 0 && len > 6) {
      branch(ex, ey, ang - 0.55 - rng() * 0.4, len * 0.65, lw * 0.72, depth - 1);
      branch(ex, ey, ang + 0.55 + rng() * 0.4, len * 0.6, lw * 0.72, depth - 1);
    }
  };
  const trunkTop = -(baseY - spot.topY) * 0.75;
  if (spot.bothSides) {
    // symmetric tree: one long branch on each side, Y shape (mirror angle = PI - theta)
    // left long branch -2.4(-137°) -> upper left; mirrored PI+2.4(approx318°) -> upper right
    branch(0, trunkTop, -2.4 - rng() * 0.6, 34 * s, 3.4 * s, 2);   // long -> upper left
    branch(0, trunkTop, Math.PI + 2.4 + rng() * 0.6, 34 * s, 3.4 * s, 2); // long -> upper right
    branch(0, trunkTop, -1.2 - rng() * 0.4, 24 * s, 2.9 * s, 1);   // medium -> upper left
    branch(0, trunkTop, Math.PI + 1.2 + rng() * 0.4, 24 * s, 2.9 * s, 1); // medium -> upper right
  } else if (m === -1) {
    // facing right: mirror of the left-facing tree across the trunk's vertical axis (mirror angle = PI - theta)
    // left-facing branch angles: long -2.4-rng*0.6, medium -1.5-rng*0.4, medium +2.4+rng*0.6, short +1.4+rng*0.5, short -1.0-rng*0.3
    // mirrored: long PI+2.4+rng*0.6(approxupper right), medium PI+1.5+rng*0.4(approxup), medium PI-2.4-rng*0.6(approxlower right), short PI-1.4-rng*0.5(approxlower left), short PI+1.0+rng*0.3(approxupper left)
    branch(0, trunkTop, Math.PI + 2.4 + rng() * 0.6, 34 * s, 3.4 * s, 2);   // long -> upper right
    branch(0, trunkTop, Math.PI + 1.5 + rng() * 0.4, 26 * s, 3.0 * s, 2);   // medium -> up
    branch(0, trunkTop, Math.PI - 2.4 - rng() * 0.6, 30 * s, 3.2 * s, 2);   // medium -> lower right
    branch(0, trunkTop, Math.PI - 1.4 - rng() * 0.5, 22 * s, 2.8 * s, 2);   // short -> lower left
    branch(0, baseY * 0.1, Math.PI + 1.0 + rng() * 0.3, 20 * s, 2.6 * s, 1); // short -> upper left
  } else {
    // facing left: long branch angle negative (upper left), short branch positive (lower right)
    branch(0, trunkTop, -2.4 - rng() * 0.6, 34 * s, 3.4 * s, 2);   // long -> upper left
    branch(0, trunkTop, -1.5 - rng() * 0.4, 26 * s, 3.0 * s, 2);   // medium -> up
    branch(0, trunkTop, 2.4 + rng() * 0.6, 30 * s, 3.2 * s, 2);    // medium -> lower left
    branch(0, trunkTop, 1.4 + rng() * 0.5, 22 * s, 2.8 * s, 2);    // short -> lower right
    branch(0, baseY * 0.1, -1.0 - rng() * 0.3, 20 * s, 2.6 * s, 1); // short -> upper left
  }

  // roots (root fanning out to both sides)
  ctx.lineWidth = 5 * s;
  handLine(ctx, 0, 0, -14 * s, 10 * s, 2, 3);
  handLine(ctx, 0, 0, 12 * s, 9 * s, 2, 3);

  ctx.restore();
}

// draw all roadside decor (layout cached, generated only once)
function drawRoadDecor(ctx, layout, w, h) {
  if (!layout) return;
  if (!layout._treeSpots) layout._treeSpots = buildTreeSpots(w, h, 9);

  // dead trees above/below the road, drawn first (characters and road draw on top)
  layout._treeSpots.forEach((s) => drawDeadTree(ctx, s));
}
