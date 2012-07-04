.SUFFIXES:
.SUFFIXES: .o .c
.PHONY: clean all

comp=gcc
progs=csnmpclientzmq ccollclientzmq

ifeq ($(shell uname -m), x86_64)
        LIB_DIR=lib64
else
        LIB_DIR=lib
endif

default: all

clean:
	rm -f *.o $(progs)

all:	$(progs)

ccollclientzmq: ccollclientzmq.o
	$(comp) -L/opt/cluster/$(LIB_DIR)/ -lzmq ccollclientzmq.o -o ccollclientzmq
	strip ccollclientzmq

csnmpclientzmq: csnmpclientzmq.o
	$(comp) -L/opt/cluster/$(LIB_DIR)/ -lzmq csnmpclientzmq.o -o csnmpclientzmq
	strip csnmpclientzmq

%.o: %.c
	$(comp) $< -O1 -c -I. -I/opt/cluster/include -o $@
