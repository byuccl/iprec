
#!/usr/bin/env python3
import json
import os
import sys
import argparse
import random
import numpy as np
import re
import pickle

# This script combines each step in the flow for IPRec, and creates a select between "creating the library for the first time", and "searching for the IP in a design"
    # IP Characterization: 
        # 1. From a selected IP Core, it launches the "specimen generation" step that generates all of the randomized designs
        # 2. Executes the library creation step with the generated data to create a library of all of the hierarchical cells seen in the designs created in step 1.
    # IP Search:
        # 1. Launches the IP search script that searchs for the IP within the given design (.dcp file)

parser = argparse.ArgumentParser()
parser.add_argument('--ip',default="xilinx.com:ip:c_accum:12.0")    # Selects the target IP
parser.add_argument('--count',default=100)                          # Number of random IP 
parser.add_argument('--part',default="xc7a100ticsg324-1L")          # Selects the FPGA architecture part

parser.add_argument('--design',default="NONE")                      # Design to Parse

args = parser.parse_args()
print(args)

if args.design == "NONE":
    #os.system("python3 create_data.py --ip=" + args.ip + " --random_count=" + str(args.count) + " --part="+args.part)   
    os.system("python3 create_lib.py --ip=" + args.ip)      
else:
    os.system("python3 search_lib.py "+args.design+" --ip=" + args.ip)   

