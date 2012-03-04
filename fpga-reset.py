#!/usr/bin/python

import sys
import string
import fcntl

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

fpgaReset()
