import re

header_path = r"C:\Users\hecto\Documents\Prg_locales\bazzar-web\app\(public)\components\Header.tsx"
with open(header_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_content = re.sub(r'<Link href="/rimec"[\s\S]*?🚢 Rimec\s*</Link>', '', content)

if new_content != content:
    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Header.tsx updated.")
else:
    print("Rimec link not found in Header.tsx")
