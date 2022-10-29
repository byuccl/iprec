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

"""
Helper functions importing/exporting iGraphs and comparing vertices

Note:
This file uses the following syntax:

for i in list1:
    for j in list2:
        if x:
            break
    else:
        do something

Familiarize yourself with the syntax here: https://stackoverflow.com/a/1859099
"""

from igraph import Graph
from itertools import zip_longest
import re


######### TCL Generated JSON to iGraph #########
def import_design(design, flat):
    """
    Main function for importing JSON generated by record_core.tcl into
    an iGraph object.
    """
    g = Graph(directed=True)
    cells = design["CELLS"]
    g.add_vertices(len(list(cells.keys())))

    # Import all cells
    for vertex, (i, (c_name, c_info)) in zip(g.vs, enumerate(cells.items())):
        vertex["id"] = i
        vertex["label"] = c_name.split("/")[-1]
        vertex["name"] = c_name
        vertex["parent"] = c_info["PARENT"]
        vertex["IS_PRIMITIVE"] = True if c_info["IS_PRIMITIVE"] else False

        if c_info["IS_PRIMITIVE"] == 1:
            vertex["color"] = "orange"
            vertex["ref"] = c_info["REF_NAME"]
            vertex["BEL_PROPERTIES"] = c_info["BEL_PROPERTIES"]
        else:
            vertex["color"] = "green"
            orig_ref = c_info["ORIG_REF_NAME"]
            vertex["ref"] = orig_ref if orig_ref else c_info["REF_NAME"]
            vertex["CELL_PROPERTIES"] = c_info["CELL_PROPERTIES"]

        if "CELL_NAME" in c_info:
            vertex["CELL_NAME"] = c_info["CELL_NAME"]

        if vertex["ref"] in ["IBUF", "OBUF"]:
            vertex["color"] = "blue"

    if flat:
        return create_edges_flat(g, design["NETS"])

    return create_edges_hier(g, design["NETS"])


def create_edges_flat(g, nets):
    """
    Creates edges from a flat design JSON recorded by record_core.tcl
    """
    vertex_edges = []
    edge_attr = {
        "name": [],
        "parent": [],
        "in_pin": [],
        "out_pint": [],
        "signal": [],
        "ports": []
    }

    for net, net_info in nets.items():
        parent = net_info["PARENT"]
        driver = net_info["LEAF.0"]["OUTPUTS"]
        if len(driver) != 1:
            continue
        driver = driver[0]
        driver_pin_name = driver.rsplit("/", 1)
        driver_v = g.vs.select(name=driver_pin_name[0])
        if not len(driver_v):
            continue
        driver_idx = driver_v[0].index
        for pin in net_info["LEAF.0"]["INPUTS"]:
            if pin == driver: 
                continue  
            pin = pin.rsplit("/", 1)
            pin_idx = g.vs.select(name=pin[0])[0].index
            vertex_edges.append((driver_idx, pin_idx))
            edge_attr["name"].append(net)
            edge_attr["parent"].append(parent)
            edge_attr["in_pin"].append(pin[1])
            edge_attr["out_pin"].append(driver_pin_name[1])
            edge_attr["signal"].append("primitive")

    edge_attr["ports"] = [dict() for i in vertex_edges]
    g.add_edges(vertex_edges, edge_attr)
    return g


def create_edges_hier(g, nets):
    """
    Creates edges from a hierarchal design JSON recorded by record_core.tcl
    """
    vertex_edges = []
    edge_attr = {
        "name": [],
        "parent": [],
        "in_pin": [],
        "out_pint": [],
        "signal": []
    }

    for net, net_info in nets.items():
        parent = net_info["PARENT"]
        driver = net_info["DRIVER"]

        if "VCC/P" in driver:
            driver_type = "CONST1"
        elif "GND/G" in driver:
            driver_type = "CONST0"
        else:
            driver_type = "primitive"

        driver_pin_name = driver.rsplit("/", 1)
        driver_v = g.vs.select(name=driver_pin_name[0])
        if not len(driver_v):
            continue

        driver_bool = "LEAF.0"  # default leaf bool
        for pin_dir in ["INPUTS", "OUTPUTS"]:
            for y in net_info["LEAF.1"][pin_dir]:
                if y == driver:
                    driver_bool = "LEAF.1"

        driver_idx = driver_v[0].index
        for leaf_bool in ["LEAF.0", "LEAF.1"]:
            for pin_dir, pins in net_info[leaf_bool].items():
                for pin in pins:
                    if pin == driver:
                        continue
                    pin = pin.rsplit("/", 1)
                    pin_idx = g.vs.select(name=pin[0])[0].index
                    if driver_bool == "LEAF.1" and leaf_bool == "LEAF.1":
                        edge_type = driver_type
                    else:
                        edge_type = "port"
                    vertex_edges.append((driver_idx, pin_idx))
                    edge_attr["name"].append(net)
                    edge_attr["parent"].append(parent)
                    edge_attr["in_pin"].append(pin[1])
                    edge_attr["out_pin"].append(driver_pin_name[1])
                    edge_attr["signal"].append(edge_type)
    
    edge_attr["ports"] = [dict() for i in vertex_edges]
    g.add_edges(vertex_edges, edge_attr)
    return vertex_edges, edge_attr


######### iGraph to Text File #########
def print_graph(graph_obj, f):
    """Print iGraph in readable-text format to a file"""
    print("GRAPH TOP:", file=f)
    for p in graph_obj.attributes():
        print(f"\t{p}: {graph_obj[p]}", file=f)

    for v in graph_obj.vs:
        print(v.index, file=f)
        for p in v.attributes():
            print(f"\t{p}: {v[p]}", file=f)

    for e in graph_obj.es():
        print(e.index, file=f)
        for p in e.attributes():
            print(f"\t{p}: {e[p]}", file=f)
        print(f"\t{e.source} -> {e.target}", file=f)


######### iGraph Comparison Functions #########
def compare_eqn(eq1, eq2):
    """Compare two LUT strings"""
    eq1_pin_dict = {}
    eq2_pin_dict = {}
    pin_name_list = ["A6", "A5", "A4", "A3", "A2", "A1"]
    eq1 = eq1.replace("O6=", "")
    eq1 = eq1.replace("O5=", "")
    eq2 = eq2.replace("O6=", "")
    eq2 = eq2.replace("O5=", "")

    if "(A6+~A6)*(" in eq1:
        eq1 = eq1.replace("(A6+~A6)*(", "")
        eq1 = eq1[:-1]
    if "(A6+~A6)*(" in eq2:
        eq2 = eq2.replace("(A6+~A6)*(", "")
        eq2 = eq2[:-1]
    eq1_fun = eq1
    eq2_fun = eq2
    for pin in pin_name_list:
        eq1_fun = eq1_fun.replace(pin, "PIN")
        eq2_fun = eq2_fun.replace(pin, "PIN")
    if eq1_fun != eq2_fun:
        return False

    for pin in pin_name_list:
        eq1_pin_dict[pin] = [m.start() for m in re.finditer(pin, eq1)]
        eq2_pin_dict[pin] = [m.start() for m in re.finditer(pin, eq2)]
    for pin in eq1_pin_dict:
        for pin2 in eq2_pin_dict:
            if eq1_pin_dict[pin] == eq2_pin_dict[pin2]:
                eq2_pin_dict.pop(pin2, None)
                break
        else:  # Syntax explained here: https://stackoverflow.com/a/1859099
            return False
    return True
    

def compare_ref(v1, v2):
    """Compare two primitive references"""
    if v1["ref"] != v2["ref"]:
        return False
    
    if not v1["IS_PRIMITIVE"]:
        return True

    for P in v1["BEL_PROPERTIES"]:
        if P not in v2["BEL_PROPERTIES"]:  # TODO: if one vertex is missing properties is it still a match?
            continue
        
        if P == "CONFIG.EQN" and not compare_eqn(v1["BEL_PROPERTIES"][P], v2["BEL_PROPERTIES"][P]):
            return False
        if v1["BEL_PROPERTIES"][P] != v2["BEL_PROPERTIES"][P]:
            return False
    return True


def is_constant_vertex(v1):
    return v1["ref"] in ["GND", "VCC"]


def get_edge_dict_in(v1, v2):
    edge_dict = {}
    for e1, e2 in zip_longest(v1.in_edges(), v2.in_edges(), fillvalue= {"signal": "port"}):
        if e2["signal"] != "port":
            key = f'{e2["in_pin"]}.{e2["out_pin"]}.{e2["signal"]}'
            edge_dict.setdefault(key, {"e2": [], "e1": []})["e2"].append(e2.source)
        if e1["signal"] != "port":
            key = f'{e1["in_pin"]}.{e1["out_pin"]}.{e1["signal"]}'
            edge_dict.setdefault(key,{"e2": [], "e1": []})["e1"].append(e1.source)
    return edge_dict


def get_edge_dict_out(v1, v2):
    edge_dict = {}
    for e1, e2 in zip_longest(v1.out_edges, v2.out_edges(), fillvalue={"signal": "port"}):
        if e2["signal"] != "port":
            key = f'{e2["in_pin"]}.{e2["out_pin"]}.{e2["signal"]}'
            edge_dict.setdefault(key, {"e2": [], "e1": []})["e2"].append(e2.target)
        if e1["signal"] != "port":
            key = f'{e1["in_pin"]}.{e1["out_pin"]}.{e1["signal"]}'
            edge_dict.setdefault(key, {"e2": [], "e1": []})["e1"].append(e1.target)
    return edge_dict


def compare_vertex(mapping, g1, v1, g2, v2):
    """Recurisvely compare vertices in two graphs"""
    if is_constant_vertex(v1):
        if compare_ref(v1, v2):
            return mapping
        return False

    if not compare_ref(v1, v2):
        return False
        
    # FOR EVERY SOURCE IN VERTEX
    edge_dict = get_edge_dict_in(v1, v2)
    for k, sources in edge_dict.items():
        for e2_src in sources["e2"]:
            es1 = sources["e1"]
            if len(es1) == 0:  # NO MATCHING EDGES
                return False
            elif len(es1) == 1:  # ONLY ONE MATCHING EDGE
                e1_src = es1[0]
                if e1_src not in mapping:
                    if e2_src in mapping.values():
                        return False
                    mapping[e1_src] = e2_src
                    tmp_map = compare_vertex(
                        dict(mapping), g1, g1.vs[e1_src], g2, g2.vs[e2_src])
                    if not tmp_map:
                        mapping.pop(e1_src, None)
                        return False
                    else:
                        es1.remove(e1_src)
                        mapping = tmp_map
                else:
                    if mapping[e1_src] != e2_src:
                        return False
                    else:
                        es1.remove(e1_src)  # TODO: investigate logic here
            else:  # MULTIPLE MATCHING EDGES
                possible_matches = []
                list_maps = []
                for e1_src in es1:
                    if e1_src not in mapping:
                        if e2_src in mapping.values():
                            continue
                        mapping[e1_src] = e2_src
                        tmp_map = compare_vertex(
                            dict(mapping), g1, g1.vs[e1_src], g2, g2.vs[e2_src])
                        mapping.pop(e1_src, None)
                        if tmp_map != 0:
                            possible_matches.append(e1_src)
                            list_maps.append(
                                (e1_src, e2_src, tmp_map))
                            mapping = list_maps[0][2]
                            break
                    else:
                        if mapping[e1_src] != e2_src:
                            pass  # used to be just a print statement here
                        else:
                            possible_matches.append(e1_src)
                            es1.remove(e1_src)
                            break
                else:
                    if not len(possible_matches):
                        return False
                    elif len(possible_matches) == 1:
                        mapping = list_maps[0][2]
                    else:
                        # IF MULTIPLE MATCH, PICK THE FIRST ONE FOR NOW, MAY NEED A "SWAP PORTS" METHOD
                        mapping = list_maps[0][2]

    edge_dict = get_edge_dict_out(v1, v2)
    # OUTPUTS
    for k in edge_dict:
        for e2_target in edge_dict[k]["e2"]:
            es1 = edge_dict[k]["e1"]
            if len(es1) == 0:  # NO MATCHING EDGES
                return False
            elif len(es1) == 1:  # ONLY ONE MATCHING EDGE
                e1_target = es1[0]
                if e1_target not in mapping:
                    if e2_target in mapping.values():
                        return False
                    mapping[e1_target] = e2_target
                    tmp_map = compare_vertex(
                        dict(mapping), g1, g1.vs[e1_target], g2, g2.vs[e2_target])
                    if tmp_map == 0:
                        mapping.pop(e1_target, None)
                        return False
                    else:
                        edge_dict[k]["e1"].remove(e1_target)
                        mapping = tmp_map
                else:
                    if mapping[e1_target] != e2_target:
                        return False
                    else:
                        edge_dict[k]["e1"].remove(e1_target)
            else:  # MULTIPLE MATCHING EDGES
                possible_matches = []
                list_maps = []
                for e1_target in es1:
                    if e1_target not in mapping:
                        if e2_target in mapping.values():
                            continue
                        mapping[e1_target] = e2_target
                        tmp_map = compare_vertex(
                            dict(mapping), g1, g1.vs[e1_target], g2, g2.vs[e2_target])
                        # list_maps.append((e1_target,e2_target,tmp_map))
                        mapping.pop(e1_target, None)
                        if tmp_map != 0:
                            edge_dict[k]["e1"].remove(e1_target)
                            possible_matches.append(e1_target)
                            list_maps.append(
                                (e1_target, e2_target, tmp_map))
                            mapping = list_maps[0][2]
                            break
                    else:
                        if mapping[e1_target] != e2_target:
                            pass  # used to be just a print statement here
                        else:
                            edge_dict[k]["e1"].remove(e1_target)
                            possible_matches.append(e1_target)
                            break

                else:
                    if len(possible_matches) == 0:
                        return False
                    elif len(possible_matches) == 1:
                        mapping = list_maps[0][2]
                    else:
                        # IF MULTIPLE MATCH, PICK THE FIRST ONE FOR NOW, MAY NEED A "SWAP PORTS" METHOD
                        mapping = list_maps[0][2]
                
    return mapping


######### Old Functions #########
def compare_vertex_verbose(mapping, g1, v1, g2, v2, depth, verbose):
    verbose = True
    depth = depth+2
    if verbose:
        if v1["CELL_NAME"].split("/")[-1] != v2["name"]:
            print("\n", "\t"*depth, "COMPARING VERTEX: NOT EQUAL!:",
                  v1.index, v2.index)
        else:
            print("\n", "\t"*depth, "COMPARING VERTEX:", v1.index, v2.index)
        print("\t"*depth, "\t", v1["CELL_NAME"])
        print("\t"*depth, "\t", v2["name"])

    if is_constant_vertex(v1):
        if verbose:
            print("\t"*depth, "\tIS CONST SOURCE")
        if compare_ref(v1, v2):
            return mapping
        else:
            return False

    if compare_ref(v1, v2):
        if verbose:
            print("\t"*depth, "\tCELLS ARE THE SAME")
        # FOR EVERY SOURCE IN VERTEX
        edge_dict = get_edge_dict_in(v1, v2)
        if verbose:
            print("\t"*depth, "\t\tEDGES:", edge_dict)
        for k in edge_dict:
            for e2_src in edge_dict[k]["e2"]:
                es1 = edge_dict[k]["e1"]
                if len(es1) == 0:  # NO MATCHING EDGES
                    if verbose:
                        print("\t"*depth, "\t\tNO MATCHING EDGES",
                              es1, e2_src, k)
                    return False
                elif len(es1) == 1:  # ONLY ONE MATCHING EDGE
                    e1_src = es1[0]
                    if e1_src not in mapping:
                        if verbose:
                            print("\t"*depth, "\t\tSOURCE NOT MAPPED")
                        if e2_src in mapping.values():
                            if verbose:
                                print("\t"*depth, "\t\tSOURCE ALREADY HAS A MATCH")
                            return False
                        mapping[e1_src] = e2_src
                        tmp_map = compare_vertex_verbose(
                            dict(mapping), g1, g1.vs[e1_src], g2, g2.vs[e2_src], depth, verbose)
                        if tmp_map == 0:
                            mapping.pop(e1_src, None)
                            return False
                        else:
                            edge_dict[k]["e1"].remove(e1_src)
                            mapping = tmp_map
                    else:
                        if verbose:
                            print("\t"*depth, "\t\tSOURCE IS MAPPED")
                        if mapping[e1_src] != e2_src:
                            if verbose:
                                print("\t"*depth, "\t\tSOURCE MAP MISMATCH")
                            return False
                        else:
                            edge_dict[k]["e1"].remove(e1_src)
                else:  # MULTIPLE MATCHING EDGES
                    pass_flag = 0
                    possible_matches = []
                    list_maps = []
                    for e1_src in es1:
                        #if verbose: print("\t"*depth,"\t\tTESTING INPUT EDGE:",e1)
                        if e1_src not in mapping:
                            if verbose:
                                print("\t"*depth, "\t\tSOURCE NOT MAPPED")
                            if e2_src in mapping.values():
                                if verbose:
                                    print("\t"*depth,
                                          "\t\tSOURCE ALREADY HAS A MATCH")
                                continue
                            mapping[e1_src] = e2_src
                            tmp_map = compare_vertex_verbose(
                                dict(mapping), g1, g1.vs[e1_src], g2, g2.vs[e2_src], depth, verbose)
                            mapping.pop(e1_src, None)
                            if tmp_map != 0:
                                possible_matches.append(e1_src)
                                list_maps.append(
                                    (e1_src, e2_src, tmp_map))
                                mapping = list_maps[0][2]
                                pass_flag = 1
                                break
                        else:
                            if verbose:
                                print("\t"*depth, "\t\tSOURCE IS MAPPED")
                            if mapping[e1_src] != e2_src:
                                if verbose:
                                    print("\t"*depth, "\t\tSOURCE MAP MISMATCH")
                            else:
                                possible_matches.append(e1_src)
                                pass_flag = 1
                                edge_dict[k]["e1"].remove(e1_src)
                                break
                    if pass_flag == 0:
                        if len(possible_matches) == 0:
                            if verbose:
                                print("\t"*depth, "\t\tNO SUCCESSFUL SOURCE MATCH")
                            return False
                        elif len(possible_matches) == 1:
                            if verbose:
                                print("\t"*depth,
                                      "\t\tONE SUCCESSFUL SOURCE MATCH")
                            #mapping[possible_matches[0]] = e2.source
                            mapping = list_maps[0][2]
                        else:
                            if verbose:
                                print(
                                    "\t"*depth, "\t\tMULTIPLE SUCCESSFUL SOURCE MATCH", possible_matches, list_maps)
                            # IF MULTIPLE MATCH, PICK THE FIRST ONE FOR NOW, MAY NEED A "SWAP PORTS" METHOD
                            mapping = list_maps[0][2]
                    else:
                        if verbose:
                            print("\t"*depth,
                                  "\t\tONE PRE-FOUND SUCCESSFUL SOURCE MATCH")
        #if verbose: print("\t"*depth,"\tMAPPING AFTER INPUTS",mapping)

        edge_dict = get_edge_dict_out(v1, v2)
        if verbose:
            print("\t"*depth, "\t\tEDGES OUT:", edge_dict)
        # OUTPUTS
        for k in edge_dict:
            if verbose:
                print("\t"*depth, "\t\tK:", k)
            for e2_target in edge_dict[k]["e2"]:
                es1 = edge_dict[k]["e1"]
                if len(es1) == 0:  # NO MATCHING EDGES
                    if verbose:
                        print("\t"*depth, "\t\tRET 1")
                    return False
                elif len(es1) == 1:  # ONLY ONE MATCHING EDGE
                    e1_target = es1[0]
                    if e1_target not in mapping:
                        if verbose:
                            print("\t"*depth, "\t\tTARGET NOT MAPPED")
                        if e2_target in mapping.values():
                            key_val = list(mapping.keys())[list(
                                mapping.values()).index(e2_target)]
                            if verbose:
                                print("\t"*depth, "\t\tRET 2")
                            return False
                        mapping[e1_target] = e2_target
                        tmp_map = compare_vertex_verbose(
                            dict(mapping), g1, g1.vs[e1_target], g2, g2.vs[e2_target], depth, verbose)
                        if tmp_map == 0:
                            mapping.pop(e1_target, None)
                            if verbose:
                                print("\t"*depth, "\t\tRET 3")
                            return False
                        else:
                            edge_dict[k]["e1"].remove(e1_target)
                            mapping = tmp_map
                    else:
                        if verbose:
                            print("\t"*depth, "\t\tTARGET IS MAPPED")
                        if mapping[e1_target] != e2_target:
                            if verbose:
                                print("\t"*depth, "\t\tTARGET MAP MISMATCH")
                            if verbose:
                                print("\t"*depth, "\t\tRET 4")
                            return False
                        else:
                            edge_dict[k]["e1"].remove(e1_target)
                else:  # MULTIPLE MATCHING EDGES
                    if verbose:
                        print("\t"*depth, "\t\tMULTIPLE EDGE MATCH:",
                              v1.index, e2_target)
                    pass_flag = 0
                    possible_matches = []
                    list_maps = []
                    for e1_target in es1:
                        if verbose:
                            print("\t"*depth, "\t\tTESTING OUTPUT EDGE:", e1_target)
                        if e1_target not in mapping:
                            if verbose:
                                print("\t"*depth, "\t\tTARGET NOT MAPPED")
                            if e2_target in mapping.values():
                                if verbose:
                                    print("\t"*depth,
                                          "\t\tTARGET ALREADY HAS A MATCH")
                                continue
                            mapping[e1_target] = e2_target
                            tmp_map = compare_vertex_verbose(
                                dict(mapping), g1, g1.vs[e1_target], g2, g2.vs[e2_target], depth, verbose)
                            # list_maps.append((e1_target,e2_target,tmp_map))
                            mapping.pop(e1_target, None)
                            if tmp_map != 0:
                                edge_dict[k]["e1"].remove(e1_target)
                                possible_matches.append(e1_target)
                                list_maps.append(
                                    (e1_target, e2_target, tmp_map))
                                mapping = list_maps[0][2]
                                pass_flag = 1
                                break
                        else:
                            if verbose:
                                print("\t"*depth, "\t\tTARGET IS MAPPED")
                            if mapping[e1_target] != e2_target:
                                if verbose:
                                    print("\t"*depth, "\t\tTARGET MAP MISMATCH", e1_target,
                                          g1.vs[e1_target]["CELL_NAME"], mapping[e1_target], e2_target)
                                # if v1.index == 37:
                                #    print("E2 EDGES:")
                                #    for x in g2.vs[v2.index].out_edges():
                                #        print("\t37EDGE:",g2.vs[x.target]["name"],x.target,x)
                            else:
                                edge_dict[k]["e1"].remove(e1_target)
                                possible_matches.append(e1_target)
                                pass_flag = 1
                                break

                    if pass_flag == 0:
                        if len(possible_matches) == 0:
                            if verbose:
                                print("\t"*depth, "\t\tNO SUCCESSFUL TARGET MATCH")
                            return False
                        elif len(possible_matches) == 1:
                            if verbose:
                                print("\t"*depth,
                                      "\t\tONE SUCCESSFUL TARGET MATCH")
                            #mapping[possible_matches[0]] = e2_target
                            mapping = list_maps[0][2]
                        else:
                            if verbose:
                                print(
                                    "\t"*depth, "\t\tMULTIPLE SUCCESSFUL TARGET MATCH:", possible_matches, list_maps)
                            # IF MULTIPLE MATCH, PICK THE FIRST ONE FOR NOW, MAY NEED A "SWAP PORTS" METHOD
                            mapping = list_maps[0][2]
                            #mapping[possible_matches[0]] = e2_target
                            #mapping = compare_vertex(dict(mapping),g1,g1.vs[possible_matches[0]],g2,g2.vs[e2_target],depth)
                    else:
                        if verbose:
                            print("\t"*depth,
                                  "\t\tONE PRE-FOUND SUCCESSFUL TARGET MATCH")
        #if verbose: print("\t"*depth,"\tMAPPING AFTER OUTPUTS",mapping)
    else:
        if verbose:
            print("\t"*depth, "\tRETURNING:CANDIDATES ARE NOT THE SAME",
                  v1["ref"], v2["ref"])
        return False
    return mapping


# def visualize_graph(name, graph_obj):
#     name = name.replace("/", ".")
#     print("printing", name)
#     print("Printing Graph")
#     fj = open("library/" + ip + "/graphs/graph" + name + ".txt", "w")
#     print_graph(graph_obj, fj)
#     fj.close()
#     return

#     visual_style = {}
#     out_name = "library/" + ip + "/graphs/graph_" + name + ".png"
#     visual_style["bbox"] = (1000, 1000)
#     visual_style["margin"] = 5
#     visual_style["vertex_size"] = 75
#     visual_style["vertex_label_size"] = 15
#     visual_style["edge_curved"] = False
#     visual_style["hovermode"] = "closest"
#     my_layout = graph_obj.layout_sugiyama()
#     visual_style["layout"] = my_layout
#     plot(graph_obj, out_name, **visual_style)

