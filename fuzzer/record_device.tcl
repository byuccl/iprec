
proc hex2bin s {
    regsub -all 0 $s 0000 s
    regsub -all 1 $s 0001 s
    regsub -all 2 $s 0010 s
    regsub -all 3 $s 0011 s
    regsub -all 4 $s 0100 s
    regsub -all 5 $s 0101 s
    regsub -all 6 $s 0110 s
    regsub -all 7 $s 0111 s
    regsub -all 8 $s 1000 s
    regsub -all 9 $s 1001 s
    regsub -all A $s 1010 s
    regsub -all B $s 1011 s
    regsub -all C $s 1100 s
    regsub -all D $s 1101 s
    regsub -all E $s 1110 s
    regsub -all F $s 1111 s
    return $s
}



proc bi_pip {P N pip_name tile_name f} {
    set DP [lindex [split $P "-"] end]
    set found 0
    foreach NP [get_pips -of_objects $N] {
        if {$P != $NP} {
            if {[string first $DP $NP] != -1} {
                set found 1
                #puts "FOUND UPHILL $NP"
                set pip_name [string map [list "<" ""] $pip_name]
                set out [lindex [split $pip_name "-"] 0]
                set tile_type [lindex [split $out "."] 0]
                set out [lindex [split $out "."] 1]
                set in [lindex [split $pip_name ">"] end]
                puts $f "$tile_name:Tile_Pip:$tile_type.$in->>$out"
                break
            }
        }
    }
    if {$found == 0} {
        set pip_name [string map [list "<" ""] $pip_name]
        puts $f "$tile_name:Tile_Pip:$pip_name"
    }
}

proc record_device_pips {file_name} {
    set f [open $file_name w]
    foreach N [get_nets -filter "TYPE!=POWER"] {
        foreach P [get_pips -of_objects [get_nets $N]] {
            set pip_name [lindex [split $P "/"] 1]
            set tile_name [lindex [split $P "/"] 0]
            if {[string first "<" $P] != -1} {
                bi_pip $P $N $pip_name $tile_name $f
            } else {
                puts $f "$tile_name:Tile_Pip:$pip_name"
            }
        }
    } 
    foreach N [get_nets -filter "TYPE==POWER"] {
        foreach P [get_pips -of_objects [get_nets $N]] {
            set pip_name [lindex [split $P "/"] 1]
            set tile_name [lindex [split $P "/"] 0]
            # Figure out direction of bi-directional PIP
            if {[string first "<" $P] != -1} {
                bi_pip $P $N $pip_name $tile_name $f
            } else {
                puts $f "$tile_name:Tile_Pip:$pip_name"
            }
        }
        break
    }
    close $f
}


proc record_device {file_name tile_type} {
    set f [open $file_name w]
    foreach T [get_tiles -filter "TYPE==$tile_type"] {
        set sites [get_sites -of_objects $T]
        for {set site_index 0} {$site_index < [llength $sites]} {incr site_index} { 
            set S [lindex $sites $site_index]
            set site_type [get_property SITE_TYPE $S]
            if {[llength [get_cells -of_objects $S]] != 0} {
                set bel_list [get_bels -include_routing_bels -of_objects $S]
                foreach B $bel_list {
                    if {[get_property NUM_CONFIGS $B] > 0} {
                        set config_props [list_property -regexp $B "CONFIG.*"]
                        foreach C $config_props {
                            # Filter the "possible values" attribute
                            if {[string first "VALUES" $C] == -1} {
                                set bel_name [string map [list "$S/" "$site_index:$site_type:"] $B]
                                set prop_val [get_property $C $B]
                                if {$prop_val != ""} {
                                    set C_name [string map [list "CONFIG." ""] $C]
                                    #if {$C == "CONFIG.EQN"} {
                                    #    set cell [get_cells -of_objects $B]
                                    #    if {$cell != ""} {
                                    #        set ref_name [get_property REF_NAME $cell ]
                                    #        # This is annoying - SRL, DRAM and so on various forms of the INIT (cell property) and EQN (bel property)
                                    #        # And these don't have the same mapping from INIT to EQN. Use only lut 6 for now
                                    #        if {$ref_name == "LUT6"} {
                                    #            set prop_val [get_property "INIT" $cell]
                                    #        } else {
                                    #            continue
                                    #        }
                                    #    }
                                    #}
                                    puts $f "$T:$bel_name:$C_name:$prop_val"
                                }
                            }
                        }
                    }
                } 
                foreach SP [get_site_pips -of_objects $S] {
                    if {[get_property "IS_USED" $SP] == 1} {
                        set sp_name [string map [list "$S/" "$site_index:$site_type:"] $SP]
                        puts $f "$T:$sp_name"
                    }    
                }    
            }
        }
    }
    
    foreach N [get_nets] {
        foreach P [get_pips -of_objects [get_nets $N] -filter "TILE=~$tile_type*"] {
            set pip_name [lindex [split $P "/"] 1]
            set tile_name [lindex [split $P "/"] 0]
            # Figure out direction of bi-directional PIP
            if {[string first "<" $P] != -1} {
                bi_pip $P $N $pip_name $tile_name
            } else {
                puts $f "$tile_name:Tile_Pip:$pip_name"
            }
        }
    } 
    close $f
}

#record_device [lindex $argv 0] [lindex $argv 1]


# Difference is alt site types need to be figured out
    # Site type isn't dynamically updated
    # Only way to know is to set the site type manually, and if it passes use that site type
    # more than 1 site type may pass however - Is there a better way?
    # Example - BRAM will always be site type RAMBFIFO36E1, but if this site type is manually set, nothing is placeable there
proc record_device_benchmark {file_name tile_type} {
    set f [open $file_name w]
    foreach T [get_tiles -filter "TYPE==$tile_type"] {
        set sites [get_sites -of_objects $T]
        for {set site_index 0} {$site_index < [llength $sites]} {incr site_index} { 
            set S [lindex $sites $site_index]
            set site_types [get_property ALTERNATE_SITE_TYPES $S]
            set cur_site_type [get_property SITE_TYPE $S]
            lappend site_types $cur_site_type  
            foreach ST $site_types {
                # Only record on site types that are possible
                if {[catch {set_property MANUAL_ROUTING $ST $S}] == 0} { 
                    if {[llength [get_cells -of_objects $S]] != 0} {
                        set bel_list [get_bels -include_routing_bels -of_objects $S]
                        foreach B $bel_list {
                            if {[get_property NUM_CONFIGS $B] > 0} {
                                set config_props [list_property -regexp $B "CONFIG.*"]
                                foreach C $config_props {
                                    # Filter the "possible values" attribute
                                    if {[string first "VALUES" $C] == -1} {
                                        set bel_name [string map [list "$S/" "$site_index:$ST:"] $B]
                                        set prop_val [get_property $C $B]
                                        if {$prop_val != ""} {
                                            set C_name [string map [list "CONFIG." ""] $C]
                                            puts $f "$T:$bel_name:$C_name:$prop_val"
                                        }
                                    }
                                }
                            }
                        } 
                        foreach SP [get_site_pips -of_objects $S] {
                            if {[get_property "IS_USED" $SP] == 1} {
                                set sp_name [string map [list "$S/" "$site_index:$ST:"] $SP]
                                puts $f "$T:$sp_name"
                            }    
                        }    
                    }
                }
                reset_property MANUAL_ROUTING $S
            }
        }
    }
    foreach N [get_nets] {
        foreach P [get_pips -of_objects [get_nets $N] -filter "TILE=~$tile_type*"] {
            set pip_name [lindex [split $P "/"] 1]
            set tile_name [lindex [split $P "/"] 0]
            puts $f "$tile_name:Tile_Pip:$pip_name"
        }
    } 
    close $f
}
