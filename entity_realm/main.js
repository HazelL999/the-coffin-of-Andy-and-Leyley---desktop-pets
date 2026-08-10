// main.js - main animation loop entry

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

let W, H, ceilH;

// Star lamp config: each star is clearly a different size, chain lengths vary, sway amounts differ
// Color reference: purple / light blue / orange / green / blue-purple
const lamps = [
  { x: 0.21, chainLen: 0.35, size: 0.17, sway: 5.0, outerColor: '#3c0f50', innerColor: '#c88cdc', glowColor: 'rgba(180,100,255,0.7)', seed: 42 },
  { x: 0.33, chainLen: 0.20, size: 0.22, sway: 3.4, outerColor: '#0a3260', innerColor: '#8cc8ff', glowColor: 'rgba(100,180,255,0.7)', seed: 97 },
  { x: 0.47, chainLen: 0.32, size: 0.16, sway: 6.2, outerColor: '#502020', innerColor: '#ffb464', glowColor: 'rgba(255,160,60,0.7)', seed: 23 },
  { x: 0.62, chainLen: 0.38, size: 0.24, sway: 2.6, outerColor: '#0a3c1e', innerColor: '#82e696', glowColor: 'rgba(80,220,100,0.7)', seed: 68 },
  { x: 0.79, chainLen: 0.28, size: 0.19, sway: 4.4, outerColor: '#5c1030', innerColor: '#ffb3d9', glowColor: 'rgba(255,140,210,0.7)', seed: 55 },
];

function resize() {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
  ceilH = H * 0.15;
}

let lastFrameT = 0;

function drawFrame(t) {
  ctx.clearRect(0, 0, W, H);

  // chase mode: full-screen switch, no longer draws the Realm scene
  if (Chase.active) {
    if (lastFrameT) {
      const dt = t - lastFrameT;
      // intro countdown
      if (Chase.introTimer > 0) Chase.introTimer = Math.max(0, Chase.introTimer - dt);
      // intro ends -> auto-trigger the opening animation (Ashley runs from slab 2 to slab 6, slabs 2~5 collapse)
      if (Chase.introTimer === 0 && !Chase.openingTriggered && !Chase.opening) {
        Chase.startOpening();
      }
      ChaseUI.tick(dt);
    }
    lastFrameT = t;
    ChaseUI.draw(ctx, W, H);
    requestAnimationFrame(drawFrame);
    return;
  }
  lastFrameT = 0;

  // 1. room background
  drawRoom(ctx, W, H);

  // 2. chains + star lamps
  const baseSize = Math.min(W, H);
  lamps.forEach((l, idx) => {
    const lx = l.x * W;
    const lSize = l.size * baseSize;
    const lChainLen = l.chainLen * H;
    const lTop = -14; // chain top slightly extends past the screen top (top link fully hidden off-screen, visually the chain grows from the top)
    const lCenterY = lTop + lChainLen;

    // chain - link size follows the star size (smaller, thinner chain)
    const chainS = lSize * 0.18;
    // each chain sways differently (hand-drawn feel)
    const sway = l.sway;
    // star lamp - hand-drawn feel, each with a different seed
    const pulse = Math.sin(t * 0.0015 + idx * 1.2) * 0.5 + 0.5;
    // star sway (anchored to the chain end, same frequency/phase)
    const swingX = Math.sin(t * 0.0008 + idx * 1.7) * sway * 0.55;
    const swingY = Math.sin(t * 0.0012 + idx * 2.0) * sway * 0.18;
    const starX = lx + swingX;
    const starY = lCenterY + swingY;
    // chain end anchors the star center (the star is drawn above the chain, covering the chain end)
    // the top attaches directly to the ceiling (no hook ring)
    drawChain(ctx, lx, lTop, lChainLen, chainS, chainS * 0.4, sway, t, idx, starX, starY);

    // star drawn directly over the chain end
    drawStarLamp(ctx, starX, starY, lSize, l.outerColor, l.innerColor, l.glowColor, pulse, l.seed);
  });

  // 2.5 three hand-drawn eyes (only if none has been used yet)
  if (!_eyeUsed) drawEyes(ctx, W, H);

  // 3. vignette (weakened so the bed is clearer)
  const vignetteGrad = ctx.createRadialGradient(W / 2, H / 2, W * 0.55, W / 2, H / 2, W * 0.95);
  vignetteGrad.addColorStop(0, 'rgba(0,0,0,0)');
  vignetteGrad.addColorStop(1, 'rgba(0,0,0,0.28)');
  ctx.fillStyle = vignetteGrad;
  ctx.fillRect(0, 0, W, H);

  requestAnimationFrame(drawFrame);
}

window.addEventListener('resize', resize);

// click dispatch: chase mode first, otherwise eye jumps
var _eyeUsed = false; // once any eye is clicked, no more eye clicks allowed
canvas.addEventListener('click', (ev) => {
  const rect = canvas.getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const my = ev.clientY - rect.top;

  // chase mode active
  if (Chase.active) {
    // intro phase (black screen with white text) does not respond to clicks
    if (Chase.introTimer > 0) return;
    // ending shown -> close the whole Realm page
    if (Chase.ending) {
      Chase.stop();
      window.close();
      return;
    }
    // click a road gap -> place flowers and advance
    if (Chase.layout) {
      const gap = hitTestRoadGap(Chase.layout, mx, my);
      if (gap >= 0) {
        Chase.clickGap(gap);
        return;
      }
    }
    return;
  }

  // murder puzzle active -> let it handle its own clicks
  if (typeof MurderScene !== 'undefined' && MurderScene.active) return;

  // once an eye has been used, block further eye clicks
  if (_eyeUsed) return;
  var hit = hitTestEye(mx, my);
  if (!hit) return;
  _eyeUsed = true;
  // hide the eyes immediately so the player can't see/try the others
  eyesHit = [];

  if (hit.jump.type === 'video') {
    window.open(hit.jump.url, '_blank');
  } else if (hit.jump.type === 'text') {
    showEyeText(hit.jump.text);
    // when the text card closes, close the Realm page
    var origClose = closeEyeText;
    closeEyeText = function() {
      origClose();
      window.close();
    };
  } else if (hit.jump.type === 'chase') {
    Chase.start(_realmParams);
  } else if (hit.jump.type === 'murder') {
    MurderScene.start();
  }
});

resize();

var _params = new URLSearchParams(window.location.search);
var _realmParams = {
  flowerTotal: parseInt(_params.get('flowers')) || 48,
  mental: {
    andrew: parseInt(_params.get('m_andrew')) || 30,
    ashley: parseInt(_params.get('m_ashley')) || 35,
  },
};

requestAnimationFrame(drawFrame);
