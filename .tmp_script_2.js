
/* â”€â”€ THREE.JS BACKGROUND & NEURAL PULSING â”€â”€ */
let triggerNeuralPulse = () => {};
(function() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas || !window.THREE || typeof THREE.WebGLRenderer !== 'function') {
    return;
  }
  try {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x02020a, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 180;

  function resize() {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize);

  const COUNT = 280;
  const positions = new Float32Array(COUNT * 3);
  const velocities = [];
  const spread = 200;

  for (let i = 0; i < COUNT; i++) {
    positions[i * 3]     = (Math.random() - .5) * spread;
    positions[i * 3 + 1] = (Math.random() - .5) * spread;
    positions[i * 3 + 2] = (Math.random() - .5) * spread * .6;
    velocities.push({
      x: (Math.random() - .5) * .06,
      y: (Math.random() - .5) * .06,
      z: (Math.random() - .5) * .03
    });
  }

  const ptGeo = new THREE.BufferGeometry();
  ptGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const ptMat = new THREE.PointsMaterial({ color: 0x9d84ff, size: 1.4, transparent: true, opacity: .75, sizeAttenuation: true });
  const points = new THREE.Points(ptGeo, ptMat);
  scene.add(points);

  const MAX_LINES = 600;
  const linePositions = new Float32Array(MAX_LINES * 6);
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  lineGeo.setDrawRange(0, 0);

  const lineMat = new THREE.LineBasicMaterial({ color: 0x6644aa, transparent: true, opacity: .2 });
  const lineSegments = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(lineSegments);

  // Restore elegant intersecting background Rings
  const rings = [];
  const ringColors = [0x5533cc, 0x2244aa, 0x1fcea0, 0x3311aa];
  for (let i = 0; i < 4; i++) {
    const geo = new THREE.TorusGeometry(18 + i * 12, .3, 8, 60);
    const mat = new THREE.MeshBasicMaterial({ color: ringColors[i], transparent: true, opacity: .12 - i * .02 });
    const ring = new THREE.Mesh(geo, mat);
    ring.position.set((Math.random() - .5) * 120, (Math.random() - .5) * 80, (Math.random() - .5) * 60);
    ring.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
    ring._speedX = (Math.random() - .5) * .003;
    ring._speedY = (Math.random() - .5) * .004;
    scene.add(ring);
    rings.push(ring);
  }

  let mx = 0, my = 0;
  document.addEventListener('mousemove', e => {
    mx = (e.clientX / window.innerWidth - .5) * 2;
    my = (e.clientY / window.innerHeight - .5) * 2;
  });

  let scrollInertia = 0;
  window.addEventListener('wheel', (e) => {
    scrollInertia += Math.abs(e.deltaY) * 0.035;
    if (scrollInertia > 25) scrollInertia = 25;
  }, { passive: true });

  const CONNECT_DIST = 38;
  let frame = 0;
  let hueShift = 0;
  let pulseIntensity = 0;
  let isCinematic = false;

  triggerNeuralPulse = () => { pulseIntensity = 1.3; };

  // Cinematic UI Engine
  const toggleCinematic = () => {
      isCinematic = !isCinematic;
      const sidebar = document.querySelector('.sidebar');
      const main = document.querySelector('.main');
      if(sidebar) {
          sidebar.style.transition = 'opacity 0.8s ease, transform 0.8s cubic-bezier(0.16, 1, 0.3, 1)';
          sidebar.style.opacity = isCinematic ? '0' : '1';
          sidebar.style.transform = isCinematic ? 'translateX(-20px)' : 'translateX(0)';
          sidebar.style.pointerEvents = isCinematic ? 'none' : 'auto';
      }
      if(main) {
          main.style.transition = 'opacity 0.8s ease, transform 0.8s cubic-bezier(0.16, 1, 0.3, 1)';
          main.style.opacity = isCinematic ? '0' : '1';
          main.style.transform = isCinematic ? 'scale(0.98) translateY(15px)' : 'scale(1) translateY(0)';
          main.style.pointerEvents = isCinematic ? 'none' : 'auto';
      }
  };

  // Bind to Shift + Z
  window.addEventListener('keydown', e => {
      if (e.shiftKey && (e.key.toLowerCase() === 'z' || e.code === 'KeyZ')) {
          toggleCinematic();
      }
  });

  // Physical Ripple Array
  const ripples = [];
  ['mousedown', 'dblclick'].forEach(evt => {
      document.getElementById('bg-canvas').addEventListener(evt, e => {
          ripples.push({ x: mx * spread * 0.8, y: -my * spread * 0.8, radius: 0, life: 1.0 });
      });
  });

  // Random ambient telemetry pulses
  // Random flashes removed per user request for a cleaner cinematic experience

  function animate() {
    requestAnimationFrame(animate);
    frame++;
    scrollInertia *= 0.92;
    
    // 1. Fluid Breathing Color Matrix
    hueShift += 0.05;
    document.documentElement.style.setProperty('--global-hue', hueShift);

    // 2. Pulse Sizing Decay & Dramatic Cinematic Warp
    pulseIntensity *= 0.975; // Slightly faster decay for impact
    ptMat.size = 1.4 + (pulseIntensity * 1.5);
    
    // Deep Camera Warp during Synthesis
    camera.fov = 60 - (pulseIntensity * 18); // Zooms aggressively in
    camera.updateProjectionMatrix();
    scene.rotation.y += pulseIntensity * 0.006; // Aggressively spin the network

    const currentHue = ((255 + hueShift) % 360) / 360; 
    
    if (pulseIntensity > 0.05) {
        lineMat.color.setHSL(currentHue, 1, 0.5 + pulseIntensity * 0.4); 
        lineMat.opacity = 0.2 + (pulseIntensity * 0.6);
    } else {
        lineMat.color.setHSL(currentHue, 1, 0.6);
        lineMat.opacity = 0.2;
    }
    ptMat.color.setHSL(currentHue, 0.8, 0.7);

    const pos = ptGeo.attributes.position.array;
    
    // Process ripples lifecycle
    for (let r = ripples.length - 1; r >= 0; r--) {
        const rip = ripples[r];
        rip.radius += 5.0; // Faster expansion
        rip.life -= 0.015; // Longer fade
        if (rip.life <= 0) ripples.splice(r, 1);
    }

    for (let i = 0; i < COUNT; i++) {
        // Apply Telemetry Ripples (Physical Push geometry only, omitting nonexistent vertex col buffers)
        for (let r = 0; r < ripples.length; r++) {
            const rip = ripples[r];
            const dxR = pos[i*3] - rip.x;
            const dyR = pos[i*3+1] - rip.y;
            // Native lock protects against rare 0-vector NaN division crashes destroying the ArrayBuffer
            const dist = Math.max(0.01, Math.sqrt(dxR*dxR + dyR*dyR)); 
            
            if (Math.abs(dist - rip.radius) < 30) {
                velocities[i].x += (dxR/dist) * 0.08 * rip.life;
                velocities[i].y += (dyR/dist) * 0.08 * rip.life;
            }
        }

        // Apply physical drag constraints to smoothly decay Ripple pushes
        velocities[i].x *= 0.99;
        velocities[i].y *= 0.99;
        
        // Restore natural baseline drift if particles slow down too much
        if(Math.abs(velocities[i].x) < 0.01) velocities[i].x += (Math.random()-0.5)*0.002;
        if(Math.abs(velocities[i].y) < 0.01) velocities[i].y += (Math.random()-0.5)*0.002;

        pos[i*3]   += velocities[i].x;
        pos[i*3+1] += velocities[i].y;
        pos[i*3+2] += velocities[i].z + scrollInertia;
      
        if (Math.abs(pos[i*3])   > spread/2) velocities[i].x *= -1;
        if (Math.abs(pos[i*3+1]) > spread/2) velocities[i].y *= -1;
        if (pos[i*3+2] > spread * 0.4) pos[i*3+2] = -spread * 0.6;
    }
    ptGeo.attributes.position.needsUpdate = true;

    let lineCount = 0;
    // Brain rapidly wires thousands of new connections during synthesis pulse
    const dynamicConnectDistSq = (38 + pulseIntensity * 45) * (38 + pulseIntensity * 45);

    for (let i = 0; i < COUNT && lineCount < MAX_LINES; i++) {
        for (let j = i + 1; j < COUNT && lineCount < MAX_LINES; j++) {
            const dx = pos[i*3] - pos[j*3];
            const dy = pos[i*3+1] - pos[j*3+1];
            const dz = pos[i*3+2] - pos[j*3+2];
            if (dx*dx + dy*dy + dz*dz < dynamicConnectDistSq) {
                linePositions[lineCount*6]   = pos[i*3];
                linePositions[lineCount*6+1] = pos[i*3+1];
                linePositions[lineCount*6+2] = pos[i*3+2];
                linePositions[lineCount*6+3] = pos[j*3];
                linePositions[lineCount*6+4] = pos[j*3+1];
                linePositions[lineCount*6+5] = pos[j*3+2];
                lineCount++;
            }
        }
    }
    lineGeo.attributes.position.needsUpdate = true;
    lineGeo.setDrawRange(0, lineCount * 2);

    rings.forEach(r => {
        r.rotation.x += r._speedX || .003;
        r.rotation.y += r._speedY || .004;
        r.position.z += scrollInertia * 2.5;
        if (r.position.z > 160) {
            r.position.z = -180 - Math.random() * 60;
            r.position.x = (Math.random() - .5) * 120;
            r.position.y = (Math.random() - .5) * 80;
        }
    });

    scene.rotation.y = frame * .0005 + mx * 0.25;
    scene.rotation.x = my * 0.12;
    renderer.render(scene, camera);
  }
  animate();
  } catch (e) {
    console.warn('Jarvis background renderer disabled:', e);
  }
})();

// --- LOCKSCREEN DRAGON AUTH SCENE ---
function resizeLockscreenScene() {
    if (window.__jarvisLockScene && typeof window.__jarvisLockScene.resize === 'function') {
        window.__jarvisLockScene.resize();
    }
}

function startLockscreenScene() {
    if (window.__jarvisLockScene && typeof window.__jarvisLockScene.start === 'function') {
        window.__jarvisLockScene.start();
    } else {
        setTimeout(() => {
            if (window.__jarvisLockScene && typeof window.__jarvisLockScene.start === 'function') {
                window.__jarvisLockScene.start();
            }
        }, 120);
    }
}

function stopLockscreenScene() {
    if (window.__jarvisLockScene && typeof window.__jarvisLockScene.stop === 'function') {
        window.__jarvisLockScene.stop();
    }
}

// --- GLOBAL INIT ---
let globalClients = [];
let dashboardRefreshLoopStarted = false;
let demoReadinessLoopStarted = false;
const API_BASE = (() => {
    try {
        if (window.location && /^https?:$/i.test(window.location.protocol)) {
            return window.location.origin;
        }
    } catch(e) {}
    return "http://localhost:8000";
})();
const JARVIS_SESSION_KEY = "jarvis_admin_session";
const nativeFetch = window.fetch.bind(window);
let appBootstrapped = false;
let appBootPromise = null;
let jarvisAuthEnabled = false;
const vaultDataCache = {};
const warmedVaultMedia = new Set();

function getJarvisSessionToken() {
    try { return localStorage.getItem(JARVIS_SESSION_KEY) || ''; } catch(e) { return ''; }
}

function setJarvisSessionToken(token) {
    try {
        if(token) localStorage.setItem(JARVIS_SESSION_KEY, token);
        else localStorage.removeItem(JARVIS_SESSION_KEY);
    } catch(e) {}
}

function buildApiUrl(path) {
    return `${API_BASE}${path}`;
}

function encodeAssetFilename(filename) {
    return String(filename || '').split('/').map(part => encodeURIComponent(part)).join('/');
}

function buildAssetUrl(clientId, filename) {
    return buildApiUrl(`/assets/${encodeURIComponent(clientId)}/${encodeAssetFilename(filename)}`);
}

function resolvePreviewUrl(rawUrl) {
    const value = String(rawUrl || '').trim();
    if(!value) return '';
    if(value.startsWith('http://') || value.startsWith('https://')) return value;
    return buildApiUrl(value.startsWith('/') ? value : `/${value}`);
}

function getVaultAssetPreviewUrl(clientId, file) {
    if(file && typeof file === 'object' && file.preview_url) {
        return resolvePreviewUrl(file.preview_url);
    }
    const filename = typeof file === 'string' ? file : file?.filename;
    return buildAssetUrl(clientId, filename);
}

function getVaultAssetPosterUrl(clientId, file) {
    if(!file || typeof file === 'string') return '';
    if(file.poster_url) return resolvePreviewUrl(file.poster_url);
    if(file.has_poster && file.filename) return `${buildAssetUrl(clientId, file.filename)}.jpg`;
    return '';
}

function getVaultAssetRecord(filename) {
    return currentVaultFiles.find(item => (typeof item === 'string' ? item : item.filename) === filename) || null;
}

/* #SECTION: UI Action Feedback */
function setButtonBusy(button, label) {
    if(!button) return null;
    if(!button.dataset.originalHtml) {
        button.dataset.originalHtml = button.innerHTML;
    }
    button.disabled = true;
    button.style.opacity = '0.72';
    button.innerHTML = `<span style="display:inline-flex; align-items:center; gap:8px;"><div class="spinner" style="width:14px; height:14px; border-width:2px; border-top-color:currentColor;"></div><span>${label}</span></span>`;
    return button.dataset.originalHtml;
}

function restoreButtonBusy(button) {
    if(!button) return;
    if(button.dataset.originalHtml) {
        button.innerHTML = button.dataset.originalHtml;
    }
    button.disabled = false;
    button.style.opacity = '1';
}

function startThinkingTicker(node, phases, intervalMs = 1400) {
    if(!node || !Array.isArray(phases) || !phases.length) return () => {};
    let index = 0;
    node.textContent = phases[0];
    const timer = window.setInterval(() => {
        index = (index + 1) % phases.length;
        node.textContent = phases[index];
    }, intervalMs);
    return () => window.clearInterval(timer);
}

function showBootOverlay(visible, message = '') {
    const overlay = document.getElementById('boot-overlay');
    const sub = document.getElementById('boot-sub');
    if(!overlay) return;
    if(message && sub) sub.textContent = message;
    overlay.classList.toggle('visible', !!visible);
    overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
}

function setBootStatus(message) {
    const sub = document.getElementById('boot-sub');
    if(sub && message) sub.textContent = message;
}

function warmVaultPreviewMedia(clientId, payload) {
    if(!payload || payload.status !== 'success') return;
    const files = Array.isArray(payload.files) ? payload.files : [];
    files.slice(0, 8).forEach(file => {
        const filename = typeof file === 'string' ? file : String(file?.filename || '').trim();
        const kind = typeof file === 'string' ? 'image' : String(file?.kind || 'image').toLowerCase();
        if(!filename || kind === 'video') return;
        const url = getVaultAssetPreviewUrl(clientId, file);
        if(warmedVaultMedia.has(url)) return;
        warmedVaultMedia.add(url);
        const img = new Image();
        img.decoding = 'async';
        img.src = url;
    });
}

async function fetchVaultData(clientId, options = {}) {
    const forceRefresh = !!options.forceRefresh;
    if(!clientId) return null;
    if(!forceRefresh && vaultDataCache[clientId]) return vaultDataCache[clientId];
    const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(clientId)}`));
    const data = await res.json();
    if(data && data.status === 'success') {
        vaultDataCache[clientId] = data;
        warmVaultPreviewMedia(clientId, data);
        return data;
    }
    throw new Error((data && (data.reason || data.message)) || 'Vault unavailable.');
}

async function preloadVaultCache(clientIds) {
    const ids = Array.isArray(clientIds) ? clientIds.filter(Boolean) : [];
    if(!ids.length) return;
    await Promise.allSettled(ids.map(clientId => fetchVaultData(clientId).catch(() => null)));
}

function showAuthOverlay(visible, message = '', isError = false) {
    const overlay = document.getElementById('auth-overlay');
    const stage = document.getElementById('auth-stage');
    const app = document.querySelector('.app');
    const note = document.getElementById('auth-note');
    const passwordInput = document.getElementById('auth-password');
    if(!overlay || !app) return;
    overlay.classList.remove('unlocking');
    if(stage) stage.classList.remove('unlocking');
    overlay.style.display = visible ? 'flex' : 'none';
    app.classList.toggle('auth-locked', visible);
    if (visible) {
        requestAnimationFrame(() => {
            resizeLockscreenScene();
            startLockscreenScene();
        });
    } else {
        stopLockscreenScene();
    }
    if(note) {
        note.textContent = message || (jarvisAuthEnabled ? 'Enter the Jarvis admin password to continue.' : '');
        note.style.color = isError ? '#8f3428' : 'rgba(106, 74, 44, 0.66)';
    }
    if(passwordInput) {
        passwordInput.value = '';
        if(visible) setTimeout(() => passwordInput.focus(), 40);
    }
}

function playUnlockTransition(onComplete) {
    const overlay = document.getElementById('auth-overlay');
    const app = document.querySelector('.app');
    if(!overlay) {
        onComplete();
        return;
    }
    if(window.__jarvisLockScene && typeof window.__jarvisLockScene.unlockBurst === 'function') {
        try { window.__jarvisLockScene.unlockBurst(); } catch(e) {}
    }
    if(app) {
        app.classList.add('auth-revealing');
        app.classList.remove('auth-locked');
    }
    overlay.classList.add('unlocking');
    setTimeout(() => {
        overlay.classList.remove('unlocking');
        if(app) app.classList.remove('auth-revealing');
        onComplete();
    }, 760);
}

function syncAuthUi() {
    const lockBtn = document.getElementById('sidebar-auth-btn');
    if(lockBtn) lockBtn.style.display = jarvisAuthEnabled ? 'block' : 'none';
}

async function handleAuthFailure(message = 'Session expired. Unlock Jarvis again to continue.') {
    setJarvisSessionToken('');
    showAuthOverlay(true, message, true);
    syncAuthUi();
}

window.fetch = async function(input, init = {}) {
    const requestUrl = typeof input === 'string' ? input : (input && input.url) || '';
    const isApiRequest = typeof requestUrl === 'string' && requestUrl.startsWith(`${API_BASE}/api/`);
    const nextInit = { ...init };

    if(isApiRequest && !requestUrl.includes('/api/auth/')) {
        const token = getJarvisSessionToken();
        if(jarvisAuthEnabled && !token) {
            handleAuthFailure();
            return new Response(JSON.stringify({ status: 'auth_required', reason: 'Jarvis admin authentication is required for this route.' }), {
                status: 401,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        const headers = new Headers(nextInit.headers || {});
        if(token) headers.set('X-Jarvis-Auth', token);
        nextInit.headers = headers;
    }

    const response = await nativeFetch(input, nextInit);
    if(isApiRequest && response.status === 401 && !requestUrl.includes('/api/auth/')) {
        handleAuthFailure();
    }
    return response;
};

function createApiEventSource(path) {
    const token = getJarvisSessionToken();
    const url = new URL(buildApiUrl(path));
    if(token) url.searchParams.set('session_token', token);
    return new EventSource(url.toString());
}

async function loginJarvis() {
    const passwordInput = document.getElementById('auth-password');
    const password = passwordInput ? passwordInput.value : '';
    try {
        const res = await nativeFetch(buildApiUrl('/api/auth/login'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password })
        });
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            jarvisAuthEnabled = !!data.auth_enabled;
            if(data.token) setJarvisSessionToken(data.token);
            syncAuthUi();
            playUnlockTransition(async () => {
                showBootOverlay(true, 'Booting Jarvis operator systems and syncing the agency workspace...');
                showAuthOverlay(false);
                try {
                    await bootstrapApp();
                } finally {
                    showBootOverlay(false);
                }
            });
            return;
        }
        showAuthOverlay(true, data.reason || 'Invalid Jarvis admin password.', true);
    } catch(e) {
        showAuthOverlay(true, 'Jarvis could not reach the local API while trying to authenticate.', true);
    }
}

async function logoutJarvis() {
    try {
        await nativeFetch(buildApiUrl('/api/auth/logout'), {
            method: 'POST',
            headers: getJarvisSessionToken() ? {'X-Jarvis-Auth': getJarvisSessionToken()} : {}
        });
    } catch(e) {}
    appBootstrapped = false;
    appBootPromise = null;
    setJarvisSessionToken('');
    Object.keys(vaultDataCache).forEach(key => delete vaultDataCache[key]);
    warmedVaultMedia.clear();
    showAuthOverlay(true, 'Dashboard locked. Re-enter the Jarvis admin password to continue.');
    syncAuthUi();
}

async function initializeJarvisAuth() {
    try {
        const headers = {};
        const token = getJarvisSessionToken();
        if(token) headers['X-Jarvis-Auth'] = token;
        const res = await nativeFetch(buildApiUrl('/api/auth/status'), { headers });
        const data = await res.json();
        jarvisAuthEnabled = !!data.auth_enabled;
        syncAuthUi();
        if(!data.auth_enabled || data.authenticated) {
            showAuthOverlay(false);
            showBootOverlay(true, 'Booting Jarvis operator systems and syncing the agency workspace...');
            try {
                await bootstrapApp();
            } finally {
                showBootOverlay(false);
            }
            return;
        }
        showAuthOverlay(true);
    } catch(e) {
        jarvisAuthEnabled = false;
        syncAuthUi();
        showBootOverlay(true, 'Starting Jarvis local workspace...');
        try {
            await bootstrapApp();
        } finally {
            showBootOverlay(false);
        }
    }
}

async function bootstrapApp() {
    if(appBootstrapped) return;
    if(appBootPromise) return appBootPromise;
    appBootPromise = (async () => {
        let clients = [];
        
        // Step 1: Linking Configs
        document.getElementById('boot-step-1')?.classList.add('active');
        document.getElementById('boot-step-2')?.classList.remove('active', 'done');
        document.getElementById('boot-step-3')?.classList.remove('active', 'done');
        setBootStatus('Linking client registries and reading the agency roster...');
        await new Promise(r => setTimeout(r, 600)); // Pacing for UI
        
        try {
            const res = await fetch(buildApiUrl("/api/clients"));
            const data = await res.json();
            if(data.status === "success" && Array.isArray(data.clients)) {
                clients = data.clients;
                globalClients = data.clients;
                populatePipelineSelectors(data.clients);
            }
        } catch(e) { console.log("System unlinked from CRM."); }
        
        // Step 2: Scheduling & Indexing
        document.getElementById('boot-step-1')?.classList.replace('active', 'done');
        document.getElementById('boot-step-2')?.classList.add('active');
        setBootStatus('Indexing schedules, approvals, and the live operator surface...');
        await new Promise(r => setTimeout(r, 700));

        const tasks = [
            renderDashboardSummary().catch(() => null),
            renderSchedule().catch(() => null),
        ];

        // Step 3: Vaults
        document.getElementById('boot-step-2')?.classList.replace('active', 'done');
        document.getElementById('boot-step-3')?.classList.add('active');
        
        if(clients.length > 0) {
            tasks.push(renderVaults().catch(() => null));
            tasks.push(renderConfigCards().catch(() => null));
            tasks.push((async () => {
                setBootStatus('Warming client vaults so creative previews open immediately...');
                await new Promise(r => setTimeout(r, 800));
                await preloadVaultCache(clients);
            })().catch(() => null));
        }

        await Promise.allSettled(tasks);
        document.getElementById('boot-step-3')?.classList.replace('active', 'done');
        await new Promise(r => setTimeout(r, 400)); // Final pause before vanishing
        
        startDashboardRefreshLoop();
        appBootstrapped = true;
    })().finally(() => {
        appBootPromise = null;
    });
    return appBootPromise;
}

function populatePipelineSelectors(clients) {
    const selectIds = ['tclient', 'legacy-dashboard-tclient'];
    selectIds.forEach(id => {
        const sel = document.getElementById(id);
        if(!sel) return;
        sel.innerHTML = '<option value="">Select Target Operations Vault...</option>';
        clients.forEach(c => {
            let opt = document.createElement("option");
            opt.value = c; opt.innerText = c;
            sel.appendChild(opt);
        });
    });
}

function startDashboardRefreshLoop() {
    if(dashboardRefreshLoopStarted) return;
    dashboardRefreshLoopStarted = true;
    setInterval(() => {
        try{ renderDashboardSummary(); } catch(e){}
        try{ renderSchedule(); } catch(e){}
        try{ renderVaults(); } catch(e){}
    }, 10000);
}

window.addEventListener('DOMContentLoaded', () => {
    initializeJarvisAuth();
    renderNavPings();
});

/* â”€â”€ UI LOGIC â”€â”€ */
const NAV_PING_STORAGE_KEY = 'jarvis_nav_ping_state_v1';
let currentPage = 'dashboard';

function loadNavPingState() {
  try {
    const raw = localStorage.getItem(NAV_PING_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch(e) {
    return {};
  }
}

let navPingState = loadNavPingState();

function saveNavPingState() {
  try {
    localStorage.setItem(NAV_PING_STORAGE_KEY, JSON.stringify(navPingState));
  } catch(e) {}
}

function renderNavPings() {
  ['schedule'].forEach(page => {
    const dot = document.getElementById(`nav-ping-${page}`);
    if(!dot) return;
    const state = navPingState[page] || {};
    dot.classList.toggle('active', !!state.active);
  });
}

function updateNavPing(page, signature, shouldPing) {
  const nextSignature = String(signature || '');
  const state = navPingState[page] || {};
  state.currentSignature = nextSignature;
  if(!shouldPing || !nextSignature) {
    state.active = false;
    state.seenSignature = nextSignature;
  } else if(currentPage === page) {
    state.active = false;
    state.seenSignature = nextSignature;
  } else if(state.seenSignature !== nextSignature) {
    state.active = true;
  } else {
    state.active = false;
  }
  navPingState[page] = state;
  saveNavPingState();
  renderNavPings();
}

function acknowledgeNavPing(page) {
  const state = navPingState[page];
  if(!state) return;
  state.active = false;
  state.seenSignature = String(state.currentSignature || '');
  navPingState[page] = state;
  saveNavPingState();
  renderNavPings();
}

function nav(page, el) {
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('p-' + page).classList.add('active');
  if (el) el.classList.add('active');
  if(page === 'schedule') acknowledgeNavPing(page);
  
  if(page === 'agents') loadAgencyConfig();
  if(page === 'dashboard') renderDashboardSummary();
  if(page === 'vaults') renderVaults();
  if(page === 'config') renderConfigCards();
  
  const cards = document.querySelectorAll(`#p-${page} .reveal-3d`);
  cards.forEach(c => c.style.animation = 'none');
  setTimeout(() => cards.forEach(c => c.style.animation = ''), 10);
}

const logsNav = document.querySelector(".nav-item:last-of-type");
if (logsNav && logsNav.innerText.includes("Audit")) {
    logsNav.onclick = function() { nav('dashboard', logsNav); };
}

async function loadAgencyConfig() {
    try {
        const res = await fetch(buildApiUrl("/api/agency/config"));
        const data = await res.json();
        if(data.owner_phone) document.getElementById('agency-owner-phone').value = data.owner_phone;
        if(data.whatsapp_access_token !== undefined) document.getElementById('agency-whatsapp-token').value = data.whatsapp_access_token || "";
        if(data.approval_routing) document.getElementById('agency-approval-routing').value = data.approval_routing;
    } catch(e) {}
}

async function saveAgencyConfig() {
    const phone = document.getElementById('agency-owner-phone').value;
    const whatsappToken = document.getElementById('agency-whatsapp-token').value;
    const approvalRouting = document.getElementById('agency-approval-routing').value;
    try {
        const res = await fetch(buildApiUrl("/api/agency/config"), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ owner_phone: phone, whatsapp_access_token: whatsappToken, approval_routing: approvalRouting })
        });
        if(res.ok) showNotification("Saved", "Agency Settings updated successfully.", false);
        else showNotification("Error", "Failed to save configuration.", true);
    } catch(e) { showNotification("Error", "Connection failed.", true); }
}
/* â”€â”€ HOLOGRAPHIC CURSOR ENGINE â”€â”€ */
async function downloadJarvisBackup() {
    try {
        const res = await fetch(buildApiUrl("/api/export-state"));
        const data = await res.json();
        if(!res.ok || data.status !== 'success') {
            throw new Error(data.reason || 'Backup export failed.');
        }
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        const stamp = new Date().toISOString().replace(/[:.]/g, '-');
        link.href = url;
        link.download = `jarvis-backup-${stamp}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showNotification('Backup Ready', 'Jarvis exported a full local state snapshot for safe keeping.', false, { position: 'bottom-right' });
    } catch(e) {
        showNotification('Backup Failed', e.message || 'Jarvis could not export the local state snapshot.', true, { position: 'bottom-right' });
    }
}
document.querySelectorAll('.hover-3d').forEach(card => {
  card.addEventListener('mousemove', e => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    card.style.setProperty('--mouse-x', `${x}px`);
    card.style.setProperty('--mouse-y', `${y}px`);
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = ((y - centerY) / centerY) * -6;
    const rotateY = ((x - centerX) / centerX) * 6;
    card.style.transform = `translateY(-4px) scale(1.02) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
  });

  card.addEventListener('mouseleave', () => {
    card.style.transform = `translateY(0) scale(1) rotateX(0) rotateY(0)`;
    card.style.transition = `transform 0.5s cubic-bezier(0.25, 1, 0.5, 1)`;
  });

  card.addEventListener('mouseenter', () => {
    card.style.transition = `transform 0.1s ease-out`;
  });
});

(function tick() {
  const n = new Date();
  document.getElementById('clock').textContent =
    String(n.getHours()).padStart(2,'0') + ':' +
    String(n.getMinutes()).padStart(2,'0') + ':' +
    String(n.getSeconds()).padStart(2,'0');
  setTimeout(tick, 1000);
})();

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderRuntimeRow(title, subtitle, badgeClass, badgeText) {
  return `
    <div class="runtime-row">
      <div>
        <div class="runtime-name">${escapeHtml(title)}</div>
        <div class="runtime-sub">${escapeHtml(subtitle)}</div>
      </div>
      <span class="badge ${badgeClass}">${escapeHtml(badgeText)}</span>
    </div>
  `;
}

function renderAttentionRow(title, copy, badgeClass, badgeText) {
  return `
    <div class="attention-row">
      <div>
        <div class="attention-title">${escapeHtml(title)}</div>
        <div class="attention-copy">${escapeHtml(copy)}</div>
      </div>
      <span class="badge ${badgeClass}">${escapeHtml(badgeText)}</span>
    </div>
  `;
}

function summarizeApprovalAssets(job) {
  const videos = Array.isArray(job?.videos) ? job.videos.length : 0;
  const images = Array.isArray(job?.images) ? job.images.length : 0;
  const kind = String(job?.media_kind || '').toLowerCase();
  if(videos || kind === 'video') return '1-video post';
  if(images > 1 || kind === 'image_carousel') return `${Math.max(images, 2)}-image carousel`;
  if(images === 1 || kind === 'image_single') return '1-image post';
  return 'Media ready';
}

function getApprovalRouteLabel(mode) {
  if(mode === 'desktop_and_whatsapp') return 'Desktop + WhatsApp';
  if(mode === 'whatsapp_only') return 'WhatsApp Only';
  return 'Desktop First';
}

function buildApprovalCaptionPreview(job) {
  const caption = String(job?.caption_text || '').trim();
  if(!caption) return 'No stored caption preview yet.';
  const words = caption.split(/\s+/).slice(0, 14).join(' ');
  return words + (caption.split(/\s+/).length > 14 ? '...' : '');
}

function buildApprovalAssetUrl(clientId, rawEntry) {
  const original = typeof rawEntry === 'string'
    ? rawEntry.trim()
    : String(rawEntry?.path || rawEntry?.filename || rawEntry?.name || '').trim();
  if(!original) return null;
  if(/^https?:\/\//i.test(original)) {
    return {
      label: original.split('/').pop() || original,
      url: original,
    };
  }

  const normalized = original.replace(/\\/g, '/').replace(/^\/+/, '');
  let resolvedClient = String(clientId || '').trim();
  let filename = normalized;

  if(normalized.startsWith('assets/')) {
    const stripped = normalized.slice('assets/'.length);
    const parts = stripped.split('/');
    if(parts.length > 1) {
      resolvedClient = parts.shift() || resolvedClient;
      filename = parts.join('/');
    } else {
      filename = stripped;
    }
  } else if(resolvedClient && normalized.startsWith(`${resolvedClient}/`)) {
    filename = normalized.slice(resolvedClient.length + 1);
  } else if(!resolvedClient && normalized.includes('/')) {
    const parts = normalized.split('/');
    if(parts.length > 1) {
      resolvedClient = parts.shift() || resolvedClient;
      filename = parts.join('/');
    }
  }

  if(!resolvedClient || !filename) return null;
  return {
    label: filename.split('/').pop() || filename,
    url: `${buildApiUrl('/assets')}/${encodeURIComponent(resolvedClient)}/${filename.split('/').map(part => encodeURIComponent(part)).join('/')}`,
  };
}

function buildApprovalMediaUrls(job) {
  const clientId = String(job?.client || '').trim();
  const imageUrls = Array.isArray(job?.images)
    ? job.images.map(name => buildApprovalAssetUrl(clientId, name)).filter(Boolean).map(item => ({ type: 'image', label: item.label, url: item.url }))
    : [];
  const videoUrls = Array.isArray(job?.videos)
    ? job.videos.map(name => buildApprovalAssetUrl(clientId, name)).filter(Boolean).map(item => ({ type: 'video', label: item.label, url: item.url }))
    : [];
  return [...imageUrls, ...videoUrls];
}

function formatApprovalScheduleLine(job) {
  const timeLabel = String(job?.time || '').trim();
  const isoDate = String(job?.scheduled_date || '').trim();
  if(isoDate) {
    try {
      const label = new Date(`${isoDate}T00:00:00`).toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric'
      });
      return `${label} at ${timeLabel}`;
    } catch(e) {}
  }
  if(Array.isArray(job?.days) && job.days.length) {
    return `${job.days.join(', ')} at ${timeLabel}`;
  }
  return timeLabel || 'Release window pending';
}

function getSidebarNavItem(page) {
  return Array.from(document.querySelectorAll('.nav-item')).find(node => {
    const raw = String(node.getAttribute('onclick') || '');
    return raw.includes(`'${page}'`) || raw.includes(`"${page}"`);
  }) || null;
}

function openPageSurface(page) {
  nav(page, getSidebarNavItem(page));
}

function escapeForSingleQuotedJs(value) {
  return String(value || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

async function postApprovalAction(approvalId, action, payload = null) {
  const actionPath = action ? `/${action}` : '';
  const res = await fetch(buildApiUrl(`/api/approvals/${encodeURIComponent(approvalId)}${actionPath}`), {
    method: 'POST',
    headers: payload ? {'Content-Type': 'application/json'} : {},
    body: payload ? JSON.stringify(payload) : null,
  });
  return await res.json();
}

function closeApprovalMoveModal() {
  document.getElementById('approval-move-modal').style.display = 'none';
  document.getElementById('approval-move-input').value = '';
  window._approvalMoveTarget = null;
}

function closeApprovalReviewModal() {
  document.getElementById('approval-review-modal').style.display = 'none';
  window._approvalReviewTarget = null;
}

function renderApprovalBriefLine(label, value, dir = 'ltr') {
  return `
    <div style="padding:12px 14px; border-radius:12px; border:1px solid rgba(255,255,255,.06); background:rgba(255,255,255,.02);">
      <div style="font-size:10px; color:var(--t4); text-transform:uppercase; letter-spacing:.12em; margin-bottom:6px;">${escapeHtml(label)}</div>
      <div dir="${dir}" style="font-size:13px; color:var(--t2); line-height:1.6;">${escapeHtml(value || 'Not set')}</div>
    </div>
  `;
}

function openApprovalReviewModal(approvalId) {
  const job = approvalCenterCache[approvalId];
  if(!job) {
    showNotification('Approval Unavailable', 'Jarvis could not find that approval in the live desktop queue.', true);
    return;
  }
  window._approvalReviewTarget = approvalId;
  document.getElementById('approval-review-title').textContent = `${String(job.client || '').replace(/[_-]/g, ' ')} · ${String(job.draft_name || 'Creative Draft')}`;
  document.getElementById('approval-review-subtitle').textContent = `Go-live ${job.scheduled_date ? new Date(job.scheduled_date + 'T00:00:00').toLocaleDateString(undefined, { weekday:'long', month:'long', day:'numeric' }) : (Array.isArray(job.days) ? job.days.join(', ') : 'Scheduled')} at ${job.time || ''}.`;
  const badges = document.getElementById('approval-review-badges');
  badges.innerHTML = [
    `<span class="badge b-pu">${escapeHtml(summarizeApprovalAssets(job))}</span>`,
      `<span class="badge ${job.whatsapp_sent ? 'b-on' : 'b-am'}">${job.whatsapp_sent ? 'WhatsApp Sent' : 'Desktop Review'}</span>`,
    `<span class="badge b-am">Ref ${escapeHtml(job.approval_id || '')}</span>`,
  ].join('');

  const media = buildApprovalMediaUrls(job);
  document.getElementById('approval-review-media').innerHTML = media.length
    ? media.map(item => item.type === 'video'
      ? `<div style="border-radius:14px; overflow:hidden; border:1px solid rgba(255,255,255,.06); background:rgba(255,255,255,.02);"><video src="${item.url}" controls playsinline preload="metadata" muted style="width:100%; display:block; background:#000;"></video><div style="padding:10px 12px; font-size:11px; color:var(--t3); font-family:'Space Mono', monospace;">${escapeHtml(item.label)}</div></div>`
      : `<div style="border-radius:14px; overflow:hidden; border:1px solid rgba(255,255,255,.06); background:rgba(255,255,255,.02);"><img src="${item.url}" alt="${escapeHtml(item.label)}" style="width:100%; height:220px; object-fit:cover; display:block;" /><div style="padding:10px 12px; font-size:11px; color:var(--t3); font-family:'Space Mono', monospace;">${escapeHtml(item.label)}</div></div>`
    ).join('')
    : `<div class="hq-empty-state">No media preview is attached to this approval yet.</div>`;

  document.getElementById('approval-review-caption').textContent = String(job.caption_text || '').trim() || 'No stored caption saved yet.';
  document.getElementById('approval-review-brief').innerHTML = [
    renderApprovalBriefLine('Focus', String(job.topic || `${job.draft_name || 'Creative Draft'} spotlight`)),
    renderApprovalBriefLine('Primary SEO Keyword', String(job.seo_keyword_used || 'Not set')),
    renderApprovalBriefLine('Caption Mode', String(job.caption_mode || 'ai').replace(/_/g, ' ')),
    renderApprovalBriefLine('Hashtags', Array.isArray(job.hashtags) && job.hashtags.length ? job.hashtags.join(' ') : 'No hashtags saved', 'auto'),
  ].join('');

  document.getElementById('approval-review-approve').onclick = () => approveFromCenter(approvalId, { skipConfirm: false, closeModal: true });
  document.getElementById('approval-review-move').onclick = () => {
    closeApprovalReviewModal();
    openApprovalMoveModal(approvalId, String(job.client || '').replace(/[_-]/g, ' '));
  };
  document.getElementById('approval-review-refine').onclick = () => rejectFromCenter(approvalId, { skipConfirm: false, closeModal: true });
  document.getElementById('approval-review-whatsapp').onclick = async () => {
    await sendApprovalToWhatsApp(approvalId);
    const freshJob = approvalCenterCache[approvalId];
    if(freshJob) openApprovalReviewModal(approvalId);
  };
  document.getElementById('approval-review-modal').style.display = 'flex';
}

function openApprovalMoveModal(approvalId, clientName) {
  window._approvalMoveTarget = approvalId;
  document.getElementById('approval-move-copy').textContent = `Tell Jarvis when ${clientName} should go live instead.`;
  document.getElementById('approval-move-modal').style.display = 'flex';
  const input = document.getElementById('approval-move-input');
  input.value = '';
  input.focus();
}

async function submitApprovalMove() {
  const approvalId = window._approvalMoveTarget;
  const releaseWindow = document.getElementById('approval-move-input').value.trim();
  if(!approvalId || !releaseWindow) {
    showNotification('Missing Window', 'Enter a new release window before updating the approval.', true);
    return;
  }
  const data = await postApprovalAction(approvalId, 'move', { release_window: releaseWindow });
  if(data.status === 'success') {
    closeApprovalMoveModal();
    showNotification('Approval Updated', 'Jarvis moved the release window and refreshed the approval state.', false, { position: 'bottom-right' });
    await renderApprovalCenter();
    await renderDashboardSummary();
    await renderSchedule();
    return;
  }
  showNotification('Move Rejected', data.reason || 'Jarvis could not update that approval.', true);
}

async function renderApprovalCenter() {
  const listEls = [
    document.getElementById('approval-center-list'),
    document.getElementById('approval-center-page-list'),
  ].filter(Boolean);
  const routingEls = [
    document.getElementById('approval-center-routing'),
    document.getElementById('approval-center-page-routing'),
  ].filter(Boolean);
  if(!listEls.length || !routingEls.length) return;
  try {
    const res = await fetch(buildApiUrl('/api/approvals/pending'));
    const data = await res.json();
    const approvals = Array.isArray(data.approvals) ? data.approvals : [];
    const routingMode = String(data.approval_routing || 'desktop_first');
    Object.keys(approvalCenterCache).forEach(key => delete approvalCenterCache[key]);
    approvals.forEach(job => {
      if(job && job.approval_id) approvalCenterCache[String(job.approval_id)] = job;
    });
    const approvalSignature = approvals.map(job => `${job.approval_id || ''}:${job.updated_at || job.requested_at || job.scheduled_date || ''}`).join('|');
    updateNavPing('approvals', approvalSignature || `count:${approvals.length}`, approvals.length > 0);
    routingEls.forEach(el => { el.textContent = `Routing: ${getApprovalRouteLabel(routingMode)}`; });
    if(!approvals.length) {
      listEls.forEach(el => {
        el.innerHTML = `<div class="hq-empty-state">No approvals are waiting. Jarvis will surface the next scheduled draft inline and can still mirror it to WhatsApp when needed.</div>`;
      });
      return;
    }

    const markup = approvals.map(job => {
      const approvalId = escapeHtml(job.approval_id || '');
      const clientRaw = String(job.client || '').replace(/[_-]/g, ' ');
      const client = escapeHtml(clientRaw);
      const draftName = escapeHtml(job.draft_name || 'Creative Draft');
      const focus = escapeHtml(job.topic || `${job.draft_name || 'Creative Draft'} spotlight`);
      const scheduleLine = escapeHtml(`${job.scheduled_date ? new Date(job.scheduled_date + 'T00:00:00').toLocaleDateString(undefined, { weekday:'long', month:'long', day:'numeric' }) : (Array.isArray(job.days) ? job.days.join(', ') : '')} at ${job.time || ''}`.trim());
      const captionPreview = escapeHtml(buildApprovalCaptionPreview(job));
      const whatsappBadge = job.whatsapp_sent
        ? `<span class="badge b-on">Sent to WhatsApp</span>`
        : `<span class="badge b-pu">Desktop Review</span>`;
      const sendButton = routingMode === 'whatsapp_only'
        ? ''
        : `<button class="hq-ghost-btn" onclick="sendApprovalToWhatsApp('${approvalId}')">${job.whatsapp_sent ? 'Resend WhatsApp' : 'Send to WhatsApp'}</button>`;
      return `
        <div class="attention-row" style="align-items:flex-start; gap:16px; flex-wrap:wrap;">
          <div style="flex:1; min-width:260px;">
            <div class="attention-title">${client} · ${draftName}</div>
            <div class="attention-copy" style="margin-top:4px;">Go-live: ${scheduleLine}</div>
            <div class="attention-copy" style="margin-top:4px;">Assets: ${escapeHtml(summarizeApprovalAssets(job))}</div>
            <div class="attention-copy" style="margin-top:4px;">Focus: ${focus}</div>
            <div class="attention-copy" dir="auto" style="margin-top:6px;">Caption: ${captionPreview}</div>
          </div>
          <div style="display:flex; flex-direction:column; gap:10px; align-items:flex-end; min-width:220px;">
            <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">${whatsappBadge}<span class="badge b-am">Ref ${approvalId}</span></div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
              <button class="hq-ghost-btn" onclick="openApprovalReviewModal('${approvalId}')">Review</button>
              <button class="hq-ghost-btn" onclick="approveFromCenter('${approvalId}')">Approve</button>
              <button class="hq-ghost-btn" onclick="openApprovalMoveModal('${approvalId}', '${clientRaw.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}')">Move Time</button>
              <button class="hq-ghost-btn" onclick="rejectFromCenter('${approvalId}')">Discard</button>
              ${sendButton}
            </div>
          </div>
        </div>
      `;
    }).join('');
    listEls.forEach(el => { el.innerHTML = markup; });
  } catch(e) {
    updateNavPing('approvals', '', false);
    listEls.forEach(el => {
      el.innerHTML = `<div class="hq-empty-state">Release controls could not load right now.</div>`;
    });
    routingEls.forEach(el => { el.textContent = 'Routing: unavailable'; });
  }
}

async function approveFromCenter(approvalId, options = {}) {
  const run = async () => {
    const data = await postApprovalAction(approvalId, 'approve');
    if(data.status === 'success') {
      showNotification('Approval Locked', 'Jarvis moved the draft into the live schedule.', false, { position: 'bottom-right' });
      if(options.closeModal) closeApprovalReviewModal();
    } else if(data.status === 'duplicate') {
      showNotification('Duplicate Prevented', 'A matching active schedule already exists, so Jarvis blocked the duplicate.', true, { position: 'bottom-right' });
      if(options.closeModal) closeApprovalReviewModal();
    } else {
      showNotification('Approval Failed', data.reason || 'Jarvis could not approve that draft.', true);
    }
    await renderApprovalCenter();
    await renderDashboardSummary();
    await renderSchedule();
    return data;
  };
  if(options.skipConfirm) return run();
  showConfirm(
    `Approve ${approvalId} and move it into the live schedule?`,
    async () => { await run(); },
    {
      title: 'Approve Release',
      confirmLabel: 'Approve & Schedule',
      tone: 'success',
      iconHtml: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>',
    }
  );
}

async function rejectFromCenter(approvalId, options = {}) {
  const run = async () => {
    const data = await postApprovalAction(approvalId, 'reject');
    if(data.status === 'success') {
      showNotification('Approval Discarded', 'Jarvis removed the draft from the live approval queue.', false, { position: 'bottom-right' });
      if(options.closeModal) closeApprovalReviewModal();
    } else {
      showNotification('Discard Failed', data.reason || 'Jarvis could not discard that approval.', true);
    }
    await renderApprovalCenter();
    await renderDashboardSummary();
    return data;
  };
  if(options.skipConfirm) return run();
  showConfirm(
    `Remove approval ${approvalId} from the live queue and send it back for refinement?`,
    async () => { await run(); },
    {
      title: 'Discard Approval',
      confirmLabel: 'Discard Approval',
      tone: 'info',
      iconHtml: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M18 2l4 4-10 10H8v-4z"/></svg>',
    }
  );
}

async function discardAllApprovals() {
  showConfirm(
      'Discard every pending approval in the live queue? This will clear the pending release lane without scheduling those drafts.',
    async () => {
      const data = await postApprovalAction('discard-all', '');
      if(data.status === 'success') {
        showNotification('Approval Queue Cleared', `Jarvis discarded ${data.removed || 0} pending approval${Number(data.removed || 0) === 1 ? '' : 's'}.`, false, { position: 'bottom-right' });
        if(window._approvalReviewTarget) closeApprovalReviewModal();
      } else {
        showNotification('Discard Failed', data.reason || 'Jarvis could not clear the approval queue.', true);
      }
      await renderApprovalCenter();
      await renderDashboardSummary();
    },
    {
      title: 'Discard All Approvals',
      confirmLabel: 'Discard All',
      tone: 'danger',
      iconHtml: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>',
    }
  );
}

async function sendApprovalToWhatsApp(approvalId) {
  const data = await postApprovalAction(approvalId, 'send-whatsapp');
  if(data.status === 'success') {
    showNotification('WhatsApp Routed', 'Jarvis pushed this approval into the mobile control lane.', false, { position: 'bottom-right' });
  } else {
    showNotification('WhatsApp Failed', data.reason || 'Jarvis could not send the approval card to WhatsApp.', true);
  }
  await renderApprovalCenter();
  await renderDashboardSummary();
  return data;
}

function renderOrchestratorApprovalState(tone, title, copy, actionsMarkup = '') {
  const palette = tone === 'success'
    ? { border: 'rgba(31,206,160,.22)', bg: 'rgba(31,206,160,.06)', text: 'var(--green)' }
    : tone === 'error'
      ? { border: 'rgba(224,85,85,.22)', bg: 'rgba(224,85,85,.06)', text: 'var(--red)' }
      : { border: 'rgba(139,108,247,.24)', bg: 'rgba(139,108,247,.07)', text: 'var(--purple)' };
  return `
    <div style="margin-top:12px; border:1px solid ${palette.border}; background:${palette.bg}; border-radius:16px; padding:14px 16px;">
      <div style="font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:${palette.text}; font-weight:700; margin-bottom:8px;">${escapeHtml(title)}</div>
      <div style="font-size:13px; color:var(--t2); line-height:1.6;">${escapeHtml(copy)}</div>
      ${actionsMarkup ? `<div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:12px;">${actionsMarkup}</div>` : ''}
    </div>
  `;
}

function renderOrchestratorApprovalCard(reply, action) {
  const job = action?.job || {};
  const approvalId = String(action?.approval_id || job?.approval_id || '').trim();
  if(!approvalId) {
    return `<div style="color:var(--t2); line-height:1.7;">${escapeHtml(String(reply || 'Jarvis prepared the release workflow.'))}</div>`;
  }
  approvalCenterCache[approvalId] = job;
  const clientRaw = String(job.client || '').replace(/[_-]/g, ' ');
  const captionPreview = buildApprovalCaptionPreview(job);
  const hostId = `chat-approval-${approvalId}-${Date.now()}`;
  const actionsMarkup = `
    <button class="hq-ghost-btn" onclick="approveApprovalFromChat('${escapeForSingleQuotedJs(approvalId)}','${hostId}')">Approve</button>
    <button class="hq-ghost-btn" onclick="openApprovalMoveModal('${escapeForSingleQuotedJs(approvalId)}','${escapeForSingleQuotedJs(clientRaw)}')">Move Time</button>
    <button class="hq-ghost-btn" onclick="discardApprovalFromChat('${escapeForSingleQuotedJs(approvalId)}','${hostId}')">Discard</button>
    <button class="hq-ghost-btn" onclick="sendApprovalToWhatsAppFromChat('${escapeForSingleQuotedJs(approvalId)}','${hostId}')">${job.whatsapp_sent ? 'Resend WhatsApp' : 'Send to WhatsApp'}</button>
    <button class="hq-ghost-btn" onclick="openApprovalReviewModal('${escapeForSingleQuotedJs(approvalId)}')">Review</button>
  `;
  return `
    <div style="color:var(--t2); line-height:1.7;">${escapeHtml(String(reply || action?.message || 'Jarvis prepared the release workflow.'))}</div>
    <div id="${hostId}">
      <div style="margin-top:12px; border:1px solid rgba(139,108,247,.18); background:rgba(255,255,255,.02); border-radius:16px; padding:16px;">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px; flex-wrap:wrap;">
          <div>
            <div style="font-size:14px; font-weight:700; color:var(--t1);">${escapeHtml(clientRaw)} · ${escapeHtml(String(job.draft_name || 'Creative Draft'))}</div>
            <div style="font-size:12px; color:var(--t3); margin-top:6px;">${escapeHtml(formatApprovalScheduleLine(job))}</div>
          </div>
          <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">
            <span class="badge b-pu">${escapeHtml(summarizeApprovalAssets(job))}</span>
      <span class="badge ${job.whatsapp_sent ? 'b-on' : 'b-am'}">${job.whatsapp_sent ? 'WhatsApp Sent' : 'Desktop Review'}</span>
            <span class="badge b-am">Ref ${escapeHtml(approvalId)}</span>
          </div>
        </div>
        <div style="font-size:12px; color:var(--t3); margin-top:12px;">Focus: ${escapeHtml(String(job.topic || `${job.draft_name || 'Creative Draft'} spotlight`))}</div>
        <div dir="auto" style="font-size:12px; color:var(--t2); line-height:1.7; margin-top:6px;">Caption: ${escapeHtml(captionPreview)}</div>
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:14px;">${actionsMarkup}</div>
      </div>
    </div>
  `;
}

async function approveApprovalFromChat(approvalId, hostId) {
  const host = document.getElementById(hostId);
  if(host) host.innerHTML = renderOrchestratorApprovalState('info', 'Locking Approval', 'Jarvis is moving this draft into the live schedule.');
  const data = await approveFromCenter(approvalId, { skipConfirm: true });
  if(!host) return;
  if(data?.status === 'success') {
    host.innerHTML = renderOrchestratorApprovalState(
      'success',
      'Release Scheduled',
      'Jarvis locked the draft into the live schedule. You can monitor delivery from Cron Schedule.',
      `<button class="hq-ghost-btn" onclick="openPageSurface('schedule')">Open Schedule</button>`
    );
    return;
  }
  if(data?.status === 'duplicate') {
    host.innerHTML = renderOrchestratorApprovalState(
      'error',
      'Duplicate Prevented',
      data.reason || 'A matching active schedule already exists, so Jarvis blocked the duplicate.',
      `<button class="hq-ghost-btn" onclick="openPageSurface('schedule')">Open Schedule</button>`
    );
    return;
  }
  host.innerHTML = renderOrchestratorApprovalState('error', 'Approval Failed', data?.reason || 'Jarvis could not approve that draft.');
}

async function discardApprovalFromChat(approvalId, hostId) {
  const host = document.getElementById(hostId);
  if(host) host.innerHTML = renderOrchestratorApprovalState('info', 'Discarding Approval', 'Jarvis is removing this draft from the approval lane.');
  const data = await rejectFromCenter(approvalId, { skipConfirm: true });
  if(!host) return;
  if(data?.status === 'success') {
    host.innerHTML = renderOrchestratorApprovalState('success', 'Approval Discarded', 'Jarvis removed the draft from the live approval queue.');
    return;
  }
  host.innerHTML = renderOrchestratorApprovalState('error', 'Discard Failed', data?.reason || 'Jarvis could not discard that approval.');
}

async function sendApprovalToWhatsAppFromChat(approvalId, hostId) {
  const host = document.getElementById(hostId);
  const data = await sendApprovalToWhatsApp(approvalId);
  if(!host) return;
  if(data?.status === 'success') {
    host.insertAdjacentHTML('beforeend', renderOrchestratorApprovalState('success', 'WhatsApp Routed', 'Jarvis pushed the approval into the mobile control lane.'));
    return;
  }
  host.insertAdjacentHTML('beforeend', renderOrchestratorApprovalState('error', 'WhatsApp Failed', data?.reason || 'Jarvis could not send the approval card to WhatsApp.'));
}

function closeClientValueBriefModal() {
  currentClientValueBrief = null;
  const modal = document.getElementById('value-brief-modal');
  if(modal) modal.style.display = 'none';
}

function renderValueBriefMetric(label, value, subline = '') {
  return `
    <div style="border:1px solid rgba(255,255,255,.06); border-radius:16px; background:rgba(255,255,255,.02); padding:14px 16px;">
      <div style="font-size:10px; color:var(--t4); font-weight:700; letter-spacing:.12em; text-transform:uppercase; margin-bottom:8px;">${escapeHtml(label)}</div>
      <div style="font-size:28px; color:var(--t1); font-weight:700; line-height:1;">${escapeHtml(String(value))}</div>
      <div style="font-size:11px; color:var(--t3); margin-top:8px; line-height:1.5;">${escapeHtml(subline)}</div>
    </div>
  `;
}

function renderValueBriefList(items, accent = 'var(--green)') {
  if(!Array.isArray(items) || !items.length) {
    return `<div class="hq-empty-state">Jarvis has nothing to show here yet.</div>`;
  }
  return items.map(item => `
    <div style="display:flex; align-items:flex-start; gap:10px;">
      <div style="width:8px; height:8px; border-radius:50%; background:${accent}; margin-top:7px; flex:0 0 auto;"></div>
      <div style="font-size:12.5px; color:var(--t2); line-height:1.65;">${escapeHtml(String(item || ''))}</div>
    </div>
  `).join('');
}

async function openClientValueBrief(clientId) {
  try {
    const res = await fetch(buildApiUrl(`/api/client-value-brief/${encodeURIComponent(clientId)}`));
    const data = await res.json();
    if(!res.ok || data.status !== 'success' || !data.brief) {
      showNotification('Operating Brief Unavailable', data.reason || 'Jarvis could not build the client operating brief right now.', true, { position: 'bottom-right' });
      return;
    }

    currentClientValueBrief = data.brief;
    const brief = data.brief;
    const metrics = brief.metrics || {};
    const readiness = brief.readiness || {};
    const timeline = brief.timeline || {};
    const narrative = brief.narrative || {};

    document.getElementById('value-brief-title').textContent = `${brief.display_name || clientId} | Client Operating Brief`;
    document.getElementById('value-brief-subtitle').textContent = `Jarvis is showing the live operating state for ${brief.display_name || clientId}: readiness, control, and execution from one operating system.`;
    document.getElementById('value-brief-badges').innerHTML = [
      `<span class="badge ${readiness.profile_ready ? 'b-on' : 'b-am'}">${readiness.profile_ready ? 'Brand Memory Ready' : 'Brand Memory Needs Work'}</span>`,
      `<span class="badge ${readiness.credentials_ready ? 'b-on' : 'b-am'}">${readiness.credentials_ready ? 'Publish Path Ready' : 'Credentials Incomplete'}</span>`,
      `<span class="badge ${readiness.mobile_control_ready ? 'b-pu' : 'b-am'}">${escapeHtml(readiness.approval_routing_label || 'Desktop First')}</span>`,
      `<span class="badge b-on">Readiness ${escapeHtml(String(readiness.score || 0))}%</span>`,
      `<span class="badge b-pu">Focus: ${escapeHtml(brief.focus_label || 'operations')}</span>`,
    ].join('');

    document.getElementById('value-brief-metrics').innerHTML = [
      renderValueBriefMetric('Assets', metrics.assets_count || 0, 'Live creative inputs secured in the client vault.'),
      renderValueBriefMetric('Drafts', metrics.draft_count || 0, 'Creative drafts staged for approvals and scheduling.'),
      renderValueBriefMetric('Approvals', metrics.pending_approval_count || 0, 'Items waiting in the approval control layer.'),
      renderValueBriefMetric('Live Jobs', metrics.active_job_count || 0, timeline.next_release_window ? `Next release: ${timeline.next_release_window}` : 'No active release queued yet.'),
      renderValueBriefMetric('Publish Runs', metrics.publish_run_count_30d || 0, metrics.publish_health_30d != null ? `${metrics.publish_health_30d}% handled cleanly in the last 30 days.` : 'No 30-day release history yet.'),
      renderValueBriefMetric('Voice Signals', metrics.voice_example_count || 0, `${metrics.copy_rule_count || 0} copy rules and ${metrics.seo_keyword_count || 0} SEO keywords locked in.`),
    ].join('');

    document.getElementById('value-brief-summary').textContent = narrative.summary || '';
    document.getElementById('value-brief-operator').textContent = narrative.operator_pitch || '';
    document.getElementById('value-brief-client').textContent = narrative.client_pitch || '';
    document.getElementById('value-brief-proof').innerHTML = renderValueBriefList(brief.proof_points || [], 'var(--green)');
    document.getElementById('value-brief-next').innerHTML = renderValueBriefList(brief.next_actions || [], 'var(--amber)');
    document.getElementById('value-brief-modal').style.display = 'flex';
  } catch(e) {
    showNotification('Operating Brief Failed', 'Jarvis could not reach the backend while building this client operating brief.', true, { position: 'bottom-right' });
  }
}

async function copyClientValueBrief() {
  if(!currentClientValueBrief?.copy_text) {
    showNotification('Nothing To Copy', 'Open a client operating brief first.', true, { position: 'bottom-right' });
    return;
  }
  try {
    await navigator.clipboard.writeText(String(currentClientValueBrief.copy_text));
    showNotification('Brief Copied', 'Jarvis copied the full client operating brief to your clipboard.', false, { position: 'bottom-right' });
  } catch(e) {
    showNotification('Copy Failed', 'The clipboard was blocked. Try copying again after interacting with the page.', true, { position: 'bottom-right' });
  }
}

function renderDemoCheckItem(item) {
  const status = String(item?.status || 'warn').toLowerCase();
  const badgeClass = status === 'pass' ? 'demo-check-pass' : status === 'fail' ? 'demo-check-fail' : 'demo-check-warn';
  const badgeText = status === 'pass' ? 'Ready' : status === 'fail' ? 'Blocked' : 'Attention';
  return `
    <div class="demo-check-item">
      <div class="demo-check-main">
        <div class="demo-check-title">${escapeHtml(item?.label || 'Untitled check')}</div>
        <div class="demo-check-copy">${escapeHtml(item?.detail || '')}</div>
      </div>
      <span class="demo-check-badge ${badgeClass}">${badgeText}</span>
    </div>
  `;
}

function renderOpsPriorityItem(item) {
  const status = String(item?.status || 'warn').toLowerCase();
  const badgeClass = status === 'pass' ? 'demo-check-pass' : status === 'fail' ? 'demo-check-fail' : 'demo-check-warn';
  const badgeText = status === 'pass' ? 'Clear' : status === 'fail' ? 'Blocked' : 'Attention';
  return `
    <div class="demo-check-item">
      <div class="demo-check-main">
        <div class="demo-check-title">${escapeHtml(item?.label || 'Untitled priority')}</div>
        <div class="demo-check-copy">${escapeHtml(item?.detail || '')}</div>
      </div>
      <span class="demo-check-badge ${badgeClass}">${badgeText}</span>
    </div>
  `;
}

function renderAgentStatusCard(card) {
  const tone = String(card?.tone || 'warn').toLowerCase();
  const liveClass = tone === 'on' ? 'on' : tone === 'off' ? 'off' : 'warn';
  const badgeClass = tone === 'on' ? 'b-on' : tone === 'off' ? 'b-re' : 'b-am';
  return `
    <div class="agent-status-card">
      <div class="agent-status-top">
        <div>
          <div class="agent-status-name">${escapeHtml(card?.name || 'Unknown Agent')}</div>
          <div class="agent-status-file">${escapeHtml(card?.file || '')}</div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="agent-status-live ${liveClass}"></span>
          <span class="badge ${badgeClass}">${escapeHtml(card?.state || 'Waiting')}</span>
        </div>
      </div>
      <div class="agent-status-copy">${escapeHtml(card?.detail || '')}</div>
    </div>
  `;
}

async function renderDashboardSummary() {
  const livePill = document.getElementById('dashboard-live-pill');
  try {
    const res = await fetch(buildApiUrl('/api/dashboard-summary'));
    const data = await res.json();
    if(data.status !== 'success') throw new Error('summary unavailable');
    const s = data.summary || {};
    const clients = Array.isArray(s.clients) ? s.clients : [];
    const nextJob = s.next_job;
    const approvalRouteLabel = getApprovalRouteLabel(String(s.approval_routing || 'desktop_first'));

    document.getElementById('hero-clients').textContent = s.client_count || 0;
    document.getElementById('hero-drafts').textContent = s.draft_count || 0;
    document.getElementById('hero-next-job').textContent = nextJob ? `${nextJob.client} · ${nextJob.display_window}` : 'No job queued';
    document.getElementById('dashboard-hero-copy').textContent = nextJob
      ? `Jarvis is tracking ${s.active_job_count || 0} active jobs across ${s.client_count || 0} clients. The next release window is ${nextJob.display_window} for ${nextJob.client}.`
      : `Jarvis is watching ${s.client_count || 0} client profiles and ${s.draft_count || 0} creative drafts. No approved job is queued right now.`;

    document.getElementById('metric-clients').textContent = s.client_count || 0;
    document.getElementById('metric-clients-sub').textContent = clients.length
      ? `${clients.filter(c => c.profile_ready && c.credentials_ready).length} fully ready for live publishing.`
      : 'Add your first client to activate the command center.';
    document.getElementById('metric-drafts').textContent = s.draft_count || 0;
    document.getElementById('metric-drafts-sub').textContent = `${s.asset_count || 0} media assets currently isolated across client vaults.`;
    document.getElementById('metric-active-jobs').textContent = s.active_job_count || 0;
    document.getElementById('metric-active-jobs-sub').textContent = nextJob
      ? `Next release: ${nextJob.client} · ${nextJob.display_window}`
      : 'Approve or schedule a draft to populate the live queue.';
    document.getElementById('metric-approvals').textContent = s.pending_approval_count || 0;
    document.getElementById('metric-approvals-sub').textContent = s.pending_approval_count
      ? `${s.pending_approval_count} draft${s.pending_approval_count === 1 ? '' : 's'} waiting. Route: ${approvalRouteLabel}.`
      : `Approval queue is currently clear. Route: ${approvalRouteLabel}.`;

    if(livePill) {
      if(s.scheduler_online) {
        livePill.innerHTML = `<div class="pill-dot"></div>Scheduler live · heartbeat ${s.heartbeat_age_seconds ?? 0}s ago`;
      } else {
        livePill.innerHTML = `<div class="pill-dot" style="background:var(--amber)"></div>Scheduler needs attention`;
      }
    }

    const opsSummaryCopy = document.getElementById('ops-summary-copy');
    if(opsSummaryCopy) {
      opsSummaryCopy.textContent = nextJob
        ? `Jarvis is tracking ${s.active_job_count || 0} live releases. The next release is ${nextJob.display_window} for ${nextJob.client}.`
        : `Jarvis is watching ${s.client_count || 0} clients, ${s.draft_count || 0} drafts, and the current runtime health across the operating system.`;
    }
    const opsSummaryStrip = document.getElementById('ops-summary-strip');
    if(opsSummaryStrip) {
      opsSummaryStrip.innerHTML = [
        `<div class="demo-summary-chip"><strong>${s.client_count || 0}</strong> clients</div>`,
        `<div class="demo-summary-chip"><strong>${s.draft_count || 0}</strong> drafts</div>`,
        `<div class="demo-summary-chip"><strong>${s.active_job_count || 0}</strong> live jobs</div>`,
        `<div class="demo-summary-chip"><strong>${s.pending_approval_count || 0}</strong> approvals</div>`,
      ].join('');
    }
    const opsPriorityList = document.getElementById('ops-priority-list');
    if(opsPriorityList) {
      const priorities = [];
      if(nextJob) {
        priorities.push({ label: 'Next release', detail: `${nextJob.client} is lined up for ${nextJob.display_window}.`, status: 'pass' });
      }
      if(s.pending_approval_count) {
        priorities.push({ label: 'Approvals waiting', detail: `${s.pending_approval_count} release approval${s.pending_approval_count === 1 ? '' : 's'} still need action.`, status: 'warn' });
      }
      const brokenClients = clients.filter(c => !c.credentials_ready || !c.profile_ready);
      if(brokenClients.length) {
        priorities.push({ label: 'Client setup attention', detail: `${brokenClients.length} client profile${brokenClients.length === 1 ? '' : 's'} still need credentials or brand intelligence.`, status: 'fail' });
      }
      if(!s.scheduler_online) {
        priorities.push({ label: 'Scheduler attention', detail: 'No recent heartbeat detected from scheduler.py.', status: 'warn' });
      }
      if(!priorities.length) {
        priorities.push({ label: 'Operating lane clear', detail: 'Jarvis is seeing a clean production surface right now.', status: 'pass' });
      }
      opsPriorityList.innerHTML = priorities.map(renderOpsPriorityItem).join('');
    }

    const attentionRows = [];
    if(nextJob) {
      attentionRows.push(renderAttentionRow('Next scheduled release', `${nextJob.client} is lined up for ${nextJob.display_window}.`, 'b-pu', 'Queued'));
    }
    if(s.pending_approval_count) {
      attentionRows.push(renderAttentionRow('Approvals waiting', `${s.pending_approval_count} approval request${s.pending_approval_count === 1 ? '' : 's'} still need a decision.`, 'b-am', 'Action'));
    }
    attentionRows.push(renderAttentionRow('Approval routing', `${approvalRouteLabel} keeps the workstation and mobile control lane in sync.`, 'b-pu', 'Policy'));
    clients.filter(c => !c.credentials_ready || !c.profile_ready).slice(0, 3).forEach(client => {
      const issueText = !client.profile_ready
        ? `Missing brand intelligence: ${(client.missing_fields || []).slice(0, 2).join(', ')}`
        : 'Live Meta credentials are incomplete for this client.';
      attentionRows.push(renderAttentionRow(client.display_name || client.client_id, issueText, 'b-re', 'Fix'));
    });
    if(!attentionRows.length) {
      attentionRows.push(renderAttentionRow('No blocking issues', 'Jarvis is seeing a clean operating surface right now.', 'b-on', 'Clear'));
    }
    const attentionQueue = document.getElementById('attention-queue');
    if(attentionQueue) attentionQueue.innerHTML = attentionRows.join('');

    const clientGrid = document.getElementById('client-readiness-grid');
    if(clientGrid) {
      if(!clients.length) {
        clientGrid.innerHTML = `<div class="hq-empty-state">No clients are registered yet. Use <strong>+ New Client</strong> to build your first live publishing account.</div>`;
      } else {
        clientGrid.innerHTML = clients.map(client => {
          const displayName = escapeHtml(client.display_name || client.client_id);
          const clientId = escapeHtml(client.client_id);
          const profileBadge = client.profile_ready ? '<span class="badge b-on">Profile Ready</span>' : '<span class="badge b-re">Profile Missing</span>';
          const credsBadge = client.credentials_ready ? '<span class="badge b-on">Credentials Ready</span>' : '<span class="badge b-am">Credentials Missing</span>';
          const footer = client.latest_drafts && client.latest_drafts.length
            ? client.latest_drafts.slice(0, 3).map(name => `<span class="badge b-pu">${escapeHtml(name)}</span>`).join('')
            : '<span class="badge b-off">No drafts yet</span>';
          return `
            <div class="client-ready-card">
              <div class="client-ready-top">
                <div>
                  <div class="client-ready-name">${displayName}</div>
                  <div class="client-ready-meta">@${clientId}</div>
                </div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">${profileBadge}${credsBadge}</div>
              </div>
              <div class="client-ready-stats">
                <div class="client-ready-stat"><strong>${client.asset_count || 0}</strong><span>Assets</span></div>
                <div class="client-ready-stat"><strong>${client.draft_count || 0}</strong><span>Drafts</span></div>
                <div class="client-ready-stat"><strong>${client.active_job_count || 0}</strong><span>Live Jobs</span></div>
              </div>
              <div class="client-ready-footer">${footer}</div>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <button class="hq-ghost-btn" onclick="openVaultModal('${clientId}')">Open Vault</button>
                <button class="hq-ghost-btn" onclick="openClientValueBrief('${clientId}')">Operating Brief</button>
                <button class="hq-ghost-btn" onclick="nav('config', document.getElementById('nav-config'))">Client Config</button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    if(Array.isArray(s.recent_activity) && s.recent_activity.length) {
      const log = document.getElementById('activity-log');
      if(log && !log.dataset.seeded) {
        log.innerHTML = s.recent_activity.slice().reverse().map((line, index) => {
          const match = String(line).replace(/</g, '&lt;').replace(/>/g, '&gt;');
          return `<div class="log-item"><div class="lt">BOOT</div><div class="ld" style="background:var(--blue)"></div><div class="lx">${match}</div></div>`;
        }).join('');
        log.dataset.seeded = 'true';
      }
    }
  } catch (e) {
    if(livePill) livePill.innerHTML = `<div class="pill-dot" style="background:var(--amber)"></div>Dashboard summary unavailable`;
    const opsSummaryCopy = document.getElementById('ops-summary-copy');
    if(opsSummaryCopy) opsSummaryCopy.textContent = 'Jarvis could not read the live operating summary from the backend.';
    const opsPriorityList = document.getElementById('ops-priority-list');
    if(opsPriorityList) opsPriorityList.innerHTML = `<div class="hq-empty-state">Operations summary is unavailable until the backend responds.</div>`;
    const attentionQueue = document.getElementById('attention-queue');
    if(attentionQueue) attentionQueue.innerHTML = `<div class="hq-empty-state">Runtime summary is unavailable until the backend responds.</div>`;
    const clientGrid = document.getElementById('client-readiness-grid');
    if(clientGrid) clientGrid.innerHTML = `<div class="hq-empty-state">Client readiness could not be loaded right now.</div>`;
  }
}

async function renderDemoReadiness(force = false) {
  const checklist = document.getElementById('demo-checklist');
  const summary = document.getElementById('demo-readiness-summary');
  const suggestions = document.getElementById('demo-suggestions');
  const summaryStrip = document.getElementById('demo-summary-strip');
  const startScript = document.getElementById('demo-start-script');
  const statusScript = document.getElementById('demo-status-script');
  const stopScript = document.getElementById('demo-stop-script');

  if(checklist) {
    checklist.innerHTML = `<div class="hq-empty-state">Jarvis is running the pre-demo audit...</div>`;
  }

  try {
    const url = force ? `${buildApiUrl('/api/demo-readiness')}?force=1&t=${Date.now()}` : buildApiUrl('/api/demo-readiness');
    const res = await fetch(url);
    const data = await res.json();
    if(data.status !== 'success') throw new Error('readiness unavailable');
    const readiness = data.readiness || {};
    const checks = Array.isArray(readiness.checks) ? readiness.checks : [];
    const readyCount = checks.filter(check => String(check.status).toLowerCase() === 'pass').length;
    const blockedCount = checks.filter(check => String(check.status).toLowerCase() === 'fail').length;
    const summaryData = readiness.summary || {};
    const recommended = summaryData.recommended_demo_client;

    if(summary) {
      if(readiness.overall_status === 'ready') {
        summary.textContent = recommended
          ? `This machine is in good shape for a live walkthrough. Lead with ${recommended.display_name}, which already has ${recommended.draft_count} draft${recommended.draft_count === 1 ? '' : 's'} prepared.`
          : 'This machine is in good shape for a live walkthrough.';
      } else if(readiness.overall_status === 'blocked') {
        summary.textContent = 'Jarvis found hard blockers that should be fixed before a client-facing demo.';
      } else {
        summary.textContent = 'Jarvis found a few issues worth tightening before the next walkthrough.';
      }
    }

    if(summaryStrip) {
      summaryStrip.innerHTML = [
        `<div class="demo-summary-chip"><strong>${readyCount}</strong> checks ready</div>`,
        `<div class="demo-summary-chip"><strong>${blockedCount}</strong> blockers</div>`,
        `<div class="demo-summary-chip"><strong>${summaryData.client_count || 0}</strong> clients mapped</div>`,
        `<div class="demo-summary-chip"><strong>${summaryData.draft_count || 0}</strong> drafts available</div>`,
      ].join('');
    }

    if(checklist) {
      checklist.innerHTML = checks.length
        ? checks.map(renderDemoCheckItem).join('')
        : `<div class="hq-empty-state">No readiness checks were returned by the backend.</div>`;
    }

    if(suggestions) {
      const rows = Array.isArray(readiness.suggestions) && readiness.suggestions.length
        ? readiness.suggestions
        : ['Jarvis does not see any special prep items right now.'];
      suggestions.innerHTML = rows.map(row => `<div class="demo-suggestion-item">${escapeHtml(row)}</div>`).join('');
    }

    if(startScript) startScript.textContent = readiness.startup?.start_script || 'scripts/start_demo.sh';
    if(statusScript) statusScript.textContent = readiness.startup?.status_script || 'scripts/demo_status.sh';
    if(stopScript) stopScript.textContent = readiness.startup?.stop_script || 'scripts/stop_demo.sh';
  } catch (e) {
    if(summary) summary.textContent = 'Jarvis could not run the pre-demo readiness audit from the backend.';
    if(checklist) checklist.innerHTML = `<div class="hq-empty-state">Pre-demo checklist unavailable until the backend responds.</div>`;
    if(suggestions) suggestions.innerHTML = `<div class="demo-suggestion-item">Restart the API if the demo-readiness endpoint is not available yet.</div>`;
  }
}

// --- SSE LOG STREAMING ---
function appendLog(timeStr, text, color) {
  const log = document.getElementById('activity-log');
  const row = document.createElement('div');
  row.className = 'log-item';
  row.innerHTML = `<div class="lt">${timeStr}</div><div class="ld" style="background:var(--${color})"></div><div class="lx">${text}</div>`;
  log.prepend(row);
  if (log.children.length > 25) log.lastChild.remove();
}

try {
  const eventSource = createApiEventSource("/api/stream-logs");
  eventSource.onmessage = function(e) {
      try {
          const data = JSON.parse(e.data);
          const now = new Date();
          const timeStr = String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');
          let color = "blue";
          if (data.message.includes("ERROR") || data.message.includes("ESCALATED")) color = "red";
          else if (data.message.includes("SUCCESS") || data.message.includes("OUT")) color = "green";
          else if (data.message.includes("SYSTEM") || data.message.includes("API")) color = "purple";
          
          appendLog(timeStr, `<strong>SYSTEM</strong> Â· ${data.message}`, color);
          try{ triggerNeuralPulse(); } catch(e){} 
      } catch(err) {}
  };
} catch(e) { console.error("SSE Failed", e); }

// --- DRAG AND DROP API ---
let uploadedImagePath = null;
function previewImage(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    
    // Vault Isolation Check
    const client = document.getElementById('tclient').value;
    if(!client) {
        showNotification("Isolated Vault Error", "You must select a target Client from the drop-down before uploading assets.", true);
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
      document.getElementById('p-drop-preview').src = e.target.result;
      document.getElementById('p-drop-preview').style.display = 'block';
      document.getElementById('p-drop-text').style.display = 'none';
      document.getElementById('p-dropzone').style.borderColor = 'var(--green)';
    };
    reader.readAsDataURL(file);
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("client_id", client);
    
    fetch(buildApiUrl("/api/upload-image"), { method: "POST", body: formData })
      .then(res => res.json())
      .then(data => {
          uploadedImagePath = data.file_path;
          const now = new Date();
          appendLog(now.getHours()+":"+now.getMinutes(), `<strong>API</strong> Â· Vaulted asset to ${uploadedImagePath}`, "green");
      }).catch(err => showNotification("Upload Disconnected", "Asset node unavailable. Is the server running?", true));
  }
}

// --- API ACTIONS & VALIDATION HUD ---
function showHUDError(fields) {
  const hud = document.createElement('div');
  hud.style.position = 'fixed';
  hud.style.top = '15%';
  hud.style.left = '50%';
  hud.style.transform = 'translate(-50%, -20px)';
  hud.style.background = 'rgba(2,2,10,0.85)';
  hud.style.border = `1px solid rgba(${INTAKE_CRYSTAL_RGB},0.42)`;
  hud.style.boxShadow = `0 10px 40px rgba(${INTAKE_CRYSTAL_RGB},0.16), inset 0 0 20px rgba(${INTAKE_CRYSTAL_RGB},0.06)`;
  hud.style.borderRadius = '14px';
  hud.style.padding = '24px 32px';
  hud.style.zIndex = '9999';
  hud.style.backdropFilter = 'blur(16px)';
  hud.style.color = 'var(--t1)';
  hud.style.opacity = '0';
  hud.style.transition = 'all 0.4s cubic-bezier(0.25, 1, 0.5, 1)';
  
  let html = `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px;color:${INTAKE_CRYSTAL}"><div style="display:flex;align-items:center;gap:12px;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><span style="font-size:16px;font-weight:700;letter-spacing:-0.5px">Context Synthesis Rejected</span></div><button onclick="this.closest('div[style*=fixed]').remove()" style="background:transparent;border:1px solid rgba(255,255,255,0.12);color:var(--t3);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:11px;font-family:'Space Mono';">Close</button></div>`;
  html += `<div style="font-size:13px;color:var(--t3);margin-bottom:12px">The client intake is missing critical brand intelligence that Jarvis needs before it can build a reliable voice profile:</div>`;
  
  fields.forEach(f => {
      html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-family:'Space Mono';font-size:12px;color:${INTAKE_CRYSTAL_SOFT}"><div style="width:4px;height:4px;background:${INTAKE_CRYSTAL};border-radius:50%"></div>${f}</div>`;
  });
  
  html += `<div style="font-size:11px;color:var(--t4);margin-top:16px;opacity:0.7">Add the missing details to the intake text, especially services, target audience, brand identity, copy rules, and 3-5 real brand voice examples.</div>`;
  
  hud.innerHTML = html;
  document.body.appendChild(hud);
  
  setTimeout(() => { hud.style.opacity = '1'; hud.style.transform = 'translate(-50%, 0)'; }, 10);
  setTimeout(() => {
      hud.style.opacity = '0';
      hud.style.transform = 'translate(-50%, 10px)';
      setTimeout(() => hud.remove(), 400);
  }, 16000);
}

function showNotification(title, message, isError = false, options = {}) {
  const hud = document.createElement('div');
  const position = options.position || 'top-center';
  hud.style.position = 'fixed';
  if(position === 'bottom-right') {
    hud.style.right = '28px';
    hud.style.bottom = '26px';
    hud.style.transform = 'translate(0, 20px)';
  } else if(position === 'bottom-center') {
    hud.style.left = '50%';
    hud.style.bottom = '26px';
    hud.style.transform = 'translate(-50%, 20px)';
  } else {
    hud.style.top = '8%';
    hud.style.left = '50%';
    hud.style.transform = 'translate(-50%, -20px)';
  }
  hud.style.background = 'rgba(2,2,10,0.85)';
  const accent = options.accent || (isError ? 'var(--red)' : 'var(--green)');
  const rgb = options.rgb || (isError ? '224,85,85' : '31,206,160');
  const duration = Number.isFinite(options.duration) ? options.duration : 4000;
  const messageColor = options.messageColor || 'var(--t3)';
  const icon = isError 
    ? `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`
    : `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
  hud.style.border = `1px solid rgba(${rgb},0.4)`;
  hud.style.boxShadow = `0 10px 40px rgba(${rgb},0.15), inset 0 0 20px rgba(${rgb},0.05)`;
  hud.style.borderRadius = '14px'; hud.style.padding = '20px 28px';
  hud.style.zIndex = '9999'; hud.style.backdropFilter = 'blur(16px)';
  hud.style.color = 'var(--t1)'; hud.style.opacity = '0';
  hud.style.transition = 'all 0.4s cubic-bezier(0.25, 1, 0.5, 1)';
  
  hud.innerHTML = `<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;color:${accent}">
    ${icon} <span style="font-size:15px;font-weight:700;letter-spacing:-0.5px">${title}</span></div>
    <div style="font-size:12.5px;color:${messageColor};line-height:1.5">${message}</div>`;
    
  document.body.appendChild(hud);
  setTimeout(() => {
      hud.style.opacity = '1';
      hud.style.transform = position === 'bottom-right'
        ? 'translate(0, 0)'
        : position === 'bottom-center'
        ? 'translate(-50%, 0)'
        : 'translate(-50%, 0)';
  }, 10);
  setTimeout(() => {
      hud.style.opacity = '0';
      hud.style.transform = position === 'bottom-right'
        ? 'translate(0, 10px)'
        : position === 'bottom-center'
        ? 'translate(-50%, 10px)'
        : 'translate(-50%, 10px)';
      setTimeout(() => hud.remove(), 400);
  }, duration);
}

function parseCsvInput(value) {
  return (value || '').split(',').map(part => part.trim()).filter(Boolean);
}

function parseLineInput(value) {
  return (value || '').split('\n').map(part => part.trim()).filter(Boolean);
}

const INTAKE_CRYSTAL = '#74c8ff';
const INTAKE_CRYSTAL_RGB = '116,200,255';
const INTAKE_CRYSTAL_SOFT = '#b8e6ff';
const INTAKE_WARNING = '#f4d38a';
const INTAKE_SUCCESS = '#8df0c4';
const INTAKE_ERROR = '#ff8c9b';

function setIntakeReviewStatus(message, tone = 'neutral') {
  const el = document.getElementById('c-review-status');
  if(!el) return;
  const colors = {
    neutral: INTAKE_CRYSTAL_SOFT,
    success: INTAKE_SUCCESS,
    warning: INTAKE_WARNING,
    error: INTAKE_ERROR
  };
  el.innerHTML = `<span style="color:${colors[tone] || colors.neutral}">${message}</span>`;
}

function populateIntakeProfileForm(profile = {}) {
  const voice = profile.brand_voice || {};
  const toneValue = Array.isArray(voice.tone) ? voice.tone.join(', ') : (voice.tone || '');
  document.getElementById('c-business').value = profile.business_name || '';
  document.getElementById('c-industry').value = profile.industry || '';
  document.getElementById('c-audience').value = profile.target_audience || '';
  document.getElementById('c-identity').value = profile.identity || '';
  document.getElementById('c-services').value = Array.isArray(profile.services) ? profile.services.join(', ') : '';
  document.getElementById('c-tone').value = toneValue;
  document.getElementById('c-style').value = voice.style || '';
  document.getElementById('c-dialect').value = voice.dialect_notes || '';
  document.getElementById('c-voice-examples').value = Array.isArray(profile.brand_voice_examples) ? profile.brand_voice_examples.join('\n') : '';
  document.getElementById('c-seo').value = Array.isArray(profile.seo_keywords) ? profile.seo_keywords.join(', ') : '';
  document.getElementById('c-hashtags').value = Array.isArray(profile.hashtag_bank) ? profile.hashtag_bank.join(', ') : '';
  document.getElementById('c-banned').value = Array.isArray(profile.banned_words) ? profile.banned_words.join(', ') : '';
  document.getElementById('c-rules').value = Array.isArray(profile.dos_and_donts) ? profile.dos_and_donts.join('\n') : '';

  const lang = profile.language_profile || {};
  document.getElementById('c-target-voice').value = lang.target_voice_language || 'arabic_gulf';
  syncIntakeJsonPreview();
}

function buildIntakeProfileJson() {
  return {
    business_name: document.getElementById('c-business').value.trim(),
    industry: document.getElementById('c-industry').value.trim(),
    identity: document.getElementById('c-identity').value.trim(),
    target_audience: document.getElementById('c-audience').value.trim(),
    services: parseCsvInput(document.getElementById('c-services').value),
    seo_keywords: parseCsvInput(document.getElementById('c-seo').value),
    hashtag_bank: parseCsvInput(document.getElementById('c-hashtags').value),
    banned_words: parseCsvInput(document.getElementById('c-banned').value),
    brand_voice_examples: parseLineInput(document.getElementById('c-voice-examples').value),
    dos_and_donts: parseLineInput(document.getElementById('c-rules').value),
    caption_defaults: {
      min_length: 150,
      max_length: 300,
      hashtag_count_min: 3,
      hashtag_count_max: 5
    },
    language_profile: {
      target_voice_language: document.getElementById('c-target-voice').value
    },
    brand_voice: {
      tone: parseCsvInput(document.getElementById('c-tone').value),
      style: document.getElementById('c-style').value.trim(),
      dialect: document.getElementById('c-target-voice').value === 'arabic_msa' ? 'msa' : (document.getElementById('c-target-voice').value.includes('arabic') ? 'gulf_arabic_khaleeji' : 'english'),
      dialect_notes: document.getElementById('c-dialect').value.trim()
    }
  };
}

function syncIntakeJsonPreview() {
  const preview = document.getElementById('c-json-preview');
  if(!preview) return;
  const profile = buildIntakeProfileJson();
  const hasSignal = Boolean(
    profile.business_name ||
    profile.industry ||
    profile.identity ||
    profile.target_audience ||
    profile.services.length ||
    profile.brand_voice_examples.length
  );
  preview.value = hasSignal ? JSON.stringify(profile, null, 2) : '';
}

// --- FILE UPLOAD HANDLER ---
async function handleBrandFile(input) {
    const file = input.files[0];
    if(!file) return;
    const status = document.getElementById('file-drop-status');
    const ext = file.name.split('.').pop().toLowerCase();

    if(['txt', 'md'].includes(ext)) {
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('c-context').value = e.target.result;
            status.textContent = `Imported ${file.name} into the intake editor - ${(file.size/1024).toFixed(1)} KB`;
        };
        reader.readAsText(file);
        return;
    }

    if(ext === 'pdf' || ext === 'docx') {
        status.innerHTML = `<span style="color:var(--amber)">Extracting readable text from ${ext.toUpperCase()}...</span>`;
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch(buildApiUrl("/api/parse-client-brief"), { method: "POST", body: formData });
            const data = await res.json();
            if(!res.ok || data.status !== 'success') {
                status.innerHTML = `<span style="color:var(--red)">${data.reason || 'Jarvis could not parse this brief file.'}</span>`;
                return;
            }
            document.getElementById('c-context').value = data.text;
            status.textContent = `Extracted ${data.source_type.toUpperCase()} brief - ${data.char_count} readable characters imported`;
            return;
        } catch(e) {
            status.innerHTML = `<span style="color:var(--red)">Jarvis could not reach the brief parser backend.</span>`;
            return;
        }
    }

    status.innerHTML = `<span style="color:var(--red)">Unsupported file type: .${ext}. Use TXT, MD, PDF, or DOCX.</span>`;
}

// Drag-and-drop support
document.addEventListener('DOMContentLoaded', () => {
    const zone = document.getElementById('file-drop-zone');
    if(zone) {
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor='rgba(139,108,247,.6)'; zone.style.background='rgba(139,108,247,.12)'; });
        zone.addEventListener('dragleave', e => { zone.style.borderColor='rgba(139,108,247,.25)'; zone.style.background='rgba(139,108,247,.04)'; });
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.style.borderColor='rgba(139,108,247,.25)'; zone.style.background='rgba(139,108,247,.04)';
            const file = e.dataTransfer.files[0];
            if(file) {
                const input = document.getElementById('file-input-brand');
                const dt = new DataTransfer();
                dt.items.add(file);
                input.files = dt.files;
                handleBrandFile(input);
            }
        });
    }

    ['c-name','c-business','c-industry','c-audience','c-identity','c-services','c-tone','c-style','c-dialect','c-voice-examples','c-seo','c-hashtags','c-banned','c-rules'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.addEventListener('input', syncIntakeJsonPreview);
    });

    syncIntakeJsonPreview();
});

async function synthesizeClient() {
  const name = document.getElementById('c-name').value.trim();
  const context = document.getElementById('c-context').value.trim();
  if(!name || !context) return showNotification("Missing Brief", "Client ID and client brief are both required before Jarvis can analyze the account.", true);
  
  const btn = document.getElementById('btn-synth');
  btn.innerText = "Analyzing Brief...";
  setIntakeReviewStatus("Jarvis is analyzing the brief and building a structured brand profile...", "neutral");
  try{ triggerNeuralPulse(); } catch(e){}
  const progressNote1 = setTimeout(() => {
      setIntakeReviewStatus("Jarvis is still analyzing the brief. Larger profiles can take around a minute on the current model path...", "neutral");
  }, 15000);
  const progressNote2 = setTimeout(() => {
      setIntakeReviewStatus("Still building the profile. Jarvis is waiting on the provider, not frozen.", "neutral");
  }, 45000);
  
  try {
      const res = await fetch(buildApiUrl("/api/synthesize-client"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client_name: name, raw_context: context })
      });
      const data = await res.json();
      
      if(data.status === "success") {
          populateIntakeProfileForm(data.data || {});
          document.getElementById('c-json-preview').style.borderColor = "var(--green)";
          setIntakeReviewStatus("Structured profile extracted. Review the brand fields, then save live credentials for this client.", "success");
      } else if (data.status === "missing") {
          populateIntakeProfileForm(data.data || {});
          showHUDError(data.missing_fields);
          document.getElementById('c-json-preview').style.borderColor = "var(--amber)";
          setIntakeReviewStatus("Jarvis extracted a partial profile. Fill the highlighted missing brand intelligence before saving.", "warning");
      } else {
          setIntakeReviewStatus(data.reason || "Jarvis could not build a valid brand profile from this brief.", "error");
          showNotification("Analysis Failed", data.reason || "Jarvis could not return a valid structured profile from this brief.", true);
      }
  } catch(e) {
      setIntakeReviewStatus("Jarvis could not reach the synthesis backend.", "error");
      showNotification("Connection Failed", "Jarvis could not reach the FastAPI backend.", true);
  } finally {
      clearTimeout(progressNote1);
      clearTimeout(progressNote2);
  }
  
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> Analyze Client Brief`;
}

async function saveClientProfile() {
  const cid = document.getElementById('c-name').value.trim();
  const phone = document.getElementById('c-phone').value.trim();
  const token = document.getElementById('c-token').value.trim();
  const fb = document.getElementById('c-fb').value.trim();
  const ig = document.getElementById('c-ig').value.trim();
  const profileJson = buildIntakeProfileJson();
  syncIntakeJsonPreview();
  
  const missing = [];
  if(!cid) missing.push("Client ID");
  if(!token) missing.push("Meta Access Token");
  if(!fb) missing.push("Facebook Page ID");
  if(!ig) missing.push("Instagram Account ID");
  if(!(profileJson.business_name || profileJson.industry || profileJson.target_audience || profileJson.identity || profileJson.services.length || profileJson.brand_voice_examples.length)) {
      missing.push("Synthesized Profile");
  }

  if(missing.length > 0) {
      return showNotification("Missing Details", `Jarvis cannot save this client yet. You are missing: <strong style="color:var(--t1)">${missing.join(', ')}</strong>`, true);
  }
  
  const btn = document.getElementById('btn-save');
  btn.innerText = "Saving Client...";
  
  const payload = {
      client_id: cid, phone_number: phone || undefined, meta_access_token: token,
      facebook_page_id: fb, instagram_account_id: ig, profile_json: profileJson
  };
  
  try {
      const res = await fetch(buildApiUrl("/api/save-client-profile"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
      });
      const saveData = await res.json();
      if(!res.ok || saveData.status === 'missing') {
          if(Array.isArray(saveData.missing_fields) && saveData.missing_fields.length) {
              showHUDError(saveData.missing_fields);
              setIntakeReviewStatus("Jarvis rejected the profile because critical brand intelligence is still missing.", "warning");
          } else {
              showNotification("Client Save Rejected", saveData.reason || 'Client profile is missing critical brand intelligence.', true);
          }
          btn.innerText = "Saving Client...";
          return;
      }
        setIntakeReviewStatus("Client profile locked in. This account is ready for vaulting, drafting, and publishing.", "success");
        showNotification(
          "Client Saved",
          `${cid} is now stored with its synthesized profile and live credentials. Returning to dashboard...`,
          false,
          { accent: INTAKE_CRYSTAL, rgb: INTAKE_CRYSTAL_RGB, messageColor: INTAKE_CRYSTAL_SOFT, duration: 9800, position: 'bottom-right' }
        );
        if(!globalClients.includes(cid)) globalClients.push(cid);
        populatePipelineSelectors(globalClients);
        const liveSelect = document.getElementById('tclient');
        if(liveSelect) liveSelect.value = cid;
        document.getElementById('c-json-preview').style.borderColor = "var(--purple)";
        try{ renderDashboardSummary(); } catch(e){}
        try{ renderConfigCards(); } catch(e){}
        
        setTimeout(() => {
          nav('dashboard', document.getElementById('nav-dashboard'));
        }, 2200);
  } catch(e) { showNotification("Save Failed", "Jarvis could not write this client profile to the backend.", true); }
  
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Save Client`;
}

async function triggerPipeline() {
  const client = document.getElementById('tclient').value;
  const topic = document.getElementById('ttopic').value.trim();
  if(!topic) { showNotification("Null Execution Trigger", "A pipeline topic objective must be defined.", true); return; }
  
  const btn = document.getElementById('btn-pipeline');
  const originalBtnHtml = btn.innerHTML;
  btn.innerHTML = `<div class="spinner" style="border-top-color:var(--t1)"></div> Running...`;
  btn.disabled = true;
  btn.style.opacity = '0.7';
  try{ triggerNeuralPulse(); } catch(e){}
  
  const now = new Date();
  const tStr = String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');
  appendLog(tStr, `<strong>SYSTEM</strong> · Pipeline triggered for ${client}...`, "purple");
  
  try {
      const res = await fetch(buildApiUrl("/api/trigger-pipeline"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client_id: client, topic: topic, image_path: uploadedImagePath })
      });
      const data = await res.json();
      
      const eD = new Date();
      const eStr = String(eD.getHours()).padStart(2,'0')+':'+String(eD.getMinutes()).padStart(2,'0')+':'+String(eD.getSeconds()).padStart(2,'0');
      
      if(data.status === "success") {
          let pIds = "";
          if(data.output) {
              const m = data.output.match(/\(ID: \d+\)/g);
              if(m) pIds = " " + m.join(", ");
          }
          appendLog(eStr, `<strong>SUCCESS</strong> · Pipeline executed cleanly.${pIds}`, "green");
          showNotification("Execution Complete", "Agents successfully published the campaign.", false);
          
          document.getElementById('ttopic').value = '';
          uploadedImagePath = null;
          document.getElementById('p-drop-preview').style.display = 'none';
          document.getElementById('p-drop-text').style.display = 'block';
          document.getElementById('p-dropzone').style.borderColor = 'rgba(255,255,255,0.15)';
      } else {
          const reasonMatch = (data.reason || "Unknown Execution Panic").substring(0, 100).replace(/<[^>]*>?/gm, '');
          appendLog(eStr, `<strong>ERROR</strong> · Pipeline halted: ${reasonMatch}...`, "red");
          showNotification("Execution Halted", "The agents encountered a critical failure. Check log.", true);
      }
  } catch(e) { 
      const crD = new Date();
      const crStr = String(crD.getHours()).padStart(2,'0')+':'+String(crD.getMinutes()).padStart(2,'0');
      appendLog(crStr, `<strong>CRITICAL</strong> Â· System daemon disconnected during pipeline execution.`, "red");
      showNotification("Daemon Execution Crash", "The background pipeline broke connection.", true); 
  } finally {
      btn.innerHTML = originalBtnHtml;
      btn.disabled = false;
      btn.style.opacity = '1';
  }
}

// --- ORCHESTRATOR MENTIONS LOGIC ---
const orchInput = document.getElementById('orch-input');
const mentionMenu = document.getElementById('mention-menu');
let mentionActive = false;
let mentionQuery = "";
let mentionMode = "client";
let mentionClient = "";
const draftMentionCache = {};
let currentOrchDraftRefs = [];
let lastImmediatePublishPrompt = "";
const approvalCenterCache = {};
const LEGACY_SMART_DRAFT_RE = /@\[(?<client>[^\]]+)\]\s+draft_id:"(?<draftId>[^"]+)"(?:\s+draft:"(?<draftName>[^"]+)")?\s*/gi;

function resolveMentionClient(rawClient) {
    const cleaned = String(rawClient || '').trim();
    if(!cleaned) return '';
    const exact = globalClients.find(c => c.toLowerCase() === cleaned.toLowerCase());
    return exact || cleaned;
}

function buildVisibleDraftToken(clientName, draftName) {
    return `@[${String(clientName || '').toLowerCase()}] Draft · ${String(draftName || '').trim()}`;
}

function absorbLegacyDraftRefsInInput() {
    const currentText = String(orchInput.value || '');
    if(!currentText.includes('draft_id:"')) return false;

    let changed = false;
    const knownRefs = new Set(
        currentOrchDraftRefs.map(ref => `${String(ref?.client_id || '').trim()}::${String(ref?.draft_id || '').trim()}`)
    );

    const rewritten = currentText.replace(LEGACY_SMART_DRAFT_RE, (...args) => {
        const groups = args.at(-1) || {};
        const clientName = resolveMentionClient(String(groups.client || '').trim());
        const draftName = String(groups.draftName || '').trim();
        const draftId = String(groups.draftId || '').trim();
        if(!clientName || !draftName || !draftId) return args[0];

        const visibleToken = buildVisibleDraftToken(clientName, draftName);
        const refKey = `${clientName}::${draftId}`;
        if(!knownRefs.has(refKey)) {
            currentOrchDraftRefs.push({
                client_id: clientName,
                draft_name: draftName,
                draft_id: draftId,
                visible_token: visibleToken,
            });
            knownRefs.add(refKey);
        }
        changed = true;
        return `${visibleToken} `;
    });

    if(!changed) return false;
    orchInput.value = rewritten;
    orchInput.selectionStart = rewritten.length;
    orchInput.selectionEnd = rewritten.length;
    return true;
}

absorbLegacyDraftRefsInInput();

async function loadDraftMentions(clientName) {
    const resolvedClient = resolveMentionClient(clientName);
    if(!resolvedClient) return [];
    if(draftMentionCache[resolvedClient]) return draftMentionCache[resolvedClient];

    try {
        const data = await fetchVaultData(resolvedClient);
        const bundles = data && data.bundles ? data.bundles : {};
        const drafts = Object.entries(bundles).map(([name, payload]) => ({
            name,
            id: String(payload?.draft_id || ''),
            type: String(payload?.bundle_type || 'image_single'),
            status: String(payload?.caption_status || 'empty'),
        })).sort((a, b) => a.name.localeCompare(b.name));
        draftMentionCache[resolvedClient] = drafts;
        return drafts;
    } catch(e) {
        return [];
    }
}

function hideMentionMenu() {
    mentionActive = false;
    mentionMode = "client";
    mentionClient = "";
    mentionQuery = "";
    mentionMenu.style.display = 'none';
}

function syncCurrentOrchDraftRefs() {
    absorbLegacyDraftRefsInInput();
    const currentText = String(orchInput.value || '');
    currentOrchDraftRefs = currentOrchDraftRefs.filter(ref => {
        const token = String(ref?.visible_token || '').trim();
        return token && currentText.includes(token);
    });
}

orchInput.addEventListener('input', function(e) {
    absorbLegacyDraftRefsInInput();
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight > 200 ? 200 : this.scrollHeight) + 'px';

    const val = this.value;
    const cursorPos = this.selectionStart;
    const textBeforeCursor = val.substring(0, cursorPos);
    const draftBracketMatch = textBeforeCursor.match(/@\[(.*?)\]\s*\.(.*)$/);
    const draftRawMatch = textBeforeCursor.match(/@(\w+)\.(.*)$/);
    const atMatch = textBeforeCursor.match(/@(\w*)$/);
    
    if(draftBracketMatch || draftRawMatch) {
       const draftMatch = draftBracketMatch || draftRawMatch;
       mentionActive = true;
       mentionMode = "draft";
       mentionClient = resolveMentionClient(draftMatch[1]);
       mentionQuery = String(draftMatch[2] || '').trim().toLowerCase();
       renderMentionMenu();
    } else if(atMatch) {
       mentionActive = true;
       mentionMode = "client";
       mentionQuery = atMatch[1].toLowerCase();
       renderMentionMenu();
    } else {
       hideMentionMenu();
    }
    syncCurrentOrchDraftRefs();
});

orchInput.addEventListener("keydown", function(e) {
    if(e.key==='Enter' && !e.shiftKey) { 
        e.preventDefault(); 
        if(!mentionActive || mentionMenu.style.display === 'none') {
            sendOrchestratorCmd(); 
        } else {
            const first = mentionMenu.querySelector('div.m-opt');
            if(first) first.click();
        }
    }
});

document.addEventListener('click', function(e) {
    if(!mentionMenu.contains(e.target) && e.target !== orchInput) {
        hideMentionMenu();
    }
});

async function renderMentionMenu() {
    if(!mentionActive) return;

    if(mentionMode === 'draft') {
        const drafts = await loadDraftMentions(mentionClient);
        const filteredDrafts = drafts.filter(d => d.name.toLowerCase().includes(mentionQuery));

        mentionMenu.innerHTML = `<div style="font-size:10px; color:var(--t4); margin-bottom:6px; font-family:'Space Mono'; padding: 0 4px; text-transform:uppercase;">SELECT DRAFT Â· ${escapeHtml(mentionClient.replace(/[_-]/g, ' '))}</div>`;

        if(filteredDrafts.length === 0) {
            mentionMenu.innerHTML += `<div style="padding:10px 12px; color:var(--t3); font-size:12px; font-family:'Inter', sans-serif;">No saved drafts matched. Open the vault and prepare one first.</div>`;
            mentionMenu.style.display = 'block';
            return;
        }

        filteredDrafts.forEach(draft => {
            const div = document.createElement('div');
            div.className = 'm-opt';
            div.style.padding = '10px 12px';
            div.style.color = 'var(--t1)';
            div.style.fontSize = '12px';
            div.style.fontFamily = "'Inter', sans-serif";
            div.style.cursor = 'pointer';
            div.style.borderRadius = '8px';
            div.style.display = 'flex';
            div.style.alignItems = 'center';
            div.style.justifyContent = 'space-between';
            div.onmouseover = () => div.style.background = 'rgba(255,255,255,0.05)';
            div.onmouseout = () => div.style.background = 'transparent';

            const draftType = draft.type === 'video'
                ? 'REEL'
                : (draft.type === 'image_carousel' ? 'CAROUSEL' : 'IMAGE');
            const statusLabel = draft.status === 'ready' ? 'READY' : 'EMPTY';

            div.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:3px; min-width:0;">
                    <span style="color:var(--t1); font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(draft.name)}</span>
                    <span style="font-size:10px; color:var(--t4); text-transform:uppercase; letter-spacing:0.7px;">Saved creative draft</span>
                </div>
                <div style="display:flex; gap:6px; flex-shrink:0; margin-left:10px;">
                    <span style="font-size:10px; padding:3px 7px; border-radius:999px; background:rgba(139,108,247,.12); color:var(--purple); border:1px solid rgba(139,108,247,.18);">${draftType}</span>
                    <span style="font-size:10px; padding:3px 7px; border-radius:999px; background:rgba(31,206,160,.1); color:var(--green); border:1px solid rgba(31,206,160,.18);">${statusLabel}</span>
                </div>
            `;
            div.onclick = () => insertVisibleDraftReference(mentionClient, draft.name, draft.id);
            mentionMenu.appendChild(div);
        });
        mentionMenu.style.display = 'block';
        return;
    }

    const filtered = globalClients.filter(c => c.toLowerCase().includes(mentionQuery));
    if(filtered.length === 0) {
        mentionMenu.style.display = 'none'; return;
    }

    mentionMenu.innerHTML = '<div style="font-size:10px; color:var(--t4); margin-bottom:6px; font-family:\'Space Mono\'; padding: 0 4px; text-transform:uppercase;">MOUNT VAULT</div>';
    filtered.forEach(c => {
        let div = document.createElement('div');
        div.className = 'm-opt';
        div.style.padding = '10px 12px'; div.style.color = 'var(--t1)';
        div.style.fontSize = '12px'; div.style.fontFamily = "'Space Mono', monospace";
        div.style.cursor = 'pointer'; div.style.borderRadius = '8px';
        div.onmouseover = () => div.style.background = 'rgba(255,255,255,0.05)';
        div.onmouseout = () => div.style.background = 'transparent';
        div.innerHTML = `<span style="color:var(--green); margin-right:4px;">@</span>${c}`;
        div.onclick = () => insertMention(c);
        mentionMenu.appendChild(div);
    });
    mentionMenu.style.display = 'block';
}

function insertMention(clientName) {
    const val = orchInput.value;
    const cursorPos = orchInput.selectionStart;
    const textBeforeCursor = val.substring(0, cursorPos);
    const textAfterCursor = val.substring(cursorPos);
    
    const atMatch = textBeforeCursor.match(/@(\w*)$/);
    if(atMatch) {
        const replaceStart = cursorPos - atMatch[0].length;
        const pill = `@[${clientName.toLowerCase()}] `;
        orchInput.value = val.substring(0, replaceStart) + pill + textAfterCursor;
        orchInput.focus();
        orchInput.selectionStart = replaceStart + pill.length;
        orchInput.selectionEnd = orchInput.selectionStart;
    }
    hideMentionMenu();
}

function insertDraftReference(clientName, draftName, draftId = '') {
    const val = orchInput.value;
    const cursorPos = orchInput.selectionStart;
    const textBeforeCursor = val.substring(0, cursorPos);
    const textAfterCursor = val.substring(cursorPos);
    const draftBracketMatch = textBeforeCursor.match(/@\[(.*?)\]\s*\.(.*)$/);
    const draftRawMatch = textBeforeCursor.match(/@(\w+)\.(.*)$/);
    const draftMatch = draftBracketMatch || draftRawMatch;
    if(!draftMatch) return;

    const replaceStart = cursorPos - draftMatch[0].length;
    const token = `@[${clientName.toLowerCase()}] Draft · ${draftName} `;
    orchInput.value = val.substring(0, replaceStart) + token + textAfterCursor;
    currentOrchDraftRefs = currentOrchDraftRefs.filter(ref => String(ref?.visible_token || '').trim() !== token.trim());
    if(draftId) {
        currentOrchDraftRefs.push({
            client_id: clientName,
            draft_name: draftName,
            draft_id: draftId,
            visible_token: token.trim(),
        });
    }
    orchInput.focus();
    orchInput.selectionStart = replaceStart + token.length;
    orchInput.selectionEnd = orchInput.selectionStart;
    hideMentionMenu();
}

function insertVisibleDraftReference(clientName, draftName, draftId = '') {
    const val = orchInput.value;
    const cursorPos = orchInput.selectionStart;
    const textBeforeCursor = val.substring(0, cursorPos);
    const textAfterCursor = val.substring(cursorPos);
    const draftBracketMatch = textBeforeCursor.match(/@\[(.*?)\]\s*\.(.*)$/);
    const draftRawMatch = textBeforeCursor.match(/@(\w+)\.(.*)$/);
    const draftMatch = draftBracketMatch || draftRawMatch;
    if(!draftMatch) return;

    const replaceStart = cursorPos - draftMatch[0].length;
    const visibleToken = buildVisibleDraftToken(clientName, draftName);
    const token = `${visibleToken} `;
    orchInput.value = val.substring(0, replaceStart) + token + textAfterCursor;
    currentOrchDraftRefs = currentOrchDraftRefs.filter(ref => String(ref?.visible_token || '').trim() !== visibleToken);
    if(draftId) {
        currentOrchDraftRefs.push({
            client_id: clientName,
            draft_name: draftName,
            draft_id: draftId,
            visible_token: visibleToken,
        });
    }
    orchInput.focus();
    orchInput.selectionStart = replaceStart + token.length;
    orchInput.selectionEnd = orchInput.selectionStart;
    hideMentionMenu();
}

async function sendOrchestratorCmd() {
    absorbLegacyDraftRefsInInput();
    let text = orchInput.value.trim();
    if(!text) return;
    const rawLowerText = text.toLowerCase();
    if(/^(try again|retry|do it again)$/i.test(text) && lastImmediatePublishPrompt) {
        text = lastImmediatePublishPrompt;
    }
    syncCurrentOrchDraftRefs();
    const outgoingDraftRefs = currentOrchDraftRefs.filter(ref => text.includes(String(ref.visible_token || '').trim()));
    
    // START RGB BREATHING
    const inputContainer = document.getElementById('orch-input-container');
    inputContainer.classList.add('processing');
    
    const chat = document.getElementById('orch-chat');
    
    // --- PREMIUM USER BUBBLE ---
    const userBubbleText = text
        .replace(/@\[(.*?)\]/g, '<span style="background:rgba(31,206,160,.15); color:#1fce9f; padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">@$1</span>')
        .replace(/draft_id:"[^"]+"\s*draft:"([^"]+)"/g, '<span style="background:rgba(139,108,247,.14); color:var(--purple); padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">Draft · $1</span>')
        .replace(/draft:"([^"]+)"/g, '<span style="background:rgba(139,108,247,.14); color:var(--purple); padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">Draft · $1</span>');
    let renderedUserBubbleText = userBubbleText;
    outgoingDraftRefs.forEach(ref => {
        const clientName = String(ref?.client_id || '').trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const draftName = String(ref?.draft_name || '').trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        if(!clientName || !draftName) return;
        const visibleDraftRe = new RegExp(`(<span[^>]*>@${clientName}</span>)\\s+Draft\\s+·\\s+${draftName}`, 'i');
        renderedUserBubbleText = renderedUserBubbleText.replace(
            visibleDraftRe,
            `$1 <span style="background:rgba(139,108,247,.14); color:var(--purple); padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">Draft · ${String(ref?.draft_name || '').trim()}</span>`
        );
    });

    chat.innerHTML += `
      <div class="chat-msg" style="display:flex; gap:14px; align-self:flex-end; flex-direction:row-reverse; margin-left:auto; max-width:80%;">
         <div class="user-avatar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:0.7;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
         </div>
         <div class="user-bubble">
            ${renderedUserBubbleText}
         </div>
      </div>
    `;
    
    orchInput.value = ''; orchInput.style.height = 'auto'; chat.scrollTop = chat.scrollHeight;
    
    // --- AI THINKING BUBBLE (SMART CONTEXT) ---
    const aiMsgId = "msg-" + Date.now();
    const lowerText = text.toLowerCase();
    if(/(post|publish).*(now|immediate|asap|instantly)/i.test(text) || /\bpost now\b/i.test(text) || /\bpost this now\b/i.test(text)) {
        lastImmediatePublishPrompt = text;
    }
    let loadingText = 'Processing...';
    let thinkingPhases = ['Processing...'];
    if(lowerText.match(/post|publish.*now|post this now|immediate|reel|carousel|draft/)) {
        loadingText = 'Preparing live publish...';
        thinkingPhases = [
            'Reading the saved draft...',
            'Preparing caption and platform payload...',
            'Handing off to Meta publish...',
            'Waiting for platform confirmation...'
        ];
    } else if(lowerText.match(/schedule|queue|approve|move time/)) {
        loadingText = 'Preparing release workflow...';
        thinkingPhases = [
            'Reading the draft and release window...',
            'Preparing the approval path...',
            'Syncing the live schedule...'
        ];
    } else if(lowerText.match(/analy|insight|perform|engagement|stats|metric/)) {
        loadingText = 'Generating performance analysis...';
        thinkingPhases = [
            'Collecting performance signals...',
            'Comparing recent post patterns...',
            'Writing the analysis...'
        ];
    } else if(lowerText.match(/search|trend|strateg|competitor|research|best practice/)) {
        loadingText = 'Fetching live sources...';
        thinkingPhases = [
            'Searching current sources...',
            'Comparing useful findings...',
            'Building a strategy answer...'
        ];
    } else if(lowerText.match(/vault|image|asset|upload/)) {
        loadingText = 'Scanning asset vault...';
        thinkingPhases = [
            'Indexing the client vault...',
            'Checking creative drafts...',
            'Preparing the response...'
        ];
    }
    
    chat.innerHTML += `
      <div id="${aiMsgId}" class="chat-msg" style="display:flex; gap:14px; max-width:85%;">
         <div class="jarvis-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
         </div>
         <div>
            <div style="font-size:12px; font-weight:600; color:var(--purple); margin-bottom:6px; text-transform:uppercase; letter-spacing:1px;">Jarvis</div>
            <div class="msg-content ai-bubble" style="display:flex; align-items:center; gap:10px; color:var(--t3);">
               <span style="display:inline-flex; gap:4px; align-items:center;">
                 <span style="width:6px; height:6px; border-radius:50%; background:var(--purple); animation:dotBounce 1.4s ease-in-out infinite; animation-delay:0s;"></span>
                 <span style="width:6px; height:6px; border-radius:50%; background:var(--purple); animation:dotBounce 1.4s ease-in-out infinite; animation-delay:0.2s;"></span>
                 <span style="width:6px; height:6px; border-radius:50%; background:var(--purple); animation:dotBounce 1.4s ease-in-out infinite; animation-delay:0.4s;"></span>
               </span>
               <span id="${aiMsgId}-phase" style="animation:textPulse 1.5s ease-in-out infinite; display:inline-block;">${loadingText}</span>
            </div>
         </div>
      </div>
    `;
    chat.scrollTop = chat.scrollHeight;
    const phaseNode = document.getElementById(`${aiMsgId}-phase`);
    const stopThinkingTicker = startThinkingTicker(phaseNode, thinkingPhases);

    try { triggerNeuralPulse(); } catch(e){}

    try {
        const res = await fetch(buildApiUrl("/api/orchestrator-chat"), {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: text, draft_refs: outgoingDraftRefs })
        });
        const data = await res.json();
        
        const msgNode = document.getElementById(aiMsgId).querySelector('.msg-content');
        if(data.status === "success") {
            let reply = data.reply || "";
            const errMatch = reply.match(/\{[^}]*"error"\s*:/);
            if(errMatch) {
                try {
                    const errJson = JSON.parse(reply);
                    renderErrorCard(msgNode, errJson.error || reply);
                } catch(e) {
                    const errorText = reply.replace(/^\{?"?error"?\s*:\s*"?/i, '').replace(/"?\}?$/, '');
                    renderErrorCard(msgNode, errorText);
                }
            } else if(data.action && data.action.type === 'approval_request' && data.action.job && data.action.approval_id) {
                msgNode.style.cssText = '';
                msgNode.className = 'msg-content ai-success-card';
                msgNode.innerHTML = renderOrchestratorApprovalCard(reply, data.action);
            } else {
                const isStructured = reply.match(/^[-*]\s|^\d+\.|^#{1,3}\s|^---|\*\*.*\*\*/m) && reply.split('\n').length > 4;
                msgNode.style.cssText = '';
                
                if(isStructured) {
                    msgNode.className = 'msg-content ai-success-card';
                    msgNode.innerHTML = renderMarkdown(reply);
                } else {
                    msgNode.className = 'msg-content ai-bubble';
                    msgNode.innerHTML = reply.replace(/\*\*(.*?)\*\*/g, '<strong style="color:var(--t1);">$1</strong>').replace(/\n/g, '<br/>');
                }
            }
        } else {
            renderErrorCard(msgNode, data.reason || "Unknown system failure.");
        }
    } catch (e) {
        const msgNode = document.getElementById(aiMsgId).querySelector('.msg-content');
        renderErrorCard(msgNode, "Connection lost to FastAPI daemon. Is the server running?");
    } finally {
        stopThinkingTicker();
        currentOrchDraftRefs = [];
        chat.scrollTop = chat.scrollHeight;
        
        // STOP RGB BREATHING & FLASH SUCCESS
        inputContainer.classList.remove('processing');
        inputContainer.classList.add('processing-done');
        setTimeout(() => inputContainer.classList.remove('processing-done'), 1500);
    }
}

function renderMarkdown(text) {
    // Lightweight markdown-to-HTML for LLM responses
    let lines = text.split('\n');
    let html = '';
    let inList = false;
    let listType = '';
    
    for(let i = 0; i < lines.length; i++) {
        let line = lines[i];
        
        // Close list if line is not a list item
        if(inList && !line.match(/^\s*[-*]\s/) && !line.match(/^\s*\d+\./)) {
            html += listType === 'ul' ? '</ul>' : '</ol>';
            inList = false;
        }
        
        // Headers
        if(line.match(/^###\s+/)) { html += `<div style="font-size:14px; font-weight:700; color:var(--t1); margin:12px 0 6px;">${line.replace(/^###\s+/, '')}</div>`; continue; }
        if(line.match(/^##\s+/))  { html += `<div style="font-size:15px; font-weight:700; color:var(--t1); margin:14px 0 6px;">${line.replace(/^##\s+/, '')}</div>`; continue; }
        if(line.match(/^#\s+/))   { html += `<div style="font-size:16px; font-weight:700; color:var(--t1); margin:16px 0 8px;">${line.replace(/^#\s+/, '')}</div>`; continue; }
        
        // Horizontal rule
        if(line.match(/^---+$/)) { html += '<hr style="border:none; border-top:1px solid rgba(255,255,255,0.06); margin:12px 0;">'; continue; }
        
        // Bullet lists
        if(line.match(/^\s*[-*]\s+/)) {
            if(!inList || listType !== 'ul') {
                if(inList) html += listType === 'ul' ? '</ul>' : '</ol>';
                html += '<ul style="margin:6px 0; padding-left:20px; list-style:none;">';
                inList = true; listType = 'ul';
            }
            let content = line.replace(/^\s*[-*]\s+/, '');
            content = inlineFormat(content);
            html += `<li style="padding:3px 0; position:relative;"><span style="color:var(--purple); position:absolute; left:-16px;">›</span>${content}</li>`;
            continue;
        }
        
        // Numbered lists (handles both "1. Text" and "1.Text")
        if(line.match(/^\s*\d+\.\s*/)) {
            if(!inList || listType !== 'ol') {
                if(inList) html += listType === 'ul' ? '</ul>' : '</ol>';
                html += '<ol style="margin:6px 0; padding-left:20px; list-style:none; counter-reset:item;">';
                inList = true; listType = 'ol';
            }
            let content = line.replace(/^\s*\d+\.\s*/, '');
            content = inlineFormat(content);
            html += `<li style="padding:3px 0; counter-increment:item;"><span style="color:var(--purple); font-weight:600; margin-right:6px;">${line.match(/^\s*(\d+)\./)[1]}.</span>${content}</li>`;
            continue;
        }
        
        // Empty line = paragraph break
        if(line.trim() === '') { html += '<div style="height:8px;"></div>'; continue; }
        
        // Normal paragraph
        html += `<div style="margin:2px 0;">${inlineFormat(line)}</div>`;
    }
    
    if(inList) html += listType === 'ul' ? '</ul>' : '</ol>';
    return html;
}

function inlineFormat(text) {
    // Bold
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong style="color:var(--t1);">$1</strong>');
    // Italic
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Inline code
    text = text.replace(/`(.*?)`/g, '<code style="background:rgba(139,108,247,.1); color:var(--purple); padding:2px 6px; border-radius:4px; font-size:12px; font-family:\'Space Mono\',monospace;">$1</code>');
    // Emoji preservation (already works)
    return text;
}

function renderErrorCard(node, errorText) {
    node.innerHTML = `
        <div style="background:rgba(224,85,85,.06); border:1px solid rgba(224,85,85,.2); border-radius:12px; padding:14px 18px;">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e05555" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
                <span style="color:#e05555; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">Execution Failed</span>
            </div>
            <div style="color:var(--t2); font-size:13px; line-height:1.6;">${errorText.replace(/\n/g, '<br/>')}</div>
        </div>
    `;
}

// --- VAULTS DOM LOGIC ---
// --- LIVE CRON SCHEDULE ---
async function renderSchedule() {
    const list = document.getElementById('schedule-list');
    if(!list) return;
    try {
        const res = await fetch(buildApiUrl("/api/schedule"));
        const data = await res.json();
        if(data.status !== "success") { list.innerHTML = `<div style="color:var(--red);padding:20px;text-align:center;">Failed to load schedule.</div>`; return; }
        
        const jobs = data.schedule;
        if(!jobs.length) {
            list.innerHTML = `<div style="color:var(--t3);font-size:13px;padding:24px;text-align:center;border:0.5px dashed rgba(255,255,255,.08);border-radius:12px;">No active jobs. Use the Orchestrator to schedule posts.</div>`;
            return;
        }
        
        list.innerHTML = jobs.map((j, i) => {
            let dayPills = '';
            if (j.scheduled_date) {
                try {
                    const d = new Date(`${j.scheduled_date}T00:00:00`);
                    const label = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
                    dayPills = `<span class="dp">${label}</span>`;
                } catch(e) {
                    dayPills = `<span class="dp">${j.scheduled_date}</span>`;
                }
            } else {
                dayPills = (j.days || []).map(d => `<span class="dp">${d}</span>`).join('');
            }
            const clientLabel = (j.client || 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const isDelivered = j.status === 'delivered';
            const sTimeStyle = isDelivered ? 'color:var(--solid-green); text-decoration:line-through;' : '';
            const rowStyle = isDelivered ? 'border-color:rgba(31,206,160,.4); background:rgba(31,206,160,.05);' : `animation:fadein .3s ease ${i * 0.05}s both;`;
            const checkMark = isDelivered ? `<div style="color:var(--solid-green); font-size:12px; font-weight:700; margin-top:6px;">DELIVERED</div>` : '';
            const delBtn = isDelivered ? '' : `<button onclick="removeScheduleEntry(${i})" style="display:inline-flex;align-items:center;justify-content:center;background:rgba(224,85,85,.1);border:1px solid rgba(224,85,85,.2);color:#e05555;border-radius:8px;padding:4px 10px;cursor:pointer;font-size:11px;font-weight:600;transition:all .2s;min-width:36px;" onmouseover="this.style.background='rgba(224,85,85,.2)'" onmouseout="this.style.background='rgba(224,85,85,.1)'" aria-label="Remove scheduled job" title="Remove scheduled job">×</button>`;
            
            return `
            <div class="s-item" style="${rowStyle}">
              <div class="stime" style="${sTimeStyle}">${j.time || '??:??'}</div>
              <div style="flex:1;min-width:0;">
                <div class="scl">${clientLabel}</div>
                <div class="stp" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">Topic: "${j.topic || 'N/A'}"</div>
                ${checkMark}
              </div>
              <div class="sdays">${dayPills}</div>
              ${delBtn}
            </div>`;
        }).join('');
    } catch(e) {
        list.innerHTML = `<div style="color:var(--red);padding:20px;text-align:center;">Cannot reach backend.</div>`;
    }
}

async function removeScheduleEntry(index) {
    try {
        const res = await fetch(buildApiUrl(`/api/schedule/${index}`), { method: 'DELETE' });
        const data = await res.json();
        if(data.status === 'success') {
            showNotification('Cron Entry Removed', `Removed job for ${data.removed?.client || 'unknown'}`, false);
            renderSchedule();
        }
    } catch(e) {}
}

let scheduleView = 'active';

function setScheduleView(view) {
    scheduleView = view === 'history' ? 'history' : 'active';
    renderSchedule();
}

function formatSchedulePills(job) {
    if (job.scheduled_date) {
        try {
            const d = new Date(`${job.scheduled_date}T00:00:00`);
            const label = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            return `<span class="dp">${label}</span>`;
        } catch(e) {
            return `<span class="dp">${job.scheduled_date}</span>`;
        }
    }
    return (job.days || []).map(d => `<span class="dp">${d}</span>`).join('');
}

function formatDeliveredAt(job) {
    if(!job.delivered_at) return 'Delivered recently';
    try {
        const d = new Date(job.delivered_at);
        return `Delivered ${d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}`;
    } catch(e) {
        return 'Delivered recently';
    }
}

function getScheduleDraftLabel(job) {
    const draftName = String(job.draft_name || job.bundle_name || '').trim();
    if(draftName) return `Draft: ${draftName}`;
    const mediaType = String(job.media_type || '').trim();
    if(mediaType) return `Format: ${mediaType}`;
    return 'Draft: Direct publish request';
}

function shortenScheduleText(value, limit = 52) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    if(!text) return '';
    return text.length > limit ? `${text.slice(0, limit).trim()}...` : text;
}

function getScheduleIntentLabel(job) {
    const seo = String(job.seo_keyword_used || '').trim();
    if(seo) return `Focus: ${shortenScheduleText(seo, 40)}`;
    const topic = String(job.topic || '').trim();
    if(!topic) return '';
    return `Focus: ${shortenScheduleText(topic, 56)}`;
}

function getScheduleCaptionHighlight(job) {
    const caption = String(job.caption_text || '').replace(/\s+/g, ' ').trim();
    if(!caption) return '';
    const words = caption.split(' ').filter(Boolean);
    const lead = words.slice(0, 12).join(' ');
    return `Caption: ${lead}${words.length > 12 ? '...' : ''}`;
}

function updateScheduleViewUI(activeCount, historyCount) {
    const counts = document.getElementById('schedule-counts');
    const title = document.getElementById('schedule-panel-title');
    const activeBtn = document.getElementById('schedule-tab-active');
    const historyBtn = document.getElementById('schedule-tab-history');
    if(counts) counts.textContent = `${activeCount} active | ${historyCount} delivered`;
    if(title) title.textContent = scheduleView === 'history' ? 'Delivered History' : 'Active Execution Jobs';
    if(activeBtn) {
        activeBtn.style.background = scheduleView === 'active' ? 'rgba(139,108,247,.18)' : 'transparent';
        activeBtn.style.borderColor = scheduleView === 'active' ? 'rgba(139,108,247,.25)' : 'rgba(255,255,255,.08)';
        activeBtn.style.color = scheduleView === 'active' ? 'var(--purple)' : 'var(--t3)';
    }
    if(historyBtn) {
        historyBtn.style.background = scheduleView === 'history' ? 'rgba(31,206,160,.12)' : 'transparent';
        historyBtn.style.borderColor = scheduleView === 'history' ? 'rgba(31,206,160,.25)' : 'rgba(255,255,255,.08)';
        historyBtn.style.color = scheduleView === 'history' ? 'var(--solid-green)' : 'var(--t3)';
    }
}

async function renderSchedule() {
    const list = document.getElementById('schedule-list');
    if(!list) return;
    try {
        const res = await fetch(buildApiUrl("/api/schedule"));
        const data = await res.json();
        if(data.status !== "success") { list.innerHTML = `<div style="color:var(--red);padding:20px;text-align:center;">Failed to load schedule.</div>`; return; }

        const activeJobs = data.schedule || [];
        const historyJobs = data.history || [];
        const scheduleSignature = activeJobs.map(job => `${job.job_id || ''}:${job.scheduled_date || ''}:${job.time || ''}:${job.status || ''}`).join('|');
        updateNavPing('schedule', scheduleSignature || `count:${activeJobs.length}`, activeJobs.length > 0);
        const jobs = scheduleView === 'history' ? historyJobs : activeJobs;
        updateScheduleViewUI(activeJobs.length, historyJobs.length);

        if(!jobs.length) {
            const emptyText = scheduleView === 'history'
                ? 'No delivered jobs are currently being retained in history.'
                : 'No active jobs. Use the Orchestrator to schedule posts.';
            list.innerHTML = `<div style="color:var(--t3);font-size:13px;padding:24px;text-align:center;border:0.5px dashed rgba(255,255,255,.08);border-radius:12px;">${emptyText}</div>`;
            return;
        }

        list.innerHTML = jobs.map((j, i) => {
            const dayPills = formatSchedulePills(j);
            const clientLabel = (j.client || 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const isHistory = scheduleView === 'history';
            const primarySubline = isHistory ? formatDeliveredAt(j) : getScheduleDraftLabel(j);
            const intentSubline = isHistory ? '' : getScheduleIntentLabel(j);
            const captionSubline = isHistory ? '' : getScheduleCaptionHighlight(j);
            const rowStyle = isHistory
                ? 'border-color:rgba(31,206,160,.25); background:rgba(31,206,160,.05);'
                : `animation:fadein .3s ease ${i * 0.05}s both;`;
            const statusBadge = isHistory
                ? `<div style="color:var(--solid-green); font-size:12px; font-weight:700; margin-top:6px;">DELIVERED</div>`
                : '';
            const delBtn = isHistory ? '' : `<button onclick="removeScheduleEntry('${j.job_id}')" style="display:inline-flex;align-items:center;justify-content:center;background:rgba(224,85,85,.1);border:1px solid rgba(224,85,85,.2);color:#e05555;border-radius:8px;padding:4px 10px;cursor:pointer;font-size:11px;font-weight:600;transition:all .2s;min-width:36px;" onmouseover="this.style.background='rgba(224,85,85,.2)'" onmouseout="this.style.background='rgba(224,85,85,.1)'" aria-label="Remove scheduled job" title="Remove scheduled job">×</button>`;

            return `
            <div class="s-item" style="${rowStyle}">
              <div class="stime" style="${isHistory ? 'color:var(--solid-green);' : ''}">${j.time || '??:??'}</div>
              <div class="s-main">
                <div class="scl">${clientLabel}</div>
                <div class="stp s-subline">${primarySubline}</div>
                ${intentSubline ? `<div class="stp s-subline" style="color:var(--t4); margin-top:2px;">${intentSubline}</div>` : ''}
                ${captionSubline ? `<div class="stp s-subline" dir="auto" style="color:rgba(255,255,255,.52); margin-top:2px;">${captionSubline}</div>` : ''}
                ${statusBadge}
              </div>
              <div class="sdays">${dayPills}</div>
              <div class="s-actions">${delBtn}</div>
            </div>`;
        }).join('');
    } catch(e) {
        updateNavPing('schedule', '', false);
        list.innerHTML = `<div style="color:var(--red);padding:20px;text-align:center;">Cannot reach backend.</div>`;
    }
}

async function removeScheduleEntry(jobId) {
    try {
        const res = await fetch(buildApiUrl(`/api/schedule/job/${jobId}`), { method: 'DELETE' });
        const data = await res.json();
        if(data.status === 'success') {
            showNotification('Cron Entry Removed', `Removed job for ${data.removed?.client || 'unknown'}`, false);
            renderSchedule();
        }
    } catch(e) {}
}

async function clearDeliveredSchedules() {
    try {
        const res = await fetch(buildApiUrl("/api/schedule/clear-delivered"), { method: 'DELETE' });
        const data = await res.json();
        if(data.status === 'success') {
            showNotification('History Purged', `Removed ${data.cleared || 0} jobs from retained history.`, false);
            renderSchedule();
        }
    } catch(e) {}
}

// Auto-poll schedule every 15s
setInterval(renderSchedule, 15000);

async function renderVaults() {
    const grid = document.getElementById('vaults-grid');
    if(!grid) return;
    if(!globalClients.length) {
        try {
            const res = await fetch(buildApiUrl("/api/clients"));
            const data = await res.json();
            if(data.status === "success" && Array.isArray(data.clients)) {
                globalClients = data.clients;
            }
        } catch(e) {}
    }
    if(!globalClients.length) {
        grid.innerHTML = `<div class="hq-empty-state">No client vaults are available yet. Add a client first.</div>`;
        return;
    }
    
    let counts = {};
    try {
        const res = await fetch(buildApiUrl("/api/vaults"));
        const data = await res.json();
        if(data.status === "success") counts = data.vaults;
    } catch(e){}
    
    grid.innerHTML = '';
    
    for(const c of globalClients) {
        const amount = counts[c] || 0;
        let folder = document.createElement('div');
        folder.className = 'v-folder reveal-3d';
        folder.innerHTML = `
            <div class="v-f-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </div>
            <div class="v-f-name">${c}</div>
            <div class="v-f-stat" id="stat-${c}">${amount} items securely vaulted. Drop files to isolate.</div>
        `;
        
        folder.addEventListener('dragover', (e) => { e.preventDefault(); folder.classList.add('drag-over'); });
        folder.addEventListener('dragleave', (e) => { e.preventDefault(); folder.classList.remove('drag-over'); });
        folder.addEventListener('drop', (e) => {
            e.preventDefault(); folder.classList.remove('drag-over');
            if(e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleBulkDrop(c, e.dataTransfer.files, `stat-${c}`);
            }
        });
        
        folder.onclick = () => openVaultModal(c);
        
        grid.appendChild(folder);
    }
}

async function handleBulkDrop(clientId, fileList, statId) {
    const statNode = document.getElementById(statId);
    if(statNode) statNode.innerHTML = `<span style="color:var(--amber)">Uploading ${fileList.length} assets...</span>`;
    
    const formData = new FormData();
    formData.append("client_id", clientId);
    for(let i = 0; i < fileList.length; i++) {
        formData.append("files", fileList[i]);
    }
    
    try {
        const res = await fetch(buildApiUrl("/api/upload-bulk"), { method: "POST", body: formData });
        const data = await res.json().catch(() => ({ status: 'error', reason: `Upload failed with HTTP ${res.status}.` }));
        if(data.status === "success") {
            delete vaultDataCache[clientId];
            if(statNode) statNode.innerHTML = `<span style="color:var(--green)">Synced ${data.uploaded_paths.length} physically to disk.</span>`;
            const now = new Date();
            const timeStr = String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
            appendLog(timeStr, `<strong>SYSTEM</strong> Â· Batch uploaded ${data.uploaded_paths.length} elements to [${clientId}] vault.`, "green");
            await renderVaults();
            if(currentVaultClient === clientId) {
                await loadVaultData(true);
            }
        } else {
             if(statNode) statNode.innerHTML = `<span style="color:var(--red)">Upload rejected.</span>`;
             showNotification('Upload Rejected', data.reason || 'Jarvis could not store those files.', true);
        }
    } catch(e) {
        if(statNode) statNode.innerHTML = `<span style="color:var(--red)">Failed connection.</span>`;
        showNotification('Upload Failed', e?.message || 'Jarvis could not reach the upload endpoint.', true);
    }
}

// --- CLIENT CONFIG DOM LOGIC ---
async function renderConfigCards() {
    const grid = document.getElementById('config-grid');
    if(!grid) return;
    if(!globalClients.length) {
        try {
            const res = await fetch(buildApiUrl("/api/clients"));
            const data = await res.json();
            if(data.status === "success" && Array.isArray(data.clients)) {
                globalClients = data.clients;
            }
        } catch(e) {}
    }
    if(!globalClients.length) {
        grid.innerHTML = `<div class="hq-empty-state">No client profiles are available yet. Add a client first.</div>`;
        return;
    }
    grid.innerHTML = '';
    
    for(const c of globalClients) {
        let card = document.createElement('div');
        card.className = 'v-folder reveal-3d';
        card.innerHTML = `
            <button onclick="event.stopPropagation(); deleteClientProfile('${c}')" title="Remove client" style="position:absolute; top:14px; right:14px; width:30px; height:30px; border-radius:50%; border:1px solid rgba(224,85,85,.28); background:rgba(224,85,85,.12); color:var(--red); display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:18px; line-height:1; z-index:2; transition:all .2s;" onmouseover="this.style.background='rgba(224,85,85,.2)'" onmouseout="this.style.background='rgba(224,85,85,.12)'">&times;</button>
            <div class="v-f-icon" style="background:rgba(47,168,224,.15); color:var(--blue);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="v-f-name">${c}</div>
            <div class="v-f-stat" style="margin-bottom:12px;">Tap a section below to expand</div>
            
            <!-- TWO COLLAPSIBLE BUTTONS -->
            <div style="display:flex; gap:8px; margin-bottom:4px;">
                <button id="btn-details-${c}" onclick="event.stopPropagation(); toggleConfigSection('${c}','details')" style="flex:1; padding:8px 0; border-radius:8px; border:1px solid rgba(139,108,247,.2); background:rgba(139,108,247,.08); color:var(--purple); font-size:11px; font-weight:600; cursor:pointer; font-family:'Space Mono'; transition:all .2s;">Client Details</button>
                <button id="btn-creds-${c}" onclick="event.stopPropagation(); toggleConfigSection('${c}','creds')" style="flex:1; padding:8px 0; border-radius:8px; border:1px solid rgba(47,168,224,.2); background:rgba(47,168,224,.08); color:var(--blue); font-size:11px; font-weight:600; cursor:pointer; font-family:'Space Mono'; transition:all .2s;">Live Credentials</button>
            </div>
            <div style="display:flex; gap:8px; margin-bottom:4px;">
<button onclick="event.stopPropagation(); openClientValueBrief('${c}')" style="flex:1; padding:8px 0; border-radius:8px; border:1px solid rgba(31,206,160,.22); background:rgba(31,206,160,.08); color:var(--green); font-size:11px; font-weight:600; cursor:pointer; font-family:'Space Mono'; transition:all .2s;">Operating Brief</button>
            </div>
            
            <!-- CLIENT DETAILS SECTION -->
            <div id="cfg-details-${c}" style="display:none; margin-top:12px; border-top:1px solid rgba(255,255,255,0.05); padding-top:14px;">
                <div style="font-size:10px; color:var(--t4); text-transform:uppercase; font-family:'Space Mono'; margin-bottom:12px;">BRAND PROFILE EDITOR</div>
                
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Target Voice Language</div>
                <div style="margin-bottom:10px;">
                    <select class="qin" id="cfg-target-voice-${c}" style="cursor:pointer;">
                        <option value="arabic_gulf">Arabic (Gulf / Khaleeji)</option>
                        <option value="arabic_msa">Arabic (MSA)</option>
                        <option value="english">English (US)</option>
                        <option value="bilingual">Bilingual (English / Arabic)</option>
                    </select>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <div>
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Business Name</div>
                        <input class="qin" id="cfg-business-${c}" placeholder="Burger Grillz" />
                    </div>
                    <div>
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Industry</div>
                        <input class="qin" id="cfg-industry-${c}" placeholder="food_beverage" />
                    </div>
                </div>
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Brand Identity</div>
                <textarea class="qin" id="cfg-identity-${c}" rows="2" style="margin-bottom:10px; resize:vertical;" placeholder="Who they are, what makes them different, and what the brand should feel like."></textarea>
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Target Audience</div>
                <input class="qin" id="cfg-audience-${c}" placeholder="Who they are selling to" style="margin-bottom:10px;" />
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Services / Offers (comma-separated)</div>
                <input class="qin" id="cfg-services-${c}" placeholder="smash burgers, loaded fries, milkshakes" style="margin-bottom:10px;" />
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <div>
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Voice Tone (comma-separated)</div>
                        <input class="qin" id="cfg-tone-${c}" placeholder="energetic, casual, youthful" />
                    </div>
                    <div>
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Voice Style</div>
                        <input class="qin" id="cfg-style-${c}" placeholder="playful, conversational, premium" />
                    </div>
                </div>
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Dialect Notes</div>
                <textarea class="qin" id="cfg-dialect-${c}" rows="2" style="margin-bottom:10px; resize:vertical;" placeholder="Khaleeji wording, phrases to prefer, phrases to avoid."></textarea>
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Brand Voice Examples (3-5, one per line)</div>
                <textarea class="qin" id="cfg-voice-examples-${c}" rows="4" style="margin-bottom:10px; resize:vertical;" placeholder="Paste 3-5 real captions or brand voice examples here."></textarea>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <div>
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">SEO Keywords (comma-separated)</div>
                        <input class="qin" id="cfg-seo-${c}" placeholder="smash burger kuwait, late night burger..." />
                    </div>
                    <div>
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Hashtag Bank (comma-separated)</div>
                        <input class="qin" id="cfg-hashtags-${c}" placeholder="#????, #???_????, #??????" />
                    </div>
                </div>
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Banned Words (comma-separated)</div>
                <input class="qin" id="cfg-banned-${c}" placeholder="cheap, diet, boring" style="margin-bottom:10px;" />
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Do / Avoid Rules (one per line)</div>
                <textarea class="qin" id="cfg-rules-${c}" rows="4" style="margin-bottom:10px; resize:vertical;" placeholder="Add copy rules, CTAs to prefer, banned phrasing, and brand constraints."></textarea>
                <button class="run-btn" style="margin-top:4px; background:linear-gradient(135deg, rgba(139,108,247,.12), rgba(47,168,224,.08)); border-color:rgba(139,108,247,.2);" onclick="event.stopPropagation(); saveClientDetails('${c}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path></svg>
                    Save Details
                </button>
                <div id="cfg-det-status-${c}" style="margin-top:8px; font-size:11px; font-family:'Space Mono';"></div>
            </div>
            
            <!-- LIVE CREDENTIALS SECTION -->
            <div id="cfg-creds-${c}" style="display:none; margin-top:12px; border-top:1px solid rgba(255,255,255,0.05); padding-top:14px;">
                <div style="font-size:10px; color:var(--t4); text-transform:uppercase; font-family:'Space Mono'; margin-bottom:12px;">LIVE CREDENTIAL EDITOR</div>
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Client WhatsApp Number (optional / V2)</div>
                <input class="qin" id="cfg-phone-${c}" placeholder="+965XXXXXXXX" style="margin-bottom:12px;" />
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Meta Access Token</div>
                <div style="display:flex; gap:8px; align-items:center; margin-bottom:12px;">
                    <input class="qin" id="cfg-token-${c}" type="password" placeholder="EAAl...ZD" style="margin-bottom:0; flex:1;" />
                    <button onclick="event.stopPropagation(); document.getElementById('cfg-token-${c}').value=''; document.getElementById('cfg-token-${c}').focus();" style="background:rgba(224,85,85,.15); border:1px solid rgba(224,85,85,.3); color:var(--red); padding:8px 14px; border-radius:10px; cursor:pointer; font-size:11px; font-family:'Space Mono'; white-space:nowrap; transition:all .2s;">Clear</button>
                </div>
                <div style="display:flex; gap:8px;">
                    <div style="flex:1;">
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Facebook Page ID</div>
                        <input class="qin" id="cfg-fb-${c}" placeholder="112493..." />
                    </div>
                    <div style="flex:1;">
                        <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Instagram Account ID</div>
                        <input class="qin" id="cfg-ig-${c}" placeholder="17841..." />
                    </div>
                </div>
                <button class="run-btn" style="margin-top:12px; background:linear-gradient(135deg, rgba(31,206,160,.15), rgba(47,168,224,.12)); border-color:rgba(31,206,160,.25);" onclick="event.stopPropagation(); updateClientConfig('${c}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path></svg>
                    Save Credentials
                </button>
                <div id="cfg-status-${c}" style="margin-top:8px; font-size:11px; font-family:'Space Mono';"></div>
            </div>
        `;
        grid.appendChild(card);
    }
}

function toggleConfigSection(clientId, section) {
    const detPanel = document.getElementById('cfg-details-' + clientId);
    const credPanel = document.getElementById('cfg-creds-' + clientId);
    const detBtn = document.getElementById('btn-details-' + clientId);
    const credBtn = document.getElementById('btn-creds-' + clientId);
    
    if(section === 'details') {
        const isOpen = detPanel.style.display !== 'none';
        credPanel.style.display = 'none';
        credBtn.style.borderColor = 'rgba(47,168,224,.2)';
        credBtn.style.background = 'rgba(47,168,224,.08)';
        if(isOpen) {
            detPanel.style.display = 'none';
            detBtn.style.borderColor = 'rgba(139,108,247,.2)';
            detBtn.style.background = 'rgba(139,108,247,.08)';
        } else {
            detPanel.style.display = 'block';
            detBtn.style.borderColor = 'rgba(139,108,247,.5)';
            detBtn.style.background = 'rgba(139,108,247,.18)';
            loadClientDetails(clientId);
        }
    } else {
        const isOpen = credPanel.style.display !== 'none';
        detPanel.style.display = 'none';
        detBtn.style.borderColor = 'rgba(139,108,247,.2)';
        detBtn.style.background = 'rgba(139,108,247,.08)';
        if(isOpen) {
            credPanel.style.display = 'none';
            credBtn.style.borderColor = 'rgba(47,168,224,.2)';
            credBtn.style.background = 'rgba(47,168,224,.08)';
        } else {
            credPanel.style.display = 'block';
            credBtn.style.borderColor = 'rgba(47,168,224,.5)';
            credBtn.style.background = 'rgba(47,168,224,.18)';
            loadClientCreds(clientId);
        }
    }
}

async function loadClientDetails(c) {
    try {
        const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(c)));
        const data = await res.json();
        const p = data.profile_json || {};
        const voice = p.brand_voice || {};
        const lang = p.language_profile || {};
        document.getElementById('cfg-target-voice-' + c).value = lang.target_voice_language || 'arabic_gulf';
        document.getElementById('cfg-business-' + c).value = p.business_name || c;
        document.getElementById('cfg-industry-' + c).value = p.industry || '';
        document.getElementById('cfg-identity-' + c).value = p.identity || '';
        document.getElementById('cfg-tone-' + c).value = Array.isArray(voice.tone) ? voice.tone.join(', ') : (voice.tone || (Array.isArray(p.tone) ? p.tone.join(', ') : (p.tone || '')));
        document.getElementById('cfg-style-' + c).value = voice.style || p.style || '';
        document.getElementById('cfg-dialect-' + c).value = voice.dialect_notes || p.dialect_notes || '';
        document.getElementById('cfg-audience-' + c).value = p.target_audience || '';
        document.getElementById('cfg-services-' + c).value = Array.isArray(p.services) ? p.services.join(', ') : '';
        document.getElementById('cfg-seo-' + c).value = Array.isArray(p.seo_keywords) ? p.seo_keywords.join(', ') : '';
        document.getElementById('cfg-hashtags-' + c).value = Array.isArray(p.hashtag_bank) ? p.hashtag_bank.join(', ') : '';
        document.getElementById('cfg-banned-' + c).value = Array.isArray(p.banned_words) ? p.banned_words.join(', ') : '';
        document.getElementById('cfg-voice-examples-' + c).value = Array.isArray(p.brand_voice_examples) ? p.brand_voice_examples.join('\n') : '';
        document.getElementById('cfg-rules-' + c).value = Array.isArray(p.dos_and_donts) ? p.dos_and_donts.join('\n') : '';
    } catch(e) {
        document.getElementById('cfg-det-status-' + c).innerHTML = '<span style="color:var(--red)">Failed to load profile.</span>';
    }
}

async function loadClientCreds(c) {
    try {
        const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(c)));
        const data = await res.json();
        const ph = data.phone_number || '';
        const tk = data.meta_access_token || '';
        const fb = data.facebook_page_id || '';
        const ig = data.instagram_account_id || '';
        document.getElementById('cfg-phone-' + c).value = ph;
        document.getElementById('cfg-token-' + c).value = tk;
        document.getElementById('cfg-fb-' + c).value = fb;
        document.getElementById('cfg-ig-' + c).value = ig;
        window._cfgOriginal = window._cfgOriginal || {};
        window._cfgOriginal[c] = { phone_number: ph, meta_access_token: tk, facebook_page_id: fb, instagram_account_id: ig };
    } catch(e) {
        document.getElementById('cfg-status-' + c).innerHTML = '<span style="color:var(--red)">Failed to load profile.</span>';
    }
}

async function deleteClientProfile(clientId) {
    showConfirm(`Remove ${clientId} completely? This will delete the client profile, brand memory, vault assets, pending approvals, and scheduled jobs for this client.`, async () => {
        try {
            const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(clientId)), {
                method: 'DELETE'
            });
            const data = await res.json();
            if(res.ok && data.status === 'success') {
                globalClients = globalClients.filter(c => c !== clientId);
                populatePipelineSelectors(globalClients);
                if(currentVaultClient === clientId) closeVaultModal();
                try{ renderConfigCards(); } catch(e){}
                try{ renderVaults(); } catch(e){}
                try{ renderSchedule(); } catch(e){}
                try{ renderDashboardSummary(); } catch(e){}
                showNotification('Client Removed', `${clientId} and its saved local state were fully removed from Jarvis.`, false, {
                    accent: 'var(--red)',
                    rgb: '224,85,85',
                    duration: 7200,
                    position: 'bottom-right'
                });
            } else {
                showNotification('Delete Rejected', data.reason || 'Jarvis could not remove this client cleanly.', true, { position: 'bottom-right' });
            }
        } catch(e) {
            showNotification('Delete Failed', 'Connection failed while removing the client.', true, { position: 'bottom-right' });
        }
    });
}

async function saveClientDetails(clientId) {
    const statusEl = document.getElementById('cfg-det-status-' + clientId);
    statusEl.innerHTML = '<span style="color:var(--amber)">Writing brand profile to disk...</span>';
    
    const businessName = document.getElementById('cfg-business-' + clientId).value.trim();
    const industry = document.getElementById('cfg-industry-' + clientId).value.trim();
    const identity = document.getElementById('cfg-identity-' + clientId).value.trim();
    const tone = document.getElementById('cfg-tone-' + clientId).value.split(',').map(s => s.trim()).filter(Boolean);
    const style = document.getElementById('cfg-style-' + clientId).value.trim();
    const dialectNotes = document.getElementById('cfg-dialect-' + clientId).value.trim();
    const audience = document.getElementById('cfg-audience-' + clientId).value.trim();
    const services = document.getElementById('cfg-services-' + clientId).value.split(',').map(s => s.trim()).filter(Boolean);
    const seoKeywords = document.getElementById('cfg-seo-' + clientId).value.split(',').map(s => s.trim()).filter(Boolean);
    const hashtagBank = document.getElementById('cfg-hashtags-' + clientId).value.split(',').map(s => s.trim()).filter(Boolean);
    const bannedWords = document.getElementById('cfg-banned-' + clientId).value.split(',').map(s => s.trim()).filter(Boolean);
    const voiceExamples = document.getElementById('cfg-voice-examples-' + clientId).value.split('\n').map(s => s.trim()).filter(Boolean);
    const rules = document.getElementById('cfg-rules-' + clientId).value.split('\n').map(s => s.trim()).filter(Boolean);
    
    const targetVoice = document.getElementById('cfg-target-voice-' + clientId).value;

    const profileUpdate = {
        profile_json: {
            business_name: businessName,
            industry,
            identity,
            target_audience: audience,
            services,
            seo_keywords: seoKeywords,
            hashtag_bank: hashtagBank,
            banned_words: bannedWords,
            brand_voice_examples: voiceExamples,
            dos_and_donts: rules,
            language_profile: {
                target_voice_language: targetVoice
            },
            brand_voice: {
                tone,
                style,
                dialect: targetVoice === 'arabic_msa' ? 'msa' : (targetVoice.includes('arabic') ? 'gulf_arabic_khaleeji' : 'english'),
                dialect_notes: dialectNotes
            }
        }
    };
    
    try {
        const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(clientId)), {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(profileUpdate)
        });        const data = await res.json();
        if(res.ok && data.status === 'success') {
            statusEl.innerHTML = '<span style="color:#1fce9f; font-size:14px; font-weight:600;">Saved</span>';
            showNotification('Profile Updated', 'Brand details saved for ' + clientId, false);
        } else {
            if(Array.isArray(data.missing_fields) && data.missing_fields.length) {
                showHUDError(data.missing_fields);
            }
            statusEl.innerHTML = `<span style="color:var(--red)">${data.reason || 'Failed.'}</span>`;
        }
    } catch(e) {
        statusEl.innerHTML = '<span style="color:var(--red)">Connection failed.</span>';
    }
}

async function updateClientConfig(clientId) {
    const phone = document.getElementById('cfg-phone-' + clientId).value;
    const token = document.getElementById('cfg-token-' + clientId).value;
    const fb = document.getElementById('cfg-fb-' + clientId).value;
    const ig = document.getElementById('cfg-ig-' + clientId).value;
    const statusEl = document.getElementById('cfg-status-' + clientId);
    
    const orig = (window._cfgOriginal || {})[clientId] || {};
    const payload = {};
    const labels = {};
    if(phone !== (orig.phone_number || ''))       { payload.phone_number = phone; labels.phone_number = 'WhatsApp Phone'; }
    if(token !== (orig.meta_access_token || ''))   { payload.meta_access_token = token; labels.meta_access_token = 'Meta Access Token'; }
    if(fb !== (orig.facebook_page_id || ''))       { payload.facebook_page_id = fb; labels.facebook_page_id = 'Facebook Page ID'; }
    if(ig !== (orig.instagram_account_id || ''))   { payload.instagram_account_id = ig; labels.instagram_account_id = 'Instagram Account ID'; }
    
    if(Object.keys(payload).length === 0) {
        statusEl.innerHTML = '<span style="color:var(--t3)">No changes detected.</span>';
        return;
    }
    
    statusEl.innerHTML = '<span style="color:var(--amber)">Writing to disk...</span>';
    
    try {
        const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(clientId)), {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if(data.status === 'success') {
            const changedLabels = data.updated_fields.map(f => labels[f] || f);
            statusEl.innerHTML = `<span style="color:#1fce9f; font-size:14px; font-weight:600;">✓ Updated: ${changedLabels.join(', ')}</span>`;
            showNotification('Config Saved', changedLabels.join(', ') + ' refreshed for ' + clientId, false);
            window._cfgOriginal[clientId] = { phone_number: phone, meta_access_token: token, facebook_page_id: fb, instagram_account_id: ig };
        } else {
            statusEl.innerHTML = `<span style="color:var(--red)">${data.reason || 'Update rejected.'}</span>`;
        }
    } catch(e) {
        statusEl.innerHTML = '<span style="color:var(--red)">Connection failed.</span>';
    }
}
// --- VAULT MODAL LOGIC (Phase 11) ---
let currentVaultClient = null;
let currentVaultFiles = [];
let currentVaultBundles = {};
let selectedVaultImages = new Set();
let vaultActiveTab = 'assets';
let editingDraftName = null;
let currentCaptionDraftName = null;
let currentCaptionStudioMode = 'manual';
let currentCaptionStudioBaseline = '';
let currentClientProfile = null;
let currentClientValueBrief = null;

async function handleVaultUpload(source) {
    if(!currentVaultClient) return;
    const input = source && source.files ? source : document.getElementById('vault-file-upload');
    const files = input && input.files ? input.files : null;
    if(!files || files.length === 0) return;
    
    const formData = new FormData();
    formData.append("client_id", currentVaultClient);
    for(let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }
    
    const nameEl = document.getElementById('modal-client-name');
    const oldName = nameEl.innerText;
    nameEl.innerHTML = `<span style="color:var(--amber)">Uploading ${files.length} assets...</span>`;
    
    try {
        const res = await fetch(buildApiUrl("/api/upload-bulk"), { method: "POST", body: formData });
        const data = await res.json().catch(() => ({ status: 'error', reason: `Upload failed with HTTP ${res.status}.` }));
        if(data.status === "success") {
            delete vaultDataCache[currentVaultClient];
            showNotification('Upload Complete', `${data.uploaded_paths.length} assets secured in vault.`, false);
            await loadVaultData(true); // Refresh UI grid instantly
            await renderVaults(); // Refresh desktop underlying cards too
        } else {
            showNotification('Upload Failed', data.reason || 'Server error', true);
        }
    } catch(e) {
        showNotification('Upload Error', e?.message || 'Could not connect to server.', true);
    }
    
    if(input) input.value = '';
    nameEl.innerText = currentVaultClient + " Vault";
}

async function openVaultModal(clientId) {
    currentVaultClient = clientId;
    currentClientProfile = null;
    editingDraftName = null;
    
    // CRITICAL: Explicitly clear the vault state to prevent multi-tenant data leaks.
    // If we don't clear this, a slow or failed network request will cause the new modal
    // to display the previous client's assets and drafts.
    currentVaultFiles = [];
    currentVaultBundles = {};
    
    document.getElementById('modal-client-name').innerText = clientId + " Vault";
    document.getElementById('vault-modal').style.display = 'flex';
    switchVaultTab('assets');
    selectedVaultImages.clear();
    updateSelectionFooter();
    await loadVaultData(true);
}


function closeVaultModal() {
    document.getElementById('vault-modal').style.display = 'none';
    closeCaptionStudio();
    currentVaultClient = null;
    selectedVaultImages.clear();
    editingDraftName = null;
}

function switchVaultTab(tab) {
    vaultActiveTab = tab;
    document.getElementById('v-tab-assets').style.borderBottomColor = (tab === 'assets') ? 'var(--purple)' : 'transparent';
    document.getElementById('v-tab-assets').style.color = (tab === 'assets') ? 'var(--t1)' : 'var(--t3)';
    
    document.getElementById('v-tab-bundles').style.borderBottomColor = (tab === 'bundles') ? 'var(--purple)' : 'transparent';
    document.getElementById('v-tab-bundles').style.color = (tab === 'bundles') ? 'var(--t1)' : 'var(--t3)';
    
    document.getElementById('v-content-assets').style.display = (tab === 'assets') ? 'block' : 'none';
    document.getElementById('v-content-bundles').style.display = (tab === 'bundles') ? 'block' : 'none';
    
    document.getElementById('v-footer').style.display = (tab === 'assets') ? 'flex' : 'none';
}

async function loadVaultData(forceRefresh = false) {
    if(!currentVaultClient) return;
    delete draftMentionCache[currentVaultClient];
    try {
        const data = await fetchVaultData(currentVaultClient, { forceRefresh });
        if(data.status === 'success') {
            currentVaultFiles = data.files || [];
            currentVaultBundles = data.bundles || {};
            const visibleBundleKeys = Object.keys(currentVaultBundles).filter(name => !(currentVaultBundles[name] || {}).scheduled_locked);
            
            // Filter out files that are already part of a saved creative draft
            const bundledFiles = new Set(
                Object.values(currentVaultBundles).flatMap(bundle =>
                    Array.isArray(bundle)
                        ? bundle
                        : (bundle.items || []).map(item => item.filename)
                )
            );
            const availableFiles = currentVaultFiles.filter(f => !bundledFiles.has(typeof f === 'string' ? f : f.filename));
            
            document.getElementById('bundle-count').innerText = visibleBundleKeys.length;
            
            renderVaultGrid(availableFiles);
            renderVaultBundles();
        }
    } catch(e) {
        // SECURITY CRITICAL: Reset the state so we don't display the previous client's assets!
        currentVaultFiles = [];
        currentVaultBundles = {};
        renderVaultGrid([]);
        renderVaultBundles();
        document.getElementById('bundle-count').innerText = "0";
        showNotification("Vault Error", "Could not load vault data for " + currentVaultClient + ". " + (e.message || ""), true);
    }
}

function renderVaultGrid(files) {
    const grid = document.getElementById('modal-grid');
    grid.innerHTML = '';
    
    if(files.length === 0) {
        grid.innerHTML = '<div style="color:var(--t3); grid-column:1/-1; padding:20px; text-align:center;">No available assets right now. Upload more media to start a new creative draft.</div>';
        return;
    }
    
    files.forEach(fObj => {
        const f = typeof fObj === 'string' ? fObj : fObj.filename;
        const safeFile = escapeJsString(f);
        const isValid = typeof fObj === 'string' ? true : (fObj.is_valid_ig !== false);
        const warning = typeof fObj === 'string' ? "" : (fObj.warning || "");
        const kind = typeof fObj === 'string' ? 'image' : (fObj.kind || 'image');
        const canRepairMeta = typeof fObj === 'string' ? false : !!fObj.can_repair_meta;
        const previewUrl = getVaultAssetPreviewUrl(currentVaultClient, fObj);
        const posterUrl = getVaultAssetPosterUrl(currentVaultClient, fObj);
        
        const isSelected = selectedVaultImages.has(f);
        const div = document.createElement('div');
        div.className = `v-item ${isSelected ? 'selected' : ''}`;
        div.style.position = 'relative';
        div.onclick = () => toggleVaultImageSelection(f, div);
        
        let warningBadge = '';
        if(!isValid) {
            warningBadge = `<div title="${warning}" style="position:absolute; top:4px; right:4px; background:rgba(224,85,85,0.92); color:#fff; font-size:9px; font-weight:800; padding:3px 6px; border-radius:4px; z-index:10; box-shadow:0 2px 5px rgba(0,0,0,0.5); backdrop-filter:blur(2px); border:1px solid rgba(255,255,255,0.2);">IG LIMIT</div>`;
        }
        
        let discardBtn = `<button onclick="event.stopPropagation(); deleteVaultImage('${safeFile}')" style="position:absolute; top:4px; left:4px; background:rgba(0,0,0,0.6); color:#fff; border:none; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:14px; z-index:10; backdrop-filter:blur(2px); transition:all 0.2s; box-shadow:0 2px 4px rgba(0,0,0,0.5); line-height:1;" onmouseover="this.style.background='var(--red)'" onmouseout="this.style.background='rgba(0,0,0,0.6)'" title="Delete Media">×</button>`;
        let repairBtn = '';
        if(canRepairMeta) {
            repairBtn = `<button onclick="event.stopPropagation(); repairVaultVideoForMeta('${safeFile}')" style="position:absolute; top:4px; left:32px; background:rgba(232,155,26,0.92); color:#101010; border:none; height:22px; border-radius:999px; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:9px; font-weight:800; z-index:10; backdrop-filter:blur(2px); transition:all 0.2s; box-shadow:0 2px 4px rgba(0,0,0,0.5); line-height:1; padding:0 8px; letter-spacing:0.06em;" onmouseover="this.style.filter='brightness(1.08)'" onmouseout="this.style.filter='none'" title="Repair this video for Meta">REPAIR</button>`;
        }
        
        const kindBadge = kind === 'video'
            ? `<div style="position:absolute; bottom:6px; right:6px; background:rgba(47,168,224,0.9); color:#fff; font-size:9px; font-weight:800; padding:3px 6px; border-radius:999px; z-index:10; letter-spacing:0.4px;">VIDEO</div>`
            : '';
        const fileLabel = `<div style="position:absolute; left:8px; right:8px; bottom:8px; background:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(4,4,10,0.86) 45%, rgba(4,4,10,0.95) 100%); color:#f3f5ff; font-size:10px; line-height:1.35; padding:24px 8px 6px; z-index:9; pointer-events:none; font-family:'Space Mono'; word-break:break-word;">${escapeHtml(f)}</div>`;
        const fallback = `<div class="vault-preview-fallback" style="display:none; width:100%; height:100%; align-items:center; justify-content:center; text-align:center; padding:16px; color:var(--t3); font-size:11px; font-family:'Space Mono'; background:rgba(255,255,255,.03);">Preview unavailable</div>`;
        const mediaPreview = kind === 'video'
            ? `<video src="${previewUrl}" ${posterUrl ? `poster="${posterUrl}"` : ''} muted autoplay loop playsinline preload="metadata" onloadedmetadata="if(!this.getAttribute('poster') && this.duration){ try { this.currentTime = Math.min(0.6, Math.max(this.duration * 0.15, 0.12)); } catch(e) {} }" onerror="this.style.display='none'; const fb=this.parentElement.querySelector('.vault-preview-fallback'); if(fb) fb.style.display='flex';" style="width:100%; height:100%; object-fit:cover; background:linear-gradient(180deg, rgba(15,18,28,.88), rgba(5,7,12,.98)); ${!isValid ? 'border:1px solid var(--red);' : ''}"></video>${fallback}`
            : `<img src="${previewUrl}" alt="${f}" onerror="this.style.display='none'; const fb=this.parentElement.querySelector('.vault-preview-fallback'); if(fb) fb.style.display='flex';" style="${!isValid ? 'border:1px solid var(--red)' : ''}" />${fallback}`;
        div.innerHTML = `${discardBtn}${repairBtn}${warningBadge}${kindBadge}${mediaPreview}${fileLabel}`;
        grid.appendChild(div);
    });
}

async function deleteVaultImage(filename) {
    showConfirm(`Are you sure you want to permanently delete '${filename}' from the vault? This cannot be undone.`, async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/${encodeURIComponent(filename)}`), { method: 'DELETE' });
            const data = await res.json();
            if(data.status === 'success') {
                delete vaultDataCache[currentVaultClient];
                selectedVaultImages.delete(filename);
                updateSelectionFooter();
                await loadVaultData(true);
                await renderVaults();
                showNotification('Deleted', `'${filename}' was removed.`, false);
            } else {
                showNotification('Error', data.reason || 'Failed to delete.', true);
            }
        } catch(e) {
            showNotification('Error', 'Connection failed.', true);
        }
    });
}

function showConfirm(text, callback, options = {}) {
    const tone = String(options.tone || 'danger');
    const title = String(options.title || 'Delete Image');
    const confirmLabel = String(options.confirmLabel || 'Delete Permanently');
    const iconHtml = options.iconHtml || '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/></svg>';
    const titleEl = document.getElementById('confirm-modal-title');
    const titleTextEl = document.getElementById('confirm-modal-title-text');
    const iconEl = document.getElementById('confirm-modal-icon');
    const confirmBtn = document.getElementById('confirm-modal-yes');
    const palette = tone === 'success'
        ? {
            color: 'var(--green)',
            bg: 'rgba(31,206,160,.15)',
            border: '1px solid rgba(31,206,160,.3)',
            hover: 'rgba(31,206,160,.25)',
          }
        : tone === 'info'
          ? {
              color: 'var(--blue)',
              bg: 'rgba(47,168,224,.15)',
              border: '1px solid rgba(47,168,224,.3)',
              hover: 'rgba(47,168,224,.24)',
            }
          : {
              color: 'var(--red)',
              bg: 'rgba(224,85,85,.15)',
              border: '1px solid rgba(224,85,85,.3)',
              hover: 'rgba(224,85,85,.25)',
            };

    document.getElementById('confirm-modal-text').innerText = text;
    titleTextEl.textContent = title;
    iconEl.innerHTML = iconHtml;
    titleEl.style.color = palette.color;
    iconEl.style.color = palette.color;
    confirmBtn.textContent = confirmLabel;
    confirmBtn.style.color = palette.color;
    confirmBtn.style.background = palette.bg;
    confirmBtn.style.border = palette.border;
    confirmBtn.onmouseover = () => { confirmBtn.style.background = palette.hover; };
    confirmBtn.onmouseout = () => { confirmBtn.style.background = palette.bg; };
    window._confirmCallback = callback;
    document.getElementById('confirm-modal').style.display = 'flex';
}

async function repairVaultVideoForMeta(filename) {
    showConfirm(`Repair '${filename}' into a Meta-safe MP4 for Instagram and Facebook publishing?`, async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/${encodeURIComponent(filename)}/repair-meta`), { method: 'POST' });
            const data = await res.json();
            if(data.status === 'success') {
                delete vaultDataCache[currentVaultClient];
                await loadVaultData(true);
                await renderVaults();
                showNotification('Video Repaired', `'${filename}' was normalized for Meta delivery.`, false);
            } else {
                showNotification('Repair Failed', data.reason || 'Jarvis could not repair this video for Meta.', true);
            }
        } catch(e) {
            showNotification('Repair Failed', 'Jarvis could not reach the backend while repairing this video.', true);
        }
    }, {
        tone: 'info',
        title: 'Repair Video For Meta',
        confirmLabel: 'Repair Video',
        iconHtml: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15.55-5.66L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15.55 5.66L3 16"></path></svg>'
    });
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').style.display = 'none';
    window._confirmCallback = null;
}

document.getElementById('confirm-modal-yes').onclick = () => {
    if(window._confirmCallback) window._confirmCallback();
    closeConfirmModal();
};

document.getElementById('approval-move-submit').onclick = submitApprovalMove;
document.getElementById('approval-move-input').addEventListener('keydown', e => {
    if(e.key === 'Enter') {
        e.preventDefault();
        submitApprovalMove();
    }
});

function toggleVaultImageSelection(filename, node) {
    const fileMeta = currentVaultFiles.find(o => (typeof o === 'string' ? o : o.filename) === filename);
    const selectedNames = Array.from(selectedVaultImages);
    const selectedKinds = new Set(selectedNames.map(name => {
        const meta = currentVaultFiles.find(o => (typeof o === 'string' ? o : o.filename) === name);
        return typeof meta === 'string' ? 'image' : (meta?.kind || 'image');
    }));
    const incomingKind = typeof fileMeta === 'string' ? 'image' : (fileMeta?.kind || 'image');
    if(selectedVaultImages.has(filename)) {
        selectedVaultImages.delete(filename);
        node.classList.remove('selected');
    } else {
        if(selectedKinds.size && !selectedKinds.has(incomingKind)) {
        showNotification('Selection Locked', 'Select either images together or one video by itself. Mixed draft types are not supported yet.', true);
            return;
        }
        if(incomingKind === 'video' && selectedVaultImages.size >= 1) {
            showNotification('Single Video Only', 'Video posts currently support one video at a time.', true);
            return;
        }
        if(selectedKinds.has('video')) {
            showNotification('Single Video Only', 'Deselect the current video before choosing another asset.', true);
            return;
        }
        selectedVaultImages.add(filename);
        node.classList.add('selected');
    }
    updateSelectionFooter();
}

function updateSelectionFooter() {
    const count = selectedVaultImages.size;
    const selectedNames = Array.from(selectedVaultImages);
    const selectedKinds = new Set(selectedNames.map(name => {
        const meta = currentVaultFiles.find(o => (typeof o === 'string' ? o : o.filename) === name);
        return typeof meta === 'string' ? 'image' : (meta?.kind || 'image');
    }));
    const primaryKind = selectedKinds.has('video') ? 'video' : 'image';
    document.getElementById('selection-count').innerText = count === 0
        ? 'No assets selected'
        : `${count} ${primaryKind}${count !== 1 ? 's' : ''} selected`;
    
    const btn = document.querySelector('#v-footer button');
    if(count === 0) {
        btn.innerText = 'Create Draft';
    } else if(primaryKind === 'video') {
        btn.innerText = 'Create Reel Draft';
    } else {
        btn.innerText = count > 1 ? `Create Carousel Draft (${count})` : `Create Image Post`;
    }
    btn.style.opacity = count > 0 ? '1' : '0.5';
    btn.disabled = count === 0;
}

function getDraftTypeLabel(bundleType) {
    if(bundleType === 'video') return 'Reel';
    if(bundleType === 'image_carousel') return 'Carousel';
    return 'Image Post';
}

function isGenericDraftTopic(draftName, topic) {
    const hint = String(topic || '').trim();
    if(!hint) return true;
    if(hint.toLowerCase() === String(draftName || '').trim().toLowerCase()) return true;
    return /^(image post|carousel|reel)\s+\d+$/i.test(hint);
}

function buildSuggestedCampaignAngle(bundleName, bundle, profileJson) {
    const services = Array.isArray(profileJson?.services) ? profileJson.services.filter(Boolean) : [];
    const primaryService = services[0] || 'the main offer';
    const audience = String(profileJson?.target_audience || '').trim();
    const businessName = String(profileJson?.business_name || currentVaultClient || '').replace(/[_-]/g, ' ').trim();
    const bundleType = String(bundle?.bundle_type || 'image_single');

    if (bundleType === 'video') {
        if (audience) {
            return `Spotlight ${primaryService} with a fast, high-energy reel that makes ${audience} want to try ${businessName} now.`;
        }
        return `Spotlight ${primaryService} with a fast, high-energy reel that makes people want to try ${businessName} now.`;
    }

    if (bundleType === 'image_carousel') {
        if (audience) {
            return `Showcase ${primaryService} clearly across the carousel and make it feel worth choosing for ${audience}.`;
        }
        return `Showcase ${primaryService} clearly across the carousel and make it feel like a standout choice at ${businessName}.`;
    }

    if (audience) {
        return `Highlight ${primaryService} in a clean premium way and make ${audience} want to act on it today.`;
    }
    return `Highlight ${primaryService} in a clean premium way and make people want to try ${businessName} today.`;
}

function getNextDraftName(bundleType) {
    const prefix = getDraftTypeLabel(bundleType);
    let nextIndex = 1;
    while(currentVaultBundles[`${prefix} ${nextIndex}`]) nextIndex += 1;
    return `${prefix} ${nextIndex}`;
}

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeJsString(text) {
    return String(text ?? '')
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'");
}

function formatCaptionPreview(bundle) {
    const caption = String(bundle?.caption_text || '').trim();
    if(!caption) return 'No copy drafted yet. Generate with Jarvis or write the final copy yourself.';
    return caption.length > 140 ? `${caption.slice(0, 140).trim()}...` : caption;
}

function getCopyStatus(bundle) {
    const mode = String(bundle?.caption_mode || 'ai');
    const text = String(bundle?.caption_text || '').trim();
    if(!text) return { label: 'No Copy Yet', color: 'var(--t4)' };
    if(mode === 'manual') return { label: 'Manual Copy Ready', color: 'var(--solid-green)' };
    if(mode === 'hybrid') return { label: 'Edited Jarvis Draft', color: 'var(--purple)' };
    return { label: 'Jarvis Draft Ready', color: 'var(--blue)' };
}

function getReadableMediaType(bundleType) {
    if(bundleType === 'video') return 'Reel';
    if(bundleType === 'image_carousel') return 'Carousel';
    return 'Image Post';
}

function refreshCaptionStudioPreview() {
    const previewNode = document.getElementById('caption-studio-preview');
    const textarea = document.getElementById('caption-studio-text');
    if(!previewNode || !textarea) return;
    const text = textarea.value.trim();
    previewNode.textContent = text || 'No copy drafted yet.';
}

function normalizeHashtagToken(tag) {
    let value = String(tag || '').trim();
    if(!value) return '';
    value = value.replace(/^#+/, '').trim();
    if(!value) return '';
    value = value.replace(/\s+/g, '_');
    value = value.replace(/[^\u0600-\u06FFA-Za-z0-9_]/g, '');
    value = value.replace(/^_+|_+$/g, '');
    return value ? `#${value}` : '';
}

function normalizeHashtagListInput(value) {
    const parts = Array.isArray(value)
        ? value
        : String(value || '').split(/[\n,ØŒ;|]+/g);
    const normalized = [];
    const seen = new Set();
    for(const part of parts) {
        const tag = normalizeHashtagToken(part);
        if(!tag) continue;
        const key = tag.toLowerCase();
        if(seen.has(key)) continue;
        seen.add(key);
        normalized.push(tag);
    }
    return normalized;
}

async function loadClientProfileForStudio() {
    if(currentClientProfile && currentClientProfile._clientId === currentVaultClient) {
        return currentClientProfile;
    }
    try {
        const res = await fetch(buildApiUrl(`/api/client/${encodeURIComponent(currentVaultClient)}`));
        const data = await res.json();
        if(data && !data.reason) {
            currentClientProfile = {
                ...data,
                _clientId: currentVaultClient
            };
            return currentClientProfile;
        }
    } catch(e) {}
    currentClientProfile = {_clientId: currentVaultClient};
    return currentClientProfile;
}

async function openCaptionStudio(bundleName) {
    const bundle = currentVaultBundles[bundleName];
    if(!bundle) return;
    currentCaptionDraftName = bundleName;
    currentCaptionStudioMode = String(bundle.caption_mode || 'ai');
    currentCaptionStudioBaseline = String(bundle.caption_text || '');

    const profile = await loadClientProfileForStudio();
    const profileJson = profile?.profile_json || {};
    const brandVoice = profileJson.brand_voice || {};
    const toneSummary = Array.isArray(brandVoice.tone) ? brandVoice.tone.join(', ') : (brandVoice.tone || (Array.isArray(profileJson.tone) ? profileJson.tone.join(', ') : (profileJson.tone || '')));
    const voiceStyle = brandVoice.style || profileJson.style || '';
    const voiceSummary = [toneSummary, voiceStyle].filter(Boolean).join(' | ') || 'Voice profile incomplete';
    const identity = profileJson.identity || 'Add a short brand identity summary in Client Config so Jarvis writes like this business, not a generic page.';
    const seoBank = Array.isArray(profileJson.seo_keywords) ? profileJson.seo_keywords.slice(0, 5).join(' | ') : '';
    const rules = Array.isArray(profileJson.dos_and_donts) ? profileJson.dos_and_donts.slice(0, 3) : [];
    const examples = Array.isArray(profileJson.brand_voice_examples) ? profileJson.brand_voice_examples.slice(0, 2) : [];
    const dos = [...rules, ...examples].join(' | ');
    const audience = profileJson.target_audience ? `Audience: ${profileJson.target_audience}` : 'Audience: add the ideal buyer in Client Config';

    document.getElementById('caption-studio-title').innerText = `${currentVaultClient.replace(/[_-]/g, ' ')} | Copy Studio`;
    document.getElementById('caption-studio-subtitle').innerText = `Define what ${bundleName} should push, highlight, or sell before Jarvis moves it into approval.`;
    document.getElementById('caption-studio-draft-name').innerText = bundleName;
    document.getElementById('caption-studio-media-type').innerText = getReadableMediaType(bundle.bundle_type || 'image_single');
    const status = getCopyStatus(bundle);
    const statusNode = document.getElementById('caption-studio-status');
    statusNode.innerText = status.label;
    statusNode.style.color = status.color;
    document.getElementById('caption-studio-voice').innerText = voiceSummary;
    document.getElementById('caption-studio-audience').innerText = audience;
    document.getElementById('caption-studio-identity').innerText = identity;
    document.getElementById('caption-studio-seo-bank').innerText = seoBank || 'Add 3-10 search phrases in Client Config so Jarvis can anchor the copy around real keywords.';
    document.getElementById('caption-studio-guidance').innerText = dos || 'Add 3-5 brand voice examples plus copy rules in Client Config so Jarvis can match the voice more precisely.';
    const topicInput = document.getElementById('caption-studio-topic');
    const seoInput = document.getElementById('caption-studio-seo');
    const hashtagsInput = document.getElementById('caption-studio-hashtags');
    const textarea = document.getElementById('caption-studio-text');
    const suggestedAngle = buildSuggestedCampaignAngle(bundleName, bundle, profileJson);
    topicInput.value = isGenericDraftTopic(bundleName, bundle.topic_hint) ? suggestedAngle : (bundle.topic_hint || '');
    seoInput.value = bundle.seo_keyword_used || '';
    hashtagsInput.value = normalizeHashtagListInput(Array.isArray(bundle.hashtags) ? bundle.hashtags : []).join(', ');
    textarea.value = bundle.caption_text || '';
    textarea.oninput = () => {
        const currentText = textarea.value.trim();
        if(!currentText) currentCaptionStudioMode = 'manual';
        else if(currentCaptionStudioBaseline && currentCaptionStudioMode === 'ai' && currentText !== currentCaptionStudioBaseline.trim()) currentCaptionStudioMode = 'hybrid';
        else if(!currentCaptionStudioBaseline) currentCaptionStudioMode = 'manual';
        refreshCaptionStudioPreview();
    };
    topicInput.oninput = refreshCaptionStudioPreview;
    seoInput.oninput = refreshCaptionStudioPreview;
    hashtagsInput.oninput = refreshCaptionStudioPreview;
    hashtagsInput.onblur = () => {
        hashtagsInput.value = normalizeHashtagListInput(hashtagsInput.value).join(', ');
        refreshCaptionStudioPreview();
    };
    refreshCaptionStudioPreview();
    document.getElementById('caption-studio-modal').style.display = 'flex';
}

function closeCaptionStudio() {
    document.getElementById('caption-studio-modal').style.display = 'none';
    currentCaptionDraftName = null;
    currentCaptionStudioBaseline = '';
    currentCaptionStudioMode = 'manual';
}

/* #SECTION: Caption Studio */
async function generateDraftCaption(button) {
    if(!currentCaptionDraftName) return;
    const topic = document.getElementById('caption-studio-topic').value.trim();
    setButtonBusy(button, 'Jarvis is drafting...');
    try {
        const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles/${encodeURIComponent(currentCaptionDraftName)}/generate-caption`), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ topic })
        });
        const data = await res.json();
        if(data.status === 'success') {
            await loadVaultData(true);
            currentCaptionStudioMode = 'ai';
            const refreshed = currentVaultBundles[currentCaptionDraftName];
            currentCaptionStudioBaseline = String(refreshed?.caption_text || '');
            if(refreshed) await openCaptionStudio(currentCaptionDraftName);
            showNotification('Caption Drafted', `${currentCaptionDraftName} now has a Jarvis draft ready for review.`, false);
            return;
        }
        showNotification('Caption Rejected', data.reason || data.message || 'Failed to generate a caption.', true);
    } catch(e) {
        showNotification('Caption Failed', 'Connection failed while generating the draft caption.', true);
    } finally {
        restoreButtonBusy(button);
    }
}

async function saveDraftCaption(closeAfterSave = false) {
    if(!currentCaptionDraftName) return;
    const draftName = currentCaptionDraftName;
    const textarea = document.getElementById('caption-studio-text');
    const topicInput = document.getElementById('caption-studio-topic');
    const hashtagsInput = document.getElementById('caption-studio-hashtags');
    const seoInput = document.getElementById('caption-studio-seo');
    if(!textarea) return;

    const captionText = textarea.value.trim();
    const hashtags = hashtagsInput
        ? normalizeHashtagListInput(hashtagsInput.value)
        : [];
    const seoKeyword = seoInput ? seoInput.value.trim() : '';
    const captionMode = captionText
        ? (currentCaptionStudioMode === 'ai' && captionText !== currentCaptionStudioBaseline ? 'hybrid' : currentCaptionStudioMode || 'manual')
        : 'manual';

    try {
        const topic = topicInput ? topicInput.value.trim() : '';
        if(topic && currentVaultBundles[draftName]) {
            currentVaultBundles[draftName].topic_hint = topic;
        }
        const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles/${encodeURIComponent(draftName)}/caption`), {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                caption_text: captionText,
                hashtags,
                seo_keyword_used: seoKeyword,
                caption_mode: captionMode
            })
        });
        const data = await res.json();
        if(data.status === 'success') {
            await loadVaultData(true);
            currentCaptionStudioBaseline = captionText;
            currentCaptionStudioMode = captionMode;
            if(closeAfterSave) closeCaptionStudio();
            else if(currentVaultBundles[draftName]) await openCaptionStudio(draftName);
            showNotification('Copy Saved', `${draftName} is now carrying a stored ${captionMode === 'ai' ? 'Jarvis' : captionMode === 'hybrid' ? 'edited Jarvis' : 'manual'} caption.`, false);
            return;
        }
        showNotification('Save Rejected', data.reason || data.message || 'Failed to save the caption.', true);
    } catch(e) {
        showNotification('Save Failed', 'Connection failed while saving the caption.', true);
    }
}

function startDraftRename(name) {
    editingDraftName = name;
    renderVaultBundles();
}

function cancelDraftRename() {
    editingDraftName = null;
    renderVaultBundles();
}

async function saveDraftRename(oldName) {
    const triggerButton = arguments[1];
    const input = document.getElementById(`draft-rename-${encodeURIComponent(oldName)}`);
    if(!input) return;
    const newName = input.value.trim();
    if(!newName || newName === oldName) {
        editingDraftName = null;
        renderVaultBundles();
        return;
    }
    setButtonBusy(triggerButton, 'Renaming...');
    input.disabled = true;
    try {
        const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles/${encodeURIComponent(oldName)}/rename`), {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ new_name: newName })
        });
        const data = await res.json();
        if(data.status === 'success') {
            if(currentVaultBundles[oldName]) {
                currentVaultBundles[newName] = currentVaultBundles[oldName];
                delete currentVaultBundles[oldName];
            }
            editingDraftName = null;
            renderVaultBundles();
            loadVaultData(true).catch(() => null);
            showNotification('Draft Renamed', `${oldName} is now ${newName}.`, false);
            return;
        }
        if(res.status === 404 && (data.detail === 'Not Found' || !data.reason)) {
            showNotification('Rename Unavailable', 'The API server is still running an older build. Restart uvicorn, refresh the dashboard, then try renaming again.', true);
            return;
        }
        showNotification('Rename Rejected', data.reason || data.message || data.detail || 'Failed to rename draft.', true);
    } catch(e) {
        showNotification('Rename Failed', 'Connection failed while renaming the draft.', true);
    } finally {
        restoreButtonBusy(triggerButton);
        if(input) input.disabled = false;
    }
}

function renderVaultBundles() {
    const list = document.getElementById('modal-bundles-list');
    list.innerHTML = '';
    
    const hiddenCount = Object.values(currentVaultBundles).filter(bundle => !Array.isArray(bundle) && bundle && bundle.scheduled_locked).length;
    const bundleKeys = Object.keys(currentVaultBundles).filter(name => !(currentVaultBundles[name] || {}).scheduled_locked);
    if(bundleKeys.length === 0) {
        const hiddenNote = hiddenCount
            ? `<div style="margin-top:8px; color:var(--t4); font-size:12px;">${hiddenCount} draft${hiddenCount === 1 ? '' : 's'} already locked into the live schedule.</div>`
            : '';
        list.innerHTML = `<div style="color:var(--t3); padding:20px; text-align:center;">No creative drafts queued yet. Select assets from Available Assets to create one.${hiddenNote}</div>`;
        return;
    }
    
    bundleKeys.forEach(bName => {
        const bundle = currentVaultBundles[bName];
        const items = Array.isArray(bundle) ? bundle.map(f => ({ filename: f, kind: 'image' })) : (bundle.items || []);
        const files = items.map(item => item.filename);
        const bundleType = Array.isArray(bundle) ? (files.length > 1 ? 'image_carousel' : 'image_single') : (bundle.bundle_type || 'image_single');
        const captionPreview = formatCaptionPreview(bundle);
        const status = getCopyStatus(bundle);
        
        let needsInstagramFix = false;
        let warningMsg = "";
        for(let imgName of files) {
            const fObj = currentVaultFiles.find(o => (typeof o === 'string' ? o : o.filename) === imgName);
            if(fObj && fObj.is_valid_ig === false) {
                needsInstagramFix = true;
                warningMsg = fObj.warning;
                break;
            }
        }

        let warningBadge = needsInstagramFix ? `<span style="background:rgba(224,85,85,0.2); color:var(--red); font-size:10px; padding:2px 8px; border-radius:12px; font-weight:700; border:1px solid rgba(224,85,85,0.3);" title="${warningMsg}">IG LIMIT</span>` : '';
        
        let imgsHtml = items.map(item => {
            const f = item.filename;
            const fObj = getVaultAssetRecord(f);
            const isBad = fObj && fObj.is_valid_ig === false;
            const previewUrl = getVaultAssetPreviewUrl(currentVaultClient, fObj || item);
            if(item.kind === 'video') {
                return `<video src="${previewUrl}" muted playsinline preload="metadata" style="width:64px;height:64px;object-fit:cover;border-radius:10px;${isBad ? 'border:2px solid var(--red);' : ''}" title="${isBad ? fObj.warning : ''}"></video>`;
            }
            return `<img src="${previewUrl}" ${isBad ? 'style="border:2px solid var(--red);"' : ''} title="${isBad ? fObj.warning : ''}" />`;
        }).join('');
        
        const encodedName = encodeURIComponent(bName);
        const safeName = escapeJsString(bName);
        const nameMarkup = editingDraftName === bName
            ? `
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <input id="draft-rename-${encodedName}" class="qin" value="${escapeHtml(bName)}" style="max-width:260px; margin:0; height:34px;" />
                    <button onclick="saveDraftRename('${safeName}', this)" style="background:rgba(31,206,160,.12); border:1px solid rgba(31,206,160,.28); color:var(--solid-green); padding:6px 12px; font-size:11px; font-weight:700; border-radius:8px; cursor:pointer; font-family:'Space Mono';">Save</button>
                    <button onclick="cancelDraftRename()" style="background:transparent; border:1px solid rgba(255,255,255,.08); color:var(--t3); padding:6px 12px; font-size:11px; font-weight:700; border-radius:8px; cursor:pointer; font-family:'Space Mono';">Cancel</button>
                </div>`
            : `
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="color:var(--t1); font-weight:600; font-size:15px;">${escapeHtml(bName)}</span>
                    <button onclick="startDraftRename('${safeName}')" style="background:transparent; border:1px solid rgba(255,255,255,.08); color:var(--t3); padding:4px 8px; font-size:10px; font-weight:700; border-radius:999px; cursor:pointer; font-family:'Space Mono';">Rename</button>
                </div>`;
        const card = document.createElement('div');
        card.className = 'bundle-card';
        card.innerHTML = `
            <div>
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap;">
                    ${nameMarkup}
                    <span style="background:rgba(139,108,247,.15); color:var(--purple); font-size:10px; padding:2px 8px; border-radius:12px; font-weight:700;">${bundleType === 'video' ? 'REEL' : files.length > 1 ? 'CAROUSEL' : 'IMAGE POST'}</span>
                    <span style="background:rgba(255,255,255,.04); color:${status.color}; font-size:10px; padding:2px 8px; border-radius:12px; font-weight:700;">${status.label}</span>
                    ${warningBadge}
                </div>
                <div class="b-imgs">${imgsHtml}</div>
                <div style="margin-top:14px; padding:14px; border-radius:12px; border:1px solid rgba(255,255,255,.05); background:rgba(255,255,255,.02);">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px; flex-wrap:wrap;">
                        <div style="font-size:12px; font-weight:700; color:var(--t2); text-transform:uppercase; letter-spacing:.6px;">Copy Snapshot</div>
                        <div style="font-size:11px; color:var(--t4);">Open JARVIS Copywriter to generate or refine the final caption.</div>
                    </div>
                    <div style="font-size:13px; color:var(--t3); line-height:1.7; margin-bottom:12px;">${escapeHtml(captionPreview)}</div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <button onclick="openCaptionStudio('${safeName}')" style="background:rgba(47,168,224,.12); border:1px solid rgba(47,168,224,.25); color:var(--blue); padding:8px 12px; font-size:11px; font-weight:700; border-radius:8px; cursor:pointer; font-family:'Space Mono';">Open Copy Studio</button>
                    </div>
                </div>
            </div>
            <button onclick="deleteBundle('${safeName}')" style="background:rgba(224,85,85,.1); border:1px solid rgba(224,85,85,.2); color:#e05555; padding:6px 16px; font-size:12px; font-weight:600; border-radius:8px; cursor:pointer; transition:all .2s;" onmouseover="this.style.background='rgba(224,85,85,.2)'" onmouseout="this.style.background='rgba(224,85,85,.1)'">Remove Draft</button>
        `;
        list.appendChild(card);
    });
}

async function createBundleFromSelection() {
    if(selectedVaultImages.size === 0) return;
    
    const filesArray = Array.from(selectedVaultImages);
    const selectedMeta = filesArray.map(name => currentVaultFiles.find(o => (typeof o === 'string' ? o : o.filename) === name));
    const hasVideo = selectedMeta.some(meta => (typeof meta === 'string' ? 'image' : (meta?.kind || 'image')) === 'video');
    const bundleType = hasVideo ? 'video' : (filesArray.length > 1 ? 'image_carousel' : 'image_single');
    const bName = getNextDraftName(bundleType);
    
    try {
        const btn = document.querySelector('#v-footer button');
        btn.innerText = "Saving...";
        
        const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles`), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ bundle_name: bName, files: filesArray, bundle_type: bundleType })
        });
        const data = await res.json();
        if(data.status === 'success') {
            selectedVaultImages.clear();
            await loadVaultData(true);
            switchVaultTab('bundles');
            showNotification('Draft Created', `${bName} is ready in Creative Drafts.`, false);
        }
    } catch(e) {
        showNotification("Error", "Failed to create the creative draft.", true);
    }
}

async function deleteBundle(bName) {
    showConfirm(`Remove draft ${bName}? The source assets will return to Available Assets.`, async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles/${encodeURIComponent(bName)}`), { method: 'DELETE' });
            const data = await res.json();
            if(data.status === 'success') {
                await loadVaultData(true);
            }
        } catch(e) {
            showNotification("Error", "Failed to remove the draft.", true);
        }
    });
}

