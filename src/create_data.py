
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
import random
from igraph import *


# This script takes in a selected IP Core then:
# 1. Launches a tcl script to get all of the possible properties of the IP
# 2. Randomly generates X number of designs with the instantiated core randomly parameterized
# 3. Writes a TCL script that creates the designs in part 2
# 4. Executes the TCL script (created in part 3) in Vivado to create the designs


class DataGenerator():
    """
    Generates designs that instantiates the single IP core with randomized properties.
    """

    def __init__(self, args):
        self.random_count = int(args.random_count)
        self.ip = args.ip
        self.part_name = args.part
        self.ignore_integer = int(args.ignore_integer)
        self.integer_step = int(args.integer_step)
        self.launch_file_name = "data/" + self.ip + "/launch.tcl"
        self.ip_dict = {}
        self.launch_file = None
        random.seed(10)

        self.makeDirs()
        self.getIPProperties()

    # Steps up the Folder Structure
    def makeDirs(self):
        os.makedirs("library/", exist_ok=True)
        os.makedirs("library/" + self.ip + "/", exist_ok=True)
        os.makedirs("data/"+self.ip+"/", exist_ok=True)

    # Executes the TCL script that creates the dictionary of parameters of the IP (in a JSON)
    def getIPProperties(self):
        if os.path.exists("data/" + self.ip + "/properties.json") == False:
            print("Running first time IP Property Dictionary Generation")
            self.launch_file = open(self.launch_file_name, "w", buffering=1)
            self.source_fuzzer_file()
            self.init_design()
            print("get_prop_dict $ip", file=self.launch_file)
            self.launch_file.close()
            self.run_tcl_script(self.launch_file_name)

        fj = open("data/" + self.ip + "/properties.json")
        self.ip_dict = json.load(fj)
        fj.close()

    # For the IP core, randomizes each parameter
    def randomProperties(self):
        for x in self.ip_dict["PROPERTY"]:
            if x["type"] == "ENUM":
                V = random.choice(x["values"])
                self.set_property(x["name"], V)
            else:
                if self.ignore_integer == 0:
                    V = random.randrange(x["min"], x["max"], self.integer_step)
                    self.set_property(x["name"], str(V))
    # Main function for fuzzing the IP

    def fuzz_IP(self):
        self.launch_file = open(self.launch_file_name, "w", buffering=1)
        for i in range(self.random_count):
            self.source_fuzzer_file()
            self.init_design()
            if i > 1:  # First design is the default one
                self.randomProperties()
            self.gen_design(str(i))
        self.launch_file.close()
        self.run_tcl_script(self.launch_file_name)

    # TCL command wrapper functions

    def source_fuzzer_file(self):
        print("source core_fuzzer.tcl", file=self.launch_file)

    def init_design(self):
        print("set ip " + self.ip, file=self.launch_file)
        print("create_design $ip " + self.part_name, file=self.launch_file)

    def set_property(self, prop, value):
        print("set_ip_property " + prop + " " + value, file=self.launch_file)

    def gen_design(self, name):
        print("synth " + name + " $ip", file=self.launch_file)

    def run_tcl_script(self, tcl_file):
        os.system("vivado -notrace -mode batch -source " + tcl_file + " -stack 2000")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Selects the target IP
    parser.add_argument('--ip', default="xilinx.com:ip:c_accum:12.0")
    # Selects the FPGA architecture part
    parser.add_argument('--part', default="xc7a100ticsg324-1L")
    # Ignores integer parameters entirely
    parser.add_argument('--ignore_integer', default="1")
    # Downsample the integers parameters, only including every 'integer_step'
    parser.add_argument('--integer_step', default=1)
    # Number of random IP
    parser.add_argument('--random_count', default=100)

    args = parser.parse_args()

    fuzzer = DataGenerator(args)
    fuzzer.fuzz_IP()
