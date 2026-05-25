import os

rimec_web = r"C:\Users\hecto\Documents\Prg_locales\rimec-web\app"
print("Files in", rimec_web)
for root, dirs, files in os.walk(rimec_web):
    for f in files:
        if f.endswith('.tsx') or f.endswith('.ts') or f.endswith('.css'):
            print(os.path.join(root, f))
