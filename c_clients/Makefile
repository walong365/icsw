include ../Makefile.config

.SUFFIXES:
.SUFFIXES: .o .c
.PHONY: clean all

comp=gcc
progs=csnmpclientzmq ccollclientzmq

ifeq ($(shell getconf LONG_BIT), 64)
LIB_DIR=lib64
else
LIB_DIR=lib
endif

default: all

clean:
	rm -f *.o $(progs)

all:	$(progs)

ccollclientzmq: ccollclientzmq.o
	$(comp) -L/opt/cluster/$(LIB_DIR)/ ccollclientzmq.o -o ccollclientzmq -lzmq
	strip ccollclientzmq

csnmpclientzmq: csnmpclientzmq.o
	$(comp) -L/opt/cluster/$(LIB_DIR)/ csnmpclientzmq.o -o csnmpclientzmq -lzmq
	strip csnmpclientzmq

%.o: %.c
	$(comp) $< -O1 -c -I. -I/opt/cluster/include -o $@

install:
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${CLUSTERBIN}
	for prog in ${progs}; do \
		${INSTALL} ${INSTALLOPTS} $$prog ${DESTDIR}/${CLUSTERBIN}; \
	done

