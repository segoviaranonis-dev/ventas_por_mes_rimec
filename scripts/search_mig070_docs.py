import os

def search_files(directory, search_str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.md', '.sql', '.py', '.txt')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if search_str.lower() in content.lower():
                            print(f"Found '{search_str}' in: {filepath}")
                except Exception:
                    pass

print("Searching workspace for 'MIG-070'...")
search_files("c:/Users/hecto/Nexus_Core", "MIG-070")
print("Searching workspace for 'verificación post-migración'...")
search_files("c:/Users/hecto/Nexus_Core", "verificación")
