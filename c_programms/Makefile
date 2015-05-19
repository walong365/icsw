###############################################################################
# Tools and options
###############################################################################
INSTALL=install
INSTALL_OPTS=-p
CC=gcc
INDENT=indent
INDENT_OPTIONS=-linux --no-tabs --indent-level4

###############################################################################
# Directories
###############################################################################
ICSW_BASE=/opt/cluster
ICSW_SBIN=$(ICSW_BASE)/sbin
ifeq ($(shell getconf LONG_BIT), 64)
LIB_DIR=lib64
else
LIB_DIR=lib
endif

###############################################################################
# Files
###############################################################################
progs=csnmpclientzmq ccollclientzmq tell_mother hoststatus tell_mother_zmq hoststatus_zmq send_collectd_zmq

###############################################################################
# Targets
###############################################################################

all: $(progs)

indent:
	$(INDENT) $(INDENT_OPTIONS) $(addsuffix .c,$(progs))

# Note: parse_uuid.c is #include'd in the *.c files
%.o: %.c parse_uuid.c
	$(CC) $< -o $@ -I$(ICSW_BASE)/include -O3 -c

%zmq: %zmq.o
	$(CC) $< -o $@ -L$(ICSW_BASE)/$(LIB_DIR) -lzmq -Xlinker -rpath=$(ICSW_BASE)/$(LIB_DIR)

%: %.o
	$(CC) $< -o $@

install: $(progs)
	$(INSTALL) $(INSTALLOPTS) -d $(DESTDIR)/$(ICSW_SBIN)
	
	# Note: -s to strip the binaries
	for prog in $(progs); do \
		$(INSTALL) $(INSTALLOPTS) -s $$prog $(DESTDIR)/$(ICSW_SBIN); \
	done

clean:
	rm -f *.o $(progs)

.PHONY: clean all indent install
