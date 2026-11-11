/* Веб-версия терминального аквариума: та же логика, что в aquarium.py,
 * но рисуется через three.js (WebGL). Мир считается в «клетках» терминала,
 * поэтому скорости и размеры совпадают с консольной версией.
 * Тексты и рисунки берутся из data.js (генерирует web/build_data.py). */
(() => {
  'use strict';

  const D = window.AQUA;
  const C = D.const;
  const SPECIES = Object.fromEntries(D.species.map(s => [s.name, s]));
  const NAMES = D.species.map(s => s.name);
  const STORE_KEY = 'aquarium.counts';

  // --- случайность ---------------------------------------------------------
  const rnd = Math.random;
  const uniform = (a, b) => a + rnd() * (b - a);
  const randint = (a, b) => a + Math.floor(rnd() * (b - a + 1));
  const choice = arr => arr[Math.floor(rnd() * arr.length)];
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const shuffle = arr => {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  };

  // --- зеркало рисунков (как _mirror в Python) -----------------------------
  const MIRROR = { '<': '>', '>': '<', '(': ')', ')': '(', '[': ']', ']': '[',
    '{': '}', '}': '{', '/': '\\', '\\': '/', '`': "'", "'": '`' };
  const widthOf = lines => Math.max(...lines.map(l => l.length));
  const mirror = lines => {
    const w = widthOf(lines);
    return lines.map(l => [...l.padEnd(w)].reverse().map(c => MIRROR[c] ?? c).join(''));
  };

  // --- рыбы ------------------------------------------------------------------
  const fishLines = f => (f.dx > 0 ? SPECIES[f.species].right : SPECIES[f.species].left);
  const fishWidth = f => widthOf(fishLines(f));
  const bounds = (f, W, H) => [Math.max(0, W - fishWidth(f)), Math.max(1, H - 4 - fishLines(f).length)];

  function spawnFish(counts, W, H) {
    let nicks = [];
    const out = [];
    for (const [name, count] of Object.entries(counts)) {
      for (let i = 0; i < count; i++) {
        if (!nicks.length) nicks = shuffle(D.nicks.slice());
        const f = { species: name, x: 0, y: 1, dx: choice([1, -1]),
          speed: uniform(...SPECIES[name].speed), color: randint(1, 6), nick: nicks.pop(),
          speech: '', speechTtl: 0, mood: '' };
        const [mx, my] = bounds(f, W, H);
        f.x = uniform(0, mx);
        f.y = randint(1, my);
        out.push(f);
      }
    }
    return out;
  }

  /** Двигает рыбу; true — только что вернулась домой после испуга. */
  function stepFish(f, W, H, dt, food) {
    const [maxX, maxY] = bounds(f, W, H);
    if (f.mood === 'flee') {
      f.x += f.dx * C.FLEE_SPEED * dt;
      const hide = fishWidth(f) + f.nick.length + 2;
      f.x = clamp(f.x, -hide, W + hide);
      f.y = clamp(f.y, 1, maxY);
      return false;
    }
    if (f.mood === 'return') {
      if (f.x >= 0 && f.x <= maxX) { f.mood = ''; return true; }
      f.dx = f.x > maxX ? -1 : 1;
      const step = Math.max(f.speed * C.RETURN_SPEED_FACTOR, C.MIN_RETURN_SPEED) * dt;
      f.x = f.dx > 0 ? Math.min(f.x + step, 0) : Math.max(f.x - step, maxX);
      f.y = clamp(f.y, 1, maxY);
      return false;
    }
    if (food && Math.abs(food[0] - f.x) <= C.FOOD_RADIUS) {
      f.dx = food[0] >= f.x ? 1 : -1;
      const step = f.speed * dt;
      f.x += clamp(food[0] - f.x, -step, step);
      f.y += clamp(food[1] - f.y, -step, step);
    } else {
      f.x += f.dx * f.speed * dt;
    }
    if (f.x >= maxX) { f.x = maxX; f.dx = -1; } else if (f.x <= 0) { f.x = 0; f.dx = 1; }
    f.y = clamp(f.y, 1, maxY);
    return false;
  }

  function relayout(fish, oldW, W, H) {
    for (const f of fish) {
      const [mx, my] = bounds(f, W, H);
      f.x = Math.min(mx, f.x * W / Math.max(1, oldW));
      f.y = randint(1, my);
    }
  }

  // --- корм и пузырьки -------------------------------------------------------
  const touches = (f, food) => f.x <= food[0] && food[0] < f.x + fishWidth(f)
    && Math.round(f.y) <= Math.round(food[1]) && Math.round(food[1]) < Math.round(f.y) + fishLines(f).length;

  function feedStep(foods, fish, H, dt) {
    const eaters = [];
    const kept = [];
    for (const food of foods) {
      food[1] += C.FOOD_FALL * dt;
      if (food[1] >= H - 3) continue;
      const eater = fish.find(f => touches(f, food));
      if (!eater) kept.push(food);
      else if (!eaters.includes(eater)) eaters.push(eater);
    }
    foods.splice(0, foods.length, ...kept);
    return eaters;
  }

  function nearestFood(f, foods) {
    const near = foods.filter(fd => Math.abs(fd[0] - f.x) <= C.FOOD_RADIUS);
    if (!near.length) return null;
    return near.reduce((a, b) => (Math.abs(a[0] - f.x) + Math.abs(a[1] - f.y)
      <= Math.abs(b[0] - f.x) + Math.abs(b[1] - f.y) ? a : b));
  }

  function nearestFish(fish, x) {
    const near = fish.filter(f => Math.abs(f.x - x) <= C.FOOD_RADIUS);
    return near.length ? near.reduce((a, b) => (Math.abs(a.x - x) <= Math.abs(b.x - x) ? a : b)) : null;
  }

  function bubbleStep(bubbles, fish, dt) {
    for (const b of bubbles) b[1] -= C.BUBBLE_RISE * dt;
    bubbles.splice(0, bubbles.length, ...bubbles.filter(b => b[1] >= 1));
    for (const f of fish) {
      if (bubbles.length < C.MAX_BUBBLES && rnd() < C.BUBBLE_RATE * dt) {
        bubbles.push([f.x + (f.dx > 0 ? fishWidth(f) - 1 : 0), f.y]);
      }
    }
  }

  // --- реплики ---------------------------------------------------------------
  function pickPhrase(f, event) {
    const pool = (D.phrases[event] || []).slice();
    let lore = ((D.speciesPhrases[f.species] || {})[event] || []).slice();
    if (event === 'idle' || event === 'poke') lore = lore.concat(D.nickPhrases[f.nick] || []);
    pool.push(...lore, ...lore);
    return pool.length ? choice(pool) : '';
  }

  function say(f, event) {
    f.speech = pickPhrase(f, event);
    f.speechTtl = f.speech ? C.SPEECH_TTL : 0;
  }

  function speechStep(fish, dt) {
    for (const f of fish) {
      if (f.speech && (f.speechTtl -= dt) <= 0) { f.speech = ''; f.speechTtl = 0; }
    }
    const speakers = fish.filter(f => f.speech).length;
    const silent = fish.filter(f => !f.speech);
    if (silent.length && speakers < C.MAX_SPEAKERS && rnd() < C.SPEECH_RATE * dt) {
      say(choice(silent), 'idle');
    }
  }

  // --- пасхалка: шквал хуёв с казаками ----------------------------------------
  function dickArt(s) {
    const veins = '  ~~   ~    ~~~  ~   '.repeat(Math.floor(s / 20) + 1).slice(0, s);
    return [
      '   .-"""-.',
      "  /   '   \\" + '_'.repeat(s + 1) + '.---"""---.',
      " |  ,   '  |" + ' '.repeat(s) + '|           `.',
      " |   '  ,  |" + veins + '|          -  )',
      "  \\  '    / " + ' '.repeat(s) + "|           ,'",
      "  /  ,  ' \\" + '_'.repeat(s + 1) + "`---...---'",
      " |  '   ,  |",
      '  \\   ,   /',
      "   `-...-'",
    ];
  }
  const dickArtMedium = s => [
    '  .-.',
    ' (   )' + '_'.repeat(s) + '.--.',
    '  ) (' + '~ '.repeat(Math.floor(s / 2)) + ' '.repeat(s % 2) + ' |   `.',
    ' (   )' + '_'.repeat(s) + '|  - )',
    "  `-'" + ' '.repeat(s + 1) + "`--'",
  ];
  const dickArtSmall = s => ['8' + '='.repeat(s) + 'D'];

  const riderFrames = kind => (kind === 'small' ? D.tinyRiderFrames : D.riderFrames);
  const riderHeight = kind => riderFrames(kind)[0].length;
  const riderWidth = kind => Math.max(...riderFrames(kind).flat().map(l => l.length));

  function art(kind, W) {
    if (kind === 'big') return dickArt(randint(Math.max(12, W >> 2), Math.max(20, W >> 1)));
    if (kind === 'medium') return dickArtMedium(randint(10, Math.max(12, W >> 2)));
    return dickArtSmall(randint(3, 12));
  }

  function spawnMonster(W, H, kind, dx, delay) {
    const a = art(kind, W);
    const lines = dx > 0 ? a : mirror(a);
    const w = widthOf(lines);
    const top = riderHeight(kind) + (kind === 'small' ? 2 : 1);
    const bottom = H - 4 - lines.length;
    const y = bottom < top ? top : kind === 'big' ? (top + bottom) >> 1 : randint(top, bottom);
    const widths = a.map(l => l.length);
    const maxW = Math.max(...widths);
    const muzzle = widths.lastIndexOf(maxW);
    const seat = Math.floor(maxW * C.RIDER_SEAT[kind]);
    return {
      x: dx > 0 ? -w : W, y, dx, lines, w, kind, muzzle, delay,
      speech: '', speed: uniform(...C.SPEED_RANGE[kind]),
      color: kind === 'big' ? 5 : choice([5, 1, 3]),
      cooldown: uniform(0, C.FIRE_RATE[kind][1]),
      riderX: dx > 0 ? seat : w - seat - riderWidth(kind),
      phase: randint(0, 2), shoutTtl: uniform(0, 1),
    };
  }

  function spawnSwarm(W, H) {
    const dx = choice([1, -1]);
    const swarm = [];
    for (const [kind, [lo, hi]] of Object.entries(C.SWARM_SIZE)) {
      for (let i = randint(lo, hi); i > 0; i--) {
        swarm.push(spawnMonster(W, H, kind, dx, uniform(0, C.SWARM_SPREAD)));
      }
    }
    swarm[0].delay = 0; // первым идёт большой
    return swarm;
  }

  function monsterStep(m, fish, W, dt) {
    if (m.delay > 0) { m.delay -= dt; return true; }
    const step = m.speed * dt;
    m.x += m.dx * step;
    const front = m.dx > 0 ? m.x + m.w : m.x;
    for (const f of fish) {
      if (f.mood === 'flee') continue;
      const ahead = (f.x + fishWidth(f) / 2 - front) * m.dx;
      if (ahead >= -m.w - step && ahead <= C.SCARE_RADIUS) {
        f.mood = 'flee';
        f.dx = m.dx;
        if (rnd() < C.PANIC_CHANCE) say(f, 'panic');
      }
    }
    return !(m.dx > 0 ? m.x > W : m.x + m.w < 0);
  }

  function swarmStep(monsters, fish, W, dt) {
    const alive = monsters.filter(m => monsterStep(m, fish, W, dt));
    monsters.splice(0, monsters.length, ...alive);
    if (!monsters.length) {
      for (const f of fish) if (f.mood === 'flee') { f.mood = 'return'; f.dx = -f.dx; }
    }
  }

  function riderLayout(m, tick) {
    const frames = riderFrames(m.kind);
    let lines = frames[(Math.floor(tick / C.SWING_TICKS) + m.phase) % frames.length];
    if (m.dx < 0) lines = mirror(lines.map(l => l.padEnd(riderWidth(m.kind))));
    const bottom = m.lines.length > 1 ? m.y : m.y - 1;
    return [bottom - lines.length + 1, Math.floor(m.x) + m.riderX, lines];
  }

  function riderStep(monsters, dt) {
    for (const m of monsters) {
      if (m.delay > 0 || (m.shoutTtl -= dt) > 0) continue;
      if (m.speech) { m.speech = ''; m.shoutTtl = uniform(...C.QUIET_TIME); } else {
        m.speech = choice(m.kind === 'small' ? D.tinyCries : D.riderCries);
        m.shoutTtl = uniform(...C.SHOUT_TIME);
      }
    }
  }

  function fireStep(monsters, shots, effects, W, dt) {
    for (const m of monsters) {
      if (m.delay > 0 || (m.cooldown -= dt) > 0) continue;
      m.cooldown = uniform(...C.FIRE_RATE[m.kind]);
      const tip = m.dx > 0 ? m.x + m.w : m.x - C.SHOT_RIGHT.length;
      if (tip < 0 || tip >= W || shots.length >= C.MAX_SHOTS) continue;
      const row = m.y + m.muzzle;
      shots.push({ x: tip, y: row, dx: m.dx, speed: m.speed + C.SHOT_SPEED });
      const flash = choice(D.flashes);
      effects.push([m.dx > 0 ? tip : tip - flash.length + 3, row - 1, flash, C.FLASH_TTL]);
    }
  }

  const shotText = s => (s.dx > 0 ? C.SHOT_RIGHT : C.SHOT_LEFT);
  const shotHead = s => Math.floor(s.x) + (s.dx > 0 ? shotText(s).length - 1 : 0);
  const hit = (f, x, y) => Math.floor(f.x) <= x && x < Math.floor(f.x) + fishWidth(f)
    && Math.floor(f.y) <= y && y < Math.floor(f.y) + fishLines(f).length;

  function shotStep(shots, effects, fish, W, dt) {
    const kept = [];
    for (const s of shots) {
      s.x += s.dx * s.speed * dt;
      if (s.x < -shotText(s).length || s.x > W) continue;
      const victim = fish.find(f => hit(f, shotHead(s), s.y));
      if (!victim) { kept.push(s); continue; }
      effects.push([shotHead(s) - 3, s.y, choice(D.splats), C.SPLAT_TTL]);
      if (rnd() < C.HIT_CHANCE) say(victim, 'hit');
    }
    shots.splice(0, shots.length, ...kept);
  }

  function effectStep(effects, dt) {
    for (const e of effects) e[3] -= dt;
    effects.splice(0, effects.length, ...effects.filter(e => e[3] > 0));
  }

  function registerX(state, key, now) {
    if (key === 'Shift' || key === 'CapsLock') return false; // для заглавной X
    if (key === 'x' || key === 'X' || key === 'ч' || key === 'Ч') {
      state.count = now - state.last <= C.EGG_GAP ? state.count + 1 : 1;
      state.last = now;
      if (state.count >= C.EGG_PRESSES) { state.count = 0; return true; }
      return false;
    }
    state.count = 0;
    return false;
  }

  // ===========================================================================
  // --- рендер: three.js -------------------------------------------------------
  // ===========================================================================
  const FONT_PX = 15;
  const CH = 19; // высота клетки, px
  const FONT = '"Menlo", "Consolas", "DejaVu Sans Mono", monospace';
  const DPR = Math.min(window.devicePixelRatio || 1, 2);
  const PALETTE = {
    1: '#ff5c6c', 2: '#5cff9d', 3: '#ffe15c', 4: '#5cb8ff', 5: '#ff5cf2', 6: '#5cf6ff',
  };
  const WHITE = '#ffffff';
  const PAD = 6; // запас под свечение, px

  const measure = document.createElement('canvas').getContext('2d');
  measure.font = `${FONT_PX}px ${FONT}`;
  const CW = Math.ceil(measure.measureText('M').width * 100) / 100; // ширина клетки, px

  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
  renderer.setPixelRatio(DPR);
  document.getElementById('stage').appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, 1, 0, -1, -10, 10);

  // фон: толща воды, лучи света, песок — шейдером
  const bgUniforms = { t: { value: 0 }, sand: { value: 0.05 }, aspect: { value: 1 } };
  const bg = new THREE.Mesh(
    new THREE.PlaneGeometry(1, 1),
    new THREE.ShaderMaterial({
      uniforms: bgUniforms,
      depthTest: false,
      depthWrite: false,
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `
        varying vec2 vUv; uniform float t; uniform float sand; uniform float aspect;
        float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        void main(){
          vec2 uv = vUv;
          vec3 deep = vec3(0.004, 0.035, 0.09), shallow = vec3(0.03, 0.30, 0.45);
          vec3 c = mix(deep, shallow, pow(uv.y, 1.6));
          float x = uv.x * aspect;
          float rays = sin(x * 6.0 + uv.y * 2.5 + t * 0.35) * sin(x * 3.7 - uv.y * 1.3 - t * 0.21);
          rays = pow(max(rays, 0.0), 4.0) * smoothstep(0.15, 1.0, uv.y) * 0.22;
          float caust = sin(x * 40.0 + t * 1.3 + sin(uv.y * 30.0 + t)) * sin(uv.y * 34.0 - t * 1.1 + sin(x * 25.0));
          c += vec3(0.3, 0.8, 1.0) * (rays + pow(max(caust, 0.0), 6.0) * 0.05 * uv.y);
          if (uv.y < sand) {
            float g = hash(floor(vec2(x, uv.y) * 220.0));
            vec3 s = mix(vec3(0.35, 0.28, 0.16), vec3(0.62, 0.52, 0.32), uv.y / sand);
            c = mix(c, s * (0.85 + 0.25 * g), smoothstep(0.0, 0.004, sand - uv.y));
          }
          gl_FragColor = vec4(c, 1.0);
        }`,
    }),
  );
  bg.renderOrder = -1;
  scene.add(bg);

  // --- текстуры из ASCII: рисуем символы по сетке на canvas --------------------
  const texCache = new Map();

  function textTexture(lines, color, opts = {}) {
    const key = `${color}|${opts.accent || ''}|${opts.glow ?? 1}|${lines.join('\n')}`;
    let t = texCache.get(key);
    if (t) return t;
    if (texCache.size > 3000) { for (const v of texCache.values()) v.tex.dispose(); texCache.clear(); }
    const cols = widthOf(lines);
    const w = cols * CW + PAD * 2;
    const h = lines.length * CH + PAD * 2;
    const cv = document.createElement('canvas');
    cv.width = Math.ceil(w * DPR);
    cv.height = Math.ceil(h * DPR);
    const ctx = cv.getContext('2d');
    ctx.scale(DPR, DPR);
    ctx.font = `${opts.bold ? 'bold ' : ''}${FONT_PX}px ${FONT}`;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';
    lines.forEach((line, r) => {
      [...line].forEach((ch, c) => {
        if (ch === ' ') return;
        const accent = opts.accent && opts.accent.includes(ch);
        const fill = accent ? WHITE : color;
        ctx.shadowColor = fill;
        ctx.shadowBlur = (accent ? 8 : 5) * (opts.glow ?? 1);
        ctx.fillStyle = fill;
        ctx.fillText(ch, PAD + c * CW + CW / 2, PAD + r * CH + CH / 2 + 1);
      });
    });
    t = { tex: makeTex(cv), w, h };
    texCache.set(key, t);
    return t;
  }

  /** Комиксное облачко с хвостиком вниз (tail: смещение хвоста по x, px). */
  function bubbleTexture(text, color, tail) {
    const key = `bubble|${color}|${tail}|${text}`;
    let t = texCache.get(key);
    if (t) return t;
    measure.font = `bold ${FONT_PX - 1}px ${FONT}`;
    const tw = Math.ceil(measure.measureText(text).width);
    const w = tw + 22 + PAD * 2;
    const h = CH + 10 + 10 + PAD * 2;
    const cv = document.createElement('canvas');
    cv.width = Math.ceil(w * DPR);
    cv.height = Math.ceil(h * DPR);
    const ctx = cv.getContext('2d');
    ctx.scale(DPR, DPR);
    const bx = PAD, by = PAD, bw = tw + 22, bh = CH + 10, r = 9;
    const tx = clamp(tail, bx + 12, bx + bw - 12);
    ctx.beginPath();
    ctx.moveTo(bx + r, by);
    ctx.arcTo(bx + bw, by, bx + bw, by + bh, r);
    ctx.arcTo(bx + bw, by + bh, bx, by + bh, r);
    ctx.lineTo(tx + 6, by + bh);
    ctx.lineTo(tx - 2, by + bh + 9);
    ctx.lineTo(tx - 6, by + bh);
    ctx.arcTo(bx, by + bh, bx, by, r);
    ctx.arcTo(bx, by, bx + bw, by, r);
    ctx.closePath();
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.fillStyle = 'rgba(250, 253, 255, 0.96)';
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    ctx.stroke();
    ctx.fillStyle = '#081420';
    ctx.font = `bold ${FONT_PX - 1}px ${FONT}`;
    ctx.textBaseline = 'middle';
    ctx.fillText(text, bx + 11, by + bh / 2 + 1);
    t = { tex: makeTex(cv), w, h, tailX: tx, tailY: by + bh + 9 };
    texCache.set(key, t);
    return t;
  }

  function makeTex(cv) {
    const tex = new THREE.CanvasTexture(cv);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    return tex;
  }

  // пул плоскостей: каждый кадр «рисуем» заново, как curses-версия
  const quad = new THREE.PlaneGeometry(1, 1);
  const pool = [];
  let used = 0;

  function blit(t, px, py) {
    let m = pool[used];
    if (!m) {
      m = new THREE.Mesh(quad, new THREE.MeshBasicMaterial({
        transparent: true, depthTest: false, depthWrite: false,
      }));
      pool.push(m);
      scene.add(m);
    }
    if (m.material.map !== t.tex) { m.material.map = t.tex; m.material.needsUpdate = true; }
    m.scale.set(t.w, t.h, 1);
    m.position.set(px + t.w / 2, -(py + t.h / 2), 0);
    m.renderOrder = used;
    m.visible = true;
    used++;
  }

  /** Текст в клетках (col, row) как в терминале. */
  const drawText = (lines, col, row, color, opts) =>
    blit(textTexture(lines, color, opts), col * CW - PAD, row * CH - PAD);

  function drawBubble(text, headCol, row, color) {
    // облачко над клеткой (headCol, row): хвостик указывает в эту клетку
    const probe = bubbleTexture(text, color, 0);
    const want = headCol * CW + CW / 2;
    let left = want - probe.w / 2;
    left = clamp(left, -PAD, view.W * CW - probe.w + PAD);
    const t = bubbleTexture(text, color, Math.round(want - left));
    blit(t, left, (row + 1) * CH - t.tailY);
  }

  // ===========================================================================
  // --- состояние и цикл ---------------------------------------------------------
  // ===========================================================================
  const view = { W: 80, H: 30, pw: 0, ph: 0 };
  const state = {
    fish: [], foods: [], bubbles: [], monsters: [], shots: [], effects: [],
    paused: false, sim: 0, egg: { count: 0, last: -99 }, counts: null,
  };

  function resize() {
    const pw = window.innerWidth;
    const ph = window.innerHeight;
    renderer.setSize(pw, ph);
    camera.left = 0; camera.right = pw; camera.top = 0; camera.bottom = -ph;
    camera.updateProjectionMatrix();
    bg.scale.set(pw, ph, 1);
    bg.position.set(pw / 2, -ph / 2, -1);
    bgUniforms.aspect.value = pw / ph;
    const oldW = view.W;
    view.pw = pw; view.ph = ph;
    view.W = Math.max(40, Math.floor(pw / CW));
    view.H = Math.max(16, Math.floor(ph / CH));
    bgUniforms.sand.value = Math.min(0.2, (2.2 * CH) / ph);
    if (state.fish.length) relayout(state.fish, oldW, view.W, view.H);
  }

  function startTank(counts) {
    state.counts = counts;
    state.fish = spawnFish(counts, view.W, view.H);
    state.foods = []; state.bubbles = []; state.monsters = []; state.shots = []; state.effects = [];
  }

  function update(dt) {
    const { W, H } = view;
    const s = state;
    if (s.paused) return;
    s.sim += dt;
    if (s.monsters.length) {
      swarmStep(s.monsters, s.fish, W, dt);
      fireStep(s.monsters, s.shots, s.effects, W, dt);
      riderStep(s.monsters, dt);
    }
    shotStep(s.shots, s.effects, s.fish, W, dt);
    effectStep(s.effects, dt);
    for (const f of s.fish) {
      const food = f.mood ? null : nearestFood(f, s.foods);
      if (stepFish(f, W, H, dt, food) && rnd() < C.HOME_CHANCE) say(f, 'home');
    }
    for (const e of feedStep(s.foods, s.fish, H, dt)) say(e, 'food_eaten');
    speechStep(s.fish, dt);
    bubbleStep(s.bubbles, s.fish, dt);
  }

  function draw() {
    const { W, H } = view;
    const s = state;
    const tick = Math.floor(s.sim * 20); // как кадры curses-версии (50 мс)
    used = 0;

    // поверхность воды бежит волной
    const wave = '^^^^ '.repeat(Math.ceil(W / 5) + 2);
    const shift = (s.sim * 1.5) % 5;
    blit(textTexture([wave], '#9fe8ff', { glow: 0.6 }), -shift * CW - PAD, -PAD + 2);

    // водоросли разной высоты качаются
    for (let x = 1; x < W - 1; x += 7) {
      const tall = 2 + ((x * 7919) % 4);
      const col = [];
      for (let r = 0; r < tall; r++) col.push((Math.floor(tick / 8) + x + r) % 2 ? '}' : '{');
      drawText(col, x, H - 1 - tall, PALETTE[2], { glow: 0.7 });
    }

    for (const f of s.fish) {
      const color = PALETTE[f.color];
      const x = Math.floor(f.x);
      const y = Math.floor(f.y);
      const lines = fishLines(f);
      drawText(lines, x, y, color, { accent: C.EYES });
      let nx = x + Math.floor((fishWidth(f) - f.nick.length) / 2);
      if (x >= 0) nx = Math.max(0, nx);
      drawText([f.nick], nx, y + lines.length, color, { glow: 0.5 });
    }

    for (const sh of s.shots) drawText([shotText(sh)], Math.floor(sh.x), sh.y, WHITE, { glow: 1.6 });
    for (const [ex, ey, text] of s.effects) drawText([text], Math.floor(ex), ey, WHITE, { bold: true, glow: 1.4 });

    const byHeight = s.monsters.slice().sort((a, b) => a.lines.length - b.lines.length);
    for (const m of byHeight) {
      if (m.delay > 0) continue;
      drawText(m.lines, Math.floor(m.x), m.y, PALETTE[m.color], { bold: true, glow: 1.2 });
      const [top, col, lines] = riderLayout(m, tick);
      drawText(lines, col, top, PALETTE[6], { bold: true });
      if (m.speech) drawBubble(m.speech, col + (lines[0].length >> 1), top - 1, PALETTE[6]);
    }

    for (const [bx, by] of s.bubbles) {
      drawText([Math.floor(by) % 2 ? '°' : 'o'], Math.floor(bx), Math.floor(by), '#bff4ff', { glow: 0.6 });
    }
    for (const fd of s.foods) drawText(['*'], Math.floor(fd[0]), Math.floor(fd[1]), '#ffd27a', { glow: 1.2 });

    for (const f of s.fish) {
      if (!f.speech) continue;
      const head = Math.floor(f.x) + (f.dx > 0 ? fishWidth(f) - 1 : 0);
      if (head < 0 || head >= W) continue; // спряталась за край — облачко не висит в углу
      const y = Math.floor(f.y);
      // над головой, а у самой поверхности — под ником
      const row = y >= 2 ? y - 1 : y + fishLines(f).length + 1;
      drawBubble(f.speech, clamp(head, 0, W - 1), row, PALETTE[f.color]);
    }

    for (let i = used; i < pool.length; i++) pool[i].visible = false;
    bgUniforms.t.value = s.sim;
    renderer.render(scene, camera);

    const banner = document.getElementById('banner');
    banner.textContent = D.stormBanner;
    banner.hidden = !(s.monsters.length && Math.floor(tick / 6) % 2 === 0);
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min((now - last) / 1000, 0.2);
    last = now;
    if (!picker.open) update(dt);
    draw();
    requestAnimationFrame(frame);
  }

  // ===========================================================================
  // --- управление ---------------------------------------------------------------
  // ===========================================================================
  function dropFood(col) {
    const x = col ?? randint(0, view.W - 2);
    state.foods.push([x, 1]);
    const seer = nearestFish(state.fish, x);
    if (seer) say(seer, 'food_seen');
  }

  function poke(f) {
    const target = f || (state.fish.length ? choice(state.fish) : null);
    if (target) say(target, 'poke');
  }

  window.addEventListener('keydown', e => {
    if (picker.open) { picker.key(e); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (registerX(state.egg, k, performance.now() / 1000) && !state.monsters.length) {
      state.monsters = spawnSwarm(view.W, view.H);
    }
    const low = k.toLowerCase();
    if (low === 'f' || low === 'а') dropFood();
    else if (low === 't' || low === 'е') poke();
    else if (low === 'p' || low === 'з') state.paused = !state.paused;
    else if (low === 'c' || low === 'с') picker.show();
    else return;
    e.preventDefault();
  });

  renderer.domElement.addEventListener('pointerdown', e => {
    if (picker.open) return;
    const col = e.clientX / CW;
    const row = e.clientY / CH;
    const target = state.fish.find(f => col >= f.x && col < f.x + fishWidth(f)
      && row >= Math.floor(f.y) && row < Math.floor(f.y) + fishLines(f).length + 1);
    if (target) poke(target); else dropFood(Math.floor(col));
  });

  window.addEventListener('resize', resize);

  // --- экран выбора рыб (как run_picker) --------------------------------------
  const picker = {
    open: false,
    cursor: 0,
    counts: {},
    show() {
      const saved = state.counts || {};
      this.counts = Object.fromEntries(NAMES.map(n => [n, saved[n] || 0]));
      this.open = true;
      document.getElementById('picker').hidden = false;
      this.render();
    },
    hide() {
      this.open = false;
      document.getElementById('picker').hidden = true;
    },
    total() { return Object.values(this.counts).reduce((a, b) => a + b, 0); },
    change(name, delta) {
      this.counts[name] = clamp(this.counts[name] + delta, 0, C.MAX_PER_SPECIES);
      this.render();
    },
    random() {
      for (const n of NAMES) this.counts[n] = randint(0, 5);
      if (!this.total()) this.counts[choice(NAMES)] = 1;
      this.render();
    },
    start() {
      if (!this.total()) return;
      try { localStorage.setItem(STORE_KEY, JSON.stringify(this.counts)); } catch (_) { /* приватный режим */ }
      startTank({ ...this.counts });
      this.hide();
    },
    key(e) {
      const name = NAMES[this.cursor];
      const k = e.key;
      if (k === 'ArrowUp') this.cursor = (this.cursor + NAMES.length - 1) % NAMES.length;
      else if (k === 'ArrowDown') this.cursor = (this.cursor + 1) % NAMES.length;
      else if (k === 'ArrowRight') this.counts[name] = Math.min(C.MAX_PER_SPECIES, this.counts[name] + 1);
      else if (k === 'ArrowLeft') this.counts[name] = Math.max(0, this.counts[name] - 1);
      else if (k === ' ') this.counts[name] = this.counts[name] ? 0 : 1;
      else if (k === 'r' || k === 'R' || k === 'к' || k === 'К') { this.random(); e.preventDefault(); return; }
      else if (k === 'Enter') { this.start(); e.preventDefault(); return; }
      else if (k === 'Escape' && state.counts) { this.hide(); return; }
      else return;
      e.preventDefault();
      this.render();
    },
    render() {
      const rows = document.getElementById('rows');
      rows.replaceChildren(...NAMES.map((name, i) => {
        const n = this.counts[name];
        const row = document.createElement('div');
        row.className = 'row' + (i === this.cursor ? ' on' : '');
        const mark = document.createElement('span');
        mark.textContent = i === this.cursor ? '▶' : '';
        const label = document.createElement('span');
        label.textContent = `[${n ? 'x' : ' '}] ${name}`;
        const icon = document.createElement('span');
        icon.className = 'icon';
        icon.textContent = SPECIES[name].icon;
        const cnt = document.createElement('span');
        cnt.className = 'cnt';
        const minus = document.createElement('button');
        minus.type = 'button';
        minus.textContent = '−';
        minus.onclick = ev => { ev.stopPropagation(); this.cursor = i; this.change(name, -1); };
        const num = document.createElement('span');
        num.className = 'n';
        num.textContent = String(n);
        const plus = document.createElement('button');
        plus.type = 'button';
        plus.textContent = '+';
        plus.onclick = ev => { ev.stopPropagation(); this.cursor = i; this.change(name, 1); };
        cnt.append(minus, num, plus);
        row.append(mark, label, icon, cnt);
        row.onclick = () => { this.cursor = i; this.counts[name] = n ? 0 : 1; this.render(); };
        return row;
      }));
      document.getElementById('go').disabled = !this.total();
    },
  };
  document.getElementById('rand').onclick = () => picker.random();
  document.getElementById('go').onclick = () => picker.start();

  // --- старт ------------------------------------------------------------------
  document.getElementById('help').innerHTML =
    '<b>f</b> или клик по воде — покормить · <b>t</b> или клик по рыбе — болтать · '
    + '<b>p</b> — пауза · <b>c</b> — выбор рыб';

  function loadCounts() {
    try {
      const data = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
      if (!data || typeof data !== 'object') return null;
      const counts = Object.fromEntries(NAMES.map(n => [n, 0]));
      for (const [name, v] of Object.entries(data)) {
        if (!(name in counts) || !Number.isInteger(v)) return null;
        counts[name] = clamp(v, 0, C.MAX_PER_SPECIES);
      }
      return Object.values(counts).some(Boolean) ? counts : null;
    } catch (_) {
      return null;
    }
  }

  resize();
  const saved = loadCounts();
  if (saved) startTank(saved); else picker.show();
  requestAnimationFrame(frame);

  // для отладки из консоли
  window.aquarium = { state, view, spawnSwarm: () => { state.monsters = spawnSwarm(view.W, view.H); } };
})();
