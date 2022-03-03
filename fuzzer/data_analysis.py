import json
import os
import argparse
import sys
import random
import pickle
from bit_parser import print_frame
from bit_parser import parse_bitstream

from jpype.types import *
from data_generator import *
from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim
from com.xilinx.rapidwright.design.tools import LUTTools
luttools = LUTTools()

##==========================================##
##            DIFF ANALYSIS                 ##
##==========================================##


def load_pkl_obj(file_name):
    pkl_obj = {}
    if os.path.exists(file_name):
        with open(file_name, 'rb') as handle:
            pkl_obj = pickle.load(handle)
    return pkl_obj


def save_pkl_obj(file_name, pkl_obj):
    with open(file_name, 'wb') as handle:
        pickle.dump(pkl_obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def print_dict(dict_obj, f):
    if f == None:
        for F in dict_obj:
            print(F, dict_obj[F])
    else:
        for F in dict_obj:
            # for x in dict_obj[F]:
            print(F, dict_obj[F], file=f)

def eqn_to_init(eqn):
    #print(eqn)
    pin_map = {'A6': 'I5', 'A5': 'I4','A4': 'I3','A3': 'I2','A2': 'I1','A1': 'I0'}
    if "(0)" in eqn:
        eqn_str = "64\'h0"
    elif "(1)" in eqn:
        if "O6=" in eqn:
            eqn_str = "64\'hFFFFFFFFFFFFFFFF"
        else:
            eqn_str = "64\'h00000000FFFFFFFF"
    elif "O6=0x" in eqn: 
        eqn_str = eqn.split("0x")[-1]
        eqn_str = "64\'h" + str(eqn_str)
    elif "O6=" in eqn: 
        for key in pin_map.keys():
            eqn = eqn.upper().replace(key, pin_map[key])
        eqn = eqn.replace("O6=","O=")
        eqn_str = luttools.getLUTInitFromEquation(eqn,6)
        eqn_str = str(eqn_str)
    elif "O5=0x" in eqn:  
        eqn_str = eqn.split("0x")[-1]
        eqn_str = "32\'h" + str(eqn_str)
    elif "O5" in eqn:  
        for key in pin_map.keys():
            eqn = eqn.upper().replace(key, pin_map[key])
        eqn = eqn.replace("O5=","O=")
        eqn_str = luttools.getLUTInitFromEquation(eqn,5)
        eqn_str = str(eqn_str)
    elif "64" in eqn:
        #print("Returning eqn str:",eqn)
        eqn_str = eqn
    else:
        print("\tUNKNOWN EQN:",eqn)
        eqn_str = "64\'h0"
    #print("\t",eqn_str)
    return eqn_str

def parse_feature_file(f, specimen, tile_type):
    print(f)
    tile_feature_dict = {}
    content = f.readlines()
    content = [x.strip() for x in content]
    for line in content:
        vals = line.split(":", 1)
        # only grab features for target tile type
        if tile_type + "_X" in vals[0]:
            config_bus = "CLB"
            if tile_type in ["BRAM_L", "BRAM_R", "BRAM"]:
                vals2 = vals[1].split(":")
                if len(vals2) == 5:
                    if "RAMB" in vals2[2]:
                        if "INIT" in vals2[3] and vals2[3] not in ["INIT_A", "INIT_B", "EN_SDBITERR_INIT_V6"]:
                            config_bus = "BLO"
            if config_bus+"."+specimen+"."+vals[0] not in tile_feature_dict:
                tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] = []
            if "EQN" in vals[1]:
                eqn = vals[1].rsplit(":",1)[-1]
                init = eqn_to_init(vals[1].rsplit(":",1)[1])
                vals[1] = vals[1].rsplit(":",1)[0] + ":" + init
                #print(eqn,init,vals[1])
            if "\'h" in vals[1]:
                base, num = vals[1].rsplit(":", 1)
                count, num = num.split("\'h")
                num = int(num, 16)
                mask = 1
                for i in range(int(count)):
                    if num & mask:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":["+str(i)+"]"]
                    else:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":!["+str(i)+"]"]
                    mask = mask << 1
            elif "\'b" in vals[1]:
                base, num = vals[1].rsplit(":", 1)
                count, num = num.split("\'b")
                num = int(num, 2)
                mask = 1
                for i in range(int(count)):
                    if num & mask:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":["+str(i)+"]"]
                    else:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":!["+str(i)+"]"]
                    mask = mask << 1
            else:
                tile_feature_dict[config_bus+"."+specimen +"."+vals[0]] += [config_bus[0]+":"+vals[1]]

    # Combine 5LUT and 6LUT properties
    if "CLB" in tile_type or "CLE" in tile_type:
        for T in tile_feature_dict:
            #print("DATA:",tile_feature_dict[T])
            tmp = tile_feature_dict[T].copy()
            for F in tile_feature_dict[T]:
                if "5LUT" in F and "EQN" in F:
                    #print("\tHas 5lut:",F)
                    bus, site, site_type, bel, config, val = F.split(":")
                    bel6 = bel.replace("5","6")
                    new_val = ":".join([bus, site, site_type, bel6, config, val])
                    old_vals = []
                    if "!" in val:
                        old_vals.append(":".join([bus, site, site_type, bel6, config, val.replace("!","")]))
                        old_vals.append(":".join([bus, site, site_type, bel6, config, val]))
                        old_vals.append(F)
                    else:
                        old_vals.append(":".join([bus, site, site_type, bel6, config, "!" + val]))
                        old_vals.append(":".join([bus, site, site_type, bel6, config, val]))
                        old_vals.append(F)
                    #print("VALS:",old_vals,new_val)
                    for x in old_vals:
                        if x in tmp:
                            tmp.remove(x)
                    if new_val not in tmp:
                        tmp.append(new_val)
            tile_feature_dict[T] = tmp.copy()
            #print("\tNew data:",tile_feature_dict[T])
    return tile_feature_dict


def parse_files():
    global fuzz_path
    file_count = 0
    fileList = os.listdir("data/" + fuzz_path + "/")
    for file in sorted(fileList):
        if ".tile" not in file and ".bit" in file and ".dcp" not in file:
            print(file)
            file_count += 1
            # Parse Bitstream
            if int(args.pips) == 1:
                specimen, tile_type, pip_ext, ext = file.split(".")
            else:
                specimen, tile_type, site_index, site_type, bel, primitive, ext = file.split(".")

            f = open("data/" + fuzz_path + "/" + file, "rb")
            tile_bit_dict = parse_bitstream(f, args.family, tilegrid, tile_type, fuzz_path + "." + specimen)
            print("PARSED BIT")
            f.close()
            # Parse Feature file
            f = open("data/" + fuzz_path + "/" + file.replace(".bit", '.ft'))
            tile_feature_dict = parse_feature_file(f, fuzz_path + "." + specimen, tile_type)
            print("PARSED FEATURE")
            f.close()

            save_pkl_obj("data/" + fuzz_path + "/" + file.replace("bit","pkl"), [tile_feature_dict, tile_bit_dict])


def get_solved_bel_bits(bel_dict,tile_type):
    bel_bits = set()
    if tile_type in ["INT_L","INT_R"]:
        for x in ["CLBLL_L","CLBLM_L","CLBLL_R","CLBLM_R"]:
            fj = open("db/db."+tile_type+".json")
            tile_bel_dict = json.load(fj) 
            fj.close()
            bel_bits |= get_solved_bel_bits(tile_bel_dict,x)
        bel_bits |= {"0_48","0_12","0_16","0_44","0_36","0_52","0_56","0_32","0_8","0_16","0_0","0_4","0_20","0_24","0_28"}
        bel_bits |= {"1_3","1_7","1_19","1_47","1_39","1_51","1_55","1_35","1_15","1_31","1_11", "1_43","1_59","1_27","1_23"}
    else:
        bel_bits = set()
        if (type(bel_dict) is dict):
            if "BUS" in bel_dict and bel_dict["BUS"] == "BLOCK_RAM":
                return bel_bits
            for key in bel_dict:
                if key != "TILE_PIP":
                    bel_bits |= get_solved_bel_bits(bel_dict[key],tile_type)
        elif (type(bel_dict) is list):
            for x in bel_dict:
                bel_bits |= set(b.replace("!","") for b in x)
    return bel_bits



def condense_data():
    global feature_dict,tile_data_rev
    fileList = os.listdir("data/" + fuzz_path + "/")
    features = set()
    bits = set()
    data = {}
    tile_data = {}
    for file in sorted(fileList):
        if ".pkl" in file:
            tile_feature_dict, tile_bit_dict = load_pkl_obj("data/" + fuzz_path + "/" + file)
            print("OUTPUT:",tile_feature_dict)
            print("BIT:",tile_bit_dict)
            for x in tile_feature_dict:
                features = features | set(tile_feature_dict[x])
                bits |= set(tile_bit_dict[x])

    feature_dict = {}
    bit_dict = {}
    for i,f in enumerate(features):
        feature_dict[f] = i
    for i,b in enumerate(bits):
        bit_dict[b] = i


    for file in sorted(fileList):
        if ".pkl" in file:
            tile_feature_dict, tile_bit_dict = load_pkl_obj("data/" + fuzz_path + "/" + file)
            for x in tile_feature_dict:
                #print("\t",x)
                tile_data[x] = {}
                tile_data[x]["bits"] = []
                tile_data[x]["features"] = []
                for y in tile_feature_dict[x]:
                    tile_data[x]["features"].append(feature_dict[y])
                for y in tile_bit_dict[x]:
                    tile_data[x]["bits"].append(bit_dict[y])
    features = list(features)
    bits = list(bits)


    tile_data_rev = {}
    for x in range(len(features)):
        tile_data_rev[x] = []

    for x in tile_data:
        for y in tile_data[x]["features"]:
            tile_data_rev[y] += [x]    

    #for x in tile_data_rev:
    #    print(x,tile_data_rev[x])

    return tile_data, features, bits, feature_dict, tile_data_rev


def sensitivity_analysis(tile_data):
    global tile_type, features, bits, tile_data_rev, args
    solved_feature_dict = {}
    
    # Init masks with first present occurance of F
    for F in tile_data_rev:
        print("INIT",F,features[F],tile_data_rev[F][0],list(bits[b] for b in tile_data[tile_data_rev[F][0]]["bits"]))
        solved_feature_dict[F] = set(tile_data[tile_data_rev[F][0]]["bits"])

    # Find always on bits for every property
    if tile_type in ["BRAM_L", "BRAM_R", "BRAM"]:
        # if it is a bram, the bus needs to match
        for T in tile_data:
            bit_set = set(tile_data[T]["bits"])
            for F in tile_data[T]["features"]:
                if features[F][0] == T[0]:
                    solved_feature_dict[F] = solved_feature_dict[F] & bit_set
    else:
        for T in tile_data:
            bit_set = set(tile_data[T]["bits"])
            for F in tile_data[T]["features"]:
                #if "INT_L.SS6END2->>WW2BEG2" in features[F]:
                #    print("AND",solved_feature_dict[F],bit_set)
                solved_feature_dict[F] = solved_feature_dict[F] & bit_set
    
    print("SOLVED FEATURE DICT")
    for x in solved_feature_dict:
        print(features[x],list(bits[b] for b in solved_feature_dict[x]))

    return solved_feature_dict


def sensitivity_analysis_v2(tile_data):
    global tile_type, features, solved_feature_dict
    solved_feature_dict = {}

    default = list(tile_data.keys())[0]
    tile_data_keys = list(tile_data.keys())
    for i in range(len(tile_data_keys)):
        T1 = tile_data_keys[i]
        if "BLO." not in T1:
            for j in range(i+1, len(tile_data_keys)):
                T2 = tile_data_keys[j]
                if "BLO." not in T2:
                    diff_features = set(tile_data[T1]["features"]) - set(tile_data[T2]["features"])
                    #print(T1,T2,diff_features)
                    if len(diff_features) == 1:
                        diff_bits = set(tile_data[T1]["bits"]) - set(tile_data[T2]["bits"])
                        for x in diff_features:
                            solved_feature_dict[x] = diff_bits
                            print(T1, T2, list(features[x] for x in diff_features), list(bits[x] for x in diff_bits))

    return solved_feature_dict


def remove_lut_bits(solved_feature_dict):
    global tile_type, features, bits, tile_data_rev, args
    print("REMOVING LUT BITS:")
    if tile_type in ["CLEL_L","CLEL_R","CLEM_R","CLEM","CLE_M"]:
        lut_bits = set()
        for F in solved_feature_dict: 
            f = features[F].rsplit(":", 1)[0]
            if "6LUT" in f:
                lut_bits |= solved_feature_dict[F]
        print("LUT BITS:",list(bits[x] for x in lut_bits))
        for F in solved_feature_dict: 
            f = features[F].rsplit(":", 1)[0]
            if "6LUT" not in f:
                print("Removing:",features[F],list(bits[x] for x in solved_feature_dict[F]))
                solved_feature_dict[F] = solved_feature_dict[F] - lut_bits
                print("Now:",features[F],list(bits[x] for x in solved_feature_dict[F]))
        
    return solved_feature_dict

def filter_bits(solved_feature_dict):
    global tile_type, features, bits, tile_data_rev, args
    possible_values = {}
    feature_sets = {}
    # remove the pip bits
    if int(args.pips) != 1:
        pip_bits = set()
        for i in range(len(features)):
            if "Tile_Pip" in features[i]:
                pip_bits = pip_bits | solved_feature_dict[i]
        for i in range(len(features)):
            if features[i][0] != "B":
                solved_feature_dict[i] = solved_feature_dict[i] - pip_bits
        if "7" not in args.family:
            solved_feature_dict = remove_lut_bits(solved_feature_dict)
        # Create the per-feature sets of bits
        always_bits = {}
        for F in solved_feature_dict:
            f = features[F].rsplit(":", 1)[0]
            v = features[F].rsplit(":", 1)[1]
            if f not in feature_sets:
                feature_sets[f] = set(solved_feature_dict[F])
                always_bits[f] = set(solved_feature_dict[F])
                possible_values[f] = [v]
            else:
                feature_sets[f] |= solved_feature_dict[F]
                always_bits[f] &= solved_feature_dict[F]
                possible_values[f] += [v]
        for f in feature_sets:
            feature_sets[f] = feature_sets[f]-always_bits[f]
        if "7" not in args.family:
            for f in feature_sets:
                if "[" in possible_values[f][0]:
                    for x in possible_values[f]:
                        bit_set = feature_sets[f]
                        for y in possible_values[f]:
                            if x!=y:
                                bit_set = bit_set - solved_feature_dict[features.index(f + ":" + y)]
                        solved_feature_dict[features.index(f + ":" + x)] = bit_set

    else: # Remove the bel bits
        
        if os.path.exists("db/db."+tile_type+".json") == 0:
            print("[YRAY ERROR]: BEL Fuzzer needs to be run before Pip Fuzzer")
        fj = open("db/db."+tile_type+".json")
        tile_bel_dict = json.load(fj) 
        fj.close()
        bel_bits = get_solved_bel_bits(tile_bel_dict,tile_type)
        bel_bit_idx = set()
        for x in bel_bits:
            if x in bits:
                bel_bit_idx.add(bits.index(x))
        print("BEL BITS:",bel_bits)
        print("BEL BITS:",bel_bit_idx)
        for i in range(len(features)):
            if features[i][0] != "B" and "Tile_Pip" in features[i] and i in solved_feature_dict:
                solved_feature_dict[i] = solved_feature_dict[i] - bel_bit_idx
        # Create the per-pip mux set of bits (Pips that have the same destination)
        always_bits = {}
        for F in solved_feature_dict:
            print(F)
            f = features[F].rsplit(">", 1)[1]
            v = features[F].rsplit(">", 1)[0]
            if f not in feature_sets:
                print("INIT",f,solved_feature_dict[F])
                feature_sets[f] = set(solved_feature_dict[F])
                always_bits[f] = set(solved_feature_dict[F])
                possible_values[f] = [v]
            else:
                print("AND",f,solved_feature_dict[F])
                feature_sets[f] |= solved_feature_dict[F]
                always_bits[f] &= solved_feature_dict[F]
                possible_values[f] += [v]
        #print("FEATURE SETS:")
        # Hardcoded filter: Pips in range 0-25 are in the INT_L/R tiles
        if "7" in args.family:
            if "INT" not in tile_type:
                min_frame = 0
                max_frame = 25
                #for f in feature_sets:
                #    feature_sets[f] = feature_sets[f]-always_bits[f]
            else:
                min_frame = 26
                max_frame = 255
            for f in feature_sets:
                tmp = set()
                for b in feature_sets[f]:
                    if min_frame <= int(bits[b].split("_")[0]) <= max_frame:
                        tmp.add(b)
                feature_sets[f] = feature_sets[f]-tmp


    print("FEATURE SETS:")
    for f in feature_sets:
        print(f,list(bits[b] for b in feature_sets[f]))
    return (feature_sets, possible_values)
    

class Feature():
    def __init__(cls, feat_str):
        '''
        C:0:DSP48E1:INMODE0INV:INMODE0
        C:0:DSP48E1:DSP48E1:BREG:1
        '''
        data = feat_str.split(':')

        # Tile pip
        if len(data) == 1:
            cls.bus = "CLB_IO_CLK"
            cls.type = "TILE_PIP"
            return
        elif len(data) == 2:
            cls.type = "TILE_PIP_OF_BEL"
            return

        if len(data) < 4:
            print(f"Data too short {feat_str}", file=sys.stderr)
        if data[0] == 'C':
            cls.bus = "CLB_IO_CLK"
        elif data[0] == 'B':
            cls.bus = "BLOCK_RAM"
        else:
            print(f"Invalid bus when creating feature with string {feat_str}")
        cls.site_idx = data[1]
        cls.site_type = data[2]
        if len(data) == 5:
            cls.type = "BEL"
            cls.bel = data[3]
            cls.prop = data[4]
        elif len(data) == 4:
            cls.type = "SITE_PIP"
            cls.site_pip = data[3]
        else:
            print(f"Error making Feature class. Bad string: {feat_str}")


def get_bits(tile_data, bit_set, features, vals):
    global tile_data_rev
    ret = {}
    for v in vals:
        ret[v] = set()
    #for s in srcs:
    for idx,f in enumerate(features):
        for T in tile_data_rev[f]:
        #if f in tile_data[T]["features"]:
            result = tile_data[T]["bits"]
            tmp = [bits[x] if x in result else f"!{bits[x]}" for x in bit_set]
            tmp.sort()
            ret[vals[idx]].add(tuple(tmp))
    for k, v in ret.items():
        ret[k] = tuple(v)
    #print(bit_set,features,vals,ret)
    return ret




def merge_json(db,bel_dict):
    if (type(bel_dict) is dict):
        for key in bel_dict:
            if key not in db:
                print("ADDED KEY:",key,bel_dict[key])
                db[key] = bel_dict[key]
            else:
                db[key] = merge_json(db[key],bel_dict[key])
    #else:
    #    db = bel_dict
    return db



def add_missing_features(db):
    global tile_type
    if int(args.pips) != 1:
        fj = open("vivado_db/bel_dict.json")
        bel_dict = json.load(fj) 
        fj.close()
        tile_bel_dict = bel_dict["TILE_TYPE"][tile_type]
    else:
        if os.path.exists("db/db."+tile_type+".json") == 0:
            print("YRAY ERROR: BEL Fuzzer needs to be run before Pip Fuzzer")
        fj = open("db/db."+tile_type+".json")
        tile_bel_dict = json.load(fj) 
        fj.close()

    db = merge_json(db,tile_bel_dict)
    print("FINISHED MERGE")
    return db



def second_analysis(tile_data, properties, values, solved_feature_dict):
    global feature_dict
    res = {"SITE_INDEX": {}, "TILE_PIP": {}}
    sites = res["SITE_INDEX"]
    for feature, bit_set in properties.items():
        feat = Feature(feature)
        if feat.type == "TILE_PIP":
            prop_rules = {}
            vals = values[feature]
            print("TOP",feature,vals)
            #if feature not in res["TILE_PIP"]:
                #print("\tINIT RES",feature)
                #res["TILE_PIP"][feature] = {"INPUTS":{}}
            feature_strs = []
            prop_rules = {}
            for v in vals:
                print("\tPIP SECOND",feature,v)
                feature_str = v + ">" + feature
                pip_name = feature_str.split(":")[1]
                bit_pip_set = solved_feature_dict[feature_dict[feature_str]]
                print("\tBITS:",bit_pip_set)
                bit_pip_set = properties[feature]
                print("\tBIT SET 2:",bit_pip_set)
                feature_strs = [feature_dict[feature_str]]
                v = v.split(".")[1]
                prop_rules.update(get_bits(tile_data, bit_pip_set, feature_strs, [v]))
            for x in prop_rules:
                print("\tSetting",x,prop_rules[x])
                #res["TILE_PIP"][feature]["INPUTS"][x] = {"BITS":prop_rules[x]}
                res["TILE_PIP"][x + ">" + feature] = {"BITS":prop_rules[x]}
        elif feat.type == "TILE_PIP_OF_BEL":
            # Don't solve for pips in the bel fuzzer
            continue
        else:
            if feat.site_idx not in sites:
                sites[feat.site_idx] = {"SITE_TYPE": {
                    feat.site_type: {"BEL": {}, "SITE_PIP": {}}}}
            elif feat.site_type not in sites[feat.site_idx]["SITE_TYPE"]:
                sites[feat.site_idx]["SITE_TYPE"][feat.site_type] = {
                    "BEL": {}, "SITE_PIP": {}}
            site_info = sites[feat.site_idx]["SITE_TYPE"][feat.site_type]
            if feat.type == "SITE_PIP":
                feature_strs = []
                vals = values[feature]
                for v in vals:
                    feature_strs.append(feature_dict[f"{feature}:{v}"])
                prop_rules = get_bits(tile_data, bit_set, feature_strs, vals)
                site_info["SITE_PIP"][feat.site_pip] = {
                    "SITE_PIP_VALUE": prop_rules}
            elif feat.type == "BEL":
                if feat.bel not in site_info["BEL"]:
                    site_info["BEL"][feat.bel] = {"CONFIG": {}}
                bel_info = site_info["BEL"][feat.bel]["CONFIG"]
                vals = values[feature]
                if '[' not in vals[0]:
                    feature_strs = []
                    for v in vals:
                        feature_strs.append(feature_dict[f"{feature}:{v}"])
                    prop_rules = get_bits(tile_data, bit_set, feature_strs, vals)
                    bel_info[feat.prop] = {"VALUE": prop_rules, "BUS": feat.bus}
                else:
                    prop_rules = {}
                    for v in vals:
                        if "!" not in v:
                            feature_str = (f"{feature}:{v}")
                            bit_hex_set = solved_feature_dict[feature_dict[feature_str]].symmetric_difference(solved_feature_dict[feature_dict[feature_str.replace("[","![")]])
                            feature_strs = [feature_dict[feature_str]]
                            prop_rules.update(get_bits(tile_data, bit_hex_set, feature_strs, [v]))
                    bel_info[feat.prop] = {"VALUE": prop_rules, "BUS": feat.bus}
    return res

##==========================================##
##            APPEND DATABASE               ##
##==========================================##


def run_data_analysis(in_fuzz_path, in_args):
    global fuzz_path, args, tile_type, tilegrid, bel_dict, feature_dict
    global bits, features
    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args

    print("Starting Differential Analysis")

    fj = open("vivado_db/tilegrid.json")
    tilegrid = json.load(fj)
    fj.close()
    fj = open("vivado_db/bel_dict.json")
    bel_dict = json.load(fj)
    fj.close()

    parse_files()
    tile_data, features, bits,feature_dict,tile_data_rev = condense_data()

    if tile_type in ["INT_L","INT_R","INT"] or int(args.pips) != 1:
        solved_feature_dict = sensitivity_analysis(tile_data)
    else:
        solved_feature_dict = sensitivity_analysis_v2(tile_data)
    properties, values = filter_bits(solved_feature_dict)
    print(properties,values)
    db = second_analysis(tile_data, properties, values,solved_feature_dict)
    db = add_missing_features(db)

    
    fj = open("db/db."+tile_type+".json", 'w')
    json_database = json.dumps(db, indent=2, sort_keys=True)
    print(json_database, file=fj)
    fj.close()
    print("DONE")
    return

