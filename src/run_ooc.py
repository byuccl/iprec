import os
from pathlib import Path
import create_lib

OOC_DIR = Path("/home/reilly/equiv/bfasst/build/xilinx_ooc/ooc/")


if __name__ == "__main__":

    for i in OOC_DIR.iterdir():
        file = i / "vivado_synth" / "design.dcp"
        if file.exists():
            create_lib.main(str(file), i.name)
            break
            os.system(
                f"python search_lib.py {file} --ip={i.name} > results/{i.name}.txt"
            )
        break
