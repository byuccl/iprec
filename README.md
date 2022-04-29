# IPRec

Xilinx CoreGen module recognition project.  Lead author Corey Simpson.

This project was sponsored by the Oﬃce of Naval Research, subcontract through GrammaTech Inc., contract number N68335-20-C-0569.

# Quick Start Guide  

**Requirements:**   
* Currently supported Python 3.8.10
* **Vivado 2020.2** is installed and sourced: 
```
source /tools/Xilinx/Vivado/2020.2/settings64.sh
```

**Run:**  

1. Run the library creation Accumulator IP, targeting the artix7 using the default part xc7a100ticsg324-1L  

```
python3 run.py --ip=xilinx.com:ip:c_accum:12.0 --count=100  
```

This will generate 100 random accumulator designs under the data/<ip_name>/ folder in the form of .dcp checkpoint files. It will then export all of the checkpoint files into .json files, and then will create the library in the library/<ip_name> folder. This will take approximately 2 hours to run.  

2. Search an input design (.dcp file) for the accumulator IP.  

```
python3 run.py --ip=xilinx.com:ip:c_accum:12.0 --design="<design_name>.dcp"  
```

This will generate a design.json file which is the final output of the best-matched accumulator IP definition within the input design. It will also export the input design as a flat .json file that will be imported into an iGraph format.  

## Run Arguments  
<pre>  
parser.add_argument('--ip',default="xilinx.com:ip:c_accum:12.0")    # Selects the target IP  
parser.add_argument('--count',default=100)                          # Number of random IP   
parser.add_argument('--part',default="xc7a100ticsg324-1L")          # Selects the FPGA architecture part  
parser.add_argument('--design',default="NONE")                      # Design to Parse  
</pre>  

When --design is set to NONE, then the library generation is run, otherwise the IP search is run.  


## File Structure    

After completing the Quick Start Guide, the following file structure will be generated:  

📦iprec  
 ┣ 📂checkpoints  
 ┃ ┣ 📜checkpoint.0.graph.pkl  
 ┃ ┣ 📜checkpoint.0.mapping.pkl  
 ┃ ┣  etc..  
 ┣ 📂data  
 ┃ ┣ 📂xilinx.com:ip:c_accum:12.0  
 ┃ ┃ ┣ 📜0.dcp  
 ┃ ┃ ┣ 📜0.json  
 ┃ ┃ ┣ 📜1.dcp  
 ┃ ┃ ┣ 📜1.json  
 ┃ ┃ ┣  etc..  
 ┃ ┃ ┣ 📜launch.tcl  
 ┃ ┃ ┗ 📜properties.json  
 ┣ 📂library  
 ┃ ┣ 📂xilinx.com:ip:c_accum:12.0  
 ┃ ┃ ┣ 📂graphs  
 ┃ ┃ ┃ ┣ 📂c_accum_v12_0_14  
 ┃ ┃ ┃ ┃ ┣ 📜0.txt  
 ┃ ┃ ┃ ┃ ┣ 📜1.txt  
 ┃ ┃ ┃ ┃ ┣  etc..  
 ┃ ┃ ┃ ┣ 📂c_accum_v12_0_14_fabric_legacy  
 ┃ ┃ ┃ ┃ ┣ 📜0.txt  
 ┃ ┃ ┃ ┃ ┣ 📜1.txt  
 ┃ ┃ ┣ 📂templates  
 ┃ ┃ ┃ ┣ 📂c_accum_v12_0_14  
 ┃ ┃ ┃ ┃ ┣ 📜0.pkl  
 ┃ ┃ ┃ ┃ ┣ 📜1.pkl  
 ┃ ┃ ┃ ┣ 📂c_accum_v12_0_14_fabric_legacy  
 ┃ ┃ ┃ ┃ ┣ 📜0.pkl  
 ┃ ┃ ┃ ┃ ┣ 📜1.pkl  
 ┃ ┃ ┗ 📜templates.json  
 ┣ 📜.gitignore  
 ┣ 📜README.md  
 ┣ 📜compare_v.py  
 ┣ 📜core_fuzzer.tcl  
 ┣ 📜create_data.py  
 ┣ 📜create_lib.py  
 ┣ 📜design.json  
 ┣ 📜record_core.tcl  
 ┣ 📜run.py  
 ┗ 📜search_lib.py  
 
 
 Final output hierarchical definition after running run.py with a design is design.json. The library contains a folder for every IP. For each IP, a graphs and a templates folder exists. For every hierarchical cell found within the specimen a folder is created. Every version of the hierarchical cell will generate a textual represetation of the iGraph circuit in the graphs folder, and a pickle save of the template found in the templates folder. A final summary of all templates in the library for the given IP is found in templates.json. All specimen designs created will be saved in the data folder. A checkpoint (.dcp) file and a json textual representation of the design is saved for each specimen. Checkpoints are used in  the process of the search algorithm, and can be used to start the search algorithm at different points in the process.  
 
