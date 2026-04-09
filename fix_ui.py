import os

path = '/home/snowaflic/agents/jarvis-dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

bad_ui = """                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <select class="qin" id="cfg-brief-lang-${c}" style="cursor:pointer;">
                        <option value="english" ${b.language_profile?.brief_language === 'english' ? 'selected' : ''}>Brief: English</option>
                        <option value="arabic" ${b.language_profile?.brief_language === 'arabic' ? 'selected' : ''}>Brief: Arabic</option>
                    </select>
                    <select class="qin" id="cfg-primary-lang-${c}" style="cursor:pointer;">
                        <option value="arabic" ${(!b.language_profile || b.language_profile.primary_language === 'arabic') ? 'selected' : ''}>Brand: Arabic</option>
                        <option value="english" ${b.language_profile?.primary_language === 'english' ? 'selected' : ''}>Brand: English</option>
                    </select>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <select class="qin" id="cfg-caption-lang-${c}" style="cursor:pointer;">
                        <option value="arabic" ${(!b.language_profile || b.language_profile.caption_output_language === 'arabic') ? 'selected' : ''}>Output: Arabic</option>
                        <option value="english" ${b.language_profile?.caption_output_language === 'english' ? 'selected' : ''}>Output: English</option>
                        <option value="bilingual" ${b.language_profile?.caption_output_language === 'bilingual' ? 'selected' : ''}>Output: Bilingual</option>
                    </select>
                    <select class="qin" id="cfg-arabic-mode-${c}" style="cursor:pointer;">
                        <option value="gulf" ${(!b.language_profile || b.language_profile.arabic_mode === 'gulf') ? 'selected' : ''}>Arabic Mode: Gulf</option>
                        <option value="msa" ${b.language_profile?.arabic_mode === 'msa' ? 'selected' : ''}>Arabic Mode: MSA</option>
                        <option value="egyptian" ${b.language_profile?.arabic_mode === 'egyptian' ? 'selected' : ''}>Arabic Mode: Egyptian</option>
                    </select>
                </div>"""

good_ui = """                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <select class="qin" id="cfg-brief-lang-${c}" style="cursor:pointer;">
                        <option value="english">Brief: English</option>
                        <option value="arabic">Brief: Arabic</option>
                    </select>
                    <select class="qin" id="cfg-primary-lang-${c}" style="cursor:pointer;">
                        <option value="arabic">Brand: Arabic</option>
                        <option value="english">Brand: English</option>
                    </select>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <select class="qin" id="cfg-caption-lang-${c}" style="cursor:pointer;">
                        <option value="arabic">Output: Arabic</option>
                        <option value="english">Output: English</option>
                        <option value="bilingual">Output: Bilingual</option>
                    </select>
                    <select class="qin" id="cfg-arabic-mode-${c}" style="cursor:pointer;">
                        <option value="gulf">Arabic Mode: Gulf</option>
                        <option value="msa">Arabic Mode: MSA</option>
                        <option value="egyptian">Arabic Mode: Egyptian</option>
                    </select>
                </div>"""

if bad_ui in text:
    text = text.replace(bad_ui, good_ui)
    print("UI fixed.")
else:
    print("Bad UI not found!")

load_search = """        document.getElementById('cfg-business-' + c).value = p.business_name || c;
        document.getElementById('cfg-industry-' + c).value = p.industry || '';"""

load_inject = """        const lang = p.language_profile || {};
        document.getElementById('cfg-brief-lang-' + c).value = lang.brief_language || 'english';
        document.getElementById('cfg-primary-lang-' + c).value = lang.primary_language || 'arabic';
        document.getElementById('cfg-caption-lang-' + c).value = lang.caption_output_language || 'arabic';
        document.getElementById('cfg-arabic-mode-' + c).value = lang.arabic_mode || 'gulf';
        document.getElementById('cfg-business-' + c).value = p.business_name || c;
        document.getElementById('cfg-industry-' + c).value = p.industry || '';"""

if load_search in text:
    text = text.replace(load_search, load_inject)
    print("Load logic injected.")
else:
    print("Load search not found")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
