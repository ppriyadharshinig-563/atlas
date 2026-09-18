import json
import sys
import os

transcript_path = r'C:\Users\Priyadharashini G\.gemini\antigravity\brain\495e6d56-0039-4721-b772-0ca90694a06c\.system_generated\logs\transcript_full.jsonl'

output_dir = r'c:\Users\Priyadharashini G\OneDrive\Desktop\vitatlas\raw_data'
os.makedirs(output_dir, exist_ok=True)

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data.get('type') == 'USER_INPUT':
            content = data.get('content', '')
            step = data.get('step_index')
            with open(os.path.join(output_dir, f'step_{step}.txt'), 'w', encoding='utf-8') as out_f:
                out_f.write(content)
            print(f"Wrote Step {step}: length {len(content)}")
