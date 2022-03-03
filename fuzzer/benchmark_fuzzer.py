import json
import os
import argparse
import sys
import random
import pickle
from multiprocessing import Pool
import jpype
import jpype.imports
from jpype.types import *
jpype.startJVM(classpath=["rapidwright-2021.2.0-standalone-lin64.jar"])

parser = argparse.ArgumentParser()
#parser.add_argument('file_name', nargs=1)                              # Selects the target tile type
#parser.add_argument('--family',default="artix7")                        # Selects the FPGA architecture family
#parser.add_argument('--part',default="xc7a100ticsg324-1L")              # Selects the FPGA part
#parser.add_argument('--family',default="kintexuplus")                        # Selects the FPGA architecture family
#parser.add_argument('--part',default="xcku5p-ffvd900-3-e")              # Selects the FPGA part
parser.add_argument('--family',default="kintexu")                        # Selects the FPGA architecture family
parser.add_argument('--part',default="xcku025-ffva1156-2-e")              # Selects the FPGA part
parser.add_argument('--keep_files',default=1)                           # 1: Keep all files generated. 0: Only keep final output
parser.add_argument('--benchmark_path',default="../benchmark/xc7a100/")    # Path to folder of .dcp benchmarks
parser.add_argument('--update_tile',default="NONE")                     # Updating just a single YRAY tile def
args = parser.parse_args()

os.chdir(args.family + "/" + args.part + "/")
from bit_parser import print_frame
from bit_parser import parse_bitstream
from bit2phy import feature_test
from bit2phy import parse_tile2
from data_analysis import parse_feature_file
from data_analysis import save_pkl_obj
from data_analysis import load_pkl_obj
os.chdir("../../")

benchmark_path = args.benchmark_path
fileList = os.listdir(benchmark_path)
benchmarks = []
for item in fileList:
    if ".dcp" in item:# and "microblaze_base_fft_x3" in item:
        benchmarks.append(benchmark_path + item)


fileList = os.listdir(args.family + "/" + args.part + "/db/")
tile_list = []
for file in sorted(fileList):
    #if "CLE" in file:
    tile_list.append(file.split(".")[1])
    
os.chdir(args.family + "/" + args.part + "/")

fj = open("vivado_db/tilegrid.json")
tilegrid = json.load(fj) 
fj.close()
os.makedirs("benchmark_data/", exist_ok=True)

def run_benchmark_fuzzer_p1(file_name):
    print(file_name)
    
    design_name = file_name.split("/")[-1].replace(".dcp","")
    os.makedirs("benchmark_data/" + design_name + "/", exist_ok=True)
    bitstream_name = "benchmark_data/" + design_name + "/design.bit"
    feature_file_name = "benchmark_data/" + design_name + "/"

    tile_input_list = "\"{"
    for i in range(len(tile_list)):
        tile_input_list += tile_list[i]
        if i != len(tile_list) - 1 :
            tile_input_list += " "
    tile_input_list += "}\""
    if os.path.exists(bitstream_name) == False:
        print("FILE DOESNT EXIST",bitstream_name)
        os.system("vivado -mode batch -source ../../parse_benchmark.tcl -tclarg ../../" + file_name + " " + bitstream_name + " " + feature_file_name + " " + tile_input_list )

def run_benchmark_fuzzer_p2(file_name):
    print(file_name)
    # Parse Feature Files
    design_name = file_name.split("/")[-1].replace(".dcp","")
    os.makedirs("benchmark_data/" + design_name + "/", exist_ok=True)
    bitstream_name = "benchmark_data/" + design_name + "/design.bit"
    feature_file_name = "benchmark_data/" + design_name + "/"

    if os.path.exists(bitstream_name) == False:
        print("RETURNING")
        return
    fileList = os.listdir("benchmark_data/" + design_name + "/")
    tile_feature_dict = {}
    phy_feature_dict = {}

    if args.update_tile == "NONE":
        for file in sorted(fileList):
            if ".ft" in file:
                print(file)
                pkl_file_name = "benchmark_data/" + design_name + "/" + file.replace(".ft",".pkl")
                #if os.path.exists(pkl_file_name) == False:
                f = open("benchmark_data/" + design_name + "/" + file)
                tile_type = file.split(".")[0]
                temp_feature_dict = parse_feature_file(f,"0",tile_type)
                f.close()
                f = open(bitstream_name, "rb")
                tile_bit_dict = parse_bitstream(f, args.family, tilegrid, tile_type, "0")
                f.close()
                tile_feature_dict[tile_type] = {}
                for x in temp_feature_dict:
                    tile_feature_dict[tile_type][x] = temp_feature_dict[x]
        # Remove ! hex values in actual:
        for x in tile_feature_dict:
            tile_feature_dict[x] ={i: [a for a in j if "!" not in a] for i,j in tile_feature_dict[x].items()}
    else:
        fj = open("benchmark_data/" + design_name + "/output.json")
        try:
            output = json.load(fj) 
        except:
            return
        fj.close()
        tile_feature_dict = output["ACTUAL"]
        phy_feature_dict = output["YRAY"]


    # Call bit to phy
    for tile_type in tile_list:
        if args.update_tile == "NONE" or tile_type == args.update_tile:
            fj = open("db/db." +tile_type + ".json", "r")
            database = json.load(fj)
            fj.close()
            f = open(bitstream_name, "rb")
            tile_data_dict = parse_bitstream(f, args.family, tilegrid, tile_type, "0")
            f.close()
            phy_feature_dict[tile_type] = {}
            for tile in sorted(tile_data_dict):
                if len(tile_data_dict[tile]) != 0:
                    phy_feature_dict[tile_type][tile] = parse_tile2(database, tile,tile_data_dict,tile_type)
            

    # Delete all generated files - save space when doing this for every benchmark
    if int(args.keep_files) == 0:
        for f in os.listdir("benchmark_data/" + design_name + "/"):
            if ".bit" not in f and "output.json" not in f:
                os.remove(os.path.join("benchmark_data/" + design_name + "/", f))

    fj = open("benchmark_data/" + design_name + "/output.json","w")
    out_json = {"ACTUAL":tile_feature_dict,"YRAY":phy_feature_dict}
    json_database = json.dumps(out_json,indent=2,sort_keys=True)
    print(json_database,file=fj)
    fj.close()


if args.update_tile == "NONE":
    pool = Pool(processes=8)
    pool.map(run_benchmark_fuzzer_p1, benchmarks)

for x in benchmarks:
    run_benchmark_fuzzer_p2(x)

