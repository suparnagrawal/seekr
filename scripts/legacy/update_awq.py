import json
with open('seekr_unified_notebook.ipynb', 'r') as f:
    data = json.load(f)

for cell in data['cells']:
    if cell['cell_type'] == 'code':
        new_source = []
        for line in cell['source']:
            if '"--model", "Qwen/Qwen2.5-7B-Instruct",' in line:
                new_source.append('    "--model", "Qwen/Qwen2.5-7B-Instruct-AWQ",\n')
            elif 'FAST_MODEL=' in line:
                new_source.append('FAST_MODEL="Qwen/Qwen2.5-7B-Instruct-AWQ"\n')
            elif 'LLM_MODEL=' in line:
                new_source.append('LLM_MODEL="Qwen/Qwen2.5-7B-Instruct-AWQ"\n')
            else:
                new_source.append(line)
        cell['source'] = new_source

with open('seekr_unified_notebook.ipynb', 'w') as f:
    json.dump(data, f, indent=1)
