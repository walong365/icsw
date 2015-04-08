PREFIX_CLUSTER=/opt/cluster

ifeq ($(shell getconf LONG_BIT), 64) 
LIB_DIR=lib64
else
LIB_DIR=lib
endif

INSTALL=install
INSTALLOPTS=-p
INDENT_OPTIONS=-linux --no-tabs --indent-level4

.SUFFIXES:
.SUFFIXES: .o .c
.PHONY: clean all indent

comp=gcc
progs=tell_mother hoststatus tell_mother_zmq hoststatus_zmq

default: all

clean:
	rm -f *.o $(progs)

all: $(progs)

indent:
	indent tell_mother.c $(INDENT_OPTIONS)
	indent hoststatus.c $(INDENT_OPTIONS)
	indent hoststatus_zmq.c $(INDENT_OPTIONS)
	indent tell_mother_zmq.c $(INDENT_OPTIONS)

tell_mother: tell_mother.o
	$(comp) tell_mother.o -o tell_mother
	strip tell_mother

hoststatus: hoststatus.o
	$(comp) hoststatus.o -o hoststatus
	strip hoststatus

tell_mother_zmq: tell_mother_zmq.o
	export LDFLAGS="-Xlinker -rpath=${PREFIX_CLUSTER}/$(LIB_DIR) "; \
	$(comp) tell_mother_zmq.o -o tell_mother_zmq -L ${PREFIX_CLUSTER}/${LIB_DIR} -lzmq;  \
	strip tell_mother_zmq

hoststatus_zmq: hoststatus_zmq.o
	export LDFLAGS="-Xlinker -rpath=${PREFIX_CLUSTER}/$(LIB_DIR) "; \
	$(comp) hoststatus_zmq.o -o hoststatus_zmq -L ${PREFIX_CLUSTER}/${LIB_DIR} -lzmq ; \
	strip hoststatus_zmq

%.o: %.c parse_uuid.c
	$(comp) -I${PREFIX_CLUSTER}/include $< -O3 -c -o $@

install: hoststatus tell_mother tell_mother_zmq hoststatus_zmq
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} hoststatus ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} hoststatus_zmq ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} tell_mother ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} tell_mother_zmq ${DESTDIR}/${PREFIX_CLUSTER}/sbin

