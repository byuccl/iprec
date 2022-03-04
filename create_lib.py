
#!/usr/bin/env python3
import json
import os
import sys
import argparse
import random
import numpy as np
import re
import pickle
import igraph
from igraph import *
from pathlib import Path
from multiprocessing import Pool
import timeit


parser = argparse.ArgumentParser()
parser.add_argument('--ip',default="xilinx.com:ip:c_accum:12.0")    # Selects the target tile type

args = parser.parse_args()
print(args)

ip = args.ip

os.makedirs("library/",exist_ok=True)
os.makedirs("library/" + ip + "/", exist_ok=True) 
os.makedirs("data/"+ip+"/", exist_ok=True) 
os.makedirs("library/" + ip + "/templates/", exist_ok=True) 
os.makedirs("library/" + ip + "/graphs/", exist_ok=True) 


##================================================================================##
##                               JSON -> IGRAPH                                  ##
##================================================================================##   


def import_design(design):
    #print("Creating Graph")
    g = Graph(directed=True)
    cells = design["CELLS"]
    g.add_vertices(len(list(cells.keys())))
    i = 0
    # Create all cells
    for x in cells:
        g.vs[i]["id"]= i
        g.vs[i]["label"]= x.split("/")[-1]
        g.vs[i]["name"]= x
        if cells[x]["IS_PRIMITIVE"] == 1:
            g.vs[i]["IS_PRIMITIVE"] = 1
            g.vs[i]["color"] = "orange"
            g.vs[i]["ref"] = cells[x]["REF_NAME"]
            g.vs[i]["BEL_PROPERTIES"] = cells[x]["BEL_PROPERTIES"]
        else:
            g.vs[i]["IS_PRIMITIVE"] = 0
            g.vs[i]["color"] = "green"
            g.vs[i]["ref"] = cells[x]["ORIG_REF_NAME"]
            g.vs[i]["CELL_PROPERTIES"] = cells[x]["CELL_PROPERTIES"]
        if "CELL_NAME" in cells[x]:
            g.vs[i]["CELL_NAME"] = cells[x]["CELL_NAME"]
        g.vs[i]["parent"] = cells[x]["PARENT"]
        if g.vs[i]["ref"] in ["IBUF","OBUF"]:
            g.vs[i]["color"] = "blue"
        i += 1

    # Create all edges
    nets = design["NETS"]
    new_edge_list = []
    name_list = []
    parent_list = []
    in_pin_list = []
    out_pin_list = []
    signal_list = []

    for x in nets:
        parent = nets[x]["PARENT"]
        driver = nets[x]["DRIVER"]
        
        driver_pin_name = driver.rsplit("/",1)
        try:
            driver_idx = g.vs.find(name=driver_pin_name[0]).index
            if "VCC/P" in driver:
                driver_type = "CONST1"
            elif "GND/G" in driver:
                driver_type = "CONST0"
            else:
                driver_type = "primitive"
            driver_bool = "LEAF.0"
            for leaf_bool in ["LEAF.0","LEAF.1"]:
                for pin_dir in ["INPUTS","OUTPUTS"]:
                    for y in nets[x][leaf_bool][pin_dir]:
                        if y == driver:
                            driver_bool = leaf_bool
            
            for leaf_bool in ["LEAF.0","LEAF.1"]:
                for pin_dir in ["INPUTS","OUTPUTS"]:
                    for pin in nets[x][leaf_bool][pin_dir]:
                        if pin != driver:
                            pin = pin.rsplit("/",1)
                            pin_idx = g.vs.find(name=pin[0]).index
                            if driver_bool == "LEAF.1" and leaf_bool == "LEAF.1":
                                edge_type = driver_type
                            else:
                                edge_type = "port"
                            new_edge_list.append((driver_idx,pin_idx))
                            name_list.append(x.split("/")[-1])
                            parent_list.append(parent)
                            in_pin_list.append(pin[1])
                            out_pin_list.append(driver_pin_name[1])
                            signal_list.append(edge_type)
                            #g.add_edges([(driver_idx,pin_idx)],{"name":x,"parent":parent,"in_pin":pin[1],"out_pin":driver_pin_name[1],"signal":edge_type})
        except:
            continue
            #print("THERE IS AN ERROR ERROR",driver_pin_name[0])
    g.add_edges(new_edge_list)
    g.es["name"] = name_list
    g.es["parent"] = parent_list
    g.es["in_pin"] = in_pin_list
    g.es["out_pin"] = out_pin_list
    g.es["signal"] = signal_list

    return g 

def get_module_subgraph(graph_obj,parent):
    # could try to use subgraph_edges(edges), or induced_subgraph(vertices)
    p = graph_obj.vs.select(name=parent)
    g = Graph(directed=True)
    if len(p) == 0:
        return None
    g.add_vertices(1,p[0].attributes())
    v_dict = {p[0].index:0}
    v_list = [p[0].index]
    g.vs[0]["name"] = g.vs[0]["name"].split("/")[-1]
    primitive_list = []
    i=1
    #print("PARENT:",parent)
    for v in graph_obj.vs.select(parent=parent):
        #print("\t",v["name"])
        v_list.append(v.index)
        v_dict[v.index] = i
        g.add_vertices(1,v.attributes())
        g.vs[i]["name"] = g.vs[i]["name"].split("/")[-1]
        g.vs[i]["parent"] = g.vs[i]["parent"].split("/")[-1]
        i+=1
    i = 0
    for e in graph_obj.es.select(parent=parent):
        if e.source not in v_dict:
            print("MISSING:",e.source,e.target,graph_obj.vs[e.source]["name"])   
        elif e.target not in v_dict:
            print("MISSING:",e.source,e.target,graph_obj.vs[e.target]["name"]) 
        else:
            g.add_edges([(v_dict[e.source],v_dict[e.target])],e.attributes())
            g.es[i]["parent"] = g.es[i]["parent"].split("/")[-1]
        i += 1
    for v in g.vs:
        v["id"] = v.index

    return g

def compare_eqn(eq1,eq2):
    eq1_pin_dict = {}
    eq2_pin_dict = {}
    pin_name_list = ["A6","A5","A4","A3","A2","A1"]
    eq1 = eq1.replace("O6=","")
    eq1 = eq1.replace("O5=","")
    eq2 = eq2.replace("O6=","")
    eq2 = eq2.replace("O5=","")
    
    if "(A6+~A6)*(" in eq1:
        eq1 = eq1.replace("(A6+~A6)*(","")
        eq1 = eq1[:-1]
    if "(A6+~A6)*(" in eq2:
        eq2 = eq2.replace("(A6+~A6)*(","")
        eq2 = eq2[:-1]
    eq1_fun = eq1
    eq2_fun = eq2
    for pin in pin_name_list:
       eq1_fun = eq1_fun.replace(pin,"PIN")
       eq2_fun = eq2_fun.replace(pin,"PIN")
    if eq1_fun == eq2_fun:
        for pin in pin_name_list:
            eq1_pin_dict[pin] = [m.start() for m in re.finditer(pin, eq1)]
            eq2_pin_dict[pin] = [m.start() for m in re.finditer(pin, eq2)]
        for pin in eq1_pin_dict:
            found = 0
            for pin2 in eq2_pin_dict:
                if eq1_pin_dict[pin] == eq2_pin_dict[pin2]:
                    found = 1
                    eq2_pin_dict.pop(pin2,None)
                    break
            if found == 0:
                return 0
        return 1
    else:
        return 0

##================================================================================##
##                                COMPARE GRAPHS                                  ##
##================================================================================##   

 
def get_user_properties(g):
    user_properties = {}
    for v in g.vs.select(IS_PRIMITIVE=0):
        for P in v["CELL_PROPERTIES"]:
            prop_str = P.upper()
            #if prop_str in user_properties:
            #    if v["CELL_PROPERTIES"][P] != user_properties[prop_str][0]:
            #        print("ERROR: DIFF PROPERTY VALUE SUB HIERARCHY",P,v["CELL_PROPERTIES"][P],prop_str,user_properties[prop_str])
            user_properties[prop_str] = [v["CELL_PROPERTIES"][P]]
    return user_properties


#This function needs to be more a strctural check, not just a naming check - 
def compare_templates(g1,template_file_name):
    g2 = igraph.Graph.Read_Pickle(template_file_name)
    v1_top = g1.vs[0]
    v2_top = g2.vs[0]
    
    if len(g1.vs) == len(g2.vs):
        for v1_name in g1.vs.select(id_ne=0)["name"]:
            v2 = g2.vs.select(name=v1_name)
            if len(v2) >= 1:
                #r4_control appears to have 2 vertices named "control"
                v2 = v2[0]
                v1 = g1.vs.find(name=v1_name)
                if v1["ref"] != v2["ref"]:
                    #if "dpm" in template_file_name:
                    #    print("RET 1")
                    return 0
                # Is this needed? I think cells with the same name always have the same bel properties?
                if v1["IS_PRIMITIVE"] == 1:
                    for P in v1["BEL_PROPERTIES"]:
                        if P in v2["BEL_PROPERTIES"]:
                            # CONFIG.LATCH_OR_FF doesn't seem to be in every FF?
                            if P == "CONFIG.EQN":
                                if compare_eqn(v1["BEL_PROPERTIES"][P],v2["BEL_PROPERTIES"][P]) == 0:
                                    #if "dpm" in template_file_name:
                                    #    print("RET 2")
                                    return 0
                            elif P == "CONFIG.LATCH_OR_FF":
                                continue
                            elif v1["BEL_PROPERTIES"][P] != v2["BEL_PROPERTIES"][P]:
                                #if "dpm" in template_file_name:
                                #    print("RET 3")
                                return 0 
            else:
                #if "dpm" in template_file_name:
                #    print("RET 4",v1_name)
                #if "depths_3to9.ram_loop[0].use_RAMB18.SDP_RAMB18E1_36x512_REGCEB_cooolgate_en_sig" not in v1_name:
                return 0
    else: 
        #if "dpm" in template_file_name:
        #    print("RET 5")
        return 0


    # TO GO BACK: Make the es1_intra include the select, and uncomment next paragraph of comment

    es1_intra = g1.es#.select(_target_ne=v1_top.index,_source_ne=v1_top.index)
    es2_intra = g2.es#.select(_target_ne=v2_top.index,_source_ne=v2_top.index) 

    if len(es1_intra) == len(es2_intra):
        for e1 in es1_intra:
            e2 = g2.es.select(_target=e1.target,_source=e1.source,in_pin=e1["in_pin"],out_pin=e1["out_pin"])
            if len(e2) != 1:
                #if "dpm" in template_file_name:
                #    print("RET 6")
                return 0     
    else:
        return 0

    # Add any extra top level ports to template
    #new_edges = 0
    #for e1 in v1_top.out_edges():
    #    e2 = g2.es.select(_source=v2_top.index,out_pin=e1["out_pin"])
    #    if len(e2) == 0:
    #        print("NEW EDGE", e1)
    #        new_edges = 1
    #        new_edge_target = g2.vs.find(name=g1.vs[e1.target]["name"]).index
    #        g2.add_edges([(0,new_edge_target)],e1.attributes())
    #for e1 in v1_top.in_edges():
    #    e2 = g2.es.select(_target=v2_top.index,in_pin=e1["in_pin"])
    #    if len(e2) == 0:
    #        print("NEW EDGE", e1)
    #        new_edges = 1
    #        new_edge_source = g2.vs.find(name=g1.vs[e1.source]["name"]).index
    #        g2.add_edges([(new_edge_source,0)],e1.attributes()) 

    #if new_edges == 1:
    update_user_properties(g2,g1["user_properties"])
    g2.write_pickle(fname=template_file_name)
    print_graph(template_file_name.replace("library/" + ip + "/templates/","").replace(".pkl",""), g2)

    return 1
    

def is_reachable(g):
    g.delete_vertices(g.vs.select(color="green"))
    g.delete_vertices(g.vs.select(ref_in=["VCC","GND"]))
    v_list = g.vs.indices
    v = g.vs[0]
    reach = g.subcomponent(v,mode="all")
    #print("\tINDICES:",v_list)
    #print("\tSUB:",reach)
    if set(reach) == set(v_list):
        return 1
    else:
        return 0

def get_spanning_trees(g,primitive_only):
    g.delete_vertices(0)
    g.delete_vertices(g.vs.select(ref_in=["VCC","GND"]))
    if primitive_only == 1:
        g.delete_vertices(g.vs.select(IS_PRIMITIVE=0))
    visited_list = []
    spanning_lists = []
    for v in g.vs:
        if v.index not in visited_list:
            visited_list.append(v.index)
            reach = g.subcomponent(v,mode="all")
            reach_id = []
            for vr in reach:
                reach_id.append(g.vs[vr]["id"])
                visited_list.append(vr)

            spanning_lists.append(reach_id)
    
    spanning_lists.sort(key=len, reverse=True)
    return spanning_lists



def create_hier_cell(ref_name,g,user_properties):  
    
    version_count = len(os.listdir("library/" + ip + "/templates/" + ref_name + "/"))
    print("NEW HIER CELL:",ref_name + "/" + str(version_count))
    cell = {}
    #cell["cells"] = g.vs["ref"]
    g["primitive_span"] = get_spanning_trees(g.copy(),1)   
    g["span"] = get_spanning_trees(g.copy(),0)   
    g["primitive_count"] = len(g.vs.select(color="orange"))
    g["user_properties"] = user_properties
    print_graph(ref_name + "/"+str(version_count), g)
    #cell_dict[ref_name + "/" + str(version_count)] = cell
    file_name = "library/" + ip + "/templates/" + ref_name + "/" + str(version_count) + ".pkl"
    g.write_pickle(fname=file_name)
    return file_name
    

def update_user_properties(g,user_properties):
    for P in g["user_properties"]:
        if P in user_properties:
            if user_properties[P][0] not in g["user_properties"][P]:
                g["user_properties"][P] += [user_properties[P][0]]


def create_templates(g,templates):
    has_new_data = 0
    for v in g.vs.select(IS_PRIMITIVE=0):
        g_sub = get_module_subgraph(g,v["name"])
        user_properties = get_user_properties(g) # FIX THIS FOR DIFF SUB HIER PROPERTIES
        g_sub["user_properties"] = user_properties
        if v["ref"] not in templates:
            os.makedirs("library/" + ip + "/templates/"+v["ref"]+"/", exist_ok=True)
            os.makedirs("library/" + ip + "/graphs/"+v["ref"]+"/", exist_ok=True)
            # Returns the pickle file name of the template created
            templates[v["ref"]] = [create_hier_cell(v["ref"],g_sub,user_properties)]
        else:
            match = 0
            for x in templates[v["ref"]]:
                if compare_templates(g_sub,x):
                    print("MATCHED:",v["ref"],x)
                    match = 1
                    break
            if match == 0:
                has_new_data = 1
                templates[v["ref"]] += [create_hier_cell(v["ref"],g_sub,user_properties)]
    return has_new_data

##================================================================================##
##                               DIFF ANALYSIS                                    ##
##================================================================================## 


def print_graph(name,graph_obj):

    f = open("library/" + ip + "/graphs/" + name + ".txt","w")
    #print("Printing Graph as text")
    print("GRAPH TOP:",file=f)
    for p in graph_obj.attributes():
        print("\t",p,":",graph_obj[p],file=f)

    for v in graph_obj.vs:
        print(v.index,file=f)
        for p in v.attributes():
            print("\t",p,":",v[p],file=f)

    for e in graph_obj.es():
        print(e.index,file=f)
        for p in e.attributes():
            print("\t",p,":",e[p],file=f)
        print("\t",e.source,"->",e.target,file=f)
    f.close()

def create_submodules():
    cell_graphs = os.listdir("data/" + ip + "/")
    cell_graphs[:] = [x for x in cell_graphs if ".json" in x and "properties" not in x]
    templates = {}
    for x in os.listdir("library/" + ip + "/templates/"):
        print("X:",x)
        templates[x] = []
        for y in os.listdir("library/" + ip + "/templates/" + x + "/"):
            templates[x] += ["library/" + ip + "/templates/" + x + "/" + y]
    
    # Use default and 0-9.json as test set
    #use_list = list(str(x) + ".json" for x in range(400,500))
    #use_list = list(str(x) + ".json" for x in range(30))  
    #use_list = ["7.json"]
    #print("LIST:",use_list)
    #f = open("graph_data.txt","w")
    x = 0
    for c in sorted(cell_graphs):
        
        #if c in use_list:
        print(c)
        fj = open("data/" + ip + "/" + c)
        try:
            design = json.load(fj) 
            fj.close()
            g = import_design(design)
            #print_graph("_design_" + c,g)
            create_templates(g,templates)
        except:
            print("DESIGN FAILED:",c)
            continue
        y = len(templates)
        z = 0
        for a in templates:
            z += len(templates[a])
        #print(x,y,z,file=f)
        x+= 1

    #f.close()
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


 
def run_tcl_script(tcl_file):
    global ip, flat
    tf = tcl_file.replace(".dcp","")
    if flat:
        tf = "benchmarks/" + ip + "/" + tf
    else:
        tf = "data/" + ip + "/" + tf
    os.system("vivado -mode batch -source record_core.tcl -tclarg " + tf + " 0 -stack 2000")           

def export_designs():
    global flat
    flat = 0
    #if flat:
    #    fileList = os.listdir("benchmarks/" + ip + "/")
    #else:
    fileList = os.listdir("data/" + ip + "/")
    fileList[:] = [x for x in fileList if ".dcp" in x]
    pool = Pool(processes=8)
    pool.map(run_tcl_script, fileList)



# Export .dcp files into JSON - can also flatten .dcp files
export_designs()

# Create all JSON files into a library
create_submodules()

