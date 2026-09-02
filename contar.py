import os

total = 0
for root, dirs, files in os.walk("."):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    linhas = len(file.readlines())
                    total += linhas
                    print(f"{linhas:4} - {path}")
            except:
                pass

print(f"\nTOTAL: {total} linhas de Python")
