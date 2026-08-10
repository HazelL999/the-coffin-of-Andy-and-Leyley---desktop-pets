// chase_ui.js - Chase mode main drawing: background, road, decor, characters, UI, endings
// Dependencies: chase.js (state), road.js (road), road_decor.js (decor), sprites.js (sprites), chase_bg.js (background)
// Ending assets (Hazel instruction #18): read images under desktop-pets/entity_realm/ending/
//   - Andrew wins: 1.png ~ 6.png (play the sequential ending in order)
//   - Ashley wins: 1.png (single)
// Path: endings/Andrew wins/i.png etc. - endingSrc() at the bottom builds the full file:// path

// ending image preload (same pattern as sprites.js)
const endingImages = {};      // endingImages['Andrew wins'][i] = Image
let endingLoaded = false;
const endingLoaders = [];
const ENDING_FOLDERS = ['Andrew wins', 'Ashley wins'];
const ENDING_COUNTS = { 'Andrew wins': 6, 'Ashley wins': 1 };

function endingSrc(folder, i) {
  // file:// relative path: from Realm/index.html to desktop-pets/entity_realm/ending/
  return 'file:///C:/Users/admin/desktop-pets/entity_realm/ending/' +
         encodeURIComponent(folder) + '/' + i + '.png';
}

function loadEndingImages() {
  if (endingLoaded) return;
  endingLoaded = true;
  for (const folder of ENDING_FOLDERS) {
    endingImages[folder] = [];
    const count = ENDING_COUNTS[folder];
    for (let i = 1; i <= count; i++) {
      const img = new Image();
      img.src = endingSrc(folder, i);
      endingImages[folder].push(img);
      endingLoaders.push(img);
    }
  }
}

// the image the current ending should show (null if none)
function endingCurrentImage() {
  const C = Chase;
  if (!C.ending) return null;
  const folder = (C.ending === 'andrew_win') ? 'Andrew wins' :
                 (C.ending === 'ashley_win') ? 'Ashley wins' :
                 null; // dream / fail pure text
  if (!folder) return null;
  const arr = endingImages[folder];
  if (!arr || arr.length === 0) return null;
  const idx = Math.min(C.endingFrame, arr.length - 1);
  return arr[idx];
}

const ChaseUI = {
  t: 0, // animation time (advanced by the main loop)

  // draw every frame (called by main.js in chase mode)
  draw(ctx, w, h) {
    const C = Chase;
    if (!C.active) return;

    // preload ending images on first entering chase mode (lazy load, avoids slowing page startup)
    if (!endingLoaded) loadEndingImages();

    // ---- intro phase: black screen with white text ----
    if (C.introTimer > 0) {
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, w, h);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#fff';
      ctx.font = '700 ' + Math.max(30, w * 0.032) + 'px "Segoe UI", sans-serif';
      ctx.fillText('YOU ARE ANDREW', w / 2, h / 2);
      return;
    }

    if (!C.layout) return;

    // ---- screen shake (opening scream phase): the whole frame shakes ----
    ctx.save();
    if (C.screenShake > 0) {
      const shake = C.screenShake;
      ctx.translate((Math.random() - 0.5) * 2 * shake, (Math.random() - 0.5) * 2 * shake);
    }

    // 1. background
    drawChaseBackground(ctx, w, h, this.t);

    // 2. roadside decor (dead trees, fences, eye signs) - drawn first, road and characters cover them
    drawRoadDecor(ctx, C.layout, w, h);

    // 3. road (the road is under the characters)
    drawRoad(ctx, C.layout);

    // 4. characters (move by interpolating along path points; Andrew left, Ashley right; sprite bottoms stand on the slab top edge)
    //    uses render positions (andrewRender/ashleyRender): smoothly interpolated during the opening and click movement animations
    const ap = this.charPos(w, h, C.layout, C.andrewRender, 'andrew');
    const sp = this.charPos(w, h, C.layout, C.ashleyRender, 'ashley');
    const charW = Math.min(w * 0.13, 140);
    const charH = charW; // sprites are square 128x128, width and height the same

    // shadows (near the character standing baseline)
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.beginPath();
    ctx.ellipse(ap.x, ap.groundY + 2, charW * 0.36, charW * 0.08, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(sp.x, sp.groundY + 2, charW * 0.36, charW * 0.08, 0, 0, Math.PI * 2);
    ctx.fill();

    // sprites: center at (groundY - charH/2), bottom exactly touches the slab top edge
    // in Ashley's 128x128 sprite the character is drawn wider than Andrew (about 5% more), scale factor keeps them visually consistent
    const charScale = { andrew: 1.0, ashley: 0.94 };
    drawSprite(ctx, 'andrew', C.andrewExpr, ap.x, ap.groundY - charH / 2, charW * charScale.andrew);
    drawSprite(ctx, 'ashley', C.ashleyExpr, sp.x, sp.groundY - charH / 2, charW * charScale.ashley);

    // 3.5 flowers: placed at Andrew's landing spot (flowers first, then Andrew steps on them)
    //    drawn above the characters (foreground) -> the flowers by his feet peek out from under the sprite, visually Andrew steps on them
    drawRoadFlowers(ctx, C.layout, C.flowerSpots);
    // (name labels removed per Hazel instruction #12: no ANDREW/ASHLEY name tags)

    // ---- opening scream: Ashley shouts "AGHHHH!" on slab 2 (big red text + screen already shaking) ----
    if (C.screamPhase) {
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = '900 ' + Math.max(22, w * 0.03) + 'px "Segoe UI", sans-serif';
      ctx.shadowColor = 'rgba(255,20,20,0.9)';
      ctx.shadowBlur = 24;
      ctx.fillStyle = '#ff2020';
      ctx.fillText('AGHHHH!', sp.x, sp.groundY - charH * 0.9);
      ctx.shadowBlur = 0;
      // faint white outline makes the red text more striking
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(255,230,230,0.85)';
      ctx.strokeText('AGHHHH!', sp.x, sp.groundY - charH * 0.9);
    }

    // 5. hint (not while the chase is running - no text hint, only gaps are clickable)

    // 6. ending
    if (C.ending) this.drawEnding(ctx, w, h);

    ctx.restore(); // restore canvas state before the screen shake
  },

  // character position: interpolate along path points (Andrew / Ashley both move right, can bend up/down)
  // layout pts has GAP_COUNT+1 points (0..GAP_COUNT), t = pos / n (0..1)
  // same formula as Chase.charX: render position and the "caught on screen" check are exactly consistent
  charPos(w, h, layout, pos, who) {
    const n = layout.gapCount;          // 12
    const t = Math.max(0, Math.min(1, pos / n)); // slab units: 0..1
    const f = t * n;                    // path point index range [0..n]
    const i = Math.min(n - 1, Math.floor(f));
    const frac = f - i;
    const a = layout.pts[i];
    const b = layout.pts[i + 1];
    const x = a.x + (b.x - a.x) * frac;
    const y = a.y + (b.y - a.y) * frac;
    // standing baseline: where the sprite bottom should touch = the top edge of the character's slab segment
    // first/last platforms are higher (top edges 348-351), middle segments slightly lower; interpolate smoothly with frac
    const segA = layout.segs[i];
    const segB = layout.segs[i + 1] || segA;
    const topA = segA.y - segA.h / 2;
    const topB = segB.y - segB.h / 2;
    const groundY = topA + (topB - topA) * frac;
    return { x, y, groundY };
  },

  // ending screen
  drawEnding(ctx, w, h) {
    const C = Chase;
    const img = endingCurrentImage();

    if (img && img.complete && img.naturalWidth > 0) {
      // ---- image ending: scaled to fit the window (not stretched full, keeps borders), original ratio preserved ----
      const scale = Math.min(w / img.naturalWidth, h / img.naturalHeight) * 0.7;
      const dw = img.naturalWidth * scale;
      const dh = img.naturalHeight * scale;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
      return;
    }

    // ---- no image (dream / fail): original text ending + darken ----
    const overlay = ctx.createRadialGradient(w / 2, h / 2, w * 0.2, w / 2, h / 2, w * 0.8);
    overlay.addColorStop(0, 'rgba(0,0,0,0.55)');
    overlay.addColorStop(1, 'rgba(0,0,0,0.88)');
    ctx.fillStyle = overlay;
    ctx.fillRect(0, 0, w, h);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const title = this.endingTitle(C.ending);
    const sub = this.endingSub(C.ending);

    ctx.fillStyle = title.color;
    ctx.font = '700 ' + Math.max(28, w * 0.034) + 'px "Segoe UI", sans-serif';
    ctx.shadowColor = 'rgba(0,0,0,0.8)';
    ctx.shadowBlur = 12;
    ctx.fillText(title.text, w / 2, h * 0.42);
    ctx.shadowBlur = 0;

    ctx.fillStyle = 'rgba(240,220,220,0.9)';
    ctx.font = '500 ' + Math.max(16, w * 0.018) + 'px "Segoe UI", sans-serif';
    ctx.fillText(sub, w / 2, h * 0.50);
  },

  endingTitle(ending) {
    switch (ending) {
      case 'fail':        return { text: 'You will forever be stepped on by your sister', color: '#c85050' };
      case 'andrew_win':  return { text: '', color: 'transparent' };
      case 'ashley_win':  return { text: '', color: 'transparent' };
      case 'dream':       return { text: "Luckily it's just a dream.", color: '#d8b060' };
      default:            return { text: 'END', color: '#c85050' };
    }
  },

  endingSub(ending) {
    switch (ending) {
      case 'fail':        return 'The flowers ran out before you reached her.';
      case 'andrew_win':  return '';
      case 'ashley_win':  return '';
      case 'dream':       return 'You wake up in your bed.';
      default:            return '';
    }
  },

  // advance time every frame (called by the main.js chase loop): advance animation time + drive the state machine animations
  tick(dt) {
    this.t += dt;
    Chase.tick(dt);
  },
};

// ============================================================
// Flowers - three small flowers placed at each of Andrew's steps (Hazel asked to restore the flower-placement steps)
// Drawing reuses "Catch a soul" from soul_game/soul_catcher.py:
//   each flower = six widening red petals (no center, no stem), angles i*60+/-8°,
//   length/thickness random (0.65~1.0), petal color #cc2222, slender cylindrical shape,
//   converging from the center, a cluster of three drawn at the gap center (middle higher, sides slightly lower)
// ============================================================

// one widening petal: narrow at the base -> thick and round at the tip, with a rounded head (exact copy of soul_catcher.py _tapered_petal)
function drawPetal(ctx, cx, cy, angleDeg, length, rBase, rTip, fill) {
  const a = angleDeg * Math.PI / 180;
  const ca = Math.cos(a), sa = Math.sin(a);
  const px = -sa, py = ca;   // normal direction
  const bx = cx, by = cy;
  const tx = cx + length * ca, ty = cy + length * sa;
  ctx.beginPath();
  ctx.moveTo(bx - px * rBase, by - py * rBase);
  ctx.lineTo(tx - px * rTip,  ty - py * rTip);
  ctx.lineTo(tx + px * rTip,  ty + py * rTip);
  ctx.lineTo(bx + px * rBase, by + py * rBase);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.arc(tx, ty, rTip, 0, Math.PI * 2);
  ctx.fill();
}

// draw one flower: six widening red petals converging from the center, no center, no stem
function drawFlower(ctx, x, y, size) {
  const rng = mulberry32(Math.floor(x * 7 + y * 13) % 100000);
  ctx.fillStyle = '#cc2222';
  for (let i = 0; i < 6; i++) {
    const angleDeg = i * 60 + (rng() - 0.5) * 16;
    const len = size * 0.45 * (0.65 + rng() * 0.35);
    const rTip = size * 0.16 * (0.8 + rng() * 0.4);
    const rBase = size * 0.10 * (0.7 + rng() * 0.6);
    drawPetal(ctx, x, y, angleDeg, len, rBase, rTip, '#cc2222');
  }
}

// draw a cluster of three small flowers (arranged horizontally; no stems, flowers directly at the gap center)
function drawFlowerCluster(ctx, x, y, baseSize) {
  // three flowers spread horizontally: dx clearly spread (+/-0.55*size), dy roughly equal (approx0, same height on the ground)
  // middle slightly bigger, sides slightly smaller -> looks like a cluster spread sideways
  // (Hazel asked: the original vertical arrangement looked upright, widen the spacing to make it horizontal)
  const offsets = [
    { dx: -baseSize * 0.55, dy:  baseSize * 0.04, sz: 0.42 },  // left
    { dx:  baseSize * 0.00, dy: -baseSize * 0.06, sz: 0.48 },  // middle (slightly bigger)
    { dx:  baseSize * 0.55, dy:  baseSize * 0.04, sz: 0.42 },  // right
  ];
  offsets.forEach((o) => {
    drawFlower(ctx, x + o.dx, y + o.dy, baseSize * o.sz);
  });
}

// draw all placed flowers (flowers = the paving under Andrew's feet)
// input flowerSpots: path index of Andrew's landing spot per step (0..GAP_COUNT)
// flower cluster drawn at Andrew's sprite landing spot (same formula as charX): directly below the sprite, x matches the character
// drawn under the characters -> the sprite covers the flowers, visually Andrew steps on them as he advances
function drawRoadFlowers(ctx, layout, flowerSpots) {
  if (!layout || !flowerSpots) return;
  const segA = layout.segs[0];
  const segB = layout.segs[1];
  const spacing = segB.x - segA.x;
  // smaller flower cluster (Hazel asked to shrink to "about current size"):
  // size = spacing * 0.4 (was 0.8), cap 45 (was 90) -> cluster width about 0.55*size approx 20-25px,
  // only about 1/3 of the gap width, clearly smaller, and won't overlap the slabs/flower clusters beside it
  const size = Math.min(spacing * 0.4, 45);
  // screen x of each step's landing spot (same formula as Chase.charX('andrew'); landing spot at road center)
  const posToX = function (pos) {
    const n = layout.gapCount;
    const t = Math.max(0, Math.min(1, pos / n));
    const f = t * n;
    const i = Math.min(n - 1, Math.floor(f));
    const frac = f - i;
    const a = layout.pts[i];
    const b = layout.pts[i + 1];
    return a.x + (b.x - a.x) * frac;
  };
  flowerSpots.forEach((spotIdx) => {
    // flowers = slab replacement: only drawn on collapsed slab positions (intact slabs don't need flowers)
    const seg = layout.segs[spotIdx];
    if (!seg || !seg.collapsed) return;

    const x = posToX(spotIdx);
    // vertical position: cluster center at the slab's original position (collapse pit), close to the ground
    // sprite bottom is at the slab top edge (the character stands on the slab top edge), cluster center slightly below the top edge
    // -> the tallest flower just peeks out from the sprite's feet/slab seam, visually "stepping on the flowers", never on the character
    const i = Math.min(spotIdx, layout.gapCount - 1);
    const a = layout.segs[i];
    const b = layout.segs[i + 1] || a;
    const topY = (a.y - a.h / 2 + b.y - b.h / 2) / 2 + layout.roadW * 0.55;
    // each cluster bobs irregularly: seeded by the landing spot for a stable random offset (each cluster different, consistent every frame, no jitter)
    // offset amplitude +/-0.35*size (about +/-7px), giving clusters varied heights instead of a rigid look
    // note: the baseline is already below the slab top edge by roadW*0.55 (about 22px); even with jitter up +8px and
    // petals extending up ~10px, the cluster top stays below the sprite's feet -> visually "stepped on",
    // never onto the sprite/slab surface (at 0.34 before, the top still touched the feet at 338, verified)
    const rngF = mulberry32(spotIdx * 7919 + 17);
    const jitter = (rngF() - 0.5) * 0.7 * size;
    drawFlowerCluster(ctx, x, topY + jitter, size);
  });
}
