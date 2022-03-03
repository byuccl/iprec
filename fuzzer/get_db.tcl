
source drc.tcl

set ::legacy_primitives [list "MUXCY" "XORCY" "AUTOBUF" "CFGLUT5" "BUF" "MMCME2_BASE" "PLLE2_BASE" "BUFGMUX" "INV" "BUFGCE" "LUT1" "LUT2" "LUT3" "LUT4" "LUT5" ] 


if {[llength $argv] == 2} {
    set ::family [lindex $argv 0] 
    set part_name [lindex $argv 1] 
} else {
    set ::family "artix7"
    set part_name "xc7a25tlcsg325-2L"
}


proc init {part_name} {
    puts "init"
    close_project -quiet
    link_design -part $part_name -quiet
    set_param tcl.collectionResultDisplayLimit 0
    
    set_msg_config -severity ERROR -suppress -quiet

    set SLICE_DRC [list "DRC RTSTAT-11 DRC DXSTAT-3"]
    set_property IS_ENABLED 0 [get_drc_checks $SLICE_DRC]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ REQP"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ DSPS"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ AVAL"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PDRC"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PLIOSTD"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PLIOBUF"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ IOSTDTYPE"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PLIDC"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ ADEF"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PDCN"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PDCY"]
    

    #set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
    #USP doesn't use the following two:
    set ::family [get_property family [get_parts -of_objects [get_projects]]]
    if {[string first "uplus" $::family] == -1} {
        set_property CFGBVS VCCO [current_design]
        set_property CONFIG_VOLTAGE 3.3 [current_design]
    }
	set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
	set_property BITSTREAM.General.UnconstrainedPins {Allow} [current_design]
}


proc get_possible_properties {C f0 prop_list} {
    # Is PULLTYPE important - how do we get it's possible values?
    set non_cfg_vals [list "BEL" "IS_BEL_FIXED" "IS_LOC_FIXED" "LOC" "DONT_TOUCH" "LOCK_PINS" "DEVICE_ID" "INIT_FILE" "HD.TANDEM" "NAME" "OFFCHIP_TERM" "PULLTYPE"]
    set property_list [list_property $C]
    foreach Pr $property_list {
        set prop [report_property -return_string $C $Pr]
        if {[lindex $prop 6] == "false"} {
            if { [lsearch -exact $non_cfg_vals $Pr] == -1 } {
                #IGNORE SIMULATION-ONLY PROPERTIES
                if {[string first "SIM_" $Pr] != 0} {
                    if { [lsearch -exact $prop_list $Pr] == -1 } {
                        lappend prop_list $Pr
                        if {$f0 == 0} {
                            incr f0
                            puts $::f "\"$Pr\": \{"
                        } else {
                            puts $::f ",\"$Pr\": \{"
                        }
                        set prop_type [lindex $prop 5]
                        puts $::f "\"PROPERTY_TYPE\":\"$prop_type\","
                        set bin_digits [lindex [split [list_property_value $Pr $C] "\'"] 0]
                        set bin_digits [string map [list "\{" ""] $bin_digits]
                        set possible_values [list_property_value $Pr $C]
                        set ref_name [get_property REF_NAME $C]
                        set default_val [get_property $Pr $C]
                        puts $::f "\"DEFAULT\":\"$default_val\","
                        if {$prop_type == "binary" || $prop_type == "hex" } {
                            puts $::f "\"BIN_DIGITS\":$bin_digits,"
                            puts $::f "\"VALUE\":\"$possible_values\""
                        } elseif {$prop_type == "double"} {
                            puts $::f "\"VALUE\":\"$possible_values\""
                        } elseif {$prop_type == "int"} {
                            if {[string first " to " $possible_values] == -1} {
                                puts $::f "\"VALUE\":\["
                                set first 0
                                foreach PV $possible_values {
                                    if {$first == 0} {
                                        incr first
                                        puts $::f "\"$PV\""
                                    } else {
                                        puts $::f ",\"$PV\""
                                    }
                                }
                                puts $::f "\]"
                            } else {
                                set max [lindex [split $possible_values " "] end]
                                set max [string map [list "\}" ""] $max]
                                set pow 1
                                while {1} {
                                    if {[expr {pow(2,$pow)}] > $max} { 
                                        break
                                    }
                                    incr pow
                                }
                                puts $::f "\"BIN_DIGITS\":$pow,"
                                puts $::f "\"VALUE\":\"$possible_values\""
                            }
                        } else {
                            puts $::f "\"VALUE\":\["
                            set first 0
                            
                            foreach PV $possible_values {
                                if {$first == 0} {
                                    incr first
                                    puts $::f "\"$PV\""
                                } else {
                                    puts $::f ",\"$PV\""
                                }
                            }
                            puts $::f "\]"
                        }
                        puts $::f "\}"
                    }
                }
            }
        }
    }
    return $prop_list
}


proc get_primitive_property_dict {} {
    set primitives [get_primitives -hierarchy -filter "PRIMITIVE_LEVEL == LEAF"]
    puts $::f "\{\"PRIMITIVE\": \{"
    set count 0
    foreach P $primitives {
        if { [lsearch -exact $::legacy_primitives $P] == -1 } {
            if {$count == 0} {
                incr count
                puts $::f "\"$P\": \{"
            } else {
                puts $::f ",\"$P\": \{"
            }
            create_cell -reference $P "C"
            set f3 0
            puts $::f "\"INVERTIBLE_PINS\": \["
            foreach CP [get_pins -of_objects [get_cells "C"]] {
                if {[catch {set_property IS_INVERTED 1 $CP}] == 0} {
                    set CP_name [lindex [split $CP "/"] end]
                    if {$f3 == 0} {
                        incr f3
                        puts $::f "\"$CP_name\""
                    } else {
                        puts $::f ",\"$CP_name\""
                    }
                }
            }
            puts $::f "\],"
            puts $::f "\"PROPERTIES\": \{"
            get_possible_properties [get_cells "C"] 0 [list]
            puts $::f "\}\}"
            remove_cell [get_cells "C"]
        }
    }
    puts $::f ",\"PORT\": \{"
    puts $::f "\"PROPERTIES\": \{"

    create_port -direction IN "p_0"
    set dirs [list "IN" "OUT" "INOUT"]
    set standards [list_property_value IOSTANDARD [get_ports "p_0"]]

    set ret [get_possible_properties [get_ports "p_0"] 0 [list]]
    foreach S $standards {
        set_property IOSTANDARD $S [get_ports "p_0"]
        foreach D $dirs {
            set_property DIRECTION $D [get_ports "p_0"]
            set ret [get_possible_properties [get_ports "p_0"] 1 $ret]
        }
    }
    puts $::f "\}\}\}\}"
}
set height_dict [dict create]
dict set height_dict "BRAM_L" 10
dict set height_dict "BRAM_R" 10
dict set height_dict "CFG_CENTER_BOT" 40
dict set height_dict "CFG_CENTER_MID" 40
dict set height_dict "CFG_CENTER_TOP" 20
dict set height_dict "CLK_HROW_BOT_R" 18
dict set height_dict "CLK_HROW_TOP_R" 18
dict set height_dict "CLK_BUFG_BOT_R" 8
dict set height_dict "CLK_BUFG_TOP_R" 8
dict set height_dict "CMT_FIFO_L" 24
dict set height_dict "CMT_FIFO_R" 24
dict set height_dict "CMT_TOP_L_LOWER_B" 32
dict set height_dict "CMT_TOP_L_LOWER_T" 18
dict set height_dict "CMT_TOP_L_UPPER_B" 24
dict set height_dict "CMT_TOP_L_UPPER_T" 26
dict set height_dict "CMT_TOP_R_LOWER_B" 32
dict set height_dict "CMT_TOP_R_LOWER_T" 18
dict set height_dict "CMT_TOP_R_UPPER_B" 24
dict set height_dict "CMT_TOP_R_UPPER_T" 26
dict set height_dict "DSP_L" 10
dict set height_dict "DSP_R" 10
dict set height_dict "GTP_CHANNEL_0" 22
dict set height_dict "GTP_CHANNEL_1" 22
dict set height_dict "GTP_CHANNEL_2" 22
dict set height_dict "GTP_CHANNEL_3" 22
dict set height_dict "GTP_COMMON" 12
dict set height_dict "HCLK_CMT_L" 10
dict set height_dict "HCLK_CMT" 10
dict set height_dict "LIOB33" 4
dict set height_dict "LIOI3" 4
dict set height_dict "LIOI3_TBYTESRC" 4
dict set height_dict "LIOI3_TBYTETERM" 4
dict set height_dict "PCIE_BOT" 40
dict set height_dict "PCIE_TOP" 10
dict set height_dict "RIOB33" 4
dict set height_dict "RIOI3" 4
dict set height_dict "RIOI3_TBYTESRC" 4
dict set height_dict "RIOI3_TBYTETERM" 4
dict set height_dict "MONITOR_BOT" 20
# KINTEXU:

if { [lsearch -exact [list "kintexuplus" "zynquplus" "virtexuplus"] $::family] == -1 } {
    dict set height_dict "BRAM" 10
    dict set height_dict "DSP" 10
    dict set height_dict "HPIO_L" 60
    dict set height_dict "GTH_QUAD_LEFT_FT" 120
    dict set height_dict "XIPHY_L" 120
    dict set height_dict "PCIE" 120
    dict set height_dict "GTH_R" 120
    dict set height_dict "AMS" 60
    dict set height_dict "HRIO_L" 60
    dict set height_dict "CFG_CFG" 120
} else {
    dict set height_dict "BRAM" 15
    dict set height_dict "DSP" 15
    dict set height_dict "HPIO_L" 90
    dict set height_dict "GTH_QUAD_LEFT_FT" 180
    dict set height_dict "XIPHY_L" 180
    dict set height_dict "PCIE" 180
    dict set height_dict "GTH_R" 180
    dict set height_dict "AMS" 90
    dict set height_dict "HRIO_L" 90
    dict set height_dict "CFG_CFG" 180
}


proc create_database {} {
    set first 0
    puts $::f "\{\"TILE_TYPE\": \{"
    foreach T_type $::tile_types {
        set tile [lindex [get_tiles -filter "TYPE =~ $T_type"] 0]
        set sites [get_sites -of_objects $tile]
        set site_count [llength $sites]
        
        if {$first == 0} {
            puts $::f "\"$T_type\": \{"
            incr first
        } else {
            puts $::f ",\"$T_type\": \{"
        }
        set f1 0
        puts $::f "\"SITE_INDEX\": \{"
        for {set i 0} {$i < $site_count} {incr i} { 
            set S [lindex $sites $i]    
            set site_type [get_property SITE_TYPE $S]
            set site_types [get_property ALTERNATE_SITE_TYPES $S]
            lappend site_types $site_type 
            if {$f1 == 0} {
                puts $::f "\"$i\": \{"
                incr f1
            } else {
                puts $::f ",\"$i\": \{"
            }
            puts $site_type
            puts $::f "\"DEFAULT_SITE_TYPE\":\"$site_type\","
            puts $::f "\"SITE_TYPE\": \{"
            set f2 0
            foreach S_type $site_types {
                if {[catch {set_property MANUAL_ROUTING $S_type $S}] == 0} {
                    if {$f2 == 0} {
                        puts $::f "\"$S_type\": \{"
                        incr f2
                    } else {
                        puts $::f ",\"$S_type\": \{"
                    }
                    set f3 0
                    puts $::f "\"BEL\": \{"
                    foreach B [get_bels -of_objects $S] {
                        set B_name [lindex [split $B "/"] end]
                        if {$f3 == 0} {
                            puts $::f "\"$B_name\": \{"
                            incr f3
                        } else {
                            puts $::f ",\"$B_name\": \{"
                        }
                        set f4 0
                        puts $::f "\"CONFIG\": \{"
                        set config_props [list_property -regexp $B "CONFIG.*"]
                        foreach C $config_props { 
                            if {[string first "VALUES" $C] != -1} {
                                set C_name [string map [list ".VALUES" "" "CONFIG." ""] $C]
                                if {$f4 == 0} {
                                    puts $::f "\"$C_name\": \{"
                                    incr f4
                                } else {
                                    puts $::f ",\"$C_name\": \{"
                                }
                                set f5 0
                                set C_vals [get_property $C $B]
                                puts $::f "\"VALUE\": \{"
                                foreach V $C_vals {
                                    set V_name [string map [list "," ""] $V]
                                    if {$f5 == 0} {
                                        puts $::f "\"$V_name\": \[\]"
                                        incr f5
                                    } else {
                                        puts $::f ",\"$V_name\": \[\]"
                                    }
                                }
                                puts $::f "\}\}"
                            }
                        }
                        puts $::f "\}\}"
                        
                    }
                    puts $::f "\},"
                    set sp_list [list]
                    puts $::f "\"SITE_PIP\": \{"
                    foreach SP [get_site_pips -of_objects $S] {
                        set sp_name [string map [list "$S/" ""] $SP]
                        set sp [lindex [split $sp_name ":"] 0]
                        set sp_val [lindex [split $sp_name ":"] 1]
                        if { [lsearch -exact $sp_list $sp] == -1 } {
                            if {[llength $sp_list] != 0} {
                                puts $::f "\}\},"
                            }
                            lappend sp_list $sp
                            puts $::f "\"$sp\": \{"
                            puts $::f "\"SITE_PIP_VALUE\":\{"
                            puts $::f "\"$sp_val\":\[\]"
                        } else {
                            puts $::f ",\"$sp_val\":\[\]"
                        }
                    }  
                    if {[llength $sp_list] != 0} {
                        puts $::f "\}\}"
                    }
                    
                   
                    puts $::f "\}\}"
                }
                reset_property MANUAL_ROUTING $S
            }
            puts $::f "\}\}"
        }
        puts $::f "\},"
        puts $::f "\"TILE_PIP\": \{"
        set f6 0 
        foreach P [get_pips -of_objects $tile] {
            set P_name [lindex [split $P "."] end]
            set O [lindex [split $P ">"] end]
            set out_list [get_pips -of_objects $tile -filter "NAME=~*$O"]
            if {$f6 != 0} {
                puts $::f ","
            } else {
                incr f6
            }
            if {[llength $out_list] == 1} {
                puts $::f "\"$P_name\":\{ \"TYPE\":\"ALWAYS\",\"BITS\":\[\] \}"
            } elseif {[string first "VCC_WIRE" $P_name] == 0} {
                puts $::f "\"$P_name\":\{ \"TYPE\":\"DEFAULT\",\"BITS\":\[\] \}"
            } elseif {([get_property IS_BUFFERED_2_1 $P] == 1) && ([get_property IS_PSEUDO $P] == 1)} {
                puts $::f "\"$P_name\":\{ \"TYPE\":\"ROUTETHRU\",\"BITS\":\[\] \}"
            } else {
                puts $::f "\"$P_name\":\{ \"TYPE\":\"PIP\",\"BITS\":\[\] \}"
            }
            ## Hardcoded psuedo checks
            #if {([get_property IS_BUFFERED_2_1 $P] == 1) && ([get_property IS_PSEUDO $P]==1)} {
            #    puts $::f "\"$P_name\":\{ \"TYPE\":\"IS_PSUEDO\",\"BITS\":\[\] \}"
            #} elseif {[llength [get_nodes -of_objects $P]] <= 1 } {
            #    puts $::f "\"$P_name\":\{ \"TYPE\":\"NO_CONNECT\",\"BITS\":\[\] \}"
            #} elseif {([llength [get_pips -of_objects [get_nodes -of_objects $P -uphill] -downhill -filter "IS_BUFFERED_2_1!=0 || IS_PSUEDO!=0"]] == 1) &&
            #          ([llength [get_pips -of_objects [get_nodes -of_objects $P -downhill] -uphill -filter "IS_BUFFERED_2_1!=0 || IS_PSUEDO!=0"]] == 1) } {
            #    puts $::f "\"$P_name\":\{ \"TYPE\":\"IS_WIRE\",\"BITS\":\[\] \}"   
            #} else {
            #    puts $::f "\"$P_name\":\{ \"TYPE\":\"PIP\",\"BITS\":\[\] \}"
            #}
        }  

        puts $::f "\}\}"
    }
    puts $::f "\}\}"
}

proc create_tilegrid {} {
    global height_dict
    set first 0
    set clock_regions [get_clock_regions]
    set max_clock 0
    foreach C $clock_regions {
        set clock_y [lindex [split $C "Y"] end]
        if {$clock_y > $max_clock} {
            set max_clock $clock_y
        }
    }
    incr max_clock
    set half_clock [expr {$max_clock/2}]
    puts "MAX:$max_clock:$half_clock"

    puts $::f "\{"
    foreach T [get_tiles] {
        if {$first == 0} {
            puts $::f "\"$T\": \{"
            incr first
        } else {
            puts $::f ",\"$T\": \{"
        }
        set has_unbonded 0
        set f1 0
        puts $::f "\"SITES\": \{"
        foreach S [get_sites -of_objects $T] {
            #If the feature exists
            if {$f1 == 0} {
                puts $::f "\"$f1\":\"$S\""
            } else {
                puts $::f ",\"$f1\":\"$S\""
            }
            incr f1
            if {[catch { [get_property IS_BONDED $S]}] == 0} {
                if {[get_property IS_BONDED $S] == 0} {
                    set has_unbonded 1
                }
            }
        }
        puts $::f "\},"
        
        set clock_region [get_clock_regions -of_objects $T]
        if {$clock_region == ""} {
            set clock_region "X-1Y-1"
        }
        set clock_x [lindex [split [lindex [split $clock_region "X"] end] "Y"] 0]
        set clock_y [lindex [split $clock_region "Y"] end]
        set coord_y [lindex [split $T "Y"] end]
        set coord_x [lindex [split [lindex [split $T "X"] end] "Y"] 0]
        set tile_type [get_property "TILE_TYPE" $T]
        set col [get_property "COLUMN" $T]
        set row [get_property "ROW" $T]
        set int_x [get_property "INT_TILE_X" $T]
        set int_y [get_property "INT_TILE_Y" $T]
        set tile_x [get_property "TILE_X" $T]
        set tile_y [get_property "TILE_Y" $T]
        
        puts $::f "\"TYPE\":\"$tile_type\","
        puts $::f "\"CLOCK_X\":$clock_x,"
        puts $::f "\"CLOCK_Y\":$clock_y,"
        puts $::f "\"Y\":$coord_y,"
        puts $::f "\"X\":$coord_x,"
        puts $::f "\"NAME\":\"$T\","
        puts $::f "\"COL\":$col,"
        puts $::f "\"ROW\":$row,"
        puts $::f "\"INT_X\":$int_x,"
        puts $::f "\"INT_Y\":$int_y,"
        puts $::f "\"TILE_X\":$tile_x,"
        puts $::f "\"TILE_Y\":$tile_y,"
        if { [lsearch -exact [list "LIOB33" "LIOB33_SING" "RIOB33" "RIOB33_SING"] $tile_type] != -1 } {
            if {$has_unbonded == 1} {
                puts $::f "\"IS_BONDED\":false,"
            } else {
                puts $::f "\"IS_BONDED\":true,"
                puts $::f "\"PACKAGE_PINS:\":\{"
                set count 0
                foreach S [get_sites -of_objects $T] {
                    set package_pin [get_package_pins -of_objects $S]
                    if {$count == 0} {
                        puts $::f "\"$count\":\"$package_pin\""
                    } else {
                        puts $::f ",\"$count\":\"$package_pin\""
                    }
                    incr count
                }
                puts $::f "\},"
            }
        }
        set h 0
        if {[dict exists $height_dict $tile_type] != 0} {
            set h [dict get $height_dict $tile_type]
        } else {
            if { [lsearch -exact [list "kintexuplus" "zynquplus" "virtexuplus"] $::family] == -1 } {
                set h 2
            } else {
                set h 3
            }
        }
        puts $::f "\"HEIGHT\":$h"
        puts $::f "\}"
    }
    puts $::f "\}"
}



proc get_site_placements { site } {
    set primitives [get_primitives -hierarchy -filter "PRIMITIVE_LEVEL == LEAF"]
    set site_placed {} 
    # Set Site type
    
    set f0 0
    puts $::f "\"BEL\": \{"
    foreach B [get_bels -of_objects $site] {
        set bel_name [lindex [split $B "/"] end]
        if {$f0 == 0} {
            incr f0
            puts $::f "\"$bel_name\": \{"
        } else {
            puts $::f ",\"$bel_name\": \{"
        }
        puts $::f "\"PRIMITIVE\": \{"
        set f1 0
        # make sure that the site chosen is not an unbonded site, but that is usually bonded.... TODO
        set package_pin [get_package_pins -of_objects $B]
        if {$package_pin != ""} {
            if {$f1 == 0} {
                incr f1
                puts $::f "\"PORT\": \{"
            } else {
                puts $::f ",\"PORT\": \{"
            }
            puts $::f "\}"
        }
        foreach P $primitives {                
            if { [lsearch -exact $::legacy_primitives $P] == -1 } {
                create_cell -reference $P "C"
                set ref_name [get_property REF_NAME [get_cells "C"]]
                tcl_drc_lut_rams $ref_name $bel_name $site
                tcl_ff_iob
                # Place and Catch
                if {[catch {[place_cell [get_cells "C"] $B]}] == 0} { 
                    if {$f1 == 0} {
                        incr f1
                        puts $::f "\"$P\": \{"
                    } else {
                        puts $::f ",\"$P\": \{"
                    }
                    set f2 0
                    if {$P == "LUT6"} {
                        tcl_lock_lut_pins
                    }
                    foreach CP [get_pins -of_objects [get_cells "C"]] {
                        set BP [get_bel_pins -of_objects $CP]
                        set CP_name [lindex [split $CP "/"] end]
                        set BP_name [string map [list "$site/" ""] $BP]
                        if {$BP != ""} {
                            if {$f2 == 0} {
                                incr f2
                                puts $::f "\"$BP_name\":\"$CP_name\""
                            } else {
                                puts $::f ",\"$BP_name\":\"$CP_name\""
                            }
                        }
                    }
                    unplace_cell [get_cells]
                    puts $::f "\}"
                }
                remove_cell [get_cells]
            }
        }
        puts $::f "\}\}"
    }
    puts $::f "\},"
    puts $::f "\"BEL_PINS\": \{"
    set f0 0
    foreach B [get_bel_pins -of_objects $site] {
        set bel_name [string map [list "$site/" ""] $B]
        set bel [lindex [split $bel_name "/"] 0]
        set legacy_bels [list "A5LUT" "B5LUT" "C5LUT" "D5LUT" "CARRY4_DMUX" "CARRY4_CMUX" "CARRY4_BMUX" "CARRY4_AMUX" "CARRY4_AXOR" "CARRY4_BXOR" "CARRY4_CXOR" "CARRY4_DXOR"]
        if { [lsearch -exact $legacy_bels $bel] == -1 } {
            if {$f0 == 0} {
                incr f0
                puts $::f "\"$bel_name\": \["
            } else {
                puts $::f ",\"$bel_name\": \["
            }
            set site_pins [get_site_pins -of_objects $B]
            set f1 0
            if {$site_pins != ""} {
                foreach SP $site_pins {
                    set SP_name [lindex [split $SP "/"] end]
                    if {$f1 == 0} {
                        incr f1
                        puts $::f "\"$SP_name\""
                    } else {
                        puts $::f ",\"$SP_name\""
                    }
                }
            }
            puts $::f "\]"
        }
    }
    puts $::f "\}"
    return $site_placed
}

proc get_tile_types {} {
    set tiles [get_tiles]
    set type {}
    foreach x $tiles {
        set prop [get_property TYPE $x]
        if { [lsearch -exact $type $prop] == -1 } {
            lappend type $prop
            if {[llength [get_pips -of_objects $x]] != 0} {
                puts $prop
            }
        }
    }
    return $type
}

proc get_tile_dict {} {
    set tiles [get_tiles]
    set type {}
    set first 0
    set bram_col [list]
    foreach T [get_tiles -filter "TYPE==BRAM_L || TYPE==BRAM_R || TYPE==BRAM"] {
        set col [get_property "COLUMN" $T]
        if { [lsearch -exact $bram_col $col] == -1 } {    
            lappend bram_col $col
        }
    }

    #set bram_col [lsort -unique $bram_col]
    
    puts $::f "\{\"BRAM_COLUMNS\":\["
    set f0 0
    foreach x $bram_col {
        if {$f0 == 0} {
            puts $::f "$x"
            incr f0
        } else {
            puts $::f ",$x"
        }
    }
    puts $::f "\],"
    
    puts $::f "\"TILE_TYPE\": \{"
    foreach x $tiles {
        set prop [get_property TYPE $x]
        if { [lsearch -exact $type $prop] == -1 } {
            if {$first == 0} {
                incr first
                puts $::f "\"$prop\": \{"
            } else {
                puts $::f ",\"$prop\": \{"
            }
            # catch edge case - LIOB33 where first tile is unbonded...
            set T [lindex [get_tiles -filter "TYPE==$prop"] end]
            set sites [get_sites -of_objects $T]
            puts $::f "\"SITE_INDEX\": \{"
            for {set i 0} {$i < [llength $sites]} {incr i} {  
                if {$i == 0} {
                    puts $::f "\"$i\": \{"
                } else {
                    puts $::f ",\"$i\": \{"
                } 
                puts $::f "\"SITE_TYPE\": \{"
                set S [lindex $sites $i] 
                set ST [get_property SITE_TYPE $S]
                set site_types [get_property ALTERNATE_SITE_TYPES $S]
                lappend site_types $ST 
                set f0 0
                foreach A $site_types {
                    if {[catch {set_property MANUAL_ROUTING $A $S}] == 0} { 
                        if {$f0 == 0} {
                            incr f0
                            puts $::f "\"$A\": \{"
                        } else {
                            puts $::f ",\"$A\": \{"
                        } 
                        get_site_placements $S
                        puts $::f "\}"
                    }
                    reset_property MANUAL_ROUTING $S
                    
                }
                puts $::f "\},"
                puts $::f "\"SITE_PINS\": \["
                set f0 0
                foreach SP [get_site_pins -of_objects $S] {
                    set SP_name [lindex [split $SP "/"] end]
                    if {$f0 == 0} {
                        incr f0
                        puts $::f "\"$SP_name\""
                    } else {
                        puts $::f ",\"$SP_name\""
                    }
                }
                puts $::f "\]"
                puts $::f "\}"
            }
            puts $::f "\}\}"
            lappend type $prop
        }
    }
    puts $::f "\}\}"
    return $type
}

proc create_pip_dict {} {
    set first 0
    puts $::f "\{\"PIPS\": \{"
    foreach T_type $::tile_types {
        set tile [lindex [get_tiles -filter "TYPE =~ $T_type"] 0]
        if {$first == 0} {
            puts $::f "\"$T_type\":\{"
            incr first
        } else {
            puts $::f ",\"$T_type\":\{"
        }
        set f0 0
        foreach P [get_pips -of_objects $tile] {
            set p_name [lindex [split $P "."] end]
            if {$f0 == 0} {
                puts $::f "\"$p_name\":\{"
                get_pip_conns $P
                puts $::f "\}"
                incr f0
            } else {
                 puts $::f ",\"$p_name\":\{"
                get_pip_conns $P
                puts $::f "\}"
            }
        }
        puts $::f "\}"
    }
    puts $::f "\}\}"
}

proc get_pip_conns {P} {
#    puts $::f "\"DOWNHILL\":\["
#    set f0 0
#    foreach D [get_pips -of_objects $P -downhill] {
#        set dp [lindex [split $D "."] end]
#        set t [get_property TYPE [get_tiles -of_objects $D]]
#        if {$f0 == 0} {
#            incr f0
#            puts $::f "\"$t:$dp\""
#        } else {
#            puts $::f ",\"$t:$dp\""
#        }
#    }
#    puts $::f "\],\"UPHILL\":\["
#    set f0 0
#    foreach U [get_pips -of_objects $P -uphill] {
#        set up [lindex [split $U "."] end]
#        set t [get_property TYPE [get_tiles -of_objects $U]]
#        if {$f0 == 0} {
#            incr f0
#            puts $::f  "\"$t:$up\""
#        } else {
#            puts $::f  ",\"$t:$up\""
#        }
#    }
#    puts $::f "\],\"SITE_PIN\":\["
    puts $::f "\"SITE_PIN\":\["
    set f0 0
    foreach S [get_site_pins -of_objects [get_nodes -of_objects $P]] {
        set s_name [lindex [split $S "/"] end]
        set site [get_sites -of_objects $S]
        set tile [get_tiles -of_objects $S]
        set T [get_property TYPE $tile]
        set site_index [lsearch -exact [get_sites -of_objects $tile] $site] 
        if {$f0 == 0} {
            incr f0
            puts $::f "\"$T:$site_index:$s_name\""
        } else {
            puts $::f ",\"$T:$site_index:$s_name\""
        }
    }
    puts $::f "\]"
}
 




proc get_all_db {} {
    init $::part_name
    write_checkpoint "init.dcp" -force
    set ::tile_types [get_tile_types]
    set ::f [open "primitive_dict.json" w]
    get_primitive_property_dict
    close $::f
    set ::f [open "bel_dict.json" w]
    create_database
    close $::f
    open_checkpoint "init.dcp"
    set ::f [open "tilegrid.json" w]
    create_tilegrid
    close $::f
    set ::f [open "tile_dict.json" w]
    get_tile_dict
    close $::f
}


file mkdir "$::family"
file mkdir "$::family/$part_name"
file mkdir "$::family/$part_name/vivado_db"

cd "$::family/$part_name/vivado_db/"
get_all_db
cd "../../.."

