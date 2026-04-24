import json
import os

log_path = r'C:\Users\Fleun\.gemini\antigravity\brain\bcaf058a-6e1a-4218-a522-e8b59f2a725f\.system_generated\logs\overview.txt'
out_path = r'C:\Users\Fleun\.gemini\antigravity\brain\bcaf058a-6e1a-4218-a522-e8b59f2a725f/whatsapp_operator_reconstructed.py'

chunks = {}

if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # Look for tool results that contain the file content
                if 'tool_results' in data:
                    for result in data['tool_results']:
                        # Check if it's a view_file result for whatsapp_operator.py
                        # The system might not explicitly label the file in results, but we can check content
                        content = result.get('content', '')
                        if 'import asyncio' in content and 'from starlette.responses import JSONResponse' in content:
                            chunks[0] = content
                        elif 'Operator Actions' in content and 'root_menu' in content:
                            # Heuristic for other chunks
                            if 'Lines 800 to 1600' in content:
                                chunks[800] = content
                            elif 'Lines 1600 to 2400' in content:
                                chunks[1600] = content
                            elif 'Lines 2400 to 3159' in content:
                                chunks[2400] = content
            except:
                continue

# Sort and join chunks
sorted_keys = sorted(chunks.keys())
full_content = ""
for k in sorted_keys:
    # Remove the "Showing lines X to Y" headers if present
    c = chunks[k]
    # Simple cleanup (heuristic)
    lines = c.split('\n')
    cleaned_lines = []
    for l in lines:
        if l.startswith('Showing lines') or l.startswith('File Path:') or l.startswith('Total Lines:'):
            continue
        # Remove line numbers like "1: "
        if ': ' in l:
            parts = l.split(': ', 1)
            if parts[0].strip().isdigit():
                cleaned_lines.append(parts[1])
            else:
                cleaned_lines.append(l)
        else:
            cleaned_lines.append(l)
    full_content += '\n'.join(cleaned_lines)

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(full_content)

print(f"Reconstructed {len(full_content)} bytes to {out_path}")
print(f"Chunks found: {list(chunks.keys())}")
