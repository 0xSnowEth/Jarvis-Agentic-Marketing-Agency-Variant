import os
import re

path = '/home/snowaflic/agents/jarvis-dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Replace CSS
css_search = re.compile(r'\.boot-overlay \{(.*?)\.boot-ring core \{(.*?)\}', re.DOTALL)
css_replace = """.boot-overlay {
  position: fixed;
  inset: 0;
  z-index: 1190;
  display: none;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at center, rgba(16, 20, 24, 0.4), rgba(5, 7, 10, 0.95) 100%);
  backdrop-filter: blur(24px);
  opacity: 0;
  transition: opacity .4s cubic-bezier(0.16, 1, 0.3, 1), visibility .4s;
}
.boot-overlay.visible {
  display: flex;
  opacity: 1;
}
.boot-hud-premium {
  position: relative;
  width: min(780px, 90vw);
  border-radius: 24px;
  background: rgba(10, 14, 20, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 40px 100px -10px rgba(0, 0, 0, 0.8), inset 0 0 0 1px rgba(0, 245, 255, 0.05), inset 0 0 80px rgba(0, 245, 255, 0.02);
  overflow: hidden;
  padding: 40px 48px;
}
.boot-hud-bg {
  position: absolute;
  inset: 0;
  background: 
    radial-gradient(ellipse at top right, rgba(0, 245, 255, 0.08), transparent 50%),
    radial-gradient(ellipse at bottom left, rgba(157, 78, 221, 0.08), transparent 50%);
  pointer-events: none;
  z-index: 0;
}
.boot-hud-content { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 32px; }
.boot-hud-header { display: flex; flex-direction: column; gap: 12px; }
.boot-hud-kicker { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 0.3em; color: #00f5ff; text-transform: uppercase; text-shadow: 0 0 10px rgba(0, 245, 255, 0.4); }
.boot-hud-title { font-family: 'Inter', -apple-system, sans-serif; font-size: clamp(28px, 4vw, 42px); font-weight: 500; letter-spacing: -0.02em; color: #ffffff; line-height: 1.1; }
.boot-hud-body { display: flex; align-items: stretch; justify-content: space-between; gap: 40px; }
.boot-hud-left { flex: 1; display: flex; flex-direction: column; gap: 24px; }
.boot-hud-sub { font-size: 14px; line-height: 1.6; color: rgba(255,255,255,0.6); font-family: 'Inter', sans-serif; }
.boot-steps-container { display: flex; flex-direction: column; }
.boot-step { display: flex; align-items: flex-start; gap: 16px; opacity: 0.4; transition: opacity 0.3s; }
.boot-step.active { opacity: 1; }
.boot-step.active .boot-step-dot { background: #00f5ff; box-shadow: 0 0 12px rgba(0, 245, 255, 0.6); border-color: transparent; }
.boot-step.done { opacity: 0.8; }
.boot-step.done .boot-step-dot { background: #9d4edd; border-color: transparent; }
.boot-step.done .boot-step-line { background: rgba(157, 78, 221, 0.4); }
.boot-step-indicator { display: flex; flex-direction: column; align-items: center; width: 12px; margin-top: 6px; }
.boot-step-dot { width: 10px; height: 10px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.2); background: transparent; transition: all 0.4s; position: relative; z-index: 2; }
.boot-step-line { width: 1px; height: 28px; background: rgba(255,255,255,0.1); margin: -2px 0; position: relative; z-index: 1; transition: background 0.4s; }
.boot-step-text { font-family: 'Space Mono', monospace; font-size: 12px; color: rgba(255,255,255,0.8); padding-bottom: 24px; padding-top: 2px; }
.boot-step:last-child .boot-step-text { padding-bottom: 0; }
.boot-system-tags { display: flex; gap: 12px; margin-top: auto; padding-top: 16px; }
.boot-tag { font-family: 'Space Mono', monospace; font-size: 10px; letter-spacing: 0.1em; color: rgba(255,255,255,0.5); padding: 6px 12px; border: 1px solid rgba(255,255,255,0.1); border-radius: 100px; text-transform: uppercase; }
.boot-hud-right { display: flex; align-items: center; justify-content: center; padding-right: 20px; }
.cyber-spinner { position: relative; width: 180px; height: 180px; display: flex; align-items: center; justify-content: center; }
.cyber-ring { position: absolute; inset: 0; border-radius: 50%; border: 1px solid transparent; }
.cyber-ring-outer { border: 1px dashed rgba(255,255,255,0.1); border-top-color: #00f5ff; animation: cyberSpin 12s linear infinite; }
.cyber-ring-middle { inset: 15px; border-top: 2px solid rgba(157, 78, 221, 0.6); border-bottom: 2px solid rgba(0, 245, 255, 0.4); animation: cyberSpin 6s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite reverse; }
.cyber-ring-inner { inset: 35px; border: 1px dotted rgba(255,255,255,0.2); border-left-color: #00f5ff; animation: cyberSpin 4s linear infinite; }
.cyber-core-glow { position: absolute; width: 60px; height: 60px; border-radius: 50%; background: radial-gradient(circle, rgba(0, 245, 255, 0.4), transparent 70%); animation: cyberPulse 2s ease-in-out infinite alternate; }
.cyber-center-icon { position: relative; z-index: 2; width: 28px; height: 28px; color: rgba(255,255,255,0.9); animation: cyberPulse 2s ease-in-out infinite alternate; }
@keyframes cyberSpin { 100% { transform: rotate(360deg); } }
@keyframes cyberPulse { 0% { opacity: 0.5; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1.1); } }
"""

# Harder to regex all the old css rules, lets just find the start and end tokens
idx_start = text.find('.boot-overlay {')
idx_end = text.find('</style>', idx_start)
css_block = text[idx_start:idx_end]

# Only remove old boot- CSS
lines = css_block.split('\n')
new_css = []
skip = False
for line in lines:
    if line.startswith('.boot-') and '{' in line:
        skip = True
    if line.startswith('}'):
        if skip:
            skip = False
            continue
    if not skip and not line.startswith('.boot-'):
        new_css.append(line)

final_css = css_replace + '\n' + '\n'.join(new_css)
text = text[:idx_start] + final_css + text[idx_end:]


# 2. Replace HTML
html_search = r'<div id="boot-overlay" class="boot-overlay" aria-hidden="true">.*?</div>\n</div>'
html_replace = """<div id="boot-overlay" class="boot-overlay" aria-hidden="true">
  <div class="boot-hud-premium">
    <div class="boot-hud-bg"></div>
    <div class="boot-hud-content">
      <div class="boot-hud-header">
        <div class="boot-hud-kicker">JARVIS SYSTEM BOOT</div>
        <div class="boot-hud-title">Synchronizing the agency control surface.</div>
      </div>
      
      <div class="boot-hud-body">
        <div class="boot-hud-left">
          <div id="boot-sub" class="boot-hud-sub">Mounting brand memory, vault indexes, approvals, schedule lanes, and live operator state...</div>
          
          <div class="boot-steps-container">
            <div class="boot-step" id="boot-step-1">
              <div class="boot-step-indicator">
                <div class="boot-step-line"></div>
                <div class="boot-step-dot"></div>
              </div>
              <div class="boot-step-text">Linking client registries</div>
            </div>
            
            <div class="boot-step" id="boot-step-2">
              <div class="boot-step-indicator">
                <div class="boot-step-line"></div>
                <div class="boot-step-dot"></div>
              </div>
              <div class="boot-step-text">Indexing schedule & approvals</div>
            </div>
            
            <div class="boot-step" id="boot-step-3">
              <div class="boot-step-indicator">
                <div class="boot-step-dot"></div>
              </div>
              <div class="boot-step-text">Warming vault media caches</div>
            </div>
          </div>
          
          <div class="boot-system-tags">
            <div class="boot-tag">Agency OS</div>
            <div class="boot-tag">Vault Sync</div>
            <div class="boot-tag">Approval Mesh</div>
          </div>
        </div>
        
        <div class="boot-hud-right">
          <div class="cyber-spinner">
            <div class="cyber-ring cyber-ring-outer"></div>
            <div class="cyber-ring cyber-ring-middle"></div>
            <div class="cyber-ring cyber-ring-inner"></div>
            <div class="cyber-core-glow"></div>
            <svg class="cyber-center-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>"""
text = re.sub(html_search, html_replace, text, flags=re.DOTALL)


# 3. Replace JS
js_start = text.find('async function bootstrapApp() {')
js_end = text.find('return appBootPromise;', js_start) + min(100, len('return appBootPromise;') + 10)
# Make sure we don't truncate incorrectly, we know the length roughly
js_end = text.find('}', js_end) + 1

js_replace = """async function bootstrapApp() {
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
}"""

old_js = text[js_start:js_end]
text = text.replace(old_js, js_replace)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Boot UI patched successfully.")
