include ../Makefile.globals

.SUFFIXES:
.SUFFIXES: .o .c
.PHONY: clean all

comp=gcc
progs=tell_mother hoststatus tell_mother_zmq

default: all

clean:
	rm -f *.o $(progs)

all: $(progs)

hoststatus: hoststatus.o
	$(comp) hoststatus.o -o hoststatus
	strip hoststatus

tell_mother: tell_mother.o
	$(comp) tell_mother.o -o tell_mother
	strip tell_mother

tell_mother_zmq: tell_mother_zmq.o
	$(comp) -L/opt/cluster/$(LIB_DIR)/ -lzmq tell_mother_zmq.o -o tell_mother_zmq
	strip tell_mother_zmq

%.o: %.c
	$(comp) -I${PREFIX_CLUSTER}/include $< -O3 -c -o $@

install: hoststatus tell_mother tell_mother_zmq
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} hoststatus ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} tell_mother ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} tell_mother_zmq ${DESTDIR}/${PREFIX_CLUSTER}/sbin

