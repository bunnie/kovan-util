#!/usr/bin/python

#####
# kovan robotics platform demo program
####

import sys
import string
import fcntl
import subprocess
from struct import *
from ctypes import *
import termios
import select
import tty

####### constants
latestVersion = 3

# servo constants
timediv = 1.0 / 13000000  # time granularity of servo counter, 13 MHz period clock
servo_period_ = 0.02
servo_zero_ = 0.0015
servo_max_ = 0.002
servo_min_ = 0.001

servo_period = int(servo_period_ / timediv)
servo_zero = int(servo_zero_ / timediv)
servo_max = int(servo_max_ / timediv)
servo_min = int(servo_min_ / timediv)

# motor constants
mot_baseclk = 208000000 / 4096  # 208MHz base clock for motor
mot_target_rate = 10000 # 10 kHz target PWM period

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
               'ana_pu'          : (0x43, 1, 7, 0, 'rw', 'analog pull-up enables'),
               'glbl_reset_edge' : (0x45, 1, 2, 2, 'rw', 'reset kovan state machines'),
               'dig_sample'      : (0x45, 1, 1, 1, 'rw', 'sample digital input'),
               'dig_update'      : (0x45, 1, 0, 0, 'rw', 'update shift chain values'),
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
               'shift_test'      : (0x20, 5, 39, 0, 'ro', 'shift test register'),
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

def dutyFromPercent(percentage):
    return int( (percentage / 100.0) * 4095 )

def driveCode(code):
    retval = 0
    for i in range (3, -1, -1):
        retval = retval << 2
        if code[i] == 'f':
            retval |= 0x2
        elif code[i] == 'r':
            retval |= 0x1
        elif code[i] == 'x':  # short stop
            retval |= 0x3
        else:
            retval |= 0

    return retval

def setDefaults():
    kovanSet('dig_out_val', 0x0)
    kovanSet('dig_pu', 0x0)
    kovanSet('dig_oe', 0x0)
    kovanSet('ana_pu', 0x0)
    kovanSet('mot_allstop', 1)
    kovanSet('mot_drive_code', driveCode(['s','s','s','s']))
    kovanSet('servo_pwm_period', servo_period)
    kovanSet('servo0_pwm_pulse', servo_zero)
    kovanSet('servo1_pwm_pulse', servo_zero)
    kovanSet('servo2_pwm_pulse', servo_zero)
    kovanSet('servo3_pwm_pulse', servo_zero)
    mot_pwm_divider = (mot_baseclk - 2 * mot_target_rate) / mot_target_rate
    assert mot_pwm_divder > 0, 'motor PWM divider is negative'
    kovanSet('mot_pwm_div', mot_pwm_divider)
    kovanSet('mot_pwm_duty', dutyFromPercent(100))

def isData():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

def printAdc(cmd):
    anapu = kovanGet('ana_pu')
    adcChan = kovanGet('adc_chan')
    if cmd == '1':
        if adcChan > 0:
            adcChan = adcChan - 1
    elif cmd == '2':
        if adcChan < 15:
            adcChan = adcChan + 1
    elif cmd == 'p':
        if adcChan > 7:
            if (anapu >> (adcChan - 8)) & 0x1:
                anapu = anapu & ~(1 << (adcChan - 8))
            else:
                anapu = anapu | (1 << (adcChan - 8))

    kovanSet('ana_pu', anapu)
    kovanSet('dig_update', 0)
    kovanSet('dig_update', 1)
    kovanSet('dig_update', 0)
    kovanSet('adc_chan', adcChan)
    kovanSet('adc_go', 1 )
    kovanSet('adc_go', 0 )
    while kovanGet('adc_valid') == 0:
        dummy = 1  # just wait
    val = kovanGet('adc_in')
    ostr = 'ADC' + str(adcChan) + ': ' + int2base(val, 10) 
    print ostr + ' ' * (12 - len(ostr)),
    for i in range(8):
        if( anapu & 0x1 ):
            sys.stdout.write(str(i))  # get rid of trailing space :P
        else:
            sys.stdout.write('.')
        anapu = anapu >> 1
    print '    ',
    print ('#' * ((40 * val) / 1024) )

m_state = ['s','s','s','s']
m_sel = 0
m_speed = 100
m_allstop = 0
def motorTest(cmd):
    global m_state
    global m_sel
    global m_speed
    global m_allstop
    if cmd >= '1' and cmd <= '4':
        m_sel = (int(cmd) - 1)
    elif cmd == ',':
        if m_speed >= 0:
            m_speed = m_speed - 1
    elif cmd == '<':
        if m_speed >= 10:
            m_speed = m_speed - 10
        else:
            m_speed = 0
    elif cmd == '.':
        if m_speed < 100:
            m_speed = m_speed + 1
    elif cmd == '>':
        if m_speed < 90:
            m_speed = m_speed + 10
        else:
            m_speed = 100
    elif cmd == 'x':
        m_allstop = 0 if m_allstop else 1
    elif cmd == 'f':
        m_state[m_sel] = 'f'
    elif cmd == 'r':
        m_state[m_sel] = 'r'
    elif cmd == 's':
        m_state[m_sel] = 's'
    elif cmd == 'b':
        m_state[m_sel] = 'x'

    kovanSet('mot_pwm_duty', dutyFromPercent(m_speed))
    kovanSet('mot_allstop', m_allstop)
    kovanSet('mot_drive_code', driveCode(m_state))

    if m_allstop == 1:
        print 'speed: all stopped ',
    else:
        print 'speed: ' + str(m_speed) + ' ',

    for i in range(4):
        if i == m_sel:
            sys.stdout.write('>')
        else:
            sys.stdout.write(' ')
        print  m_state[i],

    print ' '

# setup servo angle tracking state
s_state = [180, 180, 180, 180]
s_sel = 0
def servoTest(cmd):
    global s_state
    global s_sel

    if cmd >= '1' and cmd <= '4':
        s_sel = (int(cmd) - 1)
    elif cmd == ',':
        if s_state[s_sel] >= 0:
            s_state[s_sel] = s_state[s_sel] - 1
    elif cmd == '<':
        if s_state[s_sel] >= 10:
            s_state[s_sel] = s_state[s_sel] - 10
        else:
            s_state[s_sel] = 0
    elif cmd == '.':
        if s_state[s_sel] < 360:
            s_state[s_sel] = s_state[s_sel] + 1
    elif cmd == '>':
        if s_state[s_sel] < 350:
            s_state[s_sel] = s_state[s_sel] + 10
        else:
            s_state[s_sel] = 359
    elif cmd == '0':
        s_state[s_sel] = 180

    key = 'servo' + str(s_sel) + '_pwm_pulse'
    servo_setting = int((servo_max - servo_min) * (s_state[s_sel] / 360.0)) + servo_min
    kovanSet(key, servo_setting)

    for i in range(4):
        if i == s_sel:
            print '>',
        else:
            print ' ',
        print str(s_state[i]) + ' ' * (5 - len(str(s_state[i]))) + '|',

    print ' '

digChan = 0 # meh
def ioTest(cmd):
    global digChan
    digout = kovanGet('dig_out_val')
    digoe = kovanGet('dig_oe')
    digpu = kovanGet('dig_pu')
    digin = kovanGet('dig_in_val')
    if cmd == '+':
        if (digpu >> digChan) & 0x1:
            digpu = digpu & ~(1 << digChan)
        else:
            digpu = digpu | (1 << digChan)
    elif cmd == 'i':
        digoe = digoe & ~(1 << digChan)
    elif cmd == 'o':
        digoe = digoe | (1 << digChan)
    elif cmd == '<':
        if digChan > 0:
            digChan = digChan - 1
    elif cmd == '>':
        if digChan < 7:
            digChan = digChan + 1
    elif (cmd >= '0') and (cmd <= '7'):
        j = int(cmd)
        if( (digout >> j) & 0x1):
            digout = digout & ~(1 << j)
        else:
            digout = digout | (1 << j)

    kovanSet('dig_out_val', digout)
    kovanSet('dig_oe', digoe)
    kovanSet('dig_pu', digpu)
    kovanSet('dig_update', 1)
    kovanSet('dig_update', 0)
    kovanSet('dig_sample', 0) # capture new digital values
    kovanSet('dig_sample', 1)

    st = kovanGet('shift_test')
    print '0x' + int2base(st, 16)
    print 'in:   ',
    for i in range(8):
        if(digin & 0x1):
            sys.stdout.write('*')
        else:
            sys.stdout.write('.')
        digin = digin >> 1

    print ' '
    print 'pu:   ',
    for i in range(8):
        if(digpu & 0x1):
            sys.stdout.write('*')
        else:
            sys.stdout.write('.')
        digpu = digpu >> 1

    print ' '
    print 'oe:   ',
    for i in range(8):
        if(digoe & 0x1):
            sys.stdout.write('o')
        else:
            sys.stdout.write('i')
        digoe = digoe >> 1

    print ' '
    print 'out:  ',
    for i in range(8):
        if(digout & 0x1):
            sys.stdout.write('*')
        else:
            sys.stdout.write('.')
        digout = digout >> 1
    print ' '

    if digChan == 0:
        print 'chan: ^      7'
    elif digChan == 7:
        print 'chan: 0      ^'
    else: 
        print 'chan: 0' + ' ' * (digChan - 1) + '^' + ' ' * (6 - digChan) + '7'

    print '\n'


def interact():
    mode = 'normal'

    while True:
        if mode == 'adc':
            printAdc(cmd)
        elif mode == 'motor':
            motorTest(cmd)
        elif mode == 'io':
            ioTest(cmd)
        elif mode == 'servo':
            servoTest(cmd)

        cmd = ''
        if isData():
            cmd = sys.stdin.read(1)
            
        if mode == 'adc':
            if cmd == 'q':
                mode = 'normal'
                print "Exiting interactive ADC mode"
                continue

        if mode == 'motor':
            if cmd == 'q':
                mode = 'normal'
                print "Exiting interactive motor mode"
                kovanSet('mot_allstop', 1)
                kovanSet('mot_drive_code', driveCode(['s','s','s','s']))
                continue

        if mode == 'io':
            if cmd == 'q':
                mode = 'normal'
                print "Exiting interactive IO mode"
                continue
            
        if mode == 'servo':
            if cmd == 'q':
                mode = 'normal'
                print "Exiting interactive servo mode"
                continue

        else: # mode == 'normal' or otherwise
            if cmd == 'q':
                break
            elif cmd == '?':
                printInteractiveHelp()
            elif cmd == 'A':
                print "Entering interactive ADC mode"
                mode = 'adc'
            elif cmd == 'M':
                print "Entering interactive motor mode"
                kovanSet('mot_allstop', 0)
                kovanSet('mot_drive_code', driveCode(['s','s','s','s']))
                mode = 'motor'
            elif cmd == 'I':
                print "Entering interactive IO mode"
                mode = 'io'
            elif cmd == 'S':
                print "Entering interactine servo mode"
                mode = 'servo'
            elif cmd == 'D':
                dumpKovanRegs()

def printInteractiveHelp():
    print "Interactive options:"
    print "D           dumps all defined kovan FPGA control registers"
    print "A           go into ADC testing mode (1/2 to change channel, p to toggle pullup)"
    print "I           go into digital IO testing mode"
    print "              0-7 to toggle ouput value"
    print "              shift + 0-7 to toggle pull-up enable"
    print "              < / > to pick direction set, i / o to set direction"
    print "M           go into motor testing mode"
    print "              1-4 to select motor channel"
    print "              f/r/s/b to control forward/reverse/stop/short break"
    print "              < / > to control speed"
    print "              x to toggle all-stop"
    print "S           go into servo testing mode"
    print "              1-4 selects servo channel"
    print "              , / . and < / > controls rotor angle; 0 returns to 0-point"

def printHelp():
    print sys.argv[0] + " [cmd] [args...]"
    print "where cmd is: "
    print "? --help            prints this help"
    print "D --dump            dumps all defined kovan FPGA control registers"
    print "--fast-charge       set fast charge mode"
    print "--trickle-charge    set trickle charge mode"
    print "--adc8-battery      set ADC8 to measure the battery"
    print "--adc8-user         set ADC8 to measure user inputs"
    print "-dw <addr> <data>   write data at addr to DDR2"
    print "-dr <addr>          read data at addr from DDR2"
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


def checkVersion():
    vers = kovanGet('version_fpga')
    if vers < latestVersion:
        print "Warning: FPGA is not latest version, expected " + str(latestVersion) + " got " + str(vers)
        
### beginning of the main code
# runTests()   # now called as a command line argument

setDefaults()

checkVersion()

### setup interaction to be canonical mode
if( len(sys.argv) < 2 ):
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        printInteractiveHelp()
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
    elif cmd == '-dw':
        addr = int(sys.argv[2],16)
        data = int(sys.argv[3],16)
        kovanSet('ddr2_test_addr', addr)
        kovanSet('ddr2_write_data', data)
        kovanSet('ddr2_rdwr', 0)
        kovanSet('ddr2_docmd', 1)
        kovanSet('ddr2_docmd', 0)
    elif cmd == '-dr':
        addr = int(sys.argv[2])
        kovanSet('ddr2_test_addr', addr)
        kovanSet('ddr2_rdwr', 1)
        kovanSet('ddr2_docmd', 1)
        kovanSet('ddr2_docmd', 0)
        data = kovanGet('ddr2_read_data')
        print '0x' + int2base(addr, 16) + ': 0x' + int2base(data,16)
    elif cmd == '--fast-charge':
        subprocess.call(['regutil', '-w', 'MFP_100=0x4c40'])
        subprocess.call(['regutil', '-w', 'GPIO4_SDR=0x10'])
        subprocess.call(['regutil', '-w', 'GPIO4_PSR=0x10'])
        """
        try:
            gpio_export = open("/sys/class/gpio/export", 'w')
            gpio_export.write('100\n')
            gpio_export.close()
        except IOError, e:
            dummy = 1
        gpio_dir = open("/sys/class/gpio/gpio100/direction", 'w')
        gpio_dir.write('out\n')
        gpio_dir.close()
        gpio_value = open("/sys/class/gpio/gpio100/value", 'w')
        gpio_value.write('0\n')
        gpio_value.close()
        """
    elif cmd == '--trickle-charge':
        subprocess.call(['regutil', '-w', 'MFP_100=0x4c40'])
        subprocess.call(['regutil', '-w', 'GPIO4_SDR=0x10'])
        subprocess.call(['regutil', '-w', 'GPIO4_PCR=0x10'])
    elif cmd == '--adc8-battery':
        subprocess.call(['regutil', '-w', 'MFP_79=0xac80'])
        subprocess.call(['regutil', '-w', 'GPIO3_SDR=0x8000'])
        subprocess.call(['regutil', '-w', 'GPIO3_PSR=0x8000'])
    elif cmd == '--adc8-user':
        subprocess.call(['regutil', '-w', 'MFP_79=0xac80'])
        subprocess.call(['regutil', '-w', 'GPIO3_SDR=0x8000'])
        subprocess.call(['regutil', '-w', 'GPIO3_PCR=0x8000'])
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


