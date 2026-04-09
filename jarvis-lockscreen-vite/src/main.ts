import './style.css'
import {
  layoutNextLine,
  prepareWithSegments,
  type LayoutCursor,
  type PreparedTextWithSegments,
} from '@chenglou/pretext'

const currentOrigin = window.location.origin
const BACKEND_ORIGIN =
  (import.meta.env.VITE_JARVIS_API_ORIGIN as string | undefined)?.trim() ||
  (currentOrigin.includes(':5173') ? 'http://127.0.0.1:8000' : currentOrigin)
const DASHBOARD_PATH =
  (import.meta.env.VITE_JARVIS_APP_PATH as string | undefined)?.trim() || '/app'
const JARVIS_SESSION_KEY = 'jarvis_admin_session'

const SEGMENT_COUNT = 80
const HEAD_EASE = 0.115
const CHAIN_SPACING = 10.5
const HEAD_RADIUS = 22
const TAIL_RADIUS = 2.8
const BODY_FONT = '18px "Cormorant Garamond"'
const BODY_LINE_HEIGHT = 28
const TEXT_MARGIN_X = 58
const TEXT_MARGIN_TOP = 98
const TEXT_MARGIN_BOTTOM = 54

const MANUSCRIPT_BLOCKS = [
  'Jarvis keeps the room in order before the launch. Strong campaigns are remembered on purpose, not by accident. A measured release often outruns a noisy rush because timing, taste, and memory have already been aligned before the public sees a single frame.',
  'For agencies, the difference is rarely effort alone. It is sequence. It is what gets mounted, what gets reviewed, what gets held back, and what goes live at the exact minute the brand can carry it without strain. The room remembers the stronger line and the cleaner launch.',
  'Every client carries a different appetite for volume, pace, and risk. The operator must feel the shape of the brief, the weight of the calendar, the tone of the caption, and the quality of the asset before approving motion. Jarvis turns that judgment into an orderly surface.',
  'A good release is not theatrical by default. It is disciplined, legible, and inevitable in retrospect. The copy sounds precise. The media is ready. The draft is resolved. The approval path is clear. The schedule is not guessing. The brand memory stays intact.',
  'هناك عمل يصل بهدوء لأن الفكرة أصدق من الضوضاء. حين تكون الطبقات مرتبة، واللغة منضبطة، والتوقيت محسوباً، يصبح الإطلاق أقوى وأوضح. لا تحتاج العلامة إلى فوضى إضافية كي تُرى؛ تحتاج فقط إلى ترتيب يعرف أين يضع كل شيء.',
  'The folio remains awake until the right key turns. Great work travels with calm behind it. Brand memory is built line by line, choice by choice, and protected by the operator who knows exactly what deserves to go live.'
]

const MANUSCRIPT_TEXT = Array.from({ length: 20 }, (_, index) => MANUSCRIPT_BLOCKS[index % MANUSCRIPT_BLOCKS.length]).join(' ')

type Point = { x: number; y: number }
type Segment = Point & { radius: number }
type Particle = Point & {
  vx: number
  vy: number
  life: number
  maxLife: number
  size: number
  glow: number
}
type Rect = { left: number; top: number; right: number; bottom: number }
type TextLine = { text: string; x: number; y: number; width: number }

function must<T>(value: T | null, message: string): T {
  if (value === null) throw new Error(message)
  return value
}

const app = must(document.querySelector<HTMLDivElement>('#app'), 'App root missing')

app.innerHTML = `
  <div class="lockscreen-app">
    <canvas class="story-canvas" aria-hidden="true"></canvas>

    <div class="protocol-badge">AGENCY LOCK PROTOCOL</div>

    <div class="title-stack">
      <div class="title-line">
        <span class="dropcap">J</span>
        <div class="title-copy">
          <h1>arvis.</h1>
          <p>For Marketing agencies and content.</p>
        </div>
      </div>
      <div class="title-sub">
        Illuminated orchestration for brands that need timing, taste, and discipline before the work meets the public.
      </div>
    </div>

    <div class="panel-shell">
      <form class="login-panel" novalidate>
        <div class="panel-kicker">ADMIN PASSWORD</div>
        <label class="field-shell">
          <span class="sr-only">Jarvis admin password</span>
          <input
            class="auth-input"
            id="auth-password"
            name="password"
            type="password"
            autocomplete="current-password"
            placeholder="Enter Jarvis admin password"
          />
        </label>
        <button class="unlock-button" type="submit">UNLOCK JARVIS</button>
        <div class="panel-status" aria-live="polite">Enter the Jarvis admin password to continue.</div>
      </form>
    </div>

    <div class="page-note">
      The folio remains awake until the right key turns.
    </div>
  </div>
`

const canvas = must(app.querySelector<HTMLCanvasElement>('.story-canvas'), 'Canvas missing')
const titleStack = must(app.querySelector<HTMLElement>('.title-stack'), 'Title stack missing')
const protocolBadge = must(app.querySelector<HTMLElement>('.protocol-badge'), 'Protocol badge missing')
const loginForm = must(app.querySelector<HTMLFormElement>('.login-panel'), 'Login panel missing')
const passwordInput = must(app.querySelector<HTMLInputElement>('#auth-password'), 'Password input missing')
const panelStatus = must(app.querySelector<HTMLElement>('.panel-status'), 'Panel status missing')

const ctx = must(canvas.getContext('2d'), 'Canvas 2D context unavailable')

let preparedText: PreparedTextWithSegments | null = null
let textLines: TextLine[] = []
let width = 0
let height = 0
let dpr = 1
let animationFrame = 0
let lastTimestamp = performance.now()
let lastLayoutAt = 0
let pendingTextLayout = true
let titleRect: Rect = { left: 0, top: 0, right: 0, bottom: 0 }
let panelRect: Rect = { left: 0, top: 0, right: 0, bottom: 0 }
let protocolRect: Rect = { left: 0, top: 0, right: 0, bottom: 0 }

const pointer = {
  x: window.innerWidth * 0.56,
  y: window.innerHeight * 0.38,
  active: false,
  lastMovedAt: performance.now(),
}

const head = {
  x: window.innerWidth * 0.44,
  y: window.innerHeight * 0.34,
}

let previousHead = { ...head }
const segments: Segment[] = []
const particles: Particle[] = []

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const lerp = (start: number, end: number, amount: number) => start + (end - start) * amount

function getStoredSessionToken(): string {
  try {
    return window.localStorage.getItem(JARVIS_SESSION_KEY) ?? ''
  } catch {
    return ''
  }
}

function setStoredSessionToken(token: string) {
  try {
    if (token) window.localStorage.setItem(JARVIS_SESSION_KEY, token)
    else window.localStorage.removeItem(JARVIS_SESSION_KEY)
  } catch {
    // Ignore storage failures in the lockscreen shell.
  }
}

function redirectToDashboard(token = '') {
  if (token) setStoredSessionToken(token)
  const target = new URL(DASHBOARD_PATH, BACKEND_ORIGIN)
  window.location.href = target.toString()
}

function getEntryReason(): string {
  try {
    return new URL(window.location.href).searchParams.get('reason')?.trim() ?? ''
  } catch {
    return ''
  }
}

function getSegmentRadius(index: number): number {
  const ratio = index / (SEGMENT_COUNT - 1)
  return HEAD_RADIUS + (TAIL_RADIUS - HEAD_RADIUS) * ratio
}

function syncStaticRects() {
  const title = titleStack.getBoundingClientRect()
  const panel = loginForm.getBoundingClientRect()
  const protocol = protocolBadge.getBoundingClientRect()

  titleRect = {
    left: title.left - 24,
    top: title.top - 16,
    right: title.right + 28,
    bottom: title.bottom + 24,
  }
  panelRect = {
    left: panel.left - 26,
    top: panel.top - 26,
    right: panel.right + 26,
    bottom: panel.bottom + 30,
  }
  protocolRect = {
    left: protocol.left - 10,
    top: protocol.top - 8,
    right: protocol.right + 12,
    bottom: protocol.bottom + 12,
  }
}

function initializeSegments() {
  segments.length = 0
  for (let index = 0; index < SEGMENT_COUNT; index += 1) {
    segments.push({
      x: head.x - index * CHAIN_SPACING,
      y: head.y,
      radius: getSegmentRadius(index),
    })
  }
}

function resizeCanvas() {
  width = window.innerWidth
  height = window.innerHeight
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = Math.round(width * dpr)
  canvas.height = Math.round(height * dpr)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  syncStaticRects()
  pendingTextLayout = true
}

function subtractRange(ranges: Array<[number, number]>, cutStart: number, cutEnd: number): Array<[number, number]> {
  const next: Array<[number, number]> = []
  for (const [start, end] of ranges) {
    if (cutEnd <= start || cutStart >= end) {
      next.push([start, end])
      continue
    }
    if (cutStart > start) next.push([start, cutStart])
    if (cutEnd < end) next.push([cutEnd, end])
  }
  return next
}

function collectObstacleRects(): Rect[] {
  const obstacles: Rect[] = [titleRect, panelRect, protocolRect]

  for (let index = 0; index < segments.length; index += 1) {
    const segment = segments[index]
    const radius = segment.radius + 10
    obstacles.push({
      left: segment.x - radius,
      top: segment.y - radius,
      right: segment.x + radius,
      bottom: segment.y + radius,
    })
  }

  const headAngle = Math.atan2(segments[0].y - segments[1].y, segments[0].x - segments[1].x)
  const snoutX = segments[0].x + Math.cos(headAngle) * 34
  const snoutY = segments[0].y + Math.sin(headAngle) * 34
  obstacles.push({
    left: snoutX - 28,
    top: snoutY - 20,
    right: snoutX + 28,
    bottom: snoutY + 20,
  })

  return obstacles
}

function getFreeSpans(yTop: number, yBottom: number, obstacles: Rect[]): Array<[number, number]> {
  let spans: Array<[number, number]> = [[TEXT_MARGIN_X, width - TEXT_MARGIN_X]]
  for (const rect of obstacles) {
    if (rect.bottom < yTop || rect.top > yBottom) continue
    spans = subtractRange(spans, rect.left, rect.right)
  }
  return spans.filter(([start, end]) => end - start >= 118)
}

function relayoutText(now: number) {
  if (!preparedText) return
  if (!pendingTextLayout && now - lastLayoutAt < 34) return

  syncStaticRects()
  const obstacles = collectObstacleRects()
  const nextLines: TextLine[] = []
  let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 }

  for (let baseline = TEXT_MARGIN_TOP; baseline < height - TEXT_MARGIN_BOTTOM; baseline += BODY_LINE_HEIGHT) {
    const bandTop = baseline - BODY_LINE_HEIGHT * 0.82
    const bandBottom = baseline + BODY_LINE_HEIGHT * 0.42
    const spans = getFreeSpans(bandTop, bandBottom, obstacles)
    for (const [startX, endX] of spans) {
      const line = layoutNextLine(preparedText, cursor, endX - startX)
      if (line === null) {
        textLines = nextLines
        lastLayoutAt = now
        pendingTextLayout = false
        return
      }
      nextLines.push({ text: line.text, x: startX, y: baseline, width: line.width })
      cursor = line.end
    }
  }

  textLines = nextLines
  lastLayoutAt = now
  pendingTextLayout = false
}

function updatePointerParallax() {
  const normalizedX = (pointer.x / Math.max(width, 1)) - 0.5
  const normalizedY = (pointer.y / Math.max(height, 1)) - 0.5
  titleStack.style.transform = `translate3d(${normalizedX * 16}px, ${normalizedY * 10}px, 0)`
  loginForm.style.transform = `translate3d(${normalizedX * -12}px, ${normalizedY * -10}px, 0)`
}

function updateDragon(now: number) {
  const idle = now - pointer.lastMovedAt > 2200
  const targetX = idle ? width * 0.55 + Math.cos(now * 0.00032) * width * 0.11 : pointer.x
  const targetY = idle ? height * 0.41 + Math.sin(now * 0.00041) * height * 0.15 : pointer.y

  previousHead = { x: segments[0].x, y: segments[0].y }
  segments[0].x = lerp(segments[0].x, clamp(targetX, 110, width - 110), HEAD_EASE)
  segments[0].y = lerp(segments[0].y, clamp(targetY, 86, height - 96), HEAD_EASE)

  for (let index = 1; index < segments.length; index += 1) {
    const previous = segments[index - 1]
    const current = segments[index]
    const dx = current.x - previous.x
    const dy = current.y - previous.y
    const angle = Math.atan2(dy, dx)
    current.x = previous.x + Math.cos(angle) * CHAIN_SPACING
    current.y = previous.y + Math.sin(angle) * CHAIN_SPACING
  }

  const motion = Math.hypot(segments[0].x - previousHead.x, segments[0].y - previousHead.y)
  if (motion > 0.65) {
    emitParticles(motion)
    pendingTextLayout = true
  }
}

function emitParticles(motion: number) {
  const headAngle = Math.atan2(segments[0].y - segments[1].y, segments[0].x - segments[1].x)
  const mouthX = segments[0].x + Math.cos(headAngle) * 26
  const mouthY = segments[0].y + Math.sin(headAngle) * 26
  const burstCount = Math.min(5, 2 + Math.floor(motion * 1.1))

  for (let index = 0; index < burstCount; index += 1) {
    const spread = (Math.random() - 0.5) * 0.8
    const speed = 1.8 + Math.random() * 2.6 + motion * 0.18
    particles.push({
      x: mouthX,
      y: mouthY,
      vx: Math.cos(headAngle + spread) * speed,
      vy: Math.sin(headAngle + spread) * speed - 0.3,
      life: 18 + Math.random() * 14,
      maxLife: 26 + Math.random() * 14,
      size: 1.6 + Math.random() * 3.6,
      glow: 0.4 + Math.random() * 0.5,
    })
  }
}

function updateParticles() {
  for (let index = particles.length - 1; index >= 0; index -= 1) {
    const particle = particles[index]
    particle.x += particle.vx
    particle.y += particle.vy
    particle.vx *= 0.985
    particle.vy = particle.vy * 0.988 - 0.018
    particle.life -= 1
    if (particle.life <= 0) particles.splice(index, 1)
  }
}

function drawManuscript() {
  ctx.save()
  ctx.font = BODY_FONT
  ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = 'rgba(24, 16, 10, 0.94)'
  ctx.shadowColor = 'rgba(255, 247, 226, 0.16)'
  ctx.shadowBlur = 0.65

  for (let index = 0; index < textLines.length; index += 1) {
    const line = textLines[index]
    ctx.globalAlpha = 0.9 + ((index % 6) * 0.012)
    ctx.fillText(line.text, line.x, line.y)
  }

  ctx.restore()
}

function drawDragon() {
  const headAngle = Math.atan2(segments[0].y - segments[1].y, segments[0].x - segments[1].x)
  const headScale = 0.82

  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  ctx.strokeStyle = 'rgba(28, 18, 12, 0.18)'
  for (let index = segments.length - 2; index >= 0; index -= 1) {
    ctx.lineWidth = segments[index].radius * 1.16
    ctx.beginPath()
    ctx.moveTo(segments[index + 1].x, segments[index + 1].y)
    ctx.lineTo(segments[index].x, segments[index].y)
    ctx.stroke()
  }

  for (let index = segments.length - 1; index >= 0; index -= 1) {
    const segment = segments[index]
    const gradient = ctx.createRadialGradient(
      segment.x - segment.radius * 0.4,
      segment.y - segment.radius * 0.45,
      segment.radius * 0.1,
      segment.x,
      segment.y,
      segment.radius * 1.25,
    )
    gradient.addColorStop(0, '#2b2019')
    gradient.addColorStop(0.48, '#19110d')
    gradient.addColorStop(1, '#090605')

    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(segment.x, segment.y, segment.radius, 0, Math.PI * 2)
    ctx.fill()

    ctx.strokeStyle = 'rgba(255, 223, 171, 0.08)'
    ctx.lineWidth = Math.max(0.8, segment.radius * 0.11)
    ctx.beginPath()
    ctx.arc(
      segment.x - segment.radius * 0.12,
      segment.y - segment.radius * 0.08,
      segment.radius * 0.66,
      Math.PI * 1.05,
      Math.PI * 1.72,
    )
    ctx.stroke()
  }

  ctx.save()
  ctx.translate(segments[0].x, segments[0].y)
  ctx.rotate(headAngle)
  ctx.scale(headScale, headScale)

  ctx.fillStyle = 'rgba(12, 7, 5, 0.14)'
  ctx.beginPath()
  ctx.ellipse(10, 16, 40, 18, 0, 0, Math.PI * 2)
  ctx.fill()

  const headGradient = ctx.createLinearGradient(-30, -24, 40, 22)
  headGradient.addColorStop(0, '#352720')
  headGradient.addColorStop(0.4, '#1b120e')
  headGradient.addColorStop(1, '#090605')
  ctx.fillStyle = headGradient

  ctx.beginPath()
  ctx.moveTo(-28, -24)
  ctx.quadraticCurveTo(10, -38, 48, -8)
  ctx.quadraticCurveTo(54, -2, 54, 6)
  ctx.quadraticCurveTo(46, 20, 22, 26)
  ctx.quadraticCurveTo(-4, 30, -26, 10)
  ctx.quadraticCurveTo(-36, 0, -28, -24)
  ctx.closePath()
  ctx.fill()

  ctx.strokeStyle = 'rgba(255, 232, 192, 0.14)'
  ctx.lineWidth = 1.8
  ctx.beginPath()
  ctx.moveTo(-20, -14)
  ctx.quadraticCurveTo(10, -28, 38, -8)
  ctx.stroke()

  ctx.strokeStyle = '#201611'
  ctx.lineWidth = 5.8
  ctx.beginPath()
  ctx.moveTo(-12, -18)
  ctx.quadraticCurveTo(-20, -36, -2, -44)
  ctx.moveTo(6, -20)
  ctx.quadraticCurveTo(8, -42, 26, -44)
  ctx.stroke()

  ctx.strokeStyle = 'rgba(19, 10, 6, 0.8)'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(8, 14)
  ctx.quadraticCurveTo(30, 18, 50, 8)
  ctx.stroke()

  ctx.fillStyle = '#ffb347'
  ctx.shadowColor = 'rgba(255, 164, 44, 0.95)'
  ctx.shadowBlur = 18
  ctx.beginPath()
  ctx.ellipse(18, -8, 4.8, 3.6, 0, 0, Math.PI * 2)
  ctx.fill()

  ctx.shadowBlur = 0
  ctx.fillStyle = '#fff2ba'
  ctx.beginPath()
  ctx.arc(20, -9, 1.2, 0, Math.PI * 2)
  ctx.fill()

  ctx.restore()
  ctx.restore()
}

function drawParticles() {
  ctx.save()
  for (const particle of particles) {
    const lifeRatio = particle.life / particle.maxLife
    ctx.globalAlpha = clamp(lifeRatio, 0, 1)
    ctx.fillStyle = `hsla(${28 + lifeRatio * 20}, 94%, ${58 + lifeRatio * 12}%, ${0.6 + particle.glow * 0.25})`
    ctx.shadowColor = `hsla(${30 + lifeRatio * 12}, 100%, 66%, 0.75)`
    ctx.shadowBlur = 16
    ctx.beginPath()
    ctx.arc(particle.x, particle.y, particle.size * lifeRatio, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()
}

function render(now: number) {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  relayoutText(now)
  drawManuscript()
  drawParticles()
  drawDragon()
}

function animate(now: number) {
  const delta = now - lastTimestamp
  lastTimestamp = now
  updateDragon(now)
  updateParticles()
  updatePointerParallax()
  render(now)
  animationFrame = window.requestAnimationFrame(animate)
  if (delta > 80) pendingTextLayout = true
}

function setStatus(message: string, state: 'idle' | 'error' | 'busy' = 'idle') {
  panelStatus.textContent = message
  panelStatus.dataset.state = state
}

async function handleUnlock(event: SubmitEvent) {
  event.preventDefault()
  const password = passwordInput.value
  if (!password.trim()) {
    setStatus('Enter the Jarvis admin password first.', 'error')
    passwordInput.focus()
    return
  }

  setStatus('Authenticating with Jarvis control plane...', 'busy')
  loginForm.classList.add('is-busy')

  try {
    const response = await fetch(`${BACKEND_ORIGIN}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    const payload = (await response.json()) as { status?: string; reason?: string; token?: string }
    if (!response.ok || payload.status !== 'success' || !payload.token) {
      throw new Error(payload.reason || 'Jarvis rejected the password.')
    }

    setStatus('Seal opened. Redirecting into Jarvis...', 'busy')
    document.body.classList.add('is-unlocking')
    window.setTimeout(() => {
      redirectToDashboard(payload.token ?? '')
    }, 520)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Jarvis could not complete the unlock.'
    setStatus(message, 'error')
    passwordInput.select()
    loginForm.classList.remove('is-busy')
  }
}

async function tryResumeSession() {
  const token = getStoredSessionToken().trim()
  if (!token) return

  try {
    const response = await fetch(`${BACKEND_ORIGIN}/api/auth/status`, {
      headers: { 'X-Jarvis-Auth': token },
    })
    const payload = (await response.json()) as { authenticated?: boolean; auth_enabled?: boolean }
    if (response.ok && (payload.auth_enabled === false || payload.authenticated)) {
      setStatus('Jarvis is already unlocked. Opening the operator surface...', 'busy')
      document.body.classList.add('is-unlocking')
      window.setTimeout(() => {
        redirectToDashboard(token)
      }, 320)
      return
    }
  } catch {
    // Ignore status failures and let the user authenticate manually.
  }

  setStoredSessionToken('')
}

window.addEventListener('pointermove', (event) => {
  pointer.x = event.clientX
  pointer.y = event.clientY
  pointer.active = true
  pointer.lastMovedAt = performance.now()
})

window.addEventListener('pointerleave', () => {
  pointer.active = false
})

window.addEventListener('resize', () => {
  resizeCanvas()
})

loginForm.addEventListener('submit', (event) => {
  void handleUnlock(event as SubmitEvent)
})

async function boot() {
  resizeCanvas()
  initializeSegments()
  setStatus(getEntryReason() || 'Enter the Jarvis admin password to continue.')
  void tryResumeSession()

  await (document as Document & { fonts?: FontFaceSet }).fonts?.ready
  preparedText = prepareWithSegments(MANUSCRIPT_TEXT, BODY_FONT)
  pendingTextLayout = true
  cancelAnimationFrame(animationFrame)
  animationFrame = window.requestAnimationFrame(animate)
}

void boot()
