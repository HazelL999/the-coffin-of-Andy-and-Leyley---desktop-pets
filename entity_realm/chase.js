// chase.js - Chase mode state machine
// Entry: Chase.start() (triggered by clicking the third eye)
// Rules (continuation of Hazel's 2026-08-09 instructions; this refactor makes movement a smooth animation):
//   - After entering, the full screen switches to the "You are Andrew" scene, not layered on top of the Realm scene
//   - The whole road is paved with stone slabs (17 pieces); Andrew stands on the leftmost slab, Ashley on the 2nd slab
//   - Opening auto-animation (Hazel instruction #17): Ashley shouts "AGHHHH!" on the 2nd slab (0.7s + strong screen shake)
//     -> runs right 3 slabs to the 5th slab (2->3->4->5); slabs 2~4 behind her collapse one by one
//     (the 5th slab under her feet does not collapse)
//   - After that, each click places flowers -> Andrew steps forward 1 slab -> Ashley flees right at the same time (slower and slower)
//   - Core new mechanic: every time Ashley fully steps across a slab, the slab to her left collapses and disappears;
//     if her step speed is not enough to cross a whole slab, that slab is kept until she fully steps over it
// Flower placement rules (continuation of Hazel instruction #9):
//   - Clicking a gap = choosing the "flower spot"; flowers are placed at Andrew's landing spot (flowers first, then Andrew steps on them)
//   - Flowers = slab replacement: only drawn on collapsed slab positions, intact slabs get no flowers
//   - Catch-up check uses screen coordinates (charX); the ending only triggers when caught on screen
// Movement (2026-08-09 refactor):
//   - Andrew smoothly moves to the next slab within 0.55s after each click (easeOutQuad)
//   - Ashley flees right at the same time; each step takes longer (280->500ms, slower and slower), step distance decreases per speed curve
//   - Input is locked while moving (busy=true), unlocked only after the animation ends
// Speed curve (2026-08-09 Hazel instruction #17 fix: opening ends at slab 5, needs 12 slabs to reach 16):
//   - Andrew constant speed: +1 slab per step (unlimited stamina)
//   - Ashley fast first, slow later: per-step ticks +5,+5,+5,+4,+4,+4,+4,+3,+3,+3,+2,+2,+2,+2 (48 ticks total = 12 slabs)
//     After the opening she is at 4 (slab 5); 4 + 12 = 16 (the last slab); step 14 reaches 16, then she stops
//     Andrew +1 per step, step 16 reaches 16 -> caught on step 16 (when flowers run out)
//     48 flowers = 16 steps x 3 flowers
// Stone road (2026-08-09 Hazel instruction #14 change):
//   - GAP_COUNT=16 (was 12), ROAD_SEGMENTS=17
//   - The road tilts from lower-right to upper-left (yStart=0.78h -> yEnd=0.42h), stretching upward and longer
// Ending determination based on mental state thresholds (Hazel instruction #18, real endings):
//   Andrew unstable < 50; Ashley unstable < 40
//   Caught + Andrew<50 and Ashley>=40 -> Andrew wins: play ending/Andrew wins 1..6.png in order
//   Caught + Ashley<40 and Andrew>=50 -> Ashley wins: show ending/Ashley wins 1.png
//   Caught + both unstable (Andrew<50 and Ashley<40) -> random Andrew wins or Ashley wins
//   Caught + both stable (Andrew>=50 and Ashley>=40) -> popup "Luckily it's just a dream."
//   Flowers out before caught -> fail text "You will forever be stepped on by your sister" (fallback, basically never triggers under the curve)

const Chase = {
  // ---- demo values (plan B: hard-coded in frontend, Hazel will bridge data later) ----
  flowerTotal: 48,        // demo backpack flower count (16 times x 3 flowers)
  flowersPerStep: 3,      // each use costs 3 flowers (Hazel A confirmed: keep 3 flowers/use)
  maxSteps: 16,           // 48 / 3 = 16 step limit
  mental: { andrew: 30, ashley: 35 }, // demo: both unstable (easy to preview random endings)

  // movement values (slab units, 1 slab = one stone slab / one gap spacing)
  MAX_POS: GAP_COUNT,     // 16 = rightmost end (Ashley's finish, where Andrew catches her)
  // Ashley per-step speed curve (tick units, makes Ashley stop exactly on the last slab position 16)
  // After the opening Ashley is at 4, still needs 12 slabs (48 ticks) to reach 16; Andrew catches her at 16 in 16 steps
  // Curve design: fast first, slow later; step 14 exactly reaches 16, then she stops
  ashleyCurve: [5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 0, 0],
  // Ashley per-step duration (ms): matches the deceleration curve, first steps faster, later steps slower
  ashleyStepMs: [240, 240, 240, 280, 280, 280, 280, 320, 320, 320, 360, 360, 360, 360, 500, 500],
  // Andrew per-step duration (ms): constant speed
  andrewStepMs: 550,
  // Opening animation parameters (Hazel instruction #17):
  //   - Scream phase: Ashley shouts "AGHHHH!" on slab 2 (openingFrom), lasts screamMs=700ms + strong screen shake
  //   - Run phase: runs right 3 slabs -> the 5th slab (openingTo=4)
  //   - Collapse range: slabs 2~4 behind her (indexes 1,2,3) disappear one by one, slabs 5~6 are kept
  openingFrom: 1,         // Ashley start slab (index 1 = 2nd slab, scream position)
  openingTo: 4,           // Ashley end slab (index 4 = 5th slab), she stands on this one
  openingDelay: 250,      // wait 250ms after the intro black screen before screaming (let the player see the start)
  openingDur: 1200,       // run for 1200ms after the scream ends (easeOutQuad deceleration)
  screamMs: 700,          // scream phase duration (AGHHHH! + screen shake)
  screamShake: 14,        // screen shake amplitude during the scream phase (px)

  // ---- runtime state ----
  active: false,
  introTimer: 0,         // ms of remaining black screen with white text (>0 = intro phase)
  opening: false,        // true = opening auto-animation in progress, clicks are blocked
  openingTriggered: false, // opening animation already triggered (main.js triggers once after intro ends)
  screamPhase: false,    // true = scream phase (big AGHHHH! text + screen shake), only true during the opening
  screenShake: 0,        // screen shake amplitude (px); when >0 each frame draws offset; keeps on during the opening scream
  openingRunT0: 0,       // start time of the opening run phase (set after the scream ends)
  busy: false,           // true = movement animation playing, clicks are blocked
  step: 0,               // steps taken (user click steps, opening does not count)
  flowerSpots: [],       // flower spot per step (Andrew landing path index, 0..GAP_COUNT)
  _clickedGaps: [],      // clicked gap indexes (dedupe, 0..GAP_COUNT-1)
  layout: null,
  andrewPos: 0,          // Andrew logical position (path index, 0 = leftmost, 16 = rightmost)
  ashleyPos: 1,          // Ashley logical position (path index, 1 = 2nd slab, 16 = rightmost)
  // smooth positions for rendering (float slabs; interpolated to the logical target during animation)
  andrewRender: 0,
  ashleyRender: 1,
  // current movement animation in progress (if not null then busy)
  moveAnim: null,        // { aFrom, aTo, sFrom, sTo, t0, dur, aDur, sDur, isOpening? }
  _openingCrossed: 1,    // largest integer slab fully crossed during the opening
  _pendingExpr: null,    // expression applied only after the animation ends
  resolveAfterAnim: false, // resolve only after the animation ends
  andrewExpr: 'mad',
  ashleyExpr: 'mad',
  ending: null,          // null | 'fail' | 'andrew_win' | 'ashley_win' | 'dream'
  endingFrame: 0,        // current frame index of the ending image sequence (0 = first)
  endingFrameT0: 0,      // start time of the current ending image frame (switch to next after a while)
  onEnd: null,           // end callback (used to restore the Realm scene)
  endingShown: false,

  start(opts) {
    if (this.active) return;
    this.active = true;
    this.introTimer = 800;    // 0.8s black screen with white text "You are Andrew" (Hazel instruction #12: shortened from 1.8s)
    this.step = 0;
    this.flowerSpots = [];
    this.andrewExpr = 'mad';
    this.ashleyExpr = 'mad';
    this.ending = null;
    this.endingFrame = 0;
    this.endingFrameT0 = 0;
    this.endingShown = false;
    this.layout = buildRoad(window.innerWidth, window.innerHeight);
    // start: Andrew on the leftmost slab (index 0), Ashley on the 2nd slab (index 1)
    this.andrewPos = 0;
    this.ashleyPos = this.openingFrom;
    this.andrewRender = 0;
    this.ashleyRender = this.openingFrom;
    this.opening = false;
    this.openingTriggered = false;
    this.screamPhase = false;
    this.screenShake = 0;
    this.openingRunT0 = 0;
    this.busy = false;
    this.moveAnim = null;
    this._openingCrossed = this.openingFrom;
    this._pendingExpr = null;
    this.resolveAfterAnim = false;
    this.onEnd = (opts && opts.onEnd) || null;
    this.flowerTotal = (opts && opts.flowerTotal != null) ? opts.flowerTotal : 48;
    this.maxSteps = Math.floor(this.flowerTotal / this.flowersPerStep);
    this.mental = {
      andrew: (opts && opts.mental && opts.mental.andrew != null) ? opts.mental.andrew : 30,
      ashley: (opts && opts.mental && opts.mental.ashley != null) ? opts.mental.ashley : 35,
    };
    loadSprites();
    return true;
  },

  // Opening auto-animation (Hazel instruction #17):
  //   1) Scream phase: Ashley shouts "AGHHHH!" on slab 2 (screamMs=700ms + strong screen shake)
  //   2) Run phase: smoothly runs right 3 slabs to the 5th slab (openingTo=4, 1200ms)
  //   3) Collapse: slabs 2~4 behind her (indexes 1,2,3) collapse one by one; slab 5 is kept
  // The opening costs no flowers and does not advance step; at the end ashleyPos = openingTo = 4 (slab 5).
  // Called once by main.js after the intro ends (openingTriggered prevents re-entry).
  startOpening() {
    if (this.opening || !this.active || this.openingTriggered) return;
    this.opening = true;
    this.openingTriggered = true;
    this.busy = true;                     // lock clicks during the opening
    this.screamPhase = true;              // enter scream phase: show AGHHHH! + screen shake
    this.screenShake = this.screamShake;
    this.screamT0 = performance.now() + this.openingDelay; // wait 250ms before the scream
    this.openingRunT0 = this.screamT0 + this.screamMs;     // run starts after the scream ends
    this._openingCrossed = this.openingFrom;
    this.moveAnim = {
      aFrom: this.andrewRender,           // Andrew does not move
      aTo: this.andrewRender,
      sFrom: this.openingFrom,            // 1
      sTo: this.openingTo,                // 4
      t0: this.openingRunT0,              // the run starts after the scream ends
      dur: this.openingDur,
      aDur: 1,
      sDur: this.openingDur,
      isOpening: true,
    };
  },

  // User clicks a road gap: chooses the flower spot, flowers are placed at Andrew's landing spot, then Andrew steps on them
  // Movement is now a smooth animation: Andrew walks to the landing spot in 0.55s; Ashley flees right at the same time (each step takes longer)
  clickGap(gapIdx) {
    if (!this.active || this.ending || this.opening || this.busy) return false;
    if (this._clickedGaps.includes(gapIdx)) return false; // gap already clicked (dedupe)
    if (this.step >= this.maxSteps) return false;

    this.step++;
    this.flowerTotal -= this.flowersPerStep;

    // Andrew chases right 1 slab at constant speed (unlimited stamina, slab units) -> landing spot is the flower spot
    const aTo = Math.min(this.andrewPos + 1, this.MAX_POS);
    this.andrewPos = aTo;
    this.flowerSpots.push(aTo);
    // Ashley flees slower and slower: decreases per the speed curve (tick units +5..+0, converted to slabs +1.25..+0)
    // Curve is [5,5,4,4,3,3,2,2,1,1,0]; past the curve length she stays at +0 (completely out of stamina)
    const curveIdx = this.step - 1;
    const deltaScale = this.ashleyCurve[curveIdx] != null ? this.ashleyCurve[curveIdx] : 0;
    // ticks -> slabs: 4 ticks = 1 slab; fractional slabs allowed (used for the "fully stepped over" check)
    const deltaGap = deltaScale / 4;
    const sTo = Math.min(this.ashleyPos + deltaGap, this.MAX_POS);
    this.ashleyPos = sTo;

    // start the movement animation (busy locks clicks while moving; render position interpolates smoothly from current to target)
    this.busy = true;
    const aMs = this.andrewStepMs;
    const sMs = this.ashleyStepMs[curveIdx] != null ? this.ashleyStepMs[curveIdx] : 500;
    this.moveAnim = {
      aFrom: this.andrewRender,
      aTo: aTo,
      sFrom: this.ashleyRender,
      sTo: sTo,
      t0: performance.now(),
      dur: Math.max(aMs, sMs),
      aDur: aMs,
      sDur: sMs,
      isOpening: false,
    };

    // randomly switch expressions (applied by tick after the movement ends, avoids mid-animation face changes)
    this._pendingExpr = {
      andrew: pickRandom(SPRITE_FILES.andrew),
      ashley: pickRandom(SPRITE_FILES.ashley),
    };

    // resolve only after the animation ends (screen-coordinate catch-up only makes sense then)
    this.resolveAfterAnim = true;
    return true;
  },

  // Per-frame advance (called by the main.js chase loop): drives the opening animation + click movement animations
  tick(dt) {
    const now = performance.now();
    // ending image sequence auto-play (independent of movement animations, advances every tick)
    this.tickEnding();

    const m = this.moveAnim;
    if (!m) return;

    // ---- opening animation: scream (AGHHHH! + shake) -> Ashley smooth run + slabs collapsing one by one behind her ----
    if (m.isOpening) {
      const nowT = performance.now();
      // scream phase: starts after openingDelay, lasts screamMs; screen keeps shaking during it
      if (this.screamPhase) {
        if (nowT < this.screamT0) {
          this.screenShake = this.screamShake * 0.3; // slight pre-shake while waiting
        } else if (nowT < this.screamT0 + this.screamMs) {
          this.screenShake = this.screamShake;       // strong shake during the scream
        } else {
          this.screamPhase = false;                  // scream ends
          this.screenShake = 0;
        }
        return; // Ashley does not move during the scream phase, waiting for the run
      }
      const ts = Math.min(1, Math.max(0, (nowT - m.t0) / m.sDur));
      this.ashleyRender = m.sFrom + (m.sTo - m.sFrom) * easeOutQuad(ts);
      this.ashleyPos = this.ashleyRender;
      // crossing an integer slab -> the slab she just left collapses; the opening only collapses slabs 2~4 (indexes 1,2,3)
      const crossedNow = Math.floor(this.ashleyRender);
      while (this._openingCrossed < crossedNow) {
        this._openingCrossed++;
        const idx = this._openingCrossed - 1;
        if (idx >= 1 && idx <= 3) {        // slabs 2~4 collapse, slabs 5 and 6 are kept
          this.applyCollapseAfterMove(this._openingCrossed - 1, this._openingCrossed);
        }
      }
      if (ts >= 1) {
        this.ashleyRender = m.sTo;
        this.ashleyPos = m.sTo;
        this.moveAnim = null;
        this.opening = false;
        this.busy = false;
      }
      return;
    }

    // ---- click movement animation: Andrew / Ashley each interpolate ----
    const ta = Math.min(1, Math.max(0, (now - m.t0) / m.aDur));
    const ts = Math.min(1, Math.max(0, (now - m.t0) / m.sDur));
    const ea = easeOutQuad(ta);
    const es = easeOutQuad(ts);
    this.andrewRender = m.aFrom + (m.aTo - m.aFrom) * ea;
    this.ashleyRender = m.sFrom + (m.sTo - m.sFrom) * es;

    if (ta >= 1 && ts >= 1) {
      this.andrewRender = m.aTo;
      this.ashleyRender = m.sTo;
      this.moveAnim = null;
      this.busy = false;
      // after the animation ends: switch expressions + trigger the collapse check (Ashley collapses only after fully stepping over)
      if (this._pendingExpr) {
        this.andrewExpr = this._pendingExpr.andrew;
        this.ashleyExpr = this._pendingExpr.ashley;
        this._pendingExpr = null;
      }
      this.applyCollapseAfterMove(m.sFrom, m.sTo);
      // resolve (screen-coordinate catch-up only triggers the ending)
      if (this.resolveAfterAnim) {
        this.resolveAfterAnim = false;
        this.resolve();
      }
    }

    // ending image sequence auto-play (advances the frame index every frame, ChaseUI draws the current frame)
  },

  // ending image sequence auto-play: switch to the next image every ~1.6s, stay on the last one when done
  // Called by Chase.tick every frame; single-image / pure-text endings do not advance
  tickEnding() {
    if (!this.ending) return;
    const imgs = this.endingImages();
    if (imgs.length <= 1) return; // single image or pure text: no advance
    const perFrame = 1600;        // display duration per image (ms)
    const now = performance.now();
    if (now - this.endingFrameT0 >= perFrame && this.endingFrame < imgs.length - 1) {
      this.endingFrame++;
      this.endingFrameT0 = now;
    }
  },

  // image sequence the current ending should show (for tickEnding and ChaseUI):
  //   'andrew_win' -> [Andrew wins/1.png ... 6.png] (in order)
  //   'ashley_win' -> [Ashley wins/1.png] (single)
  //   'dream' / 'fail' -> no images (pure text)
  endingImages() {
    const aw = [];
    for (let i = 1; i <= 6; i++) aw.push('ending/Andrew wins/' + i + '.png');
    const as = ['ending/Ashley wins/1.png'];
    if (this.ending === 'andrew_win') return aw;
    if (this.ending === 'ashley_win') return as;
    return [];
  },

  // collapse check: after Ashley moves, the slab to the left of the one she "fully stepped over" collapses
  // params from/to: float positions before/after the move (path index ticks, 1 slab = 1 tick)
  applyCollapseAfterMove(from, to) {
    if (!this.layout) return;
    const segs = this.layout.segs;
    // largest integer slab fully crossed (the left side of her current position, floored)
    const crossed = Math.floor(to);
    // collapse target = the slab she just fully left (crossed - 1)
    // if this step was shorter than one slab (to did not cross a new integer), crossed is unchanged -> nothing new collapses
    const toCollapse = crossed - 1;
    if (toCollapse <= 0 || toCollapse >= segs.length) return; // the slab under Andrew (0) never collapses
    const seg = segs[toCollapse];
    if (seg && !seg.collapsed) {
      seg.collapsed = true;
      seg.collapseP = 0.0001; // trigger collapsed state (drawRoad draws the collapse pit)
    }
  },

  // character x position on screen (same formula as ChaseUI.charPos, used for the "caught on screen" check)
  charX(who) {
    if (!this.layout) return 0;
    const n = this.layout.gapCount;
    let pos = who === 'andrew' ? this.andrewRender : this.ashleyRender;
    // slab units: pos is the path index tick (0..12), t = pos / n
    const t = Math.max(0, Math.min(1, pos / n));
    const f = t * n;
    const i = Math.min(n - 1, Math.floor(f));
    const frac = f - i;
    const a = this.layout.pts[i];
    const b = this.layout.pts[i + 1];
    return a.x + (b.x - a.x) * frac;
  },

  // resolve the ending (called after each click movement animation ends)
  // Hazel instruction #18 (2026-08-09):
  //   mental.andrew < 50 -> Andrew unstable; mental.ashley < 40 -> Ashley unstable
  //   after catching up:
  //     Andrew unstable & Ashley stable  -> 'andrew_win' (play Andrew wins images in order)
  //     Ashley unstable & Andrew stable  -> 'ashley_win' (show Ashley wins image)
  //     both unstable                    -> random Andrew wins / Ashley wins
  //     both stable                      -> 'dream' (popup "Luckily it's just a dream.")
  resolve() {
    // screen catch-up check: Andrew's x >= Ashley's x (their sprites touch/overlap) counts as caught
    const reached = this.charX('andrew') >= this.charX('ashley');

    if (reached) {
      const aUnstable = this.mental.andrew < 50;
      const sUnstable = this.mental.ashley < 40;
      if (!aUnstable && !sUnstable) {
        this.ending = 'dream';      // both stable -> "Luckily it's just a dream."
      } else if (aUnstable && sUnstable) {
        // both unstable -> random winner (locked in at resolve time, avoids re-randomizing every frame during playback)
        this.ending = (Math.random() < 0.5) ? 'andrew_win' : 'ashley_win';
      } else if (aUnstable) {
        this.ending = 'andrew_win'; // Andrew unstable & Ashley stable -> Andrew wins
      } else {
        this.ending = 'ashley_win'; // Ashley unstable & Andrew stable -> Ashley wins
      }
      this.endingFrame = 0;         // ending images start from the first
      this.endingFrameT0 = performance.now();
      return;
    }

    // flowers out before caught -> fail
    if (this.flowerTotal <= 0 && this.step >= this.maxSteps) {
      this.ending = 'fail';
      this.endingFrame = 0;
      this.endingFrameT0 = performance.now();
    }
  },

  // remaining flowers
  flowersLeft() {
    return Math.max(0, this.flowerTotal);
  },

  // end the chase, return to the Realm scene (main.js calls this when clicking on the ending)
  stop() {
    if (!this.active) return;
    this.active = false;
    this.opening = false;
    this.openingTriggered = false;
    this.screamPhase = false;
    this.screenShake = 0;
    this.openingRunT0 = 0;
    this.busy = false;
    this.moveAnim = null;
    this.layout = null;
    this.endingFrame = 0;
    this.endingFrameT0 = 0;
    if (this.onEnd) {
      const cb = this.onEnd;
      this.onEnd = null;
      cb();
    }
  },
};

// easeOutQuad: smooth deceleration animation
function easeOutQuad(t) {
  return 1 - (1 - t) * (1 - t);
}

function pickRandom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}
