#!/usr/bin/python

import subprocess
import re
from struct import *
import sys
from subprocess import call

def parseBitfileHeader(bitfile, fpgaType):
    # skip first three sections
    for section in range(3):
        lengthStr = bitfile.read(2)
        length = unpack('>h',lengthStr)[0]
        designName = bitfile.read(length)
        
    key = bitfile.read(1)
    if( key != 'b' ):
        sys.exit("Bifile parsing error")
    
    lengthStr = bitfile.read(2)
    length = unpack('>h',lengthStr)[0]
    fpgaName = bitfile.read(length)
    if( not re.match(fpgaType, fpgaName) ):
        sys.exit("FPGA name in bitfile does not correspond to IDCODE of FPGA on board. Aborting.")

    key = bitfile.read(1)
    if( key != 'c' ):
        sys.exit("Bifile parsing error")
    lengthStr = bitfile.read(2)
    length = unpack('>h',lengthStr)[0]
    dateCode = bitfile.read(length)
    
    key = bitfile.read(1)
    if( key != 'd' ):
        sys.exit("Bifile parsing error")
    lengthStr = bitfile.read(2)
    length = unpack('>h',lengthStr)[0]
    timeCode = bitfile.read(length)
    
    key = bitfile.read(1)
    if( key != 'e' ):
        sys.exit("Bifile parsing error")
    lengthStr = bitfile.read(4)
    length = unpack('>L',lengthStr)[0]

    print "Found bitfile for " + fpgaName + " created from " + designName.partition(';')[0] + " on " + dateCode + " at " + timeCode
    print "Data length is " + str(length) + " bytes"
    return length

idcode = subprocess.check_output("/usr/sbin/jtag-fpga-idcode")

if( re.match("24001093", idcode) ):
    try:
        bitfile = open( "/lib/firmware/kovan-lx9.bit", 'rb' )
        fpgaType = '6slx9csg324'
    except IOError, e:
        print e
        sys.exit("Aborting")
elif( re.match("34008093", idcode) ):
    try:
        bitfile = open( "/lib/firmware/kovan-lx45.bit", 'rb' )
        fpgaType = '6slx45csg324'
    except IOError, e:
        print e
        sys.exit("Aborting")
else:
    sys.exit("Unrecognized FPGA type")

try:
    fpgadev = open( "/dev/fpga", 'wb' )
except IOError, e:
    print e
    sys.exit("Can't access /dev/fpga, aborting")

try:
    length = parseBitfileHeader(bitfile, fpgaType)
except IOError, e:
    print e
    sys.exit("Error parsing headers")

try:
    # let's try the lazy method first...read it all in and blast it out
    binaryData = bitfile.read()
    bitfile.close()

    if( len(binaryData) != length ):
        print "Warning: read data from file of length " + len(binaryData) + " does not match expected length of " + str(length)

    print "Programming...",
    fpgadev.write(binaryData)
    fpgadev.close()
    print "done."
    if( re.match('6slx9csg324', fpgaType) ):
        print "Reconfiguring frame buffer for CEA 640x480 compliance after frame doubling..."
        call(['regutil', '-w', 'LCD_SPU_V_H_ACTIVE=0x00f00140'])
        call(['regutil', '-w', 'LCD_SPUT_V_H_TOTAL=0x01070190'])
        call(['regutil', '-w', 'LCD_SPU_H_PORCH=0x00180008'])
        call(['regutil', '-w', 'LCD_SPU_V_PORCH=0x00110005'])

except IOError, e:
    print e
    sys.exit("IO error programming FPGA")

