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

import igraph
from igraph import *
import os
import random
import json
import re
import pickle


def import_design(design):
    # print("Creating Graph")
    g = Graph(directed=True)
    cells = design["CELLS"]
    g.add_vertices(len(list(cells.keys())))
    i = 0
    # Create all cells
    for x in cells:
        g.vs[i]["id"] = i
        g.vs[i]["label"] = x.split("/")[-1]
        g.vs[i]["name"] = x
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
        if g.vs[i]["ref"] in ["IBUF", "OBUF"]:
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
    port_list = []

    for x in nets:
        parent = nets[x]["PARENT"]
        driver = nets[x]["DRIVER"]
        if driver != "FLAT_DESIGN":
            driver_pin_name = driver.rsplit("/", 1)
            driver_v = g.vs.select(name=driver_pin_name[0])
            if "VCC/P" in driver:
                driver_type = "CONST1"
            elif "GND/G" in driver:
                driver_type = "CONST0"
            else:
                driver_type = "primitive"
            print("COMPARE V: DRIVER:", driver, driver_type)
            if len(driver_v) != 0:
                driver_idx = driver_v[0].index
                driver_bool = "LEAF.0"
                driver_dir = "INPUTS"
                for leaf_bool in ["LEAF.0", "LEAF.1"]:
                    for pin_dir in ["INPUTS", "OUTPUTS"]:
                        for y in nets[x][leaf_bool][pin_dir]:
                            if y == driver:
                                driver_bool = leaf_bool
                                driver_dir = pin_dir
                for leaf_bool in ["LEAF.0", "LEAF.1"]:
                    for pin_dir in ["INPUTS", "OUTPUTS"]:
                        for pin in nets[x][leaf_bool][pin_dir]:
                            if pin != driver:
                                pin = pin.rsplit("/", 1)
                                pin_idx = g.vs.select(name=pin[0])
                                if len(pin_idx) == 1:
                                    pin_idx = pin_idx[0].index
                                    if (
                                        driver_bool == "LEAF.1"
                                        and leaf_bool == "LEAF.1"
                                    ):
                                        edge_type = driver_type
                                    else:
                                        edge_type = "port"
                                    new_edge_list.append((driver_idx, pin_idx))
                                    name_list.append(x)
                                    parent_list.append(parent)
                                    in_pin_list.append(pin[1])
                                    out_pin_list.append(driver_pin_name[1])
                                    signal_list.append(edge_type)
                                    port_list.append(dict())
                                else:
                                    print("PIN INDEX ERROR", pin)
        else:
            driver = nets[x]["LEAF.0"]["OUTPUTS"]
            if len(driver) == 1:
                driver = driver[0]
                driver_pin_name = driver.rsplit("/", 1)
                driver_v = g.vs.select(name=driver_pin_name[0])
                if len(driver_v) != 0:
                    driver_idx = driver_v[0].index
                    for pin in nets[x]["LEAF.0"]["INPUTS"]:
                        if pin != driver:
                            pin = pin.rsplit("/", 1)
                            pin_idx = g.vs.select(name=pin[0])[0].index
                            new_edge_list.append((driver_idx, pin_idx))
                            name_list.append(x)
                            parent_list.append(parent)
                            in_pin_list.append(pin[1])
                            out_pin_list.append(driver_pin_name[1])
                            port_list.append(dict())
                            signal_list.append("primitive")
    g.add_edges(new_edge_list)
    g.es["name"] = name_list
    g.es["parent"] = parent_list
    g.es["in_pin"] = in_pin_list
    g.es["out_pin"] = out_pin_list
    g.es["signal"] = signal_list
    g.es["ports"] = port_list
    return g


def compare_eqn(eq1, eq2):
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
    if eq1_fun == eq2_fun:
        for pin in pin_name_list:
            eq1_pin_dict[pin] = [m.start() for m in re.finditer(pin, eq1)]
            eq2_pin_dict[pin] = [m.start() for m in re.finditer(pin, eq2)]
        for pin in eq1_pin_dict:
            found = 0
            for pin2 in eq2_pin_dict:
                if eq1_pin_dict[pin] == eq2_pin_dict[pin2]:
                    found = 1
                    eq2_pin_dict.pop(pin2, None)
                    break
            if found == 0:
                return 0
        return 1
    else:
        return 0


def compare_ref(v1, v2):
    if v1["ref"] != v2["ref"]:
        return False
    # Add bel properties
    if v1["IS_PRIMITIVE"] == 1:
        for P in v1["BEL_PROPERTIES"]:
            if P in v2["BEL_PROPERTIES"]:
                if P == "CONFIG.EQN":
                    # print("===============")
                    # print(v1["BEL_PROPERTIES"][P])
                    # print(v2["BEL_PROPERTIES"][P])
                    if (
                        compare_eqn(v1["BEL_PROPERTIES"][P], v2["BEL_PROPERTIES"][P])
                        == 0
                    ):
                        # print("FAILED EQN",v1["BEL_PROPERTIES"][P],v2["BEL_PROPERTIES"][P])
                        return 0
                    # else:
                    # print("PASSED")
                elif v1["BEL_PROPERTIES"][P] != v2["BEL_PROPERTIES"][P]:
                    return 0
    return True


def is_constant_vertex(v1):
    if v1["ref"] in ["GND", "VCC"]:
        return True
    else:
        return False


def get_edge_dict_in(v1, v2):
    edge_dict = {}
    for e2 in v2.in_edges():
        if e2["signal"] != "port":
            key = e2["in_pin"] + "." + e2["out_pin"] + "." + e2["signal"]
            if key not in edge_dict:
                edge_dict[key] = {"e2": [e2.source], "e1": []}
            else:
                edge_dict[key]["e2"] += [e2.source]
    for e1 in v1.in_edges():
        if e1["signal"] != "port":
            key = e1["in_pin"] + "." + e1["out_pin"] + "." + e1["signal"]
            if key not in edge_dict:
                edge_dict[key] = {"e2": [], "e1": [e1.source]}
            else:
                edge_dict[key]["e1"] += [e1.source]
    return edge_dict


def get_edge_dict_out(v1, v2):
    edge_dict = {}
    for e2 in v2.out_edges():
        if e2["signal"] != "port":
            key = e2["in_pin"] + "." + e2["out_pin"] + "." + e2["signal"]
            if key not in edge_dict:
                edge_dict[key] = {"e2": [e2.target], "e1": []}
            else:
                edge_dict[key]["e2"] += [e2.target]
    for e1 in v1.out_edges():
        if e1["signal"] != "port":
            key = e1["in_pin"] + "." + e1["out_pin"] + "." + e1["signal"]
            if key not in edge_dict:
                edge_dict[key] = {"e2": [], "e1": [e1.target]}
            else:
                edge_dict[key]["e1"] += [e1.target]
    return edge_dict


def compare_vertex(mapping, g1, v1, g2, v2, depth, verbose):
    # verbose = 1
    depth = depth + 2
    if verbose:
        if v1["CELL_NAME"].split("/")[-1] != v2["name"]:
            print(
                "\n", "\t" * depth, "COMPARING VERTEX: NOT EQUAL!:", v1.index, v2.index
            )
        else:
            print("\n", "\t" * depth, "COMPARING VERTEX:", v1.index, v2.index)
        print("\t" * depth, "\t", v1["CELL_NAME"])
        print("\t" * depth, "\t", v2["name"])

    if is_constant_vertex(v1):
        if verbose:
            print("\t" * depth, "\tIS CONST SOURCE")
        if compare_ref(v1, v2):
            return mapping
        else:
            return 0

    if compare_ref(v1, v2):
        if verbose:
            print("\t" * depth, "\tCELLS ARE THE SAME")
        # FOR EVERY SOURCE IN VERTEX
        edge_dict = get_edge_dict_in(v1, v2)
        if verbose:
            print("\t" * depth, "\t\tEDGES:", edge_dict)
        for k in edge_dict:
            for e2_source in edge_dict[k]["e2"]:
                es1 = edge_dict[k]["e1"]
                if len(es1) == 0:  # NO MATCHING EDGES
                    if verbose:
                        print("\t" * depth, "\t\tNO MATCHING EDGES", es1, e2_source, k)
                    return 0
                elif len(es1) == 1:  # ONLY ONE MATCHING EDGE
                    e1_source = es1[0]
                    if e1_source not in mapping:
                        if verbose:
                            print("\t" * depth, "\t\tSOURCE NOT MAPPED")
                        if e2_source in mapping.values():
                            if verbose:
                                print("\t" * depth, "\t\tSOURCE ALREADY HAS A MATCH")
                            return 0
                        mapping[e1_source] = e2_source
                        tmp_map = compare_vertex(
                            dict(mapping),
                            g1,
                            g1.vs[e1_source],
                            g2,
                            g2.vs[e2_source],
                            depth,
                            verbose,
                        )
                        if tmp_map == 0:
                            mapping.pop(e1_source, None)
                            return 0
                        else:
                            edge_dict[k]["e1"].remove(e1_source)
                            mapping = tmp_map
                    else:
                        if verbose:
                            print("\t" * depth, "\t\tSOURCE IS MAPPED")
                        if mapping[e1_source] != e2_source:
                            if verbose:
                                print("\t" * depth, "\t\tSOURCE MAP MISMATCH")
                            return 0
                        else:
                            edge_dict[k]["e1"].remove(e1_source)
                else:  # MULTIPLE MATCHING EDGES
                    pass_flag = 0
                    possible_matches = []
                    list_maps = []
                    for e1_source in es1:
                        # if verbose: print("\t"*depth,"\t\tTESTING INPUT EDGE:",e1)
                        if e1_source not in mapping:
                            if verbose:
                                print("\t" * depth, "\t\tSOURCE NOT MAPPED")
                            if e2_source in mapping.values():
                                if verbose:
                                    print(
                                        "\t" * depth, "\t\tSOURCE ALREADY HAS A MATCH"
                                    )
                                continue
                            mapping[e1_source] = e2_source
                            tmp_map = compare_vertex(
                                dict(mapping),
                                g1,
                                g1.vs[e1_source],
                                g2,
                                g2.vs[e2_source],
                                depth,
                                verbose,
                            )
                            mapping.pop(e1_source, None)
                            if tmp_map != 0:
                                possible_matches.append(e1_source)
                                list_maps.append((e1_source, e2_source, tmp_map))
                                mapping = list_maps[0][2]
                                pass_flag = 1
                                break
                        else:
                            if verbose:
                                print("\t" * depth, "\t\tSOURCE IS MAPPED")
                            if mapping[e1_source] != e2_source:
                                if verbose:
                                    print("\t" * depth, "\t\tSOURCE MAP MISMATCH")
                            else:
                                possible_matches.append(e1_source)
                                pass_flag = 1
                                edge_dict[k]["e1"].remove(e1_source)
                                break
                    if pass_flag == 0:
                        if len(possible_matches) == 0:
                            if verbose:
                                print("\t" * depth, "\t\tNO SUCCESSFUL SOURCE MATCH")
                            return 0
                        elif len(possible_matches) == 1:
                            if verbose:
                                print("\t" * depth, "\t\tONE SUCCESSFUL SOURCE MATCH")
                            # mapping[possible_matches[0]] = e2.source
                            mapping = list_maps[0][2]
                        else:
                            if verbose:
                                print(
                                    "\t" * depth,
                                    "\t\tMULTIPLE SUCCESSFUL SOURCE MATCH",
                                    possible_matches,
                                    list_maps,
                                )
                            # IF MULTIPLE MATCH, PICK THE FIRST ONE FOR NOW, MAY NEED A "SWAP PORTS" METHOD
                            mapping = list_maps[0][2]
                    else:
                        if verbose:
                            print(
                                "\t" * depth,
                                "\t\tONE PRE-FOUND SUCCESSFUL SOURCE MATCH",
                            )
        # if verbose: print("\t"*depth,"\tMAPPING AFTER INPUTS",mapping)

        edge_dict = get_edge_dict_out(v1, v2)
        if verbose:
            print("\t" * depth, "\t\tEDGES OUT:", edge_dict)
        # OUTPUTS
        for k in edge_dict:
            if verbose:
                print("\t" * depth, "\t\tK:", k)
            for e2_target in edge_dict[k]["e2"]:
                es1 = edge_dict[k]["e1"]
                if len(es1) == 0:  # NO MATCHING EDGES
                    if verbose:
                        print("\t" * depth, "\t\tRET 1")
                    return 0
                elif len(es1) == 1:  # ONLY ONE MATCHING EDGE
                    e1_target = es1[0]
                    if e1_target not in mapping:
                        if verbose:
                            print("\t" * depth, "\t\tTARGET NOT MAPPED")
                        if e2_target in mapping.values():
                            key_val = list(mapping.keys())[
                                list(mapping.values()).index(e2_target)
                            ]
                            if verbose:
                                print("\t" * depth, "\t\tRET 2")
                            return 0
                        mapping[e1_target] = e2_target
                        tmp_map = compare_vertex(
                            dict(mapping),
                            g1,
                            g1.vs[e1_target],
                            g2,
                            g2.vs[e2_target],
                            depth,
                            verbose,
                        )
                        if tmp_map == 0:
                            mapping.pop(e1_target, None)
                            if verbose:
                                print("\t" * depth, "\t\tRET 3")
                            return 0
                        else:
                            edge_dict[k]["e1"].remove(e1_target)
                            mapping = tmp_map
                    else:
                        if verbose:
                            print("\t" * depth, "\t\tTARGET IS MAPPED")
                        if mapping[e1_target] != e2_target:
                            if verbose:
                                print("\t" * depth, "\t\tTARGET MAP MISMATCH")
                            if verbose:
                                print("\t" * depth, "\t\tRET 4")
                            return 0
                        else:
                            edge_dict[k]["e1"].remove(e1_target)
                else:  # MULTIPLE MATCHING EDGES
                    if verbose:
                        print(
                            "\t" * depth,
                            "\t\tMULTIPLE EDGE MATCH:",
                            v1.index,
                            e2_target,
                        )
                    pass_flag = 0
                    possible_matches = []
                    list_maps = []
                    for e1_target in es1:
                        if verbose:
                            print("\t" * depth, "\t\tTESTING OUTPUT EDGE:", e1_target)
                        if e1_target not in mapping:
                            if verbose:
                                print("\t" * depth, "\t\tTARGET NOT MAPPED")
                            if e2_target in mapping.values():
                                if verbose:
                                    print(
                                        "\t" * depth, "\t\tTARGET ALREADY HAS A MATCH"
                                    )
                                continue
                            mapping[e1_target] = e2_target
                            tmp_map = compare_vertex(
                                dict(mapping),
                                g1,
                                g1.vs[e1_target],
                                g2,
                                g2.vs[e2_target],
                                depth,
                                verbose,
                            )
                            # list_maps.append((e1_target,e2_target,tmp_map))
                            mapping.pop(e1_target, None)
                            if tmp_map != 0:
                                edge_dict[k]["e1"].remove(e1_target)
                                possible_matches.append(e1_target)
                                list_maps.append((e1_target, e2_target, tmp_map))
                                mapping = list_maps[0][2]
                                pass_flag = 1
                                break
                        else:
                            if verbose:
                                print("\t" * depth, "\t\tTARGET IS MAPPED")
                            if mapping[e1_target] != e2_target:
                                if verbose:
                                    print(
                                        "\t" * depth,
                                        "\t\tTARGET MAP MISMATCH",
                                        e1_target,
                                        g1.vs[e1_target]["CELL_NAME"],
                                        mapping[e1_target],
                                        e2_target,
                                    )
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
                                print("\t" * depth, "\t\tNO SUCCESSFUL TARGET MATCH")
                            return 0
                        elif len(possible_matches) == 1:
                            if verbose:
                                print("\t" * depth, "\t\tONE SUCCESSFUL TARGET MATCH")
                            # mapping[possible_matches[0]] = e2_target
                            mapping = list_maps[0][2]
                        else:
                            if verbose:
                                print(
                                    "\t" * depth,
                                    "\t\tMULTIPLE SUCCESSFUL TARGET MATCH:",
                                    possible_matches,
                                    list_maps,
                                )
                            # IF MULTIPLE MATCH, PICK THE FIRST ONE FOR NOW, MAY NEED A "SWAP PORTS" METHOD
                            mapping = list_maps[0][2]
                            # mapping[possible_matches[0]] = e2_target
                            # mapping = compare_vertex(dict(mapping),g1,g1.vs[possible_matches[0]],g2,g2.vs[e2_target],depth)
                    else:
                        if verbose:
                            print(
                                "\t" * depth,
                                "\t\tONE PRE-FOUND SUCCESSFUL TARGET MATCH",
                            )
        # if verbose: print("\t"*depth,"\tMAPPING AFTER OUTPUTS",mapping)
    else:
        if verbose:
            print(
                "\t" * depth,
                "\tRETURNING:CANDIDATES ARE NOT THE SAME",
                v1["ref"],
                v2["ref"],
            )
        return 0
    return mapping


def load_pkl_obj(file_name):
    pkl_obj = {}
    if os.path.exists(file_name):
        with open(file_name, "rb") as handle:
            pkl_obj = pickle.load(handle)
    return pkl_obj


def save_pkl_obj(file_name, pkl_obj):
    with open(file_name, "wb") as handle:
        pickle.dump(pkl_obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def visualize_graph(name, graph_obj):
    name = name.replace("/", ".")
    print("printing", name)
    print("Printing Graph")
    fj = open("library/" + ip + "/graphs/graph" + name + ".txt", "w")
    # print(summary(graph_obj),file=fj)
    print_graph(graph_obj, fj)
    fj.close()
    return

    visual_style = {}
    out_name = "library/" + ip + "/graphs/graph_" + name + ".png"
    visual_style["bbox"] = (1000, 1000)
    visual_style["margin"] = 5
    visual_style["vertex_size"] = 75
    visual_style["vertex_label_size"] = 15
    visual_style["edge_curved"] = False
    visual_style["hovermode"] = "closest"
    my_layout = graph_obj.layout_sugiyama()
    visual_style["layout"] = my_layout
    plot(graph_obj, out_name, **visual_style)


def print_graph(graph_obj, f):
    print("Printing Graph as text")
    print("GRAPH TOP:", file=f)
    for p in graph_obj.attributes():
        print("\t", p, ":", graph_obj[p], file=f)

    for v in graph_obj.vs:
        print(v.index, file=f)
        for p in v.attributes():
            print("\t", p, ":", v[p], file=f)

    for e in graph_obj.es():
        print(e.index, file=f)
        for p in e.attributes():
            print("\t", p, ":", e[p], file=f)
        print("\t", e.source, "->", e.target, file=f)


def random_color():
    color = "#" + "".join([random.choice("0123456789ABCDEF") for j in range(6)])
    return color
