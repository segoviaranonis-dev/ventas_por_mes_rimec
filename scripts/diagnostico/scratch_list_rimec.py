import os

bazzar_rimec = r"C:\Users\hecto\Documents\Prg_locales\bazzar-web\app\(public)\rimec"
print("Files in", bazzar_rimec)
for root, dirs, files in os.walk(bazzar_rimec):
    for f in files:
        print(os.path.join(root, f))
