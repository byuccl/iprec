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
from itertools import cycle
import json
import random
from subprocess import Popen, PIPE

from config import ROOT_PATH, DATA_DIR, LIB_DIR, CORE_FUZZER_TCL


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
        self.log_file = DATA_DIR / self.ip / "vivado_runs.log"
        self.log_file.unlink(missing_ok=True)
        random.seed(datetime.now().timestamp())

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
            process = self.launch("0")
            process.stdin.write(f"set ip {self.ip}\n")
            self.source_fuzzer_file(process.stdin)
            self.init_design(process.stdin)
            process.stdin.write("get_prop_dict $ip\n")
            process.stdin.write("exit\n")
            process.stdin.close()
            process.wait()
        with open(ROOT_PATH / "data" / self.ip / "properties.json") as f:
            self.ip_dict = json.load(f)

    def randomize_props(self, stream):
        """Randomize each parameter in the IP core"""

        properties = {}
        for x in self.ip_dict["PROPERTY"]:
            if x["type"] == "ENUM":
                val = random.choice(x["values"])
                self.set_property(x["name"], val, stream)
                properties[x["name"]] = val
            elif not self.ignore_integer:
                val = random.randrange(x["min"], x["max"], self.integer_step)
                self.set_property(x["name"], str(val), stream)
                properties[x["name"]] = str(val)
        return properties

    def fuzz_ip(self):
        """Main fuzzer"""
        processes = [self.launch(str(x)) for x in range(8)]
        for process in processes:
            process.stdin.write(f"set ip {self.ip}\n")
        pool = cycle(processes)
        process = next(pool)
        # Generate one with all default properties
        self.init_design(process.stdin)
        self.gen_design(0, process.stdin)

        # Generate with random properties
        for i in range(1, self.random_count):
            process = next(pool)
            self.init_design(process.stdin)
            props = self.randomize_props(process.stdin)
            self.gen_design(i, process.stdin)
            with open(self.data_dir / f"{i}_props.json", "w") as f:
                json.dump(props, f, indent=4)

        for process in processes:
            process.stdin.write("exit\n")
            process.stdin.close()
        for process in processes:
            process.wait()

    # TCL command wrapper functions
    def source_fuzzer_file(self, stream):
        stream.write(f"source {CORE_FUZZER_TCL} -notrace\n")

    def init_design(self, stream):
        stream.write(f"create_design $ip {self.part_name}\n")

    def set_property(self, prop, value, stream):
        stream.write(f"set_ip_property {prop} {value}\n")

    def gen_design(self, name, stream):
        stream.write(f"synth {name} $ip\n")

    def launch(self, x):
        """Runs the export design from a .dcp of"""
        (ROOT_PATH / x).mkdir(exist_ok=True)
        cmd = [
            "vivado",
            "-notrace",
            "-mode",
            "tcl",
            "-source",
            str(CORE_FUZZER_TCL),
            "-stack",
            "2000",
            "-nolog",
            "-nojournal",
        ]

        return Popen(cmd, stdin=PIPE, cwd=(ROOT_PATH / x), universal_newlines=True)

    def run_tcl_script(self, tcl_file):
        """Start subproccess to run selected tcl script"""
        cmd = [
            "vivado",
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
        with open(self.log_file, "a+") as f:
            proc = Popen(cmd, cwd=ROOT_PATH, universal_newlines=True)
            proc.communicate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ip", help="Xilinx IP to fuzz")
    parser.add_argument("--part", default="xc7a100ticsg324-1L")
    parser.add_argument(
        "--ignore_integer",
        default=False,
        action="store_true",
        help="Completely ignore integer parameters",
    )
    parser.add_argument(
        "--integer_step",
        default=1,
        type=int,
        help="Downsample the integers parameters to be only every 'integer_step'",
    )
    parser.add_argument("--random_count", default=100, type=int, help="Number of random IP")
    args = parser.parse_args()
    DataGenerator(**args.__dict__)


if __name__ == "__main__":
    main()
