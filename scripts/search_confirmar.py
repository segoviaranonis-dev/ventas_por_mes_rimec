import os

def search_files(directory, search_str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.ts', '.tsx', '.js', '.jsx', '.json')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if search_str in content:
                            print(f"Found in: {filepath}")
                except Exception:
                    pass

search_files("c:/Users/hecto/Nexus_Core/rimec-web", "confirmar_pedido_web")
