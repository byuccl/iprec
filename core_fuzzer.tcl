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

# given an IP block design cell, it returns a json dictionary of every property, with the possible values each property can hold
proc get_prop_dict { ip} {
    set C [get_ips]
    set f [open "data/$ip/props.txt" w]
    set accum [dict create]
    foreach P [list_property $C -regexp "CONFIG.*"] {
        puts $P
        catch {[set_property -dict [list $P {12300} ]  $C > "data/$ip/out.txt" ]}
        set fp [open "data/$ip/out.txt" r]
        set file_data [read $fp]
        set data [split $file_data "\n"]
        foreach line $data {
            if {[string first "out of the range \(" $line] != -1} {
                set range [lindex [split $line "range \("] end]

                set range [string map [list ")" ""] $range]
                puts $f "$P:$range"
                dict set accum $P $range
                break
            } elseif {[string first "Valid values are - " $line] != -1} {
                set range [lindex [split $line "-"] end]
                set range [string map [list " " ""] $range]
                set vals [split $range ","]
                dict set accum $P $vals
                #puts $f "$P:$range"
                break
            } elseif {[string first "Invalid boolean value" $line] != -1} {
                dict set accum $P [list "true" "false"]
                #puts $f "$P:Boolean"
                break
            } elseif {[string first "disabled parameter" $line] != -1} {
                puts $f "$P:Disabled"
                break
            }
        }
        close $fp
    } 
    puts $accum
    close $f

    file delete -force "data/$ip/out.txt"
    file delete -force "data/$ip/props.txt"
    set f [open "data/$ip/properties.json" w]
    puts $f "\{\"PROPERTY\": \["
    set i 0
    dict for {property values} $accum {
        if {$i} { puts $f ","}
        incr i
        puts $f "\{"
        puts $f "\"name\":\"$property\","
        if {[string first "," $values] == -1} {
            puts $f "\"type\":\"ENUM\","
            puts $f "\"values\":\["
            set j 0
            foreach V $values {
                if {$j} { puts $f ","}
                incr j
                puts $f "\"$V\""
            }
            puts $f "\]"
        } else {
            puts $f "\"type\":\"INTEGER\","
            set min [lindex [split $values ","] 0]
            set max [lindex [split $values ","] 1]
            puts $f "\"min\":$min,"
            puts $f "\"max\":$max"
            
        }
        puts $f "\}"
    }
    puts $f "\]\}"
    close $f
    
    return $accum
}


# Synthesizes and Implements the design
proc synth {name ip} {
    set C [get_ips]
	set f [synth_ip $C]
    if {[catch {file rename -force $f "data/$ip/$name.dcp"}] == 0} {
        close_project
        open_checkpoint "data/$ip/$name.dcp"
        opt_design
        catch { place_design }
        catch { route_design }
        write_checkpoint "data/$ip/$name.dcp" -force
    }
    close_project
}


# Creates a project with the single instance of the IP
proc create_design { ip part} {
    file mkdir "data"
    file mkdir "data/$ip"
    set_part $part -quiet
    create_ip -vlnv $ip -module_name c_accum_0
}

# Sets the IP cell's property to the given value (has to be the only IP in the design)
proc set_ip_property { P V} {
    catch { set_property $P $V [get_ips ] }
}

# Tests the synthesis flow
proc test {} {
    set ip xilinx.com:ip:c_accum:12.0
    set name default
    set part xc7a100ticsg324-1L
    create_design $ip $part
    synth $name $ip
}

