import json
import os
import argparse
import sys
import random
import pickle


parser = argparse.ArgumentParser()
#parser.add_argument('--family',default="artix7")              # Selects the FPGA architecture family
#parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
#parser.add_argument('--family',default="kintexuplus")                        # Selects the FPGA architecture family
#parser.add_argument('--part',default="xcku5p-ffvd900-3-e")              # Selects the FPGA part
parser.add_argument('--family',default="kintexu")                        # Selects the FPGA architecture family
parser.add_argument('--part',default="xcku025-ffva1156-2-e")              # Selects the FPGA part
parser.add_argument('--tile',default="ALL")                   # Validates ALL or a given tile

args = parser.parse_args()

db_path = args.family + "/" + args.part + "/db/"
benchmark_path = args.family + "/" + args.part + "/benchmark_data/"

fileList = os.listdir(db_path)
tile_list = []
for file in sorted(fileList):
    if args.tile == "ALL" or args.tile in file:
        tile_list.append(file.split(".")[1])

fileList = os.listdir(benchmark_path)
benchmarks = []
for item in fileList:
    if os.path.exists(benchmark_path + item + "/output.json") == True:
        benchmarks.append(benchmark_path + item + "/output.json")

def parse_db(db,tile_type):
    features = []
    for i, iv in db["SITE_INDEX"].items():
        for site, sitev in iv["SITE_TYPE"].items():
            for bel, belv in sitev["BEL"].items():
                for prop, propv in belv["CONFIG"].items():
                    if "BUS" not in propv:
                        bus = "C"
                    else:
                        bus = propv["BUS"][0]
                    for val, valv in propv["VALUE"].items():
                        features += [":".join([bus,i, site,bel,prop,val])]
            for prop, propv in sitev["SITE_PIP"].items():
                for val, valv in propv["SITE_PIP_VALUE"].items():
                    features += [":".join(["C",i, site,prop,val])]
    for t, tv in db["TILE_PIP"].items():   
        features += [":".join(["C","Tile_Pip",tile_type+"."+t])]
        #print(":".join(["C","Tile_Pip",tile_type+"."+t]))
    return features


def is_configurable(db,F):
    try:
        bus, ext, pip = F.split(":")
        pip = pip.split(".")[1]
        if db["TILE_PIP"][pip]["TYPE"] != "PIP":
            return 0
    except:
        return 1
    return 1

def validate(db,features,tile_type):
    feature_pass = {}
    for F in features:
        feature_pass[F] = [0,0,0]
    ALWAYS = 0
    PRESENT = 1
    NEVER = 2
    target_feature = ["B:0:RAMB36E1:RAMB36E1:INIT_00:[11]"] #"C:0:IOB33:IBUFDISABLE_SEL:GND"
    
    for B in benchmarks:
        print(B)
        fs = open(B, "r")
        bd = json.load(fs)
        fs.close()
        if tile_type in bd["ACTUAL"]:
            for T in bd["ACTUAL"][tile_type]:
                if T in bd["YRAY"][tile_type]:
                    for F in bd["ACTUAL"][tile_type][T]:
                        #if F in target_feature:
                        #    print(F,B)
                        if F in feature_pass:
                            if F in bd["YRAY"][tile_type][T]:
                                feature_pass[F][ALWAYS] = feature_pass[F][ALWAYS]+1
                                feature_pass[F][PRESENT] = feature_pass[F][PRESENT]+1
                            else:
                                #print("FEATURE MISSING",F,T)
                                feature_pass[F][PRESENT] = feature_pass[F][PRESENT]+1
                    for F in bd["YRAY"][tile_type][T]:
                        if F not in bd["ACTUAL"][tile_type][T]:
                            if F in feature_pass:
                                feature_pass[F][NEVER] = feature_pass[F][NEVER]+1
                else:
                    if "BLO" not in T:
                        print("MISSING TILE",T,B)
                    #for F in bd["ACTUAL"][tile_type][T]:
                    #    if F in feature_pass:
                    #        feature_pass[F][PRESENT] = feature_pass[F][PRESENT]+1
                        

                
    tabulated_output = []
    percent_sum = 0
    percent_count = 0
    for F in feature_pass:
        if "5LUT" not in F:
            if "Tile_Pip" not in F or is_configurable(db,F):
                if feature_pass[F][PRESENT]!=0:
                    percent_num = feature_pass[F][ALWAYS]/feature_pass[F][PRESENT]
                    percent_sum += percent_num
                    percent_count += 1
                    percent = "{:.0%}".format(percent_num)
                    tabulated_output.append([F,percent,feature_pass[F][ALWAYS],feature_pass[F][PRESENT],feature_pass[F][NEVER]])
                else:
                    tabulated_output.append([F,"-","-","-",feature_pass[F][NEVER]])
            

    print("\n--" + "="*100 + "--")
    print("TILE:",tile_type)
    print ("{:<60} {:<10} {:<10} {:<10} {:<10}".format('FEATURE', 'PRECENT', 'FIRED', 'PRESENT','MISFIRE'))
    tmp = [tile_type,0,0,0,0,0]
    for v in tabulated_output:
        print ("{:<60} {:<10} {:<10} {:<10} {:<10}".format(v[0], v[1], v[2], v[3],v[4]))
        tmp[1] = tmp[1] + 1
        if v[1] == "-":
            tmp[5] = tmp[5] + 1
        else:
            if v[1] == "100%":
                tmp[2] = tmp[2] + 1
            else:
                tmp[3] = tmp[3] + 1
    if percent_count != 0:
        tmp[4] = "{:.0%}".format(percent_sum/percent_count)
    final_table.append(tmp)


final_table = []
for x in tile_list:
    fs = open(db_path + "db." + x + ".json", "r")
    db = json.load(fs)
    fs.close()
    features = parse_db(db, x)
    validate(db,features,x)


print("\n\n\n--" + "="*100 + "--\n FINAL OUTPUT:\n")
print ("{:<20} {:<20} {:<15} {:<15} {:<15} {:<15}".format('TILE TYPE','NUM FEATURES', '100% COUNT', 'INCORRECT', 'AVERAGE','UNTESTED'))
for v in final_table:
    print ("{:<20} {:<20} {:<15} {:<15} {:<15} {:<15}".format(v[0], v[1], v[2], v[3],v[4], v[5]))
