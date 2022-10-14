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

import argparse
from igraph import Graph
import json
from multiprocessing import Pool
from pathlib import Path
import shutil
from subprocess import Popen, STDOUT, PIPE
import sys

from numpy import record

from compare_v import compare_eqn
from config import DATA_DIR, ROOT_PATH, VIVADO


class LibraryGenerator:
    """
    Creates the Library of Hierarchical Cell definitions for the 
    randomized IP specimen designs.
    """

    def __init__(self, ip):
        if ip.endswith(".dcp"):
            self.ip = Path(ip).name[:-4]
            self.data_dir = ROOT_PATH / "data" / self.ip
            self.data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(ip, self.data_dir)
        else:
            self.ip = ip
            self.data_dir = ROOT_PATH / "data" / self.ip
            self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.lib_dir = ROOT_PATH / "library" / self.ip
        self.templ_dir =  self.lib_dir / "templates"
        self.graphs_dir = self.lib_dir / "graphs"
        self.templ_dir.mkdir(parents=True, exist_ok=True)
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        self.export_designs()
        self.create_submodules()
        self.init_templates()

    
    def import_design(self, design):
        '''Imports the json file into an iGraph'''
        g = Graph(directed=True)
        cells = design["CELLS"]
        g.add_vertices(len(list(cells.keys())))
        # Create all cells
        for i, (cell, contents) in enumerate(cells.items()):
            g_vertex = g.vs[i]
            g_vertex["id"] = i
            g_vertex["label"] = cell.split("/")[-1]
            g_vertex["name"] = cell
            if contents["IS_PRIMITIVE"] == 1:
                g_vertex["IS_PRIMITIVE"] = 1
                g_vertex["color"] = "orange"
                g_vertex["ref"] = contents["REF_NAME"]
                g_vertex["BEL_PROPERTIES"] = contents["BEL_PROPERTIES"]
            else:
                g_vertex["IS_PRIMITIVE"] = 0
                g_vertex["color"] = "green"

                # Sometimes ORIG_REF_NAME is empty if REF_NAME = original name
                tmp = contents["ORIG_REF_NAME"]
                g_vertex["ref"] = tmp if tmp else contents["REF_NAME"]

                g_vertex["CELL_PROPERTIES"] = contents["CELL_PROPERTIES"]
            if "CELL_NAME" in contents:
                g_vertex["CELL_NAME"] = contents["CELL_NAME"]
            g_vertex["parent"] = contents["PARENT"]
            if g_vertex["ref"] in ["IBUF", "OBUF"]:
                g_vertex["color"] = "blue"

        # Create all edges
        nets = design["NETS"]
        edge_data = {
            "conns": [],
            "names": [],
            "parent": [],
            "in_pin": [],
            "out_pin": [],
            "signal": [],
        }
        for x in nets:
            parent = nets[x]["PARENT"]
            driver = nets[x]["DRIVER"]
            driver_pin_name = driver.rsplit("/", 1)
            try:
                driver_idx = g.vs.find(name=driver_pin_name[0]).index
                if "VCC/P" in driver:
                    driver_type = "CONST1"
                elif "GND/G" in driver:
                    driver_type = "CONST0"
                else:
                    driver_type = "primitive"
                driver_bool = "LEAF.0"
                for leaf_bool in ["LEAF.0", "LEAF.1"]:
                    for pin_dir in ["INPUTS", "OUTPUTS"]:
                        for y in nets[x][leaf_bool][pin_dir]:
                            if y == driver:
                                driver_bool = leaf_bool
                for leaf_bool in ["LEAF.0", "LEAF.1"]:
                    for pin_dir in ["INPUTS", "OUTPUTS"]:
                        for pin in nets[x][leaf_bool][pin_dir]:
                            if pin != driver:
                                pin = pin.rsplit("/", 1)
                                pin_idx = g.vs.find(name=pin[0]).index
                                if driver_bool == "LEAF.1" and leaf_bool == "LEAF.1":
                                    edge_type = driver_type
                                else:
                                    edge_type = "port"
                                edge_data["conns"].append((driver_idx, pin_idx))
                                edge_data["names"].append(x.split("/")[-1])
                                edge_data["parent"].append(parent)
                                edge_data["in_pin"].append(pin[1])
                                edge_data["out_pin"].append(driver_pin_name[1])
                                edge_data["signal"].append(edge_type)
            except: #TODO: figure this out
                continue
        g.add_edges(edge_data["conns"])
        g.es["name"] = edge_data["names"]
        g.es["parent"] = edge_data["parent"]
        g.es["in_pin"] = edge_data["in_pin"]
        g.es["out_pin"] = edge_data["out_pin"]
        g.es["signal"] = edge_data["signal"]
        return g

    
    def get_module_subgraph(self, graph_obj, parent):
        """
        Returns an iGraph of just the signal hierarchical cell (all 
        cells that have the same parent).
        """
        p = graph_obj.vs.select(name=parent)
        g = Graph(directed=True)
        if len(p) == 0:
            return None
        g.add_vertices(1, p[0].attributes())
        v_dict = {p[0].index: 0}
        v_list = [p[0].index]
        g.vs[0]["name"] = g.vs[0]["name"].split("/")[-1]
        i = 1

        for v in graph_obj.vs.select(parent=parent):
            v_list.append(v.index)
            v_dict[v.index] = i
            g.add_vertices(1, v.attributes())
            g.vs[i]["name"] = g.vs[i]["name"].split("/")[-1]
            g.vs[i]["parent"] = g.vs[i]["parent"].split("/")[-1]
            i += 1

        for i, e in enumerate(graph_obj.es.select(parent=parent)):
            if e.source not in v_dict:
                print("MISSING:", e.source, e.target, graph_obj.vs[e.source]["name"])
            elif e.target not in v_dict:
                print("MISSING:", e.source, e.target, graph_obj.vs[e.target]["name"])
            else:
                g.add_edges([(v_dict[e.source], v_dict[e.target])], e.attributes())
                g.es[i]["parent"] = g.es[i]["parent"].split("/")[-1]
            
        for v in g.vs:
            v["id"] = v.index

        return g

    
    def get_user_properties(self, g):
        '''Gets the User Properties of the Hierarchical Cell'''
        user_properties = {}
        for v in g.vs.select(IS_PRIMITIVE=0):
            for P in v["CELL_PROPERTIES"]:
                prop_str = P.upper()
                user_properties[prop_str] = [v["CELL_PROPERTIES"][P]]
        return user_properties

    
    def compare_templates(self, g1, template_file):
        '''Compares two hierarchical cells'''
        g2 = Graph.Read_Pickle(str(template_file))
        
        if len(g1.vs) != len(g2.vs):
            return False

        for v1_name in g1.vs.select(id_ne=0)["name"]:
            v2 = g2.vs.select(name=v1_name)
            if not len(v2):
                return False
            
            v2 = v2[0]
            v1 = g1.vs.find(name=v1_name)
            if v1["ref"] != v2["ref"]:
                return False
            if v1["IS_PRIMITIVE"] == 1:
                for P in v1["BEL_PROPERTIES"]:
                    if P in v2["BEL_PROPERTIES"]:
                        if ((P == "CONFIG.EQN") and not 
                                (compare_eqn(v1["BEL_PROPERTIES"][P], v2["BEL_PROPERTIES"][P]))):
                            return False
                        elif P == "CONFIG.LATCH_OR_FF":
                            continue
                        elif v1["BEL_PROPERTIES"][P] != v2["BEL_PROPERTIES"][P]:
                            return False
            
        
        es1_intra = g1.es
        es2_intra = g2.es
        if len(es1_intra) != len(es2_intra):
            return False
        for e1 in es1_intra:
            e2 = g2.es.select(
                _target=e1.target,
                _source=e1.source,
                in_pin=e1["in_pin"],
                out_pin=e1["out_pin"],
            )
            if len(e2) != 1:
                return False
        
        self.update_user_properties(g2, g1["user_properties"])
        g2.write_pickle(fname=str(template_file))
        self.print_graph(
            template_file.parent.name, template_file.name.replace(".pkl", ""), g2
        )
        return True

    
    def get_spanning_trees(self, g, primitive_only):
        """
        Gets the spanning tree of the hierarchical cell (with or without
        non-primitive instances)
        """
        g.delete_vertices(0)
        g.delete_vertices(g.vs.select(ref_in=["VCC", "GND"]))
        if primitive_only:
            g.delete_vertices(g.vs.select(IS_PRIMITIVE=0))
        visited_list = []
        spanning_lists = []
        for v in g.vs:
            if v.index not in visited_list:
                visited_list.append(v.index)
                reach = g.subcomponent(v, mode="all")
                reach_id = []
                for vr in reach:
                    reach_id.append(g.vs[vr]["id"])
                    visited_list.append(vr)

                spanning_lists.append(reach_id)

        spanning_lists.sort(key=len, reverse=True)
        return spanning_lists

    
    def create_hier_cell(self, ref_name, g, user_properties):
        '''Creates the final hierarchical cell definition'''
        version_count = sum(1 for x in (self.templ_dir / ref_name).iterdir())
        g["primitive_span"] = self.get_spanning_trees(g.copy(), True)
        g["span"] = self.get_spanning_trees(g.copy(), False)
        g["primitive_count"] = len(g.vs.select(color="orange"))
        g["user_properties"] = user_properties
        self.print_graph(ref_name, version_count, g)
        file_name = self.templ_dir / ref_name / f"{version_count}.pkl"
        g.write_pickle(fname=str(file_name))
        return file_name

    
    def update_user_properties(self, g, user_properties):
        '''updates properties for all cells within the hierarchical cell'''
        for P in g["user_properties"]:
            if P in user_properties:
                if user_properties[P][0] not in g["user_properties"][P]:
                    g["user_properties"][P] += [user_properties[P][0]]

    
    def create_templates(self, g, templates):
        '''Main function for creating all hierarchical cells from a design'''
        has_new_data = 0
        for v in g.vs.select(IS_PRIMITIVE=0):
            g_sub = self.get_module_subgraph(g, v["name"])
            user_properties = self.get_user_properties(g)
            g_sub["user_properties"] = user_properties
            if v["ref"] not in templates:
                (self.templ_dir / v["ref"]).mkdir(exist_ok=True)
                (self.graphs_dir / v["ref"]).mkdir(exist_ok=True)
                templates[v["ref"]] = [
                    self.create_hier_cell(v["ref"], g_sub, user_properties)
                ]
            else:
                match = 0
                for x in templates[v["ref"]]:
                    if self.compare_templates(g_sub, x):
                        print("MATCHED:", v["ref"], x.name)
                        match = 1
                        break
                if match == 0:
                    has_new_data = 1
                    templates[v["ref"]].append(
                        self.create_hier_cell(v["ref"], g_sub, user_properties)
                    )
        return has_new_data

    
    def create_submodules(self):
        """
        Creates all hierarchical cell definitions from all designs 
        in the randomized specimen data.
        """
        cell_graphs = [
            x.name
            for x in self.data_dir.iterdir()
            if ".json" in x.name and "properties" not in x.name
        ]
        templates = {}
        for x in self.templ_dir.iterdir():
            print("X:", x.name)
            templates[x.name] = []
            if x.is_dir():
                for y in x.iterdir():
                    templates[x.name].append(y)
        for c in sorted(cell_graphs):
            print(self.data_dir / c)
            fj = open(self.data_dir / c, "r")
            
            design = json.load(fj)
            fj.close()
            g = self.import_design(design)
            self.create_templates(g, templates)

    
    def init_templates(self):
        """
        Parses library folder and creates dictionary of all templates.
        """
        templates = {}
        used_list = {}
        for cell in self.templ_dir.iterdir():
            if cell.is_dir():
                templates[cell.name] = {}
                for y in cell.iterdir():
                    x = cell.name
                    y = y.name
                    templates[x][y] = {}
                    templates[x][y]["file"] = str(self.templ_dir / x / y)
                    g_template = Graph.Read_Pickle(templates[x][y]["file"])
                    for t in g_template.vs.select(IS_PRIMITIVE=0, id_ne=0):
                        if t["ref"] not in used_list:
                            used_list[t["ref"]] = [x]
                        else:
                            used_list[t["ref"]] += [x]
                    span_dict = []
                    for span in g_template["primitive_span"]:
                        tmp_dict = {}
                        tmp_dict["indices"] = span
                        tmp_dict["size"] = len(span)
                        tmp_dict["matches"] = []
                        span_dict.append(tmp_dict)
                    templates[x][y]["span"] = span_dict
                    templates[x][y]["primitive_count"] = g_template["primitive_count"]
        for x in used_list:
            used_list[x] = list(set(used_list[x]))
        output = self.lib_dir / "templates.json"
        fj = open(output, "w")
        tmp = {"templates": templates, "used": used_list}
        template_json = json.dumps(tmp, indent=2, sort_keys=True)
        print(template_json, file=fj)
        fj.close()

    
    def print_graph(self, cell, version, graph_obj):
        f = open(self.graphs_dir / cell / f"{version}.txt", "w")
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
        f.close()


    def record_core(self, design_f):
        """Runs the export design from a .dcp of"""
        tcl_arg = str(self.data_dir / design_f).replace(".dcp", "")
        cmd = [VIVADO, "-notrace", "-mode", "batch", "-source", "record_core.tcl",
               "-tclarg", tcl_arg, "0", "-stack", "2000", "-nolog", "-nojournal"]
        proc = Popen(cmd, cwd=self.data_dir, stdout=PIPE, stderr=STDOUT, 
                     universal_newlines=True)
        for line in proc.stdout:
            sys.stdout.write(line)
        proc.communicate()
        assert proc.returncode == 0


    def export_designs(self):
        """Exports all specimen designs into jsons in parallel"""
        fileList = [x for x in self.data_dir.iterdir() if x.name.endswith(".dcp")]
        if len(fileList) == 1:
            self.record_core(fileList[0])
        else:
            with Pool(processes=8) as pool:
                pool.map(self.record_core, fileList)


def main():
    parser = argparse.ArgumentParser()
    # Selects the target tile type
    parser.add_argument(
        "--ip",
        default="xilinx.com:ip:c_accum:12.0",
        help="Name of Xilinx IP or single dcp",
    )
    args = parser.parse_args()
    LibraryGenerator(args.ip)


if __name__ == "__main__":
    main()
