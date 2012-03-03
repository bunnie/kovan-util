SOURCES=src/jtag.c
OBJECTS=$(SOURCES:.c=.o)
EXEC=jtag-fpga-idcode
MY_CFLAGS += 
MY_LIBS += 

all: $(OBJECTS)
	$(CC) $(LIBS) $(LDFLAGS) $(OBJECTS) $(MY_LIBS) -o $(EXEC)

clean:
	rm -f $(EXEC) $(OBJECTS)

.c.o:
	$(CC) -c $(CFLAGS) $(MY_CFLAGS) $< -o $@
