import os
import re

path = 'jarvis-dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

intake_search = """              <div class="intake-section-label">Target Audience</div>
              <input class="qin" id="c-audience" placeholder="Who this business sells to" />

              <div class="intake-section-label">Brand Identity</div>"""
intake_replace = """              <div class="intake-section-label">Target Audience</div>
              <input class="qin" id="c-audience" placeholder="Who this business sells to" />

              <div class="intake-section-label">Language Settings</div>
              <div class="intake-review-grid" style="margin-bottom:12px;">
                <select class="qin" id="c-brief-lang" style="cursor:pointer;" onchange="syncIntakeJsonPreview()">
                  <option value="english">Brief: English</option>
                  <option value="arabic">Brief: Arabic</option>
                </select>
                <select class="qin" id="c-primary-lang" style="cursor:pointer;" onchange="syncIntakeJsonPreview()">
                  <option value="arabic">Brand: Arabic</option>
                  <option value="english">Brand: English</option>
                </select>
              </div>
              <div class="intake-review-grid" style="margin-bottom:12px;">
                <select class="qin" id="c-caption-lang" style="cursor:pointer;" onchange="syncIntakeJsonPreview()">
                  <option value="arabic">Output: Arabic</option>
                  <option value="english">Output: English</option>
                  <option value="bilingual">Output: Bilingual</option>
                </select>
                <select class="qin" id="c-arabic-mode" style="cursor:pointer;" onchange="syncIntakeJsonPreview()">
                  <option value="gulf">Arabic Mode: Gulf</option>
                  <option value="msa">Arabic Mode: MSA</option>
                  <option value="egyptian">Arabic Mode: Egyptian</option>
                </select>
              </div>

              <div class="intake-section-label">Brand Identity</div>"""

populate_search = """  document.getElementById('c-hashtags').value = Array.isArray(profile.hashtag_bank) ? profile.hashtag_bank.join(', ') : '';
  document.getElementById('c-banned').value = Array.isArray(profile.banned_words) ? profile.banned_words.join(', ') : '';
  document.getElementById('c-rules').value = Array.isArray(profile.dos_and_donts) ? profile.dos_and_donts.join('\\n') : '';
  syncIntakeJsonPreview();"""
populate_replace = """  document.getElementById('c-hashtags').value = Array.isArray(profile.hashtag_bank) ? profile.hashtag_bank.join(', ') : '';
  document.getElementById('c-banned').value = Array.isArray(profile.banned_words) ? profile.banned_words.join(', ') : '';
  document.getElementById('c-rules').value = Array.isArray(profile.dos_and_donts) ? profile.dos_and_donts.join('\\n') : '';

  const lang = profile.language_profile || {};
  document.getElementById('c-brief-lang').value = lang.brief_language || 'english';
  document.getElementById('c-primary-lang').value = lang.primary_language || 'arabic';
  document.getElementById('c-caption-lang').value = lang.caption_output_language || 'arabic';
  document.getElementById('c-arabic-mode').value = lang.arabic_mode || 'gulf';
  syncIntakeJsonPreview();"""

build_search = """    caption_defaults: {
      min_length: 150,
      max_length: 300,
      hashtag_count_min: 3,
      hashtag_count_max: 5
    },
    brand_voice: {
      tone: parseCsvInput(document.getElementById('c-tone').value),
      style: document.getElementById('c-style').value.trim(),
      dialect: 'gulf_arabic_khaleeji',
      dialect_notes: document.getElementById('c-dialect').value.trim()
    }"""
build_replace = """    caption_defaults: {
      min_length: 150,
      max_length: 300,
      hashtag_count_min: 3,
      hashtag_count_max: 5
    },
    language_profile: {
      brief_language: document.getElementById('c-brief-lang').value,
      primary_language: document.getElementById('c-primary-lang').value,
      caption_output_language: document.getElementById('c-caption-lang').value,
      arabic_mode: document.getElementById('c-arabic-mode').value
    },
    brand_voice: {
      tone: parseCsvInput(document.getElementById('c-tone').value),
      style: document.getElementById('c-style').value.trim(),
      dialect: document.getElementById('c-arabic-mode').value === 'gulf' ? 'gulf_arabic_khaleeji' : 'msa',
      dialect_notes: document.getElementById('c-dialect').value.trim()
    }"""

cfg_ui_search = """            <div id="cfg-details-${c}" style="display:none; margin-top:12px; border-top:1px solid rgba(255,255,255,0.05); padding-top:14px;">
                <div style="font-size:10px; color:var(--t4); text-transform:uppercase; font-family:'Space Mono'; margin-bottom:12px;">BRAND PROFILE EDITOR</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">"""
cfg_ui_replace = """            <div id="cfg-details-${c}" style="display:none; margin-top:12px; border-top:1px solid rgba(255,255,255,0.05); padding-top:14px;">
                <div style="font-size:10px; color:var(--t4); text-transform:uppercase; font-family:'Space Mono'; margin-bottom:12px;">BRAND PROFILE EDITOR</div>
                
                <div style="font-size:11px; color:var(--t3); margin-bottom:4px; font-weight:600;">Language Settings</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
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
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">"""

cfg_save_search = """    const rules = document.getElementById('cfg-rules-' + clientId).value.split('\\n').map(s => s.trim()).filter(Boolean);
    
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
            brand_voice: {
                tone,
                style,
                dialect: 'gulf_arabic_khaleeji',
                dialect_notes: dialectNotes
            }
        }
    };"""

cfg_save_replace = """    const rules = document.getElementById('cfg-rules-' + clientId).value.split('\\n').map(s => s.trim()).filter(Boolean);
    
    const briefLang = document.getElementById('cfg-brief-lang-' + clientId).value;
    const primaryLang = document.getElementById('cfg-primary-lang-' + clientId).value;
    const captionLang = document.getElementById('cfg-caption-lang-' + clientId).value;
    const arabicMode = document.getElementById('cfg-arabic-mode-' + clientId).value;

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
                brief_language: briefLang,
                primary_language: primaryLang,
                caption_output_language: captionLang,
                arabic_mode: arabicMode
            },
            brand_voice: {
                tone,
                style,
                dialect: arabicMode === 'gulf' ? 'gulf_arabic_khaleeji' : 'msa',
                dialect_notes: dialectNotes
            }
        }
    };"""

replacements = [
    ("intake UI", intake_search, intake_replace),
    ("intake populate", populate_search, populate_replace),
    ("intake build JSON", build_search, build_replace),
    ("CFG UI", cfg_ui_search, cfg_ui_replace),
    ("CFG Save", cfg_save_search, cfg_save_replace)
]

new_content = content
for name, source, target in replacements:
    if source in new_content:
        new_content = new_content.replace(source, target)
        print(f"Success: {name}")
    else:
        print(f"FAILED: {name} not found in file")
        import sys
        sys.exit(1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Done patching.")
