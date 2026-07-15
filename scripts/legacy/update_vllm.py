import json
import os

def update_vllm_context(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist.")
        return
        
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    for cell in data.get('cells', []):
        if cell.get('cell_type') == 'code':
            source = cell.get('source', [])
            if any('vllm.entrypoints.openai.api_server' in line for line in source):
                new_source = []
                for line in source:
                    if '"--max-model-len", "4096"' in line:
                        new_source.append(line.replace('"4096"', '"16384"'))
                    else:
                        new_source.append(line)
                cell['source'] = new_source
                print(f"Updated vLLM max-model-len to 16384 in {filepath}")
                
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=1)

update_vllm_context('seekr_unified_notebook.ipynb')
update_vllm_context('colab_gpu_use.ipynb')
