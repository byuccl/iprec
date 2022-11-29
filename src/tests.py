"""
Unit testing for IPRec functions.

Tests for either/or functionality and against the results of the
functions in commit 586bf1bc1dd94739c3c9f663d7da89253b8ee930.
"""

from igraph import Graph
import json
from subprocess import Popen, STDOUT, PIPE
import unittest

from config import ROOT_PATH, TEST_RESOURCES, RECORD_CORE_TCL
from compare_v import import_design
from compare_v_refactor import import_design as import_design_refactor
from compare_v_refactor import print_graph

IPREC_OUTPUT = TEST_RESOURCES / "aes128" / "iprec_output"


class TestCompareV(unittest.TestCase):
    """
    Functions for testing compare_v.py
    """

    vertex_attr = {"label", "name", "IS_PRIMITIVE", "color", "ref", "parent"}
    edge_attr = {"parent", "in_pin", "out_pin", "signal"}

    def test_import_design_refactor(self):
        self.test_import_design(test_function=import_design_refactor, flat=True)  # type:ignore
        data = {}
        with open(IPREC_OUTPUT / "aes128.json", "r") as f:
            data = json.load(f)
        actual_graph = None
        with open(IPREC_OUTPUT / "aes128.pkl", "rb") as f:
            actual_graph = Graph.Read_Pickle(f)
        self.test_import_design(
            test_function=import_design_refactor,  # type:ignore
            data=data,
            actual_graph=actual_graph,
            flat=False,
        )

    def test_import_design(self, test_function=import_design, data={}, actual_graph=None, **kwargs):
        """
        Test import design against design imported from previous commit.
        """
        if actual_graph is None:
            with open(IPREC_OUTPUT / "aes128_flat.pkl", "rb") as f:
                actual_graph = Graph.Read_Pickle(f)
        self.assertTrue(actual_graph)

        if not data:
            with open(IPREC_OUTPUT / "aes128_flat.json", "r") as f:
                data = json.load(f)
        self.assertTrue(data)
        test_graph = test_function(data, **kwargs)

        self.assertEqual(test_graph.is_directed(), actual_graph.is_directed())

        with open(TEST_RESOURCES / "test_graph.pkl", "wb") as f:
            test_graph.write_pickle(f)

        for test_vertex in test_graph.vs():
            actual_vertex = actual_graph.vs(name=test_vertex["name"])
            self.assertEqual(
                len(actual_vertex), 1, msg=f"Vertex {test_vertex} does not exist in actual"
            )

            actual_vertex = actual_vertex[0]
            test_attr = {k: v for k, v in test_vertex.attributes().items() if "PROPERTIES" not in k}
            actual_attr = {
                k: v for k, v in actual_vertex.attributes().items() if "PROPERTIES" not in k
            }
            results = dict(test_attr.items() & actual_attr.items())
            self.assertTrue(
                self.vertex_attr < results.keys(),
                msg=f"Attributes for vertex {test_vertex} do not match. Baseline: {actual_vertex}",
            )

            if actual_vertex["IS_PRIMITIVE"]:
                test_props = test_vertex.attributes()["BEL_PROPERTIES"]
                actual_props = actual_vertex.attributes()["BEL_PROPERTIES"]
            else:
                test_props = test_vertex.attributes()["CELL_PROPERTIES"]
                actual_props = actual_vertex.attributes()["CELL_PROPERTIES"]
            self.assertEqual(
                test_props.items(),
                actual_props.items(),
                msg=f"BEL/CELL properties mismatch for {test_vertex}. Baseline: {actual_props}",
            )

            self.assertEqual(
                len(test_vertex.all_edges()),
                len(actual_vertex.all_edges()),
                msg=f"Len Edges mismatch for vertex {test_vertex}",
            )
            actual_edges = actual_vertex.all_edges()
            for test_edge in test_vertex.all_edges():
                actual_edge = None
                for actual_edge in actual_edges:
                    if (
                        actual_edge.source_vertex["name"] == (test_edge.source_vertex["name"])
                        and actual_edge.target_vertex["name"] == test_edge.target_vertex["name"]
                    ):
                        test_attr = {
                            k: v for k, v in test_edge.attributes().items() if k != "ports"
                        }
                        actual_attr = {
                            k: v for k, v in actual_edge.attributes().items() if k != "ports"
                        }
                        results = dict(test_attr.items() & actual_attr.items())
                        if not self.edge_attr < results.keys():
                            continue
                        if not actual_edge["ports"].items() == test_edge["ports"].items():
                            continue
                        break
                else:
                    self.assertTrue(False, msg=f"No match for edge {test_edge} in baseline")
                if actual_edge is not None:
                    actual_edges.remove(actual_edge)

    def test_compare_eqn(self):
        pass

    def test_compare_ref(self):
        pass

    def test_is_constant_vertex(self):
        pass

    def test_get_edge_dict(self):
        pass

    def test_compare_vertex(self):
        pass

    def test_print_graph(self):
        g = None
        with open(IPREC_OUTPUT / "aes128.pkl", "rb") as f:
            g = Graph.Read_Pickle(f)
        self.assertTrue(g)

        with open(TEST_RESOURCES / "aes128_graph.txt", "w") as f:
            print_graph(g, f)

        with open(TEST_RESOURCES / "aes128_graph.txt", "r") as f:
            with open(IPREC_OUTPUT / "aes128_graph.txt", "r") as f_actual:
                for i, (test_line, actual_line) in enumerate(zip(f, f_actual)):
                    test_line = test_line.strip()
                    actual_line = actual_line.strip()
                    self.assertTrue(test_line == actual_line, msg=f"Line {i + 1} mismatch")
                self.assertTrue(
                    f.readline() == f_actual.readline(), msg=f"Files are of different lengths"
                )
        pass


if __name__ == "__main__":
    unittest.main()
