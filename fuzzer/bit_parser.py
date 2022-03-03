#!/usr/bin/env python3


def print_frame (frame, addr,word_size):
    global bitstream_addr
    frame_data = []
    #print(addr,len(frame))
    #print(frame)
    for i in range(len(frame)):
        if frame[i] != 0:
            #print(bin(frame[i]))
            val = bin(frame[i])
            val = val.replace("\n","")
            val = val.replace("0b","")
            val = val.zfill(word_size*8)
            #print("VAL",val)
            for j in range(word_size*8):
                if val[j] == '1':   
                    frame_data.append((i,j))
                    #print(i,j)
            
    #print(hex(addr) ,frame_data)
    bitstream_addr.append(addr)
    return frame_data


def print_frame_usp (frame, addr,word_size):
    global bitstream_addr
    frame_data = []
    #print(addr,len(frame))
    #print(frame)
    for i in range(len(frame)):
        if frame[i] != 0:
            #print(bin(frame[i]))
            val = bin(frame[i])
            val = val.replace("\n","")
            val = val.replace("0b","")
            val = val.zfill(word_size*8)
            #print("VAL",val)
            #for j in range(word_size*8):
            #    if val[j] == '1':   
            #frame_data.append((i,hex(int(val,2))))
            frame_data.append((i,val))
            #        #print(i,j)
            
    #print(hex(addr) ,frame_data)
    bitstream_addr.append(addr)
    return frame_data



def parse_bitstream(f, family, tilegrid,tile_type,specimen):
    global bitstream_addr
    bitstream_addr = []
    if "uplus" in family:
        write_instr = 0x3000405D
        write_count = 186
        word_size = 2
    elif "u" in family:
        write_instr = 0x3000407B
        write_count = 123
        word_size = 4
    else:
        write_instr = 0x30004065
        write_count = 101
        word_size = 4
    
    bitstream = {}
    b = f.read(1)
    while (b != 0xaa):
        b = f.read(1)
        b = int.from_bytes(b, 'big')
    f.read(3)
    count = 0
    while (1):
        count += 1
        frame = []
        inst = f.read(4)
        if not inst:
            break
        inst = int.from_bytes(inst, 'big')
        frame_str = ""
        if (inst == write_instr):
            for i in range(write_count):
                inst = int.from_bytes(f.read(word_size), 'big')
                frame.append(inst)
            #addr_comm = int.from_bytes(f.read(4), 'big')
            f.read(4)
            addr = int.from_bytes(f.read(4), 'big')
            #f.read(8)
            #crc_comm = int.from_bytes(f.read(4), 'big')
            #crc = int.from_bytes(f.read(4), 'big')   
            #0x82017f []
            #0xc2017f []
            if addr not in bitstream:
                if "uplus" in family:
                    bitstream[addr] = print_frame_usp(frame, addr,word_size)
                else:
                    bitstream[addr] = print_frame(frame, addr,word_size)



    tile_bit_dict = {}
    frame_dict = {}
    if tilegrid is not None:
        for T in tilegrid:
            if tilegrid[T]["TYPE"] == tile_type:
                if 'bits' in tilegrid[T]:
                    for config_bus in ["CLB_IO_CLK","BLOCK_RAM"]:
                        if config_bus in tilegrid[T]['bits']:
                            tile_info = tilegrid[T]['bits'][config_bus]
                            offset = tile_info['offset']
                            words = tile_info['words']
                            frames = tile_info['frames']
                            if frames == -1:
                                frames = 100 # If the frame count wasn't solved for, any value close to the minor address max will work
                                    # since the "if Baseaddress+i in bitstream:" will catch it - 7 Series/ultra [6:0], ultra+ [7:0]
                            Baseaddress = int(tile_info['baseaddr'],16)
                            parity = "even"
                            mod_term = tilegrid[T]["HEIGHT"] / 3 * 2
                            #print(tilegrid[T]['Y'],mod_term )
                            if tilegrid[T]['Y'] % mod_term != 0:
                                parity = "odd"
                                #print("ODD",tilegrid[T]['Y'])
                            tile_data = []
                            if "uplus" in family:
                                # ultrascale+ has a bit-twiddling operation that occurs on every pair of tiles within a column
                                for i in range(frames):
                                    if Baseaddress+i in bitstream:
                                        #print("DATA:",bitstream[Baseaddress+i])
                                        if parity == "even":
                                            for j in bitstream[Baseaddress+i]:
                                                if (offset <= j[0] < offset+words-1):
                                                    word_offset = j[0]-offset
                                                elif j[0] == offset+words:
                                                    word_offset = j[0]-offset-1
                                                else:
                                                    continue
                                                for b in range(word_size*8):
                                                    if j[1][b] == '1':   
                                                        bit_offset = (word_offset*word_size*8) + (word_size*8 - b - 1)
                                                        bit_str = str(i) + "_" + str(bit_offset)
                                                        tile_data += [bit_str]
                                        else:
                                            for j in bitstream[Baseaddress+i]:
                                                if (offset+1 <= j[0] < offset+words) or j[0] == offset-1:
                                                    word_offset = j[0]-offset
                                                else:
                                                    continue
                                                if word_offset % 2 == 0:
                                                    word_offset -= 2
                                                else:
                                                    word_offset += 2
                                                if j[0] == offset+words-2:
                                                    word_offset = j[0]-offset+1
                                                for b in range(word_size*8):
                                                    if j[1][b] == '1':   
                                                        bit_offset = (word_offset*word_size*8) + (word_size*8 - b - 1)
                                                        bit_str = str(i) + "_" + str(bit_offset)
                                                        tile_data += [bit_str]
                            else:
                                for i in range(frames):
                                    if Baseaddress+i in bitstream:
                                        #print("DATA:",bitstream[Baseaddress+i])
                                        for j in bitstream[Baseaddress+i]:
                                            if (offset <= j[0] < offset+words):
                                                word_offset = ((j[0] - offset)*word_size*8) + (word_size*8 - j[1] - 1)
                                                bit_str = str(i) + "_" + str(word_offset)
                                                tile_data += [bit_str]
                            tile_bit_dict[config_bus[0:3]+"."+specimen+"."+T] = tile_data
        return tile_bit_dict
    else: # Return just the base address with bits
        for addr in bitstream:
            base_addr = addr & 0xFFFFFF80
            frame = addr & 0x7F
            if base_addr not in tile_bit_dict:
                tile_bit_dict[base_addr] = []
                frame_dict[base_addr] = 0
            if frame > frame_dict[base_addr]:
                frame_dict[base_addr] = frame
            for x in bitstream[addr]:
                tile_bit_dict[base_addr] += [str(frame) + "_" + str(x)]
        return tile_bit_dict, frame_dict
