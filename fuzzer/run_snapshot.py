#!/usr/bin/env python3
import json
import os
import sys
import argparse
import random
import pickle
from time import sleep

parser = argparse.ArgumentParser()
parser.add_argument('--family',default="spartan7")      # Selects the FPGA architecture family
parser.add_argument('--part',default="DEFAULT")         # Selects the FPGA part - family's default part is chosen if no part is given
parser.add_argument('--tilegrid_only',default="0")      # 1: Only runs the tilegrid generation for the part 0: Run both database and tilegrid generation
parser.add_argument('--extended',default="0")           # 1: Runs fuzzer on the extended set of tiles 0: only runs on the basic tiles
parser.add_argument('--tile',default="NONE")            # NONE: Runs all tiles, or <TILE_NAME> Will run only the single tile
parser.add_argument('--pips',default="0")               # 1: Runs fuzzer on pips 0: dont run pip fuzzer



args = parser.parse_args()

part = args.part

# Default parts when none specified
if args.part == "DEFAULT":
    if args.family == "spartan7":
        part = "xc7s25csga324-1"
    elif args.family == "artix7":
        part = "xc7a100ticsg324-1L"
    elif args.family == "kintex7":
        part = "xc7k70tfbv676-1"
    elif args.family == "virtex7":
        part = "xc7v2000tfhg1761-1"
    elif args.family == "zynq7":
        part = "xc7z015clg485-1"
    elif args.family == "kintexu":
        part = "xcku025-ffva1156-2-e"
    elif args.family == "virtexu":
        part = "xcvu065-ffvc1517-3-e"
    elif args.family == "zynqu":
        part = "DEFAULT"
    elif args.family == "kintexuplus":
        part = "xcku5p-ffvd900-3-e"
    elif args.family == "virtexuplus":
        part = "xcvu3p-ffvc1517-3-e"
    elif args.family == "zynquplus":
        part = "DEFAULT"
    

if part == "DEFAULT":
    print("[ERROR]: NO PART CHOSEN")
    sys.exit()

run_string = [
            "python3 fuzzer.py ",
            " --family=" + args.family + " --part=" + part,
            " > /dev/null"
        ]

series7_run_commands = [
    "CLBLL_L --random_count=500",
    "CLBLL_R --random_count=500",
    "CLBLM_L --random_count=500",
    "CLBLM_R --random_count=500",
    "DSP_L --random_count=1000",
    "DSP_R --random_count=1000",
    "BRAM_L --random_count=150",
    "BRAM_R --random_count=150",
    "INT_L",
    "INT_R",
    "LIOI3 --random_count=400",
    "RIOI3 --random_count=400",
    "LIOB33 --random_count=46 --iterative=0",
    "RIOB33 --random_count=46 --iterative=0",
    "CMT_FIFO_L --random_count=100",
    "CMT_FIFO_R --random_count=100",
    "CFG_CENTER_MID --random_count=20",
    "CLK_HROW_BOT_R --random_count=20 --iterative=0",
    "CLK_HROW_TOP_R --random_count=20 --iterative=0",
    "CLK_BUFG_BOT_R --random_count=40",
    "CLK_BUFG_TOP_R --random_count=40",
    "HCLK_CMT_L --random_count=100",
    "HCLK_CMT --random_count=100",
    "HCLK_IOI3 --random_count=100"
    ]

series7_run_commands_pips = [
    "INT_L --pips=1 --pip_iterations=100",
    "INT_R --pips=1 --pip_iterations=100",
    "DSP_L --pips=1 --pip_iterations=5",
    "DSP_R --pips=1 --pip_iterations=5",
    "BRAM_L --pips=1 --pip_iterations=5",
    "BRAM_R --pips=1 --pip_iterations=5",
    "LIOI3 --pips=1 --pip_iterations=5",
    "RIOI3 --pips=1 --pip_iterations=5",
    "LIOB33 --pips=1 --pip_iterations=5",
    "RIOB33 --pips=1 --pip_iterations=5",
    "CMT_FIFO_L --pips=1 --pip_iterations=5",
    "CMT_FIFO_R --pips=1 --pip_iterations=5",
    "CFG_CENTER_MID --pips=1 --pip_iterations=5",
    "CLK_HROW_BOT_R --pips=1 --pip_iterations=5",
    "CLK_HROW_TOP_R --pips=1 --pip_iterations=5",
    "CLK_BUFG_BOT_R --pips=1 --pip_iterations=5",
    "CLK_BUFG_TOP_R --pips=1 --pip_iterations=5",
    "HCLK_CMT_L --pips=1 --pip_iterations=5",
    "HCLK_CMT --pips=1 --pip_iterations=5",
    "HCLK_IOI3 --pips=1 --pip_iterations=5"
    ]

series7_extended_run_commands = [
    "LIOI3_TBYTESRC  --random_count=200",
    "LIOI3_TBYTETERM  --random_count=200",
    "LIOI3_SING  --random_count=200",
    "RIOI3_TBYTESRC  --random_count=200",
    "RIOI3_TBYTETERM  --random_count=200",
    "RIOI3_SING  --random_count=200",
    "LIOB33_SING  --random_count=15 --iterative=0",
    "RIOB33_SING  --random_count=15 --iterative=0",
    "MONITOR_BOT  --random_count=250 --iterative=0",
    "PCIE_BOT  --random_count=250 --iterative=0",
    "GTP_CHANNEL_0  --random_count=200 --iterative=0",
    "GTP_COMMON  --random_count=150 --iterative=0"
]


ultrascale_run_commands = [
    "BRAM --random_count=200",
    "CLEL_L --random_count=200",
    "CLEL_R --random_count=200",
    "CLE_M --random_count=200",
    "CLE_M_R --random_count=200",
    "DSP --random_count=200",
    "INT --random_count=5"
]

ultrascale_run_commands_pips = [
    "BRAM --pips=1 --pip_iterations=5",
    "CLEL_L --pips=1 --pip_iterations=5",
    "CLEL_R --pips=1 --pip_iterations=5",
    "CLE_M --pips=1 --pip_iterations=5",
    "CLE_M_R --pips=1 --pip_iterations=5",
    "DSP --pips=1 --pip_iterations=5",
    "INT --pips=1 --pip_iterations=40"
]


ultrascale_extended_run_commands = [
    "CMAC_CMAC_FT --random_count=20",
    "GTH_R --random_count=200",
    "GTY_QUAD_LEFT_FT --random_count=200",
    "HPIO_L --random_count=200",
    "HRIO_L --random_count=200",
    "PCIE --random_count=200",
    "ILMAC_ILMAC_FT --random_count=20",
    "XIPHY_L --random_count=100",
    "CFG_CFG --random_count=20",
    "AMS --random_count=200"
]

ultrascale_plus_run_commands = [
    "BRAM --random_count=200",
    "CLEL_L --random_count=200",
    "CLEL_R --random_count=200",
    "CLEM --random_count=200",
    "CLEM_R --random_count=200",
    "DSP --random_count=200",
    "INT --random_count=5"
]

ultrascale_plus_run_commands_pips = [
    "BRAM --pips=1 --pip_iterations=5",
    "CLEL_L --pips=1 --pip_iterations=5",
    "CLEL_R --pips=1 --pip_iterations=5",
    "CLEM --pips=1 --pip_iterations=5",
    "CLEM_R --pips=1 --pip_iterations=5",
    "DSP --pips=1 --pip_iterations=5",
    "INT --pips=1 --pip_iterations=40"
]


ultrascale_plus_extended_run_commands = [
    "CMAC_CMAC_FT --random_count=20",
    "GTH_R --random_count=200",
    "GTY_QUAD_LEFT_FT --random_count=200",
    "HPIO_L --random_count=200",
    "HRIO_L --random_count=200",
    "PCIE --random_count=200",
    "ILMAC_ILMAC_FT --random_count=20",
    "XIPHY_L --random_count=100",
    "CFG_CFG --random_count=20",
    "AMS --random_count=200"
]

def run_command(run_commands):
    for x in run_commands:
        if args.tile == "NONE" or args.tile in x:
            print("[LOG]: RUNNING TILE COMMAND: ",x)
            os.system(run_string[0] + x + run_string[1] + run_string[2])


if args.family[-1] == "7":
    print("[LOG]: RUNNING 7 SERIES", args.family,part)
    run_command(series7_run_commands)
    if args.pips == "1":
        run_command(series7_run_commands_pips)
    if args.extended == "1":
        run_command(series7_extended_run_commands)
elif args.family[-1] == "u":
    print("[LOG]: RUNNING ULTRASCALE", args.family,part)
    run_command(ultrascale_run_commands)
    if args.pips == "1":
        run_command(ultrascale_run_commands_pips)
    if args.extended == "1":
        run_command(ultrascale_extended_run_commands)
elif args.family[-1] == "s":
    print("[LOG]: RUNNING ULTRASCALE+", args.family,part)
    run_command(ultrascale_plus_run_commands)
    if args.pips == "1":
        run_command(ultrascale_plus_run_commands_pips)
    if args.extended == "1":
        run_command(ultrascale_plus_extended_run_commands)

