PREFIX_CLUSTER=/opt/cluster

ifeq ($(shell getconf LONG_BIT), 64) 
LIB_DIR=lib64
else
LIB_DIR=lib
endif

INSTALL=install
INSTALLOPTS=-p

.SUFFIXES:
.SUFFIXES: .o .c
.PHONY: clean all

comp=gcc
progs=send_collectd_zmq

default: all

clean:
	rm -f *.o $(progs)

all: $(progs)

send_collectd_zmq: send_collectd_zmq.o
	export LDFLAGS="-Xlinker -rpath=${PREFIX_CLUSTER}/$(LIB_DIR) "; \
	$(comp) send_collectd_zmq.o -o send_collectd_zmq -L ${PREFIX_CLUSTER}/${LIB_DIR} -lzmq;  \
	strip send_collectd_zmq

%.o: %.c parse_uuid.c
	$(comp) -I${PREFIX_CLUSTER}/include $< -O3 -c -o $@

install: send_collectd_zmq
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} send_collectd_zmq ${DESTDIR}/${PREFIX_CLUSTER}/sbin

