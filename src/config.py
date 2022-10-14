from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parent.parent
VIVADO = "/tools/Xilinx/Vivado/2020.2/bin/vivado"
DATA_DIR = ROOT_PATH / "data"
LIB_DIR = ROOT_PATH / "library"
CHECKPT_DIR = ROOT_PATH / "checkpoints"
RES_DIR = ROOT_PATH / "results"