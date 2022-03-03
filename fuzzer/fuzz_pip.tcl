


proc load_site_pin_dict {} {
    set fp [open "vivado_db/site_pin_dict.txt" r]
    set ::site_pin_dict [read $fp]
    #puts [dict get $file_data "BRAM_L"]
    close $fp

    set fp [open "vivado_db/placement_tcl_dict.txt" r]
    set ::placement_tcl_dict [read $fp]
    #puts [dict get $file_data "BRAM_L"]
    close $fp
}

set ::phys_count 0
set ::used_pips [list]

proc init_pip_fuzzer {tile_type} {
    set ::tile_list [get_tiles -filter "TYPE==$tile_type"]
    set ::used_pips [list]
}

load_site_pin_dict


proc place_cell_bel_pin {bel_pins T tile_type site_index S} {
    foreach BP $bel_pins {
        set ST [lindex [split $BP "."] 0]
        set bel_pin [lindex [split $BP "."] 1]
        set bel [lindex [split $bel_pin "/"] 0]
        set prim_key [join [list $tile_type $site_index $ST $bel] "."]
        if {[get_cells -of_objects [get_bels "$S/$bel"]] != ""} {
            return $bel_pin
        }
        if {[dict exists $::placement_tcl_dict $prim_key] != 0} {
            if {[catch {set_property MANUAL_ROUTING $ST $S}] == 0} {
                set primitive [dict get $::placement_tcl_dict $prim_key]
                set C [create_cell -reference $primitive "$T:$site_index:$bel"]
                
                if {[catch {[place_cell $C "$S/$bel"]}] == 0} { 
                    puts "PLACED6"
                } else {
                    remove_cell $C
                    #reset_property MANUAL_ROUTING [get_sites [lindex $S $site_index]]
                }
                return $bel_pin
            }
        } else {
            return "NO_DICT_ENTRY_$prim_key"
        }
    }
}




proc set_sink_of_site_pin {SP} {
    # foreach bel pin, get site pin - then look up in primitive dictionary the cell pin bel pin mapping
        # this works! minus intrasite routing, but it works - see FF bel pins
    #puts $SP
    set sp_str [lindex [split $SP "/"] end]
    set T [get_tiles -of_objects $SP]
    set tile_type [get_property TYPE $T]
    set sites [get_sites -of_objects $T]
    set S [get_sites -of_objects $SP]
    set site_index [lsearch -exact $sites $S]
    set SP_name [join [list $tile_type $site_index $sp_str] "."]
    set cell_pin ""
    if {$sp_str == "HARD0"} {
        incr ::phys_count
        create_cell -reference GND "GND_$::phys_count"
        set cell_pin [get_pins -of_objects [get_cells "GND_$::phys_count"] -filter "DIRECTION =~ OUT"]
    } elseif {$sp_str == "HARD1"} {
        incr ::phys_count
        create_cell -reference VCC "VCC_$::phys_count"
        set cell_pin [get_pins -of_objects [get_cells "VCC_$::phys_count"] -filter "DIRECTION =~ OUT"]
    } else {
        if {[dict exists $::site_pin_dict $SP_name] != 0} {
            if { [lsearch -exact [list "CLBLL_L" "CLBLL_R" "CLBLM_L" "CLBLM_R"] $tile_type] == -1 } {
                set bel_pins [dict get $::site_pin_dict $SP_name]
                set bel_pin [place_cell_bel_pin $bel_pins $T $tile_type $site_index $S]
                set cell_pin [get_pins -of_objects [get_bel_pins "$S/$bel_pin"]]
            } else {
                set bel_pin [dict get $::site_pin_dict $SP_name]
                set bel_pin [lindex [split [lindex $bel_pin 0] "."] 1]
                set cell_pin [get_pins -of_objects [get_bel_pins "$S/$bel_pin"]]
            }
        } else {
            set cell_pin "NONE"
        }   
    }
    if {($cell_pin != "NONE") && ($cell_pin != "")} {
        return $cell_pin
    } else {
        return "NONE"
    }
}

proc removed_unused_cells {} {
    set used_cells [get_cells -of_objects [get_pins -filter "IS_CONNECTED==1"]]
    create_property USED_PINS -class cell -default_value 0
    set_property USED_PINS 0 [get_cells]  
    set_property USED_PINS 1 [get_cells $used_cells]
    set_property DONT_TOUCH 0 [get_cells -filter "USED_PINS == 0"]
    remove_cell [get_cells -filter "USED_PINS == 0"]
    # Remove Failed nets:
    foreach N [get_nets -filter "ROUTE_STATUS==ANTENNAS || ROUTE_STATUS==CONFLICTS"] {
        disconnect_net -net $N -objects [get_pins -of_objects $N]
        remove_net -net $N
    }

}


proc record_pips {} {
    foreach N [get_nets] {
        foreach P [get_pips -of_objects $N] {
            puts $P
        }
    }
}
#create_route BYP_ALT1->>BYP_L1 [list]




proc get_pip_site_pin {pip direction restricted_list} {
    puts "DIRECTION:$direction"
    set visited $restricted_list
    set queue [list]
    lappend visited [lindex [split $pip "/" ] end]
    lappend queue [list $pip]
    #puts "BEFORE NODE"
    set N [get_nodes -of_objects $pip $direction]

    set SP [get_site_pins -of_objects $N -filter "IS_TEST==0 && NAME!~*/TST*"]
    if {[llength $SP] == 1} {
        puts "FOUND SP:$SP"
        return [list $SP [list $pip]]
    } elseif {[llength $SP] == 2} {
        if {$direction == "-downhill"} {
            set SP [lindex $SP 0]
        } else {
            set SP [lindex $SP 1]
        }
    }

    puts "BEFORE PIPS"
    if {[llength [get_pips $direction -of_objects [get_pips $pip]]] == 0} {
        puts "EMPTY PIP LENGTH"
        return "BORDER"
    }
    puts "STARTING BFS"
    while {[llength $queue] != 0} {
        set path [lindex $queue 0]
        set queue [lreplace $queue 0 0]
        #puts $path
        set rep [lindex $path end]
        puts "BFS.FOR:$rep"
        foreach P [get_pips $direction -of_objects [get_pips $rep]] {
            set SP [get_site_pins -of_objects [get_nodes -of_objects $P] -filter "IS_TEST==0 && NAME!~*/TST*"]
            if {$SP != ""} {
                lappend path $P
                lappend ::used_pips $P
                puts "BFS FOUND SP:$SP:$path"
                return [list $SP $path]
            } else {
                set p_name [lindex [split $P "/" ] end]
                if { [lsearch -exact $visited $p_name] == -1 } {
                    if { [lsearch -exact $::used_pips $P] == -1 } {
                        set new_path $path
                        lappend new_path $P
                        lappend queue $new_path
                        lappend visited $p_name
                        lappend ::used_pips $P
                    }
                }
            }
        }
    }
}

proc create_route {pip restricted_list T} {
    # tile list
    set T [get_tiles $T]
    if {$T == ""} {
        puts "\[FAIL\]:$pip:NO TILE FOUND"
        return
    }

    set P [get_pips -of_objects $T -filter NAME=~{*$pip}]
    #puts "TARGETED PIP:$P"

    # get site pin uphill
    set up_path [get_pip_site_pin $P "-uphill" $restricted_list]
    set down_path [get_pip_site_pin $P "-downhill" $restricted_list]

    if {($down_path == "BORDER")||($up_path == "BORDER")} {
        # This can fail at edges of the device - 
        puts "\[FAIL\]:$P:UP:$up_path:DOWN:$down_path:BORDER"
        #create_route $pip $restricted_list
        #puts "FINISHED SET"
        return
    } elseif {([lindex $down_path 0] == "")||([lindex $up_path 0] == "")} {
        # This can fail at edges of the device - 
        puts "\[FAIL\]:$P:UP:$up_path:DOWN:$down_path"
        return
    }
    set cell_pin_up [set_sink_of_site_pin [lindex $up_path 0]]
    set cell_pin_down [set_sink_of_site_pin [lindex $down_path 0]]
    #
    if {($cell_pin_up == "NONE")||($cell_pin_down == "NONE")} {
        puts "\[FAIL\]:$P:$cell_pin_up:$cell_pin_down"
        return
    }
    # Combine path
    puts "\[PASS\]:$P:$cell_pin_up:$cell_pin_down"

    set f0 0
    set path [lindex $down_path 1]
    foreach path_p [lindex $up_path 1] {
        if {$f0 != 0} {
            lappend path $path_p
        } else {
            incr f0
        }
    }
    # check for sink and source? what if it is bidirectional?
    create_net "net_$pip"
    set N [get_nets "net_$pip"]
    connect_net -net $N -objects $cell_pin_down
    connect_net -net $N -objects $cell_pin_up
    #puts "cell_pin_down:$cell_pin_down"
    #puts "cell_pin_up:$cell_pin_up"
    set path [lreverse $path]
    #puts $path
    set C [catch {set_property fixed_route $path $N}]
    puts "FINISHED SET"
}


# question: is there a design that every site pin will have a corresponding cell pin, and then just remove unused cells? (cells with no nets)

proc fuzz_pips {tile_type} {
    # target pip list
    set pip_list [list]
    foreach P [get_pips -filter "TILE=~$tile_type*"] {
        set pip_name [lindex [split $P "/"] 1]
        lappend pip_list $pip_name
    }
    # used pip list
    
    # for each pip
    foreach TP $pip_list {
        set P [get_pips -of_objects $T -filter "NAME~=*/$P"]
        foreach mode [list "-uphill" "-downhill"] {
            # get site pin uphill
            set SP_path [get_pip_site_pin $P $mode]
            # set sink of uphill site pin
            set_sink_of_site_pin [lindex $SP_path 0] $mode
        }
        # run drc checks
        # gen bitstream

    }
    
}







# TODO:
#   Test pip route generation
#   Write python control for PnR
#   Write condition for new bitstream
#   Check bitstream record device pips
#   Python parse pip ft file
#   Create database of overlapping bits
#   Catch cell pin not found error
#   Catch route not routeable error - don't retry in tcl, just rerun in python
#   
