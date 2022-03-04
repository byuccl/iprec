# Records the implemented design into a JSON file structure used for importing it into an iGraph
proc record_core {file_name} {
    open_checkpoint "$file_name.dcp"
    set f [open "$file_name.json" w]
    set i 0
    puts $f "\{\"NETS\":\{"
    foreach N [get_nets -segments -hierarchical] {
        if {$i} { puts $f ","}
        incr i
        set net_parent [get_property PARENT_CELl $N]
        puts $f "\"$N\":\{"
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

        puts $f "\"PARENT\":\"$net_parent\"\,"
        puts $f "\"DRIVER\":\"$driver\"\,"
        foreach bool [list 0 1] {
            puts $f "\"LEAF.$bool\":\{"
            puts $f "\"OUTPUTS\":\["
            set j 0
            foreach P [get_pins -of_objects $N -filter "DIRECTION==OUT && IS_LEAF==$bool"] {
                if {$j} { puts $f ","}
                incr j
                puts $f "\"$P\""
            }
            set j 0
            puts $f "\],\"INPUTS\":\["
            foreach P [get_pins -of_objects $N -filter "DIRECTION==IN && IS_LEAF==$bool"] {
                if {$j} { puts $f ","}
                incr j
                puts $f "\"$P\""
            }
            puts $f "\]"
            puts $f "\}"
            if {$bool == 0} { puts $f ","}
        }
        puts $f "\}"
    }

    puts $f "\},\"CELLS\":\{"
    # Why is this neccesary? For some reason list_property on a synthesized out of context design will fail because 
    # "ERROR: [Constraints 18-608] We cannot route the nets within the site SLICE_X5Y44. Reason: Conflicting nets for physical connection CEUSEDMUX_OUT driven by SLICE_X5Y44.CEUSEDMUX.OUT"
    # Running list property once for every cell, the second time list property won't fail with this error
    # I think it has to do with the HD_IDF_PR_InsertedInst: being added when list_property is run...? 
    set cell_list [get_cells -hierarchical]
    foreach C $cell_list {
        catch {list_property $C }
    }
    set i 0
    foreach C $cell_list {
        if {$i} { puts $f ","}
        puts $f "\"$C\":\{"
        incr i
    
        set ref_name [get_property REF_NAME $C]
        set parent [get_property PARENT $C]
        set prim_count [get_property PRIMITIVE_COUNT $C]
        set is_prim [get_property IS_PRIMITIVE $C]
        puts $f "\"REF_NAME\":\"$ref_name\","
        puts $f "\"PARENT\":\"$parent\","
        puts $f "\"PRIM_COUNT\":$prim_count,"
        puts $f "\"IS_PRIMITIVE\":$is_prim"
        if {$is_prim == 0} {
            set orig_ref_name [get_property ORIG_REF_NAME $C]
            puts $f ",\"ORIG_REF_NAME\":\"$orig_ref_name\""
            puts $f ",\"CELL_PROPERTIES\":\{"
            set j 0
            foreach P [list_property $C -regexp "\[cC\]_.*"] {
                set val [get_property $P $C]
                if {$val != ""} {
                    if {$j} { puts $f ","}
                    puts $f "\"$P\":\"$val\""
                    incr j
                }
            }
            puts $f "\}"
        } else {
            puts $f ",\"BEL_PROPERTIES\":\{"
            set B [get_bels -of_objects $C]
            set j 0
            if { $B == ""} {continue }
            if {[llength $B] > 1} {
                # LUT6_2 returns two bels for the single cell C
                foreach b $B {
                    set bel_name [lindex [split $b "/"] 1]
                    set bel_name [string map [list "A" "" "B" "" "C" "" "D" ""] $bel_name]
                    foreach P [list_property $b] {
                        if {[string first "CONFIG." $P] == -1} { continue }
                        if {[string first ".VALUES" $P] != -1} { continue }
                        set val [get_property $P $b]
                        if {$j} { puts $f ","}
                        puts $f "\"$bel_name.$P\":\"$val\""
                        incr j
                    }
                }
            } else {
                foreach P [list_property $B] {
                    if {[string first "CONFIG." $P] == -1} { continue }
                    if {[string first ".VALUES" $P] != -1} { continue }
                    set val [get_property $P $B]
                    if {$j} { puts $f ","}
                    puts $f "\"$P\":\"$val\""
                    incr j
                }
            }
            puts $f "\}"
        }
        puts $f "\}"
    }
    puts $f "\}\}"
    close $f
}


# Records a benchmark design into a flat JSON file structure used for importing it into an iGraph
proc record_flat_core {file_name} {
    puts "FLATTENING DCP"
    open_checkpoint "$file_name.dcp"
    set f [open "$file_name.json" w]
    set i 0
    set count 0
    puts $f "\{\"CELLS\":\{"
    foreach C [get_cells -hierarchical -filter "IS_PRIMITIVE==1"]  {
        set ref_name [get_property REF_NAME $C]
        set loc [get_property LOC $C]
        set bel [get_property BEL $C]
        if {($ref_name == "GND") || ($ref_name=="VCC")} {
            set name "$C" 
        } else {
           set name "$loc.$bel" 
        }
        if {$i} { puts $f ","}
        incr i
        puts $f "\"$name\":\{"
        puts $f "\"CELL_NAME\":\"$C\"," 
        set parent ""
        set prim_count ""
        set is_prim [get_property IS_PRIMITIVE $C]
        puts $f "\"REF_NAME\":\"$ref_name\","
        puts $f "\"PARENT\":\"$parent\","
        puts $f "\"PRIM_COUNT\":1,"
        puts $f "\"IS_PRIMITIVE\":$is_prim"
        puts $f ",\"BEL_PROPERTIES\":\{"
        set B [get_bels -of_objects $C]
        set j 0
        if { $B == ""} { continue }
        if { [llength $B] != 1} { continue }
        foreach P [list_property $B] {
            if {[string first "CONFIG." $P] == -1} { continue }
            if {[string first ".VALUES" $P] != -1} { continue }
            set val [get_property $P $B]
            if {$j} { puts $f ","}
            puts $f "\"$P\":\"$val\""
            incr j
        }
        puts $f "\}"
        puts $f "\}"
    }
    puts $f "\}"
    puts $f ",\"NETS\":\{"
    set i 0
    set count 0
    foreach N [get_nets -hierarchical -segments -top_net_of_hierarchical_group ] {
        set parent ""
        set net_parent ""
        if {$i} { puts $f ","}
        puts $f "\"$count\":\{"
        incr i
        incr count
        set f1 0
        set driver [all_fanin -to $N]
        puts $f "\"PARENT\":\"$net_parent\"\,"
        puts $f "\"DRIVER\":\"FLAT_DESIGN\"\,"
        set bool 0
        puts $f "\"LEAF.$bool\":\{"
        puts $f "\"OUTPUTS\":\["
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
            if {$j} { puts $f ","}
            puts $f "\"$name/$p_name\""
            incr j
        }

        set j 0
        puts $f "\],\"INPUTS\":\["
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
            if {$j} { puts $f ","}
            puts $f "\"$name/$p_name\""
            incr j
        }
        puts $f "\]"
        puts $f "\},"

        # Empty leaf 1
        puts $f "\"LEAF.1\":\{"
        puts $f "\"OUTPUTS\":\["
        puts $f "\],\"INPUTS\":\["
        puts $f "\]"
        puts $f "\}"

        # End json
        puts $f "\}"
    }
    puts $f "\}\}"
    close $f
}

# Command line arguments to flatten or keep hierarchy of the dcp
if {[lindex $argv 1] == 0} {
    record_core [lindex $argv 0] 
} else {
    record_flat_core [lindex $argv 0] 
}