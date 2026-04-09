
(() => {
  const canvas = document.getElementById('lockscreen-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const stage = document.getElementById('auth-stage');
  const sigil = document.getElementById('story-sigil');
  const sigilDots = sigil ? Array.from(sigil.querySelectorAll('.story-sigil-dot')) : [];
  const sigilArc = sigil ? sigil.querySelector('.story-sigil-arc') : null;
  const sigilInner = sigil ? sigil.querySelector('.story-sigil-inner') : null;
  const sigilCore = sigil ? sigil.querySelector('.story-sigil-core') : null;

  let W = 0;
  let H = 0;
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let rafId = 0;
  let running = false;
  let particles = [];
  let mouse = { x: window.innerWidth * 0.66, y: window.innerHeight * 0.48 };
  let segments = [];
  let lastHeadX = 0;
  let lastHeadY = 0;
  let cursorIndex = 0;
  let sigilOffsetX = 0;
  let sigilOffsetY = 0;
  let sigilTargetX = 0;
  let sigilTargetY = 0;
  let sigilTilt = 0;
  let sigilTargetTilt = 0;
  let headAngle = 0;
  let lastPointerX = mouse.x;
  let lastPointerY = mouse.y;
  const designWidth = 1620;
  const designHeight = 940;
  const chainSpacing = 5.4;
  const bodyCatchup = 0.62;

  const bodyFont = '600 24px "Cormorant Garamond", Georgia, serif';
  const bodyLineHeight = 34;
  const bodyParagraphs = [
    '"A strong campaign is not loud by accident; it is remembered on purpose."',
    'Jarvis keeps the agency room in order, so clarity survives even when the calendar begins to fill.',
    '"The finest brands do not chase attention; they earn recall."',
    'In this folio, ideas are refined until the message sounds inevitable and the timing feels exact.',
    'من عرف وقته، عرف طريقه؛ ومن عرف رسالته، عرف كيف يخاطب الناس.',
    '"A headline should arrive like a key, not like noise."',
    'The work becomes lighter when the sequence is right: draft, approval, release, and then the public eye.',
    'النجاح لا يأتي من كثرة الكلام، بل من دقة المعنى وحسن التوقيت.',
    '"The right offer sounds simple only after difficult thinking."',
    'Jarvis was built for agencies that need structure without losing elegance, and speed without losing judgment.',
    'في الصفحات الهادئة تُصاغ الحملات الكبيرة، وتظهر النبرة الصادقة دون ضجيج.',
    '"Clarity is a kind of luxury."',
    'Restraint is not weakness; restraint is control.',
    'من أتقن البداية، سهلت عليه بقية الطريق، ومن حفظ المعنى سلم من التشويش.',
    '"The page keeps only what deserves to go live."',
    'Here the room remembers what busy threads forget: the better line, the calmer sequence, the cleaner launch.',
    'هنا يبقى صوت العلامة محفوظاً، من أول سطر في الحملة إلى آخر لحظة قبل الإطلاق.',
    'Order gives ambition somewhere worthy to land, and Jarvis keeps that order awake.',
    'بين السطور الهادئة تظهر الفكرة الأصدق، وتبقى اللغة الرفيعة أقرب إلى القلوب.',
    'Great work travels with calm behind it.',
    'كل نجاح أنيق يبدأ بفكرة مضبوطة، ثم جملةٍ صادقة، ثم توقيت لا يخطئ.',
    'What is written clearly can be shipped calmly.',
    'The room remains sealed, but the standard remains high.'
  ];

  const bodyTokens = [];
  bodyParagraphs.forEach((paragraph, index) => {
    if (index > 0) bodyTokens.push({ type: 'break' });
    const dir = /[\u0600-\u06FF]/.test(paragraph) ? 'rtl' : 'ltr';
    paragraph.split(/\s+/).filter(Boolean).forEach(word => {
      bodyTokens.push({ type: 'word', text: word, dir });
    });
  });

  function buildSegments() {
    segments = Array.from({ length: 50 }, (_, i) => ({
      x: W * 0.29 + i * chainSpacing,
      y: H * 0.49 + Math.sin(i * 0.16) * 7,
      radius: Math.max(2.6, 12.5 - i * 0.16),
    }));
    lastHeadX = segments[0].x;
    lastHeadY = segments[0].y;
    headAngle = -Math.PI * 0.18;
    lastPointerX = mouse.x;
    lastPointerY = mouse.y;
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (stage) {
      const viewportScale = window.visualViewport && window.visualViewport.scale ? window.visualViewport.scale : 1;
      const stageScale = Math.min(W / designWidth, H / designHeight, 1);
      stage.style.transform = `translate(-50%, -50%) scale(${stageScale / viewportScale})`;
    }
    if (!segments.length) buildSegments();
  }

  function emitParticles(x, y, intensity) {
    if (intensity < 1.2) return;
    for (let i = 0; i < intensity; i += 1) {
      particles.push({
        x: x + (Math.random() - 0.5) * 14,
        y: y + (Math.random() - 0.5) * 12,
        vx: (Math.random() - 0.62) * 4.8,
        vy: -Math.random() * 7 - 1.5,
        life: 26 + Math.random() * 18,
        size: 2 + Math.random() * 4,
        hue: 28 + Math.random() * 18,
      });
    }
    if (particles.length > 240) particles.splice(0, particles.length - 240);
  }

  function circleInterval(cx, cy, r, bandTop, bandBot) {
    if (bandTop >= cy + r || bandBot <= cy - r) return null;
    const minDy = Math.max(0, Math.abs(cy - (bandTop + bandBot) / 2) - (bandBot - bandTop) / 2);
    if (minDy >= r) return null;
    const dx = Math.sqrt(r * r - minDy * minDy);
    return { left: cx - dx, right: cx + dx };
  }

  function rectInterval(element, bandTop, bandBot, padX = 14, padY = 12) {
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    const top = rect.top - padY;
    const bottom = rect.bottom + padY;
    if (bandTop >= bottom || bandBot <= top) return null;
    return { left: rect.left - padX, right: rect.right + padX };
  }

  function carveSlots(left, right, blocked) {
    blocked.sort((a, b) => a.left - b.left);
    const merged = [];
    for (const block of blocked) {
      if (!merged.length || block.left > merged[merged.length - 1].right) merged.push({ ...block });
      else merged[merged.length - 1].right = Math.max(merged[merged.length - 1].right, block.right);
    }
    const slots = [];
    let current = left;
    for (const block of merged) {
      if (block.left > current) slots.push({ left: current, right: Math.min(block.left, right) });
      current = Math.max(current, block.right);
    }
    if (current < right) slots.push({ left: current, right });
    return slots.filter(slot => slot.right - slot.left > 110);
  }

  function nextLineForWidth(maxWidth) {
    if (!bodyTokens.length) return null;
    let line = '';
    let dir = 'ltr';
    let advanced = false;
    while (cursorIndex < bodyTokens.length) {
      const token = bodyTokens[cursorIndex];
      if (token.type === 'break') {
        cursorIndex += 1;
        if (line) break;
        continue;
      }
      const candidate = line ? `${line} ${token.text}` : token.text;
      ctx.direction = token.dir;
      const width = ctx.measureText(candidate).width;
      if (width <= maxWidth || !line) {
        line = candidate;
        dir = token.dir;
        cursorIndex += 1;
        advanced = true;
      } else {
        break;
      }
    }
    if (!advanced) return null;
    return { text: line, dir };
  }

  function drawPaper() {
    ctx.clearRect(0, 0, W, H);

    const glow = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, Math.max(W, H) * 0.55);
    glow.addColorStop(0, 'rgba(255, 214, 150, 0.23)');
    glow.addColorStop(0.32, 'rgba(255, 222, 176, 0.14)');
    glow.addColorStop(1, 'rgba(255, 222, 176, 0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, H);

    ctx.strokeStyle = 'rgba(141, 93, 42, 0.08)';
    ctx.lineWidth = 1;
    for (let y = 128; y < H - 20; y += 42) {
      ctx.beginPath();
      ctx.moveTo(34, y + 0.5);
      ctx.lineTo(W - 34, y + 0.5);
      ctx.stroke();
    }

    ctx.strokeStyle = 'rgba(176, 73, 47, 0.14)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(78, 32);
    ctx.lineTo(78, H - 32);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(158, 110, 51, 0.18)';
    ctx.lineWidth = 1.2;
    const corners = [
      [34, 34, 84, 34, 34, 84],
      [W - 34, 34, W - 84, 34, W - 34, 84],
      [34, H - 34, 84, H - 34, 34, H - 84],
      [W - 34, H - 34, W - 84, H - 34, W - 34, H - 84],
    ];
    corners.forEach(([x1, y1, x2, y2, x3, y3]) => {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x3, y3);
      ctx.stroke();
    });
  }

  function drawParticles() {
    ctx.save();
    ctx.shadowBlur = 18;
    for (let i = particles.length - 1; i >= 0; i -= 1) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.1;
      p.life -= 1;
      p.size *= 0.97;
      if (p.life <= 0 || p.size < 0.3) {
        particles.splice(i, 1);
        continue;
      }
      ctx.globalAlpha = Math.max(0, p.life / 34);
      ctx.fillStyle = `hsl(${p.hue}, 100%, 68%)`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function traceRibbonPath() {
    ctx.beginPath();
    ctx.moveTo(segments[0].x, segments[0].y);
    for (let i = 1; i < segments.length - 1; i += 1) {
      const xc = (segments[i].x + segments[i + 1].x) / 2;
      const yc = (segments[i].y + segments[i + 1].y) / 2;
      ctx.quadraticCurveTo(segments[i].x, segments[i].y, xc, yc);
    }
    const tail = segments[segments.length - 1];
    ctx.lineTo(tail.x, tail.y);
  }

  function drawHeraldRibbon() {
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    ctx.strokeStyle = 'rgba(179, 126, 54, 0.14)';
    ctx.lineWidth = 20;
    ctx.shadowColor = 'rgba(181, 123, 52, 0.18)';
    ctx.shadowBlur = 22;
    traceRibbonPath();
    ctx.stroke();

    ctx.shadowBlur = 0;
    ctx.strokeStyle = '#19110b';
    ctx.lineWidth = 12;
    traceRibbonPath();
    ctx.stroke();

    ctx.strokeStyle = 'rgba(194, 144, 72, 0.52)';
    ctx.lineWidth = 2.4;
    traceRibbonPath();
    ctx.stroke();

    for (let i = 10; i < segments.length - 8; i += 9) {
      const s = segments[i];
      const prev = segments[Math.max(0, i - 1)];
      const next = segments[Math.min(segments.length - 1, i + 1)];
      const angle = Math.atan2(next.y - prev.y, next.x - prev.x);
      const normal = angle + (i % 18 === 0 ? -1.04 : 1.04);
      const accent = 13 - i * 0.08;
      ctx.strokeStyle = 'rgba(121, 82, 36, 0.22)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.quadraticCurveTo(
        s.x + Math.cos(normal) * accent * 0.55,
        s.y + Math.sin(normal) * accent * 0.55,
        s.x + Math.cos(normal) * accent,
        s.y + Math.sin(normal) * accent
      );
      ctx.stroke();
    }

    const head = segments[0];
    ctx.translate(head.x, head.y);
    ctx.rotate(headAngle);

    ctx.fillStyle = 'rgba(225, 176, 88, 0.16)';
    ctx.beginPath();
    ctx.ellipse(-6, 0, 34, 22, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#1a120c';
    ctx.strokeStyle = '#0d0906';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(28, 0);
    ctx.quadraticCurveTo(8, -18, -18, -11);
    ctx.lineTo(-28, 0);
    ctx.lineTo(-18, 11);
    ctx.quadraticCurveTo(8, 18, 28, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = 'rgba(217, 170, 88, 0.72)';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(12, 0);
    ctx.lineTo(-22, 0);
    ctx.moveTo(-4, -7);
    ctx.quadraticCurveTo(8, -13, 18, -9);
    ctx.moveTo(-4, 7);
    ctx.quadraticCurveTo(8, 13, 18, 9);
    ctx.stroke();

    ctx.fillStyle = '#f3ca67';
    ctx.beginPath();
    ctx.arc(16, 0, 3.2, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(198, 147, 69, 0.5)';
    ctx.fillRect(-18, -3, 18, 6);
    ctx.restore();
  }

  function drawBodyCopy() {
    const titleBlock = document.querySelector('#auth-overlay .story-title-wrap');
    const leftNote = document.querySelector('#auth-overlay .story-note.left');
    const rightNote = document.querySelector('#auth-overlay .story-note.right');
    const footerNote = document.querySelector('#auth-overlay .story-footer-note');
    const panel = document.querySelector('#auth-overlay .login-panel');

    cursorIndex = 0;
    ctx.font = bodyFont;
    ctx.fillStyle = '#3f3021';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(88, 62, 36, 0.08)';
    ctx.shadowBlur = 4;
    for (let y = 258; y < H - 40; y += bodyLineHeight) {
      const blocked = segments
        .map(seg => circleInterval(seg.x, seg.y, seg.radius + 20, y, y + bodyLineHeight))
        .filter(Boolean);
      [rectInterval(titleBlock, y, y + bodyLineHeight, 18, 12), rectInterval(leftNote, y, y + bodyLineHeight, 12, 12), rectInterval(rightNote, y, y + bodyLineHeight, 12, 12), rectInterval(footerNote, y, y + bodyLineHeight, 16, 10), rectInterval(panel, y, y + bodyLineHeight, 26, 16)]
        .filter(Boolean)
        .forEach(block => blocked.push(block));

      const slots = carveSlots(98, W - 58, blocked);
      for (const slot of slots) {
        const next = nextLineForWidth(slot.right - slot.left);
        if (!next) break;
        if (next.dir === 'rtl') {
          ctx.direction = 'rtl';
          ctx.textAlign = 'right';
          ctx.fillText(next.text, slot.right, y + bodyLineHeight / 2);
        } else {
          ctx.direction = 'ltr';
          ctx.textAlign = 'left';
          ctx.fillText(next.text, slot.left, y + bodyLineHeight / 2);
        }
      }
    }

    ctx.shadowBlur = 0;
    ctx.textAlign = 'left';
    ctx.direction = 'ltr';
  }

  function animate() {
    if (!running) return;

    drawPaper();

    sigilOffsetX += (sigilTargetX - sigilOffsetX) * 0.08;
    sigilOffsetY += (sigilTargetY - sigilOffsetY) * 0.08;
    sigilTilt += (sigilTargetTilt - sigilTilt) * 0.08;
    if (sigil) {
      const t = performance.now() * 0.001;
      const rect = sigil.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dist = Math.hypot(mouse.x - cx, mouse.y - cy);
      const proximity = Math.max(0, 1 - dist / 520);
      sigil.style.opacity = String(0.58 + proximity * 0.26);
      sigil.style.transform = `perspective(900px) translate3d(${sigilOffsetX}px, ${sigilOffsetY}px, 0) rotateX(${-sigilOffsetY * 0.22}deg) rotateY(${sigilOffsetX * 0.24}deg) rotate(${sigilTilt}deg)`;
      if (sigilArc) sigilArc.style.transform = `rotate(${28 + t * 22}deg)`;
      if (sigilInner) sigilInner.style.transform = `rotate(${-t * 16}deg)`;
      if (sigilCore) sigilCore.style.transform = `scale(${1 + proximity * 0.08})`;
      if (sigilDots.length >= 3) {
        const size = sigil.clientWidth || 396;
        const sx = size / 2;
        const sy = size / 2;
        const configs = [
          { r: size * 0.39, speed: 0.68, phase: 0.2, s: 12 },
          { r: size * 0.29, speed: -0.94, phase: 2.2, s: 10 },
          { r: size * 0.44, speed: 0.46, phase: 4.16, s: 11 }
        ];
        sigilDots.forEach((dot, index) => {
          const cfg = configs[index];
          if (!cfg) return;
          const x = sx + Math.cos(t * cfg.speed + cfg.phase) * cfg.r - cfg.s / 2;
          const y = sy + Math.sin(t * cfg.speed + cfg.phase) * cfg.r - cfg.s / 2;
          dot.style.left = `${x}px`;
          dot.style.top = `${y}px`;
        });
      }
    }

    segments[0].x = mouse.x;
    segments[0].y = mouse.y;
    for (let i = 1; i < segments.length; i += 1) {
      const dx = segments[i - 1].x - segments[i].x;
      const dy = segments[i - 1].y - segments[i].y;
      const dist = Math.hypot(dx, dy) || 0.0001;
      const targetX = segments[i - 1].x - (dx / dist) * chainSpacing;
      const targetY = segments[i - 1].y - (dy / dist) * chainSpacing;
      segments[i].x += (targetX - segments[i].x) * bodyCatchup;
      segments[i].y += (targetY - segments[i].y) * bodyCatchup;
    }

    const velocity = Math.hypot(segments[0].x - lastHeadX, segments[0].y - lastHeadY);
    const tipAngle = headAngle;
    emitParticles(
      segments[0].x + Math.cos(tipAngle) * 18,
      segments[0].y + Math.sin(tipAngle) * 18,
      Math.min(velocity * 0.45, 4)
    );
    lastHeadX = segments[0].x;
    lastHeadY = segments[0].y;

    drawParticles();
    drawHeraldRibbon();
    drawBodyCopy();

    rafId = requestAnimationFrame(animate);
  }

  function onPointerMove(event) {
    mouse.x = event.clientX;
    mouse.y = event.clientY;
    const dx = event.clientX - lastPointerX;
    const dy = event.clientY - lastPointerY;
    if (Math.hypot(dx, dy) > 0.45) {
      headAngle = Math.atan2(dy, dx);
    }
    lastPointerX = event.clientX;
    lastPointerY = event.clientY;
    if (sigil) {
      const nx = (event.clientX / Math.max(window.innerWidth, 1)) - 0.5;
      const ny = (event.clientY / Math.max(window.innerHeight, 1)) - 0.5;
      sigilTargetX = nx * 26;
      sigilTargetY = ny * 22;
      sigilTargetTilt = nx * 12;
    }
  }

  window.addEventListener('resize', resize);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', resize);
    window.visualViewport.addEventListener('scroll', resize);
  }
  window.addEventListener('pointermove', onPointerMove, { passive: true });

  resize();
  buildSegments();

  window.__jarvisLockScene = {
    ready: true,
    pendingStart: false,
    start() {
      resize();
      if (!segments.length) buildSegments();
      if (running) return;
      running = true;
      cancelAnimationFrame(rafId);
      animate();
    },
    stop() {
      this.pendingStart = false;
      running = false;
      cancelAnimationFrame(rafId);
      ctx.clearRect(0, 0, W, H);
    },
    resize() {
      resize();
    },
    unlockBurst() {
      const panel = document.querySelector('#auth-overlay .login-panel');
      if (!panel) return;
      const rect = panel.getBoundingClientRect();
      const burstX = rect.left + rect.width / 2;
      const burstY = rect.top + rect.height / 2;
      for (let i = 0; i < 80; i += 1) {
        const angle = (Math.PI * 2 * i) / 80;
        const speed = 1.8 + Math.random() * 3.6;
        particles.push({
          x: burstX + Math.cos(angle) * 12,
          y: burstY + Math.sin(angle) * 12,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 0.6,
          life: 28 + Math.random() * 14,
          size: 1.4 + Math.random() * 2.8,
          hue: 32 + Math.random() * 16,
        });
      }
    }
  };
})();
