



set checkpoint_file [lindex $argv 0] 
set bitstream_file [lindex $argv 1] 
set ft_file [lindex $argv 2] 
set input_tiles [lindex $argv 3] 

open_checkpoint $checkpoint_file

source ../../record_device.tcl

proc disable_drc {} {
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
    set_property IS_ENABLED 0 [get_drc_checks -filter "GROUP =~ HDOOC"]
    set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
    set_property SEVERITY {Warning} [get_drc_checks UCIO-1]
    
    set ::family [get_property family [get_parts -of_objects [get_projects]]]
    if {[string first "uplus" $::family] == -1} {
        set_property CFGBVS VCCO [current_design]
        set_property CONFIG_VOLTAGE 3.3 [current_design]
    }
	set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
	set_property BITSTREAM.General.UnconstrainedPins {Allow} [current_design]

}

disable_drc
place_design
route_design
write_bitstream $bitstream_file -force
puts $input_tiles
foreach T $input_tiles {
    record_device_benchmark "$ft_file$T.ft" $T
}






