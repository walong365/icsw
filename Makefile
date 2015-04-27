###############################################################################
# Paths
###############################################################################
# System
SYSCONF=/etc/sysconfig
KERNEL_CONFIGS=/usr/src/configs/
INIT=/etc/init.d
PROFDIR=/etc/profile.d

VERSION=$${VERSION}
RELEASE=$${RELEASE}

# ICSW
ICSW_BASE=/opt/cluster/
ICSW_ETC=${ICSW_BASE}/etc
ICSW_SHARE=${ICSW_BASE}/share
ICSW_BIN=${ICSW_BASE}/bin
ICSW_SBIN=${ICSW_BASE}/sbin
ICSW_SGE=${ICSW_BASE}/sge
ICSW_PIS=${ICSW_SBIN}/pis
ICSW_TFTP=/opt/cluster/system/tftpboot

CONFDIR_HM=${SYSCONF}/host-monitoring.d
LOCALBIN=/usr/local/bin
LOCALSBIN=/usr/local/sbin
META_DIR=/var/lib/meta-server
PIP_BIN=/opt/python-init/bin/pip
MOTHER_DIR=${ICSW_SHARE}/mother
NGINX_CONF=/etc/nginx/sites-enabled/localhost
PREFIX_PYTHON3=/opt/python3-init
PREFIX_PYTHON=/opt/python-init
PYTHON_LIB_LD=${PREFIX_PYTHON}/lib
PYTHON_SITE=${PREFIX_PYTHON}/lib/python2.7/site-packages
SCRIPTDIR=/usr/bin
USRSBIN=/usr/sbin
VARDIR=/var/lib/cluster/package-client

# list of target systems
TARGET_SYS_LIST=snmp_relay cluster_config_server logcheck_server cluster_server discovery_server rrd_grapher logging_server rms host_monitoring collectd mother package_install/server package_install/client meta_server md_config_server

SGE_FILES=sge_editor_conf.py modify_sge_config.sh add_logtail.sh sge_request sge_qstat create_sge_links.py build_sge6x.sh

###############################################################################
# Programs
###############################################################################
INSTALL=install
INSTALL_OPTS=-p
PYTHON=python-init
LN=ln

###############################################################################
# Dynamic settings
###############################################################################
ifeq ($(shell getconf LONG_BIT), 64)
    LIB_DIR=lib64
else
    LIB_DIR=lib
endif

STONITH_DIR:=/usr/${LIB_DIR}/stonith/plugins/external

ifneq ($(wildcard /etc/debian_version), )
    WWW_USER=www-data
    WWW_GROUP=www-data
    WEB_PREFIX=/var/www/
    DIST_TYPE:=debian
    WSGI_INI:=webfrontend.wsgi.ini-deb
else
    ifeq ($(findstring SuSE-release, $(wildcard /etc/*)), )
        WWW_USER=apache
        WWW_GROUP=apache
        WEB_PREFIX=/var/www/
        DIST_TYPE:=centos
        WSGI_INI:=webfrontend.wsgi.ini-centos
    else
         WWW_USER=wwwrun
         WWW_GROUP=www
         WEB_PREFIX=/srv/www/
         SUSE_MAJOR:=$(shell grep VERSION /etc/SuSE-release | cut -d '=' -f 2 | sed 's/ *//g' | cut -d '.' -f 1)
         SUSE_MINOR:=$(shell grep VERSION /etc/SuSE-release | cut -d '=' -f 2 | sed 's/ *//g' | cut -d '.' -f 2)
         SUSE_FULL:=${SUSE_MAJOR}${SUSE_MINOR}
         DIST_TYPE:=suse
         WSGI_INI:=webfrontend.wsgi.ini-suse
    endif
endif

###############################################################################
# Various settings
###############################################################################
VERSION_SYSLINUX=6.02
MEMTEST_VERSION=86+-5.01

###############################################################################
# Targets
###############################################################################

build:
	${MAKE} -C c_progs_collectd
	${MAKE} -C c_progs
	${MAKE} -C c_clients
	${PYTHON} ./setup.py build
	tar --transform s:^.*/:: -xjf syslinux-${VERSION_SYSLINUX}.tar.bz2 \
		syslinux-${VERSION_SYSLINUX}/bios/gpxe/gpxelinux.0 \
		syslinux-${VERSION_SYSLINUX}/bios/core/lpxelinux.0 \
		syslinux-${VERSION_SYSLINUX}/bios/core/pxelinux.0 \
		syslinux-${VERSION_SYSLINUX}/bios/memdisk/memdisk \
		syslinux-${VERSION_SYSLINUX}/bios/com32/lib/libcom32.c32 \
		syslinux-${VERSION_SYSLINUX}/bios/com32/elflink/ldlinux/ldlinux.c32 \
		syslinux-${VERSION_SYSLINUX}/bios/com32/mboot/mboot.c32
	unzip memtest*zip

install:
	# stonith from init-ha-addons
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${STONITH_DIR}
	${INSTALL} ${INSTALL_OPTS} ha-addons/ibmbcs ${DESTDIR}/${STONITH_DIR}
	# Copy the main source code
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/graphs
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/etc/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_ETC}/servers.d
	${INSTALL} ${INSTALL_OPTS} opt/cluster/etc/servers.d/*.xml ${DESTDIR}/${ICSW_ETC}/servers.d
	# setup.py
	${PYTHON} ./setup.py install --root="${DESTDIR}" --install-scripts=${ICSW_BIN}
	rm -f ${DESTDIR}/${PYTHON_SITE}/*.egg*
	# status and pci.ids
	${INSTALL} ${INSTALL_OPTS} configs/rc.status ${DESTDIR}/etc/rc.status_suse
	${INSTALL} ${INSTALL_OPTS} configs/pci.ids ${DESTDIR}/${PYTHON_SITE}/
	# Makefiles
	${MAKE} -C c_progs DESTDIR=${DESTDIR} install
	${MAKE} -C c_clients DESTDIR=${DESTDIR} install
	# INSTALL to ICSW_SBIN
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_PIS}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${LOCALSBIN}
	for file in log_error.py logging-client.py collclient.py ; do \
		${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_SBIN}; \
	done
	${INSTALL} ${INSTALL_OPTS} logwatch.py ${DESTDIR}/${ICSW_SBIN}
	${INSTALL} ${INSTALL_OPTS} packagestatus.sh ${DESTDIR}/${ICSW_SBIN}
	for file in install_package.py package_status.py make_package.py insert_package_info.py ; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_SBIN}; \
	done
	cp -a c_progs_collectd/send_collectd_zmq ${DESTDIR}/${ICSW_SBIN}
	${INSTALL} ${INSTALL_OPTS} clustershell ${DESTDIR}/${ICSW_SBIN}
	for name in fetch_ssh_keys.py ; do \
	    ${INSTALL} ${INSTALL_OPTS} $${name} ${DESTDIR}/${ICSW_SBIN}; \
	done
	for script in tls_verify.py logscan/openvpn_scan.py ; do \
	    ${INSTALL} ${INSTALL_OPTS} $$script ${DESTDIR}/${ICSW_SBIN}; \
	done
	for file in force_redhat_init_script.sh lse check_rpm_lists.py; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_SBIN}/$${file}; \
	done
	for shf in migrate_to_django restore_database remove_noctua remove_noctua_simple ; do  \
	    cp -a tools/$${shf}.sh ${DESTDIR}/${ICSW_SBIN}; \
	done
	for pyf in db_magic check_local_settings create_django_users setup_cluster restore_user_group fix_models ; do \
	    ${INSTALL} ${INSTALL_OPTS} tools/$${pyf}.py ${DESTDIR}/${ICSW_SBIN} ; \
	done
	${INSTALL} ${INSTALL_OPTS} modify_service.sh ${DESTDIR}/${ICSW_PIS}
	# Create to ICSW_SBIN
	${LN} -s ${ICSW_SBIN}/tls_verify.py ${DESTDIR}/${LOCALSBIN}/tls_verify.py
	${LN} -s ${PYTHON_SITE}/initat/cluster/manage.py ${DESTDIR}/${ICSW_SBIN}/clustermanage.py
	# ICSW_BIN
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INIT}
	${INSTALL} ${INSTALL_OPTS} icinga_scripts/check_icinga_cluster.py ${DESTDIR}/${ICSW_BIN}
	install ${INSTALL_OPTS} set_passive_checkresult.py ${DESTDIR}/${ICSW_BIN}
	cp -a cdfetch.py  ${DESTDIR}${ICSW_BIN}
	for file in license_progs loadsensor ; do \
	    install ${INSTALL_OPTS} $$file.py ${DESTDIR}${ICSW_BIN}; \
	done
	cp -a tools/modify_object.py ${DESTDIR}/${ICSW_BIN}
	if [ "${LIB_DIR}" = "lib64" ] ; then \
	    tar xzf lmutil-x64_lsb-11.12.1.0v6.tar.gz ; \
	    ${INSTALL} ${INSTALL_OPTS} lmutil ${DESTDIR}${ICSW_BIN}/lmutil; \
	else \
	    tar xzf lmutil-i86_lsb-11.12.1.0v6.tar.gz ; \
	    ${INSTALL} ${INSTALL_OPTS} lmutil ${DESTDIR}${ICSW_BIN}/lmutil; \
	fi
	${INSTALL} ${INSTALL_OPTS} sgestat.py ${DESTDIR}/${ICSW_BIN}
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${ICSW_BIN}/populate_ramdisk_local.py
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${ICSW_BIN}/copy_local_kernel.sh
	${LN} -s ${ICSW_BIN}/ics_tools.sh ${DESTDIR}/${INIT}/
	${LN} -s ${PYTHON_SITE}/send_mail.py ${DESTDIR}/${ICSW_BIN}/
	${LN} -s ./compile_openmpi.py ${DESTDIR}/${ICSW_BIN}/compile_mpich.py
	# /etc/init.d/
	${INSTALL} ${INSTALL_OPTS} loadmodules ${DESTDIR}/${INIT}/loadmodules
	${INSTALL} ${INSTALL_OPTS} init-license-server.rc ${DESTDIR}/${INIT}/init-license-server
	${INSTALL} ${INSTALL_OPTS} init_scripts/hoststatus.rc ${DESTDIR}/${INIT}/hoststatus
	${INSTALL} ${INSTALL_OPTS} init_scripts/meta-server ${DESTDIR}/${INIT}/meta-server
	${INSTALL} ${INSTALL_OPTS} init_scripts/logging-server ${DESTDIR}/${INIT}/logging-server
	# SGE stuff ICSW_SGE
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SGE}/init.d
	for name in sgemaster sgeexecd ; do \
	    ${INSTALL} ${INSTALL_OPTS} $$name ${DESTDIR}${ICSW_SGE}/init.d; \
	done
	for file in ${SGE_FILES} ; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_SGE}; \
	done
	for file in proepilogue.py qlogin_wrapper.sh sge_starter.sh; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}${ICSW_SGE}; \
	done
	${INSTALL} ${INSTALL_OPTS} batchsys.sh_client ${DESTDIR}/${ICSW_SGE}
	echo ${SGE_FILES} > ${DESTDIR}/${ICSW_SGE}/.sge_files
	echo "proepilogue.py qlogin_wrapper.sh sge_starter.sh" > ${DESTDIR}/${ICSW_SGE}/.party_files
	# /usr/sbin (mostly rc* files)
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}${USRSBIN}
	${LN} -s ${INIT}/meta-server ${DESTDIR}${USRSBIN}/rcmeta-server
	${LN} -s ${INIT}/logging-server ${DESTDIR}${USRSBIN}/rclogging-server
	${LN} -s ${INIT}/hoststatus ${DESTDIR}${USRSBIN}/rchoststatus
	${LN} -s ${INIT}/loadmodules ${DESTDIR}${USRSBIN}/rcloadmodules
	${LN} -s ${INIT}/init-license-server ${DESTDIR}${USRSBIN}/rcinit-license-server
	# SYSCONF
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/cluster
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/init-license-server.d
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/licenses
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/logging-server.d
	touch ${DESTDIR}/etc/sysconfig/cluster/.disable_rrdcached_start
	cp -a db.cf ${DESTDIR}/etc/sysconfig/cluster/db.cf.sample
	${INSTALL} ${INSTALL_OPTS} logging-server.cf ${DESTDIR}/${SYSCONF}/logging-server
	${INSTALL} ${INSTALL_OPTS} configs/host-monitoring ${DESTDIR}/${SYSCONF}/host-monitoring
	${INSTALL} ${INSTALL_OPTS} configs/host-relay ${DESTDIR}/${SYSCONF}/host-relay
	touch ${DESTDIR}/${SYSCONF}/logging-server.d/tail
	${INSTALL} ${INSTALL_OPTS} init-license-server.cf ${DESTDIR}/${SYSCONF}/init-license-server
	${INSTALL} ${INSTALL_OPTS} configs/mother.cf ${DESTDIR}/${SYSCONF}/mother
	${INSTALL} ${INSTALL_OPTS} logcheck-server.cf ${DESTDIR}/${SYSCONF}/logcheck-server
	install ${INSTALL_OPTS} md-config-server.cf ${DESTDIR}/${SYSCONF}/md-config-server
	${INSTALL} ${INSTALL_OPTS} test_license ${DESTDIR}/${SYSCONF}/init-license-server.d
	${INSTALL} ${INSTALL_OPTS} discovery-server.cf ${DESTDIR}/${SYSCONF}/discovery-server
	${INSTALL} ${INSTALL_OPTS} cluster-config-server.cf ${DESTDIR}/${SYSCONF}/cluster-config-server
	# /usr/local/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/local/bin
	for link_source in sgenodestat sgejobstat sjs sns ; do \
	    ${LN} -s ${ICSW_BIN}/sgestat.py ${DESTDIR}/usr/local/bin/$$link_source; \
	done
	# /usr/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/bin
	${LN} -s ${ICSW_BIN}/load_firmware.sh ${DESTDIR}/usr/bin/load_firmware.sh
	# /opt/cluster/lcs
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/lcs
	cp -a opt/cluster/lcs/* ${DESTDIR}${ICSW_BASE}/lcs
	# mibs
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SHARE}/mibs/cluster
	${INSTALL} ${INSTALL_OPTS} mibs/powernet385-mib ${DESTDIR}/${ICSW_SHARE}/mibs/cluster
	${INSTALL} ${INSTALL_OPTS} mibs/powernet396-mib ${DESTDIR}/${ICSW_SHARE}/mibs/cluster
	${INSTALL} ${INSTALL_OPTS} mibs/mmblade-mib ${DESTDIR}/${ICSW_SHARE}/mibs/cluster
	${INSTALL} ${INSTALL_OPTS} mibs/eonstore-mib ${DESTDIR}/${ICSW_SHARE}/mibs/cluster
	# /opt/cluster/share/mother
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} *pxelinux.0 ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} *.c32 ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} memtest${MEMTEST_VERSION}.iso ${DESTDIR}/${MOTHER_DIR}
	${INSTALL} ${INSTALL_OPTS} memdisk ${DESTDIR}/${MOTHER_DIR}/syslinux
	# examples
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SHARE}/examples/sge_licenses
	cp -a examples/* ${DESTDIR}${ICSW_SHARE}/examples/sge_licenses
	# /opt/cluster/share
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/share/cert/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/share/webcache/
	mkdir -p ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher
	mkdir -p ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher/color_rules.d
	mkdir -p ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher/color_tables.d
	cp -a color_rules.xml ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher
	cp -a color_tables.xml ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher 
	${INSTALL} ${INSTALL_OPTS} cert/* ${DESTDIR}/opt/cluster/share/cert
	# Various python files
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PROFDIR}
	cp -a cluster.schema ${DESTDIR}/opt/cluster/share
	${INSTALL} ${INSTALL_OPTS} batchsys.sh_client ${DESTDIR}/${PROFDIR}/batchsys.sh
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${KERNEL_CONFIGS}
	${INSTALL} ${INSTALL_OPTS} src/kcompile ${DESTDIR}/${KERNEL_CONFIGS}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/log/hosts
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_TFTP}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${VARDIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/lib/logging-server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/log/cluster/sockets
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${META_DIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALL_OPTS} configs/remote_ping.test ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALL_OPTS} configs/host-monitoring ${DESTDIR}/${SYSCONF}/host-monitoring
	# uwsgi 
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}${ICSW_ETC}/uwsgi
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend-common.include ${DESTDIR}${ICSW_ETC}/uwsgi/
	${INSTALL} ${INSTALL_OPTS} nginx/${WSGI_INI} ${DESTDIR}${ICSW_ETC}/uwsgi/webfrontend.wsgi.ini
	# nginx
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend.conf ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend.nsconf ${DESTDIR}/${NGINX_CONF}
	# filewatcher
	${INSTALL} ${INSTALL_OPTS} scripts/register_file_watch ${DESTDIR}/${SCRIPTDIR}
	${INSTALL} ${INSTALL_OPTS} scripts/unregister_file_watch ${DESTDIR}/${SCRIPTDIR}
	./init_proprietary.py ${DESTDIR}
	# check scripts
	${LN} -s ${PYTHON_SITE}/initat/tools/check_scripts.py ${DESTDIR}/${ICSW_SBIN}/
	${LN} -s ${PYTHON_SITE}/initat/tools/check_scripts.py ${DESTDIR}/${ICSW_SBIN}/icsw
	# remove deprecated
	rm -rf ${DESTDIR}/${PYTHON_SITE}/initat/host_monitoring/modules/deprecated
	# remove pyc
	find ${DESTDIR}/${PYTHON_SITE} -iname "*.pyc" -exec rm {} \;
	# create version files
	./create_version_file.py --version ${VERSION} --release ${RELEASE} --target ${DESTDIR}/${PYTHON_SITE}/initat/client_version.py ; \
	./create_version_file.py --version ${VERSION} --release ${RELEASE} --target ${DESTDIR}/${PYTHON_SITE}/initat/server_version.py ; \

clean:
	rm -f gpxelinux.0
	rm -f ldlinux.c32
	rm -f libcom32.c32
	rm -f lmutil
	rm -f lpxelinux.0
	rm -f mboot.c32
	rm -f memdisk
	rm -f memtest86+-5.01.iso
	make -C c_progs_collectd clean
	make -C c_progs clean
	make -C c_clients clean
	${PYTHON} ./setup.py clean
	rm -rf build

###############################################################################
# package-knife specific targets
###############################################################################

rpm_src_objs:
	@echo ${rpm_src_objs}

pkgname:
	@echo ${PKGNAME}

full_name:
	@echo ${PKGNAME}-${VERSION}-${RELEASE}

version:
	@echo ${VERSION}

release:
	@echo ${RELEASE}

.PHONY: build install clean rpm_src_objs pkgname full_name version release
