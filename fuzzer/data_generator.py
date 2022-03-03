
import json
import os
import argparse
import sys
import random
from multiprocessing import Pool

fj = open("vivado_db/primitive_dict.json")
primitive_dict = json.load(fj) 
fj.close()
fj = open("vivado_db/bel_dict.json")
bel_dict = json.load(fj) 
fj.close()
fj = open("vivado_db/tile_dict.json")
tile_dict = json.load(fj) 
fj.close()
fj = open("vivado_db/tilegrid.json")
tilegrid = json.load(fj) 
fj.close()

tile_type = ""
ft = ""
specimen_number = 0

##================================================================================##
##                                CREATE TCL SCRIPT                               ##
##================================================================================##                  

def set_dir(folder):
    print("cd " + folder,file=ft)

def set_port_standard(io_standard):
    print("if {[get_ports] != \"\"} {",file=ft)
    print("set_property IOSTANDARD "+ io_standard + " [get_ports] }",file=ft)

def create_cell(ref,count):
    print("create_cell -reference "+ ref + " C_" + str(count),file=ft)

def create_cells(ref,name_list):
    print("create_cell -reference "+ ref + " " + name_list,file=ft)

def set_site_type(tile_type,site_index,site_type):
    print("foreach T [get_tiles -filter \"TYPE==" +tile_type+"\"] { set_property MANUAL_ROUTING " + site_type + " [lindex [get_sites -of_objects $T] "+site_index+" ]}",file=ft)
    #print("set_property SITE_PIPS [list] $site_list" ,file=ft)

def reset_site_type(tile_type,site_index):
    print("foreach T [get_tiles -filter \"TYPE==" +tile_type+"\"] { reset_property MANUAL_ROUTING [lindex [get_sites -of_objects $T] "+site_index+" ]}",file=ft)

def place_cell_str(tile,site_index,bel,count):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    return "\"C_" + str(count) + "\" " + site + "/" + bel

def place_cell(tile,site_index,bel,count):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    print("place_cell [get_cells \"C_" + str(count) + "\"] " + site + "/" + bel,file=ft)

def place_cells(cell_placement_list):
    print("place_cell " + cell_placement_list,file=ft)

def set_property(count, prop, val,primitive):
    if primitive == "PORT":
        print("catch {[set_property ", prop, val, "[get_ports \"port_" + str(count) + "\"] ]}",file=ft)
    else:
        print("catch {[set_property ", prop, val, "[get_cells \"C_" + str(count) + "\"] ]}",file=ft)

def set_property_by_loc(T, site_index, site_type, bel, prop, val,primitive):
    site = "[lindex [get_sites -of_objects [get_tiles " + T + "]] " + site_index + "]"
    if primitive == "PORT":
        cell = "[get_ports -filter \"LOC==" + site + "\"]"
    else:
        cell = "[get_cells -filter \"LOC==" + site + " && BEL== " + site_type + "." + bel + "\"]"
    print("catch {[set_property ", prop, val, cell," ]}",file=ft)

def write_checkpoint(file_name):
    print("write_checkpoint " + file_name +".dcp" + " -force",file=ft)

def init_design():
    print("if {[catch {get_designs}] == 0} { close_design }",file=ft)
    print("open_checkpoint vivado_db/init.dcp -ignore_timing",file=ft)

def open_checkpoint(file_name):
    print("if {[catch {get_designs}] == 0} { close_design }",file=ft)
    print("open_checkpoint " + file_name + ".dcp -ignore_timing",file=ft)

def lock_design():
    print("foreach C [get_cells] {",file=ft)
    print("set_property DONT_TOUCH 1 $C",file=ft)
    print("}",file=ft)

def place_design():
    print("tie_unused_pins",file=ft)
    print("set r [catch {[place_design]}]",file=ft)

def route_design():
    print("catch {[route_design]}",file=ft)
    print("if {$r == 1} { catch {[place_design]}}",file=ft)

def reroute_physical_design():
    print("catch {[route_design -unroute -physical_nets]}",file=ft)
    print("catch {[route_design -physical_nets]}",file=ft)
    print("tcl_drc_ultra_latch",file=ft)
    

def write_bitstream(file_name):
    if int(args.checkpoints) == 2:
        write_checkpoint(file_name + "backup")
        print("catch {[write_bitstream " + file_name + " -force]}",file=ft)
    elif int(args.checkpoints) == 1:
        print("if {[catch {write_bitstream " + file_name + " -force}] == 1} {",file=ft)
        print("write_checkpoint " + file_name +".dcp",file=ft)
        print("close_design",file=ft)
        print("open_checkpoint " + file_name +".dcp -ignore_timing",file=ft)
        #print("tcl_drc_invalid_io_sitepips",file=ft)
        print("catch {[write_bitstream " + file_name + " -force]}",file=ft)
        print("}",file=ft)
    else:
        print("catch {[write_bitstream " + file_name + " -force]}",file=ft)

def disable_drc():
    if int(args.drc) == 0:
        print("disable_drc",file=ft)

def create_site_pip(tile, site_index, site_pip, site_pip_value):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    print( "catch {[set_property SITE_PIPS " + site +"/" + site_pip + ":" + site_pip_value + " "+  site + "]}",file=ft)

def record_feature_file(file_name):
    global tile_type
    print("record_device " + file_name + ".ft " + tile_type,file=ft)

def create_polarity_selector(count, pin, val, tile,site_index,site_type):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    print("reset_property MANUAL_ROUTING " + site,file=ft)
    print("set p [get_pins -of_objects [get_cells \"C_" + str(count) + "\"] -filter \"NAME=~*/" + pin + "\" ]",file=ft)
    #print("set p [get_pins -of_objects [get_bel_pins -of_objects [get_bels -of_objects " + site + "] -filter \"NAME=~*" + site_pip + "\"]]",file=ft)
    print("if {$p != \"\"} {set_property IS_INVERTED " + str(val) + " $p }",file=ft)
    print("set_property MANUAL_ROUTING " + site_type + " " + site,file=ft)


def add_sources():
    print("source ../../record_device.tcl",file=ft)
    print("source ../../drc.tcl",file=ft)
    print("set ::family " + args.family,file=ft)
    print("set part_name " + args.part,file=ft)

#
#def create_tile_pip(tile,pip):
#    print("lappend pip_list " + pip)
#

##########################################################
##                     DRC CHECKS                       ##
##########################################################


##############
## DRC MAIN ##
##############

def pre_placement_drc(checkpoint,tile_list):
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    if site_type == "SLICEM":
        for tile in tile_list:
            site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
            print("tcl_drc_lut_rams " + primitive + " " + bel + " " + site,file=ft)
    print("tcl_ff_iob",file=ft)
    

def post_placement_drc(pips):
    # Fix DRC checks
    if pips == 0:
        print("tcl_drc_lut_pins",file=ft)
    else:
        print("tcl_lock_lut_pins",file=ft)
        print("tcl_drc_lut_routethru_eqn",file=ft)
    print("tcl_drc_bscan",file=ft)
    print("tcl_drc_lut_ram_pins",file=ft)
    print("tcl_drc_idelay",file=ft)
    print("tcl_drc_fix_iobuf_placement",file=ft)
    print("tcl_drc_diff_pairs",file=ft)
    # lock and implement design
    lock_design()
    if pips == 0:
        place_design()
        route_design()


def pre_bitstream_drc(primitive,site_type):
    print("tcl_fix_properties " + site_type,file=ft)
    print("tcl_drc_bram_write",file=ft)
    if "INVERTIBLE_PINS" not in primitive_dict["PRIMITIVE"][primitive]:
        print("refresh_cell " + primitive,file=ft)
    elif len(primitive_dict["PRIMITIVE"][primitive]["INVERTIBLE_PINS"]) != 0 and site_type not in ["SLICEL","SLICEM","FIFO18E1","FIFO36E1"]:
        if primitive not in ["FDSE", "FDRE", "FDPE", "FDCE", "LDCE", "LDPE", "LDCE"]:
            print("refresh_cell " + primitive,file=ft)

def pip_bitstream_drc():
    #print("removed_unused_cells",file=ft)
    #print("catch { set_property DONT_TOUCH 0 [get_cells -filter \"STATUS==UNPLACED && REF_NAME!=VCC && REF_NAME!=GND\"] }",file=ft)
    #print("catch { remove_cell [get_cells -filter \"STATUS==UNPLACED && REF_NAME!=VCC && REF_NAME!=GND\"] }",file=ft)
    #print("foreach S [get_sites -filter \"SITE_TYPE==SLICEM\"] {reset_property MANUAL_ROUTING $S}",file=ft)
    print("foreach S [get_sites -filter \"SITE_TYPE==SLICEL\"] {reset_property MANUAL_ROUTING $S}",file=ft)
    print("tcl_drc_pips_reg_pins",file=ft)
    print("tie_unused_pins",file=ft)
    print("catch {[route_design]}",file=ft)
    print("tcl_drc_bram_write",file=ft)
    print("catch { refresh_cell DSP48E1 } ",file=ft)
    print("catch { refresh_cell FDCE } ",file=ft)
    print("catch { refresh_cell LUT6 } ",file=ft)
    print("catch { refresh_cell CARRY4 } ",file=ft)
    print("catch { reset_property FIXED_ROUTE [get_nets -filter \"ROUTE_STATUS==ANTENNAS\"] }",file=ft)
    #print("catch { remove_net [get_nets -filter \"ROUTE_STATUS==CONFLICTS && NAME!~lutram*\"] }",file=ft)
    print("catch {[route_design]}",file=ft)
    #print("catch { remove_net [get_nets -filter \"ROUTE_STATUS==UNROUTED\"] }",file=ft)
    #print("catch {[route_design]}",file=ft)

    print("catch {route_design -nets [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"] }",file=ft)
    print("catch {set_property is_route_fixed 0 [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]}",file=ft)
    print("catch {set_property is_bel_fixed 0 [get_cells -of_objects [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]]}",file=ft)
    print("catch {set_property is_loc_fixed 1 [get_cells -of_objects [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]]}",file=ft)
    print("catch {route_design -nets [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]}",file=ft)
    print("catch {[route_design]}",file=ft)
    #




##########################################################
##                         FUZZER                       ##
##########################################################

def hex_values(bin_digits,value):
    #print(bin_digits,value)
    if bin_digits == 1:
        return ["'b0", "'b1"]
    if "h" in value:
        max_val = value.rsplit("h",1)[1]
        max_val = int(max_val.replace("}",""),16)
    elif "b" in value:
        max_val = value.rsplit("b",1)[1]
        max_val = int(max_val.replace("}",""),2)
    else:
        max_val =value.rsplit(" ",1)[1]
        max_val = int(max_val.replace("}",""))
    hex_vals = []
    for i in range(8):
        hex_vals.append("1"*pow(2,i) + "0"*pow(2,i))
        hex_vals.append("0"*pow(2,i) + "1"*pow(2,i))
    hex_val_repeat = [128, 128, 64, 64, 32, 32, 16, 16, 8, 8, 4, 4, 2, 2, 1, 1] 
    possible_values = ["\'b0","\'b" + ("1"*bin_digits)]
    count = 0
    inc = 0
    for i in range(len(hex_vals)):
        if i%2 == 0:
            count += 1
        sub_string = hex_vals[i]*hex_val_repeat[i]
        sub_string = sub_string[len(sub_string)-bin_digits:]
        sub_string = str(bin(int(sub_string,2) & max_val))
        possible_values.append(sub_string.replace("0b",str(bin_digits)+"\'b"))
        if (pow(2,count) > bin_digits):
            inc += 1
        if inc == 2:
            break
    return possible_values

def gen_bitstream(file_name):
    global specimen_number, fuzz_path,tile_type,args
    if len(file_name.split(".")) == 6:
        tile_type, site_index, site_type, bel, primitive, tilegrid_ext = file_name.split(".")
    else:
        tile_type, site_index, site_type, bel, primitive = file_name.split(".")
    
    
    reset_site_type(tile_type,site_index)
    pre_bitstream_drc(primitive,site_type)
    #if ("7" not in args.family):
    #    print("tcl_fuzz_pins",file=ft)
    reroute_physical_design()
    set_site_type(tile_type,site_index,site_type)
    print("tcl_drc_invalid_io_sitepips", primitive, site_type,file=ft)
    record_feature_file("data/" + fuzz_path + "/" + str(specimen_number) + "." + file_name)
    write_bitstream("data/" + fuzz_path + "/" + str(specimen_number) + "." + file_name + ".bit")
    specimen_number+=1


def get_column_list():
    global tile_type
    col_list = []
    col_tile_list = []
    for T in tilegrid:
        if tile_type == tilegrid[T]["TYPE"]:
            if tilegrid[T]["COL"] not in col_list:
                col_list.append(tilegrid[T]["COL"])
                col_tile_list.append(T)
    return col_tile_list


def random_properties(tile,site_index,site_type,bel,P):
    P_dict = primitive_dict["PRIMITIVE"][P]
    V_list = []
    for prop in P_dict["PROPERTIES"]:
        if prop not in ["IOSTANDARD"]:
            prop_type = P_dict["PROPERTIES"][prop]["PROPERTY_TYPE"]
            #print(prop, P_dict["PROPERTIES"][prop])
            if prop_type in ["hex","binary"]:
                V = random.choice(hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]))
                set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
            elif prop_type in ["double"]:
                V = "double"
                print("PROPERTY:",prop," VALUE:",P_dict["PROPERTIES"][prop]["VALUE"])
            elif prop_type in ["int"]:
                if "BIN_DIGITS" in P_dict["PROPERTIES"][prop]:
                    V = random.choice(hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]))
                    V = int(V.split("\'b")[-1],2)
                    set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
                else:
                    V = random.choice(P_dict["PROPERTIES"][prop]["VALUE"])
                    set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
            else:
                if "FILE" not in prop:
                    V = random.choice(P_dict["PROPERTIES"][prop]["VALUE"])
                    set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
            if "INVERTED" not in prop:
                V_list.append(V)
    return V_list

def fuzz_tilegrid(col_tile_list,checkpoint_list):
    global tile_type, tile_dict,ft
    print("FUZZ TILEGRID")
    if len(checkpoint_list) == 0:
        print("NO POSSIBLE PLACEMENT TILEGRID SOLVER")
        return
    checkpoint = checkpoint_list[0]
    if int(args.checkpoint_choice)==-1:
        max_prop = 0 
        for C in checkpoint_list:
            tile_type, site_index, site_type, bel, primitive = C.split(".")
            if len(primitive_dict["PRIMITIVE"][primitive]["PROPERTIES"]) >= max_prop:
                max_prop = len(primitive_dict["PRIMITIVE"][primitive]["PROPERTIES"])
                checkpoint = C
    else:
        checkpoint = checkpoint_list[int(args.checkpoint_choice)]
    for j in range(int(args.checkpoint_count)):
        if j != 0:
            checkpoint = random.choice(checkpoint_list)
        tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
        ft = open("data/" + fuzz_path + "/" + checkpoint + ".tile.tcl","w",buffering=1)
        add_sources()
        open_checkpoint("checkpoints/" + checkpoint)
        disable_drc()
        for T in col_tile_list:
            v_prev = []
            for x in range(int(args.tilegrid_count)):
                #print("X:",x)
                #print("TILEGRID: ",tile_type,site_index,site_type,bel)
                if "PORT" in tile_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]["BEL"][bel]["PRIMITIVE"].keys():
                    io_stand_list = list(io for io in primitive_dict["PRIMITIVE"]["PORT"]["PROPERTIES"]["IOSTANDARD"]["VALUE"])
                    set_port_standard(io_stand_list[x])
                    random_properties(T, site_index, site_type, bel, "PORT")
                while(1):
                    v_list = random_properties(T, site_index, site_type, bel, primitive)
                    #print("LISTING:",v_list,v_prev)
                    if v_prev == [] or v_list != v_prev:
                        v_prev = v_list
                        break
                gen_bitstream(checkpoint + ".tile")
    ft.close()

def fuzzer():
    global tile_type, ft
    db = tile_dict["TILE_TYPE"][tile_type]
    tile_list = []
    col_tile_list = get_column_list()
    for T in tilegrid:
        if tile_type == tilegrid[T]["TYPE"]:
            if "IS_BONDED" not in tilegrid[T] or tilegrid[T]["IS_BONDED"] == True:
                tile_list.append(T)
    #print("TILE_LIST_LENGTH:",len(tile_list))
    if len(tile_list) > int(args.cell_count):
        tile_list = tile_list[0: int(args.cell_count)]
    if tile_type not in ["LIOB33","LIOB33_SING","RIOB33","RIOB33_SING"]:
        for x in col_tile_list:
            if x not in tile_list:
                tile_list.append(x)

    #print(tile_list)
    cur_tile = 0
    checkpoint_list = []
    # Primitives and BELS
    for i in db["SITE_INDEX"].keys():
        if int(i) < int(args.site_count):
            for j in db["SITE_INDEX"][i]["SITE_TYPE"].keys():
                if "BEL" in db["SITE_INDEX"][i]["SITE_TYPE"][j]:
                    for B in db["SITE_INDEX"][i]["SITE_TYPE"][j]["BEL"].keys():
                        if B not in ["A5LUT","B5LUT","C5LUT","D5LUT"]:
                            for P in db["SITE_INDEX"][i]["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"].keys():
                                if P not in ["PORT"]:              
                                    checkpoint_name = tile_type+"."+i+"."+j+"."+B+"."+P 
                                    if int(args.fuzzer) == 1:
                                        ft = open("data/" + fuzz_path + "/" + checkpoint_name + ".tcl","w",buffering=1)
                                        add_sources()
                                    print(checkpoint_name)
                                    checkpoint_list.append(checkpoint_name)
                                    if os.path.exists("checkpoints/"  + checkpoint_name + ".dcp") and int(args.init) == 0:
                                        open_checkpoint("checkpoints/" + checkpoint_name)
                                        disable_drc()
                                    else:
                                        init_design()
                                        disable_drc()
                                        set_site_type(tile_type,i,j)
                                        cell_count = 0
                                        cell_name_str = ""
                                        placement_str = ""
                                        for x in range(len(tile_list)):
                                            cell_name_str += "C_" + str(cell_count) + " "
                                            placement_str += place_cell_str(tile_list[x],i,B,cell_count) + " "
                                            cell_count += 1
                                        create_cells(P, cell_name_str)
                                        pre_placement_drc(checkpoint_name,tile_list)
                                        place_cells(placement_str)
                                        #DRC Fixes
                                        post_placement_drc(0)
                                        write_checkpoint("checkpoints/" + checkpoint_name)
                                    if int(args.tilegrid) != 2:
                                        # if this is a port, fuzz the port along with each primitive
                                        if "PORT" in db["SITE_INDEX"][i]["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"].keys():
                                            for io_stand in primitive_dict["PRIMITIVE"]["PORT"]["PROPERTIES"]["IOSTANDARD"]["VALUE"]:
                                                set_port_standard(io_stand)
                                                # Run a fuzzer for the primitive combination
                                                if int(args.iterative) == 1:
                                                    fuzz_primitive(checkpoint_name,tile_list,1)
                                                randomized_method(checkpoint_name,tile_list,1)
                                                fuzz_site_pips(checkpoint_name,tile_list)
                                                randomized_method(checkpoint_name,tile_list,0)
                                                gen_bitstream(checkpoint_name)
                                        else: # Fuzzing non-IO Tiles
                                            if int(args.iterative) == 1:
                                                fuzz_primitive(checkpoint_name,tile_list,0)
                                            fuzz_site_pips(checkpoint_name,tile_list)
                                            fuzz_bel_pins(checkpoint_name,tile_list)
                                            randomized_method(checkpoint_name,tile_list,0)
                                            gen_bitstream(checkpoint_name)
                                    if int(args.fuzzer) == 1:
                                        ft.close()
    if int(args.tilegrid) != 0:
        fuzz_tilegrid(col_tile_list,checkpoint_list)

def get_next_count(cur,total,checkpoint):
    #print(cur)
    cur += 1
    if cur == total:
        gen_bitstream(checkpoint)
        cur = 0
    #print("RETURNING:",cur)
    return cur
    
def fuzz_site_pips(checkpoint,tile_list):
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    db = bel_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]
    tile_count = 0
    len_tile_list = len(tile_list)
    # hardcoded fix - CLBLL FF primitives don't work well becaues of the SRUSED site pip - just only use A6LUT, plus this is faster to do only the one
    if site_type in ["SLICEL", "SLICEM"] and bel+"."+primitive != "A6LUT.LUT6":
        return
    #open_checkpoint("checkpoints/" + checkpoint)
    pol_selector = 0
    if "SITE_PIP" in db:
        for SP in db["SITE_PIP"].keys():
            if "INV" not in SP:
                for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                    create_site_pip(tile_list[tile_count],site_index,SP,V)
                    tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
            elif "CLK" in SP:
                if tile_type not in ["BRAM_L","BRAM_R"]:
                    for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                        create_site_pip(tile_list[tile_count],site_index,SP,V)
                        tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
    #gen_bitstream(checkpoint)

def fuzz_bel_pins(checkpoint,tile_list):
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    db = bel_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]
    tile_count = 0
    len_tile_list = len(tile_list)
    #open_checkpoint("checkpoints/" + checkpoint)
    pol_selector = 0
    if "SITE_PIP" in db:
        for SP in db["SITE_PIP"].keys():
            if "INV" not in SP:
                for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                    create_site_pip(tile_list[tile_count],site_index,SP,V)
                    tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
            elif "CLK" in SP:
                if tile_type not in ["BRAM_L","BRAM_R"]:
                    for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                        create_site_pip(tile_list[tile_count],site_index,SP,V)
                        tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
    #gen_bitstream(checkpoint)


def fuzz_primitive(checkpoint,tile_list,is_port):
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    if is_port == 1:
        primitive="PORT"
    count = len(tile_list)
    cell_count = 0
    P_dict = primitive_dict["PRIMITIVE"][primitive]
    # Iterative Brute Force Method
    for prop in P_dict["PROPERTIES"]:
        if prop not in ["IOSTANDARD"]:
            prop_type = P_dict["PROPERTIES"][prop]["PROPERTY_TYPE"]
            if prop_type in ["hex","binary"]:
                for V in hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]):
                    set_property(cell_count,prop,V,primitive)
                    cell_count = get_next_count(cell_count,count,checkpoint)
            elif prop_type in ["double"]:
                print("PROPERTY:",prop," VALUE:",P_dict["PROPERTIES"][prop]["VALUE"])
            elif prop_type in ["int"]:
                if "BIN_DIGITS" in P_dict["PROPERTIES"][prop]:
                    for V in hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]):
                        print(V,prop)
                        V = int(V.split("\'b")[-1],2)
                        set_property(cell_count,prop,V,primitive)
                        cell_count = get_next_count(cell_count,count,checkpoint)
                else:
                    for V in P_dict["PROPERTIES"][prop]["VALUE"]:
                        set_property(cell_count,prop,V,primitive)
                        cell_count = get_next_count(cell_count,count,checkpoint)
            else:
                for V in P_dict["PROPERTIES"][prop]["VALUE"]:
                    set_property(cell_count,prop,V,primitive)
                    cell_count = get_next_count(cell_count,count,checkpoint)
    
    #pol_selector = 0
    #for pin in P_dict["INVERTIBLE_PINS"]:
    #    pol_selector = 1
    #    for inv in [0,1]:
    #        print(cell_count,len(tile_list))
    #        create_polarity_selector(cell_count,pin,inv,tile_list[cell_count],site_index,site_type)
    #        cell_count = get_next_count(cell_count,count,checkpoint)
    #if pol_selector == 1:
    #    route_design()
    #gen_bitstream(checkpoint)


def randomized_method(checkpoint,tile_list,is_port):
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    if is_port == 1:
        primitive="PORT"
    cell_count = 0
    count = len(tile_list)
    db = bel_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]
    for x in range(int(args.random_count)):
        # random properties
        #print(cell_count)
        random_properties(tile_list[cell_count], site_index, site_type, bel, primitive)
        # random site pip
        if len(db["SITE_PIP"].keys()) != 0:
            SP = random.choice(list(db["SITE_PIP"].keys()))
            if "INV" not in SP:
                V = random.choice(list(db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys()))
                create_site_pip(tile_list[cell_count],site_index,SP,V)
            elif "CLK" in SP:
                if tile_type not in ["BRAM_L","BRAM_R"]:
                    V = random.choice(list(db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys()))
                    create_site_pip(tile_list[cell_count],site_index,SP,V)
        cell_count = get_next_count(cell_count,count,checkpoint)
    #gen_bitstream(checkpoint)


def run_tcl_script(tcl_file):
    os.system("vivado -mode batch -source data/" + fuzz_path + "/" + tcl_file + " -stack 2000")

def set_ft(fp):
    global ft
    ft = fp

def set_args(in_args):
    global args
    args = in_args


def run_data_generator(in_fuzz_path,in_args):
    global tile_type, fuzz_path, args
    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args
    fuzzer()
    if int(args.tilegrid) != 2:
        fileList = os.listdir("data/" + fuzz_path + "/")
        fileList[:] = [x for x in fileList if ".tile" not in x]
        if int(args.parallel) == 0:
            for file in fileList:
                if ".tcl" in file:
                    run_tcl_script(file)
        else:
            pool = Pool(processes=int(args.parallel))
            pool.map(run_tcl_script, fileList)
        fileList = os.listdir("data/" + fuzz_path + "/")
        for file in fileList:
            if ".tcl" in file and ".tile" in file:
                run_tcl_script(file)
    else:
        fileList = os.listdir("data/" + fuzz_path + "/")
        for file in fileList:
            if ".tcl" in file and ".tile" in file:
                print("FILE TO RUN:",file.replace(".tile",""))
                run_tcl_script(file.replace(".tile",""))
                run_tcl_script(file)