print("External library file loading")
import sys, os, subprocess, time, struct, tkinter
from PIL import Image, ImageChops, ImageTk
from math import floor, ceil
from collections import OrderedDict
import colorsys

np, cwd, gbn = (os.path.normpath, os.getcwd(), os.path.basename)
def getFileName(f): return os.path.splitext(gbn(f))[0]
def ep(f): return np(cwd+"/"+f)
def ensuredir(d):
    if not os.path.isdir(d): os.makedirs(d)
    
TDIR, TIMGDIR, OUTDIR, STATUSF = (ep("obj"), ep("obj/png"), ep("bin"), ep("obj/curstate"))
for i in (TDIR, TIMGDIR, OUTDIR): ensuredir(i)

try: Image.Image.tobytes()
except AttributeError: Image.Image.tobytes = Image.Image.tostring
except: pass

ENCNAMES = { "M1" : "M1X3-ZX7",
             "M2" : "M1X2-ZX7", }
ENCFPSEG = { "M1" : (30,15,10,10,10),
             "M2" : (20,10, 5, 5, 5), }

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Miscellaneous

def checkdel(fnp, isdel):
    retry = 60
    while os.path.isfile(fnp) == isdel:
        time.sleep(0.015)
        retry -= 1
        if retry < 1: return False
    return True

def readFile(fn):
    a = []
    with open(fn, "rb") as f:
        b = f.read(1)
        while b != b'':
            a.append(ord(b))
            b = f.read(1)
    return a
    
def writeFile(fn, a):
    with open(fn, "wb+") as f: 
        if isinstance(a, str):
            f.write(a.encode('latin-1'))
        else:
            f.write(bytearray(a))

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# Video window class

class Application(tkinter.Frame):
    def __init__(self, master=None):
        tkinter.Frame.__init__(self, master)
        self.master.title("* Ohhhh yesss!")
        self.master.geometry('200x200')
        self.master.minsize(400,300)
        self.pack()
        self.img = ImageTk.PhotoImage(Image.new('RGB', (96,72), 0))
        self.canvas = tkinter.Canvas(self.master, width=320, height=240)
        self.canvas.place(x=10, y=10, width=320, height=240)
        self.canvas.configure(bg='white', width=96, height=72, state=tkinter.NORMAL)
        self.imgobj = self.canvas.create_image(1, 1, image=self.img, anchor=tkinter.NW, state=tkinter.NORMAL)
        
    def updateframe(self, pimg):
        self.img = ImageTk.PhotoImage(pimg)
        self.canvas.itemconfig(self.imgobj, image=self.img)
        self.update_idletasks()
        self.update()
        
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# Export data to TI calculator appvar type
TI_VAR_PROG_TYPE, TI_VAR_PROTPROG_TYPE, TI_VAR_APPVAR_TYPE = (0x05, 0x06, 0x15)
TI_VAR_FLAG_RAM, TI_VAR_FLAG_ARCHIVED = (0x00, 0x80)

def export8xv(fpath, fname, fdata):
    # Ensure that filedata is bytes
    if isinstance(fdata, str):
        fdata = fdata.encode('latin-1')
    fdata = bytes(bytearray(fdata))
    
    # Add size bytes to file data as per (PROT)PROG/APPVAR data structure
    fdata = struct.pack('<H', len(fdata)) + fdata
    
    # Construct variable header
    fname_bytes = fname.encode('ascii').ljust(8, b'\x00')[:8]
    vheader  = b"\x0D\x00" + struct.pack("<H", len(fdata)) + bytes([TI_VAR_APPVAR_TYPE])
    vheader += fname_bytes
    vheader += b"\x00" + bytes([TI_VAR_FLAG_ARCHIVED]) + struct.pack("<H", len(fdata))
    variable = vheader + fdata
    
    # Construct header, add file data, then add footer
    output  = b"**TI83F*\x1A\x0A\x00"
    output += b"Cherries! Steaks! Gravy! Rawr!".ljust(42, b'\x00')[:42]
    output += struct.pack('<H', len(variable)) + variable
    output += struct.pack('<H', sum(variable) & 0xFFFF)
    
    # Output result to file
    writeFile(np(fpath+"/"+fname+".8xv"), output)

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# Frame data packager

class CmprSeg():
    def __init__(self, segid, data):
        self.segid = segid
        self.data = data
        self.size = len(data)
        
class Framebuf():
    def __init__(self, config):
        self.frame_buffer = bytearray()
        self.cmpr_arr = []
        self.frames_per_segment = config.getFramesPerSegment()
        self.cur_frame = 0
        self.cur_segment = 0
        self.cmpr_len = 0
        self.raw_len = 0
        self.vid_w, self.vid_h = config.getImgDims()
        self.vid_title = config.titl
        self.vid_author = config.auth
        self.bit_depth = config.getBitDepthCode()
        self.videoname = config.vname
        self.encoding = config.enco
        
    def addframe(self, framedata):
        global TDIR
        if framedata:
            self.frame_buffer.extend(bytearray(framedata))
            self.cur_frame += 1
            if self.cur_frame >= self.frames_per_segment:
                framedata = None
                
        if not framedata and self.frame_buffer:
            tfo = np(TDIR+"/tin")
            tfc = np(TDIR+"/tout")
            if os.path.exists(tfo): os.remove(tfo)
            if os.path.exists(tfc): os.remove(tfc)
            if not checkdel(tfo, True):
                raise IOError("Input file "+tfo+" could not be deleted.")
            if not checkdel(tfc, True):
                raise IOError("Output file "+tfo+" could not be deleted.")
            
            writeFile(tfo, self.frame_buffer)
            if not checkdel(tfo, False):
                raise IOError("Input file "+tfo+" could not be created.")
                
            FNULL = open(os.devnull, "w")
            subprocess.call([np(cwd+"/tools/zx7.exe"), tfo, tfc], stdout=FNULL)
            
            if not checkdel(tfc, False):
                raise IOError("Output file "+tfo+" could not be created.")
            self.cmpr_arr.append(CmprSeg(self.cur_segment, readFile(tfc)))
            self.raw_len += len(self.frame_buffer)
            self.cmpr_len += self.cmpr_arr[-1].size
            sys.stdout.write("\nOutput seg "+str(self.cur_segment)+" size "+str(self.cmpr_arr[-1].size)+"      \n")
            self.frame_buffer = bytearray()
            self.cur_frame = 0
            self.cur_segment += 1
    
    def flushtofile(self):
        global ENCNAMES, OUTDIR
        output_filename = self.videoname
        if self.frame_buffer: self.addframe(None)
        outfilename = str(os.path.splitext(os.path.basename(output_filename))[0])
        video_decoder = ENCNAMES[self.encoding[:2]]
        self.cmpr_arr = sorted(self.cmpr_arr, key=lambda i: i.size, reverse=True)
        slack = -1
        curfile = 0
        curseg = 0
        tslack = 0
        maxslack = 65000
        total_len = 0
        
        while len(self.cmpr_arr) > 0:
            slack = maxslack
            segs_in_file = 0
            i = 0
            wfiledata = b""
            while i < len(self.cmpr_arr):
                if self.cmpr_arr[i].size > slack:
                    i += 1
                else:
                    a  = self.cmpr_arr.pop(i)
                    s  = struct.pack('<H', a.segid) + struct.pack('<H', a.size)
                    s += bytes(bytearray(a.data))
                    wfiledata += s
                    curseg += 1
                    segs_in_file += 1
                    slack -= a.size + 4
                    print("Segment " + str(a.segid) + " sized " + str(a.size) + " written.")
            
            wfilename = outfilename[:5] + str(curfile).zfill(3)
            wtempdata = b"8CEVDat" + outfilename.encode('ascii').ljust(9, b'\x00')[:9]
            wtempdata += bytes([segs_in_file & 0xFF])
            wfiledata = wtempdata + wfiledata
            export8xv(OUTDIR, wfilename, wfiledata)
            print("File output: " + str(wfilename))
            curfile += 1
            tslack += slack
            total_len += len(wfiledata)
    
        mfiledata  = b"8CEVDaH" + video_decoder.encode('ascii').ljust(9, b'\x00')[:9]
        mfiledata += self.vid_title.encode('latin-1') + b"\x00"
        mfiledata += self.vid_author.encode('latin-1') + b"\x00"
        mfiledata += struct.pack("<H", curseg)
        mfiledata += struct.pack("<H", self.vid_w)
        mfiledata += struct.pack("<H", self.vid_h)
        mfiledata += struct.pack("B", self.frames_per_segment)
        mfiledata += struct.pack("B", self.bit_depth)
        export8xv(OUTDIR, outfilename, mfiledata)
        
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# Image filtering and processing

def gethsv(t): return colorsys.rgb_to_hsv(*(i/255.0 for i in t))

def rgb24torgb555(rgbtuple):
    return struct.pack("<H", ((rgbtuple[0]>>3)<<10) + ((rgbtuple[1]>>3)<<5) + (rgbtuple[2]>>3))

def paltolist(s, transparent=None):
    o = []
    
    # Falls s eine Liste von Tuples/Listen ist (z.B. [(r,g,b), (r,g,b)...])
    if len(s) > 0 and isinstance(s[0], (tuple, list)):
        for color in s:
            r = color[0] if isinstance(color[0], int) else ord(color[0])
            g = color[1] if isinstance(color[1], int) else ord(color[1])
            b = color[2] if isinstance(color[2], int) else ord(color[2])
            o.append((r & ~0x7, g & ~0x7, b & ~0x7))
    else:
        # Falls s eine flache Liste/Bytes/Strings ist (z.B. r,g,b,r,g,b...)
        i = 0
        while i < len(s):
            try:
                r = s[i+0] if isinstance(s[i+0], int) else ord(s[i+0])
                g = s[i+1] if isinstance(s[i+1], int) else ord(s[i+1])
                b = s[i+2] if isinstance(s[i+2], int) else ord(s[i+2])
                o.append((r & ~0x7, g & ~0x7, b & ~0x7))
                i += 3
            except (IndexError, TypeError):
                # Falls ein einzelnes Element selbst ein Tuple/String der Länge 3 ist
                try:
                    c = s[i]
                    r = c[0] if isinstance(c[0], int) else ord(c[0])
                    g = c[1] if isinstance(c[1], int) else ord(c[1])
                    b = c[2] if isinstance(c[2], int) else ord(c[2])
                    o.append((r & ~0x7, g & ~0x7, b & ~0x7))
                except:
                    o.append((0, 0, 0))
                i += 1

    while len(o) < 256: 
        o.append(None)
    if transparent is not None and transparent < len(o): 
        o[transparent] = None
    return o


def fedge(d, wa, ha, w):
    def scx(d, wa, ha, w):
        for x in wa:
            for y in ha:
                if d[y*w+x]: return x
    def scy(d, wa, ha, w):
        for y in ha:
            for x in wa:
                if d[y*w+x]: return y
    return (scx(d, wa, ha, w), scy(d, wa, ha, w))

def findDiffRect(im1, im2, hdiv):
    w, h = im1.size
    d = ImageChops.difference(im1.convert("RGB"), im2.convert("RGB")).tobytes()
    # In Python 3, d is bytes. d[i] is already an int.
    d = tuple(d[i] + d[i+1]*256 + d[i+2]*65536 for i in range(0, len(d), 3))
   
    if not any(d): return (None,)
    wa, ha = (list(range(w)), list(range(h)))
    l, t = fedge(d, wa, ha, w)
    wa.reverse()
    ha.reverse()
    r, b = fedge(d, wa, ha, w)
    l, r = (int(floor(l/hdiv)*hdiv), int(ceil((r+1)/hdiv)*hdiv-1))
    if (l, r, t, b) == (0, w-1, 0, h-1): return None
    return [l, t, r+1-l, b+1-t]

def imgToPackedData(img, bpp):
    a = tuple(bytearray(img.tobytes()))
    d = []
    if bpp == 1: b, c, m = (8, (0,1,2,3,4,5,6,7), 0x01)
    elif bpp == 2: b, c, m = (4, (0,2,4,6), 0x03)
    elif bpp == 4: b, c, m = (2, (0,4), 0x0F)
    elif bpp == 8: return bytes(bytearray(a))
    else: raise ValueError("Invalid bpp ("+str(bpp)+") passed. Only 1, 2, 4 accepted")
    
    for i in range(len(a) // b):
        t = 0
        for j, k in enumerate(c): t += (a[i*b+j] & m) << k
        d.append(t)
    return bytes(bytearray(d))

def findDiff8x8Grid(im1, im2, sw):
    w, h = im1.size
    im2 = im2.convert("RGB")
    arr = []
    for y in range(0, int(ceil(h*1.0/sw))*sw, sw):
        for x in range(0, w - w%sw, sw):
            x2 = x + sw if x + sw <= w else w
            y2 = y + sw if y + sw <= h else h
            r = im2.crop((x, y, x2, y2))
            if r.tobytes() != im1.crop((x, y, x2, y2)).tobytes():
                arr.append(r)
            else:
                arr.append(None)
    return arr
    
def test8x8Grid(im1, arr, im2, sw):
    w, h = im1.size
    imt = im1.copy().convert("RGB")
    im2 = im2.convert("RGB")
    i = 0
    for y in range(0, int(ceil(h*1.0/sw))*sw, sw):
        for x in range(0, w - w%sw, sw):
            if not arr[i]: continue
            x2 = x + sw if x + sw <= w else w
            y2 = y + sw if y + sw <= h else h
            imt.paste(arr[i], (x, y, x2, y2))
            i += 1
    r = ImageChops.difference(imt, im2)
    return (any(r.tobytes()), r)
    
def dumpGridData(arr, sw, internal_bpp):
    t, bitfield, datafield, matches = ([], [], [], 0)
    for i in range(len(arr) % 8): t.append(arr.pop(0))
    a = iter(arr)
    a = zip(a, a, a, a, a, a, a, a)
    if t != []: a = [t] + list(a)
    for i in a:
        bits = 0
        for j in i:
            bits = bits >> 1
            if j:
                bits |= 0x80
                t_bytes = imgToPackedData(j, internal_bpp)
                datafield.extend(bytearray(t_bytes))
                matches += 1
        if len(i) % 8 > 0: bits = bits >> abs(len(i) % (-8))
        bitfield.append(bits)
    s = bytes(bytearray(bitfield) + bytearray(datafield))
    return s

def quantizetopalette(silf, palette, dither=Image.NONE):
    silf.load()
    palette.load()
    if palette.mode != "P": raise ValueError("Palette image must have palette")
    if silf.mode not in ("RGB","L"):
        raise ValueError("Only RGB or L mode images can be quantized to a palette")
    im = silf.im.convert("P", dither, palette.im)
    try: return silf._new(im)
    except AttributeError: return silf._makeself(im)
    
quant2pal = quantizetopalette

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# Project-specific functions and classes

def getImageList():
    global TIMGDIR
    return [i for i in os.listdir(TIMGDIR) if os.path.isfile(np(TIMGDIR+"/"+i)) and i.lower().endswith('.png')]

class Config(object):
    def __new__(cls, *args):
        if not hasattr(cls, 'instance'): cls.instance = super(Config, cls).__new__(cls)
        return cls.instance
        
    def __init__(self, statusfile):
        self.status = statusfile
        self.doffmpeg = False
        if not os.path.isfile(self.status):
            with open(self.status, 'w') as f: f.write("\nM1\n\n\n")
        with open(self.status, 'r') as f: self.arr = [line.strip() for line in f]
        
        # Ensure we have at least 4 items in the list to avoid unpacking errors
        while len(self.arr) < 4:
            self.arr.append("")
        self.vname, self.enco, self.titl, self.auth = self.arr[:4]
        
    def update(self, videoname, encodername, title, author):
        def cleanPngBuffer():
            global TIMGDIR
            a = getImageList()
            for i in a:
                try: os.remove(np(TIMGDIR+'/'+i))
                except Exception as e: print(e)
        
        if videoname:
            if self.vname and self.vname != videoname:
                print("Input video name has changed since last build. Cleaning png buffer.")
                cleanPngBuffer()
                self.doffmpeg = True
            self.vname = videoname
            
        if encodername and self.enco != encodername:
            self.enco = encodername
            self.doffmpeg = True
            
        if title: self.titl = title
        if author: self.auth = author
        
        if not os.path.isfile(self.vname):
            raise IOError("File "+str(self.vname)+" does not exist.")
            
        self.getBitDepthCode() 
        self.getFramesPerSegment()
        
    def save(self):
        # Join requires strings
        writeFile(self.status, "\n".join([str(self.vname), str(self.enco), str(self.titl), str(self.auth)]))
        
    def process(self, force_reprocess=False):
        global TDIR, TIMGDIR
        from ffmpy import FFmpeg
        def chk(self, v): return self.enco.startswith(v)
        
        if not (self.doffmpeg or force_reprocess): return
        
        if chk(self, 'M1'): hres = 96; vres = -2; vflags = "neighbor"
        elif chk(self, 'M2'): hres = 144; vres = -2; vflags = "neighbor"
        else: raise ValueError("Illegal encoder value was passed. Cannot encode video")
        
        o1, o2, oi = (np(TDIR+'/t1.mp4'), np(TDIR+'/t2.mp4'), np(TIMGDIR+'/i%05d.png'))
        try:
            print("Converting video to target dimensions")
            FFmpeg(
                inputs  = { self.vname: '-y'},
                outputs = { o1: '-c:v libx264 -profile:v baseline -preset medium -vf scale='+str(hres)+':'+str(vres)+':flags='+str(vflags)+' -r 30 -an'},
            ).run()
            print("Outputting individual frames to .png files")
            FFmpeg(
                inputs  = { o1: '-y'},
                outputs = { oi: '-f image2'},
            ).run()
        except Exception as e:
            print(e)
            print("An error has occurred during transcoding. Script has terminated.")
            sys.exit(2)
    
    def cleanOutput(self):
        global OUTDIR
        fl = [f for f in os.listdir(OUTDIR) if os.path.isfile(OUTDIR+"/"+f) and f[:5]==self.vname[:5]]
        for i in fl: os.remove(np(OUTDIR+'/'+i))

    def getImgList(self):
        global TIMGDIR
        return [np(TIMGDIR+'/'+i) for i in sorted(getImageList())]
        
    def getImgDims(self):
        return Image.open(self.getImgList()[0]).size
        
    def getBitDepthCode(self):
        i = None
        if len(self.enco) == 4:
            try: 
                i = ["B1","G2","G4","C4","A4","G8","C8","A8","CF"].index(self.enco[2:])
            except Exception as e: 
                raise ValueError("Invalid codec subcode")
        else:
            i = (-1)
        if i == None: raise RuntimeError("Bit depth failed to initialize. This shouldn't happen.")
        return i
        
    def getFramesPerSegment(self):
        i = self.getBitDepthCode()
        en = self.enco[:2]
        r = None
        if i < 0:
            r = ENCFPSEG[en]
        else:
            try: r = ENCFPSEG[en][i]
            except: raise ValueError("Decoder "+str(en)+" does not support subtype "+str(self.enco[2:]))
        if r == None: raise RuntimeError("Failure to return frames per segment")
        return r
