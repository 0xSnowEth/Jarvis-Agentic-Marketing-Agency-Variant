
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
    return;
}

function startLockscreenScene() {
    return;
}

function stopLockscreenScene() {
    return;
}

// --- GLOBAL INIT ---
let globalClients = [];
let clientsSearchQuery = '';
let clientVaultCounts = {};
let clientWorkspaceDataCache = {};
let activeClientWorkspaceRequestToken = 0;
let activeVaultGridRequestToken = 0;
const deletingClientIds = new Set();
const clientWorkspaceSectionState = {};
let clientWizardStep = 1;
let latestReadinessChecks = {};
let dashboardRefreshLoopStarted = false;
let demoReadinessLoopStarted = false;
let clientWorkspaceInteractionUntil = 0;
let activeVaultUploadCount = 0;
const API_BASE = (() => {
    try {
        if (window.location && /^https?:$/i.test(window.location.protocol)) {
            return window.location.origin;
        }
    } catch(e) {}
    return "http://localhost:8000";
})();
const JARVIS_SESSION_KEY = "jarvis_admin_session";
const JARVIS_PUBLIC_ENTRY = "/";
const nativeFetch = window.fetch.bind(window);
let appBootstrapped = false;
let appBootPromise = null;
let jarvisAuthEnabled = false;
const vaultAssetsCache = {};
const vaultDraftsCache = {};
const warmedVaultMedia = new Set();

function markClientWorkspaceInteraction(durationMs = 15000) {
    clientWorkspaceInteractionUntil = Math.max(clientWorkspaceInteractionUntil, Date.now() + Math.max(1000, Number(durationMs || 0)));
}

function shouldSuspendClientWorkspaceAutoRefresh() {
    return currentPage === 'clients' || !!currentVaultClient || activeVaultUploadCount > 0 || Date.now() < clientWorkspaceInteractionUntil;
}

function getJarvisSessionToken() {
    try { return localStorage.getItem(JARVIS_SESSION_KEY) || ''; } catch(e) { return ''; }
}

function setJarvisSessionToken(token) {
    try {
        if(token) localStorage.setItem(JARVIS_SESSION_KEY, token);
        else localStorage.removeItem(JARVIS_SESSION_KEY);
    } catch(e) {}
}

function consumeJarvisSessionTokenFromUrl() {
    try {
        const url = new URL(window.location.href);
        const token = String(url.searchParams.get('session_token') || '').trim();
        if(!token) return;
        setJarvisSessionToken(token);
        url.searchParams.delete('session_token');
        window.history.replaceState({}, document.title, url.toString());
    } catch(e) {}
}

consumeJarvisSessionTokenFromUrl();

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
    if(file && typeof file === 'object') {
        const thumbUrl = String(file.thumb_url || file.preview_url || file.full_url || '').trim();
        if(thumbUrl) return resolvePreviewUrl(thumbUrl);
    }
    const filename = typeof file === 'string' ? file : file?.filename;
    return buildAssetUrl(clientId, filename);
}

function getVaultAssetFullUrl(clientId, file) {
    if(file && typeof file === 'object') {
        const fullUrl = String(file.full_url || file.preview_url || '').trim();
        if(fullUrl) return resolvePreviewUrl(fullUrl);
    }
    const filename = typeof file === 'string' ? file : file?.filename;
    return buildAssetUrl(clientId, filename);
}

function getVaultAssetPosterUrl(clientId, file) {
    if(!file || typeof file === 'string') return '';
    if(file.poster_thumb_url || file.poster_url) return resolvePreviewUrl(file.poster_thumb_url || file.poster_url);
    if(file.has_poster && file.filename) return `${buildAssetUrl(clientId, file.filename)}.jpg`;
    return '';
}

function getVaultAssetPosterFullUrl(clientId, file) {
    if(!file || typeof file === 'string') return '';
    if(file.poster_full_url || file.poster_url) return resolvePreviewUrl(file.poster_full_url || file.poster_url);
    if(file.has_poster && file.filename) return `${buildAssetUrl(clientId, file.filename)}.jpg`;
    return '';
}

function getVaultAssetRecord(filename) {
    return currentVaultFiles.find(item => (typeof item === 'string' ? item : item.filename) === filename) || null;
}

function clearVaultCache(clientId = '') {
    const key = String(clientId || '').trim();
    if(key) {
        delete vaultAssetsCache[key];
        delete vaultDraftsCache[key];
        Array.from(warmedVaultMedia).forEach(entry => {
            if(String(entry || '').startsWith(`${key}:`)) warmedVaultMedia.delete(entry);
        });
        return;
    }
    Object.keys(vaultAssetsCache).forEach(cacheKey => delete vaultAssetsCache[cacheKey]);
    Object.keys(vaultDraftsCache).forEach(cacheKey => delete vaultDraftsCache[cacheKey]);
    warmedVaultMedia.clear();
}

function normalizeVaultAssetRecord(clientId, asset) {
    if(!asset || typeof asset !== 'object') return asset;
    const metadata = (asset.metadata && typeof asset.metadata === 'object') ? asset.metadata : {};
    const filename = String(asset.filename || asset.original_filename || '').trim();
    const kind = String(asset.kind || asset.media_kind || metadata.media_kind || 'image').trim().toLowerCase();
    const warning = String(asset.warning || metadata.meta_repair_reason || '').trim();
    const hasPoster = asset.has_poster === true || metadata.has_poster === true;
    return {
        ...asset,
        filename,
        kind,
        is_video: kind === 'video',
        is_valid_ig: asset.is_valid_ig !== false && !warning,
        warning,
        can_repair_meta: kind === 'video' && !!metadata.needs_meta_repair,
        has_poster: hasPoster,
        width: Number(asset.width || metadata.width || 0) || 0,
        height: Number(asset.height || metadata.height || 0) || 0,
        mime_type: String(asset.mime_type || metadata.mime_type || ''),
        size_bytes: Number(asset.size_bytes || metadata.byte_size || metadata.size_bytes || 0) || 0,
        version_token: String(asset.version_token || metadata.preview_version || ''),
        thumb_url: asset.thumb_url || asset.preview_url || buildAssetUrl(clientId, filename),
        full_url: asset.full_url || buildAssetUrl(clientId, filename),
        poster_thumb_url: asset.poster_thumb_url || asset.poster_url || (hasPoster && filename ? `${buildAssetUrl(clientId, filename)}.jpg` : ''),
        poster_full_url: asset.poster_full_url || (hasPoster && filename ? `${buildAssetUrl(clientId, filename)}.jpg` : ''),
        preview_url: asset.thumb_url || asset.preview_url || buildAssetUrl(clientId, filename),
        poster_url: asset.poster_thumb_url || asset.poster_url || (hasPoster && filename ? `${buildAssetUrl(clientId, filename)}.jpg` : ''),
    };
}

function renderInstagramLimitBadge(warning = '', options = {}) {
    const compact = options.compact === true;
    const title = escapeHtml(String(warning || 'Instagram feed publishing requires a different asset format.').trim());
    if(compact) {
        return `<span title="${title}" style="background:rgba(224,85,85,0.18); color:#ff8f8f; font-size:10px; padding:2px 8px; border-radius:999px; font-weight:700; border:1px solid rgba(224,85,85,0.35); letter-spacing:0.08em; font-family:'Space Mono';">IG LIMIT</span>`;
    }
    return `<div title="${title}" style="position:absolute; top:8px; right:8px; background:linear-gradient(180deg, rgba(224,85,85,0.96), rgba(188,49,49,0.96)); color:#fff; font-size:9px; font-weight:800; padding:4px 7px; border-radius:999px; z-index:10; box-shadow:0 10px 24px rgba(0,0,0,0.32); backdrop-filter:blur(8px); border:1px solid rgba(255,255,255,0.18); letter-spacing:0.08em; font-family:'Space Mono';">IG LIMIT</div>`;
}

function renderInstagramLimitNote(warning = '', options = {}) {
    const subtle = options.subtle === true;
    const message = escapeHtml(String(warning || 'Instagram feed publishing needs a corrected aspect ratio or media format.').trim());
    return `<div style="margin-top:${subtle ? '8px' : '10px'}; padding:${subtle ? '8px 10px' : '10px 12px'}; border-radius:12px; background:rgba(224,85,85,0.08); border:1px solid rgba(224,85,85,0.22); color:${subtle ? '#ff9b9b' : 'var(--red)'}; font-size:12px; line-height:1.55;">${message}</div>`;
}

function getVisibleBundleKeys() {
    return Object.keys(currentVaultBundles).filter(name => !(currentVaultBundles[name] || {}).scheduled_locked);
}

function getAvailableVaultFiles() {
    const bundledFiles = new Set(
        Object.values(currentVaultBundles).flatMap(bundle =>
            Array.isArray(bundle)
                ? bundle
                : (bundle.items || []).map(item => item.filename)
        )
    );
    return currentVaultFiles.filter(f => !bundledFiles.has(typeof f === 'string' ? f : f.filename));
}

function renderCurrentVaultState() {
    document.getElementById('bundle-count').innerText = getVisibleBundleKeys().length;
    renderVaultGrid(getAvailableVaultFiles());
    renderVaultBundles();
}

function mergeUploadedAssetsIntoVault(clientId, uploadedAssets) {
    const incomingAssets = Array.isArray(uploadedAssets) ? uploadedAssets : [];
    if(!incomingAssets.length) return;

    const normalizedAssets = incomingAssets
        .map(asset => normalizeVaultAssetRecord(clientId, asset))
        .filter(asset => asset && asset.filename);

    if(!normalizedAssets.length) return;

    const merged = new Map(
        currentVaultFiles.map(item => {
            const record = typeof item === 'string' ? { filename: item } : item;
            return [record.filename, record];
        })
    );
    normalizedAssets.forEach(asset => merged.set(asset.filename, asset));
    currentVaultFiles = Array.from(merged.values());

    if(vaultAssetsCache[clientId] && vaultAssetsCache[clientId].status === 'success') {
        const cachedFiles = Array.isArray(vaultAssetsCache[clientId].files) ? vaultAssetsCache[clientId].files : [];
        const cachedMerged = new Map(
            cachedFiles.map(item => {
                const record = typeof item === 'string' ? { filename: item } : item;
                return [record.filename, record];
            })
        );
        normalizedAssets.forEach(asset => cachedMerged.set(asset.filename, asset));
        vaultAssetsCache[clientId] = {
            ...vaultAssetsCache[clientId],
            files: Array.from(cachedMerged.values()),
        };
    }

    renderCurrentVaultState();
}

function replaceVaultDraftBundles(clientId, bundles) {
    const normalizedBundles = (bundles && typeof bundles === 'object') ? bundles : {};
    if(currentVaultClient === clientId) {
        currentVaultBundles = { ...normalizedBundles };
        renderCurrentVaultState();
    }
    vaultDraftsCache[clientId] = {
        status: 'success',
        bundles: { ...normalizedBundles },
    };
}

function upsertVaultDraftBundle(clientId, draftName, payload) {
    const safeClientId = String(clientId || '').trim();
    const safeDraftName = String(draftName || '').trim();
    if(!safeClientId || !safeDraftName || !payload || typeof payload !== 'object') return;
    const nextPayload = { ...payload };
    if(currentVaultClient === safeClientId) {
        currentVaultBundles = {
            ...currentVaultBundles,
            [safeDraftName]: nextPayload,
        };
        renderCurrentVaultState();
    }
    const cached = vaultDraftsCache[safeClientId];
    vaultDraftsCache[safeClientId] = {
        status: 'success',
        bundles: {
            ...((cached && typeof cached.bundles === 'object') ? cached.bundles : {}),
            [safeDraftName]: nextPayload,
        },
    };
}

function buildDirectVaultMediaFallback(clientId, item = {}) {
    const filename = String(item?.filename || '').trim();
    if(!filename) return null;
    const kind = String(item?.kind || 'image').trim().toLowerCase();
    if(kind === 'video') {
        return null;
    }
    return {
        url: getVaultAssetPreviewUrl(clientId, { filename, kind }),
        label: filename,
        isVideo: false,
        clientId,
    };
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
    if(visible) {
        setBootProgress(0);
        document.querySelectorAll('.boot-step').forEach(step => step.classList.remove('active', 'done'));
    }
    overlay.classList.toggle('visible', !!visible);
    overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
}

function setBootStatus(message) {
    const sub = document.getElementById('boot-sub');
    if(sub && message) sub.textContent = message;
}

function setBootProgress(step, total = 3) {
    const fill = document.getElementById('boot-progress-fill');
    if(!fill) return;
    const safeTotal = Math.max(1, Number(total || 3));
    const safeStep = Math.max(0, Math.min(safeTotal, Number(step || 0)));
    const percent = safeStep <= 0 ? 10 : Math.round((safeStep / safeTotal) * 100);
    fill.style.width = `${percent}%`;
}

function warmVaultPreviewMedia(clientId, payload) {
    const files = Array.isArray(payload?.files) ? payload.files : [];
    const candidates = files
        .map(file => normalizeVaultAssetRecord(clientId, file))
        .slice(0, 10)
        .map(file => ({
            key: `${clientId}:${file.filename}:${file.version_token || ''}`,
            url: file.kind === 'video' ? getVaultAssetPosterUrl(clientId, file) : getVaultAssetPreviewUrl(clientId, file),
        }))
        .filter(item => item.url);

    candidates.forEach(item => {
        if(warmedVaultMedia.has(item.key)) return;
        warmedVaultMedia.add(item.key);
        const img = new Image();
        img.decoding = 'async';
        img.loading = 'eager';
        img.src = item.url;
        if(typeof img.decode === 'function') {
            img.decode().catch(() => null);
        }
    });
}

function renderVaultAssetSkeleton(count = 8) {
    const grid = document.getElementById('modal-grid');
    if(!grid) return;
    grid.innerHTML = '';
    const skeletonCount = Math.max(4, count);
    for(let i = 0; i < skeletonCount; i += 1) {
        const tile = document.createElement('div');
        tile.className = 'v-item';
        tile.style.position = 'relative';
        tile.style.pointerEvents = 'none';
        tile.style.overflow = 'hidden';
        tile.innerHTML = `
            <div class="v-item-media">
                <div class="vault-media-skeleton"></div>
            </div>
            <div class="v-item-footer">
                <div style="height:12px; width:72%; border-radius:999px; background:rgba(255,255,255,.06);"></div>
            </div>
        `;
        grid.appendChild(tile);
    }
}

function renderVaultDraftsPlaceholder(message = 'Creative drafts are syncing in the background...') {
    const list = document.getElementById('modal-bundles-list');
    if(!list) return;
    list.innerHTML = `<div style="color:var(--t3); padding:20px; text-align:center;">${escapeHtml(message)}</div>`;
}

async function fetchVaultAssets(clientId, options = {}) {
    const forceRefresh = !!options.forceRefresh;
    const resolvedClientId = resolveWorkspaceClientId(clientId);
    if(!resolvedClientId) return null;
    if(!forceRefresh && vaultAssetsCache[resolvedClientId]) return vaultAssetsCache[resolvedClientId];
    const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(resolvedClientId)}/assets`));
    const raw = await res.text();
    let data = null;
    try {
        data = raw ? JSON.parse(raw) : null;
    } catch(jsonErr) {
        throw new Error((raw || `Vault request failed with status ${res.status}.`).trim());
    }
    if(data && data.status === 'success') {
        vaultAssetsCache[resolvedClientId] = data;
        warmVaultPreviewMedia(resolvedClientId, data);
        return data;
    }
    throw new Error((data && (data.reason || data.message)) || 'Vault unavailable.');
}

async function fetchVaultDrafts(clientId, options = {}) {
    const forceRefresh = !!options.forceRefresh;
    const resolvedClientId = resolveWorkspaceClientId(clientId);
    if(!resolvedClientId) return null;
    if(!forceRefresh && vaultDraftsCache[resolvedClientId]) return vaultDraftsCache[resolvedClientId];
    const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(resolvedClientId)}/drafts`));
    const raw = await res.text();
    let data = null;
    try {
        data = raw ? JSON.parse(raw) : null;
    } catch(jsonErr) {
        throw new Error((raw || `Creative drafts request failed with status ${res.status}.`).trim());
    }
    if(data && data.status === 'success') {
        vaultDraftsCache[resolvedClientId] = data;
        return data;
    }
    throw new Error((data && (data.reason || data.message)) || 'Creative drafts unavailable.');
}

async function fetchVaultData(clientId, options = {}) {
    const [assets, drafts] = await Promise.all([
        fetchVaultAssets(clientId, options),
        fetchVaultDrafts(clientId, options),
    ]);
    return {
        status: 'success',
        files: assets?.files || [],
        bundles: drafts?.bundles || {},
    };
}

async function preloadVaultCache(clientIds) {
    const ids = Array.isArray(clientIds) ? clientIds.filter(Boolean) : [];
    if(!ids.length) return;
    await Promise.allSettled(ids.map(clientId => fetchVaultAssets(clientId).catch(() => null)));
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
        note.style.color = isError ? 'var(--red)' : 'var(--t3)';
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
    showBootOverlay(false);
    syncAuthUi();
    const target = new URL(JARVIS_PUBLIC_ENTRY, window.location.origin);
    target.searchParams.set('reason', message);
    window.location.replace(target.toString());
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
    clearVaultCache();
    warmedVaultMedia.clear();
    syncAuthUi();
    window.location.replace(new URL(JARVIS_PUBLIC_ENTRY, window.location.origin).toString());
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
        window.location.replace(new URL(JARVIS_PUBLIC_ENTRY, window.location.origin).toString());
        return;
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
        setBootProgress(1);
        setBootStatus('Linking client registries and reading the agency roster...');
        await new Promise(r => setTimeout(r, 600)); // Pacing for UI
        
        try {
            const res = await fetch(buildApiUrl("/api/clients"));
            const data = await res.json();
            if(data.status === "success" && Array.isArray(data.clients)) {
                clients = data.clients;
                globalClients = data.clients;
                populatePipelineSelectors(data.clients);
                populateOrchestratorComposerClients();
            }
        } catch(e) { console.log("System unlinked from CRM."); }
        
        // Step 2: Scheduling & Indexing
        document.getElementById('boot-step-1')?.classList.replace('active', 'done');
        document.getElementById('boot-step-2')?.classList.add('active');
        setBootProgress(2);
        setBootStatus('Indexing schedules, approvals, and the live operator surface...');
        await new Promise(r => setTimeout(r, 700));

        const tasks = [
            renderDashboardSummary().catch(() => null),
            renderSchedule().catch(() => null),
        ];

        // Step 3: Vaults
        document.getElementById('boot-step-2')?.classList.replace('active', 'done');
        document.getElementById('boot-step-3')?.classList.add('active');
        setBootProgress(3);
        
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
        setBootProgress(3);
        await new Promise(r => setTimeout(r, 400)); // Final pause before vanishing
        
        nav('dashboard', getSidebarNavItem('dashboard'));
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
        if(!shouldSuspendClientWorkspaceAutoRefresh()) {
            try{ renderVaults(); } catch(e){}
            try{ renderConfigCards(); } catch(e){}
        }
        try{ renderSettingsHealth(); } catch(e){}
    }, 10000);
}

window.addEventListener('DOMContentLoaded', () => {
    initializeJarvisAuth();
    renderNavPings();
});

document.addEventListener('focusin', event => {
    const target = event.target;
    if(target && (target.closest('#config-grid') || target.closest('#vault-modal') || target.closest('.client-wizard-shell'))) {
        markClientWorkspaceInteraction();
    }
});

document.addEventListener('input', event => {
    const target = event.target;
    if(target && (target.closest('#config-grid') || target.closest('#vault-modal') || target.closest('.client-wizard-shell'))) {
        markClientWorkspaceInteraction();
    }
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
  const targetPage = getPrimaryNavPage(page);
  setJarvisDrawerState(false);
  closeScheduleDrawer();
  currentPage = targetPage;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const targetNode = document.getElementById('p-' + targetPage);
  targetNode.classList.add('active');
  if(targetNode) targetNode.setAttribute('aria-hidden', 'false');
  const activeNav = el || getSidebarNavItem(targetPage);
  if (activeNav) activeNav.classList.add('active');
  if(targetPage === 'schedule') acknowledgeNavPing(targetPage);
  
  if(targetPage === 'agents') {
    loadAgencyConfig();
    renderSettingsHealth();
  }
  if(targetPage === 'dashboard') renderDashboardSummary();
  if(targetPage === 'clients') {
    renderVaults();
    renderConfigCards();
    updateClientWizardSummary();
  }
  if(targetPage === 'schedule') {
    renderSchedule();
    renderStrategyPlans().catch(() => null);
  }
  if(targetPage === 'orchestrator') {
    prepareJarvisSurface();
  }
  syncJarvisFabMode();
  
  const cards = document.querySelectorAll(`#p-${targetPage} .reveal-3d`);
  cards.forEach(c => c.style.animation = 'none');
  setTimeout(() => cards.forEach(c => c.style.animation = ''), 10);
}

function syncJarvisFabMode() {
    const fab = document.getElementById('jarvis-fab');
    const scheduleFab = document.getElementById('schedule-fab');
    const drawer = document.getElementById('p-orchestrator');
    const scheduleDrawer = document.getElementById('schedule-drawer');
    if(!fab) return;
    const jarvisPageActive = getPrimaryNavPage(currentPage) === 'orchestrator';
    const schedulePageActive = getPrimaryNavPage(currentPage) === 'schedule';
    const drawerOpen = !!drawer?.classList.contains('open');
    const scheduleDrawerOpen = !!scheduleDrawer?.classList.contains('open');
    fab.classList.toggle('hidden', jarvisPageActive || drawerOpen || schedulePageActive || scheduleDrawerOpen);
    fab.classList.remove('jarvis-fab-compact');
    fab.style.right = '24px';
    fab.style.bottom = '24px';
    fab.style.top = 'auto';
    if(scheduleFab) {
        scheduleFab.classList.toggle('hidden', !schedulePageActive || scheduleDrawerOpen || drawerOpen);
    }
}

function setClientWizardStep(step, options = {}) {
    const normalized = Math.max(1, Math.min(3, Number(step || 1)));
    clientWizardStep = normalized;
    document.querySelectorAll('.client-wizard-step').forEach(node => {
        const nodeStep = Number(node.dataset.step || 0);
        node.classList.toggle('is-active', nodeStep === normalized);
        node.classList.toggle('is-done', nodeStep < normalized);
    });
    document.querySelectorAll('.client-wizard-panel[data-panel-step]').forEach(node => {
        const nodeStep = Number(node.dataset.panelStep || 0);
        node.classList.toggle('is-active', nodeStep === normalized);
    });
    updateClientWizardSummary();
    syncJarvisFabMode();
    if(options.scroll) {
        const targetPanel = document.querySelector(`.client-wizard-panel[data-panel-step="${normalized}"]`) || document.querySelector('.client-wizard-shell');
        targetPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function updateClientWizardSummary() {
    const clientId = String(document.getElementById('c-name')?.value || '').trim();
    const brandName = String(document.getElementById('c-quick-brand')?.value || document.getElementById('c-business')?.value || '').trim();
    const language = String(document.getElementById('c-quick-language')?.value || 'arabic').trim();
    const profile = buildIntakeProfileJson();
    const tokens = [
      clientId,
      document.getElementById('c-token')?.value,
      document.getElementById('c-fb')?.value,
      document.getElementById('c-ig')?.value,
      document.getElementById('c-quick-offer')?.value,
      document.getElementById('c-quick-audience')?.value,
      document.getElementById('c-quick-tone')?.value,
      document.getElementById('c-quick-products')?.value,
      profile.business_name,
      profile.identity,
      profile.target_audience,
      Array.isArray(profile.services) ? profile.services.join(',') : '',
      Array.isArray(profile.brand_voice_examples) ? profile.brand_voice_examples.join('\n') : '',
    ];
    const filled = tokens.filter(value => String(value || '').trim()).length;
    const score = Math.max(0, Math.min(100, Math.round((filled / tokens.length) * 100)));
    const stepTitles = {
      1: 'Connect channels',
      2: 'Brand basics',
      3: 'Review & save',
    };
    const statusCopy = {
      1: 'Start with the workspace ID and channel credentials, then move into the quick setup.',
      2: 'Simple answers are enough here. Website links and old briefs only enrich the profile.',
      3: 'Jarvis drafted the structure. Review the profile carefully, then save the client live.',
    };
    const languageLabels = {
      arabic: 'Arabic',
      english: 'English',
      bilingual: 'Arabic + English',
    };
    const clientValue = document.getElementById('wizard-summary-client');
    const languageValue = document.getElementById('wizard-summary-language');
    const stepValue = document.getElementById('wizard-summary-step');
    const stageValue = document.getElementById('wizard-summary-stage');
    const scoreValue = document.getElementById('wizard-summary-score');
    const meterValue = document.getElementById('wizard-summary-meter');
    const statusValue = document.getElementById('wizard-summary-status');
    const copyValue = document.getElementById('wizard-summary-copy');
    if(clientValue) clientValue.textContent = brandName || clientId || 'New workspace';
    if(languageValue) languageValue.textContent = languageLabels[language] || 'Arabic';
    if(stepValue) stepValue.textContent = `Step ${clientWizardStep}`;
    if(stageValue) stageValue.textContent = stepTitles[clientWizardStep];
    if(scoreValue) scoreValue.textContent = `${score}%`;
    if(meterValue) meterValue.style.width = `${score}%`;
    if(statusValue) statusValue.textContent = statusCopy[clientWizardStep];
    if(copyValue) copyValue.textContent = clientWizardStep === 3
      ? 'Jarvis drafted the brand structure here. Edit it until the voice feels right before saving.'
      : 'Jarvis can synthesize from simple answers. Optional links and briefs only enrich the profile.';
}

function startNewClientWizard() {
    nav('clients', document.getElementById('nav-clients'));
    resetClientIntakeForm();
    setClientWizardStep(1, { scroll: true });
    document.getElementById('c-name')?.focus();
}

function syncApprovalRoutingUi() {
    const phone = String(document.getElementById('agency-owner-phone')?.value || '').trim();
    const token = String(document.getElementById('agency-whatsapp-token')?.value || '').trim();
    const select = document.getElementById('agency-approval-routing');
    const lane = document.getElementById('agency-mobile-lane');
    const desktopNote = document.getElementById('agency-desktop-routing-note');
    const laneNote = document.getElementById('agency-mobile-lane-note');
    const laneCopy = document.getElementById('agency-mobile-lane-copy');
    if(!select) return;
    const whatsappHealthy = !!latestReadinessChecks.whatsapp_runtime?.ok;
    const current = String(select.value || 'desktop_first').trim() || 'desktop_first';
    const options = [
      { value: 'desktop_first', label: 'Desktop First' },
      { value: 'desktop_and_whatsapp', label: 'Desktop + WhatsApp Mirror' },
    ];
    if(whatsappHealthy || current === 'whatsapp_only') {
      options.push({ value: 'whatsapp_only', label: 'WhatsApp Only' });
    }
    select.innerHTML = options.map(option => `<option value="${option.value}">${option.label}</option>`).join('');
    select.value = options.some(option => option.value === current) ? current : 'desktop_first';
    const showAdvanced = Boolean(phone || token || select.value !== 'desktop_first');
    if(lane) {
      lane.style.display = showAdvanced ? 'block' : 'none';
      if(select.value !== 'desktop_first') lane.open = true;
    }
    if(desktopNote) desktopNote.textContent = `Current default: ${getApprovalRouteLabel(select.value)}`;
    if(laneNote) {
      laneNote.textContent = whatsappHealthy
        ? 'WhatsApp runtime is healthy. Mobile approval routing is available.'
        : token
          ? 'WhatsApp runtime still needs attention. Jarvis will keep desktop as the safe fallback.'
          : 'Desktop stays the main workstation. WhatsApp only appears when the runtime is ready.';
    }
    if(laneCopy) {
      laneCopy.textContent = showAdvanced
        ? 'Use this only when the agency genuinely needs a mobile approval lane.'
        : 'Add the owner phone and token only when you want WhatsApp approval routing in the live workflow.';
    }
}

async function loadAgencyConfig() {
    try {
        const res = await fetch(buildApiUrl("/api/agency/config"));
        const data = await res.json();
        if(data.owner_phone) document.getElementById('agency-owner-phone').value = data.owner_phone;
        if(data.whatsapp_access_token !== undefined) document.getElementById('agency-whatsapp-token').value = data.whatsapp_access_token || "";
        if(data.approval_routing) document.getElementById('agency-approval-routing').value = data.approval_routing;
    } catch(e) {}
    syncApprovalRoutingUi();
}

function setAgencyConfigSavingState(isSaving) {
    const button = document.getElementById('agency-config-save-btn');
    if(!button) return;
    if(!button.dataset.defaultLabel) {
        button.dataset.defaultLabel = button.textContent.trim();
    }
    button.disabled = !!isSaving;
    button.classList.toggle('is-saving', !!isSaving);
    button.setAttribute('aria-busy', isSaving ? 'true' : 'false');
    button.innerHTML = isSaving
        ? '<span>Saving</span><span class="save-dots">...</span>'
        : button.dataset.defaultLabel;
}

function setSynthesizeButtonState(isBuilding) {
    const button = document.getElementById('btn-synth');
    if(!button) return;
    if(!button.dataset.defaultMarkup) {
        button.dataset.defaultMarkup = button.innerHTML.trim();
    }
    button.disabled = !!isBuilding;
    button.classList.toggle('is-building', !!isBuilding);
    button.setAttribute('aria-busy', isBuilding ? 'true' : 'false');
    button.innerHTML = isBuilding
        ? '<span class="client-wizard-build-shell"><span class="client-wizard-build-sigil" aria-hidden="true"></span><span class="client-wizard-build-copy">Building Profile<span class="client-wizard-build-dots">...</span></span></span>'
        : button.dataset.defaultMarkup;
}

async function saveAgencyConfig() {
    const phone = document.getElementById('agency-owner-phone').value;
    const whatsappToken = document.getElementById('agency-whatsapp-token').value;
    const approvalRouting = document.getElementById('agency-approval-routing').value;
    setAgencyConfigSavingState(true);
    try {
        const res = await fetch(buildApiUrl("/api/agency/config"), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ owner_phone: phone, whatsapp_access_token: whatsappToken, approval_routing: approvalRouting })
        });
        syncApprovalRoutingUi();
        if(res.ok) showNotification("Saved", "Approval controls updated successfully.", false, { position: 'bottom-right' });
        else showNotification("Error", "Failed to save configuration.", true);
    } catch(e) { showNotification("Error", "Connection failed.", true); }
    finally { setAgencyConfigSavingState(false); }
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
  card.addEventListener('mouseenter', () => {
    card.classList.add('hover-active');
  });

  card.addEventListener('mouseleave', () => {
    card.classList.remove('hover-active');
  });
});

(function tick() {
  const n = new Date();
  const clock = document.getElementById('clock');
  if(clock) {
    clock.textContent =
      String(n.getHours()).padStart(2,'0') + ':' +
      String(n.getMinutes()).padStart(2,'0') + ':' +
      String(n.getSeconds()).padStart(2,'0');
  }
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
  const navMap = {
    dashboard: 'nav-dashboard',
    orchestrator: 'nav-orchestrator',
    clients: 'nav-clients',
    schedule: 'nav-schedule',
    agents: 'nav-agents',
  };
  const mapped = navMap[getPrimaryNavPage(page)];
  if(mapped) {
    const node = document.getElementById(mapped);
    if(node) return node;
  }
  return Array.from(document.querySelectorAll('.nav-item')).find(node => node.offsetParent !== null && String(node.getAttribute('onclick') || '').includes(`'${page}'`)) || null;
}

function openPageSurface(page) {
  nav(page, getSidebarNavItem(page));
}

function getFilteredClients() {
  const query = String(clientsSearchQuery || '').trim().toLowerCase();
  if(!query) return [...globalClients];
  return globalClients.filter(client => String(client || '').toLowerCase().includes(query));
}

function handleClientsSearch(value = '') {
  clientsSearchQuery = String(value || '').trim();
  renderVaults();
  renderConfigCards();
}

function getPrimaryNavPage(page) {
  if(page === 'vaults' || page === 'config' || page === 'clients') return 'clients';
  if(page === 'logs' || page === 'agents') return 'agents';
  if(page === 'schedule') return 'schedule';
  if(page === 'orchestrator') return 'orchestrator';
  return 'dashboard';
}

function prepareJarvisSurface() {
  populateOrchestratorComposerClients();
  renderOrchestratorComposerSelections();
  syncMissionControlActionUI();
  renderMissionControlPlanCard();
  renderMissionControlRunTimeline();
  hydrateMissionControlRun();
}

function setJarvisDrawerState(open) {
  const drawer = document.getElementById('p-orchestrator');
  const backdrop = document.getElementById('assistant-backdrop');
  const fab = document.getElementById('jarvis-fab');
  if(!drawer || !backdrop) return;
  const jarvisPageActive = getPrimaryNavPage(currentPage) === 'orchestrator';
  drawer.classList.toggle('drawer-mode', !!open);
  drawer.classList.toggle('open', !!open);
  if(open) drawer.classList.add('active');
  else if(!jarvisPageActive) drawer.classList.remove('active');
  drawer.setAttribute('aria-hidden', (open || jarvisPageActive) ? 'false' : 'true');
  backdrop.classList.toggle('open', !!open);
  if(fab) fab.classList.toggle('hidden', !!open || jarvisPageActive);
  syncJarvisFabMode();
}

function openJarvisDrawer() {
  closeScheduleDrawer();
  prepareJarvisSurface();
  setJarvisDrawerState(true);
}

function closeJarvisDrawer() {
  setJarvisDrawerState(false);
}

function toggleJarvisDrawer() {
  const drawer = document.getElementById('p-orchestrator');
  if(drawer?.classList.contains('open')) closeJarvisDrawer();
  else openJarvisDrawer();
}

function setScheduleDrawerState(open) {
  const drawer = document.getElementById('schedule-drawer');
  const backdrop = document.getElementById('schedule-drawer-backdrop');
  if(!drawer || !backdrop) return;
  drawer.classList.toggle('open', !!open);
  drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
  backdrop.classList.toggle('open', !!open);
  syncJarvisFabMode();
}

function openScheduleDrawer() {
  closeJarvisDrawer();
  renderSchedule().catch(() => null);
  setScheduleDrawerState(true);
}

function closeScheduleDrawer() {
  setScheduleDrawerState(false);
}

function toggleScheduleDrawer() {
  const drawer = document.getElementById('schedule-drawer');
  if(drawer?.classList.contains('open')) closeScheduleDrawer();
  else openScheduleDrawer();
}

function scrollJarvisThreadToLatest() {
  const chat = document.getElementById('orch-chat');
  const shell = document.querySelector('#p-orchestrator .orch-shell');
  if(chat?.lastElementChild && typeof chat.lastElementChild.scrollIntoView === 'function') {
    chat.lastElementChild.scrollIntoView({ block: 'end', behavior: 'auto' });
  }
  if(chat) chat.scrollTop = chat.scrollHeight;
  if(shell) shell.scrollTop = shell.scrollHeight;
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

function renderWorkEmpty(message) {
  return `<div class="work-empty">${escapeHtml(message)}</div>`;
}

function renderWorkBadges(badges = []) {
  const filtered = Array.isArray(badges) ? badges.filter(Boolean) : [];
  return filtered.length ? `<div class="work-item-badges">${filtered.join('')}</div>` : '';
}

function renderWorkBadge(label, tone = 'neutral') {
  const palette = {
    good: 'background:rgba(31,206,160,.12); color:var(--solid-green); border:1px solid rgba(31,206,160,.24);',
    warn: 'background:rgba(232,155,26,.12); color:var(--amber); border:1px solid rgba(232,155,26,.24);',
    danger: 'background:rgba(224,85,85,.12); color:var(--red); border:1px solid rgba(224,85,85,.24);',
    info: 'background:rgba(47,168,224,.12); color:var(--blue); border:1px solid rgba(47,168,224,.24);',
    neutral: 'background:rgba(255,255,255,.05); color:var(--t3); border:1px solid rgba(255,255,255,.08);',
  };
  return `<span class="work-item-badge" style="${palette[tone] || palette.neutral}">${escapeHtml(label)}</span>`;
}

function renderWorkItem(title, copy, options = {}) {
  const kicker = options.kicker ? `<div class="work-item-kicker">${escapeHtml(options.kicker)}</div>` : '';
  const meta = options.meta ? `<div class="work-item-meta">${options.meta}</div>` : '';
  const action = options.actionLabel && options.actionOnclick
    ? `<button type="button" class="work-item-action" onclick="${options.actionOnclick}">${escapeHtml(options.actionLabel)}</button>`
    : '';
  return `
    <div class="work-item">
      <div class="work-item-main">
        ${kicker}
        <div class="work-item-title">${escapeHtml(title)}</div>
        <div class="work-item-copy">${copy}</div>
        ${meta}
      </div>
      ${action}
    </div>
  `;
}

function humanizeSettingCheckKey(key) {
  const labels = {
    api: 'API',
    runtime_state: 'Runtime state',
    scheduler: 'Scheduler',
    public_media_host: 'Public media host',
    whatsapp_runtime: 'WhatsApp',
    meta_client_credentials: 'Meta credentials',
    tunnel_runtime: 'Tunnel runtime',
  };
  return labels[key] || String(key || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderSettingsHealthRow(key, check = {}) {
  const ok = !!check.ok;
  return `
    <div class="health-check-row">
      <div class="health-check-copy">
        <div class="health-check-title">${escapeHtml(humanizeSettingCheckKey(key))}</div>
        <div class="health-check-text">${escapeHtml(check.detail || (ok ? 'Healthy.' : 'Needs attention.'))}</div>
      </div>
      ${renderWorkBadge(ok ? 'Healthy' : 'Attention', ok ? 'good' : 'danger')}
    </div>
  `;
}

async function renderDashboardSummary() {
  const livePill = document.getElementById('dashboard-live-pill');
  const workSummary = document.getElementById('work-summary-copy');
  const setupList = document.getElementById('work-setup-list');
  const approvalsList = document.getElementById('work-approvals-list');
  const scheduledList = document.getElementById('work-scheduled-list');
  const blockedList = document.getElementById('work-blocked-list');
  const publishedList = document.getElementById('work-published-list');

  try {
    const [summaryRes, approvalsRes, scheduleRes, healthRes] = await Promise.allSettled([
      fetch(buildApiUrl('/api/dashboard-summary')).then(r => r.json()),
      fetch(buildApiUrl('/api/approvals/pending')).then(r => r.json()),
      fetch(buildApiUrl('/api/schedule')).then(r => r.json()),
      fetch(buildApiUrl('/api/health')).then(r => r.json()),
    ]);

    const summaryPayload = summaryRes.status === 'fulfilled' ? summaryRes.value : null;
    if(!summaryPayload || summaryPayload.status !== 'success') throw new Error('summary unavailable');

    const approvalsPayload = approvalsRes.status === 'fulfilled' ? approvalsRes.value : {};
    const schedulePayload = scheduleRes.status === 'fulfilled' ? scheduleRes.value : {};
    const healthPayload = healthRes.status === 'fulfilled' ? healthRes.value : {};

    const s = summaryPayload.summary || {};
    const clients = Array.isArray(s.clients) ? s.clients : [];
    const approvals = Array.isArray(approvalsPayload.approvals) ? approvalsPayload.approvals : [];
    const activeJobs = Array.isArray(schedulePayload.schedule) ? schedulePayload.schedule : [];
    const historyJobs = Array.isArray(schedulePayload.history) ? schedulePayload.history : [];
    const checks = healthPayload.readiness?.checks || {};
    const runtimeIssues = Object.entries(checks).filter(([, check]) => check && check.ok === false);
    const nextJob = s.next_job || activeJobs[0] || null;

    const chipClients = document.getElementById('work-chip-clients');
    const chipDrafts = document.getElementById('work-chip-drafts');
    const chipApprovals = document.getElementById('work-chip-approvals');
    const chipNext = document.getElementById('work-chip-next');
    if(chipClients) chipClients.textContent = s.client_count || clients.length || 0;
    if(chipDrafts) chipDrafts.textContent = s.draft_count || 0;
    if(chipApprovals) chipApprovals.textContent = approvals.length || s.pending_approval_count || 0;
    if(chipNext) chipNext.textContent = nextJob ? `${nextJob.client || 'Queued'} · ${nextJob.display_window || `${nextJob.scheduled_date || ''} ${nextJob.time || ''}`.trim()}` : 'No release queued';

    if(workSummary) {
      if(approvals.length) {
        workSummary.textContent = `Jarvis found ${approvals.length} approval${approvals.length === 1 ? '' : 's'} waiting right now. Clear those first, then move into the scheduled queue and only open settings if something is actually blocked.`;
      } else if(nextJob) {
        workSummary.textContent = `Jarvis is keeping the next release lined up for ${nextJob.client || 'the queue'} at ${nextJob.display_window || `${nextJob.scheduled_date || ''} ${nextJob.time || ''}`.trim()}. This home surface stays focused on action, not theater.`;
      } else {
        workSummary.textContent = `Jarvis is watching ${clients.length} client${clients.length === 1 ? '' : 's'}, ${s.draft_count || 0} draft${Number(s.draft_count || 0) === 1 ? '' : 's'}, and the runtime surface. Nothing urgent is queued right now.`;
      }
    }

    if(livePill) {
      if(!runtimeIssues.length) {
        livePill.innerHTML = `<div class="pill-dot"></div>Queue healthy · ${approvals.length} approval${approvals.length === 1 ? '' : 's'} waiting`;
      } else {
        livePill.innerHTML = `<div class="pill-dot" style="background:var(--amber)"></div>${escapeHtml(humanizeSettingCheckKey(runtimeIssues[0][0]))} needs attention`;
      }
    }

    const setupClients = clients.filter(client => !client.profile_ready || !client.credentials_ready || Number(client.draft_count || 0) === 0);
    if(setupList) {
      setupList.innerHTML = setupClients.length ? setupClients.slice(0, 6).map(client => {
        const issues = [];
        if(!client.profile_ready && Array.isArray(client.missing_fields) && client.missing_fields.length) {
          issues.push(`Missing ${client.missing_fields.slice(0, 3).join(', ')}`);
        }
        if(!client.credentials_ready) issues.push('Meta credentials still need to be connected.');
        if(Number(client.draft_count || 0) === 0) issues.push('No saved draft is ready yet.');
        return renderWorkItem(
          client.display_name || client.client_id,
          escapeHtml(issues.join(' ') || 'This client still needs setup attention.'),
          {
            kicker: 'Client setup',
            meta: renderWorkBadges([
              renderWorkBadge(client.profile_ready ? 'Profile Ready' : 'Profile Missing', client.profile_ready ? 'good' : 'danger'),
              renderWorkBadge(client.credentials_ready ? 'Credentials Ready' : 'Credentials Missing', client.credentials_ready ? 'good' : 'warn'),
              renderWorkBadge(`${client.draft_count || 0} Drafts`, Number(client.draft_count || 0) > 0 ? 'info' : 'warn'),
            ]),
            actionLabel: 'Open Clients',
            actionOnclick: "nav('clients', document.getElementById('nav-clients'))",
          }
        );
      }).join('') : renderWorkEmpty('All mapped clients have profiles, credentials, and at least one draft ready.');
    }

    if(approvalsList) {
      approvalsList.innerHTML = approvals.length ? approvals.slice(0, 6).map(job => renderWorkItem(
        `${job.client || 'Unknown client'} · ${job.draft_name || 'Draft'}`,
        escapeHtml(`${buildApprovalCaptionPreview(job)} Scheduled for ${formatApprovalScheduleLine(job)}.`),
        {
          kicker: 'Approval waiting',
          meta: renderWorkBadges([
            renderWorkBadge(summarizeApprovalAssets(job), 'info'),
            renderWorkBadge(job.whatsapp_sent ? 'WhatsApp sent' : 'Desktop review', job.whatsapp_sent ? 'good' : 'warn'),
            renderWorkBadge(getApprovalRouteLabel(approvalsPayload.approval_routing || 'desktop_first'), 'neutral'),
          ]),
          actionLabel: 'Review',
          actionOnclick: `openApprovalReviewModal('${escapeForSingleQuotedJs(job.approval_id || '')}')`,
        }
      )).join('') : renderWorkEmpty('No approvals are waiting right now.');
    }

    if(scheduledList) {
      scheduledList.innerHTML = activeJobs.length ? activeJobs.slice(0, 6).map(job => renderWorkItem(
        `${String(job.client || 'Unknown').replace(/_/g, ' ')} · ${getScheduleDraftLabel(job).replace(/<[^>]+>/g, '')}`,
        escapeHtml(`Scheduled for ${job.display_window || `${job.scheduled_date || ''} ${job.time || ''}`.trim() || 'Time pending'}. ${getScheduleIntentLabel(job).replace(/<[^>]+>/g, '')}`),
        {
          kicker: 'Scheduled release',
          meta: `<div class="work-item-badges">${formatSchedulePills(job) || renderWorkBadge(job.time || 'Scheduled', 'info')}</div>`,
          actionLabel: 'Open Calendar',
          actionOnclick: "nav('schedule', document.getElementById('nav-schedule'))",
        }
      )).join('') : renderWorkEmpty('No upcoming releases are scheduled in the next window.');
    }

    const blockedEntries = [];
    runtimeIssues.forEach(([key, check]) => {
      blockedEntries.push(renderWorkItem(
        humanizeSettingCheckKey(key),
        escapeHtml(check.detail || 'This runtime dependency needs attention before delivery is fully reliable.'),
        {
          kicker: 'Runtime',
          meta: renderWorkBadges([renderWorkBadge('Attention', 'danger')]),
          actionLabel: 'Open Settings',
          actionOnclick: "nav('agents', document.getElementById('nav-agents'))",
        }
      ));
    });
    clients.filter(client => !client.credentials_ready || !client.profile_ready).slice(0, 4).forEach(client => {
      blockedEntries.push(renderWorkItem(
        client.display_name || client.client_id,
        escapeHtml(!client.profile_ready
          ? `Brand profile still needs review${Array.isArray(client.missing_fields) && client.missing_fields.length ? `: ${client.missing_fields.slice(0, 3).join(', ')}` : '.'}`
          : 'Meta credentials are incomplete for this client.'),
        {
          kicker: 'Client health',
          meta: renderWorkBadges([
            renderWorkBadge(client.profile_ready ? 'Profile Ready' : 'Profile Missing', client.profile_ready ? 'good' : 'danger'),
            renderWorkBadge(client.credentials_ready ? 'Credentials Ready' : 'Credentials Missing', client.credentials_ready ? 'good' : 'warn'),
          ]),
          actionLabel: 'Open Clients',
          actionOnclick: "nav('clients', document.getElementById('nav-clients'))",
        }
      ));
    });
    if(blockedList) {
      blockedList.innerHTML = blockedEntries.length ? blockedEntries.join('') : renderWorkEmpty('No blocked runtime checks or broken client setups are currently visible.');
    }

    if(publishedList) {
      publishedList.innerHTML = historyJobs.length ? historyJobs.slice(0, 6).map(job => renderWorkItem(
        `${String(job.client || 'Unknown').replace(/_/g, ' ')} · ${getScheduleDraftLabel(job).replace(/<[^>]+>/g, '')}`,
        escapeHtml(formatDeliveredAt(job).replace(/<[^>]+>/g, '')),
        {
          kicker: 'Delivered',
          meta: renderWorkBadges([renderWorkBadge(job.status || 'Delivered', 'good')]),
          actionLabel: 'Open Calendar',
          actionOnclick: "nav('schedule', document.getElementById('nav-schedule'))",
        }
      )).join('') : renderWorkEmpty('No recent published history is available yet.');
    }

    if(Array.isArray(s.recent_activity) && s.recent_activity.length) {
      const log = document.getElementById('activity-log');
      if(log && !log.dataset.seeded) {
        log.innerHTML = s.recent_activity.slice().reverse().map(line => {
          const match = String(line).replace(/</g, '&lt;').replace(/>/g, '&gt;');
          return `<div class="log-item"><div class="lt">BOOT</div><div class="ld" style="background:var(--blue)"></div><div class="lx">${match}</div></div>`;
        }).join('');
        log.dataset.seeded = 'true';
      }
    }
  } catch (e) {
    if(livePill) livePill.innerHTML = `<div class="pill-dot" style="background:var(--amber)"></div>Work queue unavailable`;
    if(workSummary) workSummary.textContent = 'Jarvis could not read the live operator queue from the backend.';
    if(setupList) setupList.innerHTML = renderWorkEmpty('Client setup data is unavailable until the backend responds.');
    if(approvalsList) approvalsList.innerHTML = renderWorkEmpty('Approval inbox is unavailable until the backend responds.');
    if(scheduledList) scheduledList.innerHTML = renderWorkEmpty('Calendar data is unavailable until the backend responds.');
    if(blockedList) blockedList.innerHTML = renderWorkEmpty('Blocked runtime data is unavailable until the backend responds.');
    if(publishedList) publishedList.innerHTML = renderWorkEmpty('Recent publish history is unavailable until the backend responds.');
  }
}

async function renderSettingsHealth() {
  const list = document.getElementById('settings-health-list');
  if(!list) return;
  try {
    const res = await fetch(buildApiUrl('/api/health'));
    const data = await res.json();
    const checks = data.readiness?.checks || {};
    latestReadinessChecks = checks;
    syncApprovalRoutingUi();
    const entries = Object.entries(checks);
    list.innerHTML = entries.length
      ? entries.map(([key, check]) => renderSettingsHealthRow(key, check)).join('')
      : renderWorkEmpty('No readiness checks were returned by the backend.');
  } catch (e) {
    latestReadinessChecks = {};
    syncApprovalRoutingUi();
    list.innerHTML = renderWorkEmpty('Runtime health is unavailable until the backend responds.');
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
  if(!log) return;
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
  hud.style.right = '28px';
  hud.style.bottom = '26px';
  hud.style.transform = 'translate(0, 20px)';
  hud.style.maxWidth = '420px';
  hud.style.background = 'rgba(2,2,10,0.85)';
  hud.style.border = `1px solid rgba(${INTAKE_CRYSTAL_RGB},0.42)`;
  hud.style.boxShadow = `0 10px 40px rgba(${INTAKE_CRYSTAL_RGB},0.16), inset 0 0 20px rgba(${INTAKE_CRYSTAL_RGB},0.06)`;
  hud.style.borderRadius = '14px';
  hud.style.padding = '20px 22px';
  hud.style.zIndex = '9999';
  hud.style.backdropFilter = 'blur(16px)';
  hud.style.color = 'var(--t1)';
  hud.style.opacity = '0';
  hud.style.transition = 'all 0.4s cubic-bezier(0.25, 1, 0.5, 1)';
  
  let html = `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;color:${INTAKE_CRYSTAL}"><div style="display:flex;align-items:center;gap:12px;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><span style="font-size:15px;font-weight:700;letter-spacing:-0.4px">Profile Needs Review</span></div><button onclick="this.closest('div[style*=fixed]').remove()" style="background:transparent;border:1px solid rgba(255,255,255,0.12);color:var(--t3);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:11px;font-family:'Space Mono';">Close</button></div>`;
  html += `<div style="font-size:13px;color:var(--t3);margin-bottom:12px;line-height:1.55">Jarvis still needs a few important brand details before this client profile is reliable enough to save:</div>`;
  
  fields.forEach(f => {
      html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-family:'Space Mono';font-size:12px;color:${INTAKE_CRYSTAL_SOFT}"><div style="width:4px;height:4px;background:${INTAKE_CRYSTAL};border-radius:50%"></div>${f}</div>`;
  });
  
  html += `<div style="font-size:11px;color:var(--t4);margin-top:14px;opacity:0.8;line-height:1.5">Complete the missing fields in the review panel, then save the client once the profile looks right.</div>`;
  
  hud.innerHTML = html;
  document.body.appendChild(hud);
  
  setTimeout(() => { hud.style.opacity = '1'; hud.style.transform = 'translate(0, 0)'; }, 10);
  setTimeout(() => {
      hud.style.opacity = '0';
      hud.style.transform = 'translate(0, 10px)';
      setTimeout(() => hud.remove(), 400);
  }, 16000);
}

function showNotification(title, message, isError = false, options = {}) {
  const hud = document.createElement('div');
  const position = options.position || 'top-center';
  const notificationState = String(options.state || (isError ? 'error' : 'success')).toLowerCase();
  const isPending = notificationState === 'pending';
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
  const accent = options.accent || (isPending ? 'var(--amber)' : isError ? 'var(--red)' : 'var(--green)');
  const rgb = options.rgb || (isPending ? '244,211,138' : isError ? '224,85,85' : '31,206,160');
  const duration = Number.isFinite(options.duration) ? options.duration : 4000;
  const messageColor = options.messageColor || 'var(--t3)';
  const icon = isPending
    ? `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" opacity=".45"></circle><path d="M12 7v5l3 2"></path></svg>`
    : isError 
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

function toast(message, tone = 'success', options = {}) {
  const normalizedTone = String(tone || 'success').toLowerCase();
  const isError = normalizedTone === 'error';
  const title = normalizedTone === 'warn'
    ? 'Attention'
    : isError
      ? 'Action Failed'
      : normalizedTone === 'success'
        ? 'Updated'
        : 'Jarvis';
  return showNotification(title, String(message || ''), isError, options);
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
  const accents = {
    neutral: `rgba(${INTAKE_CRYSTAL_RGB},0.16)`,
    success: 'rgba(31,206,160,0.16)',
    warning: 'rgba(244,211,138,0.16)',
    error: 'rgba(224,85,85,0.16)'
  };
  const borders = {
    neutral: `rgba(${INTAKE_CRYSTAL_RGB},0.26)`,
    success: 'rgba(31,206,160,0.28)',
    warning: 'rgba(244,211,138,0.28)',
    error: 'rgba(224,85,85,0.28)'
  };
  const glyph = {
    neutral: 'J',
    success: '✓',
    warning: '!',
    error: '×'
  };
  el.style.background = accents[tone] || accents.neutral;
  el.style.borderColor = borders[tone] || borders.neutral;
  el.innerHTML = `<span style="display:flex;align-items:flex-start;gap:10px;color:${colors[tone] || colors.neutral}"><span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;border:1px solid currentColor;font-size:11px;line-height:1;flex-shrink:0;margin-top:1px;">${glyph[tone] || glyph.neutral}</span><span>${message}</span></span>`;
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
  let targetVoice = lang.target_voice_language || '';
  if(!targetVoice) {
    if(lang.caption_output_language === 'bilingual' || lang.primary_language === 'bilingual') targetVoice = 'bilingual';
    else if(lang.caption_output_language === 'english' || lang.primary_language === 'english') targetVoice = 'english';
    else if(lang.arabic_mode === 'msa') targetVoice = 'arabic_msa';
    else targetVoice = 'arabic_gulf';
  }
  document.getElementById('c-target-voice').value = targetVoice;
  syncIntakeJsonPreview();
  updateClientWizardSummary();
}

function buildQuickIntakePayload() {
  return {
    brand_name: document.getElementById('c-quick-brand').value.trim(),
    business_type: document.getElementById('c-quick-type').value.trim(),
    what_they_sell: document.getElementById('c-quick-offer').value.trim(),
    target_audience: document.getElementById('c-quick-audience').value.trim(),
    main_language: document.getElementById('c-quick-language').value.trim(),
    brand_tone: document.getElementById('c-quick-tone').value.trim(),
    products_examples: document.getElementById('c-quick-products').value.trim(),
    city_market: document.getElementById('c-quick-city').value.trim(),
    offer_focus: document.getElementById('c-quick-promo').value.trim(),
    words_to_avoid: document.getElementById('c-quick-avoid').value.trim(),
    inspiration_links: document.getElementById('c-quick-links').value.trim(),
  };
}

function hasQuickIntakeSignal(payload = buildQuickIntakePayload()) {
  const meaningfulKeys = [
    'brand_name',
    'business_type',
    'what_they_sell',
    'target_audience',
    'brand_tone',
    'products_examples',
    'city_market',
    'offer_focus',
    'words_to_avoid',
    'inspiration_links'
  ];
  return meaningfulKeys.some(key => String(payload[key] || '').trim());
}

function resetClientIntakeForm() {
  [
    'c-name', 'c-context', 'c-phone', 'c-token', 'c-fb', 'c-ig',
    'c-quick-brand', 'c-quick-type', 'c-quick-offer', 'c-quick-audience',
    'c-quick-language', 'c-quick-tone', 'c-quick-products', 'c-quick-city',
    'c-quick-promo', 'c-quick-avoid', 'c-quick-links', 'c-website', 'c-social'
  ].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'SELECT') {
      el.selectedIndex = 0;
      return;
    }
    el.value = '';
  });
  populateIntakeProfileForm({});
  const fileInput = document.getElementById('file-input-brand');
  if (fileInput) fileInput.value = '';
  const fileStatus = document.getElementById('file-drop-status');
  if (fileStatus) fileStatus.textContent = 'Optional: drop PDF, DOCX, TXT, or MD here to enrich the quick setup.';
  const preview = document.getElementById('c-json-preview');
  if (preview) {
    preview.value = '';
    preview.style.borderColor = '';
  }
  setIntakeReviewStatus('Fill the quick setup above, then let Jarvis draft the profile here. You can edit everything before saving.', 'neutral');
  setClientWizardStep(1);
  updateClientWizardSummary();
}

function scrubClientWizardAutofillLeak() {
  const workspaceInput = document.getElementById('c-name');
  const tokenInput = document.getElementById('c-token');
  if(!workspaceInput || !tokenInput) return;

  const workspaceValue = String(workspaceInput.value || '').trim();
  const tokenValue = String(tokenInput.value || '').trim();
  if(!workspaceValue && !tokenValue) return;

  const structuralFields = [
    'c-phone', 'c-fb', 'c-ig',
    'c-quick-brand', 'c-quick-type', 'c-quick-offer', 'c-quick-audience',
    'c-quick-tone', 'c-quick-products', 'c-website', 'c-social', 'c-context'
  ];
  const hasMeaningfulClientSetup = structuralFields.some(id => String(document.getElementById(id)?.value || '').trim());
  const looksLikePhoneLeak = /^\+?\d{8,15}$/.test(workspaceValue);
  const looksLikeTokenLeak = tokenValue.length > 24;

  if(!hasMeaningfulClientSetup && (looksLikePhoneLeak || looksLikeTokenLeak)) {
    workspaceInput.value = '';
    tokenInput.value = '';
    updateClientWizardSummary();
  }
}

function buildIntakeProfileJson() {
  const targetVoice = document.getElementById('c-target-voice').value;
  const captionOutputLanguage = targetVoice === 'bilingual' ? 'bilingual' : (targetVoice === 'english' ? 'english' : 'arabic');
  const arabicMode = targetVoice === 'arabic_msa' ? 'msa' : 'gulf';
  const primaryLanguage = targetVoice === 'bilingual' ? 'bilingual' : (targetVoice === 'english' ? 'english' : 'arabic');
  return {
    business_name: document.getElementById('c-business').value.trim(),
    industry: document.getElementById('c-industry').value.trim(),
    identity: document.getElementById('c-identity').value.trim(),
    target_audience: document.getElementById('c-audience').value.trim(),
    website_url: document.getElementById('c-website').value.trim(),
    social_url: document.getElementById('c-social').value.trim(),
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
      target_voice_language: targetVoice,
      brief_language: captionOutputLanguage,
      primary_language: primaryLanguage,
      caption_output_language: captionOutputLanguage,
      arabic_mode: captionOutputLanguage === 'arabic' ? arabicMode : ''
    },
    brand_voice: {
      tone: parseCsvInput(document.getElementById('c-tone').value),
      style: document.getElementById('c-style').value.trim(),
      dialect: targetVoice === 'arabic_msa' ? 'msa' : (targetVoice.includes('arabic') ? 'gulf_arabic_khaleeji' : 'english'),
      dialect_notes: document.getElementById('c-dialect').value.trim()
    }
  };
}

function syncIntakeJsonPreview() {
  const preview = document.getElementById('c-json-preview');
  if(!preview) {
    updateClientWizardSummary();
    return;
  }
  const profile = buildIntakeProfileJson();
  const quickIntake = buildQuickIntakePayload();
  const website = document.getElementById('c-website').value.trim();
  const social = document.getElementById('c-social').value.trim();
  const rawContext = document.getElementById('c-context').value.trim();
  const hasSignal = Boolean(
    profile.business_name ||
    profile.industry ||
    profile.identity ||
    profile.target_audience ||
    profile.services.length ||
    profile.brand_voice_examples.length
  );
  if(hasSignal) {
    preview.value = JSON.stringify(profile, null, 2);
    return;
  }
  const requestPreview = {
    quick_intake: quickIntake,
    website_url: website || undefined,
    social_url: social || undefined,
    raw_context: rawContext || undefined
  };
  const requestHasSignal = hasQuickIntakeSignal(quickIntake) || website || social || rawContext;
  preview.value = requestHasSignal ? JSON.stringify(requestPreview, null, 2) : '';
  updateClientWizardSummary();
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
            status.textContent = `Imported ${file.name} into the optional notes section - ${(file.size/1024).toFixed(1)} KB`;
            syncIntakeJsonPreview();
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
            status.textContent = `Extracted ${data.source_type.toUpperCase()} brief - ${data.char_count} readable characters merged into optional notes`;
            syncIntakeJsonPreview();
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

    [
      'c-name','c-business','c-industry','c-audience','c-identity','c-services','c-tone','c-style','c-dialect',
      'c-voice-examples','c-seo','c-hashtags','c-banned','c-rules','c-context','c-website','c-social',
      'c-quick-brand','c-quick-type','c-quick-offer','c-quick-audience','c-quick-language','c-quick-tone',
      'c-quick-products','c-quick-city','c-quick-promo','c-quick-avoid','c-quick-links'
    ].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.addEventListener('input', syncIntakeJsonPreview);
        if(el && el.tagName === 'SELECT') el.addEventListener('change', syncIntakeJsonPreview);
    });

    syncIntakeJsonPreview();
    setTimeout(scrubClientWizardAutofillLeak, 60);
    setTimeout(scrubClientWizardAutofillLeak, 500);
    ['agency-owner-phone', 'agency-whatsapp-token', 'agency-approval-routing'].forEach(id => {
        const el = document.getElementById(id);
        if(!el) return;
        el.addEventListener('input', syncApprovalRoutingUi);
        el.addEventListener('change', syncApprovalRoutingUi);
    });
    updateClientWizardSummary();
    syncJarvisFabMode();
});

async function synthesizeClient() {
  const name = document.getElementById('c-name').value.trim();
  const context = document.getElementById('c-context').value.trim();
  const quickIntake = buildQuickIntakePayload();
  const websiteUrl = document.getElementById('c-website').value.trim();
  const socialUrl = document.getElementById('c-social').value.trim();
  if(!name) return showNotification("Missing Client ID", "Jarvis still needs the client workspace ID before it can build the profile.", true);
  if(!hasQuickIntakeSignal(quickIntake) && !context && !websiteUrl && !socialUrl) {
    return showNotification("Missing Client Details", "Give Jarvis a few simple client details, a website/social link, or some extra notes before synthesis.", true);
  }
  
  const btn = document.getElementById('btn-synth');
  setSynthesizeButtonState(true);
  setIntakeReviewStatus("Jarvis is turning the quick setup and optional sources into a structured brand profile...", "neutral");
  try{ triggerNeuralPulse(); } catch(e){}
  const synthController = new AbortController();
  const synthAbortTimer = setTimeout(() => synthController.abort(), 110000);
  const progressNote1 = setTimeout(() => {
      setIntakeReviewStatus("Jarvis is still shaping the profile. The current model path can take a bit longer when it is under load.", "neutral");
  }, 15000);
  const progressNote2 = setTimeout(() => {
      setIntakeReviewStatus("Still building the profile. Jarvis is waiting on the provider, not frozen.", "neutral");
  }, 32000);
  const progressNote3 = setTimeout(() => {
      setIntakeReviewStatus("Still building. Jarvis is keeping the synthesis request alive because the provider is slow, not because the workflow broke.", "neutral");
  }, 65000);
  
  try {
      const res = await fetch(buildApiUrl("/api/synthesize-client"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          signal: synthController.signal,
          body: JSON.stringify({
            client_name: name,
            raw_context: context,
            quick_intake: quickIntake,
            website_url: websiteUrl || undefined,
            social_url: socialUrl || undefined
          })
      });
      const data = await res.json();
      
      if(data.status === "success") {
          populateIntakeProfileForm(data.data || {});
          document.getElementById('c-json-preview').style.borderColor = "var(--green)";
          setIntakeReviewStatus("Structured profile extracted. Review the brand fields, then save live credentials for this client.", "success");
          setClientWizardStep(3, { scroll: true });
          showNotification(
            "Profile Built",
            "Jarvis successfully turned the quick setup and optional sources into a structured brand profile.",
            false,
            { accent: 'var(--green)', rgb: '31,206,160', duration: 5200, position: 'bottom-right' }
          );
      } else if (data.status === "missing") {
          populateIntakeProfileForm(data.data || {});
          showHUDError(data.missing_fields);
          document.getElementById('c-json-preview').style.borderColor = "var(--amber)";
          setIntakeReviewStatus("Jarvis extracted a usable first-pass profile. Fill the highlighted missing brand intelligence before saving.", "warning");
          setClientWizardStep(3, { scroll: true });
          showNotification(
            "Profile Needs Review",
            "Jarvis extracted the profile but still needs a few missing brand details before this client can be saved.",
            false,
            { accent: 'var(--amber)', rgb: '244,211,138', duration: 6200, position: 'bottom-right' }
          );
      } else {
          setIntakeReviewStatus(data.reason || "Jarvis could not build a valid brand profile from this brief.", "error");
          showNotification("Analysis Failed", data.reason || "Jarvis could not return a valid structured profile from this brief.", true, { position: 'bottom-right' });
      }
  } catch(e) {
      if (e && e.name === "AbortError") {
          setIntakeReviewStatus("Jarvis stopped the profile build because the current synthesis path took too long. Try again or simplify the intake details.", "error");
          showNotification("Build Timed Out", "Jarvis stopped waiting for the profile build because the provider took too long.", true, { position: 'bottom-right' });
      } else {
          setIntakeReviewStatus("Jarvis could not reach the synthesis backend.", "error");
          showNotification("Connection Failed", "Jarvis could not reach the FastAPI backend.", true, { position: 'bottom-right' });
      }
  } finally {
      clearTimeout(synthAbortTimer);
      clearTimeout(progressNote1);
      clearTimeout(progressNote2);
      clearTimeout(progressNote3);
      setSynthesizeButtonState(false);
  }
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
      setClientWizardStep(3, { scroll: true });
      return showNotification("Missing Details", `Jarvis cannot save this client yet. You are missing: <strong style="color:var(--t1)">${missing.join(', ')}</strong>`, true, { position: 'bottom-right' });
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
              setClientWizardStep(3, { scroll: true });
          } else {
              showNotification("Client Save Rejected", saveData.reason || 'Client profile is missing critical brand intelligence.', true, { position: 'bottom-right' });
          }
          btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Save Client`;
          return;
      }
        setIntakeReviewStatus("Client profile locked in. This account is ready for vaulting, drafting, and publishing.", "success");
	        showNotification(
	          "Client Saved",
	          `${cid} is now stored with its synthesized profile and live credentials. Opening Work...`,
	          false,
	          { accent: INTAKE_CRYSTAL, rgb: INTAKE_CRYSTAL_RGB, messageColor: INTAKE_CRYSTAL_SOFT, duration: 9800, position: 'bottom-right' }
	        );
	        if(!globalClients.includes(cid)) globalClients.push(cid);
	        upsertClientWorkspaceData(saveData.client || payload);
	        clientVaultCounts[cid] = Number(clientVaultCounts[cid] || 0);
	        populatePipelineSelectors(globalClients);
	        const liveSelect = document.getElementById('tclient');
	        if(liveSelect) liveSelect.value = cid;
	        document.getElementById('c-json-preview').style.borderColor = "var(--purple)";
	        try{ renderDashboardSummary(); } catch(e){}
	        try{ await refreshClientWorkspaceViews(); } catch(e){}
	        nav('dashboard', document.getElementById('nav-dashboard'));
	        returnViewportToTop();
	        resetClientIntakeForm();
  } catch(e) { showNotification("Save Failed", "Jarvis could not write this client profile to the backend.", true, { position: 'bottom-right' }); }
  
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Save Client`;
}

function returnViewportToTop() {
  const topTarget = document.querySelector('.main') || document.querySelector('.shell') || document.body;
  try {
    topTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch(e) {}
  try {
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
  } catch(e) {
    window.scrollTo(0, 0);
  }
  try {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  } catch(e) {}
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
let orchestratorComposerSelections = [];
let currentOrchMentionContext = null;
let lastImmediatePublishPrompt = "";
const ORCH_LAST_PROMPT_STORAGE_KEY = 'jarvisLastOrchestratorPrompt';
const ORCH_LAST_PROMPT_REFS_STORAGE_KEY = 'jarvisLastOrchestratorPromptRefs';
let lastOrchestratorPrompt = '';
let lastOrchestratorPromptRefs = [];
let orchestratorMissionPlan = null;
let orchestratorMissionRunId = localStorage.getItem('jarvisMissionRunId') || '';
let orchestratorMissionRun = null;
let orchestratorMissionPollHandle = null;
let orchestratorMissionLastFinalizedRunId = '';
let orchestratorMissionSeenItemStates = {};
let orchestratorMissionRunRenderSignature = '';
const ORCHESTRATOR_RUN_STATUS_BUBBLE_ID = 'orch-run-status-bubble';
const approvalCenterCache = {};
const LEGACY_SMART_DRAFT_RE = /@\[(?<client>[^\]]+)\]\s+draft_id:"(?<draftId>[^"]+)"(?:\s+draft:"(?<draftName>[^"]+)")?\s*/gi;
const JARVIS_DRAFT_SEPARATOR = '·';
const JARVIS_DRAFT_SEPARATOR_PATTERN = '(?:\\u00B7|Â·)';

function resolveMentionClient(rawClient) {
    const cleaned = String(rawClient || '').trim();
    if(!cleaned) return '';
    const exact = globalClients.find(c => c.toLowerCase() === cleaned.toLowerCase());
    return exact || cleaned;
}

function normalizeWorkspaceClientKey(value) {
    return String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '');
}

function resolveWorkspaceClientId(rawClient) {
    const cleaned = String(rawClient || '').trim();
    if(!cleaned) return '';
    const exact = resolveMentionClient(cleaned);
    if(exact && exact !== cleaned) return exact;
    const normalized = normalizeWorkspaceClientKey(cleaned);
    const pools = [
        ...(Array.isArray(globalClients) ? globalClients : []),
        ...Object.keys(clientWorkspaceDataCache || {}),
        ...Object.keys(clientVaultCounts || {}),
    ];
    const seen = new Set();
    for(const candidate of pools) {
        const key = String(candidate || '').trim();
        if(!key || seen.has(key)) continue;
        seen.add(key);
        if(normalizeWorkspaceClientKey(key) === normalized) return key;
    }
    return exact || cleaned;
}

function hydrateOrchestratorHelperNote() {
    const host = document.querySelector('#p-orchestrator .orch-helper-note');
    if(!host) return;
    host.innerHTML = `
      <span>Use one clause per release task, then separate the next task with a comma or “and also”.</span>
      <span>@ selects client ${JARVIS_DRAFT_SEPARATOR} . selects draft ${JARVIS_DRAFT_SEPARATOR} add time for schedules ${JARVIS_DRAFT_SEPARATOR} say "run it" after preview.</span>
    `;
}

hydrateOrchestratorHelperNote();

function hydrateOrchestratorWorkspaceChrome() {
    const pageSub = document.querySelector('#p-orchestrator .page-sub');
    if(pageSub) pageSub.innerHTML = 'The live command surface for immediate posting, approvals, and scheduled launches. Mount the client, state the intent, and let Jarvis prepare the exact execution path.';

    const title = document.querySelector('#p-orchestrator .orch-workspace-title');
    if(title) title.textContent = 'Command the release desk.';

    const copy = document.querySelector('#p-orchestrator .orch-workspace-copy');
    if(copy) copy.textContent = 'Write the release once. Jarvis resolves the draft, checks readiness, and lays out the exact next move before anything goes live.';

    const selectedText = document.querySelector('#p-orchestrator .orch-selected-text');
    if(selectedText) selectedText.textContent = 'Mounted drafts stay here as quiet context while the chat stays primary.';

    const supportMeta = document.querySelector('#orch-support-drawer .orch-panel-meta');
    if(supportMeta) supportMeta.textContent = 'Open this only when you want manual overrides or quiet draft loading.';

    const intro = document.querySelector('#orch-chat .chat-msg .ai-bubble');
    if(intro) {
        intro.innerHTML = `Write the release in one line. Example: <strong style="color:var(--t1);">post @Northline_Dental . Whitening Launch now, and also post @Cedar_Atelier . Studio Reel tonight at 8:00 PM</strong>. Jarvis will resolve the path, flag risks, and wait for your approval before execution.`;
    }

    const supportBody = document.querySelector('#orch-support-drawer .orch-support-body');
    const helperNote = document.querySelector('#orch-support-drawer .orch-helper-note');
    let planHost = document.getElementById('mission-control-plan');
    if(!planHost && supportBody) {
        planHost = document.createElement('div');
        planHost.id = 'mission-control-plan';
        planHost.style.minHeight = '120px';
        planHost.style.border = '1px solid rgba(255,255,255,.06)';
        planHost.style.borderRadius = '16px';
        planHost.style.background = 'rgba(255,255,255,.02)';
        planHost.style.padding = '14px';
        planHost.style.marginTop = '14px';
        supportBody.appendChild(planHost);
    } else if(planHost && supportBody && helperNote && planHost.parentElement !== supportBody) {
        planHost.style.minHeight = '120px';
        planHost.style.padding = '14px';
        planHost.style.marginTop = '14px';
        helperNote.insertAdjacentElement('afterend', planHost);
    }

    const detail = document.getElementById('orch-execution-details');
    const runHost = document.getElementById('mission-control-run');
    if(detail && runHost && !detail.querySelector('.orch-floating-head')) {
        const summary = detail.querySelector('summary') || document.createElement('summary');
        summary.textContent = 'Release timeline';
        const body = document.createElement('div');
        body.className = 'orch-floating-body';
        body.appendChild(runHost);

        const head = document.createElement('div');
        head.className = 'orch-floating-head';
        head.innerHTML = `
            <div>
                <div class="orch-floating-kicker">Live Supervision</div>
                <div class="orch-floating-title">Release timeline</div>
                <div class="orch-floating-copy">Keep this open only while Jarvis is posting, scheduling, or routing approvals.</div>
            </div>
            <button type="button" class="orch-floating-close" data-orch-action="close-supervision" aria-label="Close release timeline">&times;</button>
        `;

        detail.innerHTML = '';
        detail.appendChild(summary);
        detail.appendChild(head);
        detail.appendChild(body);
    }
}

hydrateOrchestratorWorkspaceChrome();

function buildVisibleDraftToken(clientName, draftName) {
    return `@[${String(clientName || '').trim()}] Draft ${JARVIS_DRAFT_SEPARATOR} ${String(draftName || '').trim()}`;
}

function renderOrchestratorComposerSelections() {
    const host = document.getElementById('orch-composer-selected');
    if(!host) return;
    if(!orchestratorComposerSelections.length) {
        host.innerHTML = `<div style="font-size:12px; color:var(--t4); padding:2px 0 0;">No drafts are mounted yet. Mention them inline with <strong style="color:var(--green);">@</strong> and <strong style="color:var(--purple);">.</strong>, or use the quiet loader below.</div>`;
        renderJarvisBatchSummary();
        return;
    }
    host.innerHTML = orchestratorComposerSelections.map((ref, index) => `
        <div style="display:inline-flex; align-items:center; gap:8px; padding:8px 10px; border-radius:999px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); max-width:100%;">
            <span style="font-size:12px; color:var(--green); font-weight:600;">@${escapeHtml(String(ref.client_id || ''))}</span>
            <span style="font-size:12px; color:var(--purple); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Draft ${JARVIS_DRAFT_SEPARATOR} ${escapeHtml(String(ref.draft_name || ''))}</span>
            <button type="button" onclick="removeOrchestratorComposerSelection(${index})" style="background:none; border:none; color:var(--t4); cursor:pointer; font-size:14px; line-height:1;">x</button>
        </div>
    `).join('');
    renderJarvisBatchSummary();
}

function normalizeRetryPromptRefs(refs = []) {
    return (Array.isArray(refs) ? refs : []).map(ref => {
        const clientName = resolveMentionClient(ref?.client_id);
        const draftName = String(ref?.draft_name || '').trim();
        const draftId = String(ref?.draft_id || '').trim();
        if(!clientName || !draftName) return null;
        return {
            client_id: clientName,
            draft_name: draftName,
            draft_id: draftId,
            visible_token: buildVisibleDraftToken(clientName, draftName),
        };
    }).filter(Boolean);
}

function updateRetryPromptButton() {
    const btn = document.getElementById('orch-retry-last-btn');
    const copy = document.getElementById('orch-retry-last-copy');
    const hasPrompt = !!String(lastOrchestratorPrompt || '').trim();
    if(btn) {
        btn.disabled = !hasPrompt;
        btn.textContent = hasPrompt ? 'Retry last prompt' : 'No saved prompt yet';
    }
    if(copy) {
        copy.textContent = hasPrompt
            ? `Restores your last exact Jarvis command${lastOrchestratorPromptRefs.length ? ` with ${lastOrchestratorPromptRefs.length} mounted draft${lastOrchestratorPromptRefs.length === 1 ? '' : 's'}` : ''}.`
            : 'Restores your exact last Jarvis command after refresh or token repair.';
    }
}

function loadLastOrchestratorPrompt() {
    try {
        lastOrchestratorPrompt = String(localStorage.getItem(ORCH_LAST_PROMPT_STORAGE_KEY) || '').trim();
        const rawRefs = JSON.parse(localStorage.getItem(ORCH_LAST_PROMPT_REFS_STORAGE_KEY) || '[]');
        lastOrchestratorPromptRefs = normalizeRetryPromptRefs(rawRefs);
    } catch(_e) {
        lastOrchestratorPrompt = '';
        lastOrchestratorPromptRefs = [];
    }
    updateRetryPromptButton();
}

function saveLastOrchestratorPrompt(prompt, refs = []) {
    lastOrchestratorPrompt = String(prompt || '').trim();
    lastOrchestratorPromptRefs = normalizeRetryPromptRefs(refs);
    try {
        if(lastOrchestratorPrompt) localStorage.setItem(ORCH_LAST_PROMPT_STORAGE_KEY, lastOrchestratorPrompt);
        else localStorage.removeItem(ORCH_LAST_PROMPT_STORAGE_KEY);
        if(lastOrchestratorPromptRefs.length) localStorage.setItem(ORCH_LAST_PROMPT_REFS_STORAGE_KEY, JSON.stringify(lastOrchestratorPromptRefs));
        else localStorage.removeItem(ORCH_LAST_PROMPT_REFS_STORAGE_KEY);
    } catch(_e) {}
    updateRetryPromptButton();
}

function restoreLastOrchestratorPrompt() {
    if(!String(lastOrchestratorPrompt || '').trim()) return false;
    orchInput.value = lastOrchestratorPrompt;
    currentOrchDraftRefs = normalizeRetryPromptRefs(lastOrchestratorPromptRefs);
    orchestratorComposerSelections = currentOrchDraftRefs.map(ref => ({ ...ref }));
    clearMissionControlPlan();
    renderOrchestratorComposerSelections();
    orchInput.style.height = 'auto';
    orchInput.style.height = (orchInput.scrollHeight > 200 ? 200 : orchInput.scrollHeight) + 'px';
    orchInput.focus();
    orchInput.selectionStart = orchInput.value.length;
    orchInput.selectionEnd = orchInput.value.length;
    return true;
}

function getOrchestratorClauseStartIndex(text) {
    const source = String(text || '');
    let start = 0;
    const patterns = [/,\s*/g, /;\s*/g, /\band also\b\s*/gi, /\band then\b\s*/gi, /\n+/g];
    patterns.forEach((pattern) => {
        pattern.lastIndex = 0;
        let match;
        while((match = pattern.exec(source)) !== null) {
            const candidate = match.index + match[0].length;
            if(candidate > start) start = candidate;
        }
    });
    return start;
}

function getCurrentOrchestratorMentionContext(value, cursorPos) {
    const source = String(value || '');
    const caret = Math.max(0, Number(cursorPos || 0));
    const beforeCursor = source.slice(0, caret);
    const clauseStart = getOrchestratorClauseStartIndex(beforeCursor);
    const clauseText = beforeCursor.slice(clauseStart);
    const atMatch = clauseText.match(/@([A-Za-z0-9_-]*)$/);
    if(atMatch) {
        return {
            mode: 'client',
            query: String(atMatch[1] || '').toLowerCase(),
            replaceStart: clauseStart + atMatch.index,
            replaceEnd: caret,
            client: '',
        };
    }

    const bracketPattern = /@\[(?<client>[^\]]+)\]/g;
    const rawPattern = /(?<!\[)@(?<client>[A-Za-z0-9_-]+)/g;
    const candidates = [];
    for(const match of clauseText.matchAll(bracketPattern)) {
        candidates.push({
            client: String(match.groups?.client || '').trim(),
            index: match.index,
            tokenLength: String(match[0] || '').length,
        });
    }
    for(const match of clauseText.matchAll(rawPattern)) {
        candidates.push({
            client: String(match.groups?.client || '').trim(),
            index: match.index,
            tokenLength: String(match[0] || '').length,
        });
    }
    if(!candidates.length) return null;
    candidates.sort((a, b) => a.index - b.index);
    const lastClient = candidates.at(-1);
    if(!lastClient) return null;

    const clientLabel = resolveMentionClient(String(lastClient.client || '').trim());
    const afterClient = clauseText.slice(lastClient.index + lastClient.tokenLength);
    const dotMatch = afterClient.match(/^\s*\.\s*([^@,\n;]*)$/);
    if(!dotMatch) return null;

    return {
        mode: 'draft',
        query: String(dotMatch[1] || '').trim().toLowerCase(),
        replaceStart: clauseStart + lastClient.index,
        replaceEnd: caret,
        client: clientLabel,
    };
}

function normalizeJarvisDraftSeparator(text) {
    return String(text || '').replace(/Draft\s+\u00B7/g, `Draft ${JARVIS_DRAFT_SEPARATOR}`);
}

function finalizeJarvisUserBubbleText(text, outgoingDraftRefs = []) {
    let rendered = normalizeJarvisDraftSeparator(text);
    outgoingDraftRefs.forEach(ref => {
        const clientName = String(ref?.client_id || '').trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const draftName = String(ref?.draft_name || '').trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        if(!clientName || !draftName) return;
        const visibleDraftRe = new RegExp(`(<span[^>]*>@${clientName}</span>)\\s+Draft\\s+\\u00B7\\s+${draftName}`, 'i');
        rendered = rendered.replace(
            visibleDraftRe,
            `$1 <span style="background:rgba(139,108,247,.14); color:var(--purple); padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">Draft ${JARVIS_DRAFT_SEPARATOR} ${String(ref?.draft_name || '').trim()}</span>`
        );
    });
    return rendered;
}

function renderJarvisBatchSummary() {
    const host = document.getElementById('orch-batch-summary');
    if(!host) return;
    if(orchestratorMissionRun) {
        host.textContent = `Run: ${String(orchestratorMissionRun.status || 'queued').replace(/_/g, ' ')}`;
        host.style.color = 'var(--green)';
        host.style.borderColor = 'rgba(31,206,160,.18)';
        host.style.background = 'rgba(31,206,160,.08)';
        return;
    }
    if(orchestratorMissionPlan) {
        const ready = Number(orchestratorMissionPlan?.totals?.ready || 0);
        const total = Number(orchestratorMissionPlan?.totals?.total || 0);
        const planAction = String(orchestratorMissionPlan.action || '').replace(/_/g, ' ');
        host.textContent = planAction === 'mixed' ? `${ready}/${total} release tasks ready` : `${ready}/${total} ready for ${planAction}`;
        host.style.color = orchestratorMissionPlan.can_run ? 'var(--blue)' : 'var(--amber)';
        host.style.borderColor = orchestratorMissionPlan.can_run ? 'rgba(47,168,224,.18)' : 'rgba(224,168,47,.18)';
        host.style.background = orchestratorMissionPlan.can_run ? 'rgba(47,168,224,.08)' : 'rgba(224,168,47,.08)';
        return;
    }
    if(orchestratorComposerSelections.length) {
        host.textContent = `${orchestratorComposerSelections.length} draft${orchestratorComposerSelections.length === 1 ? '' : 's'} loaded`;
        host.style.color = 'var(--t3)';
        host.style.borderColor = 'rgba(255,255,255,.08)';
        host.style.background = 'rgba(255,255,255,.03)';
        return;
    }
    host.textContent = 'No drafts loaded';
    host.style.color = 'var(--t4)';
    host.style.borderColor = 'rgba(255,255,255,.08)';
    host.style.background = 'rgba(255,255,255,.03)';
}

function removeOrchestratorComposerSelection(index) {
    orchestratorComposerSelections.splice(index, 1);
    clearMissionControlPlan();
    renderOrchestratorComposerSelections();
}

function clearOrchestratorComposerSelections() {
    orchestratorComposerSelections = [];
    clearMissionControlPlan();
    renderOrchestratorComposerSelections();
}

async function populateOrchestratorComposerClients() {
    const select = document.getElementById('orch-composer-client');
    if(!select) return;
    const currentValue = select.value;
    const clients = [...globalClients].sort((a, b) => a.localeCompare(b));
    select.innerHTML = `<option value="">Select client</option>` + clients.map(client => `<option value="${escapeHtml(client)}">${escapeHtml(client)}</option>`).join('');
    if(currentValue && clients.includes(currentValue)) {
        select.value = currentValue;
    }
}

async function handleOrchestratorComposerClientChange() {
    const clientSelect = document.getElementById('orch-composer-client');
    const draftSelect = document.getElementById('orch-composer-draft');
    if(!clientSelect || !draftSelect) return;
    const clientName = resolveMentionClient(clientSelect.value);
    draftSelect.innerHTML = `<option value="">Loading drafts...</option>`;
    if(!clientName) {
        draftSelect.innerHTML = `<option value="">Select draft</option>`;
        return;
    }
    const drafts = await loadDraftMentions(clientName);
    draftSelect.innerHTML = `<option value="">Select draft</option>` + drafts.map(draft => `
        <option value="${escapeHtml(String(draft.id || ''))}" data-draft-name="${escapeHtml(draft.name)}">
            ${escapeHtml(draft.name)}
        </option>
    `).join('');
}

function addOrchestratorComposerSelection() {
    const clientSelect = document.getElementById('orch-composer-client');
    const draftSelect = document.getElementById('orch-composer-draft');
    if(!clientSelect || !draftSelect) return;
    const clientName = resolveMentionClient(clientSelect.value);
    const draftId = String(draftSelect.value || '').trim();
    const selectedOption = draftSelect.options[draftSelect.selectedIndex];
    const draftName = String(selectedOption?.dataset?.draftName || selectedOption?.text || '').trim();
    if(!clientName || !draftName) {
        toast('Select a client and draft first.', 'warn');
        return;
    }
    if(addDraftToJarvisSelection({ client_id: clientName, draft_name: draftName, draft_id: draftId })) {
        toast(`${draftName} loaded into Jarvis.`, 'success');
    }
}

function composeSelectedDraftBatch(mode = 'post_now') {
    if(!orchestratorComposerSelections.length) {
        toast('Add at least one draft to the batch first.', 'warn');
        return;
    }
    const refs = orchestratorComposerSelections.map(ref => ({
        client_id: resolveMentionClient(ref.client_id),
        draft_name: String(ref.draft_name || '').trim(),
        draft_id: String(ref.draft_id || '').trim(),
        visible_token: buildVisibleDraftToken(resolveMentionClient(ref.client_id), ref.draft_name),
    }));
    const tokens = refs.map(ref => ref.visible_token);
    let command = '';
    if(mode === 'approval') {
        command = `Hey Jarvis, send ${tokens.join(', ')} for approval.`;
    } else {
        command = `Hey Jarvis, post ${tokens.join(', ')} now.`;
    }
    orchInput.value = command;
    currentOrchDraftRefs = refs;
    orchInput.style.height = 'auto';
    orchInput.style.height = (orchInput.scrollHeight > 200 ? 200 : orchInput.scrollHeight) + 'px';
    orchInput.focus();
    orchInput.selectionStart = orchInput.value.length;
    orchInput.selectionEnd = orchInput.value.length;
}


function getMissionControlAction() {
    return String(document.getElementById('mission-control-action')?.value || 'post_now').trim();
}

function getMissionControlSchedulePayload() {
    return {
        scheduled_date: String(document.getElementById('mission-control-date')?.value || '').trim(),
        time: String(document.getElementById('mission-control-time')?.value || '').trim(),
    };
}

function syncMissionControlActionUI() {
    const disabled = getMissionControlAction() === 'post_now';
    const wrap = document.getElementById('mission-control-schedule');
    const whatsappBtn = document.getElementById('mission-control-whatsapp-btn');
    if(wrap) {
        wrap.style.opacity = disabled ? '.55' : '1';
        wrap.style.pointerEvents = disabled ? 'none' : 'auto';
    }
    if(whatsappBtn) {
        whatsappBtn.style.display = getMissionControlAction() === 'send_for_approval' ? 'inline-flex' : 'none';
    }
}

function clearMissionControlPlan() {
    orchestratorMissionPlan = null;
    renderMissionControlPlanCard();
    renderJarvisBatchSummary();
}

function persistMissionControlRunId(runId) {
    orchestratorMissionRunId = String(runId || '').trim();
    if(orchestratorMissionRunId) localStorage.setItem('jarvisMissionRunId', orchestratorMissionRunId);
    else localStorage.removeItem('jarvisMissionRunId');
}

function clearMissionControlRun() {
    orchestratorMissionRun = null;
    if(orchestratorMissionPollHandle) clearInterval(orchestratorMissionPollHandle);
    orchestratorMissionPollHandle = null;
    orchestratorMissionSeenItemStates = {};
    orchestratorMissionRunRenderSignature = '';
    persistMissionControlRunId('');
    renderMissionControlRunTimeline();
    renderJarvisBatchSummary();
}

function getMissionControlItemStateKey(item = {}, index = 0) {
    return String(item?.draft_id || item?.job_id || item?.approval_id || `${item?.client_id || 'client'}::${item?.draft_name || 'draft'}::${index}`);
}

function describeMissionControlItemOutcome(item = {}) {
    const action = String(item?.action || '').trim().toLowerCase();
    const summary = escapeHtml(String(item?.summary || `${item?.client_id || 'Client'} · ${item?.draft_name || 'Draft'}`));
    const message = escapeHtml(String(item?.message || ''));
    const status = String(item?.status || '').trim().toLowerCase();
    if(action === 'post_now') {
        return `<strong style="color:var(--green);">${summary}</strong><br/>${message || 'Post completed.'}`;
    }
    if(action === 'send_for_approval') {
        const raw = item?.result && typeof item.result === 'object' ? item.result : {};
        const approvalAction = {
            type: 'approval_request',
            approval_id: raw?.approval_id || '',
            job: raw?.job || null,
            message: item?.message || 'Approval prepared.',
        };
        if(approvalAction.approval_id && approvalAction.job) {
            return renderOrchestratorApprovalCard(item?.message || 'Approval prepared.', approvalAction);
        }
        return `<strong style="color:${status === 'approval_sent_whatsapp' ? 'var(--green)' : 'var(--t1)'};">${summary}</strong><br/>${message || 'Approval prepared.'}`;
    }
    return `<strong style="color:var(--blue);">${summary}</strong><br/>${message || 'Scheduled successfully.'}`;
}

function appendJarvisBubbleShell(options = {}) {
    const chat = document.getElementById('orch-chat');
    if(!chat) return null;
    const bubbleId = String(options.bubbleId || `jarvis-bubble-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    const bubbleClass = String(options.bubbleClass || 'ai-bubble').trim();
    const bubbleStyle = String(options.bubbleStyle || '').trim();
    const label = escapeHtml(String(options.label || 'Jarvis'));
    const accent = escapeHtml(String(options.accent || 'var(--purple)'));
    chat.insertAdjacentHTML('beforeend', `
      <div class="chat-msg" style="display:flex; gap:14px; align-items:flex-start;">
        <div class="jarvis-avatar" style="width:46px; height:46px; border-radius:16px; box-shadow:none;">
          <span style="font-family:'Space Mono', monospace; font-size:14px; font-weight:700; color:rgba(214,203,255,.96); letter-spacing:.12em;">J</span>
        </div>
        <div style="min-width:0; flex:1 1 auto;">
          <div style="font-size:12px; font-weight:700; color:${accent}; margin-bottom:6px; text-transform:uppercase; letter-spacing:.14em;">${label}</div>
          <div id="${bubbleId}" class="${bubbleClass}"${bubbleStyle ? ` style="${bubbleStyle}"` : ''}></div>
        </div>
      </div>`);
    chat.scrollTop = chat.scrollHeight;
    return document.getElementById(bubbleId);
}

function buildMissionControlPublishPayload(item = {}) {
    const raw = item?.result && typeof item.result === 'object' ? item.result : {};
    const candidateTexts = [
        String(item?.message || '').trim(),
        String(raw?.message || '').trim(),
        String(raw?.output || '').trim().replace(/\s+/g, ' '),
    ].filter(Boolean);
    for(const text of candidateTexts) {
        const parsed = parsePublishSuccessReply(text);
        if(parsed) return parsed;
    }
    const clientId = resolveWorkspaceClientId(item?.client_id || '') || String(item?.client_id || '').trim();
    if(!clientId) return null;
    return {
        clientId,
        platforms: [],
        raw: candidateTexts[0] || '',
    };
}

function buildMissionControlPublishRefs(item = {}) {
    const clientId = resolveWorkspaceClientId(item?.client_id || '');
    const refs = [];
    if(clientId) {
        refs.push({
            client_id: clientId,
            draft_name: String(item?.draft_name || '').trim(),
            draft_id: String(item?.draft_id || '').trim(),
        });
    }
    const raw = item?.result && typeof item.result === 'object' ? item.result : {};
    if(Array.isArray(raw?.draft_refs)) {
        raw.draft_refs.forEach(ref => {
            const refClientId = resolveWorkspaceClientId(ref?.client_id || clientId || '');
            if(!refClientId) return;
            refs.push({
                client_id: refClientId,
                draft_name: String(ref?.draft_name || item?.draft_name || '').trim(),
                draft_id: String(ref?.draft_id || item?.draft_id || '').trim(),
            });
        });
    }
    return refs.filter(ref => String(ref?.client_id || '').trim());
}

function appendMissionControlOutcomeBubble(item = {}) {
    const action = String(item?.action || '').trim().toLowerCase();
    const status = String(item?.status || '').trim().toLowerCase();
    if(action === 'post_now' && status === 'published') {
        const payload = buildMissionControlPublishPayload(item);
        if(!payload) {
            appendJarvisSystemBubble(describeMissionControlItemOutcome(item));
            return;
        }
        const bubble = appendJarvisBubbleShell({
            bubbleClass: 'msg-content ai-success-card',
            label: 'Jarvis',
            accent: 'var(--purple)',
        });
        if(!bubble) return;
        bubble.innerHTML = renderPublishSuccessCard(payload, null);
        const refs = buildMissionControlPublishRefs(item);
        resolvePublishSuccessMedia(refs)
            .then(media => {
                if(bubble.isConnected) bubble.innerHTML = renderPublishSuccessCard(payload, media);
            })
            .catch(() => null);
        return;
    }
    appendJarvisSystemBubble(describeMissionControlItemOutcome(item));
}

function announceMissionControlItemTransitions(previousRun = null, nextRun = null) {
    const nextItems = Array.isArray(nextRun?.items) ? nextRun.items : [];
    nextItems.forEach((item, index) => {
        const stateKey = getMissionControlItemStateKey(item, index);
        const previousState = orchestratorMissionSeenItemStates[stateKey];
        const nextState = String(item?.status || '').trim().toLowerCase();
        orchestratorMissionSeenItemStates[stateKey] = nextState;
        if(!nextState || previousState === nextState) return;
        if(!['published','scheduled','approval_ready','approval_sent_whatsapp','completed','partial_success','failed'].includes(nextState)) return;
        appendMissionControlOutcomeBubble(item);
    });
}

function setMissionControlButtonState(buttonId, label, disabled) {
    const btn = document.getElementById(buttonId);
    if(!btn) return;
    btn.textContent = label;
    btn.disabled = !!disabled;
    btn.style.opacity = disabled ? '.72' : '1';
    btn.style.cursor = disabled ? 'default' : 'pointer';
}

function appendJarvisSystemBubble(html) {
    const bubble = appendJarvisBubbleShell({
        bubbleClass: 'ai-bubble',
        bubbleStyle: 'background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.06); border-radius:18px; box-shadow:none; padding:16px 18px;',
        label: 'Jarvis',
        accent: 'var(--purple)',
    });
    if(bubble) bubble.innerHTML = html;
}

function upsertJarvisSystemBubble(bubbleId, html) {
    const chat = document.getElementById('orch-chat');
    if(!chat) return;
    let bubble = document.getElementById(bubbleId);
    if(!bubble) {
        chat.insertAdjacentHTML('beforeend', `
          <div class="chat-msg" style="display:flex; gap:14px; align-items:flex-start;">
            <div class="jarvis-avatar" style="width:46px; height:46px; border-radius:16px; box-shadow:none;">
              <span style="font-family:'Space Mono', monospace; font-size:14px; font-weight:700; color:rgba(214,203,255,.96); letter-spacing:.12em;">J</span>
            </div>
            <div style="min-width:0;">
              <div style="font-size:12px; font-weight:700; color:var(--purple); margin-bottom:6px; text-transform:uppercase; letter-spacing:.14em;">Jarvis</div>
              <div id="${bubbleId}" class="ai-bubble" style="background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.06); border-radius:18px; box-shadow:none; padding:16px 18px;"></div>
            </div>
          </div>`);
        bubble = document.getElementById(bubbleId);
    }
    if(bubble) bubble.innerHTML = html;
    chat.scrollTop = chat.scrollHeight;
}

function getMissionControlRunCounts(run = {}) {
    const items = Array.isArray(run?.items) ? run.items : [];
    const rawCounts = items.reduce((acc, item) => {
        const key = String(item?.status || '').trim().toLowerCase() || 'queued';
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    const totals = (run && typeof run === 'object' && run.totals && typeof run.totals === 'object') ? run.totals : {};
    return {
        queued: Math.max(
            Number(rawCounts.queued || 0),
            Number(rawCounts.preflight || 0) + Number(rawCounts.publishing || 0),
            Number(totals.queued || 0) + Number(totals.preflight || 0) + Number(totals.publishing || 0)
        ),
        preflight: Math.max(Number(rawCounts.preflight || 0), Number(totals.preflight || 0)),
        publishing: Math.max(Number(rawCounts.publishing || 0), Number(totals.publishing || 0)),
        posted: Math.max(Number(rawCounts.published || 0), Number(totals.published || 0)),
        scheduled: Math.max(Number(rawCounts.scheduled || 0), Number(totals.scheduled_complete || 0)),
        approvals: Math.max(
            Number(rawCounts.approval_ready || 0) + Number(rawCounts.approval_sent_whatsapp || 0),
            Number(totals.approval_ready || 0) + Number(totals.approval_sent_whatsapp || 0)
        ),
        failed: Math.max(Number(rawCounts.failed || 0), Number(totals.failed || 0)),
        partial: Number(rawCounts.partial_success || 0),
        completed: Number(rawCounts.completed || 0),
    };
}

function getMissionControlRunSummary(run = {}) {
    const counts = getMissionControlRunCounts(run);
    const parts = [];
    if(counts.posted) parts.push(`posted <strong style="color:var(--green);">${counts.posted}</strong>`);
    if(counts.scheduled) parts.push(`scheduled <strong style="color:var(--blue);">${counts.scheduled}</strong>`);
    if(counts.approvals) parts.push(`approval-ready <strong style="color:var(--purple);">${counts.approvals}</strong>`);
    if(counts.publishing) parts.push(`publishing <strong style="color:var(--green);">${counts.publishing}</strong>`);
    if(counts.preflight) parts.push(`checking <strong style="color:var(--blue);">${counts.preflight}</strong>`);
    if(counts.failed) parts.push(`failed <strong style="color:var(--red);">${counts.failed}</strong>`);
    if(!parts.length && counts.queued) parts.push(`queued <strong style="color:var(--t3);">${counts.queued}</strong>`);
    return parts.join(', ');
}

function renderMissionControlRunStatusCard(run = {}) {
    const items = Array.isArray(run?.items) ? run.items : [];
    const counts = getMissionControlRunCounts(run);
    const summary = getMissionControlRunSummary(run);
    const normalizedRunStatus = String(run?.status || 'starting').trim().toLowerCase();
    const runStatus = escapeHtml(normalizedRunStatus.replace(/_/g, ' '));
    const firstFailedItem = items.find(item => String(item?.status || '').trim().toLowerCase() === 'failed');
    const rawDetail = String(run?.start_error || firstFailedItem?.message || '').trim();
    const escapedDetail = rawDetail ? escapeHtml(rawDetail) : '';
    let headline = 'Jarvis is preparing the release.';
    let detail = summary ? `Current progress: ${summary}.` : 'Jarvis is preparing the release.';
    if(normalizedRunStatus === 'start_failed') {
        headline = 'Jarvis could not confirm the release start.';
        detail = escapedDetail || 'The server did not acknowledge the release start in time. Nothing was marked as published from this timeout alone.';
    } else if(normalizedRunStatus === 'failed') {
        headline = counts.failed === 1 ? '1 release item failed.' : `${counts.failed} release items failed.`;
        detail = escapedDetail || (summary ? `Completed before failure: ${summary}.` : 'Jarvis stopped before any item reached a final success state.');
    } else if(normalizedRunStatus === 'partial_success') {
        headline = 'Jarvis finished part of the release.';
        detail = summary ? `Final result: ${summary}.` : 'Some items completed, but at least one item needs attention.';
        if(escapedDetail) detail += ` ${escapedDetail}`;
    } else if(normalizedRunStatus === 'completed') {
        headline = 'Jarvis completed the release.';
        detail = summary ? `Final result: ${summary}.` : 'Every item reached a final state.';
    }
    return `
      <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:14px; flex-wrap:wrap;">
        <div>
          <div style="font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--purple); font-weight:700; margin-bottom:8px;">Live release</div>
          <div style="font-size:14px; color:var(--t1); line-height:1.65;">${headline}</div>
          <div style="font-size:12px; color:var(--t3); margin-top:8px; line-height:1.6;">${detail}</div>
          <div style="font-size:12px; color:var(--t3); margin-top:8px;">State: ${runStatus}</div>
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">
          <span class="badge b-off">Queued ${counts.queued}</span>
          <span class="badge b-on">Posted ${counts.posted}</span>
          <span class="badge b-pu">Approvals ${counts.approvals}</span>
          <span class="badge b-am">Scheduled ${counts.scheduled}</span>
          <span class="badge b-re">Failed ${counts.failed}</span>
        </div>
      </div>`;
}

function getMissionControlRunRenderSignature(run = null) {
    if(!run) return 'empty';
    const items = Array.isArray(run?.items) ? run.items : [];
    return JSON.stringify({
        status: String(run?.status || ''),
        items: items.map((item, index) => ({
            i: index,
            summary: String(item?.summary || ''),
            status: String(item?.status || ''),
            phase: String(item?.phase || ''),
            message: String(item?.message || ''),
            approval_id: String(item?.approval_id || ''),
            job_id: String(item?.job_id || ''),
            whatsapp_sent: item?.whatsapp_sent === true,
        })),
    });
}

function refreshOrchestratorIntroCard() {
    const intro = document.querySelector('#orch-chat .chat-msg .ai-bubble');
    if(!intro) return;
    intro.innerHTML = `Write the release in one line. Example: <strong style="color:var(--t1);">post @Northline_Dental . Whitening Launch now, and also post @Cedar_Atelier . Studio Reel tonight at 8:00 PM</strong>.`;
}

function summarizeMissionControlPlan(plan) {
    const total = Number(plan?.totals?.total || 0);
    const ready = Number(plan?.totals?.ready || 0);
    const scheduled = Number(plan?.totals?.schedule || 0);
    const immediate = Number(plan?.totals?.post_now || 0);
    const blocked = (plan?.items || []).filter(item => String(item?.status || '').toLowerCase() === 'blocked');
    let html = `<strong style="color:var(--t1);">Command review ready.</strong><br/>I checked <strong style="color:var(--t1);">${ready}/${total}</strong> parsed release ${total === 1 ? 'task' : 'tasks'}.`;
    if(immediate || scheduled) {
        html += `<br/><span style="color:var(--t3);">${immediate ? `${immediate} now` : ''}${immediate && scheduled ? ' · ' : ''}${scheduled ? `${scheduled} scheduled` : ''}</span>`;
    }
    if(blocked.length) {
        html += `<br/><span style="color:var(--amber);">${blocked.length} clause${blocked.length === 1 ? ' is' : 's are'} blocked and must be fixed before I can run the release.</span>`;
    } else {
        html += `<br/><span style="color:var(--green);">The release set is ready. Say <strong>"run it"</strong> or press <strong>Start release</strong>.</span>`;
    }
    return html;
}

function summarizeMissionControlRun(run) {
    const items = Array.isArray(run?.items) ? run.items : [];
    const counts = items.reduce((acc, item) => {
        const key = String(item?.status || 'queued').toLowerCase();
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    const published = Number(counts.published || 0);
    const scheduled = Number(counts.scheduled || 0);
    const approvals = Number(counts.approval_ready || 0) + Number(counts.approval_sent_whatsapp || 0);
    const partial = Number(counts.partial_success || 0);
    const failed = Number(counts.failed || 0);
    return `<strong style="color:var(--t1);">Batch ${escapeHtml(String(run?.status || 'running').replace(/_/g, ' '))}.</strong><br/>Published: <strong style="color:var(--green);">${published}</strong> &nbsp; Scheduled: <strong style="color:var(--blue);">${scheduled}</strong> &nbsp; Approvals: <strong style="color:var(--purple);">${approvals}</strong> &nbsp; Partial: <strong style="color:var(--amber);">${partial}</strong> &nbsp; Failed: <strong style="color:var(--red);">${failed}</strong>`;
}

function renderJarvisPlanActions(plan) {
    if(!plan) return '';
    const canRun = !!plan.can_run;
    const items = Array.isArray(plan?.items) ? plan.items : [];
    const hasApprovalTasks = items.some(item => String(item?.action || '').trim().toLowerCase() === 'send_for_approval');
    return `
      <div class="orch-inline-actions">
        ${canRun ? `<button type="button" class="orch-inline-action-btn is-primary" data-orch-action="run-plan">Start release</button>` : ''}
        ${canRun && hasApprovalTasks ? `<button type="button" class="orch-inline-action-btn is-quiet" data-orch-action="run-plan-whatsapp">Route to WhatsApp</button>` : ''}
        <button type="button" class="orch-inline-action-btn is-quiet" data-orch-action="open-supervision">Open timeline</button>
        <button type="button" class="orch-inline-action-btn is-danger" data-orch-action="clear-loaded">Clear loaded</button>
      </div>`;
}

function toggleOrchestratorSupportDrawer(forceState = null) {
    const drawer = document.getElementById('orch-support-drawer');
    if(!drawer) return;
    drawer.open = typeof forceState === 'boolean' ? forceState : !drawer.open;
}

function openOrchestratorExecutionDetails(forceState = true) {
    const detail = document.getElementById('orch-execution-details');
    if(!detail) return;
    detail.open = typeof forceState === 'boolean' ? forceState : true;
    renderMissionControlRunTimeline();
    if(orchestratorMissionRunId) hydrateMissionControlRun(false);
    detail.classList.add('is-focused');
    setTimeout(() => detail.classList.remove('is-focused'), 1400);
}

function addDraftToJarvisSelection(ref) {
    const clientName = resolveMentionClient(ref?.client_id);
    const draftName = String(ref?.draft_name || '').trim();
    const draftId = String(ref?.draft_id || '').trim();
    if(!clientName || !draftName) return false;
    const exists = orchestratorComposerSelections.some(item => String(item.client_id).toLowerCase() === clientName.toLowerCase() && String(item.draft_name).toLowerCase() === draftName.toLowerCase());
    if(exists) { toast('That draft is already loaded into Jarvis.', 'warn'); return false; }
    orchestratorComposerSelections.push({ client_id: clientName, draft_name: draftName, draft_id: draftId, visible_token: buildVisibleDraftToken(clientName, draftName) });
    clearMissionControlPlan();
    renderOrchestratorComposerSelections();
    return true;
}

function addDraftToJarvisFromVault(draftName) {
    const bundle = currentVaultBundles?.[draftName] || {};
    if(addDraftToJarvisSelection({ client_id: currentVaultClient, draft_name: draftName, draft_id: String(bundle?.draft_id || '').trim() })) {
        toast(`${draftName} added to Jarvis.`, 'success');
    }
}

function renderMissionControlPlanCard() {
    const host = document.getElementById('mission-control-plan');
    if(!host) return;
    if(!orchestratorComposerSelections.length && !orchestratorMissionPlan) {
        host.innerHTML = `<div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--t4);font-family:'Space Mono';margin-bottom:10px;">Command Review</div><div style="font-size:14px;color:var(--t3);line-height:1.7;">Jarvis will place the parsed release clauses here before anything moves live.</div>`;
        renderJarvisBatchSummary();
        return;
    }
    if(!orchestratorMissionPlan) {
        host.innerHTML = `<div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--t4);font-family:'Space Mono';margin-bottom:10px;">Command Review</div><div style="font-size:13px;color:var(--t3);line-height:1.65;margin-bottom:12px;">Preview will validate the loaded drafts, confirm platform readiness, and stage Jarvis's execution order.</div><div style="display:flex;flex-direction:column;gap:8px;">${orchestratorComposerSelections.map((item, i) => `<div style="padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.02);font-size:13px;color:var(--t2);">${i + 1}. ${escapeHtml(String(item.client_id || ''))} - ${escapeHtml(String(item.draft_name || ''))}</div>`).join('')}</div>`;
        renderJarvisBatchSummary();
        return;
    }
    const warnings = Array.isArray(orchestratorMissionPlan.warnings) ? orchestratorMissionPlan.warnings : [];
    host.innerHTML = `<div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:10px;"><div><div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--t4);font-family:'Space Mono';">Command Review</div><div style="font-size:14px;color:var(--t2);margin-top:6px;">${escapeHtml(String(orchestratorMissionPlan.action || '').replace(/_/g, ' '))} · ${orchestratorMissionPlan.totals?.ready || 0}/${orchestratorMissionPlan.totals?.total || 0} ready</div></div><div style="font-size:11px;color:${orchestratorMissionPlan.can_run ? 'var(--green)' : 'var(--red)'};font-family:'Space Mono';text-transform:uppercase;">${orchestratorMissionPlan.can_run ? 'Ready' : 'Blocked'}</div></div><div style="font-size:12px;color:${orchestratorMissionPlan.can_run ? 'var(--green)' : 'var(--amber)'};line-height:1.6;margin-bottom:12px;">${orchestratorMissionPlan.can_run ? 'Jarvis can start this release now. Review the cards below first.' : 'Fix the blocked release cards before you start anything.'}</div>${warnings.length ? `<div style="margin-bottom:10px;padding:10px 12px;border-radius:12px;background:rgba(224,168,47,.08);border:1px solid rgba(224,168,47,.18);color:var(--amber);font-size:12px;line-height:1.6;">${warnings.map(escapeHtml).join('<br>')}</div>` : ''}<div style="display:flex;flex-direction:column;gap:8px;">${(orchestratorMissionPlan.items || []).map(item => { const status = String(item?.status || '').toLowerCase(); const warningBlock = item.warning ? `<div style="font-size:12px;color:${status === 'blocked' ? 'var(--red)' : 'var(--amber)'};margin-top:8px;line-height:1.6;">${escapeHtml(item.warning)}</div>` : ''; return `<div style="padding:12px 14px;border-radius:14px;border:1px solid rgba(255,255,255,.06);background:${status === 'blocked' ? 'rgba(224,85,85,.08)' : 'rgba(255,255,255,.02)'};"><div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;"><div><div style="font-size:13px;color:var(--t1);font-weight:600;">${escapeHtml(String(item.summary || 'Draft'))}</div><div style="font-size:12px;color:var(--t4);margin-top:4px;">${escapeHtml(String(item.platform_label || 'No platforms'))}</div></div><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end;"><span style="font-size:11px;color:${status === 'blocked' ? 'var(--red)' : 'var(--t3)'};font-family:'Space Mono';text-transform:uppercase;">${escapeHtml(status)}</span></div></div>${warningBlock}</div>`; }).join('')}</div>`;
    renderJarvisBatchSummary();
}

function renderMissionControlRunTimeline() {
    const host = document.getElementById('mission-control-run');
    if(!host) return;
    if(!orchestratorMissionRun) {
        orchestratorMissionRunRenderSignature = 'empty';
        host.innerHTML = `<div style="font-size:14px;color:var(--t2);line-height:1.7;">No active release yet.</div><div style="font-size:12px;color:var(--t4);line-height:1.6;margin-top:8px;">When you start a release, Jarvis will keep the live state here without pushing the whole page downward.</div>`;
        renderJarvisBatchSummary();
        return;
    }
    const nextSignature = getMissionControlRunRenderSignature(orchestratorMissionRun);
    if(nextSignature === orchestratorMissionRunRenderSignature) return;
    orchestratorMissionRunRenderSignature = nextSignature;
    host.innerHTML = `<div style="display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:12px;"><div style="font-size:14px;color:var(--t2);">${escapeHtml(String(orchestratorMissionRun.status || 'queued').replace(/_/g, ' '))}</div><button type="button" data-orch-action="dismiss-run" class="orch-inline-action-btn is-quiet" style="padding:8px 10px;min-width:auto;">Dismiss</button></div><div style="display:flex;flex-direction:column;gap:8px;">${(orchestratorMissionRun.items || []).map((item, i) => { const status = String(item.status || '').toLowerCase(); const tone = status === 'failed' ? 'var(--red)' : status === 'partial_success' ? 'var(--amber)' : status === 'scheduled' ? 'var(--blue)' : status === 'approval_ready' || status === 'approval_sent_whatsapp' ? 'var(--purple)' : 'var(--green)'; return `<div style="padding:10px 12px;border-radius:14px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.02);"><div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;"><div><div style="font-size:13px;color:var(--t1);">${i + 1}. ${escapeHtml(String(item.summary || 'Draft'))}</div><div style="font-size:12px;color:var(--t4);margin-top:4px;">${escapeHtml(String(item.phase || 'Queued'))}</div>${item.message ? `<div style="font-size:12px;color:var(--t3);margin-top:6px;line-height:1.6;">${escapeHtml(item.message)}</div>` : ''}</div><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;"><div style="font-size:11px;color:${tone};font-family:'Space Mono';text-transform:uppercase;">${escapeHtml(String(item.status || 'queued').replace(/_/g, ' '))}</div></div></div></div>`; }).join('')}</div>`;
    renderJarvisBatchSummary();
}

function applyJarvisBatchIntent(intent = {}, refs = []) {
    if(intent.action) {
        const actionSelect = document.getElementById('mission-control-action');
        if(actionSelect) actionSelect.value = intent.action;
    }
    if(intent.schedule?.scheduled_date) {
        const dateInput = document.getElementById('mission-control-date');
        if(dateInput) dateInput.value = intent.schedule.scheduled_date;
    }
    if(intent.schedule?.time) {
        const timeInput = document.getElementById('mission-control-time');
        if(timeInput) timeInput.value = intent.schedule.time;
    }
    if(Array.isArray(refs) && refs.length) {
        orchestratorComposerSelections = refs.map(ref => ({
            client_id: resolveMentionClient(ref.client_id),
            draft_name: String(ref.draft_name || '').trim(),
            draft_id: String(ref.draft_id || '').trim(),
            visible_token: buildVisibleDraftToken(resolveMentionClient(ref.client_id), ref.draft_name),
        }));
        renderOrchestratorComposerSelections();
    }
    syncMissionControlActionUI();
}

async function previewMissionControlPlan(options = {}) {
    if(!orchestratorComposerSelections.length) { toast('Load at least one draft into Jarvis first.', 'warn'); return null; }
    const action = String(options.actionOverride || getMissionControlAction()).trim();
    const items = Array.isArray(options.refsOverride) && options.refsOverride.length
        ? options.refsOverride.map(ref => ({ client_id: resolveMentionClient(ref.client_id), draft_name: String(ref.draft_name || '').trim(), draft_id: String(ref.draft_id || '').trim() || undefined }))
        : orchestratorComposerSelections.map(ref => ({ client_id: resolveMentionClient(ref.client_id), draft_name: String(ref.draft_name || '').trim(), draft_id: String(ref.draft_id || '').trim() || undefined }));
    const payload = { action, items };
    if(action !== 'post_now') payload.schedule = options.scheduleOverride || getMissionControlSchedulePayload();
    setMissionControlButtonState('mission-control-preview-btn', 'Previewing release...', true);
    try {
        const res = await fetch(buildApiUrl('/api/orchestrator/plan'), { method:'POST', headers:{ 'Content-Type':'application/json' }, body:JSON.stringify(payload) });
        const data = await res.json();
        if(!res.ok || data.status !== 'success') throw new Error(data.detail || data.reason || 'Failed to preview execution plan.');
        orchestratorMissionPlan = data.plan || null;
        renderMissionControlPlanCard();
        renderJarvisBatchSummary();
        if(options.forceOpenDetails) openOrchestratorExecutionDetails(true);
        else if(!orchestratorMissionPlan?.can_run) toggleOrchestratorSupportDrawer(true);
        if(options.appendChat !== false) {
            appendJarvisSystemBubble(`${summarizeMissionControlPlan(orchestratorMissionPlan || {})}${renderJarvisPlanActions(orchestratorMissionPlan || {})}`);
        }
        if(!options.silentToast) toast('Release preview ready.', 'success');
        return orchestratorMissionPlan;
    } catch(err) {
        if(!options.silentToast) toast(err?.message || 'Failed to preview the release.', 'error');
        return null;
    } finally { setMissionControlButtonState('mission-control-preview-btn', 'Preview release', false); }
}

function startMissionControlPolling() {
    if(orchestratorMissionPollHandle) clearInterval(orchestratorMissionPollHandle);
    orchestratorMissionPollHandle = setInterval(() => hydrateMissionControlRun(true), 1600);
}

async function hydrateMissionControlRun(silent = false) {
    if(!orchestratorMissionRunId) return;
    try {
        const res = await fetch(buildApiUrl(`/api/orchestrator/runs/${encodeURIComponent(orchestratorMissionRunId)}`));
        const data = await res.json();
        if(!res.ok || data.status !== 'success') {
            const reason = String(data?.detail || data?.reason || 'Run not found.').trim();
            if(res.status === 404 || /run not found/i.test(reason)) {
                clearMissionControlRun();
                if(!silent) toast('The previous live release session expired after a server restart. Jarvis cleared the stale timeline state.', 'warn');
                return;
            }
            throw new Error(reason);
        }
        const previousRun = orchestratorMissionRun;
        orchestratorMissionRun = data.run || null;
        announceMissionControlItemTransitions(previousRun, orchestratorMissionRun);
        upsertJarvisSystemBubble(ORCHESTRATOR_RUN_STATUS_BUBBLE_ID, renderMissionControlRunStatusCard(orchestratorMissionRun || {}));
        renderMissionControlRunTimeline();
        const normalizedRunStatus = String(orchestratorMissionRun?.status || '').toLowerCase();
        if(['completed','failed','partial_success'].includes(normalizedRunStatus)) {
            if(orchestratorMissionPollHandle) clearInterval(orchestratorMissionPollHandle);
            orchestratorMissionPollHandle = null;
            if(orchestratorMissionRun?.run_id) orchestratorMissionLastFinalizedRunId = orchestratorMissionRun.run_id;
        } else {
            startMissionControlPolling();
        }
    } catch(err) {
        if(!silent) toast(err?.message || 'Failed to load the run state.', 'error');
    }
}

async function runMissionControlPlan(options = {}) {
    if(!orchestratorMissionPlan && !options.skipPreview) await previewMissionControlPlan({ appendChat:false, silentToast:true });
    if(!orchestratorMissionPlan) return null;
    if(!orchestratorMissionPlan.can_run) { if(!options.silentToast) toast('Fix the blocked items in the plan first.', 'warn'); return null; }
    setMissionControlButtonState('mission-control-run-btn', 'Starting release...', true);
    orchestratorMissionSeenItemStates = {};
    orchestratorMissionRun = {
        run_id: orchestratorMissionRunId || '',
        status: 'starting',
        items: (Array.isArray(orchestratorMissionPlan?.items) ? orchestratorMissionPlan.items : []).map(item => ({
            ...item,
            status: 'queued',
            phase: item?.action === 'post_now' ? 'Queued for publish' : item?.action === 'send_for_approval' ? 'Queued for approval' : 'Queued for schedule',
            message: item?.warning || '',
            })),
    };
    upsertJarvisSystemBubble(ORCHESTRATOR_RUN_STATUS_BUBBLE_ID, renderMissionControlRunStatusCard(orchestratorMissionRun));
    renderMissionControlRunTimeline();
    renderJarvisBatchSummary();
    let timeout = null;
    try {
        const controller = new AbortController();
        timeout = setTimeout(() => controller.abort(), Number(options.timeoutMs || 45000));
        const res = await fetch(buildApiUrl('/api/orchestrator/run'), {
            method:'POST',
            headers:{ 'Content-Type':'application/json' },
            body:JSON.stringify({ plan: { ...orchestratorMissionPlan, approval_routing_override: String(options.approvalRoutingOverride || '').trim() } }),
            signal: controller.signal,
        });
        clearTimeout(timeout);
        const data = await res.json();
        if(!res.ok || data.status !== 'success') throw new Error(data.detail || data.reason || 'Failed to start the release run.');
        persistMissionControlRunId(data.run_id || '');
        orchestratorMissionLastFinalizedRunId = '';
        orchestratorMissionRun = data.run || null;
        upsertJarvisSystemBubble(ORCHESTRATOR_RUN_STATUS_BUBBLE_ID, renderMissionControlRunStatusCard(orchestratorMissionRun || {}));
        renderMissionControlRunTimeline();
        renderJarvisBatchSummary();
        startMissionControlPolling();
        if(!options.silentToast) toast('Jarvis is supervising the release.', 'success');
        return orchestratorMissionRun;
    } catch(err) {
        persistMissionControlRunId('');
        const startFailureMessage = err?.name === 'AbortError'
            ? 'Jarvis did not receive a confirmed start response within 45 seconds. The release may still be queued on the server, but the UI could not confirm it.'
            : String(err?.message || 'Jarvis could not start the release.');
        orchestratorMissionRun = {
            run_id: '',
            status: 'start_failed',
            start_error: startFailureMessage,
            items: (Array.isArray(orchestratorMissionPlan?.items) ? orchestratorMissionPlan.items : []).map(item => ({
                ...item,
                status: 'queued',
                phase: 'Start not confirmed',
                message: startFailureMessage,
            })), 
        };
        upsertJarvisSystemBubble(ORCHESTRATOR_RUN_STATUS_BUBBLE_ID, renderMissionControlRunStatusCard(orchestratorMissionRun));
        renderMissionControlRunTimeline();
        if(!options.silentToast) toast(startFailureMessage, 'error');
        return null;
    } finally {
        if(timeout) clearTimeout(timeout);
        setMissionControlButtonState('mission-control-run-btn', 'Start release', false);
    }
}

window.previewMissionControlPlan = previewMissionControlPlan;
window.runMissionControlPlan = runMissionControlPlan;
window.clearOrchestratorComposerSelections = clearOrchestratorComposerSelections;
loadLastOrchestratorPrompt();
refreshOrchestratorIntroCard();

document.addEventListener('click', async function(e) {
    const actionBtn = e.target.closest('[data-orch-action]');
    if(!actionBtn) return;
    const action = String(actionBtn.getAttribute('data-orch-action') || '').trim();
    if(!action) return;
    e.preventDefault();
    e.stopPropagation();
    if(actionBtn.dataset.busy === '1') return;
    if(action === 'toggle-support') {
        toggleOrchestratorSupportDrawer();
        return;
    }
    if(action === 'open-supervision') {
        openOrchestratorExecutionDetails(true);
        return;
    }
    if(action === 'close-supervision') {
        openOrchestratorExecutionDetails(false);
        return;
    }
    if(action === 'dismiss-run') {
        clearMissionControlRun();
        return;
    }
    if(action === 'clear-loaded') {
        clearOrchestratorComposerSelections();
        return;
    }
    if(action === 'retry-last-prompt') {
        if(restoreLastOrchestratorPrompt()) {
            toast('Last Jarvis prompt restored.', 'success');
        } else {
            toast('No saved Jarvis prompt yet.', 'warn');
        }
        return;
    }
    if(action === 'run-plan') {
        const originalLabel = actionBtn.textContent;
        actionBtn.dataset.busy = '1';
        actionBtn.disabled = true;
        actionBtn.textContent = 'Starting release...';
        try {
            const run = await runMissionControlPlan({ appendChat: true, silentToast: false });
            if(run) {
                actionBtn.textContent = 'Release started';
                actionBtn.classList.remove('is-primary');
                actionBtn.classList.add('is-quiet');
            } else {
                actionBtn.textContent = 'Try again';
                actionBtn.disabled = false;
                delete actionBtn.dataset.busy;
                return;
            }
        } catch(_err) {
            actionBtn.textContent = originalLabel || 'Start release';
            actionBtn.disabled = false;
            delete actionBtn.dataset.busy;
            return;
        }
    }
    if(action === 'run-plan-whatsapp') {
        const originalLabel = actionBtn.textContent;
        actionBtn.dataset.busy = '1';
        actionBtn.disabled = true;
        actionBtn.textContent = 'Routing to WhatsApp...';
        try {
            const run = await runMissionControlPlan({
                appendChat: true,
                silentToast: false,
                approvalRoutingOverride: 'desktop_and_whatsapp',
            });
            if(run) {
                actionBtn.textContent = 'WhatsApp routed';
                actionBtn.classList.remove('is-primary');
                actionBtn.classList.add('is-quiet');
            } else {
                actionBtn.textContent = 'Try again';
                actionBtn.disabled = false;
                delete actionBtn.dataset.busy;
                return;
            }
        } catch(_err) {
            actionBtn.textContent = originalLabel || 'Route to WhatsApp';
            actionBtn.disabled = false;
            delete actionBtn.dataset.busy;
            return;
        }
    }
});

function detectJarvisBatchIntent(text) {
    const lower = String(text || '').toLowerCase();
    if(!lower.trim()) return null;
    const approval = /(approval|approve|send .*approval|route .*approval)/i.test(lower);
    const schedule = /\bschedule\b|\bqueue\b|tomorrow|next week|\b\d{1,2}(:\d{2})?\s?(am|pm)\b/i.test(lower);
    const publish = /(post|publish|go live|release)/i.test(lower);
    const previewOnly = /(preview|check|validate|ready|what will|plan|review)/i.test(lower) && !/run|go ahead|execute|launch|do it/i.test(lower);
    const autoRun = /(now|immediately|go ahead|execute|launch|run it|do it|post it|publish it)/i.test(lower) || publish || approval || schedule;
    let action = '';
    if(approval) action = 'send_for_approval';
    else if(schedule) action = 'schedule';
    else if(publish) action = 'post_now';
    if(!action) return null;
    const schedulePayload = {};
    if(action === 'schedule') {
        const timeMatch = lower.match(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i);
        if(timeMatch) {
            const hour = Number(timeMatch[1]);
            const minutes = String(timeMatch[2] || '00').padStart(2, '0');
            schedulePayload.time = `${hour}:${minutes} ${String(timeMatch[3] || '').toUpperCase()}`;
        }
        if(/\btomorrow\b/i.test(lower)) {
            const d = new Date();
            d.setDate(d.getDate() + 1);
            schedulePayload.scheduled_date = d.toISOString().slice(0, 10);
        }
    }
    return { action, mode: previewOnly ? 'preview' : (autoRun ? 'run' : 'preview'), schedule: schedulePayload };
}

function resolveJarvisBatchRefs(text, explicitRefs = []) {
    if(Array.isArray(explicitRefs) && explicitRefs.length) return explicitRefs;
    const lower = String(text || '').toLowerCase();
    if(orchestratorComposerSelections.length && (/\b(selected|loaded|these|them|batch)\b/i.test(lower) || /(post|publish|approval|schedule|queue|go live|release)/i.test(lower))) {
        return orchestratorComposerSelections.map(ref => ({
            client_id: resolveMentionClient(ref.client_id),
            draft_name: String(ref.draft_name || '').trim(),
            draft_id: String(ref.draft_id || '').trim(),
            visible_token: buildVisibleDraftToken(resolveMentionClient(ref.client_id), ref.draft_name),
        }));
    }
    return [];
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
        const data = await fetchVaultDrafts(resolvedClient);
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
    currentOrchMentionContext = null;
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

    const context = getCurrentOrchestratorMentionContext(this.value, this.selectionStart);
    currentOrchMentionContext = context;
    if(context?.mode === 'draft') {
       mentionActive = true;
       mentionMode = "draft";
       mentionClient = resolveMentionClient(context.client);
       mentionQuery = context.query;
       renderMentionMenu();
    } else if(context?.mode === 'client') {
       mentionActive = true;
       mentionMode = "client";
       mentionQuery = context.query;
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

        mentionMenu.innerHTML = `<div style="font-size:10px; color:var(--t4); margin-bottom:6px; font-family:'Space Mono'; padding: 0 4px; text-transform:uppercase;">SELECT DRAFT · ${escapeHtml(mentionClient.replace(/[_-]/g, ' '))}</div>`;

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
    const textAfterCursor = val.substring(cursorPos);
    const context = currentOrchMentionContext || getCurrentOrchestratorMentionContext(val, cursorPos);
    if(!context || context.mode !== 'client') return;
    const pill = `@[${clientName}] `;
    orchInput.value = val.substring(0, context.replaceStart) + pill + textAfterCursor;
    orchInput.focus();
    orchInput.selectionStart = context.replaceStart + pill.length;
    orchInput.selectionEnd = orchInput.selectionStart;
    hideMentionMenu();
}

function insertDraftReference(clientName, draftName, draftId = '') {
    const val = orchInput.value;
    const cursorPos = orchInput.selectionStart;
    const textAfterCursor = val.substring(cursorPos);
    const context = currentOrchMentionContext || getCurrentOrchestratorMentionContext(val, cursorPos);
    if(!context || context.mode !== 'draft') return;

    const replaceStart = context.replaceStart;
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

function insertVisibleDraftReference(clientName, draftName, draftId = '') {
    const val = orchInput.value;
    const cursorPos = orchInput.selectionStart;
    const textAfterCursor = val.substring(cursorPos);
    const context = currentOrchMentionContext || getCurrentOrchestratorMentionContext(val, cursorPos);
    if(!context || context.mode !== 'draft') return;

    const replaceStart = context.replaceStart;
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
        const exists = orchestratorComposerSelections.some(item => String(item.client_id).toLowerCase() === String(clientName).toLowerCase() && String(item.draft_name).toLowerCase() === String(draftName).toLowerCase());
        if(!exists) {
            orchestratorComposerSelections.push({
                client_id: clientName,
                draft_name: draftName,
                draft_id: draftId,
                visible_token: visibleToken,
            });
            clearMissionControlPlan();
            renderOrchestratorComposerSelections();
        }
    }
    orchInput.focus();
    orchInput.selectionStart = replaceStart + token.length;
    orchInput.selectionEnd = orchInput.selectionStart;
    hideMentionMenu();
}

function renderJarvisChatPlanCard(plan, sourceText = '') {
    const items = Array.isArray(plan?.items) ? plan.items : [];
    const total = Number(plan?.totals?.total || items.length || 0);
    const ready = Number(plan?.totals?.ready || 0);
    const immediate = Number(plan?.totals?.post_now || 0);
    const scheduled = Number(plan?.totals?.schedule || 0);
    return `
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div><strong style="color:var(--t1);">I prepared the release set.</strong> I resolved <strong style="color:var(--t1);">${ready}/${total}</strong> clause${total === 1 ? '' : 's'}.${immediate || scheduled ? ` <span style="color:var(--t3);">${immediate ? `${immediate} now` : ''}${immediate && scheduled ? ' · ' : ''}${scheduled ? `${scheduled} scheduled` : ''}</span>` : ''}</div>
        <div class="orch-inline-plan">
          ${items.map((item, index) => `
            <div class="orch-inline-plan-card ${item.status === 'blocked' ? 'is-blocked' : ''}">
              <div class="orch-inline-plan-head">
                <div class="orch-inline-plan-title">${index + 1}. ${escapeHtml(String(item.summary || 'Draft'))}</div>
                <div class="orch-inline-tag">${escapeHtml(String(item.status || 'ready').replace(/_/g, ' '))}</div>
              </div>
              <div class="orch-inline-plan-tags">
                <div class="orch-inline-tag">${escapeHtml(String(item.action || plan?.action || 'review').replace(/_/g, ' '))}</div>
                ${item.schedule?.scheduled_date ? `<div class="orch-inline-tag">${escapeHtml(String(item.schedule.scheduled_date || ''))}</div>` : ''}
                ${item.schedule?.time ? `<div class="orch-inline-tag">${escapeHtml(String(item.schedule.time || ''))}</div>` : ''}
                <div class="orch-inline-tag">${escapeHtml(String(item.platform_label || 'No platforms'))}</div>
              </div>
              ${item.warning ? `<div class="orch-inline-plan-note" style="color:${item.status === 'blocked' ? 'var(--red)' : 'var(--amber)'};">${escapeHtml(String(item.warning || ''))}</div>` : ''}
            </div>`).join('')}
        </div>
        ${renderJarvisPlanActions(plan)}
      </div>`;
}

async function sendOrchestratorCmd() {
    absorbLegacyDraftRefsInInput();
    syncCurrentOrchDraftRefs();
    const typedText = orchInput.value.trim();
    if(!typedText) return;
    const isRetryShortcut = /^(try again|retry|do it again)$/i.test(typedText);
    const typedOutgoingDraftRefs = currentOrchDraftRefs.filter(ref => typedText.includes(String(ref.visible_token || '').trim()));
    if(!isRetryShortcut) saveLastOrchestratorPrompt(typedText, typedOutgoingDraftRefs);
    let text = typedText;
    let outgoingDraftRefs = typedOutgoingDraftRefs;
    if(isRetryShortcut && lastImmediatePublishPrompt) {
        text = lastImmediatePublishPrompt;
    }
    if(isRetryShortcut && String(lastOrchestratorPrompt || '').trim()) {
        text = lastOrchestratorPrompt;
        outgoingDraftRefs = normalizeRetryPromptRefs(lastOrchestratorPromptRefs);
    }
    const rawLowerText = text.toLowerCase();
    const batchIntent = detectJarvisBatchIntent(text);
    const effectiveBatchRefs = resolveJarvisBatchRefs(text, outgoingDraftRefs);
    
    // START RGB BREATHING
    const inputContainer = document.getElementById('orch-input-container');
    inputContainer.classList.add('processing');
    
    const chat = document.getElementById('orch-chat');
    
    // --- PREMIUM USER BUBBLE ---
    const userBubbleText = text
        .replace(/@\[(.*?)\]/g, '<span style="background:rgba(31,206,160,.15); color:#1fce9f; padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">@$1</span>')
        .replace(/draft_id:"[^"]+"\s*draft:"([^"]+)"/g, '<span style="background:rgba(139,108,247,.14); color:var(--purple); padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">Draft · $1</span>')
        .replace(/draft:"([^"]+)"/g, '<span style="background:rgba(139,108,247,.14); color:var(--purple); padding:2px 8px; border-radius:6px; font-weight:600; font-size:13px;">Draft · $1</span>');
    let renderedUserBubbleText = finalizeJarvisUserBubbleText(userBubbleText, outgoingDraftRefs);
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
            <span style="font-family:'Space Mono', monospace; font-size:13px; letter-spacing:.12em; color:rgba(255,255,255,.72);">OP</span>
         </div>
         <div class="user-bubble">
            ${renderedUserBubbleText}
         </div>
      </div>
    `;
    
    orchInput.value = ''; orchInput.style.height = 'auto'; scrollJarvisThreadToLatest();

    if(/^(run it|go ahead|execute( it)?|launch( it)?|do it)$/i.test(text) && orchestratorMissionPlan?.can_run) {
        const aiMsgId = "msg-" + Date.now();
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
                   <span style="display:inline-block;">Running the approved batch now...</span>
                </div>
             </div>
          </div>
        `;
        scrollJarvisThreadToLatest();
        const msgNode = document.getElementById(aiMsgId)?.querySelector('.msg-content');
        try {
            const run = await runMissionControlPlan({ appendChat: false, silentToast: true, skipPreview: true });
            if(!run) {
                renderErrorCard(msgNode, 'Jarvis could not start the release run.');
            } else {
                document.getElementById(aiMsgId)?.remove();
            }
        } catch(e) {
            renderErrorCard(msgNode, e?.message || 'Jarvis could not start the release run.');
        } finally {
            currentOrchDraftRefs = [];
            scrollJarvisThreadToLatest();
            inputContainer.classList.remove('processing');
            inputContainer.classList.add('processing-done');
            setTimeout(() => inputContainer.classList.remove('processing-done'), 1500);
        }
        return;
    }

    if(batchIntent && effectiveBatchRefs.length && !outgoingDraftRefs.length) {
        const aiMsgId = "msg-" + Date.now();
        chat.innerHTML += `
          <div id="${aiMsgId}" class="chat-msg" style="display:flex; gap:14px; max-width:85%;">
             <div class="jarvis-avatar">
                <span style="font-family:'Space Mono', monospace; font-size:14px; font-weight:700; color:rgba(214,203,255,.96); letter-spacing:.12em;">J</span>
             </div>
             <div>
                <div style="font-size:12px; font-weight:600; color:var(--purple); margin-bottom:6px; text-transform:uppercase; letter-spacing:1px;">Jarvis</div>
                <div class="msg-content ai-bubble" style="display:flex; align-items:center; gap:10px; color:var(--t3);">
                   <span style="display:inline-flex; gap:4px; align-items:center;">
                     <span style="width:6px; height:6px; border-radius:50%; background:var(--purple); animation:dotBounce 1.4s ease-in-out infinite; animation-delay:0s;"></span>
                     <span style="width:6px; height:6px; border-radius:50%; background:var(--purple); animation:dotBounce 1.4s ease-in-out infinite; animation-delay:0.2s;"></span>
                     <span style="width:6px; height:6px; border-radius:50%; background:var(--purple); animation:dotBounce 1.4s ease-in-out infinite; animation-delay:0.4s;"></span>
                   </span>
                   <span style="display:inline-block;">Resolving the selected drafts and preparing the batch...</span>
                </div>
             </div>
          </div>
        `;
        scrollJarvisThreadToLatest();
        const msgNode = document.getElementById(aiMsgId)?.querySelector('.msg-content');
        try {
            applyJarvisBatchIntent(batchIntent, effectiveBatchRefs);
            const plan = await previewMissionControlPlan({
                actionOverride: batchIntent.action,
                scheduleOverride: batchIntent.schedule,
                refsOverride: effectiveBatchRefs,
                appendChat: false,
                silentToast: true,
            });
            if(!plan) {
                renderErrorCard(msgNode, "Jarvis could not prepare the execution plan.");
            } else if(plan.can_run && batchIntent.mode === 'run') {
                const run = await runMissionControlPlan({ appendChat: false, silentToast: true, skipPreview: true });
                if(!run) {
                    renderErrorCard(msgNode, "Jarvis could not start the release run.");
                } else {
                    document.getElementById(aiMsgId)?.remove();
                }
            } else {
                msgNode.className = 'msg-content ai-bubble';
                msgNode.innerHTML = renderJarvisChatPlanCard(plan, text);
            }
        } catch(e) {
            renderErrorCard(msgNode, e?.message || 'Jarvis could not prepare the structured batch.');
        } finally {
            currentOrchDraftRefs = [];
            scrollJarvisThreadToLatest();
            inputContainer.classList.remove('processing');
            inputContainer.classList.add('processing-done');
            setTimeout(() => inputContainer.classList.remove('processing-done'), 1500);
        }
        return;
    }
    
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
    scrollJarvisThreadToLatest();
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
            } else if(data.task_preview) {
                const previewItems = Array.isArray(data.task_preview?.items) ? data.task_preview.items : [];
                orchestratorComposerSelections = previewItems
                    .filter(item => String(item?.client_id || '').trim() && String(item?.draft_name || '').trim())
                    .map(item => ({
                        client_id: resolveMentionClient(item.client_id),
                        draft_name: String(item.draft_name || '').trim(),
                        draft_id: String(item.draft_id || '').trim(),
                        visible_token: buildVisibleDraftToken(resolveMentionClient(item.client_id), item.draft_name),
                    }));
                orchestratorMissionPlan = data.task_preview;
                renderOrchestratorComposerSelections();
                renderMissionControlPlanCard();
                renderJarvisBatchSummary();
                if(!data.task_preview?.can_run) {
                    toggleOrchestratorSupportDrawer(true);
                }
                msgNode.style.cssText = '';
                msgNode.className = 'msg-content ai-bubble';
                msgNode.innerHTML = renderJarvisChatPlanCard(data.task_preview, text);
            } else {
                const isStructured = reply.match(/^[-*]\s|^\d+\.|^#{1,3}\s|^---|\*\*.*\*\*/m) && reply.split('\n').length > 4;
                msgNode.style.cssText = '';
                
                if(await tryRenderPublishSuccessCard(msgNode, reply, outgoingDraftRefs)) {
                    // rendered as premium publish confirmation card
                } else if(isStructured) {
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
        scrollJarvisThreadToLatest();
        
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
    if(counts) counts.textContent = `${activeCount} upcoming | ${historyCount} delivered`;
    if(title) title.textContent = scheduleView === 'history' ? 'Delivered History' : 'Upcoming Releases';
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

let strategyPlansCache = [];
let strategyPlanActiveClient = '';
const strategyPlanActiveIds = {};
let strategyLoadingInterval = null;
let strategyLoadingPhaseIndex = 0;

function escapeJsString(value) {
    return String(value || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' ');
}

function getStrategyLoadingPhases() {
    return [
        'Reading the brand profile',
        'Scanning the last 30 days',
        'Distilling trend signals',
        'Composing the plan',
    ];
}

function setStrategyLoadingPhase(phaseIndex = 0, message = '') {
    const phases = document.querySelectorAll('#strategy-loading-phases .strategy-console-phase');
    phases.forEach((phase, index) => {
        phase.classList.toggle('is-active', index === phaseIndex);
        phase.classList.toggle('is-done', index < phaseIndex);
    });
    const statusNode = document.getElementById('strategy-status');
    if(statusNode && message) {
        statusNode.innerHTML = message;
    }
}

function setStrategyPlannerBusy(isBusy, source = 'build') {
    const shell = document.getElementById('strategy-builder-shell');
    const buildBtn = document.getElementById('strategy-build-btn');
    const refreshBtn = document.getElementById('strategy-refresh-signals-btn');
    if(shell) shell.classList.toggle('is-loading', !!isBusy);
    if(isBusy) {
        if(buildBtn) setButtonBusy(buildBtn, source === 'refresh' ? 'Refreshing signals...' : 'Building plan...');
        if(refreshBtn) setButtonBusy(refreshBtn, 'Surfing the web...');
    } else {
        if(buildBtn) restoreButtonBusy(buildBtn);
        if(refreshBtn) restoreButtonBusy(refreshBtn);
    }
}

function startStrategyLoadingSequence(source = 'build') {
    clearInterval(strategyLoadingInterval);
    strategyLoadingPhaseIndex = 0;
    const phrases = getStrategyLoadingPhases();
    const lead = source === 'refresh'
        ? 'The Strategy Planner agent is now surfing the web...'
        : 'The Strategy Planner agent is now surfing the web...';
    setStrategyLoadingPhase(0, `<strong style="color:var(--t1);">${lead}</strong><br/><span style="color:var(--t3);">Jarvis is reading the brand, checking recent signals, and shaping a premium plan.</span>`);
    strategyLoadingInterval = setInterval(() => {
        strategyLoadingPhaseIndex = Math.min(strategyLoadingPhaseIndex + 1, phrases.length - 1);
        const phase = phrases[strategyLoadingPhaseIndex];
        const phaseCopy = strategyLoadingPhaseIndex === 0
            ? 'Jarvis is reading the profile and brand voice.'
            : strategyLoadingPhaseIndex === 1
                ? 'Jarvis is scanning recent signals from the last 30 days.'
                : strategyLoadingPhaseIndex === 2
                    ? 'Jarvis is distilling the strongest trend cues.'
                    : 'Jarvis is composing the final editorial directions.';
        setStrategyLoadingPhase(strategyLoadingPhaseIndex, `<strong style="color:var(--t1);">${phase}...</strong><br/><span style="color:var(--t3);">${phaseCopy}</span>`);
    }, 1100);
}

function stopStrategyLoadingSequence(success = true, message = '') {
    clearInterval(strategyLoadingInterval);
    strategyLoadingInterval = null;
    strategyLoadingPhaseIndex = 0;
    setStrategyPlannerBusy(false);
    const statusNode = document.getElementById('strategy-status');
    if(statusNode && message) {
        statusNode.innerHTML = `<span style="color:${success ? 'var(--green)' : 'var(--red)'};">${message}</span>`;
    }
    const phases = document.querySelectorAll('#strategy-loading-phases .strategy-console-phase');
    phases.forEach((phase, index) => {
        phase.classList.toggle('is-active', success && index === phases.length - 1);
        phase.classList.toggle('is-done', success && index < phases.length - 1);
    });
}

function setStrategyPlanFocus(clientId = '', planId = '') {
    const normalizedClientId = String(clientId || '').trim();
    if(!normalizedClientId) return;
    strategyPlanActiveClient = normalizedClientId;
    if(planId) strategyPlanActiveIds[normalizedClientId] = String(planId || '').trim();
    syncStrategyPlanUiState();
    renderStrategyPlans().catch(() => null);
}

function removeStrategyPlanFromLocalState(planId) {
    const normalizedPlanId = String(planId || '').trim();
    if(!normalizedPlanId) return;
    const removedPlans = strategyPlansCache.filter(plan => String(plan?.plan_id || '').trim() === normalizedPlanId);
    if(!removedPlans.length) return;
    strategyPlansCache = strategyPlansCache.filter(plan => String(plan?.plan_id || '').trim() !== normalizedPlanId);
    const affectedClients = [...new Set(removedPlans.map(plan => String(plan?.client_id || '').trim()).filter(Boolean))];
    affectedClients.forEach(clientId => {
        const remainingPlans = strategyPlansCache.filter(plan => String(plan?.client_id || '').trim() === clientId);
        const activePlanId = String(strategyPlanActiveIds[clientId] || '').trim();
        if(activePlanId === normalizedPlanId) {
            if(remainingPlans.length) strategyPlanActiveIds[clientId] = String(remainingPlans[0]?.plan_id || '').trim();
            else delete strategyPlanActiveIds[clientId];
        }
        if(strategyPlanActiveClient === clientId && !remainingPlans.length) {
            strategyPlanActiveClient = String(groupStrategyPlansByClient(strategyPlansCache)[0]?.clientId || '').trim();
        }
    });
}

function removeStrategyClientPlansFromLocalState(clientId) {
    const normalizedClientId = String(clientId || '').trim();
    if(!normalizedClientId) return 0;
    const beforeCount = strategyPlansCache.length;
    strategyPlansCache = strategyPlansCache.filter(plan => String(plan?.client_id || '').trim() !== normalizedClientId);
    delete strategyPlanActiveIds[normalizedClientId];
    if(strategyPlanActiveClient === normalizedClientId) {
        strategyPlanActiveClient = String(groupStrategyPlansByClient(strategyPlansCache)[0]?.clientId || '').trim();
    }
    return Math.max(0, beforeCount - strategyPlansCache.length);
}

function getStrategyResearchSummary(plan) {
    const snapshot = plan?.research_snapshot || {};
    const sourceCount = Number(snapshot.source_count || snapshot.sources?.length || snapshot.results?.length || 0);
    const updatedAt = String(snapshot.fetched_at || snapshot.updated_at || '').trim();
    const freshness = updatedAt ? `Updated ${updatedAt.slice(0, 10)}` : 'Research: last 30 days';
    return {
        sourceCount,
        freshness,
        note: String(snapshot.summary || snapshot.note || snapshot.insight || '').trim(),
    };
}

function getStrategyPlanSourceLinks(item) {
    const links = [];
    const rawLinks = Array.isArray(item?.source_links) ? item.source_links : [];
    rawLinks.forEach((link, index) => {
        if(!link) return;
        if(typeof link === 'string') {
            links.push({ label: `Source ${index + 1}`, url: link });
            return;
        }
        const url = String(link.url || link.link || '').trim();
        if(!url) return;
        links.push({
            label: String(link.title || link.label || `Source ${index + 1}`).trim(),
            url,
        });
    });
    return links;
}

function getStrategyPlanSourceSignals(item) {
    return Array.isArray(item?.source_signals) ? item.source_signals.filter(Boolean) : [];
}

async function ensureGlobalClientsLoaded() {
    if(globalClients.length) return globalClients;
    try {
        const res = await fetch(buildApiUrl("/api/clients"));
        const data = await res.json();
        if(data.status === "success" && Array.isArray(data.clients)) {
            globalClients = data.clients;
            populateOrchestratorComposerClients();
        }
    } catch(e) {}
    return globalClients;
}

function parsePublishSuccessReply(reply) {
    const text = String(reply || '').trim();
    if(!/^Pipeline completed successfully for /i.test(text)) return null;
    const clientMatch = text.match(/^Pipeline completed successfully for ([^.]+)\./i);
    const clientId = clientMatch ? String(clientMatch[1] || '').trim() : '';
    const platforms = [];
    const fbMatch = text.match(/Facebook\s+published\s+\(ID:\s*([^)]+)\)/i);
    const igMatch = text.match(/Instagram\s+published\s+\(ID:\s*([^)]+)\)/i);
    if(fbMatch) platforms.push({ label: 'Facebook', id: String(fbMatch[1] || '').trim() });
    if(igMatch) platforms.push({ label: 'Instagram', id: String(igMatch[1] || '').trim() });
    return { clientId, platforms, raw: text };
}

async function resolvePublishSuccessMedia(refs = []) {
    const first = Array.isArray(refs) ? refs[0] : null;
    const clientId = resolveWorkspaceClientId(first?.client_id || '');
    if(!clientId) return null;
    try {
        const draftName = String(first?.draft_name || '').trim();
        const draftId = String(first?.draft_id || '').trim();
        const cachedBundles = (vaultDraftsCache[clientId] && typeof vaultDraftsCache[clientId].bundles === 'object')
            ? vaultDraftsCache[clientId].bundles
            : {};
        let bundle = draftName ? cachedBundles[draftName] : null;
        if(!bundle && currentVaultClient === clientId && currentVaultBundles && typeof currentVaultBundles === 'object') {
            bundle = draftName ? currentVaultBundles[draftName] : null;
        }
        if(!bundle) {
            const drafts = await fetchVaultDrafts(clientId);
            const bundles = drafts?.bundles || {};
            bundle = draftName ? bundles[draftName] : null;
            if(!bundle && draftId) {
                bundle = Object.values(bundles).find(item => String(item?.draft_id || '').trim() === draftId) || null;
            }
        }
        const items = Array.isArray(bundle?.items) ? bundle.items : [];
        const firstItem = items[0];
        const filename = String(firstItem?.filename || '').trim();
        if(!filename) return null;
        const cachedAssets = (vaultAssetsCache[clientId] && Array.isArray(vaultAssetsCache[clientId].files))
            ? vaultAssetsCache[clientId].files
            : [];
        let asset = cachedAssets.find(item => String(item?.filename || '').trim() === filename) || null;
        if(!asset && currentVaultClient === clientId) {
            asset = (Array.isArray(currentVaultFiles) ? currentVaultFiles : []).find(item => String((typeof item === 'string' ? item : item?.filename) || '').trim() === filename) || null;
        }
        if(!asset) {
            try {
                const assets = await fetchVaultAssets(clientId);
                asset = (Array.isArray(assets?.files) ? assets.files : []).find(item => String(item?.filename || '').trim() === filename) || null;
            } catch(_) {}
        }
        if(!asset) {
            return buildDirectVaultMediaFallback(clientId, firstItem);
        }
        const isVideo = String(asset?.kind || firstItem?.kind || '').toLowerCase() === 'video';
        return {
            url: isVideo ? getVaultAssetPosterUrl(clientId, asset) : getVaultAssetPreviewUrl(clientId, asset),
            label: filename,
            isVideo,
            clientId,
        };
    } catch(_) {
        const fallbackItem = Array.isArray(first?.items) ? first.items[0] : null;
        return buildDirectVaultMediaFallback(clientId, fallbackItem || {});
    }
}

function renderPublishSuccessCard(payload, media = null) {
    const clientLabel = escapeHtml(String(payload?.clientId || 'Client'));
    const platformMarkup = (Array.isArray(payload?.platforms) ? payload.platforms : []).map(platform => `
      <div class="publish-success-platform">
        <div class="publish-success-platform-label">${escapeHtml(platform.label)}</div>
        <div class="publish-success-platform-value">${escapeHtml(platform.id)}</div>
      </div>
    `).join('');
    const mediaMarkup = media?.url
        ? `<img src="${escapeHtml(media.url)}" alt="${escapeHtml(media.label || clientLabel)}" loading="eager" decoding="async" width="140" height="140" />`
        : `<div class="publish-success-media-fallback">Live release<br/>confirmed</div>`;
    return `
      <div class="publish-success-card">
        <div class="publish-success-media">
          <div class="publish-success-stamp">Published</div>
          ${mediaMarkup}
        </div>
        <div class="publish-success-copy">
          <div class="publish-success-kicker">Release Confirmed</div>
          <div class="publish-success-title">${clientLabel} is live.</div>
          <div class="publish-success-meta">Jarvis handed the release off successfully and received platform confirmation from the connected publish lanes.</div>
          <div class="publish-success-platforms">${platformMarkup || '<div class="publish-success-platform"><div class="publish-success-platform-label">Status</div><div class="publish-success-platform-value">Published successfully</div></div>'}</div>
        </div>
      </div>
    `;
}

async function tryRenderPublishSuccessCard(node, reply, refs = []) {
    const payload = parsePublishSuccessReply(reply);
    if(!payload || !node) return false;
    const media = await resolvePublishSuccessMedia(refs);
    node.className = 'msg-content';
    node.style.cssText = '';
    node.innerHTML = renderPublishSuccessCard(payload, media);
    return true;
}

async function refreshGlobalClients() {
    try {
        const res = await fetch(buildApiUrl("/api/clients"));
        const data = await res.json();
        if(data.status === "success" && Array.isArray(data.clients)) {
            globalClients = data.clients;
            populateOrchestratorComposerClients();
        }
    } catch(e) {}
    return globalClients;
}

function upsertClientWorkspaceData(payload) {
    const clientId = String(payload?.client_id || '').trim();
    if(!clientId) return null;
    clientWorkspaceDataCache[clientId] = payload;
    return clientWorkspaceDataCache[clientId];
}

function syncClientAssetBadges() {
    const ids = Array.isArray(globalClients) ? globalClients : [];
    ids.forEach(clientId => {
        const badge = document.getElementById(`cfg-health-drafts-${clientId}`);
        if(badge) {
            badge.textContent = `Assets ${clientVaultCounts[clientId] || 0}`;
        }
    });
}

function getClientWorkspaceStatus(clientId) {
    const payload = clientWorkspaceDataCache[clientId] || null;
    const profile = payload?.profile_json || {};
    const profileReady = !!(profile.business_name && profile.identity && profile.target_audience);
    const credsReady = !!(payload?.meta_access_token && (payload?.facebook_page_id || payload?.instagram_account_id));
    return {
        payload,
        profileReady,
        profileText: payload ? (profileReady ? 'Profile Ready' : 'Profile Needs Review') : 'Profile Loading',
        profileClass: payload ? (profileReady ? 'b-on' : 'b-am') : 'b-am',
        credsReady,
        credsText: payload ? (credsReady ? 'Credentials Ready' : 'Credentials Missing') : 'Credentials Loading',
        credsClass: payload ? (credsReady ? 'b-on' : 'b-am') : 'b-am',
    };
}

async function refreshClientWorkspaceData(force = false) {
    if(!force && Object.keys(clientWorkspaceDataCache).length) return clientWorkspaceDataCache;
    const requestToken = ++activeClientWorkspaceRequestToken;
    try {
        const res = await fetch(buildApiUrl("/api/clients/full"));
        const data = await res.json();
        if(requestToken !== activeClientWorkspaceRequestToken) return clientWorkspaceDataCache;
        if(data.status === "success" && Array.isArray(data.clients)) {
            const nextCache = {};
            data.clients.forEach(item => {
                const clientId = String(item?.client_id || '').trim();
                if(clientId) nextCache[clientId] = item;
            });
            clientWorkspaceDataCache = nextCache;
        }
    } catch(e) {}
    return clientWorkspaceDataCache;
}

function applyClientWorkspaceData(clientId, payload) {
    const data = payload || clientWorkspaceDataCache[clientId] || null;
    if(!data) return false;
    const profile = data.profile_json || {};
    const voice = profile.brand_voice || {};
    const lang = profile.language_profile || {};

    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if(el) el.value = value ?? '';
    };
    const setBadge = (id, cls, text) => {
        const el = document.getElementById(id);
        if(el) {
            el.className = `badge ${cls}`;
            el.textContent = text;
        }
    };

    setValue(`cfg-target-voice-${clientId}`, lang.target_voice_language || profile.target_voice_language || 'arabic_gulf');
    setValue(`cfg-business-${clientId}`, profile.business_name || clientId);
    setValue(`cfg-industry-${clientId}`, profile.industry || '');
    setValue(`cfg-identity-${clientId}`, profile.identity || '');
    setValue(`cfg-tone-${clientId}`, Array.isArray(voice.tone) ? voice.tone.join(', ') : (voice.tone || (Array.isArray(profile.tone) ? profile.tone.join(', ') : (profile.tone || ''))));
    setValue(`cfg-style-${clientId}`, voice.style || profile.style || '');
    setValue(`cfg-dialect-${clientId}`, voice.dialect_notes || profile.dialect_notes || '');
    setValue(`cfg-audience-${clientId}`, profile.target_audience || '');
    setValue(`cfg-services-${clientId}`, Array.isArray(profile.services) ? profile.services.join(', ') : '');
    setValue(`cfg-seo-${clientId}`, Array.isArray(profile.seo_keywords) ? profile.seo_keywords.join(', ') : '');
    setValue(`cfg-hashtags-${clientId}`, Array.isArray(profile.hashtag_bank) ? profile.hashtag_bank.join(', ') : '');
    setValue(`cfg-banned-${clientId}`, Array.isArray(profile.banned_words) ? profile.banned_words.join(', ') : '');
    setValue(`cfg-voice-examples-${clientId}`, Array.isArray(profile.brand_voice_examples) ? profile.brand_voice_examples.join('\n') : '');
    setValue(`cfg-rules-${clientId}`, Array.isArray(profile.dos_and_donts) ? profile.dos_and_donts.join('\n') : '');

    setValue(`cfg-phone-${clientId}`, data.phone_number || '');
    setValue(`cfg-token-${clientId}`, data.meta_access_token || '');
    setValue(`cfg-fb-${clientId}`, data.facebook_page_id || '');
    setValue(`cfg-ig-${clientId}`, data.instagram_account_id || '');

    window._cfgOriginal = window._cfgOriginal || {};
    window._cfgOriginal[clientId] = {
        phone_number: data.phone_number || '',
        meta_access_token: data.meta_access_token || '',
        facebook_page_id: data.facebook_page_id || '',
        instagram_account_id: data.instagram_account_id || ''
    };

    const status = getClientWorkspaceStatus(clientId);
    setBadge(`cfg-health-profile-${clientId}`, status.profileClass, status.profileText);
    setBadge(`cfg-health-creds-${clientId}`, status.credsClass, status.credsText);
    const assetCount = Number(clientVaultCounts[clientId] || 0);
    setBadge(`cfg-health-drafts-${clientId}`, assetCount > 0 ? 'b-pu' : 'b-am', assetCount > 0 ? `${assetCount} Assets` : 'No Assets');
    return true;
}

function applyConfigSectionVisualState(clientId, section, options = {}) {
    const detPanel = document.getElementById('cfg-details-' + clientId);
    const credPanel = document.getElementById('cfg-creds-' + clientId);
    const detBtn = document.getElementById('btn-details-' + clientId);
    const credBtn = document.getElementById('btn-creds-' + clientId);
    if(!detPanel || !credPanel || !detBtn || !credBtn) return;

    const normalized = section === 'details' || section === 'creds' ? section : '';
    clientWorkspaceSectionState[clientId] = normalized;

    detPanel.style.display = normalized === 'details' ? 'block' : 'none';
    credPanel.style.display = normalized === 'creds' ? 'block' : 'none';
    detBtn.style.borderColor = normalized === 'details' ? 'rgba(139,108,247,.5)' : 'rgba(139,108,247,.2)';
    detBtn.style.background = normalized === 'details' ? 'rgba(139,108,247,.18)' : 'rgba(139,108,247,.08)';
    credBtn.style.borderColor = normalized === 'creds' ? 'rgba(47,168,224,.5)' : 'rgba(47,168,224,.2)';
    credBtn.style.background = normalized === 'creds' ? 'rgba(47,168,224,.18)' : 'rgba(47,168,224,.08)';

    if(options.skipLoad) return;
    if(normalized === 'details') {
        loadClientDetails(clientId);
    } else if(normalized === 'creds') {
        loadClientCreds(clientId);
    }
}

function populateStrategyClientOptions() {
    const select = document.getElementById('strategy-client');
    if(!select) return;
    const previous = String(select.value || '').trim();
    const clients = [...globalClients].sort((a, b) => String(a).localeCompare(String(b)));
    select.innerHTML = `<option value="">Select client</option>${clients.map(client => `<option value="${escapeHtml(String(client))}">${escapeHtml(String(client).replace(/_/g, ' '))}</option>`).join('')}`;
    if(previous && clients.includes(previous)) {
        select.value = previous;
    }
}

function formatStrategyWindowLabel(value) {
    const key = String(value || '').trim().toLowerCase();
    if(key === 'next_30_days') return 'Next 30 days';
    if(key === 'next_7_days') return 'Next 7 days';
    return String(value || 'Custom window').replace(/_/g, ' ');
}

function formatStrategyConfidence(value) {
    const numeric = Number(value);
    if(Number.isNaN(numeric)) return '50%';
    return `${Math.round(Math.max(0, Math.min(numeric, 1)) * 100)}%`;
}

function syncStrategyPlanUiState() {
    const select = document.getElementById('strategy-client');
    const clearBtn = document.getElementById('strategy-clear-client-btn');
    const clientId = String(select?.value || '').trim();
    if(clearBtn) {
        clearBtn.disabled = !clientId;
        clearBtn.textContent = clientId ? `Clear ${clientId.replace(/_/g, ' ')} plans` : `Clear selected client's plans`;
    }
}

function setStrategyClientFilter(clientId = '') {
    const select = document.getElementById('strategy-client');
    const nextClient = String(clientId || '').trim();
    strategyPlanActiveClient = nextClient;
    if(select) select.value = nextClient;
    syncStrategyPlanUiState();
    renderStrategyPlans().catch(() => null);
}

function groupStrategyPlansByClient(plans) {
    const grouped = new Map();
    for(const plan of Array.isArray(plans) ? plans : []) {
        const clientId = String(plan?.client_id || 'Unknown_Client').trim() || 'Unknown_Client';
        if(!grouped.has(clientId)) grouped.set(clientId, []);
        grouped.get(clientId).push(plan);
    }
    return [...grouped.entries()]
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([clientId, clientPlans]) => ({
            clientId,
            plans: clientPlans,
            itemCount: clientPlans.reduce((sum, plan) => sum + (Array.isArray(plan?.items) ? plan.items.length : 0), 0),
        }));
}

function renderStrategyClientPills(groups, selectedClient) {
    const host = document.getElementById('strategy-client-pills');
    if(!host) return;
    const list = Array.isArray(groups) ? groups : [];
    if(!list.length) {
        host.innerHTML = '';
        return;
    }
    host.innerHTML = list.map(group => {
        const clientId = String(group.clientId || '').trim();
        const active = clientId === selectedClient;
        return `<button type="button" class="strategy-client-pill ${active ? 'is-active' : ''}" onclick="setStrategyClientFilter('${escapeJsString(clientId)}')">${escapeHtml(clientId.replace(/_/g, ' '))} <span>${group.plans.length}</span></button>`;
    }).join('');
}

function renderStrategyPlanCards(plans) {
    const host = document.getElementById('strategy-plan-list');
    const counts = document.getElementById('strategy-plan-counts');
    if(!host) return;
    const list = Array.isArray(plans) ? plans : [];
    const totalItems = list.reduce((sum, plan) => sum + (Array.isArray(plan?.items) ? plan.items.length : 0), 0);
    const groups = groupStrategyPlansByClient(list);
    const selectedClient = String(document.getElementById('strategy-client')?.value || '').trim();
    renderStrategyClientPills(groups, selectedClient);
    syncStrategyPlanUiState();
    if(counts) counts.textContent = `${list.length} plan${list.length === 1 ? '' : 's'} | ${totalItems} item${totalItems === 1 ? '' : 's'} | ${groups.length} client${groups.length === 1 ? '' : 's'}`;
    if(!list.length) {
        host.innerHTML = `<div class="strategy-plan-empty">No saved strategy plans yet for this client.</div>`;
        return;
    }
    host.innerHTML = groups.map((group, groupIndex) => {
        const clientId = String(group.clientId || '').trim();
        const planCount = group.plans.length;
        const itemCount = group.itemCount;
        const selected = clientId === selectedClient;
        return `
          <section class="strategy-client-group">
            <div class="strategy-client-group-head">
              <div>
                <div class="strategy-client-group-title">${escapeHtml(clientId.replace(/_/g, ' '))}</div>
                <div class="strategy-client-group-meta">${planCount} plan${planCount === 1 ? '' : 's'} · ${itemCount} item${itemCount === 1 ? '' : 's'}</div>
                <div class="strategy-client-group-copy">Jarvis keeps these as planning directions for this client until you materialize them for operator review.</div>
              </div>
              <div class="strategy-client-group-actions">
                ${selected ? '' : `<button type="button" class="work-item-ghost" onclick="setStrategyClientFilter('${escapeHtml(clientId)}')">Only this client</button>`}
                <button type="button" class="work-item-ghost" onclick="deleteStrategyPlansForSelectedClient('${escapeHtml(clientId)}')">Clear client plans</button>
              </div>
            </div>
            <div class="strategy-plan-stack">
              ${group.plans.map((plan, index) => {
                  const items = Array.isArray(plan?.items) ? plan.items : [];
                  const planId = String(plan?.plan_id || '').trim();
                  const materialized = String(plan?.status || '').toLowerCase() === 'materialized';
                  const summary = escapeHtml(String(plan?.summary || 'Strategy plan ready.'));
                  const windowLabel = escapeHtml(formatStrategyWindowLabel(plan?.window || plan?.timeframe || 'next_7_days'));
                  const objective = escapeHtml(String(plan?.objective || '').trim());
                  const goal = escapeHtml(String(plan?.goal || '').trim());
                  const campaign = escapeHtml(String(plan?.campaign_context || '').trim());
                  const openAttr = (selected && index === 0) || (!selectedClient && groupIndex === 0 && index === 0) ? 'open' : '';
                  return `
                    <details class="strategy-plan-card" ${openAttr}>
                      <summary>
                        <div>
                          <div class="strategy-plan-summary-title">${summary}</div>
                          <div class="strategy-plan-summary-meta">${windowLabel}${objective ? ` · ${objective}` : ''}${goal ? ` · Goal: ${goal}` : ''}</div>
                          ${campaign ? `<div class="strategy-plan-summary-copy">${campaign}</div>` : ''}
                        </div>
                        <div class="strategy-plan-summary-right">
                          <span class="strategy-plan-status" style="color:${materialized ? 'var(--green)' : 'var(--purple)'};">${escapeHtml(String(plan?.status || 'ready').replace(/_/g, ' '))}</span>
                          <span class="client-wizard-chip">${items.length} item${items.length === 1 ? '' : 's'}</span>
                        </div>
                      </summary>
                      <div class="strategy-plan-card-body">
                        <div class="strategy-plan-actions">
                          <button type="button" class="orch-inline-action-btn ${materialized ? 'is-quiet' : 'is-primary'}" onclick="materializeStrategyPlan('${escapeHtml(planId)}')" ${materialized ? 'disabled' : ''}>${materialized ? 'Suggestions ready' : 'Materialize suggestions'}</button>
                          <button type="button" class="work-item-ghost" onclick="deleteStrategyPlanById('${escapeHtml(planId)}')">Delete plan</button>
                        </div>
                        ${items.map((item, itemIndex) => {
                            const status = String(item?.status || 'planned').toLowerCase();
                            const statusTone = status === 'suggested' ? 'var(--green)' : 'var(--amber)';
                            const platforms = Array.isArray(item?.platforms) ? item.platforms.filter(Boolean).join(' + ') : '';
                            const signals = Array.isArray(item?.source_signals) ? item.source_signals.filter(Boolean) : [];
                            return `
                              <div class="strategy-plan-item">
                                <div class="strategy-plan-item-head">
                                  <div>
                                    <div class="strategy-plan-item-title">${itemIndex + 1}. ${escapeHtml(String(item?.topic || 'Untitled direction'))}</div>
                                    <div class="strategy-plan-item-meta">${escapeHtml(String(item?.format || 'content'))}${platforms ? ` · ${escapeHtml(platforms)}` : ''}${item?.recommended_time ? ` · ${escapeHtml(String(item.recommended_time))}` : ''}</div>
                                  </div>
                                  <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                                    <span class="strategy-plan-status" style="color:${statusTone};">${escapeHtml(status.replace(/_/g, ' '))}</span>
                                    <span style="font-size:11px; color:var(--t4); font-family:'Space Mono';">${escapeHtml(formatStrategyConfidence(item?.confidence))}</span>
                                  </div>
                                </div>
                                ${item?.hook_direction ? `<div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Hook:</strong> ${escapeHtml(String(item.hook_direction))}</div>` : ''}
                                ${item?.rationale ? `<div class="strategy-plan-item-copy">${escapeHtml(String(item.rationale))}</div>` : ''}
                                ${signals.length ? `<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">${signals.map(signal => `<span class="dp">${escapeHtml(String(signal))}</span>`).join('')}</div>` : ''}
                                ${item?.needs_review ? `<div style="font-size:11px; color:var(--amber); margin-top:8px; font-family:'Space Mono';">Needs review before scheduling</div>` : ''}
                              </div>`;
                        }).join('')}
                      </div>
                    </details>`;
              }).join('')}
            </div>
          </section>`;
    }).join('');
}

async function renderStrategyPlans() {
    await ensureGlobalClientsLoaded();
    populateStrategyClientOptions();
    syncStrategyPlanUiState();
    const select = document.getElementById('strategy-client');
    const host = document.getElementById('strategy-plan-list');
    if(!host) return;
    const clientId = String(select?.value || '').trim();
    try {
        let url = buildApiUrl('/api/strategy/plans');
        if(clientId) url += `?client_id=${encodeURIComponent(clientId)}`;
        const res = await fetch(url);
        const data = await res.json();
        if(data.status !== 'success') throw new Error(data.reason || 'Failed to load strategy plans.');
        strategyPlansCache = Array.isArray(data.plans) ? data.plans : [];
        renderStrategyPlanCards(strategyPlansCache);
    } catch(err) {
        host.innerHTML = `<div class="strategy-plan-empty" style="color:var(--red);">${escapeHtml(err?.message || 'Failed to load strategy plans.')}</div>`;
    }
}

async function buildStrategyPlan() {
    await ensureGlobalClientsLoaded();
    populateStrategyClientOptions();
    const clientId = String(document.getElementById('strategy-client')?.value || '').trim();
    const windowName = String(document.getElementById('strategy-window')?.value || 'next_7_days').trim();
    const goal = String(document.getElementById('strategy-goal')?.value || '').trim();
    const campaignContext = String(document.getElementById('strategy-context')?.value || '').trim();
    const statusNode = document.getElementById('strategy-status');
    if(!clientId) {
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--amber);">Pick a client first so Jarvis knows which brand it is planning for.</span>`;
        toast('Pick a client first.', 'warn');
        return;
    }
    if(statusNode) statusNode.innerHTML = `<span style="color:var(--blue);">Jarvis is building the strategy plan...</span>`;
    try {
        const res = await fetch(buildApiUrl('/api/strategy/plans'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId, window: windowName, goal, campaign_context: campaignContext }),
        });
        const data = await res.json();
        if(!res.ok || data.status !== 'success') throw new Error(data.reason || 'Jarvis could not build the strategy plan.');
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--green);">Strategy plan saved. Jarvis kept it as planned work, not a live schedule.</span>`;
        toast('Strategy plan ready.', 'success');
        await renderStrategyPlans();
    } catch(err) {
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--red);">${escapeHtml(err?.message || 'Jarvis could not build the strategy plan.')}</span>`;
        toast(err?.message || 'Jarvis could not build the strategy plan.', 'error');
    }
}

function renderStrategyPlanCards(plans) {
    const host = document.getElementById('strategy-plan-list');
    const counts = document.getElementById('strategy-plan-counts');
    if(!host) return;
    const list = Array.isArray(plans) ? plans : [];
    const totalItems = list.reduce((sum, plan) => sum + (Array.isArray(plan?.items) ? plan.items.length : 0), 0);
    const groups = groupStrategyPlansByClient(list);
    const select = document.getElementById('strategy-client');
    let selectedClient = String(select?.value || strategyPlanActiveClient || groups[0]?.clientId || '').trim();
    if(selectedClient && !groups.some(group => String(group?.clientId || '').trim() === selectedClient)) {
        selectedClient = String(groups[0]?.clientId || '').trim();
    }
    if(select && selectedClient && select.value !== selectedClient) select.value = selectedClient;
    strategyPlanActiveClient = selectedClient;
    renderStrategyClientPills(groups, selectedClient);
    syncStrategyPlanUiState();
    if(counts) counts.textContent = `${list.length} plan${list.length === 1 ? '' : 's'} | ${totalItems} item${totalItems === 1 ? '' : 's'} | ${groups.length} client${groups.length === 1 ? '' : 's'}`;
    if(!list.length) {
        host.innerHTML = `<div class="strategy-plan-empty">No saved strategy plans yet for this client.</div>`;
        return;
    }
    const selectedGroup = groups.find(group => String(group.clientId || '').trim() === selectedClient) || groups[0];
    const clientId = String(selectedGroup?.clientId || '').trim();
    const plansForClient = Array.isArray(selectedGroup?.plans) ? selectedGroup.plans : [];
    const planCount = plansForClient.length;
    const itemCount = Number(selectedGroup?.itemCount || plansForClient.reduce((sum, plan) => sum + (Array.isArray(plan?.items) ? plan.items.length : 0), 0));
    let activePlanId = String(strategyPlanActiveIds[clientId] || plansForClient[0]?.plan_id || '').trim();
    let activePlan = plansForClient.find(plan => String(plan?.plan_id || '').trim() === activePlanId) || plansForClient[0] || null;
    if(activePlan) {
        const resolvedPlanId = String(activePlan.plan_id || '').trim();
        if(resolvedPlanId && resolvedPlanId !== activePlanId) {
            activePlanId = resolvedPlanId;
        }
    }
    if(clientId) strategyPlanActiveIds[clientId] = activePlanId;
    const activeItems = Array.isArray(activePlan?.items) ? activePlan.items : [];
    const research = getStrategyResearchSummary(activePlan || {});
    const sourceSignals = activeItems.flatMap(item => getStrategyPlanSourceSignals(item));
    const sourceLinks = activeItems.flatMap(item => getStrategyPlanSourceLinks(item));
    const researchBadge = research.sourceCount ? `${research.sourceCount} recent signals` : 'Research: last 30 days';
    const canvasMeta = [
        formatStrategyWindowLabel(activePlan?.window || activePlan?.timeframe || 'next_7_days'),
        activePlan?.objective ? `Objective: ${String(activePlan.objective).trim()}` : '',
        activePlan?.goal ? `Goal: ${String(activePlan.goal).trim()}` : '',
    ].filter(Boolean).join(' | ');
    const canvasNote = [activePlan?.summary, research.note].filter(Boolean).join(' ');
    host.innerHTML = `
      <section class="strategy-client-group strategy-client-group--focus">
        <div class="strategy-client-group-head">
          <div>
            <div class="strategy-client-group-title">${escapeHtml(clientId.replace(/_/g, ' '))}</div>
            <div class="strategy-client-group-meta">${planCount} plan${planCount === 1 ? '' : 's'} | ${itemCount} item${itemCount === 1 ? '' : 's'} | ${researchBadge}</div>
            <div class="strategy-client-group-copy">Jarvis keeps one active canvas per client so the plan reads like a premium deck instead of a long list.</div>
          </div>
          <div class="strategy-client-group-actions">
            <button type="button" class="work-item-ghost" onclick="deleteStrategyPlansForSelectedClient('${escapeJsString(clientId)}')">Clear client plans</button>
            <button type="button" class="work-item-ghost" onclick="renderStrategyPlans()">Refresh view</button>
          </div>
        </div>
        <div class="strategy-plan-tabs">
          ${plansForClient.map(plan => {
              const planId = String(plan?.plan_id || '').trim();
              const active = planId === activePlanId;
              const title = String(plan?.summary || plan?.objective || plan?.goal || 'Untitled plan').trim();
              return `<button type="button" class="strategy-plan-tab ${active ? 'is-active' : ''}" onclick="setStrategyPlanFocus('${escapeJsString(clientId)}','${escapeJsString(planId)}')">${escapeHtml(title.length > 42 ? `${title.slice(0, 42).trim()}...` : title)} <span>${Array.isArray(plan?.items) ? plan.items.length : 0}</span></button>`;
          }).join('')}
        </div>
        <div class="strategy-plan-canvas">
          <div class="strategy-plan-canvas-head">
            <div style="min-width:0;">
              <div class="strategy-plan-canvas-kicker">
                <span class="strategy-plan-badge">${escapeHtml(researchBadge)}</span>
                <span class="strategy-plan-badge">${escapeHtml(String(activePlan?.status || 'ready').replace(/_/g, ' '))}</span>
              </div>
              <div class="strategy-plan-summary-title" style="margin-top:10px;">${escapeHtml(String(activePlan?.summary || 'Strategy plan ready.'))}</div>
              <div class="strategy-plan-summary-meta">${escapeHtml(canvasMeta)}</div>
              ${canvasNote ? `<div class="strategy-plan-plan-note">${escapeHtml(canvasNote)}</div>` : ''}
            </div>
            <div class="strategy-client-group-actions">
              <button type="button" class="orch-inline-action-btn ${String(activePlan?.status || '').toLowerCase() === 'materialized' ? 'is-quiet' : 'is-primary'}" onclick="materializeStrategyPlan('${escapeJsString(String(activePlan?.plan_id || ''))}')" ${String(activePlan?.status || '').toLowerCase() === 'materialized' ? 'disabled' : ''}>${String(activePlan?.status || '').toLowerCase() === 'materialized' ? 'Suggestions ready' : 'Materialize plan'}</button>
              <button type="button" class="work-item-ghost" onclick="deleteStrategyPlanById('${escapeJsString(String(activePlan?.plan_id || ''))}')">Delete plan</button>
              <button type="button" class="work-item-ghost" onclick="refreshStrategyMarketSignals(this)">Refresh research</button>
            </div>
          </div>
          <div class="strategy-plan-canvas-grid">
            <div class="strategy-plan-canvas-column">
              <div class="strategy-plan-canvas-label">Plan brief</div>
              <div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Timeframe:</strong> ${escapeHtml(formatStrategyWindowLabel(activePlan?.window || activePlan?.timeframe || 'next_7_days'))}</div>
              ${activePlan?.objective ? `<div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Objective:</strong> ${escapeHtml(String(activePlan.objective))}</div>` : ''}
              ${activePlan?.goal ? `<div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Goal:</strong> ${escapeHtml(String(activePlan.goal))}</div>` : ''}
              ${activePlan?.campaign_context ? `<div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Campaign context:</strong> ${escapeHtml(String(activePlan.campaign_context))}</div>` : ''}
            </div>
            <div class="strategy-plan-canvas-column">
              <div class="strategy-plan-canvas-label">Source coverage</div>
              <div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Signals:</strong> ${escapeHtml(research.sourceCount ? `${research.sourceCount} recent signals` : 'Research snapshot attached to this plan')}</div>
              <div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Freshness:</strong> ${escapeHtml(research.freshness)}</div>
              ${sourceSignals.length ? `<div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;">${sourceSignals.slice(0, 8).map(signal => `<span class="dp">${escapeHtml(String(signal))}</span>`).join('')}</div>` : ''}
            </div>
          </div>
          <div class="strategy-plan-item-grid">
            ${(activeItems.length ? activeItems : []).map((item, itemIndex) => {
                const status = String(item?.status || 'planned').toLowerCase();
                const statusTone = status === 'suggested' || status === 'materialized' ? 'var(--green)' : 'var(--amber)';
                const platforms = Array.isArray(item?.platforms) ? item.platforms.filter(Boolean).join(' + ') : '';
                const signals = getStrategyPlanSourceSignals(item);
                const itemLinks = getStrategyPlanSourceLinks(item);
                return `
                  <article class="strategy-plan-item">
                    <div class="strategy-plan-item-head">
                      <div>
                        <div class="strategy-plan-item-title">${itemIndex + 1}. ${escapeHtml(String(item?.topic || 'Untitled direction'))}</div>
                        <div class="strategy-plan-item-meta">${escapeHtml(String(item?.format || 'content'))}${platforms ? ` | ${escapeHtml(platforms)}` : ''}${item?.recommended_time ? ` | ${escapeHtml(String(item.recommended_time))}` : ''}</div>
                      </div>
                      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                        <span class="strategy-plan-status" style="color:${statusTone};">${escapeHtml(status.replace(/_/g, ' '))}</span>
                        <span style="font-size:11px; color:var(--t4); font-family:'Space Mono';">${escapeHtml(formatStrategyConfidence(item?.confidence))}</span>
                      </div>
                    </div>
                    ${item?.hook_direction ? `<div class="strategy-plan-item-copy"><strong style="color:var(--t2);">Hook:</strong> ${escapeHtml(String(item.hook_direction))}</div>` : ''}
                    ${item?.rationale ? `<div class="strategy-plan-item-copy">${escapeHtml(String(item.rationale))}</div>` : ''}
                    ${signals.length ? `<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;">${signals.map(signal => `<span class="dp">${escapeHtml(String(signal))}</span>`).join('')}</div>` : ''}
                    ${item?.needs_review ? `<div style="font-size:11px; color:var(--amber); margin-top:10px; font-family:'Space Mono'; letter-spacing:.08em; text-transform:uppercase;">Needs review before scheduling</div>` : ''}
                    ${(signals.length || itemLinks.length) ? `
                      <details class="strategy-plan-why">
                        <summary>Why now</summary>
                        <div class="strategy-plan-why-copy">${signals.length ? `Signals: ${escapeHtml(signals.join(' | '))}` : 'Jarvis attached source context to this item.'}</div>
                        ${itemLinks.length ? `<div class="strategy-plan-source-list">${itemLinks.slice(0, 3).map(link => `<a class="strategy-plan-source-link" href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label)}</a>`).join('')}</div>` : ''}
                      </details>
                    ` : ''}
                  </article>`;
            }).join('')}
          </div>
        </div>
      </section>`;
}

async function renderStrategyPlans() {
    await ensureGlobalClientsLoaded();
    populateStrategyClientOptions();
    syncStrategyPlanUiState();
    const select = document.getElementById('strategy-client');
    const host = document.getElementById('strategy-plan-list');
    if(!host) return;
    const clientId = String(select?.value || '').trim();
    try {
        let url = buildApiUrl('/api/strategy/plans');
        if(clientId) url += `?client_id=${encodeURIComponent(clientId)}`;
        const res = await fetch(url);
        const data = await res.json();
        if(!res.ok || data.status !== 'success') throw new Error(data.reason || 'Failed to load strategy plans.');
        strategyPlansCache = Array.isArray(data.plans) ? data.plans : [];
        renderStrategyPlanCards(strategyPlansCache);
    } catch(err) {
        host.innerHTML = `<div class="strategy-plan-empty" style="color:var(--red);">${escapeHtml(err?.message || 'Failed to load strategy plans.')}</div>`;
    }
}

async function refreshStrategyMarketSignals(button = null) {
    await buildStrategyPlan(button, { mode: 'refresh' });
}

async function buildStrategyPlan(triggerButton = null, options = {}) {
    await ensureGlobalClientsLoaded();
    populateStrategyClientOptions();
    const clientId = String(document.getElementById('strategy-client')?.value || '').trim();
    const windowName = String(document.getElementById('strategy-window')?.value || 'next_7_days').trim();
    const goal = String(document.getElementById('strategy-goal')?.value || '').trim();
    const campaignContext = String(document.getElementById('strategy-context')?.value || '').trim();
    const statusNode = document.getElementById('strategy-status');
    const buildBtn = triggerButton && triggerButton.tagName === 'BUTTON' ? triggerButton : document.getElementById('strategy-build-btn');
    const refreshBtn = document.getElementById('strategy-refresh-signals-btn');
    if(!clientId) {
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--amber);">Pick a client first so Jarvis knows which brand it is planning for.</span>`;
        toast('Pick a client first.', 'warn');
        return;
    }
    const loadingSource = String(options.mode || 'build');
    setStrategyPlannerBusy(true, loadingSource);
    startStrategyLoadingSequence(loadingSource);
    if(statusNode) {
        statusNode.innerHTML = `<strong style="color:var(--t1);">${loadingSource === 'refresh' ? 'Refreshing market signals...' : 'Building the strategy plan...'}</strong><br/><span style="color:var(--t3);">Jarvis is reading the brand, checking recent signals, and shaping the editorial direction.</span>`;
    }
    try {
        const res = await fetch(buildApiUrl('/api/strategy/plans'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId, window: windowName, goal, campaign_context: campaignContext }),
        });
        const data = await res.json();
        if(!res.ok || data.status !== 'success') throw new Error(data.reason || 'Jarvis could not build the strategy plan.');
        stopStrategyLoadingSequence(true, 'Strategy plan saved. Jarvis kept it as planned work, not a live schedule.');
        toast('Strategy plan ready.', 'success');
        await renderStrategyPlans();
    } catch(err) {
        stopStrategyLoadingSequence(false, err?.message || 'Jarvis could not build the strategy plan.');
        toast(err?.message || 'Jarvis could not build the strategy plan.', 'error');
    } finally {
        setStrategyPlannerBusy(false);
        if(buildBtn) restoreButtonBusy(buildBtn);
        if(refreshBtn) restoreButtonBusy(refreshBtn);
    }
}

async function materializeStrategyPlan(planId) {
    const statusNode = document.getElementById('strategy-status');
    try {
        const res = await fetch(buildApiUrl(`/api/strategy/plans/${encodeURIComponent(planId)}/materialize`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();
        if(!res.ok || data.status !== 'success') throw new Error(data.reason || 'Jarvis could not materialize the strategy suggestions.');
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--green);">Strategy suggestions are ready for operator review. They were not auto-scheduled.</span>`;
        toast('Strategy suggestions materialized.', 'success');
        await renderStrategyPlans();
    } catch(err) {
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--red);">${escapeHtml(err?.message || 'Jarvis could not materialize the strategy plan.')}</span>`;
        toast(err?.message || 'Jarvis could not materialize the strategy plan.', 'error');
    }
}

async function deleteStrategyPlanById(planId) {
    const normalizedPlanId = String(planId || '').trim();
    const statusNode = document.getElementById('strategy-status');
    if(!normalizedPlanId) return;
    showConfirm('Delete this strategy plan? This only removes the saved plan, not any live scheduled content.', async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/strategy/plans/${encodeURIComponent(normalizedPlanId)}`), {
                method: 'DELETE',
            });
            const data = await res.json();
            if(!res.ok || data.status !== 'success') throw new Error(data.reason || 'Jarvis could not delete the strategy plan.');
            removeStrategyPlanFromLocalState(normalizedPlanId);
            renderStrategyPlanCards(strategyPlansCache);
            if(statusNode) statusNode.innerHTML = `<span style="color:var(--green);">Strategy plan removed.</span>`;
            showNotification('Strategy Plan Deleted', 'Jarvis removed the saved plan from the workspace. Live scheduled content was not touched.', false, { position: 'bottom-right' });
            renderStrategyPlans().catch(() => null);
        } catch(err) {
            if(statusNode) statusNode.innerHTML = `<span style="color:var(--red);">${escapeHtml(err?.message || 'Jarvis could not delete the strategy plan.')}</span>`;
            showNotification('Delete Failed', err?.message || 'Jarvis could not delete the strategy plan.', true, { position: 'bottom-right' });
        }
    }, {
        tone: 'danger',
        title: 'Delete Strategy Plan',
        confirmLabel: 'Delete plan',
        iconHtml: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke=\"currentColor\" stroke-width=\"2\"><path d=\"M3 6h18\"></path><path d=\"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\"></path><path d=\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6\"></path><path d=\"M10 11v6\"></path><path d=\"M14 11v6\"></path></svg>'
    });
}

async function deleteStrategyPlansForSelectedClient(clientOverride = '') {
    const select = document.getElementById('strategy-client');
    const statusNode = document.getElementById('strategy-status');
    const clientId = String(clientOverride || select?.value || '').trim();
    if(!clientId) {
        if(statusNode) statusNode.innerHTML = `<span style="color:var(--amber);">Pick a client first, or use the client group actions to clear plans.</span>`;
        toast('Pick a client first.', 'warn');
        return;
    }
    showConfirm(`Delete all saved strategy plans for ${clientId.replace(/_/g, ' ')}? This will not touch any live scheduled posts.`, async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/strategy/plans?client_id=${encodeURIComponent(clientId)}`), {
                method: 'DELETE',
            });
            const data = await res.json();
            if(!res.ok || data.status !== 'success') throw new Error(data.reason || 'Jarvis could not clear the client plans.');
            const removedCount = removeStrategyClientPlansFromLocalState(clientId) || Number(data.removed || 0);
            renderStrategyPlanCards(strategyPlansCache);
            if(statusNode) statusNode.innerHTML = `<span style="color:var(--green);">Removed ${removedCount} saved strategy plan${removedCount === 1 ? '' : 's'} for ${escapeHtml(clientId.replace(/_/g, ' '))}.</span>`;
            showNotification('Client Plans Cleared', `Jarvis removed ${removedCount} saved plan${removedCount === 1 ? '' : 's'} for ${clientId.replace(/_/g, ' ')}.`, false, { position: 'bottom-right' });
            renderStrategyPlans().catch(() => null);
        } catch(err) {
            if(statusNode) statusNode.innerHTML = `<span style="color:var(--red);">${escapeHtml(err?.message || 'Jarvis could not clear the client plans.')}</span>`;
            showNotification('Delete Failed', err?.message || 'Jarvis could not clear the client plans.', true, { position: 'bottom-right' });
        }
    }, {
        tone: 'danger',
        title: 'Clear Client Plans',
        confirmLabel: 'Clear plans',
        iconHtml: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke=\"currentColor\" stroke-width=\"2\"><path d=\"M3 6h18\"></path><path d=\"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\"></path><path d=\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6\"></path><path d=\"M10 11v6\"></path><path d=\"M14 11v6\"></path></svg>'
    });
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
                populateOrchestratorComposerClients();
            }
        } catch(e) {}
    }
    if(!globalClients.length) {
        grid.innerHTML = `<div class="hq-empty-state">No client vaults are available yet. Add a client first.</div>`;
        return;
    }
    const visibleClients = getFilteredClients();
    if(!visibleClients.length) {
        grid.innerHTML = `<div class="hq-empty-state">No client matched your current search.</div>`;
        return;
    }

    const renderVaultFolderCards = (counts) => {
        const normalizedCounts = counts || {};
        grid.innerHTML = '';
        for(const c of visibleClients) {
        const amount = normalizedCounts[c] || 0;
        const isDeleting = deletingClientIds.has(c);
        let folder = document.createElement('div');
        folder.className = `v-folder reveal-3d${isDeleting ? ' client-vault-pending' : ''}`;
        folder.dataset.clientId = c;
        folder.innerHTML = `
            <div class="v-f-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </div>
            <div class="v-f-name">${c}</div>
            <div class="v-f-stat" id="stat-${c}">${isDeleting ? 'Removing client and clearing vaulted assets...' : `${amount} items securely vaulted. Drop files to isolate.`}</div>
        `;
        if(isDeleting) {
            folder.style.opacity = '0.45';
            folder.style.pointerEvents = 'none';
        }
        
        folder.addEventListener('dragover', (e) => { e.preventDefault(); folder.classList.add('drag-over'); });
        folder.addEventListener('dragleave', (e) => { e.preventDefault(); folder.classList.remove('drag-over'); });
        folder.addEventListener('drop', (e) => {
            e.preventDefault(); folder.classList.remove('drag-over');
            if(isDeleting) return;
            if(e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleBulkDrop(c, e.dataTransfer.files, `stat-${c}`);
            }
        });
        
        folder.onclick = () => { if(!isDeleting) openVaultModal(c); };
        
        grid.appendChild(folder);
        }
    };

    renderVaultFolderCards(clientVaultCounts);

    const requestToken = ++activeVaultGridRequestToken;
    let counts = {};
    try {
        const res = await fetch(buildApiUrl("/api/vaults"));
        const data = await res.json();
        if(data.status === "success") counts = data.vaults;
    } catch(e){}
    if(requestToken !== activeVaultGridRequestToken) return;
    clientVaultCounts = counts || {};
    renderVaultFolderCards(clientVaultCounts);
    syncClientAssetBadges();
}

async function refreshClientWorkspaceViews() {
    await refreshGlobalClients();
    await Promise.allSettled([
        renderConfigCards(),
        renderVaults(),
    ]);
}

async function handleBulkDrop(clientId, fileList, statId) {
    markClientWorkspaceInteraction(30000);
    activeVaultUploadCount += 1;
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
            clearVaultCache(clientId);
            if(statNode) statNode.innerHTML = `<span style="color:var(--green)">Synced ${data.uploaded_paths.length} physically to disk.</span>`;
            const now = new Date();
            const timeStr = String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
            appendLog(timeStr, `<strong>SYSTEM</strong> Â· Batch uploaded ${data.uploaded_paths.length} elements to [${clientId}] vault.`, "green");
            await renderVaults();
            if(currentVaultClient === clientId) {
                await loadVaultAssetsData(true);
                await loadVaultDraftsData(true);
            }
        } else {
             if(statNode) statNode.innerHTML = `<span style="color:var(--red)">Upload rejected.</span>`;
             showNotification('Upload Rejected', data.reason || 'Jarvis could not store those files.', true);
        }
    } catch(e) {
        if(statNode) statNode.innerHTML = `<span style="color:var(--red)">Failed connection.</span>`;
        showNotification('Upload Failed', e?.message || 'Jarvis could not reach the upload endpoint.', true);
    } finally {
        activeVaultUploadCount = Math.max(0, activeVaultUploadCount - 1);
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
                populateOrchestratorComposerClients();
            }
        } catch(e) {}
    }
    if(!globalClients.length) {
        grid.innerHTML = `<div class="hq-empty-state">No client profiles are available yet. Add a client first.</div>`;
        return;
    }
    const visibleClients = getFilteredClients();
    if(!visibleClients.length) {
        grid.innerHTML = `<div class="hq-empty-state">No client matched your current search.</div>`;
        return;
    }
    await refreshClientWorkspaceData();
    grid.innerHTML = '';
    
    for(const c of visibleClients) {
        const isDeleting = deletingClientIds.has(c);
        const workspaceStatus = getClientWorkspaceStatus(c);
        const badgeMarkup = isDeleting
            ? `<span class="badge b-am">Removing Client</span>`
            : `
                <span id="cfg-health-profile-${c}" class="badge ${workspaceStatus.profileClass}">${workspaceStatus.profileText}</span>
                <span id="cfg-health-creds-${c}" class="badge ${workspaceStatus.credsClass}">${workspaceStatus.credsText}</span>
                <span id="cfg-health-drafts-${c}" class="badge b-am">Assets ${clientVaultCounts[c] || 0}</span>
            `;
        let card = document.createElement('div');
        card.className = `v-folder reveal-3d${isDeleting ? ' client-card-pending-delete' : ''}`;
        card.dataset.clientId = c;
        card.innerHTML = `
            <button class="client-card-delete-btn" onclick="event.stopPropagation(); deleteClientProfile('${c}')" title="Remove client" ${isDeleting ? 'disabled' : ''} style="position:absolute; top:14px; right:14px; width:30px; height:30px; border-radius:50%; border:1px solid rgba(224,85,85,.28); background:rgba(224,85,85,.12); color:var(--red); display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:18px; line-height:1; z-index:2; transition:all .2s;" onmouseover="this.style.background='rgba(224,85,85,.2)'" onmouseout="this.style.background='rgba(224,85,85,.12)'">${isDeleting ? '…' : '&times;'}</button>
            <div class="v-f-icon" style="background:rgba(47,168,224,.15); color:var(--blue);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="v-f-name">${c}</div>
            <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px;">
                ${badgeMarkup}
            </div>
            <div class="v-f-stat" style="margin-bottom:12px;">${isDeleting ? 'Removing client, drafts, approvals, schedules, and reports...' : 'Tap a section below to expand'}</div>
            
            <!-- TWO COLLAPSIBLE BUTTONS -->
            <div style="display:flex; gap:8px; margin-bottom:4px;">
                <button id="btn-details-${c}" onclick="event.stopPropagation(); toggleConfigSection('${c}','details')" ${isDeleting ? 'disabled' : ''} style="flex:1; padding:8px 0; border-radius:8px; border:1px solid rgba(139,108,247,.2); background:rgba(139,108,247,.08); color:var(--purple); font-size:11px; font-weight:600; cursor:pointer; font-family:'Space Mono'; transition:all .2s;">Client Details</button>
                <button id="btn-creds-${c}" onclick="event.stopPropagation(); toggleConfigSection('${c}','creds')" ${isDeleting ? 'disabled' : ''} style="flex:1; padding:8px 0; border-radius:8px; border:1px solid rgba(47,168,224,.2); background:rgba(47,168,224,.08); color:var(--blue); font-size:11px; font-weight:600; cursor:pointer; font-family:'Space Mono'; transition:all .2s;">Live Credentials</button>
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
                        <input class="qin" id="cfg-business-${c}" placeholder="Harbor Pilates" />
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
                <input class="qin" id="cfg-services-${c}" placeholder="reformer sessions, private coaching, posture workshops" style="margin-bottom:10px;" />
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
                        <input class="qin" id="cfg-seo-${c}" placeholder="reformer pilates, private studio sessions, posture coaching..." />
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
        if(isDeleting) {
            card.style.pointerEvents = 'none';
        }
        grid.appendChild(card);
        if(isDeleting) continue;
        if(!applyClientWorkspaceData(c, workspaceStatus.payload)) {
            loadClientProfile(c);
        }
        applyConfigSectionVisualState(c, clientWorkspaceSectionState[c], { skipLoad: true });
    }
}

function toggleConfigSection(clientId, section) {
    markClientWorkspaceInteraction(20000);
    const current = clientWorkspaceSectionState[clientId] || '';
    const next = current === section ? '' : section;
    applyConfigSectionVisualState(clientId, next);
}

async function loadClientProfile(clientId, force = false) {
    try {
        if(!force && applyClientWorkspaceData(clientId)) {
            return;
        }
        const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(clientId)));
        const data = await res.json();
        if(!res.ok || data.status === 'error') {
            throw new Error(data.reason || `Failed to load ${clientId}.`);
        }
        upsertClientWorkspaceData(data);
        applyClientWorkspaceData(clientId, data);
    } catch(e) {
        const detailStatus = document.getElementById('cfg-det-status-' + clientId);
        const credsStatus = document.getElementById('cfg-status-' + clientId);
        if(detailStatus) detailStatus.innerHTML = '<span style="color:var(--red)">Failed to load profile.</span>';
        if(credsStatus) credsStatus.innerHTML = '<span style="color:var(--red)">Failed to load credentials.</span>';
    }
}

async function loadClientDetails(c) {
    await loadClientProfile(c, true);
}

async function loadClientCreds(c) {
    await loadClientProfile(c, true);
}

function getClientNodes(clientId) {
    return Array.from(document.querySelectorAll('[data-client-id]')).filter(node => node.dataset.clientId === clientId);
}

function setClientRemovalState(clientId, pending) {
    getClientNodes(clientId).forEach(node => {
        node.classList.toggle('client-card-pending-delete', pending);
        if(pending) node.classList.remove('client-card-removing');
        node.style.pointerEvents = pending ? 'none' : '';
        const stat = node.querySelector('.v-f-stat');
        if(stat) {
            stat.textContent = pending
                ? 'Removing client, drafts, approvals, schedules, and reports...'
                : 'Tap a section below to expand';
        }
        const button = node.querySelector('.client-card-delete-btn');
        if(button) {
            button.disabled = pending;
            button.textContent = pending ? '…' : '×';
        }
    });
}

function animateClientRemoval(clientId) {
    getClientNodes(clientId).forEach(node => node.classList.add('client-card-removing'));
}

async function deleteClientProfile(clientId) {
    showConfirm(`Remove ${clientId} completely? This will delete the client profile, brand memory, vault assets, pending approvals, and scheduled jobs for this client.`, async () => {
        if(deletingClientIds.has(clientId)) return;
        deletingClientIds.add(clientId);
        setClientRemovalState(clientId, true);
        renderVaults().catch(() => null);
        showNotification('Removing Client', `Jarvis is clearing ${clientId} across vaults, drafts, approvals, schedules, and reports.`, false, {
            state: 'pending',
            accent: 'var(--amber)',
            rgb: '244,211,138',
            duration: 5200,
            position: 'bottom-right'
        });
        try {
            const res = await fetch(buildApiUrl('/api/client/' + encodeURIComponent(clientId)), {
                method: 'DELETE'
            });
            const data = await res.json();
            if(res.ok && data.status === 'success') {
                animateClientRemoval(clientId);
                globalClients = globalClients.filter(c => c !== clientId);
                delete clientWorkspaceDataCache[clientId];
                delete clientVaultCounts[clientId];
                populatePipelineSelectors(globalClients);
                populateOrchestratorComposerClients();
                if(currentVaultClient === clientId) closeVaultModal();
                setTimeout(() => {
                    try{ renderConfigCards(); } catch(e){}
                    try{ renderVaults(); } catch(e){}
                }, 220);
                try{ renderSchedule(); } catch(e){}
                try{ renderDashboardSummary(); } catch(e){}
                showNotification('Client Removed', `${clientId} and its saved local state were fully removed from Jarvis.`, false, {
                    accent: 'var(--red)',
                    rgb: '224,85,85',
                    duration: 7200,
                    position: 'bottom-right'
                });
            } else {
                deletingClientIds.delete(clientId);
                setClientRemovalState(clientId, false);
                try{ renderConfigCards(); } catch(e){}
                renderVaults().catch(() => null);
                showNotification('Delete Rejected', data.reason || 'Jarvis could not remove this client cleanly.', true, { position: 'bottom-right' });
            }
        } catch(e) {
            deletingClientIds.delete(clientId);
            setClientRemovalState(clientId, false);
            try{ renderConfigCards(); } catch(err){}
            renderVaults().catch(() => null);
            showNotification('Delete Failed', 'Connection failed while removing the client.', true, { position: 'bottom-right' });
            return;
        }
        deletingClientIds.delete(clientId);
    });
}

async function saveClientDetails(clientId) {
    markClientWorkspaceInteraction(20000);
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
        });
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            upsertClientWorkspaceData(data.client || {
                ...(clientWorkspaceDataCache[clientId] || { client_id: clientId }),
                profile_json: profileUpdate.profile_json
            });
            applyClientWorkspaceData(clientId);
            statusEl.innerHTML = '<span style="color:#1fce9f; font-size:14px; font-weight:600;">Saved</span>';
            showNotification('Profile Updated', 'Brand details saved for ' + clientId, false);
            returnViewportToTop();
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
    markClientWorkspaceInteraction(20000);
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
            upsertClientWorkspaceData(data.client || {
                ...(clientWorkspaceDataCache[clientId] || { client_id: clientId }),
                phone_number: phone,
                meta_access_token: token,
                facebook_page_id: fb,
                instagram_account_id: ig
            });
            applyClientWorkspaceData(clientId);
            statusEl.innerHTML = `<span style="color:#1fce9f; font-size:14px; font-weight:600;">✓ Updated: ${changedLabels.join(', ')}</span>`;
            showNotification('Config Saved', changedLabels.join(', ') + ' refreshed for ' + clientId, false);
            window._cfgOriginal[clientId] = { phone_number: phone, meta_access_token: token, facebook_page_id: fb, instagram_account_id: ig };
            returnViewportToTop();
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
let currentClientProfileRequest = null;
let currentClientValueBrief = null;
let activeCaptionStudioRequestToken = 0;
let currentCaptionStudioOpenMeta = null;
let activeVaultAssetsRequestToken = 0;
let activeVaultDraftsRequestToken = 0;

async function uploadVaultBatch(clientId, files, phaseLabel) {
    if(!clientId || !files || !files.length) return null;
    const formData = new FormData();
    formData.append("client_id", clientId);
    for (const file of files) {
        formData.append("files", file);
    }
    const res = await fetch(buildApiUrl("/api/upload-bulk"), { method: "POST", body: formData });
    const data = await res.json().catch(() => ({ status: 'error', reason: `Upload failed with HTTP ${res.status}.` }));
    if(data.status !== "success") {
        throw new Error(data.reason || `${phaseLabel} upload failed.`);
    }
    return data;
}

async function handleVaultUpload(source) {
    if(!currentVaultClient) return;
    markClientWorkspaceInteraction(30000);
    activeVaultUploadCount += 1;
    const input = source && source.files ? source : document.getElementById('vault-file-upload');
    const files = input && input.files ? input.files : null;
    if(!files || files.length === 0) return;

    const clientId = currentVaultClient;
    const allFiles = Array.from(files);
    const imageFiles = allFiles.filter(file => {
        const type = String(file.type || '').toLowerCase();
        return type.startsWith('image/');
    });
    const videoFiles = allFiles.filter(file => {
        const type = String(file.type || '').toLowerCase();
        return type.startsWith('video/');
    });
    const otherFiles = allFiles.filter(file => !imageFiles.includes(file) && !videoFiles.includes(file));
    const orderedBatches = [];
    if(imageFiles.length) orderedBatches.push({ label: 'image', files: imageFiles });
    if(videoFiles.length) orderedBatches.push({ label: 'video', files: videoFiles });
    if(otherFiles.length) orderedBatches.push({ label: 'asset', files: otherFiles });

    const nameEl = document.getElementById('modal-client-name');
    const oldName = nameEl.innerText;
    nameEl.innerHTML = `<span style="color:var(--amber)">Uploading ${files.length} assets...</span>`;
    
    try {
        let uploadedCount = 0;
        for (const batch of orderedBatches) {
            if (clientId !== currentVaultClient) break;
            nameEl.innerHTML = `<span style="color:var(--amber)">Uploading ${uploadedCount + batch.files.length} of ${allFiles.length} assets...</span>`;
            const data = await uploadVaultBatch(clientId, batch.files, batch.label);
            uploadedCount += Array.isArray(data.uploaded_paths) ? data.uploaded_paths.length : batch.files.length;
            if (clientId === currentVaultClient) {
                mergeUploadedAssetsIntoVault(clientId, data.assets || []);
                nameEl.innerHTML = `<span style="color:var(--amber)">${batch.label === 'image' ? 'Images' : 'Assets'} ready. Syncing vault...</span>`;
                clearVaultCache(clientId);
                loadVaultAssetsData(true).catch(() => null);
                loadVaultDraftsData(true).catch(() => null);
            }
            if (batch.label === 'image' && videoFiles.length && clientId === currentVaultClient) {
                nameEl.innerHTML = `<span style="color:var(--amber)">Images ready. Processing ${videoFiles.length} video${videoFiles.length === 1 ? '' : 's'}...</span>`;
            }
        }
        renderVaults().catch(() => null);
        showNotification('Upload Complete', `${uploadedCount} assets secured in vault.`, false);
    } catch(e) {
        showNotification('Upload Error', e?.message || 'Could not connect to server.', true);
    } finally {
        activeVaultUploadCount = Math.max(0, activeVaultUploadCount - 1);
    }
    
    if(input) input.value = '';
    nameEl.innerText = (currentVaultClient || clientId) + " Vault";
}

async function openVaultModal(clientId) {
    markClientWorkspaceInteraction(30000);
    const resolvedClientId = resolveWorkspaceClientId(clientId);
    const previousVaultClient = currentVaultClient;
    currentVaultClient = resolvedClientId;
    if(previousVaultClient !== currentVaultClient && currentClientProfile?._clientId !== currentVaultClient) {
        currentClientProfile = null;
        currentClientProfileRequest = null;
    }
    editingDraftName = null;
    logCaptionStudioTiming('vault_modal_visible', performance.now(), { client: currentVaultClient });

    document.getElementById('modal-client-name').innerText = currentVaultClient + " Vault";
    document.getElementById('vault-modal').style.display = 'flex';
    switchVaultTab('assets');
    selectedVaultImages.clear();
    updateSelectionFooter();

    const cachedAssets = vaultAssetsCache[currentVaultClient];
    const cachedDrafts = vaultDraftsCache[currentVaultClient];

    currentVaultFiles = Array.isArray(cachedAssets?.files) ? cachedAssets.files : [];
    currentVaultBundles = cachedDrafts?.bundles || {};

    if(currentVaultFiles.length) renderVaultGrid(getAvailableVaultFiles());
    else renderVaultAssetSkeleton();

    if(cachedDrafts?.bundles) {
        renderVaultBundles();
        document.getElementById('bundle-count').innerText = getVisibleBundleKeys().length;
    } else {
        document.getElementById('bundle-count').innerText = '0';
        renderVaultDraftsPlaceholder();
    }

    loadVaultAssetsData(!cachedAssets).catch(() => null);
    loadVaultDraftsData(!cachedDrafts).catch(() => null);
    primeClientProfileForStudio(currentVaultClient);
}


function closeVaultModal() {
    document.getElementById('vault-modal').style.display = 'none';
    closeCaptionStudio();
    currentVaultClient = null;
    selectedVaultImages.clear();
    editingDraftName = null;
    markClientWorkspaceInteraction(3000);
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
    await Promise.allSettled([
        loadVaultAssetsData(forceRefresh),
        loadVaultDraftsData(forceRefresh),
    ]);
}

async function loadVaultAssetsData(forceRefresh = false) {
    if(!currentVaultClient) return;
    const clientId = resolveWorkspaceClientId(currentVaultClient);
    currentVaultClient = clientId;
    const requestToken = ++activeVaultAssetsRequestToken;
    const knownAssetCount = Number(clientVaultCounts[clientId] || 0);
    try {
        const data = await fetchVaultAssets(clientId, { forceRefresh });
        if(requestToken !== activeVaultAssetsRequestToken || clientId !== currentVaultClient) return;
        if(data.status === 'success') {
            currentVaultFiles = data.files || [];
            if(!currentVaultFiles.length && knownAssetCount > 0) {
                renderVaultFetchFailure(clientId, `Jarvis expected ${knownAssetCount} asset${knownAssetCount === 1 ? '' : 's'} here, but the current vault response came back empty.`, { knownAssetCount });
                return;
            }
            renderVaultGrid(getAvailableVaultFiles());
        }
    } catch(e) {
        if(requestToken !== activeVaultAssetsRequestToken || clientId !== currentVaultClient) return;
        if(!currentVaultFiles.length) {
            renderVaultFetchFailure(clientId, e?.message || 'Jarvis could not load this vault right now.', { knownAssetCount });
        } else {
            renderVaultGrid(getAvailableVaultFiles());
        }
        showNotification("Vault Error", "Could not load assets for " + clientId + ". " + (e.message || ""), true);
    }
}

async function loadVaultDraftsData(forceRefresh = false) {
    if(!currentVaultClient) return;
    const clientId = currentVaultClient;
    const requestToken = ++activeVaultDraftsRequestToken;
    delete draftMentionCache[clientId];
    try {
        const data = await fetchVaultDrafts(clientId, { forceRefresh });
        if(requestToken !== activeVaultDraftsRequestToken || clientId !== currentVaultClient) return;
        if(data.status === 'success') {
            currentVaultBundles = data.bundles || {};
            document.getElementById('bundle-count').innerText = getVisibleBundleKeys().length;
            renderCurrentVaultState();
        }
    } catch(e) {
        if(requestToken !== activeVaultDraftsRequestToken || clientId !== currentVaultClient) return;
        currentVaultBundles = {};
        renderVaultBundles();
        document.getElementById('bundle-count').innerText = "0";
        showNotification("Vault Error", "Could not load drafts for " + clientId + ". " + (e.message || ""), true);
    }
}

function renderVaultGrid(files) {
    const grid = document.getElementById('modal-grid');
    grid.innerHTML = '';
    
    if(files.length === 0) {
        grid.innerHTML = '<div style="color:var(--t3); grid-column:1/-1; padding:20px; text-align:center;">No available assets right now. Upload more media to start a new creative draft.</div>';
        return;
    }
    
    files.forEach((fObj, index) => {
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
        
        const warningBadge = !isValid ? renderInstagramLimitBadge(warning) : '';
        const warningNote = !isValid ? renderInstagramLimitNote(warning, { subtle: true }) : '';
        
        let discardBtn = `<button onclick="event.stopPropagation(); deleteVaultImage('${safeFile}')" class="vault-media-delete-btn" title="Delete Media">×</button>`;
        let repairBtn = '';
        if(canRepairMeta) {
            repairBtn = `<button onclick="event.stopPropagation(); repairVaultVideoForMeta('${safeFile}')" class="vault-media-repair-btn" title="Repair this video for Meta">Repair</button>`;
        }
        
        const kindBadge = kind === 'video'
            ? `<div class="vault-media-kind-badge">Video</div>`
            : '';
        const fileLabel = `<div class="v-item-title">${escapeHtml(f)}</div>`;
        const fallback = `<div class="vault-preview-fallback" style="display:none;">Preview unavailable</div>`;
        const skeleton = `<div class="vault-media-skeleton"></div>`;
        const sharedImgAttrs = `loading="${index < 4 ? 'eager' : 'lazy'}" decoding="async" fetchpriority="${index < 2 ? 'high' : 'auto'}" width="240" height="240" onload="const tile=this.closest('.v-item'); if(tile) tile.classList.add('is-loaded');" onerror="this.style.display='none'; const media=this.closest('.v-item-media'); const fb=media && media.querySelector('.vault-preview-fallback'); if(fb) fb.style.display='flex'; if(media) media.parentElement.classList.add('is-loaded');"`;
        const mediaPreview = kind === 'video'
            ? (posterUrl
                ? `<img src="${posterUrl}" alt="${escapeHtml(f)}" ${sharedImgAttrs} style="${!isValid ? 'border:1px solid var(--red)' : ''}" />${fallback}`
                : `<div class="vault-video-preview-fallback" style="${!isValid ? 'border:1px solid var(--red);' : ''}">Video ready</div>`)
            : `<img src="${previewUrl}" alt="${escapeHtml(f)}" ${sharedImgAttrs} style="${!isValid ? 'border:1px solid var(--red)' : ''}" />${fallback}`;
        div.innerHTML = `
            ${discardBtn}
            ${repairBtn}
            <div class="v-item-media">
                ${skeleton}
                ${warningBadge}
                ${kindBadge}
                ${mediaPreview}
            </div>
            <div class="v-item-footer">
                ${fileLabel}
                ${warningNote}
            </div>
        `;
        grid.appendChild(div);
    });
}

async function deleteVaultImage(filename) {
    showConfirm(`Are you sure you want to permanently delete '${filename}' from the vault? This cannot be undone.`, async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/${encodeURIComponent(filename)}`), { method: 'DELETE' });
            const data = await res.json();
            if(data.status === 'success') {
                clearVaultCache(currentVaultClient);
                selectedVaultImages.delete(filename);
                updateSelectionFooter();
                await loadVaultAssetsData(true);
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
                clearVaultCache(currentVaultClient);
                await loadVaultAssetsData(true);
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
        .replace(/'/g, "\\'")
        .replace(/\r?\n/g, ' ');
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

async function loadClientProfileForStudio(clientId = currentVaultClient) {
    const resolvedClientId = resolveWorkspaceClientId(clientId || currentVaultClient);
    if(!resolvedClientId) return { _clientId: '', profile_json: {} };
    if(currentClientProfile && currentClientProfile._clientId === resolvedClientId && !currentClientProfile._isFallback) {
        return currentClientProfile;
    }
    const cachedWorkspaceProfile = clientWorkspaceDataCache[resolvedClientId];
    if(cachedWorkspaceProfile) {
        currentClientProfile = {
            ...cachedWorkspaceProfile,
            _clientId: resolvedClientId,
            _isFallback: false,
        };
        return currentClientProfile;
    }
    if(currentClientProfileRequest && currentClientProfileRequest.clientId === resolvedClientId) {
        return currentClientProfileRequest.promise;
    }
    const promise = (async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/client/${encodeURIComponent(resolvedClientId)}`));
            const data = await res.json();
            if(data && !data.reason) {
                const payload = {
                    ...data,
                    _clientId: resolvedClientId,
                    _isFallback: false,
                };
                currentClientProfile = payload;
                upsertClientWorkspaceData({ ...data, client_id: resolvedClientId });
                return payload;
            }
        } catch(e) {}
        const fallback = { _clientId: resolvedClientId, profile_json: {}, _isFallback: true };
        currentClientProfile = fallback;
        return fallback;
    })().finally(() => {
        if(currentClientProfileRequest?.clientId === resolvedClientId) currentClientProfileRequest = null;
    });
    currentClientProfileRequest = { clientId: resolvedClientId, promise };
    return promise;
}

function primeClientProfileForStudio(clientId) {
    loadClientProfileForStudio(clientId).catch(() => null);
}

function logCaptionStudioTiming(stage, startedAt, meta = {}) {
    try {
        const duration = Number((performance.now() - startedAt).toFixed(1));
        const payload = { stage, duration_ms: duration, ...meta };
        window.__jarvisUiTimings = Array.isArray(window.__jarvisUiTimings) ? window.__jarvisUiTimings : [];
        window.__jarvisUiTimings.push(payload);
        if(window.__jarvisUiTimings.length > 60) window.__jarvisUiTimings.shift();
        console.debug('[JarvisTiming]', payload);
    } catch(e) {}
}

function getCaptionStudioProfileSnapshot(profile) {
    const profileJson = profile?.profile_json || {};
    const brandVoice = profileJson.brand_voice || {};
    const toneSummary = Array.isArray(brandVoice.tone)
        ? brandVoice.tone.join(', ')
        : (brandVoice.tone || (Array.isArray(profileJson.tone) ? profileJson.tone.join(', ') : (profileJson.tone || '')));
    const voiceStyle = brandVoice.style || profileJson.style || '';
    const voiceSummary = [toneSummary, voiceStyle].filter(Boolean).join(' | ') || 'Voice profile still needs detail';
    const identity = profileJson.identity || 'Add a short brand identity summary in Client Config so Jarvis writes like this business, not a generic page.';
    const seoBank = Array.isArray(profileJson.seo_keywords) ? profileJson.seo_keywords.slice(0, 5).join(' | ') : '';
    const rules = Array.isArray(profileJson.dos_and_donts) ? profileJson.dos_and_donts.slice(0, 3) : [];
    const examples = Array.isArray(profileJson.brand_voice_examples) ? profileJson.brand_voice_examples.slice(0, 2) : [];
    const dos = [...rules, ...examples].join(' | ');
    const audience = profileJson.target_audience || 'Add the ideal buyer in Client Config so Jarvis writes to the right audience.';
    return {
        profileJson,
        voiceSummary,
        identity,
        seoBank: seoBank || 'Add 3-10 search phrases in Client Config so Jarvis can anchor the copy around real keywords.',
        dos: dos || 'Add 3-5 brand voice examples plus copy rules in Client Config so Jarvis can match the voice more precisely.',
        audience,
    };
}

function renderCaptionStudioAssetStrip(bundle) {
    const strip = document.getElementById('caption-studio-asset-strip');
    if(!strip) return;
    const files = Array.isArray(bundle?.files) ? bundle.files.slice(0, 4) : [];
    if(!files.length) {
        strip.innerHTML = `<div class="caption-studio-asset-fallback" style="width:100%; max-width:160px;">No media yet</div>`;
        return;
    }
    strip.innerHTML = files.map((fileName, index) => {
        const fileMeta = currentVaultFiles.find(item => (typeof item === 'string' ? item : item?.filename) === fileName) || fileName;
        const kind = typeof fileMeta === 'string' ? 'image' : (fileMeta?.kind || 'image');
        const thumbUrl = kind === 'video'
            ? getVaultAssetPosterUrl(currentVaultClient, fileMeta)
            : getVaultAssetPreviewUrl(currentVaultClient, fileMeta);
        if(thumbUrl) {
            return `<div class="caption-studio-asset-thumb"><img src="${thumbUrl}" alt="${escapeHtml(fileName)}" loading="${index < 2 ? 'eager' : 'lazy'}" decoding="async" /></div>`;
        }
        return `<div class="caption-studio-asset-fallback">${kind === 'video' ? 'Video' : 'Preview'}</div>`;
    }).join('');
}

function bindCaptionStudioInputs(bundleName, bundle) {
    const topicInput = document.getElementById('caption-studio-topic');
    const seoInput = document.getElementById('caption-studio-seo');
    const hashtagsInput = document.getElementById('caption-studio-hashtags');
    const textarea = document.getElementById('caption-studio-text');
    const initialSuggestedAngle = buildSuggestedCampaignAngle(bundleName, bundle, {});
    topicInput.dataset.seedMode = isGenericDraftTopic(bundleName, bundle.topic_hint) ? 'generic' : 'custom';
    topicInput.dataset.lastSuggestedAngle = initialSuggestedAngle;
    topicInput.value = topicInput.dataset.seedMode === 'generic' ? initialSuggestedAngle : (bundle.topic_hint || '');
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
    topicInput.oninput = () => {
        topicInput.dataset.seedMode = 'custom';
        refreshCaptionStudioPreview();
    };
    seoInput.oninput = refreshCaptionStudioPreview;
    hashtagsInput.oninput = refreshCaptionStudioPreview;
    hashtagsInput.onblur = () => {
        hashtagsInput.value = normalizeHashtagListInput(hashtagsInput.value).join(', ');
        refreshCaptionStudioPreview();
    };
}

function renderCaptionStudioLoadingState(bundleName, bundle) {
    const shell = document.getElementById('caption-studio-shell');
    const statusNode = document.getElementById('caption-studio-status');
    const voiceNode = document.getElementById('caption-studio-voice');
    const briefStatusNode = document.getElementById('caption-studio-brief-status');
    const audienceNode = document.getElementById('caption-studio-audience');
    const identityNode = document.getElementById('caption-studio-identity');
    const seoBankNode = document.getElementById('caption-studio-seo-bank');
    const guidanceNode = document.getElementById('caption-studio-guidance');
    const topicInput = document.getElementById('caption-studio-topic');

    if(shell) shell.classList.add('is-hydrating');
    document.getElementById('caption-studio-title').innerText = `${currentVaultClient.replace(/[_-]/g, ' ')} | Copy Studio`;
    document.getElementById('caption-studio-subtitle').innerText = `Define what ${bundleName} should push, highlight, or sell before Jarvis moves it into approval.`;
    document.getElementById('caption-studio-draft-name').innerText = bundleName;
    document.getElementById('caption-studio-media-type').innerText = getReadableMediaType(bundle.bundle_type || 'image_single');
    const status = getCopyStatus(bundle);
    statusNode.innerText = status.label;
    statusNode.style.color = status.color;
    voiceNode.innerText = 'Loading client voice...';
    audienceNode.innerText = 'Loading audience...';
    identityNode.innerText = 'Jarvis is reading the saved client profile so the copy stays on-brand.';
    seoBankNode.innerText = 'Loading SEO anchors...';
    guidanceNode.innerText = 'Loading do / avoid rules...';
    if(briefStatusNode) {
        briefStatusNode.className = 'caption-studio-brief-status is-loading';
        briefStatusNode.innerText = 'Loading brand brief...';
    }
    if(topicInput) topicInput.dataset.seedMode = topicInput.dataset.seedMode || 'generic';
    renderCaptionStudioAssetStrip(bundle);
}

function renderCaptionStudioProfileState(profile, bundleName, bundle, options = {}) {
    const shell = document.getElementById('caption-studio-shell');
    const snapshot = getCaptionStudioProfileSnapshot(profile);
    const topicInput = document.getElementById('caption-studio-topic');
    const voiceNode = document.getElementById('caption-studio-voice');
    const audienceNode = document.getElementById('caption-studio-audience');
    const identityNode = document.getElementById('caption-studio-identity');
    const seoBankNode = document.getElementById('caption-studio-seo-bank');
    const guidanceNode = document.getElementById('caption-studio-guidance');
    const briefStatusNode = document.getElementById('caption-studio-brief-status');
    const suggestedAngle = buildSuggestedCampaignAngle(bundleName, bundle, snapshot.profileJson);

    if(shell) shell.classList.remove('is-hydrating');
    voiceNode.innerText = snapshot.voiceSummary;
    audienceNode.innerText = snapshot.audience;
    identityNode.innerText = snapshot.identity;
    seoBankNode.innerText = snapshot.seoBank;
    guidanceNode.innerText = snapshot.dos;
    if(briefStatusNode) {
        briefStatusNode.className = `caption-studio-brief-status ${options.fallback ? 'is-fallback' : 'is-ready'}`;
        briefStatusNode.innerText = options.fallback
            ? 'Profile partially unavailable. You can still write and save the copy.'
            : 'Brand brief ready';
    }
    if(topicInput) {
        const currentValue = topicInput.value.trim();
        const lastSuggestion = String(topicInput.dataset.lastSuggestedAngle || '').trim();
        const canSwapSuggestion = topicInput.dataset.seedMode === 'generic' && (!currentValue || currentValue === lastSuggestion);
        topicInput.dataset.lastSuggestedAngle = suggestedAngle;
        if(canSwapSuggestion) topicInput.value = suggestedAngle;
    }
    refreshCaptionStudioPreview();
}

async function hydrateCaptionStudioProfile(bundleName, requestToken) {
    const bundle = currentVaultBundles[bundleName];
    if(!bundle) return;
    try {
        const profile = await loadClientProfileForStudio(currentVaultClient);
        if(requestToken !== activeCaptionStudioRequestToken || currentCaptionDraftName !== bundleName) return;
        renderCaptionStudioProfileState(profile, bundleName, bundle);
        if(currentCaptionStudioOpenMeta?.requestToken === requestToken) {
            logCaptionStudioTiming('copy_studio_profile_ready', currentCaptionStudioOpenMeta.startedAt, {
                client: currentVaultClient,
                draft: bundleName,
            });
        }
    } catch(e) {
        if(requestToken !== activeCaptionStudioRequestToken || currentCaptionDraftName !== bundleName) return;
        renderCaptionStudioProfileState({ _clientId: currentVaultClient, profile_json: {} }, bundleName, bundle, { fallback: true });
    }
}

async function openCaptionStudio(bundleName, triggerButton = null) {
    const bundle = currentVaultBundles[bundleName];
    if(!bundle) return;
    const startedAt = performance.now();
    setButtonBusy(triggerButton, 'Opening Studio...');
    currentCaptionDraftName = bundleName;
    currentCaptionStudioMode = String(bundle.caption_mode || 'ai');
    currentCaptionStudioBaseline = String(bundle.caption_text || '');
    const requestToken = ++activeCaptionStudioRequestToken;
    currentCaptionStudioOpenMeta = {
        requestToken,
        startedAt,
        client: currentVaultClient,
        draft: bundleName,
    };

    bindCaptionStudioInputs(bundleName, bundle);
    renderCaptionStudioLoadingState(bundleName, bundle);
    refreshCaptionStudioPreview();
    document.getElementById('caption-studio-modal').style.display = 'flex';
    window.requestAnimationFrame(() => {
        restoreButtonBusy(triggerButton);
        logCaptionStudioTiming('copy_studio_visible', startedAt, {
            client: currentVaultClient,
            draft: bundleName,
        });
    });
    hydrateCaptionStudioProfile(bundleName, requestToken).catch(() => null);
}

function closeCaptionStudio() {
    activeCaptionStudioRequestToken += 1;
    currentCaptionStudioOpenMeta = null;
    const shell = document.getElementById('caption-studio-shell');
    if(shell) shell.classList.remove('is-hydrating');
    document.getElementById('caption-studio-modal').style.display = 'none';
    currentCaptionDraftName = null;
    currentCaptionStudioBaseline = '';
    currentCaptionStudioMode = 'manual';
}

/* #SECTION: Caption Studio */
async function generateDraftCaption(button) {
    if(!currentCaptionDraftName) return;
    const startedAt = performance.now();
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
            clearVaultCache(currentVaultClient);
            await loadVaultDraftsData(true);
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
        logCaptionStudioTiming('caption_generate', startedAt, {
            client: currentVaultClient,
            draft: currentCaptionDraftName || '',
        });
        restoreButtonBusy(button);
    }
}

function renderVaultFetchFailure(clientId, message = '', options = {}) {
    const grid = document.getElementById('modal-grid');
    if(!grid) return;
    const knownAssetCount = Number(options.knownAssetCount || 0);
    grid.innerHTML = `
      <div class="vault-error-state">
        <div class="vault-error-title">Vault could not be loaded cleanly.</div>
        <div class="vault-error-copy">
          ${escapeHtml(message || `Jarvis could not load the vault for ${clientId}.`)}
          ${knownAssetCount > 0 ? `<br/><br/>Jarvis still expects ${knownAssetCount} saved asset${knownAssetCount === 1 ? '' : 's'} for this client, so the vault itself is not treated as empty.` : ''}
        </div>
        <div class="vault-error-actions">
          <button type="button" class="hq-ghost-btn" onclick="loadVaultAssetsData(true)">Retry vault</button>
          <button type="button" class="hq-ghost-btn" onclick="renderVaults().catch(() => null)">Refresh clients</button>
        </div>
      </div>
    `;
}

async function saveDraftCaption(closeAfterSave = false, button = null) {
    if(!currentCaptionDraftName) return;
    const startedAt = performance.now();
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

    setButtonBusy(button, closeAfterSave ? 'Saving & returning...' : 'Saving...');
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
            const savedDraft = data.draft && typeof data.draft === 'object'
                ? {
                    ...data.draft,
                    topic_hint: topic || data.draft.topic_hint || ''
                }
                : {
                    ...(currentVaultBundles[draftName] || {}),
                    caption_text: captionText,
                    hashtags,
                    seo_keyword_used: seoKeyword,
                    caption_mode: captionMode,
                    caption_status: 'ready',
                    topic_hint: topic || currentVaultBundles[draftName]?.topic_hint || ''
                };
            upsertVaultDraftBundle(currentVaultClient, draftName, savedDraft);
            currentCaptionStudioBaseline = captionText;
            currentCaptionStudioMode = captionMode;
            if(closeAfterSave) closeCaptionStudio();
            else if(currentVaultBundles[draftName]) await openCaptionStudio(draftName);
            loadVaultDraftsData(true).catch(() => null);
            showNotification('Copy Saved', `${draftName} is now carrying a stored ${captionMode === 'ai' ? 'Jarvis' : captionMode === 'hybrid' ? 'edited Jarvis' : 'manual'} caption.`, false);
            return;
        }
        showNotification('Save Rejected', data.reason || data.message || 'Failed to save the caption.', true);
    } catch(e) {
        showNotification('Save Failed', 'Connection failed while saving the caption.', true);
    } finally {
        logCaptionStudioTiming('caption_save', startedAt, {
            client: currentVaultClient,
            draft: draftName,
            action: closeAfterSave ? 'save_return' : 'save_stay',
        });
        restoreButtonBusy(button);
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
            clearVaultCache(currentVaultClient);
            loadVaultDraftsData(true).catch(() => null);
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
        
        let imgsHtml = items.map((item, index) => {
            const f = item.filename;
            const fObj = getVaultAssetRecord(f);
            const previewUrl = getVaultAssetPreviewUrl(currentVaultClient, fObj || item);
            const posterUrl = getVaultAssetPosterUrl(currentVaultClient, fObj || item);
            if(item.kind === 'video') {
                if(posterUrl) {
                    return `<img src="${posterUrl}" alt="${escapeHtml(f)}" loading="${index < 3 ? 'eager' : 'lazy'}" decoding="async" width="64" height="64" onerror="this.replaceWith(Object.assign(document.createElement('div'), { className: 'bundle-thumb-fallback', textContent: 'VIDEO' }));" />`;
                }
                return `<div class="bundle-thumb-fallback">VIDEO</div>`;
            }
            return `<img src="${previewUrl}" alt="${escapeHtml(f)}" loading="${index < 3 ? 'eager' : 'lazy'}" decoding="async" width="64" height="64" onerror="this.replaceWith(Object.assign(document.createElement('div'), { className: 'bundle-thumb-fallback', textContent: 'PREVIEW' }));" />`;
        }).join('');
        
        const encodedName = encodeURIComponent(bName);
        const safeName = escapeJsString(bName);
        const nameMarkup = editingDraftName === bName
            ? `
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <input id="draft-rename-${encodedName}" class="qin" value="${escapeHtml(bName)}" style="max-width:260px; margin:0; height:34px;" />
                    <button onclick="saveDraftRename('${safeName}', this)" class="bundle-rename-save">Save</button>
                    <button onclick="cancelDraftRename()" class="bundle-rename-cancel">Cancel</button>
                </div>`
            : `
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span class="bundle-card-title">${escapeHtml(bName)}</span>
                    <button onclick="startDraftRename('${safeName}')" class="bundle-rename-btn">Rename</button>
                </div>`;
        const statusToneClass = status.label === 'Jarvis Draft Ready'
            ? 'is-ready'
            : (status.label === 'No Copy Yet' ? 'is-empty' : 'is-warning');
        const card = document.createElement('div');
        card.className = 'bundle-card';
        card.innerHTML = `
            <div class="bundle-card-main">
                <div class="bundle-card-head">
                    <div class="bundle-card-copy">
                        <div class="bundle-card-kicker">Creative Draft</div>
                        <div class="bundle-card-title-row">${nameMarkup}</div>
                    </div>
                    <div class="bundle-card-pills">
                        <span class="bundle-card-pill is-type">${bundleType === 'video' ? 'Reel' : files.length > 1 ? 'Carousel' : 'Image Post'}</span>
                        <span class="bundle-card-pill ${statusToneClass}" style="color:${status.color};">${status.label}</span>
                    </div>
                </div>
                <div class="b-imgs">${imgsHtml}</div>
                <div class="bundle-card-preview">
                    <div class="bundle-card-preview-head">
                        <div class="bundle-card-preview-title">Copy Snapshot</div>
                        <div class="bundle-card-preview-copy">Open Copy Studio to draft, refine, or lock the final caption.</div>
                    </div>
                    <div class="bundle-card-preview-body">${escapeHtml(captionPreview)}</div>
                    <div class="bundle-card-actions">
                        <button onclick="openCaptionStudio('${safeName}', this)" class="bundle-card-btn bundle-card-btn-primary">Open Copy Studio</button>
                        <button onclick="addDraftToJarvisFromVault('${safeName}')" class="bundle-card-btn bundle-card-btn-secondary">Load Into Workspace</button>
                    </div>
                </div>
            </div>
            <button onclick="deleteBundle('${safeName}')" class="bundle-card-btn bundle-card-btn-danger">Remove Draft</button>
        `;
        list.appendChild(card);
    });
}

async function createBundleFromSelection(button = null) {
    if(selectedVaultImages.size === 0) return;
    
    const filesArray = Array.from(selectedVaultImages);
    const selectedMeta = filesArray.map(name => currentVaultFiles.find(o => (typeof o === 'string' ? o : o.filename) === name));
    const hasVideo = selectedMeta.some(meta => (typeof meta === 'string' ? 'image' : (meta?.kind || 'image')) === 'video');
    const bundleType = hasVideo ? 'video' : (filesArray.length > 1 ? 'image_carousel' : 'image_single');
    const bName = getNextDraftName(bundleType);
    
    setButtonBusy(button, 'Saving draft...');
    try {
        const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles`), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ bundle_name: bName, files: filesArray, bundle_type: bundleType })
        });
        const data = await res.json();
        if(data.status === 'success') {
            selectedVaultImages.clear();
            if(data.bundles && typeof data.bundles === 'object') {
                replaceVaultDraftBundles(currentVaultClient, data.bundles);
            } else if(data.draft && typeof data.draft === 'object') {
                upsertVaultDraftBundle(currentVaultClient, bName, data.draft);
            }
            updateSelectionFooter();
            switchVaultTab('bundles');
            loadVaultDraftsData(true).catch(() => null);
            showNotification('Draft Created', `${bName} is ready in Creative Drafts.`, false);
            return;
        }
        showNotification("Error", data.reason || data.message || "Failed to create the creative draft.", true);
    } catch(e) {
        showNotification("Error", "Failed to create the creative draft.", true);
    } finally {
        restoreButtonBusy(button);
    }
}

async function deleteBundle(bName) {
    showConfirm(`Remove draft ${bName}? The source assets will return to Available Assets.`, async () => {
        try {
            const res = await fetch(buildApiUrl(`/api/vault/${encodeURIComponent(currentVaultClient)}/bundles/${encodeURIComponent(bName)}`), { method: 'DELETE' });
            const data = await res.json();
            if(data.status === 'success') {
                clearVaultCache(currentVaultClient);
                await loadVaultDraftsData(true);
            }
        } catch(e) {
            showNotification("Error", "Failed to remove the draft.", true);
        }
    });
}

