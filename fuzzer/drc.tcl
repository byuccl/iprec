
proc tcl_lock_lut_pins {} {
    foreach C [get_cells -filter "REF_NAME==LUT6"] {
        reset_property LOCK_PINS $C
        catch {set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $C}
    }
}

proc disable_drc {} {
    #set_msg_config -severity ERROR -suppress -quiet
    set SLICE_DRC [list "DRC RTSTAT-11 DRC DXSTAT-3"]
    set_property IS_ENABLED 0 [get_drc_checks $SLICE_DRC]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ DPCA"]
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
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ MDRV"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ NDRV"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ PDIL"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ UTLZ"]
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ THRU"]

}



proc tcl_drc_pips_reg_pins {} {
    set idx 0
    foreach C [get_cells -filter "PRIMITIVE_SUBGROUP==SDR"] {
        foreach PS [list "CE" "CLR" "S" "R"] {
            set P [get_pins $C/$PS]
            if {$P != ""} {
                if {[get_property IS_CONNECTED [get_pins $P]] == 1} {
                    disconnect_net -objects [get_pins $P]
                }
                set N [create_net "fuzz_pin.$idx"]
                connect_net -objects [get_pins $P] -net $N
                set sites [get_sites -filter "SITE_TYPE==SLICEL && PRIMITIVE_COUNT==0"]
                set index [expr {int(rand() * [llength $sites])}]
                set S [lindex $sites $index]
                create_cell -reference FDSE "fuzz.FDCE.$idx"
                connect_net -objects "fuzz.FDCE.$idx/Q" -net $N
                place_cell [get_cells "fuzz.FDCE.$idx"] [get_sites $S]
            }
            incr idx
        }
        
    }
}

proc tcl_drc_ff_clk {} {
    foreach N [get_nets -filter "ROUTE_STATUS==CONFLICTS"] {
        set S [get_sites -of_objects $N -filter "SITE_TYPE==SLICEL"]
        if {$S != ""} {
            set_property MANUAL_ROUTING SLICEL $S
            reset_property SITE_PIPS $S
            reset_property MANUAL_ROUTING $S
        }
    }
}


proc tcl_drc_lut_pins {} {
    # Route Design an Extra Time
    if {[llength [get_cells -filter "REF_NAME==LUT6"]] !=0 } { 
        # Lock all pins
        reset_property LOCK_PINS [get_cells -filter "REF_NAME==LUT6"]
        set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells -filter "REF_NAME==LUT6"]
        set site_type [get_property MANUAL_ROUTING [get_sites -of_objects [lindex [get_cells -filter "REF_NAME==LUT6"] 0]]]
        # Tie all inputs to the output
        foreach C [get_cells -filter "REF_NAME==LUT6"] {
            create_cell -reference GND "GND_$C"
            create_net "net_$C"
            #reset_property MANUAL_ROUTING [get_sites -of_objects $C]
            #set_property ALLOW_COMBINATORIAL_LOOPS TRUE [get_nets [get_nets "net_$C"]]
            #connect_net -net [get_nets "net_$C"] -objects [get_pins -of_objects $C -filter "DIRECTION =~ OUT"]
            connect_net -net [get_nets "net_$C"] -objects [get_pins -of_objects $C -filter "DIRECTION =~ IN"]
            connect_net -net [get_nets "net_$C"] -objects [get_pins -of_objects [get_cells "GND_$C"] -filter "DIRECTION =~ OUT"]
        }
        catch {[route_design -physical_nets]}
    }

}

proc refresh_cell {ref_name} {
    set c_list [get_cells -filter "REF_NAME==$ref_name"]
    foreach C $c_list {
        if {[get_property LOC $C] != ""} {
            set loc [get_property LOC $C]
            set bel [get_property BEL $C]
            set f0 1
            unplace_cell $C
            place_cell $C "$loc/$bel"
        }
    }
    if {[llength $c_list] != 0} { catch {[route_design]} }
    puts "done refresh"
}

proc tcl_drc_bram_write {} {
    refresh_cell "RAMB18E1"
    refresh_cell "RAMB36E1"
    refresh_cell "FIFO36E1"
}

proc tcl_drc_ultra_latch {} {
    set cell_list [get_cells -filter "REF_NAME==LDCE || REF_NAME==LDPE"]
    if {[llength $cell_list] > 0} {
        catch {[route_design -physical_nets -unroute]}
    }
}

proc tcl_drc_bscan {} {
    set count 0
    if {[llength [get_cells -of_objects [get_sites -filter "SITE_TYPE==BSCAN"]]] > 0} {
        for {set i 0} {$i < [llength [get_sites -filter "SITE_TYPE==BSCAN"]]} {incr i} { 
            set S [lindex [get_sites -filter "SITE_TYPE==BSCAN"] $i]  
            if {[get_cells -of_objects $S] != ""} {
                set cell [get_cells -of_objects $S]
                set jtag_val [expr {$i + 1}]
                set_property JTAG_CHAIN $jtag_val $cell
                create_net -net "bscan_net_$i"
                connect_net -net "bscan_net_$i" -objects [get_pins -of_objects $cell -filter "NAME=~*TDI"]
                connect_net -net "bscan_net_$i" -objects [get_pins -of_objects $cell -filter "NAME=~*TDO"]
            }
        }
    }
}

proc tcl_ff_iob {} {
    foreach C [get_cells] {
        set ref [get_property REF_NAME $C]
        if { [lsearch -exact [list "FDSE" "FDRE" "FDPE" "FDCE" "LDCE" "LDPE" "LDCE"] $ref] != -1 } {
            set_property IOB TRUE $C
        }
    }
}

proc tcl_drc_lut_rams {ref bel site} {
    if {[get_property SITE_TYPE $site] == "SLICEM"} {
        if { [lsearch -exact [list "kintexu" "kintexuplus" "zynquplus"] $::family] != -1 } {
            if { [lsearch -exact [list "RAMD32" "RAMD64E" "RAMS32" "RAMS64E1" "RAMS64E"] $ref] != -1 } {
                if {($bel == "H6LUT") || ($bel == "H5LUT")} {
                    create_cell -reference $ref "lutram_H_$site"
                    place_cell [get_cells "lutram_H_$site"] "$site/H6LUT"
                }
            }
        } else {
            if {($ref == "RAMD32" ) || ( $ref=="RAMD64E") } {
                if {($bel == "A6LUT") || ($bel == "B6LUT") || ($bel == "B5LUT") || ($bel == "A5LUT")} {
                    create_cell -reference $ref "lutram_D_$site"
                    create_cell -reference $ref "lutram_C_$site"
                    place_cell [get_cells "lutram_D_$site"] "$site/D6LUT"
                    place_cell [get_cells "lutram_C_$site"] "$site/C6LUT"
                } elseif {($bel == "C6LUT") || ($bel == "C5LUT")} {
                    create_cell -reference $ref "lutram_D_$site"
                    place_cell [get_cells "lutram_D_$site"] "$site/D6LUT"
                }
            } elseif {($ref == "RAMS32") || ($ref=="RAMS64E") || ($ref=="RAMS64E")} {
                if {($bel == "D6LUT") || ($bel == "D5LUT")} {
                    create_cell -reference $ref "lutram_D_$site"
                    place_cell [get_cells "lutram_D_$site"] "$site/D6LUT"
                }
            }
        }
    }
}

proc tcl_drc_lut_ram_pins {} {
    set count 0
    foreach S [get_sites -filter "SITE_TYPE==SLICEM"] {
        set cells [get_cells -of_objects $S -filter "REF_NAME=~RAM*"]
        if {[llength $cells] != 0} {
            set D6cell [get_cells -of_objects [get_bels "$S/D6LUT"]]
            if {$D6cell == ""} {
                set D6cell [get_cells -of_objects [get_bels "$S/D5LUT"]]
            }
            set ref [get_property REF_NAME $D6cell]
            set o_pin [get_pins "$D6cell/O"]
            create_net -net "lutram_$count"
            if {($ref == "RAMD32" ) || ( $ref=="RAMD64E") } {
                set addr_pins [get_pins -of_objects [get_cells -of_objects $S ] -filter "REF_PIN_NAME=~RADR*"]
            } elseif {($ref == "RAMS32") || ($ref=="RAMS64E")} {
                set addr_pins [get_pins -of_objects [get_cells -of_objects $S ] -filter "REF_PIN_NAME=~ADR*"]
            }
            connect_net -net "lutram_$count" -objects $addr_pins
            connect_net -net "lutram_$count" -objects $o_pin
            incr count
        }
    }
}


proc tcl_drc_lut_routethru_eqn {} {
    catch { set_property INIT 64'hFFFFFFFFFFFFFFFF [get_cells -filter "REF_NAME==LUT6"]}
    puts "tcl lut routethru"
}

proc tcl_drc_idelay {} {
    if {[llength [get_cells -filter "REF_NAME==IDELAY"]] !=0 } {
        set ctrl_tile_list [get_tiles -filter "TYPE =~ HCLK_IOI3"]
        set count 0
        foreach T $ctrl_tile_list {
            set S [get_sites -of_objects $T -filter "SITE_TYPE =~ IDELAYCTRL"]
            create_cell -reference IDELAYCTRL "I_$count"
            place_cell "I_$count" $S
            incr count
        }
    }
}


# IO FIXES

proc tcl_drc_fix_iobuf_placement {} {
    set port_count 0
    set s_list [list]
    foreach cell [get_cells -filter "PRIMITIVE_GROUP==IO"] {
        set S [get_sites -of_objects $cell]
        if { [lsearch -exact $s_list $S] == -1 } {
            lappend s_list $S
            puts $S
            puts [report_property $S]
            create_net "port_net_$port_count"
            set pack_pin [get_package_pins -of_objects $S]
            if {[string first "obuf" [get_property PRIMITIVE_SUBGROUP [get_cells $cell]]] != -1} {
                create_port "port_$port_count" -direction OUT 
                place_port "port_$port_count" $pack_pin
                connect_net -net "port_net_$port_count" -objects "$cell/O"
                connect_net -net "port_net_$port_count" -objects [get_ports "port_$port_count"]
                # For some reason this fails on IOB33S site types? for OBUFDS primitives
                set_property IOSTANDARD LVCMOS18 [get_ports "port_$port_count"]
            } elseif {[string first "ibuf" [get_property PRIMITIVE_SUBGROUP [get_cells $cell]]] != -1} {
                create_port -direction IN "port_$port_count"
                place_port "port_$port_count" $pack_pin
                connect_net -net "port_net_$port_count" -objects "$cell/I"
                connect_net -net "port_net_$port_count" -objects [get_ports "port_$port_count"]
                set_property IOSTANDARD LVCMOS25 [get_ports "port_$port_count"]
            }
            set_property DONT_TOUCH 1 [get_nets "port_net_$port_count"] 
            incr port_count
        }
    }
}


proc tcl_drc_diff_pairs {} {
    set port_count 0
    set io_ds_list [list "IBUFDS_DIFF_OUT" "IBUFDS_IBUFDISABLE_INT" "OBUFDS" "IBUFDS" "OBUFTDS" "IBUFDS_INTERMDISABLE_INT" "IBUFDS_GTE2" "OBUFTDS_DCIEN"]
    foreach cell [get_cells -filter "PRIMITIVE_GROUP==IO"] {
        set ref [get_property REF_NAME $cell]
        set site [get_sites -of_objects $cell]
        set tile [get_tiles -of_objects $site]
        foreach S [get_sites -of_objects $tile] {
            if {$S!=$site } {
                set pack_pin [get_package_pins -of_objects $S]
            }
        }
        if { [lsearch -exact $io_ds_list $ref] != -1 } {
            create_net "port_ds_net_$port_count"
            if {[string first "obuf" [get_property PRIMITIVE_SUBGROUP [get_cells $cell]]] != -1} {
                create_port -direction OUT "port_ds_$port_count"
                connect_net -net "port_ds_net_$port_count" -objects "$cell/OB"
                connect_net -net "port_ds_net_$port_count" -objects [get_ports "port_ds_$port_count"]
                place_port "port_ds_$port_count" $pack_pin
                set_property IOSTANDARD DIFF_SSTL15 [get_ports "port_ds_$port_count"]
            } elseif {[string first "ibuf" [get_property PRIMITIVE_SUBGROUP [get_cells $cell]]] != -1} {
                create_port -direction IN "port_ds_$port_count"
                place_port "port_ds_$port_count" $pack_pin
                connect_net -net "port_ds_net_$port_count" -objects "$cell/IB"
                connect_net -net "port_ds_net_$port_count" -objects [get_ports "port_ds_$port_count"]
                set_property IOSTANDARD DIFF_SSTL15 [get_ports "port_ds_$port_count"]
            }
            incr port_count
        }
        
    }
}



proc tcl_fuzz_pins {} {
    set idx 0
    foreach C [get_cells] {
        if {[get_property LOC $C] != ""} {
            set loc [get_property LOC $C]
            set bel [get_property BEL $C]
            set ST [get_property MANUAL_ROUTING [get_sites -of_objects $C]]
            set in_pins [get_pins -of_objects $C -filter "DIRECTION==IN"]
            reset_property MANUAL_ROUTING [get_sites -of_objects $C]
            unplace_cell $C
            if {[llength $in_pins] > 30} {
                set loop_count 20
            } else {
                set loop_count 1
            }
            set lp 0
            set index_ls [list ]
            while {$lp < $loop_count} {
                set index [expr {int(rand() * [llength $in_pins])}]
                set P [lindex $in_pins $index]
                if { [lsearch -exact $index_ls $index] != -1 } {
                    continue
                }
                lappend index_ls $index
                if {[catch {[get_pins $P]}] == 0} {
                    continue
                }
                if {[catch {set_property IS_INVERTED 1 [get_pins $P]}] == 0} {
                    continue
                }

                if {[get_property IS_CONNECTED [get_pins $P]] == 1} {
                    disconnect_net -objects [get_pins $P]
                }

                if {[string first "/CK" $P] != -1} {
                    continue
                }
                if {[string first "/CLK" $P] != -1} {
                    continue
                }
                set N [create_net "fuzz_pin.$idx"]
                connect_net -objects [get_pins $P] -net $N
                set srcs [list "VCC" "GND"]
                set index [expr {int(rand() * [llength $srcs])}]
                set src [lindex $srcs $index]
                if {$src == "VCC"} {
                    create_cell -reference VCC "fuzz.VCC.$idx"
                    connect_net -objects "fuzz.VCC.$idx/P" -net $N
                } else {
                    create_cell -reference GND "fuzz.GND.$idx"
                    connect_net -objects "fuzz.GND.$idx/G" -net $N
                }
                incr lp
                incr idx
            }
            place_cell $C "$loc/$bel"
            set_property MANUAL_ROUTING $ST [get_sites -of_objects $C]
        }
        
    }
    foreach N [get_nets -filter "NAME=~fuzz_pin* && TYPE==GROUND"] {
        foreach RB [get_bels -include_routing_bels -of_objects $N] {
            if {[string first "/CLKINV" $RB] != -1} {
                disconnect_net -net $N -objects [get_pins -of_objects $N]
                remove_net $N
            }
        }
    }
}



proc tcl_drc_invalid_io_sitepips {ref ST} {
    set_property IS_ENABLED 0 [get_drc_checks [list "DRC PLCK-87" "DRC BIVRU-1"]]
    ## When IBUFDISABLE is being manually set, the manual routing property needs to be reset
     if { [lsearch -exact [list "IOB33" "IOB33S" "IOB33M"] $ST] != -1 } {
        if { [lsearch -exact [list "IBUF" "IBUF_INTERMDISABLE" "IBUF_IBUFDISABLE"] $ref] == -1 } {
            foreach S [get_sites -filter "MANUAL_ROUTING != \"\" "] {
                reset_property SITE_PIPS $S
            }
        } else {
            set site_list [list]
            foreach S [get_sites -filter "MANUAL_ROUTING != \"\" "]  {
                reset_property MANUAL_ROUTING $S
                lappend site_list $S
            }
            refresh_cell IBUF
            refresh_cell IBUF_INTERMDISABLE
            refresh_cell IBUF_IBUFDISABLE
            foreach S $site_list {
                set_property MANUAL_ROUTING $ST $S
            }
            # Remove problem site pips, these two don't work plus aren't required
            foreach S $site_list {
                set SP [get_property SITE_PIPS $S]
                foreach B [list "DIFFI_INUSED" "PADOUTUSED"] {
                    set idx [lsearch $SP $B]
                    set SP [lreplace $SP $idx $idx]
                }
                set_property SITE_PIPS $SP $S
            }
        }
    }
    bufgctrl_pins
}



#ERROR: [DRC InOutTerm-3] IN_TERM/OUT_TERM unsupported value: xc7a25tlcsg325-2L devices do not support an IN_TERM value of UNTUNED_SPLIT_25, but port port_0 uses this value.

proc tcl_drc_port_standards { site_type } {
    set_property IS_ENABLED 0 [get_drc_checks [list "DRC PLCK-87" "DRC BIVRU-1"]]
    set io_list [list "HSTL_I" "HSTL_I_18" "HSTL_II" "HSTL_II_18" "SSTL15" "SSTL15_R" "SSTL18_I" "SSTL18_II" "SSTL135" "SSTL135_R"]
    set sing_list [list "LVTTL" "LVCMOS33" "LVCMOS25" "LVCMOS18" "LVCMOS15" "LVCMOS12" "HSUL_12" "HSTL_I" "HSTL_II" "HSTL_I_18" "HSTL_II_18" "SSTL18_I" "SSTL18_II" "SSTL15" "SSTL15_R" "SSTL135" "SSTL135_R" "PCI33_3" "MOBILE_DDR"]
    set diff_list [list "DIFF_HSTL_I" "DIFF_HSTL_II" "DIFF_HSTL_I_18" "DIFF_HSTL_II_18" "DIFF_SSTL18_I" "DIFF_SSTL18_II" "DIFF_SSTL15" "DIFF_SSTL15_R" "DIFF_SSTL135" "DIFF_SSTL135_R" "DIFF_HSUL_12" "DIFF_MOBILE_DDR" "BLVDS_25" "LVDS_25" "RSDS_25" "TMDS_33" "MINI_LVDS_25" "PPDS_25"]
    set split_list [list "UNTUNED_SPLIT_25" "UNTUNED_SPLIT_75"]
    foreach P [get_ports] {
        set standard [get_property IOSTANDARD $P]
        set S [get_sites -of_objects $P]

        if {($standard == "LVCMOS33") || ($standard == "LVCMOS25") || ($standard == "LVCMOS15") || ($standard == "LVCMOS12")} {
            if {[get_property DRIVE $P] == 24} {
                set_property DRIVE 4 $P
            }
        }
        if {($standard == "LVCMOS12")} {
            if {[get_property DRIVE $P] == 16} {
                set_property DRIVE 4 $P
            }
        }


        if {$S != "" } {
            set ST [get_property SITE_TYPE $S]
            if { [lsearch -exact [list "IOB33S" "IOB33M"] $site_type] == -1 } {
                if {[get_property DIFF_TERM $P] == 1} {
                    set_property DIFF_TERM 0 $P
                }
                #if { [lsearch -exact $diff_list $standard] == -1 } {
                #    set possible_index [llength $sing_list]
                #    set random_index [expr {int(rand()*$possible_index)}]
                #    set_property IOSTANDARD [lindex $sing_list $random_index] [get_ports]
                #}
            } else {
                #set possible_index [llength $diff_list]
                #set random_index [expr {int(rand()*$possible_index)}]
                set ports [get_ports -of_objects $S]
                #set_property IOSTANDARD [lindex $diff_list $random_index] [get_ports]
                set_property IN_TERM NONE $ports
                set_property DIFF_TERM 1 $ports
            }
            set standard [get_property IOSTANDARD $P]
            if { [lsearch -exact $io_list $standard] == -1 } {
                set_property IN_TERM NONE $P
            }
            set in_term [get_property IN_TERM $P]
            if { [lsearch -exact $split_list $in_term] != -1 } {
                set_property IN_TERM NONE $P
            } 
            if {[get_property DIRECTION $P] == "OUT"} {
                set_property IN_TERM NONE $P
            }
        }
    }
}


proc bufgctrl_pins {} {
    if {[llength [get_cells -filter "REF_NAME==BUFGCTRL"]] > 0} {
        if {[llength [get_nets -filter "ROUTE_STATUS==CONFLICTS"]] > 0} {
            disconnect_net -objects [get_pins -of_objects [get_nets -of_objects [get_cells -filter "REF_NAME==BUFGCTRL"]]]
        }
    }
}




# PROPERTY FIXES:


proc sprop { name val obj } {
    puts "setting.$name.$val.$obj"
	set_property $name $val $obj
}
proc prop { name obj } {
	puts "returning $obj.$name: [get_property $name $obj]"
	return [get_property $name $obj]
}
proc assert { name val obj } {
    puts "assrt.$name.$val.$obj"
	return [assertf $name == $val $obj]
}
proc assertn { name val obj } {
	return [assertf $name != $val $obj]
}
proc assertf { name f val obj } {
	return [expr {[prop $name $obj]} $f {$val}]
}
proc deny { name val obj } {
	return [assertf $name != $val $obj]
}
proc and args {
	set ob [lindex $args end]
	set params [lreplace $args end end]
	foreach p $params {
		if {![{*}$p $ob]} {
			return 0
		}
	}
	return 1
}
proc T obj {
	return true
}
proc tcl_fix_properties { site_type } {
	set fixes {
	{"RAMB36E1"
		{{{assert EN_ECC_READ TRUE} {sprop RAM_MODE SDP}}
		 {{assert EN_ECC_WRITE TRUE} {sprop RAM_MODE SDP}}
		 {{and
			{assert RAM_MODE SDP}
			{assert DOA_REG 1}} {sprop DOB_REG 1}}
		 {{and
			{assert RAM_MODE SDP}
			{assert DOB_REG 1}} {sprop DOA_REG 1}}
		 {{and
			{assert RAM_MODE SDP}
			{assert RSTREG_PRIORITY_A REGCE}} {sprop RSTREG_PRIORITY_B REGCE}}
		 {{and
			{assert RAM_MODE SDP}
			{assert RSTREG_PRIORITY_B REGCE}} {sprop RSTREG_PRIORITY_A REGCE}}
		 {{and
			{assert RAM_MODE SDP}
			{assert WRITE_MODE_A NO_CHANGE}} {sprop WRITE_MODE_A WRITE_FIRST}}
		 {{and
			{assert RAM_MODE SDP}
			{assert WRITE_MODE_B NO_CHANGE}} {sprop WRITE_MODE_B WRITE_FIRST}}
		 {{assert RAM_MODE SDP} {sprop RAM_EXTENSION_A NONE}}
		 {{assert RAM_MODE SDP} {sprop RAM_EXTENSION_B NONE}}
		 {{assert RAM_EXTENSION_A UPPER} {sprop READ_WIDTH_A 1}}
		 {{assert RAM_EXTENSION_A UPPER} {sprop WRITE_WIDTH_A 1}}
		 {{assert RAM_EXTENSION_B UPPER} {sprop READ_WIDTH_B 1}}
		 {{assert RAM_EXTENSION_B UPPER} {sprop WRITE_WIDTH_B 1}}
		 {{assert RAM_EXTENSION_A LOWER} {sprop READ_WIDTH_A 1}}
		 {{assert RAM_EXTENSION_A LOWER} {sprop WRITE_WIDTH_A 1}}
		 {{assert RAM_EXTENSION_B LOWER} {sprop READ_WIDTH_B 1}}
		 {{assert RAM_EXTENSION_B LOWER} {sprop WRITE_WIDTH_B 1}}}}
	{"RAMB18E1"
		{{{and
			{assert RAM_MODE SDP}
			{assert DOA_REG 1}} {sprop DOB_REG 1}}
		 {{and
			{assert RAM_MODE SDP}
			{assert DOB_REG 1}} {sprop DOA_REG 1}}
		 {{and
			{assert RAM_MODE SDP}
			{assert RSTREG_PRIORITY_A REGCE}} {sprop RSTREG_PRIORITY_B REGCE}}
		 {{and
			{assert RAM_MODE SDP}
			{assert RSTREG_PRIORITY_B REGCE}} {sprop RSTREG_PRIORITY_A REGCE}}
		 {{and
			{assert RAM_MODE SDP}
			{assert WRITE_MODE_A NO_CHANGE}} {sprop WRITE_MODE_A WRITE_FIRST}}
		 {{and
			{assert RAM_MODE SDP}
			{assert WRITE_MODE_B NO_CHANGE}} {sprop WRITE_MODE_B WRITE_FIRST}}}}
	{"FIFO36E1"
		{{{assert EN_SYN 1} {sprop FIRST_WORD_FALL_THROUGH 0}}
		 {{assert EN_SYN 0} {sprop DO_REG 1}}
		 {{assert EN_ECC_READ 1} {sprop DATA_WIDTH 72}}
		 {{assert EN_ECC_WRITE 1} {sprop DATA_WIDTH 72}}}}
	{"FIFO18E1"
		{{{assert EN_SYN 1} {sprop FIRST_WORD_FALL_THROUGH 0}}
		 {{assert EN_SYN 0} {sprop DO_REG 1}}}}
	{"DSP48E1"
		{{{assertn USE_SIMD ONE48} {sprop USE_MULT NONE}}
         {{assert USE_MULT NONE} {sprop MREG 0}}
         {{assert AREG 0} {sprop ACASCREG 0}}
		 {{assert BREG 0} {sprop BCASCREG 0}}
         {{assert AREG 1} {sprop ACASCREG 1}}
         {{assert BREG 1} {sprop BCASCREG 1}}
		 {{assert ACASCREG 0} {sprop AREG 0}}
		 {{assert BCASCREG 0} {sprop BREG 0}}
		 {{assert ACASCREG 2} {sprop AREG 2}}
		 {{assert BCASCREG 2} {sprop BREG 2}}}}
	{".*FIFO"
		{{{assert SYNCHRONOUS_MODE TRUE} {sprop SYNCHRONOUS_MODE FALSE}}}}
	{"OSERDESE2"
		{{{assertf DATA_WIDTH > 4} {sprop TRISTATE_WIDTH 1}}
		 {{assert DATA_RATE_TQ DDR} {sprop TRISTATE_WIDTH 4}}
		 {{assert DATA_RATE_TQ SDR} {sprop TRISTATE_WIDTH 1}}
		 {{assert DATA_RATE_TQ BUF} {sprop TRISTATE_WIDTH 1}}}}
		 }
	foreach C [get_cells] {
		foreach E $fixes {
			if {[regexp [lindex $E 0] [prop REF_NAME $C]]} {
				foreach I [lindex $E 1] {
                    puts FIXING:
					puts "{{*}[lindex $I 0] $C} = [{*}[lindex $I 0] $C]"
					if {[{*}[lindex $I 0] $C]} {
						{*}[lindex $I 1] $C
					}
				}
			}
		}
	}
    drc_fifo_range
    tcl_drc_port_standards $site_type
    bufgctrl_pins
}


proc drc_fifo_range {} {
    #UG 473 - Table 2-8
    foreach C [get_cells -filter "REF_NAME==FIFO36E1 || REF_NAME==FIFO18E1"] {
        # THIS IS MESSING UP ALMOST_EMPTY - When true, the offset is 1 greater than the bel property?
        set_property FIRST_WORD_FALL_THROUGH 0 $C
        # THIS IS MESSING UP ALMOST_FULL - When false, the offset is 1 less than the bel property?
        set_property EN_SYN 1 $C
        # FIX THE ABOVE LINES
        if {[get_property REF_NAME $C] == "FIFO36E1"} {
            set_property IS_RSTREG_INVERTED 1'b0 $C 
            if {[get_property EN_SYN $C] == 0} {
                set min 5
                if {[get_property DATA_WIDTH $C] == 4} {
                    set max 8186
                } elseif {[get_property DATA_WIDTH $C] == 9} {
                    set max 4090
                } elseif {[get_property DATA_WIDTH $C] == 18} {
                    set max 2042
                } elseif {[get_property DATA_WIDTH $C] == 36} {
                    set max 1018
                } elseif {[get_property DATA_WIDTH $C] == 72} {
                    set max 506
                }
                set f_max [expr {$max-1}]
                set f_min [expr {$min-1}]
                if {[get_property FIRST_WORD_FALL_THROUGH $C] == 1} {
                incr max
                incr min
                }
                
            } else {
                set min 1
                if {[get_property DATA_WIDTH $C] == 4} {
                    set max 8190
                } elseif {[get_property DATA_WIDTH $C] == 9} {
                    set max 4094
                } elseif {[get_property DATA_WIDTH $C] == 18} {
                    set max 2046
                } elseif {[get_property DATA_WIDTH $C] == 36} {
                    set max 1022
                } elseif {[get_property DATA_WIDTH $C] == 72} {
                    set max 510
                }
                set f_max $max
                set f_min $min
            }
        } elseif {[get_property REF_NAME $C] == "FIFO18E1"} {
            set_property IS_RSTREG_INVERTED 1'b0 $C 
            if {[get_property EN_SYN $C] == 0} {
                set min 5
                if {[get_property DATA_WIDTH $C] == 4} {
                    set max 4090
                } elseif {[get_property DATA_WIDTH $C] == 9} {
                    set max 2042
                } elseif {[get_property DATA_WIDTH $C] == 18} {
                    set max 1018
                } elseif {[get_property DATA_WIDTH $C] == 36} {
                    set max 506
                }
                set f_max [expr {$max-1}]
                set f_min [expr {$min-1}]
                if {[get_property FIRST_WORD_FALL_THROUGH $C] == 1} {
                incr max
                incr min
                }
            } else {
                set min 1
                if {[get_property DATA_WIDTH $C] == 4} {
                    set max 4094
                } elseif {[get_property DATA_WIDTH $C] == 9} {
                    set max 2046
                } elseif {[get_property DATA_WIDTH $C] == 18} {
                    set max 1022
                } elseif {[get_property DATA_WIDTH $C] == 36} {
                    set max 510
                }
                set f_max $max
                set f_min $min
            }
        }
        
        set empty [get_property ALMOST_EMPTY_OFFSET $C]
        set empty [lindex [split $empty "h"] end]
        scan $empty %x empty
        if {$empty < $min} {
            set_property ALMOST_EMPTY_OFFSET $min $C 
        } elseif {$empty > $max} {
            set new_empty [expr $empty & $max]
            set new_empty [format %X $new_empty]
            set_property ALMOST_EMPTY_OFFSET $new_empty $C 
        }
        set full [get_property ALMOST_FULL_OFFSET $C]
        set full [lindex [split $full "h"] end]
        scan $full %x full
        if {$full < $f_min} {
            set_property ALMOST_FULL_OFFSET $f_min $C 
        } elseif {$full > $f_max} {
            set new_full [expr $full & $f_max]
            set new_full [format %X $new_full]
            set_property ALMOST_FULL_OFFSET $new_full $C 
        }
    }
}