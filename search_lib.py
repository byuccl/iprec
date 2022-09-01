#!/usr/bin/env python3

# Copyright 2020-2022 IPRec Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import json
import os
import argparse
import pickle
import igraph
import time
from igraph import *
from compare_v import *
from multiprocessing import Pool

# This script takes in a design (.dcp file) and an IP core name and searches for the IP core within the design

parser = argparse.ArgumentParser()
parser.add_argument('file_name', nargs=1)    
parser.add_argument('--ip',default="xilinx.com:ip:c_accum:12.0")    # Selects the target tile typ

args = parser.parse_args()
print(args)

greedy_method = 1

ip = args.ip  
file_name = args.file_name[0]
templates = {}
prim_count = 0
mapped_list = []
used_list = {}


# Checks if the incoming hier template matches port definitions
def replace_pre_check(g,v1_id,g_hier):
    v2_top = g_hier.vs[0]
    v1 = g.vs[v1_id]
    for e2 in v2_top.out_edges():
        es1_out = v1.in_edges()
        es1 = list(x for x in es1_out if x["in_pin"] == e2["out_pin"])
        if len(es1) == 0:
            return 1
    for e2 in v2_top.in_edges():
        es1_out = v1.out_edges()
        es1 = list(x for x in es1_out if x["out_pin"] == e2["in_pin"])
        if len(es1) == 0:
            return 1
    return 0

# Replaces the vertex at v1_id in g with g_hier if descend, otherwise replaces top level vertex with v_hier
def replace_hier_cell(g,g_hier,v1_id,direction):
    #print("REPLACING:",len(g.vs),len(g_hier.vs),v1_id,direction)
    original_length = len(g.vs)
    if direction == "ascend":
        v2_top_id = 0
    else:
        v2_top_id = original_length
    if direction == "descend":
        if replace_pre_check(g,v1_id,g_hier):
            return g,0, [] 
    v_dict = {}
    v_list = []
    i = len(g.vs)
    max_id = max(g.vs["id"])
    new_vertices = []
    if direction == "descend":
        descend_top_name = g.vs[v1_id]["name"]
    for v in g_hier.vs:
        # Switch the ID to be replaced with the new ID if switching replacing order (ascending)
        if direction == "ascend" and v["id"] == v1_id:
            v1_id = i
            new_vertices.append(0)
        v_list.append(v.index)
        v_dict[v.index] = i
        g.add_vertices(1,v.attributes())
        g.vs[i]["id"] = i
        if direction == "descend":
            g.vs[i]["name"] = descend_top_name + "/" + g.vs[i]["name"]
            #print("NEW NAME:",g.vs[i]["name"],descend_top_name)
        new_vertices.append(i)
        i+=1

    v2_top = g.vs[v2_top_id]
    v1 = g.vs[v1_id]
    for e in g_hier.es:
        if e.source not in v_dict:
            print("MISSING:",e.source,e.target,graph_obj.vs[e.source]["name"])   
        elif e.target not in v_dict:
            print("MISSING:",e.source,e.target,graph_obj.vs[e.target]["name"]) 
        else:
            g.add_edges([(v_dict[e.source],v_dict[e.target])],e.attributes())
    v1_port_edges = v1.out_edges() + v1.in_edges()
    for e2 in v2_top.out_edges():
        es1_out = v1.in_edges()
        es1 = list(x for x in es1_out if x["in_pin"] == e2["out_pin"])
        if len(es1) == 0:
            return g,0, []
        for e1 in es1:
            e_new = g.add_edge(e1.source,e2.target)
            if g.vs[e1.source]["color"] == "green" or g.vs[e2.target]["color"] == "green":
                e_new["signal"] = "port"
            elif g.vs[e1.source]["ref"] == "VCC":
                e_new["signal"] = "CONST1"
            elif g.vs[e1.source]["ref"] == "GND":
                e_new["signal"] = "CONST0"
            else:
                e_new["signal"] = "primitive"
            e_new["parent"] = e2["parent"]
            e_new["name"] = e2["name"]
            e_new["in_pin"] = e2["in_pin"]
            e_new["out_pin"] = e1["out_pin"]
    for e2 in v2_top.in_edges():
        es1_out = v1.out_edges()
        es1 = list(x for x in es1_out if x["out_pin"] == e2["in_pin"])
        if len(es1) == 0:
            #if e2["out_pin"] != "G":
            return g,0, []
        for e1 in es1:
            e_new = g.add_edge(e2.source,e1.target)
            if g.vs[e2.source]["color"] == "green" or g.vs[e1.target]["color"] == "green":
                e_new["signal"] = "port"
            elif g.vs[e2.source]["ref"] == "VCC":
                e_new["signal"] = "CONST1"
            elif g.vs[e2.source]["ref"] == "GND":
                e_new["signal"] = "CONST0"
            else:
                e_new["signal"] = "primitive"
            e_new["parent"] = e2["parent"]
            e_new["name"] = e2["name"]
            e_new["in_pin"] = e1["in_pin"]
            e_new["out_pin"] = e2["out_pin"]
    v2_top["color"] = "black"
    v1_top = g.vs[v1_id]
    v1_top["color"] = "black"
    remove_es = v2_top.in_edges() + v2_top.out_edges() + v1_top.in_edges() + v1_top.out_edges()
    g.delete_edges(remove_es)
    if direction == "ascend":
        contracted_order = list(range(0,len(g.vs)))
        contracted_order[0] = original_length
        contracted_order[original_length] = 0
        g.contract_vertices(contracted_order,"first")
        g.vs[0]["id"] = 0
        top_name = g.vs[0]["name"]
        g.vs[original_length]["id"] = original_length
        for i in range(1,len(g.vs)):
            g.vs[i]["name"] = top_name + "/" + g.vs[i]["name"]

    return g, 1, new_vertices

# Gets all hier cells connected to the limit_vertices list
def get_spanning_hier_cells(g_template,mapping,limit_vertices):
    mapped_id = []
    if limit_vertices == None:
        mapped_id = mapping.values()
    else:
        mapped_id = limit_vertices
    
    max_v = len(g_template.vs)
    mapped_id = list(x for x in mapped_id if x < max_v)
    neighbor_vs = g_template.neighborhood(vertices=mapped_id, order=1, mode='all', mindist=1)
    neighborhood = [item for sublist in neighbor_vs for item in sublist]
    neighborhood = list(set(neighborhood))
    hier_vs_id = []
    for x in neighborhood:
        if g_template.vs["color"][x] == "green":
            hier_vs_id.append(x)
    if 0 in hier_vs_id:
        hier_vs_id.remove(0)
    return hier_vs_id

def save_checkpoint(g,g_template,mapping):
    os.makedirs("checkpoints", exist_ok=True)
    for i in range(100):
        file_name = "checkpoints/checkpoint." + str(i) + ".mapping.pkl"
        if os.path.exists(file_name) == False:
            # print("\t\tSAVING CHECKPOINT:",i,len(mapping))
            with open(file_name, 'wb') as handle:
                pickle.dump(mapping, handle, protocol=pickle.HIGHEST_PROTOCOL)
            g_template.write_pickle(fname=file_name.replace(".mapping",".graph"))
            break

def open_checkpoint(i):
    mapping = {}
    file_name = "checkpoints/checkpoint." + str(i) + ".mapping.pkl"
    if os.path.exists(file_name):
        with open(file_name, 'rb') as handle:
            mapping = pickle.load(handle)
    g = igraph.Graph.Read_Pickle(file_name.replace(".mapping",".graph"))
    return g,mapping

def print_json_map(g,g_template,mapping):
    design = {"LEAF":[]}
    mapping_rev = {}
    for x in mapping:
        mapping_rev[mapping[x]] = x

    for x in g_template.vs:
        b = x["name"]
        hier = b.split("/")
        D = design
        
        for i in range(len(hier)-1):
            H = hier[i]
            if H not in D:
                D[H] = {"LEAF":[]}
            D = D[H]
        if x["color"] == "orange":
            D["LEAF"] += [hier[-1]]
        elif x["color"] == "green":
            D[hier[-1]] =  {"LEAF":[]}
        else:
            print("BLACK:",hier)
    fj = open("design.json",'w')
    json_design = json.dumps(design,indent=2,sort_keys=True)
    print(json_design,file=fj)
    fj.close() 

def update_map(g,g_template,mapping,new_vertices,verbose):
    original_map = dict(mapping)
    mapped_list = list(mapping.values())
    mapped_keys = list(mapping.keys())

    # It would be faster to get unmapped_neighbor by just passing in the new vertices and getting those neighbors
        # also only run the descending function on green neighbors of the new vertices?
        # also if it fails replacing, the don't try it again next iteration...
    unmapped_neighbor = set()
    for x in new_vertices:
        for y in g_template.neighbors(x,mode="all"):
            if y in mapped_list:
                unmapped_neighbor.add(y)
    unmapped_neighbor = list(unmapped_neighbor)
    edge_limit = 200
        # This prevents cells who are connected to tons of things from being run frequently
        # Example: FF whose output is connected to hundreds of other FF's CE pin.
    for x in unmapped_neighbor:
        key = mapped_keys[mapped_list.index(x)]
        if len(g_template.vs[x].out_edges()) < edge_limit:
            tmp_mapping = compare_vertex(mapping,g,g.vs[key],g_template,g_template.vs[x],0,verbose)
            if tmp_mapping == 0:
                return 0
            else:
                mapping = tmp_mapping

    return mapping

descend_failed_dict = {}


def print_map_cells(mapping,g,g_template):
    #return
    err_count = 0
    for x in sorted(mapping):
        #print(x,return_mapping[x])
        a = g.vs[x]["CELL_NAME"].split("/")[-1] 
        b = g_template.vs[mapping[x]]["name"]
        if a != b:
            print("\t\t\t",x,mapping[x],a," -> " ,b, "####### NOT EQUAL")
            err_count += 1
        else:
            print("\t\t\t",x,mapping[x],a," -> " ,b)

def descend_parallel(ver):
    global templates,ref,g_temp,v_par_id,ret_graph,g,g_par, return_mapping
    g_hier = igraph.Graph.Read_Pickle(templates[ref][ver]["file"])
    g_new = g_temp.copy()
    g_new,pass_flag, new_vertices = replace_hier_cell(g_new,g_hier,v_par_id,"descend")
    tmp_graph = g_new.copy()
    if pass_flag == 1:
        mapping = update_map(g_par,g_new,dict(return_mapping),new_vertices,0)
        if mapping != 0:
            if ret_graph == 1: 
                return tmp_graph.copy(), dict(mapping),new_vertices
            elif ret_graph == 2:
                return len(mapping)
            else:
                return 1
    return 0

def descend(g,g_template,pass_mapping,limit_vertices):
    global templates, descend_failed_dict,ref,g_temp,v_par_id,ret_graph,g_par,return_mapping
    # print("\tDESCEND")
    pass_graph = ""
    return_mapping = pass_mapping
    descend_pass_flag = 1
    best_length = 0
    best_average = 0
    best_decision = None
    while (1):
        decision_list = []
        v_hier_id_list = get_spanning_hier_cells(g_template,pass_mapping,limit_vertices)
        updated_flag = 0
        for v_hier_id in v_hier_id_list:

            if v_hier_id not in descend_failed_dict:
                descend_failed_dict[v_hier_id] = []
            ref = g_template.vs.find(id=v_hier_id)["ref"]
            pass_num = 0
            possible_matches = []
            average = 0
            new_vertex_list = []
            g_temp = g_template
            g_par = g
            v_par_id = v_hier_id
            ret_graph = 2
            versions = list(x for x in templates[ref].keys() if x not in descend_failed_dict[v_par_id])
            pool = Pool(processes=8)
            results = pool.map(descend_parallel,versions)
            for idx,x in enumerate(results):
                if x:
                    pass_num += 1
                    possible_matches.append(versions[idx])
                    average += (templates[ref][versions[idx]]["primitive_count"])
                else:
                    descend_failed_dict[v_par_id].append(versions[idx])
            average = average / pass_num if pass_num != 0 else 0
            #print("AVERAGE:",average,pass_num,best_average)
            if average >= best_average:
                best_average = average
                decision_list = [v_par_id,ref,possible_matches]
            if pass_num == 1:
                ret_graph = 1
                g_template, return_mapping, new_vertex_list = descend_parallel(possible_matches[0])
                if limit_vertices != None:
                    limit_vertices += new_vertex_list
                else:
                    limit_vertices = new_vertex_list
                updated_flag = 1
            elif pass_num > 1:
                for idx,x in enumerate(results):
                    if x > best_length:
                        best_decision = [v_par_id,ref,versions[idx]]
                        best_length = x
            else:
                descend_pass_flag = 0
        if updated_flag == 0:
            break

    return g_template, return_mapping, best_decision, descend_pass_flag, decision_list

def ascend(g,g_template,pass_mapping):
    global templates
    # print("\tASCEND")
    pass_graph = ""
    return_mapping = pass_mapping
    
    decision_list = {}
    root_node = g_template.vs[0]
    pass_num = 0
    updated_flag = 0
    if root_node["ref"] in used_list:
        for ref in used_list[root_node["ref"]]:
            possible_matches = []
            for ver in templates[ref]:
                g_hier = igraph.Graph.Read_Pickle(templates[ref][ver]["file"])

                g_new = g_template.copy()
                v_hier_top_s = g_hier.vs.select(ref=root_node["ref"])
                for v_hier_top in v_hier_top_s:
                    g_new,pass_flag, new_vertices = replace_hier_cell(g_new,g_hier,v_hier_top["id"],"ascend")
                    tmp_graph = g_new.copy()
                    if pass_flag == 1:
                        mapping = update_map(g,g_new,dict(return_mapping),new_vertices,0)
                        if mapping != 0:
                            pass_num += 1
                            possible_matches.append((ver,v_hier_top.index))
                            if pass_num == 1:
                                pass_graph = tmp_graph.copy()
                                pass_mapping = dict(mapping)
            if len(possible_matches) > 0:
                decision_list[ref] = possible_matches
    if pass_num == 1:
        g_template = pass_graph.copy()
        return_mapping = dict(pass_mapping)
        updated_flag = 1
    return g_template, return_mapping, decision_list


def recurse_descend(descend_decision_dec,g,g_template,mapping,depth):
    global templates, v_par_id,ref,ret_graph,g_par,g_temp
    # print("\tRECURSE DESCEND")
    ret_graph = 1
    ref = descend_decision_dec[1]
    v_par_id = descend_decision_dec[0]
    g_descended, mapping_descended, new_vertex_list = descend_parallel(descend_decision_dec[2])
    return g_descended,mapping_descended, 1



def recurse_ascend(ascend_decision_list,g,g_template,mapping,depth):
    global templates
    # print("\tRECURSE ASCEND")
    if len(ascend_decision_list ) == 0:
        return g_template, mapping, 0

    g_ascended, mapping_ascended = None,[]
    for x in ascend_decision_list:
        for decision in ascend_decision_list[x]:
            ref = x
            ver,v_id = decision
            g_hier = igraph.Graph.Read_Pickle(templates[ref][ver]["file"])
            g_new = g_template.copy()
            g_new,pass_flag,new_vertices = replace_hier_cell(g_new,g_hier,v_id,"ascend")
            tmp_mapping = update_map(g,g_new,dict(mapping),new_vertices,0)
            if greedy_method == 1:
                g_tmp,tmp_mapping = run_replace_greedy(g,g_new,tmp_mapping,depth+1)
            else:
                g_tmp = g_new
            if len(tmp_mapping) >= len(mapping_ascended):
                g_ascended = g_tmp.copy()
                mapping_ascended = dict(tmp_mapping)
    if len(mapping_ascended) > len(mapping):
        return g_ascended,mapping_ascended, 0
    else:
        return g_ascended,mapping_ascended, 1


def run_replace_greedy(g,g_template,mapping,depth):
    global descend_failed_dict
    if depth >= 2:
        return g_template, mapping
    
    while(1):
        # Try every decision
        descend_decision_dec,ascend_decision_dec = None, []
        while(1):
            # Descend as much as possible
            original_length = len(g_template.vs)
            g_template, mapping, descend_decision_dec, descend_pass_flag, dec_list = descend(g,g_template,mapping,None)
            g_template, mapping, ascend_decision_list = ascend(g,g_template,mapping)
            if len(g_template.vs) == original_length:
                break     
        # Descend/Ascend has settled - need to try decisions now
        if descend_decision_dec != None:
            g_template, mapping, recurse_pass_flag = recurse_descend(descend_decision_dec,g,g_template,mapping,depth)
        else:
            g_template, mapping, recurse_pass_flag = recurse_ascend(ascend_decision_list,g,g_template,mapping,depth)
        if recurse_pass_flag == 0 and descend_decision_dec == None and len(ascend_decision_list) == 0:
            return g_template, mapping
    return None


def run_replace(g,g_template,mapping,depth):
    global descend_failed_dict,templates,ref,g_temp,v_par_id,ret_graph,g_par, return_mapping
    biggest_graph = g_template
    biggest_map = mapping
    recurse_pass_flag = 0
    # print("\n#### Starting Ascend/descend Function ####\n DEPTH:",depth)
    while(1):
        descend_decision_dec,ascend_decision_dec = None, []
        dec_list = []
        while(1):
            # Descend as much as possible
            original_length = len(g_template.vs)
            g_template, mapping, descend_decision_dec, descend_pass_flag, dec_list = descend(g,g_template,mapping,None)
            g_template, mapping, ascend_decision_list = ascend(g,g_template,mapping)
            if len(g_template.vs) == original_length:
                break     
        # Ascending and Descending has settled
        if len(mapping) > len(biggest_map):
            biggest_map = mapping
            biggest_graph = g_template
        # Recursively Try all Descending decisions
        # print("DEC LIST:",dec_list)
        if len(dec_list) != 0:
            # print("DESCENDING RECURSIVE:",dec_list)
            for x in dec_list[2]:
                ref = dec_list[1]
                v_par_id = dec_list[0]
                g_temp = g_template
                g_par = g
                ret_graph = 1
                g_descended, mapping_descended, new_vertex_list = descend_parallel(x)
                g_descended, mapping_descended = run_replace(g,g_descended,mapping_descended,depth+1) # Recurse
                if len(mapping_descended) > len(biggest_map):
                    biggest_map = mapping_descended
                    biggest_graph = g_descended
            g_template = biggest_graph    
            mapping = biggest_map
        else:
            g_template, mapping, recurse_pass_flag = recurse_ascend(ascend_decision_list,g,g_template,mapping,depth)
        if recurse_pass_flag == 0 and descend_decision_dec == None and len(ascend_decision_list) == 0:
            return biggest_graph, biggest_map
    return None          


def find_template(g,g_template,verbose,template,ver):
    global prim_count, mapped_list, templates
    # print("SEARCHING:",template,ver)
    template_name = g_template.vs[0]["ref"]
    biggest_map, biggest_graph = [],None
    # have span max be on a sliding scale - based off of len(templates)
    for span in templates[template][ver]["span"]:
        
        if span["size"] <= 5:
            has_complex_prim = 0
            for x in span["indices"]:
                if g_template.vs[x]["ref"] in ["DSP48E1"]:
                    has_complex_prim = 1
            if has_complex_prim == 0:
                continue
        v2 = g_template.vs[span["indices"][0]]
        print("\tNEW SPAN:",span["indices"],template,ver)
        for v in g.vs.select(ref=v2["ref"]):
            mapping = {}
            mapping[v.index] = v2.index 
            mapping = compare_vertex(mapping,g,v,g_template,v2,0,verbose)

            if mapping != 0 and len(mapping) > 1:
                # print("####### STARTING NEW FIND TEMPLATE: #######")
                if greedy_method == 1:
                    g_tmp_template,tmp_mapping = run_replace_greedy(g,g_template,mapping,0)
                else:
                    g_tmp_template,tmp_mapping = run_replace(g,g_template,mapping,0)
                save_checkpoint(g,g_tmp_template,tmp_mapping)
                if len(tmp_mapping) > len(biggest_map):
                    biggest_map = tmp_mapping
                    biggest_graph = g_tmp_template.copy()  
    return biggest_graph,biggest_map



def search(g):
    global prim_count, templates
    count = 0
    biggest_map, biggest_graph = [],None
    while(count < 1):
        count += 1
        for x in templates:
            for y in templates[x]:
                g_template = igraph.Graph.Read_Pickle(templates[x][y]["file"])
                verbose = 0
                g_template_tmp,tmp_template_mapping = find_template(g,g_template,verbose,x,y)
                if tmp_template_mapping != 0 and len(tmp_template_mapping) > len(biggest_map):
                    biggest_map = tmp_template_mapping
                    biggest_graph = g_template_tmp.copy()        

    return biggest_graph, biggest_map

def label_const_sources(g):
    for v in g.vs.select(ref="GND"):
        for e in v.out_edges():
            e["signal"] = "CONST0"
    for v in g.vs.select(ref="VCC"):
        for e in v.out_edges():
            e["signal"] = "CONST1"   
    return g


def print_graph(g):
    print("GRAPH TOP:")
    for p in g.attributes():
        print("\t",p,":",g[p])
    
    for v in g.vs:
        print(v.index)
        for p in v.attributes():
            print("\t",p,":",v[p])
    
    for e in g.es():
        print(e.index)
        for p in e.attributes():
            print("\t",p,":",e[p])
        print("\t",e.source,"->",e.target)



def start_from_checkpoint(g,i):
    g_template, mapping = open_checkpoint(i)

    run_replace(g,g_template,mapping,0)
    print_json_map(g,g_template,mapping)
    print_all_cells(g,g_template,mapping)



def print_all_cells(g,g_template,mapping):
    for x in mapping:
        print(g.vs[x]["CELL_NAME"])
    err_count = 0
    for x in mapping:
        #print(x,return_mapping[x])
        a = g.vs[x]["CELL_NAME"]
        b = g_template.vs[mapping[x]]["name"]
        if a.split("/")[-1] != b.split("/")[-1]:
            print("\t\t\t",x,mapping[x],a," -> " ,b, "####### NOT EQUAL")
            err_count += 1
        else:
            print("\t\t\t",x,mapping[x],a," -> " ,b)
    print("TOTAL ERRORS:",err_count)
    print("TOTAL CORRECT:",len(mapping))
    print("TOTAL PRIMITIVES:",len(g.vs))
    percentage = "{:.0%}".format(len(mapping)/len(g.vs))
    print("PERCENTAGE CORRECT:",percentage)


def import_dcp(file_name):
    dcp = file_name.replace(".dcp","")
    os.system("vivado -mode batch -quiet -source record_core.tcl -tclarg " + dcp + " 1 -stack 2000")


def main():
    global file_name, templates, used_list
    if ".dcp" in file_name:
        import_dcp(file_name)
        file_name = file_name.replace(".dcp",".json")

    fj = open("library/" + ip + "/templates.json")
    tmp = json.load(fj) 
    templates = tmp["templates"]
    used_list = tmp["used"]
    fj.close()


    if os.path.exists(file_name.replace(".json",".pkl")) == False:
        fj = open(file_name)
        design = json.load(fj) 
        fj.close()
        g = import_design(design)
        g = label_const_sources(g)
        g.write_pickle(fname=file_name.replace(".json",".pkl"))
    else:
        g = igraph.Graph.Read_Pickle(file_name.replace(".json",".pkl"))

    # Either search, or start from a known checkpoint
    g_template, template_mapping = search(g)
    # start_from_checkpoint(g,99)

    if len(template_mapping)!=0:
        save_checkpoint(g,g_template,template_mapping)
        print_json_map(g,g_template,template_mapping)
        print_all_cells(g,g_template,template_mapping)
    else:
        print("NO FOUND TEMPLATES")
main()


