"""Global path variables."""

from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_PATH / "data"
LIB_DIR = ROOT_PATH / "library"
CHECKPT_DIR = ROOT_PATH / "checkpoints"
RES_DIR = ROOT_PATH / "results"
RECORD_CORE_TCL = ROOT_PATH / "src" / "record_core.tcl"
CORE_FUZZER_TCL = ROOT_PATH / "src" / "core_fuzzer.tcl"
TEST_RESOURCES = ROOT_PATH / "test_resources"
