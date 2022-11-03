import os
from pathlib import Path
from create_lib import LibraryGenerator
from config import DATA_DIR

OOC_DIR = Path("/home/reilly/equiv/bfasst/build/xilinx_ooc/ooc/")


def make_libs():
    for i in OOC_DIR.iterdir():
        design_dir = i / "vivado_synth"
        for j in design_dir.iterdir():
            if j.name.endswith(".dcp"):
                dcp = str(j)
                LibraryGenerator(dcp)
                ip = j.name[:-4]
                os.system(
                    f"python src/search_lib.py data/{ip}/{ip}.dcp --ip={ip} > results/{i.name}.txt"
                )


def search_libs():
    for i in DATA_DIR.iterdir():
        for j in i.iterdir():
            if j.name.endswith(".dcp"):
                ip = j.name[:-4]
                os.system(
                    f"python src/search_lib.py {j} --ip={ip} > results/{i.name}.txt"
                )


if __name__ == "__main__":
    # create_libs()
    search_libs()
