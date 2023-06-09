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
Create graph library of hierarchal ip.
"""

import argparse
import json
import shutil
from itertools import cycle
from pathlib import Path
from subprocess import Popen, PIPE
from igraph import Graph

from compare_v_refactor import compare_eqn, import_design, print_graph
from config import RECORD_CORE_TCL, ROOT_PATH


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
        self.log_file = self.lib_dir / "vivado_log.txt"
        self.log_file.unlink(missing_ok=True)

        self.templ_dir = self.lib_dir / "templates"
        self.graphs_dir = self.lib_dir / "graphs"
        self.templ_dir.mkdir(parents=True, exist_ok=True)
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        self.export_designs()
        self.create_submodules()
        self.init_templates()

    def get_module_subgraph(self, graph_obj, parent):
        """
        Returns an iGraph of just the signal hierarchical cell (all
        cells that have the same parent).
        """
        parents = graph_obj.vs.select(name=parent)
        g = Graph(directed=True)
        if len(parents) == 0:
            return None
        g.add_vertices(1, parents[0].attributes())
        v_dict = {parents[0].index: 0}
        v_list = [parents[0].index]
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
        """Gets the User Properties of the Hierarchical Cell"""
        user_properties = {}
        for v in g.vs.select(IS_PRIMITIVE=False):
            for prop in v["CELL_PROPERTIES"]:
                prop_str = prop.upper()
                user_properties[prop_str] = [v["CELL_PROPERTIES"][prop]]
        return user_properties

    def compare_properties(self, props1, props2):
        for prop in props1:
            if prop in props2:
                if (prop == "CONFIG.EQN") and not compare_eqn(props1[prop], props2[prop]):
                    return False
                if prop == "CONFIG.LATCH_OR_FF":
                    continue
                if props1[prop] != props2[prop]:
                    return False
        return True

    def compare_templates(self, g1, template_file):
        """Compares two hierarchical cells"""
        g2 = Graph.Read_Pickle(str(template_file))

        if len(g1.vs) != len(g2.vs):
            return False

        for v1 in g1.vs.select(id_ne=0):
            v2 = g2.vs.select(name=v1["name"])
            if not v2 or v1["ref"] != v2[0]["ref"]:
                return False

            if v1["IS_PRIMITIVE"] and not self.compare_properties(
                v1["BEL_PROPERTIES"], v2[0]["BEL_PROPERTIES"]
            ):
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
        self.print_graph_version(
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
            g.delete_vertices(g.vs.select(IS_PRIMITIVE=False))
        visited_list = []
        spanning_lists = []
        for v in g.vs:
            if v.index not in visited_list:
                visited_list.append(v.index)
                reach = g.subcomponent(v, mode="all")
                reach_id = []
                for v_reach in reach:
                    reach_id.append(g.vs[v_reach]["id"])
                    visited_list.append(v_reach)

                spanning_lists.append(reach_id)

        spanning_lists.sort(key=len, reverse=True)
        return spanning_lists

    def create_hier_cell(self, ref_name, g, user_properties):
        """Creates the final hierarchical cell definition"""
        version_count = sum(1 for x in (self.templ_dir / ref_name).iterdir())
        g["primitive_span"] = self.get_spanning_trees(g.copy(), True)
        g["span"] = self.get_spanning_trees(g.copy(), False)
        g["primitive_count"] = len(g.vs.select(color="orange"))
        g["user_properties"] = user_properties
        self.print_graph_version(ref_name, version_count, g)
        file_name = self.templ_dir / ref_name / f"{version_count}.pkl"
        g.write_pickle(fname=str(file_name))
        return file_name

    def update_user_properties(self, g, user_properties):
        """updates properties for all cells within the hierarchical cell"""
        for prop in g["user_properties"]:
            if prop in user_properties:
                if user_properties[prop][0] not in g["user_properties"][prop]:
                    g["user_properties"][prop] += [user_properties[prop][0]]

    def create_templates(self, g, templates):
        """Main function for creating all hierarchical cells from a design"""
        has_new_data = 0
        for v in g.vs.select(IS_PRIMITIVE=False):
            g_sub = self.get_module_subgraph(g, v["name"])
            user_properties = self.get_user_properties(g)
            g_sub["user_properties"] = user_properties
            if v["ref"] not in templates:
                (self.templ_dir / v["ref"]).mkdir(exist_ok=True)
                (self.graphs_dir / v["ref"]).mkdir(exist_ok=True)
                templates[v["ref"]] = [self.create_hier_cell(v["ref"], g_sub, user_properties)]
            else:
                match = 0
                for x in templates[v["ref"]]:
                    if self.compare_templates(g_sub, x):
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
            templates[x.name] = []
            if x.is_dir():
                for y in x.iterdir():
                    templates[x.name].append(y)
        for cell in sorted(cell_graphs):
            with open(self.data_dir / cell, "r") as f:
                try:
                    design = json.load(f)
                except json.decoder.JSONDecodeError:
                    print(
                        f"{cell} file is improperly formatted - it is likely that record_core.tcl failed on this design"
                    )
                    continue
            try:
                g = import_design(design, flat=False)
                self.create_templates(g, templates)
            except KeyError as e:
                print(f"{cell}")
                raise e

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
                    for template in g_template.vs.select(IS_PRIMITIVE=False, id_ne=0):
                        if template["ref"] not in used_list:
                            used_list[template["ref"]] = [x]
                        else:
                            used_list[template["ref"]] += [x]
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
        with open(output, "w") as f:
            tmp = {"templates": templates, "used": used_list}
            json.dump(tmp, f, indent=2, sort_keys=True)

    def print_graph_version(self, cell, version, graph_obj):
        with open(self.graphs_dir / cell / f"{version}.txt", "w") as f:
            print_graph(graph_obj, f)

    def launch(self):
        """Runs the export design from a .dcp of"""
        cmd = [
            "vivado",
            "-notrace",
            "-mode",
            "tcl",
            "-source",
            str(RECORD_CORE_TCL),
            "-stack",
            "2000",
            "-nolog",
            "-nojournal",
        ]
        return Popen(cmd, stdin=PIPE, cwd=ROOT_PATH, universal_newlines=True)

    def export_designs(self):
        """Exports all specimen designs into jsons in parallel"""
        file_list = [x for x in self.data_dir.iterdir() if x.name.endswith(".dcp")]
        processes = [self.launch() for _ in range(8)]
        pool = cycle(processes)
        for f in file_list:
            process = next(pool)
            process.stdin.write(f"open_checkpoint {self.data_dir / f}\n")
            process.stdin.write(
                f"set json [open {str((self.data_dir / f)).replace('.dcp', '.json')} w]\n"
            )
            process.stdin.write("record_core $json\n")
            process.stdin.write("close $json\n")
            process.stdin.write("close_design\n")
        for process in processes:
            process.stdin.write("exit\n")
            process.stdin.close()
        for process in processes:
            process.wait()


def main():
    parser = argparse.ArgumentParser()
    # Selects the target tile type
    parser.add_argument(
        "ip",
        help="Name of Xilinx IP or single dcp",
    )
    args = parser.parse_args()
    LibraryGenerator(args.ip)


if __name__ == "__main__":
    main()
