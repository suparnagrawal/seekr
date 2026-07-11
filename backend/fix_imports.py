import os

directory = '/home/suparn/seekr/backend'
for root, _, files in os.walk(directory):
    for file in files:
        if file.endswith('.py') and ('/app/' in root or '/app' == root or '/tests/' in root or '/tests' == root):
            filepath = os.path.join(root, file)
            with open(filepath, 'r') as f:
                content = f.read()
            if 'from app.' in content or 'import app.' in content:
                content = content.replace('from app.', 'from backend.app.')
                content = content.replace('import app.', 'import backend.app.')
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"Fixed {filepath}")
