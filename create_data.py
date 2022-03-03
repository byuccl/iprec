
#!/usr/bin/env python3
import json
import os
import sys
import argparse
import random
import numpy as np
import re
import pickle
from igraph import *
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--ip',default="xilinx.com:ip:c_accum:12.0")    # Selects the target IP
parser.add_argument('--part',default="xc7a100ticsg324-1L")          # Selects the FPGA architecture part
parser.add_argument('--ignore_integer',default="1")                 #
parser.add_argument('--integer_step',default=1)                     #
parser.add_argument('--default_only',default=0)                     #
parser.add_argument('--random_count',default=100)                   # Number of random IP                

#import create_lib
#from create_lib import *

args = parser.parse_args()
print(args)

ip = args.ip
part_name = args.part
launch_file_name = "data/" + ip + "/launch.tcl"

os.makedirs("library/", exist_ok=True) 
os.makedirs("library/" + ip + "/", exist_ok=True) 
os.makedirs("data/"+ip+"/", exist_ok=True) 


##================================================================================##
##                                CREATE TCL SCRIPT                               ##
##================================================================================##                  


def source_fuzzer_file():
    print("source core_fuzzer.tcl",file=ft)

def init_design():
    global ip,part_name
    print("set ip " + ip,file=ft)
    print("create_design $ip " + part_name,file=ft)

def set_property(prop, value):
    print(prop,value)
    print("set_ip_property " + prop + " " + value,file=ft)

def gen_design(name):  
    print("synth " + name + " $ip",file=ft)

def run_tcl_script(tcl_file):
    os.system("vivado -mode batch -source " + tcl_file + " -stack 2000")

##================================================================================##
##                                     FUZZER                                     ##
##================================================================================##                  

if os.path.exists("data/" + ip + "/properties.json") == False:
    print("Running first time IP Property Dictionary Generation")
    ft = open(launch_file_name,"w",buffering=1)
    source_fuzzer_file()
    init_design()
    print("get_prop_dict $ip",file=ft)
    ft.close()
    run_tcl_script(launch_file_name)


fj = open("data/" + ip + "/properties.json")
ip_dict = json.load(fj) 
fj.close()


def run_iterative_sweep(count):
    for x in ip_dict["PROPERTY"]:
        if x["type"] == "ENUM":
            for V in x["values"]:
                init_design()
                set_property(x["name"],V)
                gen_design(str(count))
                count += 1
        else:
            if args.ignore_integer == "0":
                for V in range(x["min"],x["max"],int(args.integer_step)):
                    init_design()
                    set_property(x["name"],str(V))
                    gen_design(str(count))
                    count += 1
    return count

def run_random(count,num):
    i = 0
    while (i < num):
        init_design()
        for x in ip_dict["PROPERTY"]:
            if x["type"] == "ENUM":
                V = random.choice(x["values"])
                set_property(x["name"],V)
            else:
                if args.ignore_integer == "0":
                    V = random.randrange(x["min"],x["max"],int(args.integer_step))
                    set_property(x["name"],str(V))
        gen_design(str(count))
        count += 1
        i += 1

def run_default():
    init_design()
    gen_design("default")





len_list = []
key_list = []
value_list = []
current_list = []
used_list = []
design_count = 0

def print_current():
    #print("PRINTING CURRENT")
    print(current_list)
    #print(list(value_list[x][current_list[x]] for x in range(len(current_list))), current_list)
    #for i in range(len(key_list)):
    #    print(key_list[i], ":", value_list[i][current_list[i]])
    #print("\n")

def incr_current(i):
    msb = i
    if i < len(key_list):
        current_list[i] = current_list[i] + 1
        for j in range(i,len(key_list)):
            if current_list[j] == len_list[j]:
                current_list[j] = 0
                if j+1 < len(current_list):
                    current_list[j+1] = current_list[j+1] + 1
                    msb = j
                else:
                    return -1
        #else:
        #    break
    else:
        print("ATTEMPTED INCR OUT OF INDEX")
    return msb

def has_new_data():
    x = random.randint(0,100)
    if x < 30:
        return 1
    else:
        return 0


def random_current():
    global used_list
    while (1):
        for i in range(len(key_list)):
            current_list[i] = random.randint(0,len_list[i]-1)
        print_current()
        if current_list not in used_list:
            used_list.append(list(current_list))
            return


def generate_current():
    global ft, design_count
    ft = open(launch_file_name,"w",buffering=1)
    source_fuzzer_file()
    init_design()
    for i in range(len(current_list)):
        set_property(key_list[i],value_list[i][current_list[i]])
    print("GENERATING DESIGN")
    design_name = str(design_count)
    gen_design(design_name)
    design_count = design_count + 1
    run_tcl_script(launch_file_name) 
    return design_name


def add_current_tcl():
    global ft, design_count
    init_design()
    for i in range(len(current_list)):
        set_property(key_list[i],value_list[i][current_list[i]])
    design_name = str(design_count)
    gen_design(design_name)
    design_count = design_count + 1
    return design_name

def add_to_library(design_name):
    templates = {}
    for x in os.listdir("library/" + ip + "/templates/"):
        templates[x] = []
        for y in os.listdir("library/" + ip + "/templates/" + x + "/"):
            templates[x] += ["library/" + ip + "/templates/" + x + "/" + y]

    fj = open("data/" + ip + "/" + design_name + ".json")
    design = json.load(fj) 
    fj.close()
    g = import_design(design)
    #print_graph("_design_" + c,g)
    has_new_data = create_templates(g,templates)
    return has_new_data

def run_all_skip():
    for x in ip_dict["PROPERTY"]:
        if x["type"] == "ENUM":
            #value_dict[x["name"]] = x["values"]
            len_list.append(len(x["values"]))
            key_list.append(x["name"])
            value_list.append(x["values"])
            for V in x["values"]:
                #init_design()
                print(x["name"],":",V)
        else:
            if args.ignore_integer == "0":
                #value_dict[x["name"]] = range(x["min"],x["max"],int(args.integer_step))
                len_list.append(len(range(x["min"],x["max"],int(args.integer_step))))
                key_list.append(x["name"])
                value_list.append(range(x["min"],x["max"],int(args.integer_step)))
                for V in range(x["min"],x["max"],int(args.integer_step)):
                    print(x["name"],":",str(V))
    for i in range(len(key_list)):
        current_list.append(0)
        print(key_list[i])
        print("\t",len_list[i])
        print("\t",value_list[i])
    incr_current(0)
    msb_incr = 0
    while(1):
        print("NEW ITERATION")
        design_name = generate_current()
        print("ADDING TO LIBRARY")
        has_new_data = add_to_library(design_name)
        print_current()
        print("HAS_NEW_DATA:",has_new_data)
        if has_new_data == 0:
            print("SKIPPED")
            for i in range(0,msb_incr):
                current_list[i] = 0
            msb_incr = incr_current(msb_incr+1)
        else:
            msb_incr = incr_current(0)
        if msb_incr == -1 or msb_incr == len(key_list):
            break


 
def run_v1():
    global ft, args
    random_run_count = int(args.random_count)

    for x in ip_dict["PROPERTY"]:
        if x["type"] == "ENUM":
            #if all(x.isnumeric() for x in x["values"]) and len(x["values"] > 5):
            # Maybe just check for "width"
            if x["name"] in ["CONFIG.input_width","CONFIG.phase_factor_width"]:
                limited_ls = ["0","8","16","32","64","128"]
                for i in limited_ls:
                    if i not in x["values"]:
                        limited_ls.remove(i)
                key_list.append(x["name"])
                value_list.append(limited_ls)
                len_list.append(len(limited_ls))
                for V in limited_ls:
                    print(x["name"],":",V)
            else:
                #value_dict[x["name"]] = x["values"]
                len_list.append(len(x["values"]))
                key_list.append(x["name"])
                value_list.append(x["values"])
                for V in x["values"]:
                    print(x["name"],":",V)
        else:
            if args.ignore_integer == "0":
                #value_dict[x["name"]] = range(x["min"],x["max"],int(args.integer_step))
                if int(args.integer_step) != 1:
                    limited_ls = [0,8,16,32,64,128]
                    count = 0
                    for i in limited_ls:
                        if x["min"] < i < x["max"]:
                            continue
                        else:
                            limited_ls.remove(i)
                    key_list.append(x["name"])
                    value_list.append(limited_ls)
                    len_list.append(len(limited_ls))
                else:
                    len_list.append(len(range(x["min"],x["max"],int(args.integer_step))))
                    key_list.append(x["name"])
                    value_list.append(range(x["min"],x["max"],int(args.integer_step)))
                for V in range(x["min"],x["max"],int(args.integer_step)):
                    print(x["name"],":",str(V))
    for i in range(len(key_list)):
        current_list.append(0)
        print(key_list[i])
        print("\t",len_list[i])
        print("\t",value_list[i])

    
    ft = open(launch_file_name,"w",buffering=1)
    
    count = 0

    random_design_list = []
    while(count < random_run_count):
        count += 1
        source_fuzzer_file()
        print("NEW ITERATION")
        design_name = add_current_tcl()
        random_design_list.append(design_name)
        #print_current()
        random_current()
    run_tcl_script(launch_file_name)
    sys.exit()

    
    for x in random_design_list:
        add_to_library(x)

    templates = {}
    always_properties = {}
    f2 = 0
    for x in os.listdir("library/" + ip + "/templates/"):
        templates[x] = []
        f1 = 0
        property_split = {}
        for y in os.listdir("library/" + ip + "/templates/" + x + "/"):
            templates[x] += ["library/" + ip + "/templates/" + x + "/" + y]
            gt = igraph.Graph.Read_Pickle("library/" + ip + "/templates/" + x + "/" + y)
            if f1 == 0:
                f1 += 1
                for P in gt["user_properties"]:
                    print(P)
                    property_split[P] = {}
                    property_split[P]["value"] = gt["user_properties"][P][0]
                    property_split[P]["type"] = "ALWAYS"
                    property_split[P]["dc_count"] = 0
                if f2 == 0:
                    f2 += 1
                    for P in gt["user_properties"]:
                        always_properties[P] = gt["user_properties"][P][0]
                    print("ALWAYS:",always_properties)
            for P in gt["user_properties"]:
                if P in property_split:
                    if property_split[P]["type"] == "ALWAYS":
                        if len(gt["user_properties"][P]) == 1:
                            if gt["user_properties"][P][0] != property_split[P]["value"]:
                                property_split[P]["type"] = "VAR"
                                property_split[P]["value"] = list(set([property_split[P]["value"]] + gt["user_properties"][P]))
                        else:
                            property_split[P]["type"] = "VAR"
                            property_split[P]["value"] = list(set([property_split[P]["value"]] + gt["user_properties"][P]))
                            property_split[P]["dc_count"] += 1
                    else:
                        if len(gt["user_properties"][P]) == 1:
                            property_split[P]["value"] = list(set(property_split[P]["value"] + gt["user_properties"][P]))
                        else:
                            property_split[P]["value"] = list(set(property_split[P]["value"] + gt["user_properties"][P]))
                            property_split[P]["dc_count"] += 1
                if P in always_properties:
                    if len(gt["user_properties"][P]) == 1:
                        if always_properties[P] != gt["user_properties"][P][0]:
                            always_properties.pop(P,None)
                    else:
                        always_properties.pop(P,None)
        print(x, "variants:",len(templates[x]))
        for P in property_split:
            print("\t",P,property_split[P])
    print("ALWAYS:",always_properties)

    for x in templates:
        print("")
        print(x)
        f1 = 0
        for y in templates[x]:
            gt = igraph.Graph.Read_Pickle(y)
            if f1 == 0:
                for K in gt["user_properties"].keys():
                    print(K + ", ", end='')
                f1 += 1
            print("")
            f2 = 0
            for P in gt["user_properties"]:
                if f2 != 0:
                    print(", ",end='')
                f2 += 1
                if len(gt["user_properties"][P]) == 1:
                    print(gt["user_properties"][P][0], end = '')
                else:
                    print("-", end = '')
 

#def fuzzer():
#    global ip_name, ft
#    script_count = 0
#    ft = open(launch_file_name,"w",buffering=1)
#    source_fuzzer_file()
#    run_default()
#
#    #num = run_iterative_sweep(1)
#    run_tcl_script(launch_file_name)


#if int(args.default_only) == 1:
#    fuzzer()
#else:
#    #run_all()
run_v1()