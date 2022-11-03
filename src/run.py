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
Run iprec flow.

This script combines each step in the flow for IPRec, and creates a select
between "creating the library for the first time", and "searching for the ip
in a design"
ip Characterization:
1. From a selected ip Core, it launches the "specimen generation" step that
generates all of the randomized designs.
2. Executes the library creation step with the generated data to create a
library of all of the hierarchical cells seen in the designs created in step 1.
ip Search:
1. Launches the ip search script that searchs for the ip within the given
design (.dcp file)
"""

import os
import argparse
from pathlib import Path

from .create_data import DataGenerator
from .create_lib import LibraryGenerator

ROOT_PATH = Path(__file__).resolve().parent.parent


def run_flow(ip, count=100, part="xc7a100ticsg324-1L", design=None, force=False):
    if (design is None) or (not (ROOT_PATH / "library" / ip).exists()) or force:
        if not ip.endswith(".dcp"):
            DataGenerator(ip=ip, part=part, random_count=count)
        LibraryGenerator(ip=ip)
    if design:
        os.system("python search_lib.py " + design + " --ip=" + ip)


def run():
    """Parse arguments and pass them to the iprec flow."""
    parser = argparse.ArgumentParser()
    # Selects the target ip
    parser.add_argument("ip", help="Xilinx ip or DCP file of ip to scan for")
    parser.add_argument("--count", default=100, help="Number of random ip", type=int)
    parser.add_argument("--part", default="xc7a100ticsg324-1L", help="Xilinx device part")
    parser.add_argument("--design", default=None, help="Design to scan for ip")
    parser.add_argument(
        "--force",
        "-f",
        default=False,
        action="store_true",
        help="Force regeneration of ip data/libraries",
    )
    args = parser.parse_args()

    run_flow(**args.__dict__)


if __name__ == "__main__":
    run()
