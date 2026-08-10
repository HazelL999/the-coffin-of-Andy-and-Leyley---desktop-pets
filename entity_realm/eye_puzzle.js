// eye_puzzle.js - First eye: "Who are you?" investigation puzzle
// Flow: black "YOU ARE ANDY" (0.8s, matches chase intro) -> murder site picture
//       -> Q1 Who are you? (Andy / Andrew) -> Q2 hardworker (No)
//       -> Q3 family man (No) -> Q4 drag 3 correct words into slots -> unlock image
// No "click to continue" hints anywhere: the scene picture advances to Q1 on click.
const MurderScene = {
  IMG: 'murder site.png',          // scene image
  COFFIN1: 'You are Andy/open the coffin-1.png',  // first coffin reveal (dark, faceless)
  COFFIN2: 'You are Andy/open the coffin-2.jpg',  // second coffin reveal (face, sorrowful)
  FLASHBACK: 'You are Andy/flashback.jpg',        // memory flashes during the reveal
  active: false,
  phase: 'idle',                   // idle | intro | scene | q1 | q2 | q3 | q4 | q4-pending | done
  img: null,
  shake: 0,                        // terror-shake amplitude (px), set right before terrorShake()
  andrewShakes: 0,                 // Q1: Andrew-click count (>=5 removes the button)
  q2ok: false,
  q3ok: false,
  slots: [null, null, null],       // Q4: filled answers (order-insensitive check)
  correctSet: ['Murderer', 'Brother', 'Lovesick'],
  // Q4 drop slots (fractions of the displayed image) - measured from Hazel's
  // annotated red boxes on murder site.png (1795x1179), box centers:
  //   slot1 body-left (699,533.5) -> (0.3894,0.4525)
  //   slot2 body-upper-right (967.5,430.1) -> (0.5390,0.3648)
  //   slot3 body-lower-right (967,730.3) -> (0.5387,0.6195)
  slotFracs: [{ x: 0.3894, y: 0.4525 }, { x: 0.5390, y: 0.3648 }, { x: 0.5387, y: 0.6195 }],
  overlay: null,
  sceneWrap: null,                 // container that receives the terror shake (image + questions)
  imgRect: { x: 0, y: 0, w: 0, h: 0 },
  unlockShown: false,
  _adv: null,                      // scene -> q1 click listener (removed before re-add)

  start() {
    if (this.active) return;
    this.active = true;
    this.phase = 'intro';
    this.andrewShakes = 0;
    this.shake = 0;
    this.q2ok = this.q3ok = false;
    this.slots = [null, null, null];
    this.unlockShown = false;
    this.img = new Image();
    this.img.src = this.IMG;
    this.buildOverlay();
    this.renderIntro();
    // black "YOU ARE ANDY" for 0.8s (same duration as the third-eye intro)
    setTimeout(() => { if (this.active && this.phase === 'intro') this.showScene(); }, 800);
  },

  stop() {
    this.active = false;
    if (this._adv) { this.overlay.removeEventListener('click', this._adv); this._adv = null; }
    if (this.overlay) { this.overlay.remove(); this.overlay = null; }
  },

  buildOverlay() {
    const ov = document.createElement('div');
    ov.id = 'murder-overlay';
    Object.assign(ov.style, {
      position: 'fixed', left: '0', top: '0', width: '100%', height: '100%',
      background: '#000', zIndex: '9999', overflow: 'hidden',
      fontFamily: '"Segoe UI", sans-serif'
    });
    this.overlay = ov;
    document.body.appendChild(ov);
  },

  addExitButton() {
    const exit = document.createElement('div');
    Object.assign(exit.style, {
      position: 'absolute', top: '14px', right: '18px', zIndex: '60',
      color: '#888', cursor: 'pointer', fontSize: '22px', padding: '6px'
    });
    exit.textContent = '✕';
    exit.title = 'Exit';
    exit.addEventListener('click', (ev) => { ev.stopPropagation(); this.stop(); });
    this.overlay.appendChild(exit);
  },

  renderIntro() {
    this.overlay.innerHTML = '';
    const t = document.createElement('div');
    Object.assign(t.style, {
      position: 'absolute', inset: '0', display: 'flex', alignItems: 'center',
      justifyContent: 'center', color: '#fff', fontSize: 'min(40px, 6vw)',
      fontWeight: '700', letterSpacing: '2px'
    });
    t.textContent = 'YOU ARE ANDY';
    this.overlay.appendChild(t);
    this.addExitButton();
  },

  showScene() {
    this.phase = 'scene';
    this.renderScene();
  },

  renderScene() {
    this.overlay.innerHTML = '';
    this.sceneWrap = null;
    this.addExitButton();

    const img = this.img;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const vw = window.innerWidth, vh = window.innerHeight;
    // fit image (contain), centered, leaving space at the bottom for Q4 options
    const scale = Math.min(vw / iw, (vh * 0.86) / ih);
    const w = iw * scale, h = ih * scale;
    this.imgRect = { x: (vw - w) / 2, y: (vh * 0.04) + (vh * 0.86 - h) / 2, w, h };

    // scene wrapper (target of the terror shake)
    const wrap = document.createElement('div');
    Object.assign(wrap.style, { position: 'absolute', inset: '0', zIndex: '1' });
    this.overlay.appendChild(wrap);
    this.sceneWrap = wrap;

    const imgEl = document.createElement('img');
    imgEl.src = img.src;
    Object.assign(imgEl.style, {
      position: 'absolute', left: this.imgRect.x + 'px', top: this.imgRect.y + 'px',
      width: w + 'px', height: h + 'px', zIndex: '1'
    });
    wrap.appendChild(imgEl);

    const isQuestion = (this.phase !== 'scene' && this.phase !== 'intro' && this.phase !== 'idle');
    if (isQuestion) {
      // dim the picture so the question stands out
      const dim = document.createElement('div');
      Object.assign(dim.style, {
        position: 'absolute', inset: '0', background: 'rgba(0,0,0,0.55)', zIndex: '10'
      });
      wrap.appendChild(dim);

      const qBox = document.createElement('div');
      Object.assign(qBox.style, {
        position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', zIndex: '20'
      });
      wrap.appendChild(qBox);
      this.qBox = qBox;

      if (this.phase === 'q1') this.renderQ1(qBox);
      else if (this.phase === 'q2') this.renderQ2(qBox);
      else if (this.phase === 'q3') this.renderQ3(qBox);
      else if (this.phase === 'q4') this.renderQ4(qBox);
      else if (this.phase === 'q4-pending') this.renderQ4Pending(qBox);
      else if (this.phase === 'done') this.renderDone(qBox);
    } else if (this.phase === 'scene') {
      // scene: picture only, no hint text - a click anywhere advances to Q1
      if (this._adv) this.overlay.removeEventListener('click', this._adv);
      this._adv = () => {
        if (this.active && this.phase === 'scene') { this.phase = 'q1'; this.renderScene(); }
      };
      this.overlay.addEventListener('click', this._adv);
    }
  },

  // violent shake: big translation + rotation + red flash
  // the red gets redder with every wrong Andrew click (Q1): 0.30 -> 0.70
  terrorShake() {
    const amp = Math.max(10, this.shake);
    const wrap = this.sceneWrap;
    if (!wrap) return;
    // red flash layer - escalates with every wrong Andrew click (Q1)
    let redAlpha = 0.45;
    if (this.phase === 'q1' && this.andrewShakes > 0) {
      redAlpha = 0.30 + this.andrewShakes * 0.10;   // 0.40 -> 0.50 -> 0.60 -> 0.70 -> 0.80
    }
    const flash = document.createElement('div');
    Object.assign(flash.style, {
      position: 'absolute', inset: '0', background: 'rgba(180,0,0,' + redAlpha + ')',
      zIndex: '55', pointerEvents: 'none'
    });
    this.overlay.appendChild(flash);
    flash.animate(
      [{ opacity: 0.9 }, { opacity: 0.15 }, { opacity: 0.7 }, { opacity: 0 }],
      { duration: 420, iterations: 1, easing: 'ease-out' }
    );
    setTimeout(() => flash.remove(), 500);
    // violent shake on the scene wrapper
    // violent shake: rapid multi-frame jitter (original feel) + red flash kept
    wrap.animate([
      { transform: 'translate(0,0)' },
      { transform: 'translate(' + (-amp) + 'px,' + (amp * 0.6) + 'px)' },
      { transform: 'translate(' + amp + 'px,' + (-amp * 0.6) + 'px)' },
      { transform: 'translate(' + (-amp * 0.6) + 'px,' + (-amp) + 'px)' },
      { transform: 'translate(' + (amp * 0.7) + 'px,' + (amp * 0.5) + 'px)' },
      { transform: 'translate(' + (-amp * 0.5) + 'px,' + (amp * 0.7) + 'px)' },
      { transform: 'translate(' + (amp * 0.4) + 'px,' + (-amp * 0.4) + 'px)' },
      { transform: 'translate(0,0)' }
    ], { duration: 380 + amp * 10, iterations: 1, easing: 'ease-in-out' });
  },

  // ---- question card: plain grey-black, white text ----
  // opts.flyTop: stay centered ~1s then drift to the top so the scene stays visible (Q4)
  questionCard(qBox, text, buttons, opts) {
    const holder = document.createElement('div');
    Object.assign(holder.style, {
      position: 'absolute', left: '0', top: '0', width: '100%', height: '100%',
      zIndex: '25', pointerEvents: 'none'
    });
    const card = document.createElement('div');
    Object.assign(card.style, {
      position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
      background: '#111111',
      border: '1px solid #555555',
      borderRadius: '6px',
      padding: '32px 48px 28px', textAlign: 'center',
      boxShadow: '0 0 44px rgba(0,0,0,0.95)',
      pointerEvents: 'auto'
    });
    holder.appendChild(card);
    if (opts && opts.flyTop) {
      // hold centered for ~1s, then drift up out of the way (keeps the scene visible)
      holder.animate(
        [
          { top: '0px', offset: 0 },
          { top: '0px', offset: 0.5 },
          { top: '-38vh', offset: 1 }
        ],
        { duration: 2000, iterations: 1, easing: 'ease-in-out', fill: 'forwards' }
      );
    }
    qBox.appendChild(holder);
    const t = document.createElement('div');
    Object.assign(t.style, {
      color: '#f0f0f0', fontSize: 'min(28px, 4.2vw)', fontWeight: '700',
      letterSpacing: '2px', marginBottom: '24px',
      textShadow: '0 2px 8px rgba(0,0,0,0.9)'
    });
    t.textContent = text;
    card.appendChild(t);
    buttons.forEach((b) => {
      const btn = document.createElement('div');
      Object.assign(btn.style, {
        display: 'inline-block', margin: '7px 11px', padding: '12px 36px',
        background: '#0a0a0a', border: '1px solid #666666', color: '#e6e6e6',
        borderRadius: '4px', fontSize: 'min(20px, 3vw)', cursor: 'pointer',
        userSelect: 'none', letterSpacing: '2px',
        transition: 'border-color 0.12s, color 0.12s'
      });
      btn.textContent = b.label;
      btn.addEventListener('mouseenter', () => { btn.style.borderColor = '#cfcfcf'; btn.style.color = '#fff'; });
      btn.addEventListener('mouseleave', () => { btn.style.borderColor = '#666666'; btn.style.color = '#e6e6e6'; });
      btn.addEventListener('click', b.onClick);
      card.appendChild(btn);
    });
    qBox.appendChild(holder);
  },

  // ---- Q1: Who are you? ----
  renderQ1(qBox) {
    qBox.innerHTML = '';
    const buttons = [{ label: 'Andy', onClick: () => this.answerQ1('Andy') }];
    if (this.andrewShakes < 5) buttons.push({ label: 'Andrew', onClick: () => this.answerQ1('Andrew') });
    this.questionCard(qBox, 'Who are you?', buttons);
  },

  answerQ1(answer) {
    if (answer === 'Andy') {
      this.shake = 0;
      this.phase = 'q2';
      this.renderScene();
    } else {
      // wrong: escalating violent shake; the 5th click removes the Andrew button
      this.andrewShakes++;
      this.shake = 14 + this.andrewShakes * 8;   // 22 -> 30 -> 38 -> 46 -> 54
      this.renderScene();
      this.terrorShake();
    }
  },

  // ---- Q2 / Q3 ----
  renderQ2(qBox) {
    qBox.innerHTML = '';
    this.questionCard(qBox, 'Andrew Graves is a hardworker.', [
      { label: 'Yes', onClick: () => this.answerYesNo('q2', 'Yes') },
      { label: 'No', onClick: () => this.answerYesNo('q2', 'No') }
    ]);
  },

  renderQ3(qBox) {
    qBox.innerHTML = '';
    this.questionCard(qBox, 'Andrew Graves is a family man.', [
      { label: 'Yes', onClick: () => this.answerYesNo('q3', 'Yes') },
      { label: 'No', onClick: () => this.answerYesNo('q3', 'No') }
    ]);
  },

  answerYesNo(which, label) {
    const correct = 'No'; // both Q2 and Q3 are answered "No"
    if (label === correct) {
      if (which === 'q2') this.q2ok = true;
      else this.q3ok = true;
      if (which === 'q2') {
        this.phase = 'q3';
      } else {
        this.phase = 'q4';
      }
      this.renderScene();
    } else {
      // wrong -> violent shake, stay on the question
      this.shake = 20;
      this.renderScene();
      this.terrorShake();
    }
  },

  // ---- Q4: drag words into slots ----
  renderQ4(qBox) {
    qBox.innerHTML = '';
    this.questionCard(qBox, 'Andrew Graves is a ______', [], { flyTop: true });

    // dashed drop slots over the body outline - appear AFTER the title card has
    // drifted up (title flyTop takes ~2s), so they don't clash with the scene
    const slotsRow = document.createElement('div');
    slotsRow.id = 'q4-slots';
    Object.assign(slotsRow.style, { position: 'absolute', zIndex: '30', opacity: '0' });
    this.slotEls = [];
    this.slotFracs.forEach((sf, i) => {
      const s = document.createElement('div');
      const sz = Math.max(84, this.imgRect.w * 0.115); // a bit larger than the red boxes for easier dropping
      const sh = sz * 0.72;
      Object.assign(s.style, {
        position: 'absolute', left: (this.imgRect.x + sf.x * this.imgRect.w - sz / 2) + 'px',
        top: (this.imgRect.y + sf.y * this.imgRect.h - sh / 2) + 'px',
        width: sz + 'px', height: sh + 'px',
        border: '2px dashed #e8e8e8', borderRadius: '8px', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 'min(15px, 2vw)', background: 'rgba(0,0,0,0.30)'
      });
      s.textContent = this.slots[i] || '';
      s.dataset.slot = i;
      s.addEventListener('dragover', (ev) => { ev.preventDefault(); });
      s.addEventListener('drop', (ev) => { ev.preventDefault(); this.dropSlot(i, ev); });
      slotsRow.appendChild(s);
      this.slotEls.push(s);
    });
    qBox.appendChild(slotsRow);
    // fade the slots in slowly after the title has drifted away (~2s flyTop + 900ms fade)
    slotsRow.animate(
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: 900, delay: 2000, iterations: 1, easing: 'ease-out', fill: 'forwards' }
    );

    // draggable word options at the bottom
    const opts = ['Murderer', 'Student', 'Good Person', 'Lovesick', 'Brother'];
    const bar = document.createElement('div');
    Object.assign(bar.style, {
      position: 'absolute', left: '0', bottom: '0', width: '100%', padding: '16px 0',
      display: 'flex', gap: '14px', justifyContent: 'center', background: 'rgba(0,0,0,0.6)',
      zIndex: '35'
    });
    opts.forEach((w) => {
      const c = document.createElement('div');
      Object.assign(c.style, {
        padding: '10px 20px', border: '1px solid #aaa', color: '#fff', borderRadius: '8px',
        cursor: 'grab', background: '#111', fontSize: 'min(17px, 2.4vw)'
      });
      c.textContent = w;
      c.draggable = true;
      c.addEventListener('dragstart', (ev) => { ev.dataTransfer.setData('text/plain', w); });
      bar.appendChild(c);
    });
    qBox.appendChild(bar);
  },

  dropSlot(i, ev) {
    const w = ev.dataTransfer.getData('text/plain');
    this.slots[i] = w;
    this.slotEls[i].textContent = w;
    this.checkQ4();
  },

  checkQ4() {
    const filled = this.slots.filter(Boolean);
    if (filled.length < 3) return;
    // correct set must match regardless of order (wrong answer in wrong slot still ok as long as
    // the three correct words are present)
    const ok = this.correctSet.every((c) => filled.includes(c)) && filled.length === 3;
    if (ok) {
      this.phase = 'done';
      this.renderScene();
    } else {
      // wrong: clear and shake
      this.shake = 14;
      this.slots = [null, null, null];
      this.renderScene();
      this.terrorShake();
    }
  },

  // ---- done: reveal the coffin in two steps (coffin-1 then coffin-2) with a slow,
  // heavy, sorrowful mood; the flashback memory flashes 0.3s and 0.5s.
  renderDone(qBox) {
    qBox.innerHTML = '';
    const S = this;
    const doc = qBox.ownerDocument;

    const box = doc.createElement('div');
    Object.assign(box.style, {
      position: 'absolute', inset: '0', background: '#000',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      overflow: 'hidden', zIndex: '40'
    });
    qBox.appendChild(box);

    const stage = doc.createElement('div');
    Object.assign(stage.style, {
      position: 'relative', width: '100%', height: '100%',
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    });
    box.appendChild(stage);

    // first reveal: coffin-1 (faceless, curled-up figure)
    const img1 = doc.createElement('img');
    img1.src = S.COFFIN1;
    Object.assign(img1.style, {
      position: 'absolute', margin: 'auto', maxWidth: '92%', maxHeight: '94%',
      objectFit: 'contain', zIndex: '3', transformOrigin: '50% 100%',
      filter: 'brightness(0.92) contrast(1.06) saturate(0.85)'
    });
    stage.appendChild(img1);

    // second reveal: coffin-2 (sorrowful face) - hidden until img1 fades
    const img2 = doc.createElement('img');
    img2.src = S.COFFIN2;
    Object.assign(img2.style, {
      position: 'absolute', margin: 'auto', maxWidth: '92%', maxHeight: '94%',
      objectFit: 'contain', zIndex: '3', opacity: '0', transformOrigin: '50% 100%',
      filter: 'brightness(0.9) contrast(1.08) saturate(0.82)'
    });
    stage.appendChild(img2);

    // memory flashback layer
    const f = doc.createElement('img');
    f.src = S.FLASHBACK;
    Object.assign(f.style, {
      position: 'absolute', inset: '0', margin: 'auto', maxWidth: '92%', maxHeight: '94%',
      objectFit: 'contain', zIndex: '4', opacity: '0', pointerEvents: 'none',
      filter: 'brightness(0.85) contrast(1.1) saturate(0.7)'
    });
    stage.appendChild(f);

    // heavy vignette that deepens the sorrowful dread
    const vig = doc.createElement('div');
    Object.assign(vig.style, {
      position: 'absolute', inset: '0', zIndex: '5', pointerEvents: 'none',
      background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.55) 78%, rgba(0,0,0,0.92) 100%)'
    });
    stage.appendChild(vig);

    // 1) coffin-1 emerges from the darkness: slow rising from the deep,
    // growing slightly as it surfaces (like a memory/soul drifting up)
    img1.animate(
      [
        { opacity: 0, transform: 'translateY(6%) scale(0.92)', offset: 0 },
        { opacity: 0, transform: 'translateY(6%) scale(0.92)', offset: 0.14 },
        { opacity: 0.9, transform: 'translateY(3%) scale(0.95)', offset: 0.4 },
        { opacity: 1, transform: 'translateY(0) scale(1)', offset: 1 }
      ],
      { duration: 1500, iterations: 1, easing: 'ease-out', fill: 'forwards' }
    );
    // subtle dread drift after it fully surfaces (slow upward sway)
    img1.animate(
      [
        { transform: 'translateY(0)' },
        { transform: 'translateY(-8px)' },
        { transform: 'translateY(0)' }
      ],
      { duration: 2000, delay: 1600, iterations: 1, easing: 'ease-in-out', fill: 'forwards' }
    );

    // 2) coffin-1 sinks away, coffin-2 slowly surfaces
    img1.animate(
      [{ opacity: 1 }, { opacity: 0 }],
      { duration: 600, delay: 2300, iterations: 1, easing: 'ease-in', fill: 'forwards' }
    );
    img2.animate(
      [
        { opacity: 0, transform: 'scale(0.94)' },
        { opacity: 0.25, transform: 'scale(0.965)' },
        { opacity: 1, transform: 'scale(1)' }
      ],
      { duration: 1300, delay: 2400, iterations: 1, easing: 'ease-out', fill: 'forwards' }
    );

    // 3) sorrowful breathing: coffin-2 slowly swells then settles
    img2.animate(
      [
        { transform: 'scale(1)' },
        { transform: 'scale(1.012)' },
        { transform: 'scale(1)' }
      ],
      { duration: 4200, delay: 3900, iterations: 1, easing: 'ease-in-out', fill: 'forwards' }
    );

    // 4) memory flashes: 0.3s and 0.5s, with a shuddering jitter on the flash layer
    const flashTimes = [3200, 5100];
    const flashDurs = [300, 500];
    flashTimes.forEach((t, i) => {
      setTimeout(() => {
        f.animate(
          [
            { opacity: 0, transform: 'translate(0,0) scale(1)' },
            { opacity: 0.95, transform: 'translate(2px,-2px) scale(1.02)', offset: 0.2 },
            { opacity: 0.9, transform: 'translate(-2px,2px) scale(1.015)', offset: 0.5 },
            { opacity: 0.6, transform: 'translate(1px,-1px) scale(1.01)', offset: 0.8 },
            { opacity: 0, transform: 'translate(0,0) scale(1)', offset: 1 }
          ],
          { duration: flashDurs[i], iterations: 1, easing: 'linear' }
        );
      }, t);
    });

    // 5) after the last flash, coffin-2 holds for 0.3s, then snaps to total black
    //    (like switching off the light); a click on the black screen exits the realm.
    const LAST_FLASH_END = flashTimes[1] + flashDurs[1];   // 5600ms
    const BLACK_AT = LAST_FLASH_END + 300;                 // hold coffin-2 for 0.3s
    const black = doc.createElement('div');
    Object.assign(black.style, {
      position: 'absolute', inset: '0', zIndex: '50', pointerEvents: 'none',
      background: '#000', opacity: '0'
    });
    stage.appendChild(black);
    // sudden blackout - like a light switch being flipped off
    black.animate(
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: 60, delay: BLACK_AT, iterations: 1, easing: 'linear', fill: 'forwards' }
    );
    // after the blackout, a white farewell text fades in on the black screen
    const farewell = doc.createElement('div');
    Object.assign(farewell.style, {
      position: 'absolute', inset: '0', zIndex: '51',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', textAlign: 'center', gap: '18px',
      color: '#ffffff', opacity: '0', pointerEvents: 'none',
      fontFamily: '"Segoe UI", sans-serif', padding: '0 8vw'
    });
    const line1 = doc.createElement('div');
    line1.textContent = "That's you, Andrew Graves, who died in the coffin.";
    Object.assign(line1.style, { fontSize: 'min(20px, 2.9vw)', fontWeight: '500', letterSpacing: '1px' });
    const line2 = doc.createElement('div');
    line2.textContent = "Poor little Andy, farewell to your Andrew.";
    Object.assign(line2.style, { fontSize: 'min(20px, 2.9vw)', fontWeight: '500', opacity: '1', letterSpacing: '1px' });
    farewell.appendChild(line1);
    farewell.appendChild(line2);
    stage.appendChild(farewell);
    farewell.animate(
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: 900, delay: BLACK_AT + 60 + 200, iterations: 1, easing: 'ease-out', fill: 'forwards' }
    );
    // once black, a click exits the realm
    setTimeout(() => {
      if (!S.active) return;
      const exitOnce = (ev) => { ev.stopPropagation(); box.removeEventListener('click', exitOnce); S.stop(); };
      box.addEventListener('click', exitOnce);
    }, BLACK_AT + 60 + 100);
  }
};