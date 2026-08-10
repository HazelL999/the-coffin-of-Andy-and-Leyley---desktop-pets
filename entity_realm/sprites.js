// sprites.js - Preload Andrew / Ashley expression sprites (local 01.png copies)
// Each expression is a 128x128 sprite, mapped to the file basename to avoid enumerating paths repeatedly
// Asset directory: sprites/ (same level as index.html), read-only, does not modify the source project

const SPRITE_FILES = {
  andrew: ['mad', 'fuck', 'furious', 'pissed_off'],
  ashley: ['are_u_serious', 'crying', 'endure', 'mad', 'no_way', 'shouting', 'scolding', 'unsatisfied'],
};

const spriteImages = { andrew: {}, ashley: {} };
let spritesLoaded = false;
const spriteLoaders = [];

function loadSprites() {
  if (spritesLoaded) return;
  spritesLoaded = true;
  for (const who of ['andrew', 'ashley']) {
    for (const name of SPRITE_FILES[who]) {
      const img = new Image();
      img.src = 'sprites/' + who + '_' + name + '.png';
      spriteImages[who][name] = img;
      spriteLoaders.push(img);
    }
  }
}

function drawSprite(ctx, who, name, cx, cy, targetW) {
  const img = spriteImages[who][name];
  if (!img || !img.complete || img.naturalWidth === 0) return;
  const scale = targetW / img.naturalWidth;
  const w = img.naturalWidth * scale;
  const h = img.naturalHeight * scale;
  ctx.drawImage(img, cx - w / 2, cy - h / 2, w, h);
}

// fallback in case user scripts load before this file (normally won't happen)
if (typeof window !== 'undefined') {
  window.addEventListener('load', loadSprites);
}
