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
This script takes in a selected IP Core then:
1. Launches a tcl script to get all of the possible properties of the IP
2. Randomly generates X number of designs with the instantiated core randomly parameterized
3. Writes a TCL script that creates the designs in part 2
4. Executes the TCL script (created in part 3) in Vivado to create the designs
"""

import argparse
from datetime import datetime
import json
import random
from subprocess import Popen, PIPE, STDOUT
import sys

from .config import ROOT_PATH, VIVADO, DATA_DIR, LIB_DIR, CORE_FUZZER_TCL


class DataGenerator:
    """
    Generates designs that instantiates the single IP core with randomized properties.
    """

    def __init__(self, ip, part, ignore_integer=True, integer_step=1, random_count=100):
        self.random_count = random_count
        self.ip = ip
        self.part_name = part
        self.ignore_integer = ignore_integer
        self.integer_step = integer_step
        self.launch_file_name = DATA_DIR / ip / "launch.tcl"
        self.ip_dict = {}
        self.launch_file = None
        random.seed(datetime.now())

        self.data_dir = DATA_DIR / self.ip
        self.lib_dir = LIB_DIR / self.ip
        self.make_dirs()
        self.get_ip_props()
        self.fuzz_ip()

    # Steps up the Folder Structure
    def make_dirs(self):
        self.lib_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # Executes the TCL script that creates the dictionary of parameters of the IP (in a JSON)
    def get_ip_props(self):
        """Get Properties for configurable IP"""
        if not (ROOT_PATH / "data" / self.ip / "properties.json").exists():
            print("Running first time IP Property Dictionary Generation")
            self.launch_file = open(self.launch_file_name, "w", buffering=1)
            self.source_fuzzer_file()
            self.init_design()
            print("get_prop_dict $ip", file=self.launch_file)
            self.launch_file.close()
            self.run_tcl_script(self.launch_file_name)
        with open("data/" + self.ip + "/properties.json") as f:
            self.ip_dict = json.load(f)

    def randomize_props(self):
        """Randomize each parameter in the IP core"""

        for x in self.ip_dict["PROPERTY"]:
            if x["type"] == "ENUM":
                val = random.choice(x["values"])
                self.set_property(x["name"], val)
            elif not self.ignore_integer:
                val = random.randrange(x["min"], x["max"], self.integer_step)
                self.set_property(x["name"], str(val))

    def fuzz_ip(self):
        """Main fuzzer"""
        self.launch_file = open(self.launch_file_name, "w", buffering=1)

        # Generate one with all default properties
        self.source_fuzzer_file()
        self.init_design()
        self.gen_design(1)

        # Generate with random properties
        for i in range(1, self.random_count):
            self.source_fuzzer_file()
            self.init_design()
            self.randomize_props()
            self.gen_design(i)

        self.launch_file.close()
        self.run_tcl_script(self.launch_file_name)

    # TCL command wrapper functions

    def source_fuzzer_file(self):
        print(f"source {CORE_FUZZER_TCL}", file=self.launch_file)

    def init_design(self):
        print(f"set ip {self.ip}", file=self.launch_file)
        print(f"create_design $ip {self.part_name}", file=self.launch_file)

    def set_property(self, prop, value):
        print(f"set_ip_property {prop} {value}", file=self.launch_file)

    def gen_design(self, name):
        print(f"synth -quiet {name} $ip", file=self.launch_file)

    def run_tcl_script(self, tcl_file):
        """Start subproccess to run selected tcl script"""
        cmd = [
            VIVADO,
            "-notrace",
            "-mode",
            "batch",
            "-source",
            str(tcl_file),
            "-stack",
            "2000",
            "-nolog",
            "-nojournal",
        ]
        proc = Popen(cmd, cwd=self.data_dir, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
        for line in proc.stdout:
            sys.stdout.write(line)
        proc.communicate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="xilinx.com:ip:c_accum:12.0")
    parser.add_argument("--part", default="xc7a100ticsg324-1L")
    parser.add_argument("--ignore_integer", default=False, action="store_true",
                        help="Completely ignore integer parameters")
    parser.add_argument("--integer_step", default=1, type=int,
                        help="Downsample the integers parameters to be only every 'integer_step'")
    parser.add_argument("--random_count", default=100, type=int, help="Number of random IP")
    args = parser.parse_args()
    DataGenerator(**args.__dict__)


if __name__ == "__main__":
    main()
