
import random
import re
import json
import jpype
import jpype.imports
from jpype.types import *
from data_generator import *
from data_analysis import parse_feature_file
#jpype.startJVM(classpath=["rapidwright-2021.1.1-standalone-lin64.jar"])


from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def init_rapidwright(part_name):
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)


def get_placement_dict(primitive_dict):
    global device,design
    primitive_dict.pop("AND2B1L",None)
    #print(primitive_dict.keys())
    placement_map = {}
    for x in Unisim.values():
        # If x in primitive json - Unisim.getTransform(series) isn't working
        if str(x) in primitive_dict:
            try:
                a = design.createCell("tmp"+str(x),x)
                placement = a.getCompatiblePlacements()
                tmp_dict = {}
                for k in placement:
                    tmp_dict[str(k)] = list(str(v) for v in placement[k])
                placement_map[str(x)] = tmp_dict
                design.removeCell(a)
            except:
                continue


    # Need to invert placement_map for bel-> primitive
    bel_prim = {}
    for P in placement_map:
        for ST in placement_map[P]:
            for B in placement_map[P][ST]:
                if (ST,B) not in bel_prim:
                    bel_prim[(ST,B)] = [P]
                else:
                    bel_prim[(ST,B)] += [P]
    #for x in bel_prim:
    #    print(x,bel_prim[x])
    return bel_prim


def is_ultrascale_tieoff(N):
    global args
    if "7" not in args.family:
        s,n = str(N).rsplit("/",1)
        if n == "VCC_WIRE":
            return s + ".US.HARD1"
        elif n == "GND_WIRE":
            return s + ".US.HARD0"
        else:
            return 0
    else:
        return 0


def is_valid_SP(SP,direction,N):
    global used_sites, banned_pin_list, args, tile_type
    # Also need a list of nodes that are used to prevent path collisions
    if SP == None:
        return 0
    if direction == "UP": 
        if SP.isInput():
            return 0
    else:
        if SP.isInput() == False:
            return 0

    S = SP.getSite()
    ST = str(S.getSiteTypeEnum())
    T = S.getTile()
    TT = str(T.getTileTypeEnum())
    if "CTRL" in str(N) and "7" not in args.family:
        if ST not in ["SLICEL","TIEOFF","SLICEM"]:
            return 0
    elif ST not in ["SLICEL","TIEOFF"] and TT != tile_type :
        return 0
    if str(SP).split("/")[-1] in banned_pin_list:
        return 0
    if str(S) in used_sites:
        return 0
    return 1


def dfs(P,direction,path,depth,max_depth, banned_pips):
    global ft
    if depth > max_depth:
        return None

    if direction == "UP":
        N = P.getStartNode()
    else:
        N = P.getEndNode()

    if N is None or N.isInvalidNode():
        return None
    else:
        path.append(str(N))
        SP = N.getSitePin()
        #print("\tSP:",SP)
        if is_valid_SP(SP,direction,N):
            return [path,N.getSitePin()]
        u_tieoff = is_ultrascale_tieoff(N)
        if u_tieoff != 0: # Check if node is a hard0/hard1 in ultrascale
            return [path,u_tieoff]
        if direction == "UP":
            pips = N.getAllUphillPIPs()
        else:
            pips = N.getAllDownhillPIPs()
        #print("\tNODES",list(str(x) for x in nodes),file=ft)
        random.shuffle(pips)
        if len(banned_pips) > 0:
            for PP in pips:
                p_simple = str(PP).split("/")[-1]
                if p_simple not in banned_pips:
                    #print("\t\tCHOOSE:",P,PP,p_simple,direction,path)
                    #print("\t\t\t",len(banned_pips),banned_pips,pips)
                    ret = dfs(PP,direction,path.copy(),depth+1,max_depth,[])
                    if ret is not None:
                        return ret
        else:
           for PP in pips:
                ret = dfs(PP,direction,path.copy(),depth+1,max_depth,[])
                if ret is not None:
                    return ret 
    return None


def dfs_main(P,direction,max_depth):
    global ft, pip_dict

    banned_pips = []
    p_simple = str(P).rsplit("/")[-1]
    if p_simple in pip_dict:
        pd = pip_dict[p_simple]
        for ps in pd:
            for p in pd[ps]:
                p_name = p.rsplit(":")[-1]
                banned_pips.append(p_name)
    print("FINAL BAN",P,banned_pips)
    return dfs(P,direction,[],0,max_depth, banned_pips)

def get_rapid_tile_list(tile_type):
    tile_list = []
    for T in device.getAllTiles():
        if T.getTileTypeEnum().toString() == tile_type:
            tile_list.append(T)
    return tile_list



def create_and_place(primitive,site, site_type,bel):
    if bel == "PHY":
        cell_name = site+"."+bel+"."+primitive
        loc = site+"/"+bel
        print("create_cell -reference",primitive,cell_name,file=ft)
    else:
        cell_name = site+"."+bel+"."+primitive
        loc = site+"/"+bel
        print("create_cell -reference",primitive,cell_name,file=ft)
        if str(site_type) == "SLICEM":
            print("tcl_drc_lut_rams ",primitive, bel, "[get_sites",site,"]",file=ft) 
        print("catch { set_property MANUAL_ROUTING",str(site_type),"[get_sites",site,"]}",file=ft)
        print("catch { place_cell",cell_name,loc,"}",file=ft)
        print("catch { reset_property MANUAL_ROUTING","[get_sites",site,"]}",file=ft)


def get_bel_of_pin(BP):
    B = BP.getBEL()
    print("GETTING BEL OF PIN:", BP)
    if "RBEL" in str(B):
        if BP.isInput():
            rbel_pins = B.getPins()
            for rbel_pin in rbel_pins:
                if rbel_pin.isOutput():
                    rbel_conns = rbel_pin.getSiteConns()
                    for RBP in rbel_conns:
                        return get_bel_of_pin(RBP)
        else:
            rbel_pins = B.getPins()
            for rbel_pin in rbel_pins:
                if rbel_pin.isInput():
                    rbel_conns = rbel_pin.getSiteConns()
                    for RBP in rbel_conns:
                        return get_bel_of_pin(RBP)
    else:
        return B,str(BP).replace(".","/")

def get_placement(site_pin):
    global primitive_map
    ff_regex = re.compile('([A-H]FF.?/CE)|([A-H]FF.?/SR)')

    if "HARD1" in str(site_pin):
        if "US" in str(site_pin):
            S = site_pin.split(".")[0]
            BP = S+".PHY.VCC/P"
            ST = "INT"
        else:
            S = site_pin.getSite()
            BP = str(S)+".PHY.VCC/P"
            ST = S.getSiteTypeEnum()
        #print(site_pin,S,ST,BP)
        return BP,"VCC",str(S),str(ST),"PHY",0
    elif "HARD0" in str(site_pin):
        if "US" in str(site_pin):
            S = site_pin.split(".")[0]
            BP = S+".PHY.GND/G"
            ST = "INT"
        else:
            S = site_pin.getSite()
            BP = str(S)+".PHY.GND/G"
            ST = S.getSiteTypeEnum()
        return BP,"GND",str(S),str(ST),"PHY",0
    else:
        S = site_pin.getSite()
        site_types = list(x for x in S.getAlternateSiteTypeEnums()) + [S.getSiteTypeEnum()]
        for ST in site_types:
            #print("\t\t",ST)
            try:
                port_bel_pin = site_pin.getBELPin(ST)
            except:
                continue
            bel_conns = port_bel_pin.getSiteConns()
            print("\t\tGETTING PLACEMENT:",ST,S,bel_conns)
            for BP in bel_conns:
                B,BP_sink = get_bel_of_pin(BP)
                print("\tRETURNED:",B,BP_sink)
                #print("\t\t\tGETTING CONNS:",B,BP_sink)
                if str(ST) in ["SLICEM","SLICEL"] and "5LUT" in str(B):
                    B = str(B).replace("5","6")
                    BP_sink = str(BP_sink).replace("5LUT","6LUT")
                #print("\t\t\t",BP,BP.getDir(),B)
                key = (str(ST),str(B).replace("(BEL)",""))
                if key in primitive_map:
                    #create_and_place(primitive_map[key][0],str(S),key[0],key[1])
                    #print("SINK:",BP_sink)
                    if "7" not in args.family:
                        if BP_sink in ["CARRY4/CYINIT","CARRY4/CI","CARRY8/CI","CARRY8/CI_TOP"]:
                            is_bp = 0
                            BP_sink = str(S)+".CARRY4."+BP_sink
                        elif BP_sink in ["CARRY8/AX","CARRY8/BX","CARRY8/CX","CARRY8/DX","CARRY8/EX","CARRY8/FX","CARRY8/GX","CARRY8/HX"]:
                            continue
                            # These pins don't automatically have their cell pins mapped to these bel pins - not sure how to remap them
                                # Remap by unplace, attach pin, then replace
                        elif ff_regex.match(BP_sink): #{ABCDEFG}/FF{2}/{SR|CE}
                            is_bp = 2
                            BP_sink = str(S)+"/"+BP_sink
                        else:
                            is_bp = 1
                            BP_sink = str(S)+"/"+BP_sink
                    else:
                        is_bp = 1
                        BP_sink = str(S)+"/"+BP_sink

                    # Need to check if BP is actually a part of the primitive - Such as the CLK bel pin of the A6LUT in SLICEM not used in LUT6
                    primitive = primitive_map[key][0]
                    if primitive == "LUT6" and ("CLK" in BP_sink or "WE" in BP_sink) and "7" not in args.family:
                        primitive = "SRLC32E"
                    if primitive == "FDCE" and ("CLK" in BP_sink) and "7" not in args.family:
                        primitve = "FDSE"
                    return BP_sink,primitive,str(S),key[0],key[1],is_bp
                else:
                    print("\t#",B,BP_sink,"NO PRIMITIVE",file=ft)
                    return 0

def reset_manual_routing(CP):
    print("set S [get_sites -of_objects [get_cells -of_objects [get_pins",CP,"]]]",file=ft)
    print("set ST [get_property MANUAL_ROUTING $S]",file=ft)
    print("reset_property MANUAL_ROUTING $S",file=ft)




def attach_net(BP,is_bp,net_name):
    if is_bp == 1:
        print("set P [get_pins -of_objects [get_bel_pins ",BP,"]]",file=ft)
    elif is_bp == 2:
        print("#IS BP 2:",file=ft)
        bel = BP.rsplit("/",1)[0]
        pin = BP.rsplit("/",1)[1]
        if pin == "SR":
            pin = "CLR"
        print("set P [get_pins [get_cells -of_objects [get_bels " + bel + "]]/"+pin+"]",file=ft)
    else:
        print("set P [get_pins ",BP,"]",file=ft)
    print("if {$P != \"\"} {",file=ft)
    print("set C [get_cells -of_objects $P]\nset loc [get_property LOC $C]\nset bel [get_property BEL $C]",file=ft)
    print("if {$loc != \"\"} { catch { unplace_cell $C  } }",file=ft)
    print("connect_net -net",net_name, "-objects $P",file=ft)
    print("if {$loc != \"\"} { catch { place_cell $C \"$loc/$bel\" } }",file=ft)
    print("}",file=ft)
    
def add_nets():
    global nets, ft
    for x in nets:
        is_bel_pin_up, is_bel_pin_down, BP_up, BP_down, path,net_name = x
        print("set N [create_net -net", net_name,"]",file=ft)
        attach_net(BP_up,is_bel_pin_up,net_name)
        attach_net(BP_down,is_bel_pin_down,net_name)
        print("catch {set_property FIXED_ROUTE",path,"$N}",file=ft)
    nets = []

def create_net(is_bp_up,is_bp_down,BP_up, BP_down, path,net_name):
    global nets
    nets.append([is_bp_up, is_bp_down,BP_up, BP_down, path,net_name])
    

def export_path(path_up, site_pin_up,path_down, site_pin_down,net_name):
    up,down = [],[]
    #BP_sink, primitive, site, site_type, bel
    up = get_placement(site_pin_up)
    down = get_placement(site_pin_down)
    print("\tEXPORT:",path_up, site_pin_up,path_down, site_pin_down,net_name,up,down)
    if up and down:
        if ".".join(up[2:5]) != ".".join(down[2:5]): # Check if site/site_type/bel is equivalent - only place one
            create_and_place(*up[1:5])
            create_and_place(*down[1:5])
        else:
            create_and_place(*up[1:5])
        path_down.reverse()
        #path_down = path_down[:-2]
        path = list(str(x) for x in path_down) + (list(str(x) for x in path_up))
        path_str = "{"
        for x in path:
            path_str += x + " "
        path_str += "}"
        create_net(up[5],down[5],up[0],down[0],path_str,net_name)
        return 1
    else:
        return 0
    



def generate_pip_bitstream():
    global fuzz_path, specimen_number, tile_type
    post_placement_drc(1)
    add_nets()
    pip_bitstream_drc()
    print("record_device_pips data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.ft",file=ft)
    write_bitstream("data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.bit")
    specimen_number+=1
    open_checkpoint("vivado_db/init")
    return 

def add_used_site(site_pin):
    global used_sites
    if "HARD" not in str(site_pin):
        S = str(site_pin.getSite())
    elif ".US." in str(site_pin):
        S = site_pin.split(".")[0]
    else:
        S = str(site_pin.getSite())
    print("SITEPIN:",site_pin,S)
    used_sites.append(S)



def run_pip_generation(tile_list,pip_list):   
    global specimen_number,tile_type,fuzz_path, used_sites, ft, banned_pin_list,args
    used_tiles = [] # need to make sure placement doesn't collide with other tiles
    max_pips_test = 75
    if len(tile_list) < max_pips_test:
        max_pips_test = 10
    if tile_type in ["BRAM_L","BRAM_R","BRAM"]:
        max_pips_test = 1
    if max_pips_test > len(tile_list):
        max_pips_test = len(tile_list)
    cur_tile_list = tile_list.copy()
    used_sites = []
    max_attempt = {}
    iteration = 0
    banned_pin_list = ["SR","CE"]
    if "7" in args.family:
        series_depth = 6
        max_route_attempt = 2
    else:
        series_depth = 7
        max_route_attempt = 20
    
    while(1):
        random.shuffle(pip_list)
        current_pip_count = 0
        for i in pip_list:
            attempt_count = 0
            current_pip_count += 1
            max_depth = series_depth
            if i in max_attempt:
                max_route_attempt = 5
                max_depth+=2
                if max_attempt[i] > 4:
                    max_route_attempt = 10
                    max_depth+=2
                if max_attempt[i] > 9:
                    max_route_attempt = 20
                    max_depth+=2
                if max_attempt[i] > 15:
                    max_route_attempt = 30
                    max_depth+=2
            while (1):
                attempt_count += 1
                T = random.choice(cur_tile_list)
                P = T.getPIPs()[i]
                #path_up, site_pin_up = bfs(P,"DOWN")
                #path_down, site_pin_down = bfs(P,"UP")
                #print("MAX DEPTH:",max_depth)
                ret_up = dfs_main(P,"UP",max_depth)
                ret_down = dfs_main(P,"DOWN",max_depth)
                if ret_up != None and ret_down != None:
                    path_up, site_pin_up = ret_down
                    path_down, site_pin_down = ret_up
                    print("##",T,P,max_depth,file=ft)
                    print("##",ret_up,ret_down,file=ft)
                    net_name = str(T)+"."+str(P).split("/")[1]
                    if export_path(path_up, site_pin_up,path_down, site_pin_down,net_name):
                        add_used_site(site_pin_up)
                        add_used_site(site_pin_down)
                        cur_tile_list.remove(T)
                        break
                elif attempt_count >= max_route_attempt:
                    print("##",P,"MAX ATTEMPT REACHED",max_depth,file=ft)
                    if i not in max_attempt:
                        max_attempt[i] = 1
                    else:
                        max_attempt[i] = max_attempt[i] + 1
                    break

            if current_pip_count%max_pips_test == max_pips_test-1:
                generate_pip_bitstream()
                used_sites = []
                cur_tile_list = tile_list.copy()
            #if specimen_number%10 == 3:
            #    break
        generate_pip_bitstream()
        ft.close()
        os.system("vivado -mode batch -source data/" + fuzz_path + "/fuzz_pips.tcl -stack 2000")
        pips = tile_list[0].getPIPs()
        pip_list = check_pip_files(pips)

        if len(pip_list) == 0 or iteration >= int(args.pip_iterations):
            break
        init_file()
        iteration+=1
        if iteration >= 2:
            banned_pin_list = []




def add_pip_to_set(set_name,P):
    global pip_set
    if set_name not in pip_set:
        pip_set[set_name] = [P.rsplit("/",1)[-1]]
    else:
        pip_set[set_name] += [P.rsplit("/",1)[-1]]



def generate_pip_sets(pip_list):
    global pip_set
    pip_set = {}
    for pip in pip_list:
        P = str(pip)
        set_name = P.rsplit(">",1)[-1]
        if "<" in P:
            up_P = P.replace("<","")
            add_pip_to_set(set_name,up_P.rsplit("/",1)[-1])
            dest = P.rsplit(">",1)[-1]
            base_src = P.rsplit("<",2)[0]
            base, src = base_src.rsplit(".")
            base = base.split("/")[-1]
            add_pip_to_set(src,base+"."+dest + "->>" + src)
        else:
            add_pip_to_set(set_name,P)

    for x in pip_set:
        print(x,len(pip_set[x]),pip_set[x])

def check_pip_files(pip_list):
    global fuzz_path, pip_dict, bel_dict, pip_set
    pip_dict = {}
    fileList = os.listdir("data/" + fuzz_path + "/")
    for file in sorted(fileList):
        if ".ft" in file:
            if os.path.exists("data/" + fuzz_path + "/" + file.replace(".ft", '.bit')):
                specimen, tile_type, pip_ext, ext = file.split(".")
                # Parse Feature file
                f = open("data/" + fuzz_path + "/" + file)
                tile_feature_dict = parse_feature_file(f, fuzz_path + "." + specimen, tile_type)
                print("PARSED FEATURE")
                f.close()
                for T in tile_feature_dict:
                    if tile_type in T:
                        for F in tile_feature_dict[T]:
                            F_name = F.rsplit(":",1)[-1]
                            if F_name not in pip_dict:
                                tmp = {}
                                for PF in tile_feature_dict[T]:
                                    set_p = PF.rsplit(">",1)[-1]
                                    tmp[set_p] = {PF}
                                pip_dict[F_name] = tmp
                                #pip_dict[F_name] = set(tile_feature_dict[T])
                            else:
                                diff_keys = set(pip_dict[F_name].keys()) - set(list(x.rsplit(">",1)[-1] for x in tile_feature_dict[T]))
                                #print("DIFF KEYS:",diff_keys)
                                for x in diff_keys:
                                    pip_dict[F_name].pop(x,None)
                                for PF in tile_feature_dict[T]:
                                    set_p = PF.rsplit(">",1)[-1]
                                    if set_p in pip_dict[F_name]:
                                        pip_dict[F_name][set_p].add(PF)
                                        if len(pip_dict[F_name][set_p]) >= len(pip_set[set_p]):
                                            pip_dict[F_name].pop(set_p,None)
                                #pip_dict[F_name] = pip_dict[F_name] & set(tile_feature_dict[T])
    #print("PRINTING PIP DICT:")
    #for F in pip_dict:
    #    print(F,pip_dict[F])

    for F in pip_dict:
        # If pip is default/always, then remove it entirely
        if F.split(".")[-1] in bel_dict["TILE_PIP"] and bel_dict["TILE_PIP"][F.split(".")[-1]]["TYPE"] != "PIP":
            pip_dict[F] = {}
        else:
            remove_pips = set()
            # Remove always and default pips
            for x in pip_dict[F]:
                #print("X:",x)
                for y in pip_dict[F][x]:
                    #print("Y:",y)
                    if y.split(".")[-1] in bel_dict["TILE_PIP"] and bel_dict["TILE_PIP"][y.split(".")[-1]]["TYPE"] != "PIP":
                        remove_pips.add(x)
            #print("Removing:",remove_pips)
            for x in remove_pips:
                pip_dict[F].pop(x,None)
            #pip_dict[F] = pip_dict[F] - remove_pips
        
        #print(F,len(pip_dict[F]),pip_dict[F])

    remaining_pips = []
    pips = list(str(x).split("/")[-1] for x in pip_list)
    #print(pip_dict.keys())
    for idx, x in enumerate(pips):
        #print("ENUM",idx,x)
        F = x.split(".")[-1]
        if bel_dict["TILE_PIP"][F]["TYPE"] != "PIP":
            continue
        if x not in pip_dict or len(pip_dict[x]) > 1:
            remaining_pips.append(idx)
    
    #for x in pip_dict:
    #   if len(pip_dict[x]) > 1:
    #        remaining_pips.append(pips.index(x.split(":")[-1]))
    print("REMAINING:", len(remaining_pips))
    for x in remaining_pips:
        print(x,pips[x])
        if pips[x] in pip_dict:
            print("\t",pip_dict[pips[x]])
    print("DONE CHECK")
    return remaining_pips


def init_file():
    global ft, fuzz_path, args
    ft = open("data/" + fuzz_path + "/fuzz_pips.tcl","w",buffering=1)
    set_ft(ft)
    print("source ../../record_device.tcl",file=ft)
    print("source ../../drc.tcl",file=ft)
    open_checkpoint("vivado_db/init")
    disable_drc()
    #print("source ../../fuzz_pip.tcl",file=ft)
    print("set ::family " + args.family,file=ft)
    print("set part_name " + args.part,file=ft)


def run_pip_fuzzer(in_fuzz_path,in_args):
    global args, tile_type, tile_dict, primitive_map, nets, ft, fuzz_path, specimen_number, bel_dict, pip_dict
    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args
    set_args(in_args)
    nets = []
    fj = open("vivado_db/primitive_dict.json")
    primitive_dict = json.load(fj) 
    fj.close()
    fj = open("vivado_db/bel_dict.json")
    bel_dict = json.load(fj) 
    fj.close()
    bel_dict = bel_dict["TILE_TYPE"][tile_type]
    specimen_number = 0
    pip_dict = {}
    init_file()
    init_rapidwright(args.part)
    primitive_map = get_placement_dict(primitive_dict["PRIMITIVE"])
    tile_list = get_rapid_tile_list(tile_type)
    generate_pip_sets(tile_list[0].getPIPs())


    pip_list = check_pip_files(tile_list[0].getPIPs())
    
    run_pip_generation(tile_list,pip_list)
    check_pip_files(tile_list[0].getPIPs())

    
