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

"""
This script takes in a design (.dcp file) and an IP core name and 
searches for the IP core within the design
"""

import argparse
from igraph import Graph
import json
from multiprocessing import Pool
from pathlib import Path
import pickle
from subprocess import Popen, STDOUT, PIPE
import sys

from compare_v import compare_vertex, import_design
from config import VIVADO, CHECKPT_DIR


GREEDY = True


class IP_Search:
    """
    Class of methods used to search for an IP in a flat netlist design.

    The input design does not have to be a flat netlist; the import scripts will
    flatten the netlist for you.
    """

    def __init__(self, IP, design, checkpoint, force_gen):
        """
        Setup and run IP search.

        IP (str) search ip from library.
        design (Path) a vivado dcp or json netlist.
        checkpoint (int) the point to resume search.
        force_gen (bool) force regeneration of pickle file
        """
        self.templates = {}
        self.mapped_list = []
        self.used_list = {}
        self.descend_failed_dict = {}

        if design.suffix == ".dcp":
            self.import_dcp(design)
            file_root = f"{str(design)[:-4]}"
            json_f = Path(f"{file_root}.json")
            pickle_f = Path(f"{file_root}.pkl")
        else:
            json_f = design
            pickle_f = Path(f"{str(design)[:-5]}.pkl")

        if not pickle_f.exists():
            with open(json_f) as f:
                design_data = json.load(f)
            
            g = import_design(design_data)
            g = self.label_const_sources(g)
            g.write_pickle(fname=str(pickle_f))
        else:
            g = Graph.Read_Pickle(str(pickle_f))

        # Either search, or start from a known checkpoint
        if not checkpoint:
            self.checkpt = 0
            g_template, template_mapping = self.search(g)
        else:
            self.checkpt = checkpoint + 1
            g_template, template_mapping = self.start_from_checkpoint(g, checkpoint)

        if len(template_mapping) != 0:
            self.save_checkpoint(g, g_template, template_mapping)
            self.print_json_map(g, g_template, template_mapping)
            self.print_all_cells(g, g_template, template_mapping)
        else:
            print("NO FOUND TEMPLATES")

    
    def save_checkpoint(self, g, g_template, mapping):
        CHECKPT_DIR.mkdir(exist_ok=True)
        while True:
            file_name = CHECKPT_DIR / f"checkpoint_{self.checkpt}.mapping.pkl"
            with open(file_name, "wb") as handle:
                pickle.dump(mapping, handle, protocol=pickle.HIGHEST_PROTOCOL)
            g_template.write_pickle(
                fname=str(CHECKPT_DIR / f"checkpoint_{self.checkpt}.graph")
            )
            yield
            self.checkpt += 1


    def open_checkpoint(self, checkpt):
        mapping = {}
        file_name = CHECKPT_DIR / f"checkpoint_{checkpt}.mapping.pkl"
        with open(file_name, "rb") as handle:
            mapping = pickle.load(handle)
        g = Graph.Read_Pickle(str(CHECKPT_DIR / f"checkpoint_{checkpt}.graph"))
        return g, mapping

    # Checks if the incoming hier template matches port definitions
    def replace_pre_check(self, g, v1_id, g_hier):
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
    def replace_hier_cell(self, g, g_hier, v1_id, direction):
        # print("REPLACING:",len(g.vs),len(g_hier.vs),v1_id,direction)
        original_length = len(g.vs)
        if direction == "ascend":
            v2_top_id = 0
        else:
            v2_top_id = original_length
        if direction == "descend":
            if self.replace_pre_check(g, v1_id, g_hier):
                return g, 0, []
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
            g.add_vertices(1, v.attributes())
            g.vs[i]["id"] = i
            if direction == "descend":
                g.vs[i]["name"] = descend_top_name + "/" + g.vs[i]["name"]
                # print("NEW NAME:",g.vs[i]["name"],descend_top_name)
            new_vertices.append(i)
            i += 1

        v2_top = g.vs[v2_top_id]
        v1 = g.vs[v1_id]
        for e in g_hier.es:
            if e.source not in v_dict:
                print("MISSING:", e.source, e.target, g_hier.vs[e.source]["name"])
            elif e.target not in v_dict:
                print("MISSING:", e.source, e.target, g_hier.vs[e.target]["name"])
            else:
                g.add_edges([(v_dict[e.source], v_dict[e.target])], e.attributes())
        v1_port_edges = v1.out_edges() + v1.in_edges()
        for e2 in v2_top.out_edges():
            es1_out = v1.in_edges()
            es1 = list(x for x in es1_out if x["in_pin"] == e2["out_pin"])
            if len(es1) == 0:
                return g, 0, []
            for e1 in es1:
                e_new = g.add_edge(e1.source, e2.target)
                if (
                    g.vs[e1.source]["color"] == "green"
                    or g.vs[e2.target]["color"] == "green"
                ):
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
                # if e2["out_pin"] != "G":
                return g, 0, []
            for e1 in es1:
                e_new = g.add_edge(e2.source, e1.target)
                if (
                    g.vs[e2.source]["color"] == "green"
                    or g.vs[e1.target]["color"] == "green"
                ):
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
        remove_es = (
            v2_top.in_edges()
            + v2_top.out_edges()
            + v1_top.in_edges()
            + v1_top.out_edges()
        )
        g.delete_edges(remove_es)
        if direction == "ascend":
            contracted_order = list(range(0, len(g.vs)))
            contracted_order[0] = original_length
            contracted_order[original_length] = 0
            g.contract_vertices(contracted_order, "first")
            g.vs[0]["id"] = 0
            top_name = g.vs[0]["name"]
            g.vs[original_length]["id"] = original_length
            for i in range(1, len(g.vs)):
                g.vs[i]["name"] = top_name + "/" + g.vs[i]["name"]

        return g, 1, new_vertices

    # Gets all hier cells connected to the limit_vertices list
    def get_spanning_hier_cells(self, g_template, mapping, limit_vertices):
        mapped_id = []
        if limit_vertices == None:
            mapped_id = mapping.values()
        else:
            mapped_id = limit_vertices

        max_v = len(g_template.vs)
        mapped_id = list(x for x in mapped_id if x < max_v)
        neighbor_vs = g_template.neighborhood(
            vertices=mapped_id, order=1, mode="all", mindist=1
        )
        neighborhood = [item for sublist in neighbor_vs for item in sublist]
        neighborhood = list(set(neighborhood))
        hier_vs_id = []
        for x in neighborhood:
            if g_template.vs["color"][x] == "green":
                hier_vs_id.append(x)
        if 0 in hier_vs_id:
            hier_vs_id.remove(0)
        return hier_vs_id

    def update_map(self, g, g_template, mapping, new_vertices, verbose):
        original_map = dict(mapping)
        self.mapped_list = list(mapping.values())
        mapped_keys = list(mapping.keys())

        # It would be faster to get unmapped_neighbor by just passing in the new vertices and getting those neighbors
        # also only run the descending function on green neighbors of the new vertices?
        # also if it fails replacing, the don't try it again next iteration...
        unmapped_neighbor = set()
        for x in new_vertices:
            for y in g_template.neighbors(x, mode="all"):
                if y in self.mapped_list:
                    unmapped_neighbor.add(y)
        unmapped_neighbor = list(unmapped_neighbor)
        edge_limit = 200
        # This prevents cells who are connected to tons of things from being run frequently
        # Example: FF whose output is connected to hundreds of other FF's CE pin.
        for x in unmapped_neighbor:
            key = mapped_keys[self.mapped_list.index(x)]
            if len(g_template.vs[x].out_edges()) < edge_limit:
                tmp_mapping = compare_vertex(
                    mapping, g, g.vs[key], g_template, g_template.vs[x], 0, verbose
                )
                if tmp_mapping == 0:
                    return 0
                else:
                    mapping = tmp_mapping

        return mapping

    def print_map_cells(self, mapping, g, g_template):
        # return
        err_count = 0
        for x in sorted(mapping):
            # print(x,return_mapping[x])
            a = g.vs[x]["CELL_NAME"].split("/")[-1]
            b = g_template.vs[mapping[x]]["name"]
            if a != b:
                print("\t\t\t", x, mapping[x], a, " -> ", b, "####### NOT EQUAL")
                err_count += 1
            else:
                print("\t\t\t", x, mapping[x], a, " -> ", b)

    def descend_parallel(self, ver):
        g_hier = Graph.Read_Pickle(self.templates[self.ref][ver]["file"])
        g_new = self.g_temp.copy()
        g_new, pass_flag, new_vertices = self.replace_hier_cell(
            g_new, g_hier, self.v_par_id, "descend"
        )
        tmp_graph = g_new.copy()
        if pass_flag == 1:
            mapping = self.update_map(
                self.g_par, g_new, dict(self.return_mapping), new_vertices, 0
            )
            if mapping != 0:
                if self.ret_graph == 1:
                    return tmp_graph.copy(), dict(mapping), new_vertices
                elif self.ret_graph == 2:
                    return len(mapping)
                else:
                    return 1
        return 0

    def descend(self, g, g_template, pass_mapping, limit_vertices):
        pass_graph = ""
        return_mapping = pass_mapping
        descend_pass_flag = 1
        best_length = 0
        best_average = 0
        best_decision = None
        while 1:
            decision_list = []
            v_hier_id_list = self.get_spanning_hier_cells(
                g_template, pass_mapping, limit_vertices
            )
            updated_flag = 0
            for v_hier_id in v_hier_id_list:

                if v_hier_id not in self.descend_failed_dict:
                    self.descend_failed_dict[v_hier_id] = []
                self.ref = g_template.vs.find(id=v_hier_id)["ref"]
                pass_num = 0
                possible_matches = []
                average = 0
                new_vertex_list = []
                self.g_temp = g_template
                self.g_par = g
                v_par_id = v_hier_id
                self.ret_graph = 2
                versions = list(
                    x
                    for x in self.templates[self.ref].keys()
                    if x not in self.descend_failed_dict[v_par_id]
                )
                pool = Pool(processes=8)
                results = pool.map(self.descend_parallel, versions)
                for idx, x in enumerate(results):
                    if x:
                        pass_num += 1
                        possible_matches.append(versions[idx])
                        average += self.templates[self.ref][versions[idx]][
                            "primitive_count"
                        ]
                    else:
                        self.descend_failed_dict[v_par_id].append(versions[idx])
                average = average / pass_num if pass_num != 0 else 0
                # print("AVERAGE:",average,pass_num,best_average)
                if average >= best_average:
                    best_average = average
                    decision_list = [v_par_id, self.ref, possible_matches]
                if pass_num == 1:
                    self.ret_graph = 1
                    g_template, return_mapping, new_vertex_list = self.descend_parallel(
                        possible_matches[0]
                    )
                    if limit_vertices != None:
                        limit_vertices += new_vertex_list
                    else:
                        limit_vertices = new_vertex_list
                    updated_flag = 1
                elif pass_num > 1:
                    for idx, x in enumerate(results):
                        if x > best_length:
                            best_decision = [v_par_id, self.ref, versions[idx]]
                            best_length = x
                else:
                    descend_pass_flag = 0
            if updated_flag == 0:
                break

        return (
            g_template,
            return_mapping,
            best_decision,
            descend_pass_flag,
            decision_list,
        )

    def ascend(self, g, g_template, pass_mapping):
        pass_graph = ""
        return_mapping = pass_mapping

        decision_list = {}
        root_node = g_template.vs[0]
        pass_num = 0
        updated_flag = 0
        if root_node["ref"] in self.used_list:
            for self.ref in self.used_list[root_node["ref"]]:
                possible_matches = []
                for ver in self.templates[self.ref]:
                    g_hier = Graph.Read_Pickle(self.templates[self.ref][ver]["file"])

                    g_new = g_template.copy()
                    v_hier_top_s = g_hier.vs.select(ref=root_node["ref"])
                    for v_hier_top in v_hier_top_s:
                        g_new, pass_flag, new_vertices = self.replace_hier_cell(
                            g_new, g_hier, v_hier_top["id"], "ascend"
                        )
                        tmp_graph = g_new.copy()
                        if pass_flag == 1:
                            mapping = self.update_map(
                                g, g_new, dict(return_mapping), new_vertices, 0
                            )
                            if mapping != 0:
                                pass_num += 1
                                possible_matches.append((ver, v_hier_top.index))
                                if pass_num == 1:
                                    pass_graph = tmp_graph.copy()
                                    pass_mapping = dict(mapping)
                if len(possible_matches) > 0:
                    decision_list[self.ref] = possible_matches
        if pass_num == 1:
            g_template = pass_graph.copy()
            return_mapping = dict(pass_mapping)
            updated_flag = 1
        return g_template, return_mapping, decision_list

    def recurse_descend(self, descend_decision_dec, g, g_template, mapping, depth):
        # print("\tRECURSE DESCEND")
        self.ret_graph = 1
        self.ref = descend_decision_dec[1]
        self.v_par_id = descend_decision_dec[0]
        g_descended, mapping_descended, new_vertex_list = self.descend_parallel(
            descend_decision_dec[2]
        )
        return g_descended, mapping_descended, 1

    def recurse_ascend(self, ascend_decision_list, g, g_template, mapping, depth):
        if len(ascend_decision_list) == 0:
            return g_template, mapping, 0

        g_ascended, mapping_ascended = None, []
        for x in ascend_decision_list:
            for decision in ascend_decision_list[x]:
                ref = x
                ver, v_id = decision
                g_hier = Graph.Read_Pickle(self.templates[ref][ver]["file"])
                g_new = g_template.copy()
                g_new, pass_flag, new_vertices = self.replace_hier_cell(
                    g_new, g_hier, v_id, "ascend"
                )
                tmp_mapping = self.update_map(g, g_new, dict(mapping), new_vertices, 0)
                if GREEDY:
                    g_tmp, tmp_mapping = self.run_replace_greedy(
                        g, g_new, tmp_mapping, depth + 1
                    )
                else:
                    g_tmp = g_new
                if len(tmp_mapping) >= len(mapping_ascended):
                    g_ascended = g_tmp.copy()
                    mapping_ascended = dict(tmp_mapping)
        if len(mapping_ascended) > len(mapping):
            return g_ascended, mapping_ascended, 0
        else:
            return g_ascended, mapping_ascended, 1

    def run_replace_greedy(self, g, g_template, mapping, depth):
        if depth >= 2:
            return g_template, mapping

        while 1:
            # Try every decision
            descend_decision_dec, ascend_decision_dec = None, []
            while 1:
                # Descend as much as possible
                original_length = len(g_template.vs)
                (
                    g_template,
                    mapping,
                    descend_decision_dec,
                    descend_pass_flag,
                    dec_list,
                ) = self.descend(g, g_template, mapping, None)
                g_template, mapping, ascend_decision_list = self.ascend(
                    g, g_template, mapping
                )
                if len(g_template.vs) == original_length:
                    break
            # Descend/Ascend has settled - need to try decisions now
            if descend_decision_dec != None:
                g_template, mapping, recurse_pass_flag = self.recurse_descend(
                    descend_decision_dec, g, g_template, mapping, depth
                )
            else:
                g_template, mapping, recurse_pass_flag = self.recurse_ascend(
                    ascend_decision_list, g, g_template, mapping, depth
                )
            if (
                recurse_pass_flag == 0
                and descend_decision_dec == None
                and len(ascend_decision_list) == 0
            ):
                return g_template, mapping
        return None

    def run_replace(self, g, g_template, mapping, depth):
        biggest_graph = g_template
        biggest_map = mapping
        recurse_pass_flag = 0
        # print("\n#### Starting Ascend/descend Function ####\n DEPTH:",depth)
        while 1:
            descend_decision_dec, ascend_decision_dec = None, []
            dec_list = []
            while 1:
                # Descend as much as possible
                original_length = len(g_template.vs)
                (
                    g_template,
                    mapping,
                    descend_decision_dec,
                    descend_pass_flag,
                    dec_list,
                ) = self.descend(g, g_template, mapping, None)
                g_template, mapping, ascend_decision_list = self.ascend(
                    g, g_template, mapping
                )
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
                    self.ref = dec_list[1]
                    self.v_par_id = dec_list[0]
                    self.g_temp = g_template
                    self.g_par = g
                    self.ret_graph = 1
                    g_descended, mapping_descended, new_vertex_list = self.descend_parallel(
                        x
                    )
                    g_descended, mapping_descended = self.run_replace(
                        g, g_descended, mapping_descended, depth + 1
                    )  # Recurse
                    if len(mapping_descended) > len(biggest_map):
                        biggest_map = mapping_descended
                        biggest_graph = g_descended
                g_template = biggest_graph
                mapping = biggest_map
            else:
                g_template, mapping, recurse_pass_flag = self.recurse_ascend(
                    ascend_decision_list, g, g_template, mapping, depth
                )
            if (
                recurse_pass_flag == 0
                and descend_decision_dec == None
                and len(ascend_decision_list) == 0
            ):
                return biggest_graph, biggest_map
        return None

    def find_template(self, g, g_template, verbose, template, ver):
        # print("SEARCHING:",template,ver)
        template_name = g_template.vs[0]["ref"]
        biggest_map, biggest_graph = [], None
        # have span max be on a sliding scale - based off of len(templates)
        for span in self.templates[template][ver]["span"]:

            if span["size"] <= 5:
                has_complex_prim = 0
                for x in span["indices"]:
                    if g_template.vs[x]["ref"] in ["DSP48E1"]:
                        has_complex_prim = 1
                if has_complex_prim == 0:
                    continue
            v2 = g_template.vs[span["indices"][0]]
            print("\tNEW SPAN:", span["indices"], template, ver)
            for v in g.vs.select(ref=v2["ref"]):
                mapping = {}
                mapping[v.index] = v2.index
                mapping = compare_vertex(mapping, g, v, g_template, v2, 0, verbose)

                if mapping != 0 and len(mapping) > 1:
                    # print("####### STARTING NEW FIND TEMPLATE: #######")
                    if GREEDY:
                        g_tmp_template, tmp_mapping = self.run_replace_greedy(
                            g, g_template, mapping, 0
                        )
                    else:
                        g_tmp_template, tmp_mapping = self.run_replace(
                            g, g_template, mapping, 0
                        )
                    self.save_checkpoint(g, g_tmp_template, tmp_mapping)
                    if len(tmp_mapping) > len(biggest_map):
                        biggest_map = tmp_mapping
                        biggest_graph = g_tmp_template.copy()
        return biggest_graph, biggest_map

    def search(self, g):
        biggest_map, biggest_graph = [], None

        for x in self.templates:
            for y in self.templates[x]:
                g_template = Graph.Read_Pickle(self.templates[x][y]["file"])
                verbose = 0
                g_template_tmp, tmp_template_mapping = self.find_template(
                    g, g_template, verbose, x, y
                )
                if tmp_template_mapping != 0 and len(tmp_template_mapping) > len(
                    biggest_map
                ):
                    biggest_map = tmp_template_mapping
                    biggest_graph = g_template_tmp.copy()

        return biggest_graph, biggest_map

    def label_const_sources(self, g):
        for v in g.vs.select(ref="GND"):
            for e in v.out_edges():
                e["signal"] = "CONST0"
        for v in g.vs.select(ref="VCC"):
            for e in v.out_edges():
                e["signal"] = "CONST1"
        return g

    def print_graph(self, g):
        print("GRAPH TOP:")
        for p in g.attributes():
            print("\t", p, ":", g[p])

        for v in g.vs:
            print(v.index)
            for p in v.attributes():
                print("\t", p, ":", v[p])

        for e in g.es():
            print(e.index)
            for p in e.attributes():
                print("\t", p, ":", e[p])
            print("\t", e.source, "->", e.target)

    def start_from_checkpoint(self, g, i):
        g_template, mapping = self.open_checkpoint(i)
        return self.run_replace(g, g_template, mapping, 0)

    def print_all_cells(self, g, g_template, mapping):
        for x in mapping:
            print(g.vs[x]["CELL_NAME"])
        err_count = 0
        for x in mapping:
            # print(x,return_mapping[x])
            a = g.vs[x]["CELL_NAME"]
            b = g_template.vs[mapping[x]]["name"]
            if a.split("/")[-1] != b.split("/")[-1]:
                print("\t\t\t", x, mapping[x], a, " -> ", b, "####### NOT EQUAL")
                err_count += 1
            else:
                print("\t\t\t", x, mapping[x], a, " -> ", b)
        print("TOTAL ERRORS:", err_count)
        print("TOTAL CORRECT:", len(mapping))
        print("TOTAL PRIMITIVES:", len(g.vs))
        percentage = "{:.0%}".format(len(mapping) / len(g.vs))
        print("PERCENTAGE CORRECT:", percentage)

    def import_dcp(self, design):
        """
        Run tcl script that opens the vivado checkpoint of a design and writes
        a flattened netlist to json.
        """
        tcl_arg = str(design).replace(".dcp", "")
        cmd = [
            VIVADO,
            "-notrace",
            "-mode",
            "batch",
            "-source",
            "record_core.tcl",
            "-tclarg",
            tcl_arg,
            "1",
            "-stack",
            "2000",
            "-nolog",
            "-nojournal",
        ]
        proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
        for line in proc.stdout:
            sys.stdout.write(line)
        proc.communicate()
        assert proc.returncode == 0


    def print_json_map(self, g_template, mapping):
        """
        Print the matched templates in the design to json (final result).
        """
        design = {"LEAF": []}

        for x in g_template.vs:
            hier = x["name"].split("/")
            hier_ptr = design

            if x["color"] == "orange":
                for i in hier[:-1]:
                    hier_ptr = hier_ptr.setdefault(i, {"LEAF": []})
                hier_ptr["LEAF"] += [hier[-1]]
            elif x["color"] == "green":
                for i in hier:
                    hier_ptr = hier_ptr.setdefault(i, {"LEAF": []})
            else:
                print("BLACK:", hier)

        with open("design.json", "w") as f:
            json.dump(obj=design, fp=f, indent=2, sort_keys=True)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("design", help="DCP file to search for IP", type=Path)
    parser.add_argument("IP")
    parser.add_argument("--checkpoint", "-c", help="Checkpoint to continue search from",
                        default=False, type=int)
    parser.add_argument("--force", "-f", 
                        help="Force the Graph object to be recreated from the netlist",
                        default=False, action="store_true")

    args = parser.parse_args()

    IP_Search(**args.__dict__)


if __name__ == "__main__":
    main()
