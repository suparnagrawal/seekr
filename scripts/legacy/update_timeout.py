import json
with open('seekr_unified_notebook.ipynb', 'r') as f:
    data = json.load(f)

for cell in data['cells']:
    if cell['cell_type'] == 'code':
        new_source = []
        for line in cell['source']:
            if 'client = httpx.AsyncClient(base_url="http://localhost:8001")' in line:
                new_source.append('client = httpx.AsyncClient(base_url="http://localhost:8001", timeout=None)\n')
            else:
                new_source.append(line)
        cell['source'] = new_source

with open('seekr_unified_notebook.ipynb', 'w') as f:
    json.dump(data, f, indent=1)
