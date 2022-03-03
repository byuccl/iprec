import json
import os
import argparse
import sys
import random
from bit_parser import print_frame
from bit_parser import parse_bitstream
import numpy as np

##===============================================##
##                   TILEGRID                    ##
##===============================================##

fj = open("vivado_db/tilegrid.json")
tilegrid = json.load(fj) 
fj.close()

tilegrid_feature_dict = {}
tilegrid_bit_dict = {}
tilegrid_frame_dict = {}
fuzz_path = ""
tile_type = ""





def parse_tilegrid_files(fileList):
    has_data = 0
    tilegrid_frame_dict = {}
    for file in sorted(fileList):
        if ".tile" in file:
            print(file)
            if ".bit" in file and ".dcp" not in file:
                has_data = 1
                specimen,tile_type,site_index,site_type,bel,primitive,tile,ext = file.split(".")
                tilegrid_bit_dict[specimen] = {}
                tilegrid_feature_dict[specimen] = {}

                f = open("data/" + fuzz_path + "/" + file,"rb")
                tile_bits, tilegrid_frame_dict = parse_bitstream(f, args.family,None,tile_type,specimen)
                for x in tile_bits:
                    tilegrid_bit_dict[specimen][x] = tile_bits[x]
                f.close()
                ft_file = "data/" + fuzz_path + "/" + file
                f = open(ft_file.replace(".bit",".ft"))
                content = f.readlines()
                f.close()

                content = [x.strip() for x in content]
                for line in content: 
                    vals = line.split(":",1)                    
                    if vals[0] not in tilegrid_feature_dict[specimen]:
                        tilegrid_feature_dict[specimen][vals[0]] = np.array([vals[1]],dtype=object)
                    else:
                        tilegrid_feature_dict[specimen][vals[0]] = np.insert(tilegrid_feature_dict[specimen][vals[0]],0, vals[1])

    return tilegrid_feature_dict, has_data,tilegrid_frame_dict



def get_column_address(tilegrid_feature_dict,tilegrid_frame_dict):
    tilegrid_diff = {}
    if args.family in ["artix7","kintexu", "spartan7","kintex7","virtex7","virtexu","zynqu","zynq"]:
        col_mask = 0xFF80
        block_shift = 23
    else:
        col_mask = 0x1FF00
        block_shift = 24
    key_list = list(sorted(tilegrid_feature_dict.keys()))
    for i in range(len(key_list)):
        print("NEW KEY",i,key_list[i])
        S1 = key_list[i]
        for j in range(i+1, len(key_list)):
            print("\tNEW NEXT KEY:",j,key_list[j])
            S2 = key_list[j]
            diff_tiles = []
            for T in tilegrid_feature_dict[S1].keys():
                print("\t\tTILE:",T)
                if T in tilegrid_feature_dict[S1] and T in tilegrid_feature_dict[S2]:
                    diff = set(tilegrid_feature_dict[S1][T]).symmetric_difference(tilegrid_feature_dict[S2][T])
                    if diff:
                        diff_tiles.append(T)
            print("DIFF_TILES:",diff_tiles)
            diff_columns = []
            for x in diff_tiles:
                tile_col_name = x.rsplit("Y",1)[0]
                if tile_col_name not in diff_columns:
                    diff_columns.append(tile_col_name)
            if len(diff_columns) == 1:
                print("DIFF_TILES:",diff_tiles,diff_columns)
                tile_col_name = diff_tiles[0].rsplit("Y",1)[0]
                for B in tilegrid_bit_dict[S1].keys():
                    diff_bit = set(tilegrid_bit_dict[S1][B]).symmetric_difference(tilegrid_bit_dict[S2][B])
                    if diff_bit:
                        print("DIFF_BITS:",diff_bit)
                        col_addr = B & col_mask
                        if B < (1<<block_shift):
                            tilegrid_diff[tile_col_name] = {}
                            tilegrid_diff[tile_col_name]["COL_ADDR"] = col_addr
                            tilegrid_diff[tile_col_name]["FRAME_COUNT"] = tilegrid_frame_dict[B] + 1
    print("DIFF TILE COLUMNS",tilegrid_diff)
    
    return tilegrid_diff


def estimate_column_address(col_name):
    if args.family in ["artix7","kintexu", "spartan7","kintex7","virtex7","virtexu","zynqu","zynq"]:
        col_shift = 7
        col_addr = int(col_name.rsplit("X")[-1]) << col_shift
    else:
        col_shift = 8
        # This estimate is not correct for ultrascale/+, I think it is X_coord * 3 + index.(L,C,R)
        col_addr = int(col_name.rsplit("X")[-1]) << col_shift
    print(col_name,int(col_name.rsplit("X")[-1]),col_addr,col_shift)
    return col_addr

def solve_tilegrid():
    global tile_type, fuzz_path
    print("Starting Tilegrid analysis")
    fileList = os.listdir("data/" + fuzz_path + "/")
    tilegrid_feature_dict, has_data, tilegrid_frame_dict = parse_tilegrid_files(fileList)
          
    
    tilegrid_diff = get_column_address(tilegrid_feature_dict,tilegrid_frame_dict)


    int_tile_dict = {}
    max_clock_y = 0
    for T in tilegrid:
        if tilegrid[T]["TYPE"] in ["INT_L", "INT_R", "INT"]:
            if args.family in ["artix7","spartan7","kintex7","virtex7"]:
                int_tile_dict[tilegrid[T]["TILE_Y"]] = tilegrid[T]["Y"]%50
            else:
                int_tile_dict[tilegrid[T]["TILE_Y"]] = tilegrid[T]["Y"]%60
        if tilegrid[T]["CLOCK_Y"] > max_clock_y:
            max_clock_y = tilegrid[T]["CLOCK_Y"]

    if max_clock_y == 0:
        half_clock = 0
    else:
        half_clock = int(max_clock_y/2 + 1)
    print("MAX_CLOCK:",max_clock_y,half_clock)
    # Assign base addresses
    for T in tilegrid:
        if tilegrid[T]["TYPE"] == tile_type:
            if args.family in ["artix7","spartan7","kintex7","virtex7"]:
                if tilegrid[T]["CLOCK_Y"] >= half_clock:
                    clock_col = tilegrid[T]["CLOCK_Y"] - half_clock
                    top = 0
                else:
                    clock_col = half_clock - tilegrid[T]["CLOCK_Y"] - 1
                    top = 1
            else:
                clock_col = tilegrid[T]["CLOCK_Y"]
                top = 0

            tile_col_name = T.rsplit("Y",1)[0]
            if tilegrid[T]["CLOCK_Y"] == -1: # see CLK_BUFG_BOT_R, move this to get_db.tcl
                clock_col = 0
            if tile_col_name in tilegrid_diff: 
                col_addr = tilegrid_diff[tile_col_name]["COL_ADDR"]
                print("FOUND COL ADDR",tile_col_name,col_addr)   
            else:
                col_addr = estimate_column_address(tile_col_name)
                print("CALC COL ADDR",tile_col_name,col_addr)   
            height = tilegrid[T]["HEIGHT"]
            if args.family in ["artix7", "spartan7","kintex7","virtex7"]:
                crc = [50]
                if height == 2:
                    int_y = tilegrid[T]["TILE_Y"]
                elif height%2 == 0:
                    int_y = tilegrid[T]["TILE_Y"] - int(height/4*3200) + 1600
                else:
                    int_y = tilegrid[T]["TILE_Y"] - (int(height/4))*3200
                words_per_int = 2
            elif args.family in ["kintexu","zynqu","virtexu"]:
                crc = [60,61,62]
                int_y = tilegrid[T]["TILE_Y"]
                words_per_int = 2
            else:
                crc = [90,91,92,93,94,95]
                int_y = tilegrid[T]["TILE_Y"]
                words_per_int = 3
            
            if int_y not in int_tile_dict:
                absolute_difference_function = lambda list_value : abs(list_value - int_y)
                int_y = min(int_tile_dict, key=absolute_difference_function)
                offset = int_tile_dict[int_y] * words_per_int
            else:
                offset = int_tile_dict[int_y] * words_per_int
            if tile_type in ["HCLK_IOI3"]:
                offset = 50
            elif offset >= crc[0]:
                offset += len(crc)
            if args.family in ["kintexuplus", "zynquplus","virtexuplus"]:
                base_addr = (top<<23) + (clock_col<<18) + (col_addr)
            else:
                base_addr = (top<<22) + (clock_col<<17) + (col_addr)
            
            tilegrid[T]["bits"] = {}
            tilegrid[T]["bits"]["CLB_IO_CLK"] = {}
            tilegrid[T]["bits"]["CLB_IO_CLK"]["baseaddr"] = hex(base_addr)
            if tile_col_name in tilegrid_diff:
                tilegrid[T]["bits"]["CLB_IO_CLK"]["frames"] = tilegrid_diff[tile_col_name]["FRAME_COUNT"]
            else:
                tilegrid[T]["bits"]["CLB_IO_CLK"]["frames"] = -1
            tilegrid[T]["bits"]["CLB_IO_CLK"]["offset"] = offset
            tilegrid[T]["bits"]["CLB_IO_CLK"]["words"] = height
            
            if tilegrid[T]["TYPE"] in ["BRAM_L","BRAM_R", "BRAM"]:
                tilegrid[T]["bits"]["BLOCK_RAM"] = {}
                col_addr = tile_dict["BRAM_COLUMNS"].index(tilegrid[T]["COL"])
                if args.family in ["kintexuplus", "zynquplus","virtexuplus"]:
                    base_addr = (1<<24) + (top<<23) + (clock_col<<18) + (col_addr << 8)
                    frame_max = 256
                else:
                    base_addr = (1<<23) + (top<<22) + (clock_col<<17) + (col_addr << 7)
                    frame_max = 128
                
                tilegrid[T]["bits"]["BLOCK_RAM"]["baseaddr"] = hex(base_addr)
                tilegrid[T]["bits"]["BLOCK_RAM"]["frames"] = frame_max
                tilegrid[T]["bits"]["BLOCK_RAM"]["offset"] = offset
                tilegrid[T]["bits"]["BLOCK_RAM"]["words"] = height

    fj = open("vivado_db/tilegrid.json",'w')
    json_database = json.dumps(tilegrid,indent=2,sort_keys=True)
    print(json_database,file=fj)
    fj.close()



def run_tilegrid_solver(in_fuzz_path,in_args):
    global fuzz_path, args,tile_type, tile_dict
    tile_type = in_args.tile_type[0]
    print("RUNNING TILEGRID SOLVER")
    fuzz_path = in_fuzz_path
    args = in_args
        
    fj = open("vivado_db/tile_dict.json")
    tile_dict = json.load(fj) 
    fj.close()

    solve_tilegrid()
    
    fj = open("vivado_db/tilegrid.json",'w')
    json_database = json.dumps(tilegrid,indent=2,sort_keys=True)
    print(json_database,file=fj)
    fj.close()