import os

def search_files(directory, term):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.md', '.txt')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if term.lower() in content.lower():
                            print(f"Found '{term}' in {filepath}:")
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if term.lower() in line.lower():
                                    start = max(0, i - 2)
                                    end = min(len(lines), i + 5)
                                    print(f"  Lines {start}-{end}:")
                                    for j in range(start, end):
                                        print(f"    {j}: {lines[j]}")
                                    print("-" * 40)
                except Exception:
                    pass

search_files("c:/Users/hecto/Nexus_Core", "verificación")
search_files("c:/Users/hecto/Nexus_Core", "queries")
