#!/usr/bin/python

import sys
import string
import fcntl
import subprocess
from struct import *
from ctypes import *
import termios
import select
import tty

#####
# helper routine to print hex strings from integers; not native in python
digs = string.digits + string.lowercase

def int2base(x, base):
    if x < 0: sign = -1
    elif x==0: return '0'
    else: sign = 1
    x *= sign
    digits = []
    while x:
        digits.append(digs[x % base])
        x /= base
    if sign < 0:
        digits.append('-')
    digits.reverse()
    return ''.join(digits)

######
# build ioctl types
# from linux/include/asm-generic/ioctl.h
ioc_sizebits = int(14)

ioc_nrbits = int(8)
ioc_typebits  = int(8)
ioc_dirbits = int(2)
ioc_nrmask = int((1 << ioc_nrbits) - 1)
ioc_typemask = int((1 << ioc_typebits) - 1)
ioc_sizemask = int((1 << ioc_sizebits) - 1)
ioc_dirmask = int((1 << ioc_dirbits) - 1)

ioc_nrshift = int(0)
ioc_typeshift = int(ioc_nrshift + ioc_nrbits)
ioc_sizeshift = int(ioc_typeshift + ioc_typebits)
ioc_dirshift = int(ioc_sizeshift + ioc_sizebits)

ioc_none = int(0)
ioc_write = int(1)
ioc_read = int(2)

ioc_int_size = int(4)

def ioctl_ioc(iodir, iotype, nr, size):
    return int(((iodir)  << ioc_dirshift) | \
	 ((iotype) << ioc_typeshift) | \
	 ((nr)   << ioc_nrshift) | \
	 ((size) << ioc_sizeshift))

def ioctl_iow(iotype, nr, size):
    if( size >= (1 << ioc_sizebits) ):
        sys.exit("invalid size to ioctl")
    return ioctl_ioc(ioc_write, iotype, nr, size) 

def ioctl_ior(iotype, nr, size):
    if( size >= (1 << ioc_sizebits) ):
        sys.exit("invalid size to ioctl")
    return ioctl_ioc(ioc_read, iotype, nr, size) 

fpga_ioc_magic = ord('c')
fpga_iocwtest = ioctl_iow(fpga_ioc_magic, 1, ioc_int_size)
fpga_iocrtest = ioctl_ior(fpga_ioc_magic, 2, ioc_int_size)
fpga_iocreset = ioctl_iow(fpga_ioc_magic, 3, ioc_int_size)
fpga_iocled0 =  ioctl_iow(fpga_ioc_magic, 4, ioc_int_size)
fpga_iocled1 =  ioctl_iow(fpga_ioc_magic, 5, ioc_int_size)
fpga_iocdone =  ioctl_ior(fpga_ioc_magic, 6, ioc_int_size)
fpga_iocinit =  ioctl_ior(fpga_ioc_magic, 7, ioc_int_size)

try:
    fpga_dev = open("/dev/fpga", 'wb')
except IOError, e:
    sys.exit("Can't open /dev/fpga, aborting")

def fpgaReset():
    fcntl.ioctl(fpga_dev, fpga_iocreset)

""""
FROM linux/i2c.h:
struct i2c_msg {
	__u16 addr;	/* slave address			*/
	__u16 flags;
#define I2C_M_TEN		0x0010	/* this is a ten bit chip address */
#define I2C_M_RD		0x0001	/* read data, from slave to master */
#define I2C_M_NOSTART		0x4000	/* if I2C_FUNC_PROTOCOL_MANGLING */
#define I2C_M_REV_DIR_ADDR	0x2000	/* if I2C_FUNC_PROTOCOL_MANGLING */
#define I2C_M_IGNORE_NAK	0x1000	/* if I2C_FUNC_PROTOCOL_MANGLING */
#define I2C_M_NO_RD_ACK		0x0800	/* if I2C_FUNC_PROTOCOL_MANGLING */
#define I2C_M_RECV_LEN		0x0400	/* length will be first received byte */
	__u16 len;		/* msg length				*/
	__u8 *buf;		/* pointer to msg data			*/
};

FROM linux/i2c-dev.h:
/* This is the structure as used in the I2C_RDWR ioctl call */
struct i2c_rdwr_ioctl_data {
	struct i2c_msg __user *msgs;	/* pointers to i2c_msgs */
	__u32 nmsgs;			/* number of i2c_msgs */
};

#define I2C_RDWR	0x0707	/* Combined R/W transfer (one STOP only) */
"""

"""
I2C_M_TEN		= 0x0010 #	/* this is a ten bit chip address */
I2C_M_RD		= 0x0001 #	/* read data, from slave to master */
I2C_M_NOSTART		= 0x4000 #	/* if I2C_FUNC_PROTOCOL_MANGLING */
I2C_M_REV_DIR_ADDR	= 0x2000 #	/* if I2C_FUNC_PROTOCOL_MANGLING */
I2C_M_IGNORE_NAK	= 0x1000 #	/* if I2C_FUNC_PROTOCOL_MANGLING */
I2C_M_NO_RD_ACK		= 0x0800 #	/* if I2C_FUNC_PROTOCOL_MANGLING */
I2C_M_RECV_LEN		= 0x0400 #	/* length will be first received byte */

I2C_RDWR                = 0x0707

class I2C_MSG(Structure):
    _fields_ = [ ("addr", c_ushort),
                 ("flags", c_ushort),
                 ("len", c_ushort),
                 ("buf", POINTER(c_byte)) ]

class I2C_RDRWR_IOCTL_DATA(Structure):
    _fields_ = [ ("msgs", POINTER(I2C_MSG)),
                 ("nmsgs", c_uint) ]

def i2c_read(i2cdev, i2cdevaddr, startreg, data):
    try:
        i2cfd = open(i2cdev, 'wb')
    except IOError, e:
        sys.exit("Can't open I2C device " + i2cdev)

    output = c_byte(startreg)

    messages = (I2C_MSG * 2)()
    messages[0].addr = c_ushort(i2cdevaddr)
    messages[0].flags = c_ushort(i2cdevaddr)
    messages[0].len = c_ushort(1)
    import pdb; pdb.set_trace()
    messages[0].buf = pointer(output)

    messages[1].addr = c_ushort(i2cdevaddr)
    messages[1].flags = c_ushort(I2C_M_RD)
    messages[1].len = c_ushort(sizeof(data))
    messages[1].buf = pointer(data)

    packets = I2C_RDWR_IOCTL_DATA()
    packets.msgs = messages
    packets.nmsgs = 2

    try:
        fcntl.ioctl(i2cfd, I2C_RDWR, pointer(packets), 1)
    except IOError, e:
        print "Unable to communicate with i2c device"
        close(i2cfd)
        return 1

    close(i2cfd)

    return 0

readbuf = create_string_buffer(256)
i2c_read("/dev/i2c-0", 0x1e, 0, readbuf)

print sizeof(readbuf), repr(readbuf.raw)
"""

def test_i2c_calls():
    buf = i2c_read(0x70, 8)
    print "readback value: "
    print buf

    buf2 = [0xde, 0xad, 0xbe, 0xef]
    i2c_write(0x70, buf2)
    print "wrote deadbeef"

    buf3 = i2c_read(0x70, 8)
    print "readback value: "
    print buf3

    for i in range(4):
        assert buf3[i] == buf2[i], 'test failed'


# hard code these, as they never change
i2cdev = 0
i2cdevaddr = 0x1e

def i2c_read(startreg, length):
    retval = []
    for addr in range(startreg, startreg + length):
#        import pdb; pdb.set_trace()
        readbuf = subprocess.check_output(["/usr/sbin/i2cget", "-y", \
                                           str(i2cdev), str(i2cdevaddr), str(addr)])
        retval.append(int(readbuf,16))
    return retval

def i2c_write(startreg, buf):
    if( len(buf) + startreg > 0xFF ):
        print "I2C write: buffer too long"
        return 1

    for addr in range(startreg, startreg + len(buf)):
        retval = subprocess.call(["/usr/sbin/i2cset", "-y", \
                  str(i2cdev), str(i2cdevaddr), str(addr), str(buf[addr - startreg])])
        if( retval != 0 ):
            print "I2C write communication error"
            return 1
    return retval

kovan_cmds = { 'dig_out_val'     : (0x40, 1, 7, 0, 'rw', 'digital output values'),
               'dig_oe'          : (0x41, 1, 7, 0, 'rw', 'digital output enables'),
               'dig_pu'          : (0x42, 1, 7, 0, 'rw', 'digital pull-up enables'),
               'ana_pu'          : (0x43, 1, 7, 0, 'rw', 'digital pull-up enables'),
               'glbl_reset_edge' : (0x45, 1, 2, 2, 'rw', 'reset kovan state machines'),
               'dig_sample'      : (0x45, 1, 1, 1, 'rw', 'sample digital input'),
               'dig_update'      : (0x45, 1, 0, 0, 'rw', 'update digtial input value'),
               'adc_go'          : (0x46, 1, 4, 4, 'rw', 'sample ADC data'),
               'adc_chan'        : (0x46, 1, 3, 0, 'rw', 'set ADC channel to sample'),
               'mot_allstop'     : (0x47, 1, 0, 0, 'rw', 'force all motors to stop'),
               'mot_drive_code'  : (0x48, 1, 7, 0, 'rw', 'send motor driving code'),
               'mot_pwm_duty'    : (0x49, 2, 15, 0, 'rw', 'motor PWM duty cycle'),
               'mot_pwm_div'     : (0x4b, 2, 15, 0, 'rw', 'motor PWM clock divider'),
               'servo_pwm_period': (0x4d, 3, 23, 0, 'rw', 'servo PWM period (abs time)'),
               'servo0_pwm_pulse': (0x50, 3, 23, 0, 'rw', 'servo 0 PWM pulse width'),
               'servo1_pwm_pulse': (0x53, 3, 23, 0, 'rw', 'servo 1 PWM pulse width'),
               'servo2_pwm_pulse': (0x56, 3, 23, 0, 'rw', 'servo 2 PWM pulse width'),
               'servo3_pwm_pulse': (0x59, 3, 23, 0, 'rw', 'servo 3 PWM pulse width'),
               'ddr2_write_data' : (0x60, 4, 31, 0, 'rw', 'DDR2 test write data'),
               'ddr2_test_addr'  : (0x64, 4, 29, 0, 'rw', 'DDR2 test address'),
               'ddr2_rdwr'       : (0x68, 1, 0, 0,  'rw', 'DDR2 1 = read, 0 = write'),
               'ddr2_docmd'      : (0x68, 1, 1, 1,  'rw', 'DDR2 commit command'),
                   
               'dig_val_good'    : (0x80, 1, 1, 1,  'ro', 'digital in value up to date'),
               'dig_busy'        : (0x80, 1, 0, 0,  'ro', 'digital chain is busy'),
               'adc_in'          : (0x81, 2, 9, 0,  'ro', 'ADC input value'),
               'dig_in_val'      : (0x84, 1, 7, 0,  'ro', 'digital input value'),
               'adc_valid'       : (0x83, 1, 0, 0,  'ro', 'ADC input value up to date'),
               
               'ddr2_read_data'  : (0x90, 4, 31, 0, 'ro', 'DDR2 readback data'),
               'ddr2_rd_avail'   : (0x94, 1, 0, 0,  'ro', 'DDR2 read available'),
               'ddr2_wr_empty'   : (0x94, 1, 1, 1,  'ro', 'DDR2 write buffer empty'),
               'ddr2_calib_done' : (0x94, 1, 2, 2,  'ro', 'DDR2 calibration done'),
               'ddr2_sm_dbg'     : (0x95, 1, 7, 0,  'ro', 'DDR2 state machine debug'),
               
               'version_fpga'    : (0xfc, 2, 15, 0, 'ro', 'FPGA version number'),
               'version_machine' : (0xfe, 2, 15, 0, 'ro', 'Machine type code'),
               'fpga_serial'     : (0x38, 7, 55, 0, 'ro', 'FPGA serial number'),
               }

# fields of kovan_cmds
kcmd_addr = 0
kcmd_len = 1
kcmd_msb = 2
kcmd_lsb = 3
kcmd_mode = 4
kcmd_desc = 5

def kovanSet(register, value):
    try:
        desc = kovan_cmds[register]
    except KeyError, e:
        print "unknown register " + register + " requested in kovanSet"
        return
    
    if desc[kcmd_mode] != 'rw':
        print "Warning: attempting write to read-only register " + desc[kcmd_desc]

    # retrieve original value, if we don't consume the whole bitfield
    val = 0
    if (desc[kcmd_msb] - desc[kcmd_lsb] + 1) != (8 * desc[kcmd_len]):
        val = kovanGetRaw(register)

    # compute a mask
    mask = 0
    for i in range(desc[kcmd_lsb], desc[kcmd_msb] + 1):
        mask <<= 1
        mask |= 1
    mask <<= desc[kcmd_lsb]

    val &= ~mask
    
    val |= ((value << desc[kcmd_lsb]) & mask)
    
    obuf = []
    while val > 0:
        obuf.append(val & 0xFF)
        val >>= 8
    if len(obuf) == 0:
        obuf = [0]

    assert len(obuf) <= desc[kcmd_len], 'computed obuf is longer than command length'

    i2c_write(desc[kcmd_addr], obuf)

# masks and shifts value
def kovanGet(register):
    try:
        desc = kovan_cmds[register]
    except KeyError, e:
        print "unknown register " + register + " requested in kovanSet"
        return
    val = kovanGetRaw(register)

    # compute a mask
    mask = 0
    for i in range(desc[kcmd_lsb], desc[kcmd_msb] + 1):
        mask <<= 1
        mask |= 1
    mask <<= desc[kcmd_lsb]

    val &= mask

    val >>= desc[kcmd_lsb]
    return val


# returns unshifted result from i2c read of the block
def kovanGetRaw(register):
    try:
        desc = kovan_cmds[register]
    except KeyError, e:
        print "unknown register " + register + " requested in kovanSet"
        return

    val = 0
    buf = i2c_read(desc[kcmd_addr], desc[kcmd_len])
    for i in range(len(buf) -1 , -1, -1):
        val <<= 8
        val |= buf[i]

    return val


def test_kovanSet():
    kovan_cmds['test_partial_mask1'] = (0x78, 1, 5, 2, 'rw', 'test partial masking')
    kovan_cmds['test_partial_mask2'] = (0x78, 1, 7, 0, 'rw', 'test full masking')

    print "test partial masking within one byte"
    testval = 0
    kovanSet('test_partial_mask2', testval)
    ret = kovanGet('test_partial_mask2')
    assert ret == testval, 'test prep failed' 

    # test partial masking with 0 in the background
    testval = 0xb
    kovanSet('test_partial_mask1', testval)
    ret = kovanGet('test_partial_mask1')
    assert ret == testval, 'partial mask 1 failed'
    ret = kovanGetRaw('test_partial_mask1')
    assert ret == (testval << 2), 'partial mask 1 failed'

    testval = 0xff
    kovanSet('test_partial_mask2', testval)
    ret = kovanGet('test_partial_mask2')
    assert ret == testval, 'test prep failed' 

    # test partial masking with 0xff in the background
    testval = 0x6
    kovanSet('test_partial_mask1', testval)
    ret = kovanGet('test_partial_mask1')
    assert ret == testval, 'partial mask 1 failed'
    ret = kovanGetRaw('test_partial_mask1')
    # value should be 1101 1011 = 0xDB
    assert ret == 0xDB, 'partial mask 1 failed'

    print "test multi-byte values"
    kovan_cmds['test_multi1'] = (0x79, 3, 23, 0, 'rw', '3-byte test register')
    testval = 0x92CB0F
    kovanSet('test_multi1', testval)
    ret = kovanGet('test_multi1')
    assert ret == testval, 'basic multi-byte value test failed'
    
    kovan_cmds['test_byteorder1'] = (0x79, 1, 7, 0, 'rw', 'lsb of 3-byte test')
    ret = kovanGet('test_byteorder1')
    assert ret == (testval & 0xff), 'multi-byte value endianess failed'

    # probably should add a test to test multi-byte partial masking too...

    print "test one-bit changes"
    kovan_cmds['test_onebit'] = (0x7c, 1, 2, 2, 'rw', '1-bit change test')
    kovan_cmds['test_onebitsetup'] = (0x7c, 1, 7, 0, 'rw', 'setup for 1-bit change')
    testval = 0x69
    kovanSet('test_onebitsetup', testval)
    ret = kovanGet('test_onebitsetup')
    assert ret == testval, 'setup for onebit test failed'

    kovanSet('test_onebit', 1)
    ret = kovanGet('test_onebit')
    assert ret == 1, 'onebit test failed'
    ret = kovanGet('test_onebitsetup')
    assert ret == 0x69 | 0x2, 'onebit test failed'

    kovanSet('test_onebit', 0)
    ret = kovanGet('test_onebit')
    assert ret == 0, 'onebit test failed'
    ret = kovanGet('test_onebitsetup')
    assert ret == 0x69, 'onebit test failed'

def dumpKovanRegs():
#    import pdb; pdb.set_trace()
    namelist = kovan_cmds.keys()
    namelist.sort()
    for regname in namelist:
        desc = kovan_cmds[regname]
        ret = kovanGet(regname)
        print '0x' + int2base(ret,16) + ': ' + regname + ' - ' + desc[kcmd_desc]

def setDefaults():
    kovanSet('dig_out_val', 0x0)

def isData():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

def interact():
    while True:
        cmd = ''
        if isData():
            cmd = sys.stdin.read(1)
        if cmd == 'q':
            break
        elif cmd == 'D':
            dumpKovanRegs()

def printHelp():
    print sys.argv[0] + " [cmd] [args...]"
    print "where cmd is: "
    print "? --help            prints this help"
    print "D --dump            dumps all defined kovan FPGA control registers"
    print "--unit-tests        run unit tests (development only)x"
    print "\nOr you may use any of these direct commands:"
    print "providing an argument writes that value, otherwise, it will read."
    cmds = kovan_cmds.keys()
    cmds.sort()
    for name in cmds:
        print name + " "*(20 - len(name)) + kovan_cmds[name][kcmd_desc]


alltests = [ locals()[t] for t in sorted(locals()) if t.startswith("test_") ]

def runTests():
    for t in alltests:
        print '-'*50
        print t
        result = t()

### beginning of the main code
# runTests()   # now called as a command line argument

setDefaults()

### setup interaction to be canonical mode
if( len(sys.argv) < 2 ):
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        interact()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

else:
    canonical = False

    cmd = sys.argv[1]
    if cmd == '--help':
        print "Usage: "
        printHelp()
    elif cmd == 'D' or cmd == '--dump':
        dumpKovanRegs()
    elif cmd == '--unit-tests':
        print "running unit tests"
        runTests()
    else:
        if sys.argv[1] in kovan_cmds:
            if len(sys.argv) == 2:
                ret = kovanGet(sys.argv[1])
                print sys.argv[1] + " = 0x" + int2base(ret, 16)
            else:
                kovanSet(sys.argv[1], int(sys.argv[2]))
        else:
            print "Command " + cmd + " not recognized"
            printHelp()


