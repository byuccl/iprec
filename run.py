
#!/usr/bin/env python3
import json
import os
import sys
import argparse
import random
import numpy as np
import re
import pickle

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

