#!/usr/bin/env python3
import glob
import json
import os
import sys
import argparse
import random
import numpy as np
from bit_parser import print_frame
from bit_parser import parse_bitstream
from multiprocessing import Pool
import pickle
from time import sleep


##================================================================================##
##                                PARSE THE TILE DATA                             ##
##================================================================================##


def test_bits(valv,tile_data):
    for eq in valv:
        found_eq = 1
        for B in eq:
            if "!" in B:
                B_not = B.replace("!","")
                if B_not in tile_data:
                    found_eq = 0
                    break
            else:
                if B not in tile_data:
                    found_eq = 0
                    break
        if found_eq == 1:
            return 1
    return 0
        
def feature_test(props, tile, loc, value,tile_data_dict):
    features = []
    for prop, propv in props.items():
        if "BUS" not in propv:
            bus = "C"
        else:
            bus = propv["BUS"][0]
        if bus == tile[0]:
            for val, valv in propv[value].items():
                #if "CLBL" in tile:
                    #print("TESTING:",tile,loc,prop,val,tile_data_dict[tile])
                #    p = 1
                if test_bits(valv,tile_data_dict[tile]):
                    #if "CLBL" in tile:
                    #    print("\tPASSED")
                    found_feature = ":".join([bus+":"+loc, prop, val])
                    features.append(found_feature)
                    #break
    return features

def parse_tile2(d, t,tile_data_dict,tile_type):
    features = []
    for i, iv in d["SITE_INDEX"].items():
        for site, sitev in iv["SITE_TYPE"].items():
            for bel, belv in sitev["BEL"].items():
                features += feature_test(belv["CONFIG"],t,":".join([i, site,bel]),"VALUE",tile_data_dict)
            features += feature_test(sitev["SITE_PIP"],t,":".join([i,site]),"SITE_PIP_VALUE",tile_data_dict)
    # Add Tile pips
    for i, iv in d["TILE_PIP"].items():
        if "BITS" in iv:
            if (test_bits(iv["BITS"],tile_data_dict[t])):
                #C:Tile_Pip:INT_L.WW4END0->>WW4BEG0
                features += [":".join(["C","Tile_Pip",tile_type + "." + i])]

    return features

def parse_tile(nested_dictionary, tile, path):
    global tile_data_dict
    for key, value in nested_dictionary.items():
        if key == "VALUE" or key == "SITE_PIP_VALUE":
            found_feature = "NONE"
            found_default = 1
            for v in value:
                found = 1
                for B in value[v]["ON"]:
                    if B not in tile_data_dict[tile]:
                        found = 0
                if found == 1:
                    if found_feature == "NONE" and len(value[v]["ON"]) == 0:
                        found_feature = path + ":" + key + ":" + v
                    elif len(value[v]["ON"]) != 0:
                        found_default = 0
                        found_feature = path + ":" + key + ":" + v
                        print(found_feature)
            if found_default == 1 and found_feature != "NONE":
                print("DEFAULT:", found_feature)

        elif type(value) is dict:
            parse_tile(value, tile, path + ":" + key)


##================================================================================##
##                                PARSE THE BITSTREAM                             ##
##================================================================================##

def main():
    parser = argparse.ArgumentParser(
        description="Look at bits in a bitstream and translate to rules that should fire as a result."
    )
    # Please use argparse for all our scripts, it is the only sane way to make a program parameterizable
    parser.add_argument("bit_file")
    parser.add_argument("--tile")
    parser.add_argument("--dumpdict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--family", default="artix7")
    parser.add_argument("--part_name", default="xc7a100ticsg324-1L")
    parser.add_argument("--path_to_db_folder", default="../byu_db/")
    parser.add_argument("--path_to_tilegrid", default="../byu_db/tilegrid.json")

    args = parser.parse_args()

    fs = open(args.path_to_tilegrid, "r")
    tilegrid = json.load(fs)

    for x in glob.glob(args.path_to_db_folder + "db.*.json"):
        tile_type = os.path.basename(x).split(".")[1]
        if args.tile is not None and args.tile != tile_type:
            continue

        fj = open(x, "r")
        database = json.load(fj)
        fj.close()
        f = open(args.bit_file, "rb")
        tile_data_dict = parse_bitstream(f, args.family, tilegrid, tile_type, "0")
        f.close()

        if args.dumpdict:
            print(f"\nBits for tile type: {tile_type}")
            for key, val in tile_data_dict.items():
                if len(val) != 0:
                    val.sort()
                    print(f"  {key}: {val}")
            print()

        for tile in sorted(tile_data_dict):
            if len(tile_data_dict[tile]) != 0:
                print("## ", tile, " ##")
                parse_tile2(database, tile,tile_type)
    fs.close()

#main()
