from pathlib import Path
import os

ignores = [
    "LICENSE",
    "iter.py"
]

def processFile(p):
    cmd = f"cat /tmp/LICENSE {p}.sav > {p}"
    print(cmd)
    os.system(cmd)

def main():
    for p in Path( '.' ).rglob( '*' ):
        if str(p) in ignores:
            pass
        elif str(p).startswith(".git"):
            pass
        elif str(p).endswith(".json"):
            pass
        elif str(p).endswith(".png"):
            pass
        elif str(p).endswith(".sav"):
            pass
        elif p.is_dir():
            pass
        else:
            #print(p)
            processFile( str(p) )

main()
