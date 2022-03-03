

# PY FUZZER



## Quick Start Guide  

**Requirements:**   
* Currently supported Python 3.8.10
* **Vivado 2020.2** is installed and sourced: 
```
source /tools/Xilinx/Vivado/2020.2/settings64.sh
```

* RapidWright 2021.2.0 - this file needs to be installed within the BitRec folder (on the same level as run_snapshot.py)  
```
wget https://github.com/Xilinx/RapidWright/releases/download/v2021.2.0-beta/rapidwright-2021.2.0-standalone-lin64.jar
```



**Run:**  

1. Run the fuzzer for the DSP_L tile, targeting the artix7 using the default part xc7a100ticsg324-1L

```
python3 run_snapshot.py --family=artix7 --tile=DSP_L
```

This will take approximately 15 minutes to run (depending on the machine), and generate around 28 bitstreams under <family_name>/<part_name>/data/0000/. Final output products will be under <family_name>/<part_name>/db/db.DSP_L.json. Errors such as "*Site <xxx> cannot be sitetype ...*" are expected at the beginning of the fuzzer. The first time you run the fuzzer "get_db.tcl" will be run, which will generate the file structure, as well as 4 json dictionaries for the fuzzer to use.  

2. Run the database generation for the artix7 - This will take 12+ hours.  

```
python3 run_snapshot.py --family=artix7
```

## Run Snapshot Arguments
<pre>
parser.add_argument('--family',default="spartan7")      # Selects the FPGA architecture family  
parser.add_argument('--part',default="DEFAULT")         # Selects the FPGA part - family's default part is chosen if no part is given  
parser.add_argument('--tilegrid_only',default="0")      # 1: Only runs the tilegrid generation for the part 0: Run both database and tilegrid generation  
parser.add_argument('--extended',default="0")           # 1: Runs fuzzer on the extended set of tiles 0: only runs on the basic tiles  
parser.add_argument('--tile',default="NONE")            # NONE: Runs all tiles, or <TILE_NAME> Will run only the single tile  
</pre>



## File Structure   

After completing the Quick Start Guide, the following file structure will be generated:

📦artix7  
 ┗ 📂xc7a100ticsg324-1L  
 ┃ ┣ 📂checkpoints  
 ┃ ┃ ┣ 📜DSP_L.0.DSP48E1.DSP48E1.DSP48E1.dcp  
 ┃ ┃ ┗ 📜DSP_L.1.DSP48E1.DSP48E1.DSP48E1.dcp  
 ┃ ┣ 📂data  
 ┃ ┃ ┣ 📂0000  
 ┃ ┃ ┃ ┣ 📜0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.bit  
 ┃ ┃ ┃ ┣ 📜0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.ft  
 ┃ ┃ ┃ ┣ 📜0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.pkl  
 ┃ ┃ ┃ ┣ 📜27.DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tile.bit  
 ┃ ┃ ┃ ┣ 📜27.DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tile.ft  
 ┃ ┃ ┃ ┣ 📜DSP_L.0.DSP48E1.DSP48E1.DSP48E1.tcl  
 ┃ ┃ ┃ ┣ 📜DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tcl  
 ┃ ┃ ┃ ┗ 📜DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tile.tcl  
 ┃ ┃ ┃ ┗ etc..  
 ┃ ┣ 📂db  
 ┃ ┃ ┣ 📜db.DSP_L.json  
 ┃ ┣ 📂fuzzer_data  
 ┃ ┃ ┗ 📜DSP_L.data.pkl  
 ┃ ┗ 📂vivado_db  
 ┃ ┃ ┣ 📜bel_dict.json  
 ┃ ┃ ┣ 📜init.dcp  
 ┃ ┃ ┣ 📜primitive_dict.json  
 ┃ ┃ ┣ 📜tile_dict.json  
 ┃ ┃ ┗ 📜tilegrid.json  

* Every fuzzer run is family and part specific, so everything will be generated under a family and a part folder, in this case artix7/xc7a100ticsg324-1L.   
* Fuzzer data will be stored in the "data" folder. Every run of the fuzzer will create a new sequentially named folder, starting at 0000. These files within the 0000 folder have the syntax of specimen_number.TILE_TYPE.SITE_INDEX.SITE_TYPE.BEL.PRIMITIVE.extension.  
* The fuzzer will attempt to place all possible primitives on every site-type bel combination.   
* The .ft files are the textual representation of the design, the .bit file is the bitstream for the design, and the .pkl file containes a pickled array of two elements, containing the combination of the .ft and .bit files, but on a per-tile basis.   
* The .tcl files are the scripts that are run on vivado to generate all of the specimen designs within the folder.
* The .tile files are the specimens that are specific to solving for the tilegrid - designs whose differences are limited to a single column in the device.
* The checkpoint designs which are placed and routed designs are located in the checkpoints folder.  
* The db folder contains the final output of the fuzzer. 
* vivado_db contains several databases used by the fuzzer. The important one for bitstream->netlist purposes is the tilegrid.json.

* init.dcp - This is the "initialized" state of the FPGA for the targeted part. The fuzzer will open this checkpoint as opposed to recreating a new empty design for speedup purposes.  
* bel_dict.json - this contains a dictionary of all tile types, their sites and respective site types, all BELs and their respective properties.  
* primitive_dict.json - this contains a list of every primitive with all cell properties and their possible values.  
* tile_dict.json - This contains a dictionary of every tile type, their sites and respective site types, and what primitives are placeable in every bel.   Additionally, all cell pins are shown with their respective bel pins.  
* tilegrid.json - This contains a dictionary of every tile, and all grid coordinates, and bitstream address information. 



## Database Gaps


1. DRC Property Fixes   
   Not all configurations of a primitive are valid. These in-valid combinations of configurations are enumerated in the DRC checks under the "AVAL" group of DRC checks (under All Rules, Netlist, Instance, Invalid attribute value, in the DRC report window). These DRC checks may be supressed, and Vivado will still generate a valid bitstream, however the issue is that the properties that Vivado reports for a given bel will not match the contents of the bitstream. Essentially, the bel properties can be in an invalid state, and Vivado will generate a bitstream ,ignoring some of these properties to fit it back into a valid state, and the only indication of vivado "ignoring bel properties" are in the DRC AVAL checks. This check is harder to identify. Turning on AVAL drc checks is a good way, as well as incorporating hardcoded fixes to ensure the invalid property combinations are never met.  

2. DRC Placement Fixes  
   These rules have to do with being able to generate a bitstream or not. For a given primitive, there exists rules that need to be followed to place the primitive in a valid manner. The difference from "DRC Property Fixes" is that the bitstream generation won't even run if these rules are invalid. Some example rules are LUTRAMs, where to place a LUTRAM on a A6LUT bel, you also have to place a LUTRAM on the D6LUT. Failed bitstreams are a good indication of failing this check. Solutions to this problem have to be hardcoded and based on experience, DRC checks, and documentation.  

3. Dependent Bits  
   There exists bits that configure multiple properties at the same time. One exmaple is in the DSP_L tile, where the ACASCREG and AREG need to be the same value at all times (values 0, 1 or 2), except for the in the case where ACASCREG=1, then AREG can equal 2. There exists a single set of bits to choose between AREG equaling 0, 1 or 2, as to be expected. However the exists no bits to indicate the values of ACASCREG, and instead there exists a bit that is 1 when ACASCREG == AREG, and 0 otherwise. This case in the DSP (along with the BCASCREG/BREG properties), is the only current example we have. This may occur in many other tiles as well. For future work, the solution is to have a second pass at the differential analysis, running on just the pips that were never associated with a property, and search for all situations that the bit was on, and off. A more complex algorithm can then deduce the dependency. Fixing this situation would also fix others that we have not detected.  

4. "Polluted" Pip bits  
   This occurs when a property value's on bit have more than just the bits that configure the given feature, and in our current state of our fuzzer, is inseperable to the bits that configure a nearby pip. This is due to the fact that our fuzzer doesn't solve for Pips. One solution is to incoporate Prjxray's database of bits, and filter those out of each property. Future work can also add a pip fuzzer.  

5. Invisible Properties  
   This one is the hardest to detect, hardest to fix, and is always in the back of my mind, because we don't know if it is localized to a few tiles, or if other tiles have similar properties. This occurs in at least 2 tile types: CMT_TOP_L/R_LOWER_B, and CMT_TOP_L/R_UPPER_T, or the "MMCM" and "PLLE2" tiles, and more than likely in the Phaser In and Phaser Out tiles as well (CMT_TOP_L/R_LOWER_T, CMT_TOP_L/R_UPPER_B). This tile however is fairly low on the priorty list. The issue is that the bel properties that are normally written directly into the bitstream, go through a "transformation phase" that is not visible to the user in any way. For example, properties that are encoded into the primitive, such as delay_time, phase, and clk_cycle, and then transformmed into variables such as high time, low time, and edge. The sign of this occurance is the property type of "double", where a property is given a string double type, however it is never directly written to the bitstream. The only current solution to this is by reading Xilinx documentation - XAPP888 - can we deduce the memory mapping for the MMCM and PLLE2 primitives. Future work can hard code this mapping directly into our database - prjxray has essentially done the same. No similar documentation for the Phase tiles has been found to date.  




## Fuzzer.py Arguments  

run_snapshot.py is just a wrapper for fuzzer.py, using known working arguments for each tile - some tiles need more data than others, which is dependent on the number of bel properties a tile contains. Some arguments are used for testing purposes, as well as rerunning portions of the fuzzer.  

<pre>
parser.add_argument('tile_type', nargs=1)                   # Selects the target tile type
parser.add_argument('--family',default="spartan7")          # Selects the FPGA architecture family
parser.add_argument('--part',default="xc7s25csga324-1")     # Selects the FPGA part
parser.add_argument('--init',default=1)                     # 1:reinitialize checkpoint files, 0:use old checkpoints
parser.add_argument('--checkpoints',default=1)              # 1:Write checkpoint files for every bitstream
parser.add_argument('--fuzzer',default=1)                   # 1:Run data generation 0: skip data generation, just run differential analysis
parser.add_argument('--drc',default=0)                      # 1:Enable Vivado DRC checks, 0:Disable Vivado DRC Checks
parser.add_argument('--diff_folder',default="NONE")         # Specifiy a different folder to run diff analysis on - EX. "0011"
parser.add_argument('--verbose',default=0)                  # 1: Outputs initialized differential data and bitstream data to file
parser.add_argument('--tilegrid',default=1)                 # 1: Run if needed, 0: don't run, 2: only run tilegrid 
parser.add_argument('--iterative',default=1)                # 1: Runs iterative method, 0: random only
parser.add_argument('--random_count',default=200)           # Number of randomized cells to create
parser.add_argument('--tilegrid_count',default=2)           # Number of tilegrid specimens to create per column
parser.add_argument('--cell_count',default=510)             # Maximum number of tiles to use per bitstream
parser.add_argument('--site_count',default=100)             # Maximum number of sites to fuzz - useful for tiles with identical sites
parser.add_argument('--checkpoint_choice',default=-1)       # Site values of the checkpoint to open for the tilegrid fuzzer
parser.add_argument('--checkpoint_count',default=1)         # Number of different checkpoint files to run tilegrid generation on
parser.add_argument('--parallel',default=8)                 # Runs tile in parallel for N number of processes
parser.add_argument('--pips',default=0)                     # 1: Turns on the pip_fuzzer, 0: turns it off
</pre>


