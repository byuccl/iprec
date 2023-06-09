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

# This script opens a checkpoint file, and exports all of the design's properties into a JSON that can be parsed and imported into iGraph.
    # There is also an option to keep hierarchy (record_core), or flatten all of the hierarchy (record_flat_core)

# This function is used in create_lib.py that will export the IP core design into a JSON file to be imported into iGraph
# Should take an open output file, and expects a checkpoint to be open.
proc record_core {out} {
    set i 0
    puts $out "\{\"NETS\":\{"
    # Record all the of Nets properties, which needs:
        # Which Hier. Cell pins it is connected to
        # Which Leaf Cell pins it is connected to
        # Which pin is the driver
    foreach N [get_nets -segments -hierarchical] {
        if {$i} { puts $out ","}
        incr i
        set net_parent [get_property PARENT_CELl $N]
        puts $out "\"$N\":\{"
        set driver [all_fanin -to $N]
        if {[llength $driver] >= 1} {
            set pins [get_pins -of_objects $N -filter "DIRECTION==OUT"]
            if {$pins == ""} { 
                set pins [get_pins -of_objects $N]
            }
            foreach D $driver {
                if { [lsearch -exact $pins $D] != -1 } {
                    set driver $D
                }
            }
        } else {
            set driver [get_pins -of_objects $N -filter "DIRECTION==OUT"]
        }

        puts $out "\"PARENT\":\"$net_parent\"\,"
        puts $out "\"DRIVER\":\"$driver\"\,"
        foreach bool [list 0 1] {
            puts $out "\"LEAF.$bool\":\{"
            puts $out "\"OUTPUTS\":\["
            set j 0
            foreach P [get_pins -of_objects $N -filter "DIRECTION==OUT && IS_LEAF==$bool"] {
                if {$j} { puts $out ","}
                incr j
                puts $out "\"$P\""
            }
            set j 0
            puts $out "\],\"INPUTS\":\["
            foreach P [get_pins -of_objects $N -filter "DIRECTION==IN && IS_LEAF==$bool"] {
                if {$j} { puts $out ","}
                incr j
                puts $out "\"$P\""
            }
            puts $out "\]"
            puts $out "\}"
            if {$bool == 0} { puts $out ","}
        }
        puts $out "\}"
    }

    puts $out "\},\"CELLS\":\{"
    # Records the current state of all of the Cell's in the design, which includes:
        # The type of cell it is (ref name)
        # The parent cell
        # What BEL it is mapped to
        # All of the corresponding BEL's properties
    set cell_list [get_cells -hierarchical]
    foreach C $cell_list {
        catch {list_property -quiet $C }
    }
    set i 0
    foreach C $cell_list {
        if {$i} { puts $out ","}
        puts $out "\"$C\":\{"
        incr i
    
        set ref_name [get_property REF_NAME $C]
        set parent [get_property PARENT $C]
        set prim_count [get_property PRIMITIVE_COUNT $C]
        set is_prim [get_property IS_PRIMITIVE $C]
        puts $out "\"REF_NAME\":\"$ref_name\","
        puts $out "\"PARENT\":\"$parent\","
        puts $out "\"PRIM_COUNT\":$prim_count,"
        puts $out "\"IS_PRIMITIVE\":$is_prim"
        if {$is_prim == 0} {
            set orig_ref_name [get_property ORIG_REF_NAME $C]
            puts $out ",\"ORIG_REF_NAME\":\"$orig_ref_name\""
            puts $out ",\"CELL_PROPERTIES\":\{"
            set j 0
            foreach P [list_property $C -regexp "\[cC\]_.*"] {
                set val [get_property $P $C]
                if {$val != ""} {
                    if {$j} { puts $out ","}
                    puts $out "\"$P\":\"$val\""
                    incr j
                }
            }
            puts $out "\}"
        } else {
            puts $out ",\"BEL_PROPERTIES\":\{"
            set B [get_bels -of_objects $C]
            set j 0
            if { $B != ""} {
                if {[llength $B] > 1} {
                    # LUT6_2 returns two bels for the single cell C
                    foreach b $B {
                        set bel_name [lindex [split $b "/"] 1]
                        set bel_name [string map [list "A" "" "B" "" "C" "" "D" ""] $bel_name]
                        foreach P [list_property $b] {
                            if {[string first "CONFIG." $P] == -1} { continue }
                            if {[string first ".VALUES" $P] != -1} { continue }
                            set val [get_property $P $b]
                            if {$j} { puts $out ","}
                            puts $out "\"$bel_name.$P\":\"$val\""
                            incr j
                        }
                    }
                } else {
                    foreach P [list_property $B] {
                        if {[string first "CONFIG." $P] == -1} { continue }
                        if {[string first ".VALUES" $P] != -1} { continue }
                        set val [get_property $P $B]
                        if {$j} { puts $out ","}
                        puts $out "\"$P\":\"$val\""
                        incr j
                    }
                }
            }
            puts $out "\}"
        }
        puts $out "\}"
    }
    puts $out "\}\}"
}

# Records a benchmark design into a flat JSON file structure used for importing it into an iGraph
    # This is used in the search_lib.py script to export the input design into iGraph to be searched
proc record_flat_core {out} {
    puts "FLATTENING DCP"
    set i 0
    set count 0
    puts $out "\{\"CELLS\":\{"
    # Records the current state of all of the leaf Cells, which needs:
        # What type of cell it is (ref_name)
        # What BEL it is mapped to
        # All of the corresponding BEL's properties
    foreach C [get_cells -hierarchical -filter "IS_PRIMITIVE==1"]  {
        set ref_name [get_property REF_NAME $C]
        set loc [get_property LOC $C]
        set bel [get_property BEL $C]
        if {($ref_name == "GND") || ($ref_name=="VCC")} {
            set name "$C" 
        } else {
           set name "$loc.$bel" 
        }
        if {$i} { puts $out ","}
        incr i
        puts $out "\"$name\":\{"
        puts $out "\"CELL_NAME\":\"$C\"," 
        set parent ""
        set prim_count ""
        set is_prim [get_property IS_PRIMITIVE $C]
        puts $out "\"REF_NAME\":\"$ref_name\","
        puts $out "\"PARENT\":\"$parent\","
        puts $out "\"PRIM_COUNT\":1,"
        puts $out "\"IS_PRIMITIVE\":$is_prim"
        puts $out ",\"BEL_PROPERTIES\":\{"
        set B [get_bels -of_objects $C]
        set j 0
        if { $B != ""} { 
            if { [llength $B] == 1} {
                foreach P [list_property $B] {
                    if {[string first "CONFIG." $P] == -1} { continue }
                    if {[string first ".VALUES" $P] != -1} { continue }
                    set val [get_property $P $B]
                    if {$j} { puts $out ","}
                    puts $out "\"$P\":\"$val\""
                    incr j
                }
            }
        }
        puts $out "\}"
        puts $out "\}"
    }
    puts $out "\}"
    puts $out ",\"NETS\":\{"
    # Record all the of Nets properties, which needs:
        # Which Leaf Cell pins it is connected to
    set i 0
    set count 0
    foreach N [get_nets -hierarchical -segments -top_net_of_hierarchical_group ] {
        set parent ""
        set net_parent ""
        if {$i} { puts $out ","}
        puts $out "\"$count\":\{"
        incr i
        incr count
        set f1 0
        set driver [all_fanin -to $N]
        puts $out "\"PARENT\":\"$net_parent\"\,"
        puts $out "\"DRIVER\":\"FLAT_DESIGN\"\,"
        set bool 0
        puts $out "\"LEAF.$bool\":\{"
        puts $out "\"OUTPUTS\":\["
        set j 0
        foreach P [get_pins -leaf -of_objects $N -filter "DIRECTION==OUT"] {
            set C [get_cells -of_objects $P]
            set ref_name [get_property REF_NAME $C]
            set loc [get_property LOC $C]
            set bel [get_property BEL $C]
            set p_name [lindex [split $P "/"] end]
            if {($ref_name == "GND") || ($ref_name=="VCC")} {
                set name "$C" 
            } else {
                set name "$loc.$bel" 
            }
            if {$j} { puts $out ","}
            puts $out "\"$name/$p_name\""
            incr j
        }

        set j 0
        puts $out "\],\"INPUTS\":\["
        foreach P [get_pins -leaf -of_objects $N -filter "DIRECTION==IN"] {
            set C [get_cells -of_objects $P]
            set ref_name [get_property REF_NAME $C]
            set loc [get_property LOC $C]
            set bel [get_property BEL $C]
            set p_name [lindex [split $P "/"] end]
            if {($ref_name == "GND") || ($ref_name=="VCC")} {
                set name "$C" 
            } else {
                set name "$loc.$bel" 
            }
            if {$j} { puts $out ","}
            puts $out "\"$name/$p_name\""
            incr j
        }
        puts $out "\]"
        puts $out "\},"

        # Empty leaf 1
        puts $out "\"LEAF.1\":\{"
        puts $out "\"OUTPUTS\":\["
        puts $out "\],\"INPUTS\":\["
        puts $out "\]"
        puts $out "\}"

        # End json
        puts $out "\}"
    }
    puts $out "\}\}"
}

# Command line arguments to flatten or keep hierarchy of the dcp
set_msg_config -id {Vivado 12-508} -limit 0
set_msg_config -id {Common 17-346} -limit 0
set_msg_config -severity INFO -limit 0
