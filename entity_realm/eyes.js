// eyes.js - Three minimalist hand-drawn red eyes (upper arc + lower arc + solid red pupil)
// Click to jump: videos use window.open, text uses an in-page popup

const eyesConfig = [
  { x: 0.28, size: 0.07, yOff: -0.045, seed: 1101, jump: { type: 'murder' } },
  { x: 0.50, size: 0.07, yOff: +0.030, seed: 2202, jump: { type: 'text',  text: '<b>You found this program\'s easter egg.</b><br><br>This is Hazel\'s tribute to the game -- a fan-made<br>vibe-coding creation. Thank you for wandering here.' } },
  { x: 0.72, size: 0.07, yOff: -0.005, seed: 3303, jump: { type: 'chase' } },
];

let eyesHit = [];

function drawEyes(ctx, w, h) {
  eyesHit = [];
  const baseY = h * 0.62; // a bit lower

  eyesConfig.forEach((cfg, idx) => {
    const rng = mulberry32(cfg.seed);
    const ex = cfg.x * w;
    const eyeH = cfg.size * h;
    const eyeW = eyeH * 1.2;
    const ey = baseY - eyeH * 0.1 + cfg.yOff * h; // vertical offset

    eyesHit.push({ x: ex, y: ey, rx: eyeW * 0.52, ry: eyeH * 0.52, idx });

    // brighter glowing red
    const color = '#f03030';

    const wob = (v) => v * (1 + (rng() - 0.5) * 0.12);

    // soft red glow (glowing feel)
    const glowGrad = ctx.createRadialGradient(ex, ey, eyeH * 0.1, ex, ey, eyeW * 0.75);
    glowGrad.addColorStop(0, 'rgba(240,48,48,0.30)');
    glowGrad.addColorStop(0.5, 'rgba(240,48,48,0.12)');
    glowGrad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = glowGrad;
    ctx.beginPath();
    ctx.arc(ex, ey, eyeW * 0.75, 0, Math.PI * 2);
    ctx.fill();

    // upper arc (with slight hand-drawn wobble)
    ctx.strokeStyle = color;
    ctx.lineWidth = eyeH * 0.08;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(ex - eyeW / 2, ey + (rng() - 0.5) * eyeH * 0.04);
    ctx.quadraticCurveTo(
      ex + (rng() - 0.5) * eyeW * 0.08, ey - eyeH * wob(0.55),
      ex + eyeW / 2 + (rng() - 0.5) * eyeW * 0.04, ey + (rng() - 0.5) * eyeH * 0.04
    );
    ctx.stroke();

    // lower arc (with slight hand-drawn wobble)
    ctx.beginPath();
    ctx.moveTo(ex - eyeW / 2, ey + (rng() - 0.5) * eyeH * 0.04);
    ctx.quadraticCurveTo(
      ex + (rng() - 0.5) * eyeW * 0.08, ey + eyeH * wob(0.55),
      ex + eyeW / 2 + (rng() - 0.5) * eyeW * 0.04, ey + (rng() - 0.5) * eyeH * 0.04
    );
    ctx.stroke();

    // solid red pupil (slightly offset, a bit smaller)
    const pr = eyeH * 0.2;
    const px = ex + (rng() - 0.5) * eyeW * 0.06;
    const py = ey + (rng() - 0.5) * eyeH * 0.04;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(px, py, pr, 0, Math.PI * 2);
    ctx.fill();
  });
}

function hitTestEye(mx, my) {
  for (let i = 0; i < eyesHit.length; i++) {
    const e = eyesHit[i];
    const nx = (mx - e.x) / e.rx;
    const ny = (my - e.y) / e.ry;
    if (nx * nx + ny * ny <= 1) return eyesConfig[e.idx];
  }
  return null;
}

function handleEyeClick(mx, my) {
  const hit = hitTestEye(mx, my);
  if (!hit) return false;
  if (hit.jump.type === 'video') {
    window.open(hit.jump.url, '_blank');
  } else if (hit.jump.type === 'text') {
    showEyeText(hit.jump.text);
  } else if (hit.jump.type === 'chase') {
    Chase.start(_realmParams);
  } else if (hit.jump.type === 'murder') {
    MurderScene.start();
  }
  return true;
}

function showEyeText(text) {
  closeEyeText();
  var isEgg = (text.indexOf('easter egg') >= 0);
  const overlay = document.createElement('div');
  overlay.id = 'eye-text-overlay';
  Object.assign(overlay.style, {
    position: 'fixed', left: '0', top: '0', width: '100%', height: '100%',
    background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: '9999', cursor: 'pointer'
  });
  const card = document.createElement('div');
  if (isEgg) {
    Object.assign(card.style, {
      background: 'linear-gradient(135deg, #2a1f1a 0%, #1a1410 100%)',
      border: '2px solid #e8a0c8',
      borderRadius: '16px',
      padding: '40px 48px', maxWidth: '460px',
      color: '#f0dce8',
      fontFamily: '"Georgia", "Segoe UI", serif', fontSize: '15px', lineHeight: '1.9',
      boxShadow: '0 0 60px rgba(232,160,200,0.25), inset 0 0 40px rgba(232,160,200,0.06)',
      cursor: 'default', textAlign: 'center',
      animation: 'eggFade 0.5s ease-out'
    });
    if (!document.getElementById('egg-anim')) {
      const s = document.createElement('style');
      s.id = 'egg-anim';
      s.textContent = '@keyframes eggFade{0%{opacity:0;transform:translateY(20px)}100%{opacity:1;transform:translateY(0)}}';
      document.head.appendChild(s);
    }
  } else {
    Object.assign(card.style, {
      background: '#160606', border: '2px solid #a01818', borderRadius: '14px',
      padding: '32px 40px', maxWidth: '420px', color: '#e8b8b8',
      fontFamily: '"Segoe UI", sans-serif', fontSize: '16px', lineHeight: '1.7',
      boxShadow: '0 8px 40px rgba(160,24,24,0.35)', cursor: 'default',
      textAlign: 'center'
    });
  }
  card.innerHTML = text;
  const closeBtn = document.createElement('div');
  Object.assign(closeBtn.style, {
    marginTop: '24px', cursor: 'pointer', fontSize: '14px',
    borderRadius: '20px', padding: '8px 24px',
    display: 'inline-block', transition: 'opacity 0.2s'
  });
  if (isEgg) {
    Object.assign(closeBtn.style, {
      color: '#e8a0c8', border: '1px solid #e8a0c8',
      background: 'rgba(232,160,200,0.08)'
    });
    closeBtn.textContent = 'Thank you';
  } else {
    Object.assign(closeBtn.style, {
      color: '#ff8a8a', border: '1px solid #a01818'
    });
    closeBtn.textContent = 'Close';
  }
  closeBtn.addEventListener('click', (ev) => { ev.stopPropagation(); closeEyeText(); });
  closeBtn.addEventListener('mouseenter', () => closeBtn.style.opacity = '0.7');
  closeBtn.addEventListener('mouseleave', () => closeBtn.style.opacity = '1');
  card.appendChild(closeBtn);
  overlay.appendChild(card);
  overlay.addEventListener('click', closeEyeText);
  document.body.appendChild(overlay);
}

function closeEyeText() {
  const old = document.getElementById('eye-text-overlay');
  if (old) old.remove();
}
