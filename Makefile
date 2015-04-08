###############################################################################
# Paths
###############################################################################
# System
SYSCONF=/etc/sysconfig
KERNEL_CONFIGS=/usr/src/configs/
INIT=/etc/init.d
PROFDIR=/etc/profile.d

# ICSW
ICSW_BASE=/opt/cluster/
ICSW_BIN=${ICSW_BASE}/bin
ICSW_SBIN=${ICSW_BASE}/sbin
ICSW_SGE=${ICSW_BASE}/sge
ICSW_TFTP=/opt/cluster/system/tftpboot

PYINIT_BASE=/opt/python-init/
PYINIT_SITE=/opt/python-init/lib/python2.7/site-packages/

CONFDIR_HM=${SYSCONF}/host-monitoring.d
INITAT27=${PYTHON_LIB_LD}/python2.7/site-packages/initat
INITAT=${PYTHON_LIB_LD}/python/site-packages/initat
LOCALBIN=/usr/local/bin
LOCALSBIN=/usr/local/sbin
META_DIR=/var/lib/meta-server
MOTHER_DIR=${ICSW_BASE}/share/mother
NGINX_CONF=/etc/nginx/sites-enabled/localhost
PREFIX_PYTHON3=/opt/python3-init
PREFIX_PYTHON=/opt/python-init
PYINITLIB=${PYINIT}/lib
PYINIT=/opt/python-init
PYTHON_LIB_LD=${PREFIX_PYTHON}/lib
PYTHON_SITE=${PREFIX_PYTHON}/lib/python2.7/site-packages
SBIN=/usr/sbin
SCRIPTDIR=/usr/bin
SPREFIX=${ICSW_BASE}/sbin
SYSCONF=/etc/sysconfig
USRSBIN=/usr/sbin
VARDIR=/var/lib/cluster/package-client

SGE_FILES=sge_editor_conf.py modify_sge_config.sh add_logtail.sh sge_request sge_qstat create_sge_links.py build_sge6x.sh post_install.sh

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
	${PYTHON} ./cbc-tools_setup.py build
	${PYTHON} ./meta-server_setup.py build
	${PYTHON} ./host-monitoring_setup.py build
	${PYTHON} ./python-modules-base_setup.py build
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
	# Copy the main source code
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYINIT_SITE}/
	cp -a initat ${DESTDIR}/${PYINIT_SITE}/
	# setup.py
	${PYTHON} ./cbc-tools_setup.py install --root="${DESTDIR}" --install-scripts=${ICSW_BASE}/bin
	${PYTHON} ./meta-server_setup.py install --root "${DESTDIR}"
	${PYTHON} ./host-monitoring_setup.py install --root "${DESTDIR}"
	${PYTHON} ./python-modules-base_setup.py install --root="${DESTDIR}"
	# Makefiles
	make -C c_progs DESTDIR=${DESTDIR} install
	${MAKE} -C c_clients DESTDIR=${DESTDIR} install
	# INSTALL to ICSW_SBIN
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SBIN}/pis
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${LOCALSBIN}
	for file in logging-server.py log_error.py logging-client.py ; do \
		${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_SBIN}; \
	done
	${INSTALL} ${INSTALL_OPTS} logwatch.py ${DESTDIR}/${ICSW_SBIN}
	for shf in post_install server_installed ; do \
	    ${INSTALL} ${INSTALL_OTPS} tools/$${shf}.sh ${DESTDIR}/${ICSW_BASE}/sbin/pis ; \
	done
	${INSTALL} ${INSTALL_OPTS} meta-server.py ${DESTDIR}/${SPREFIX}
	${INSTALL} ${INSTALL_OPTS} packagestatus.sh ${DESTDIR}/${SPREFIX}
	for file in install_package.py package_status.py make_package.py insert_package_info.py ; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${SPREFIX}; \
	done
	for file in package-server.py package-client.py; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${SPREFIX}; \
	done
	for file in rms-server.py ; do \
	    install ${INSTALL_OPTS} $${file} ${DESTDIR}/${SPREFIX}; \
	done
	${INSTALL} ${INSTALL_OPTS} openmpi_source_post_install.py ${DESTDIR}/${ICSW_BASE}/sbin/pis
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend_pre_start.sh ${DESTDIR}/opt/cluster/sbin
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend_post_install.sh ${DESTDIR}/opt/cluster/sbin
	cp -a rrd-grapher.py ${DESTDIR}/${ICSW_BASE}/sbin
	${INSTALL} ${INSTALL_OPTS} mother.py ${DESTDIR}/${ICSW_BASE}/sbin
	${INSTALL} ${INSTALL_OPTS} logcheck-server.py ${DESTDIR}/${ICSW_BASE}/sbin
	install ${INSTALL_OPTS} md-config-server.py ${DESTDIR}/${ICSW_BASE}/sbin
	${INSTALL} ${INSTALL_OPTS} discovery-server.py ${DESTDIR}/${ICSW_BASE}/sbin
	${INSTALL} ${INSTALL_OPTS} cluster-server.py ${DESTDIR}/${ICSW_BASE}/sbin
	cp -a c_progs_collectd/send_collectd_zmq ${DESTDIR}/${ICSW_BASE}/sbin
	cp -a collectd-init.py  ${DESTDIR}${ICSW_BASE}/sbin 
	${INSTALL} ${INSTALL_OPTS} clustershell ${DESTDIR}/${ICSW_BASE}/sbin
	for script in start_node.sh stop_node.sh check_node.sh disable_node.sh; do \
		${INSTALL} ${INSTALL_OPTS} scripts/$$script ${DESTDIR}/${ICSW_SBIN}; \
	done
	for name in cluster-config-server.py fetch_ssh_keys.py ; do \
		${INSTALL} ${INSTALL_OPTS} $${name} ${DESTDIR}/${ICSW_BASE}/sbin; \
	done
	for script in host-monitoring-zmq.py tls_verify.py snmp-relay.py logscan/openvpn_scan.py ; do \
		${INSTALL} ${INSTALL_OPTS} $$script ${DESTDIR}/${ICSW_SBIN}; \
	done
	for file in find_group_id.sh find_user_id.sh force_redhat_init_script.sh lse check_rpm_lists.py; do \
		${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_SBIN}/$${file}; \
	done
	for sbin_file in start_cluster.sh stop_cluster.sh start_server.sh stop_server.sh check_cluster.sh check_server.sh; do \
		${INSTALL} ${INSTALL_OPTS} cluster/bin/$$sbin_file ${DESTDIR}/${ICSW_SBIN}; \
	done
	for shf in migrate_to_django restore_database remove_noctua remove_noctua_simple ; do  \
	    cp -a tools/$${shf}.sh ${DESTDIR}/${ICSW_BASE}/sbin; \
	done
	for pyf in db_magic check_local_settings create_django_users setup_cluster restore_user_group fix_models ; do \
	    ${INSTALL} ${INSTALL_OPTS} tools/$${pyf}.py ${DESTDIR}/${ICSW_BASE}/sbin ; \
	done
	${INSTALL} ${INSTALL_OPTS} modify_service.sh ${DESTDIR}/${ICSW_SBIN}/pis
	${INSTALL} ${INSTALL_OPTS} get_pids_from_meta.py ${DESTDIR}/${ICSW_SBIN}/
	# Create to ICSW_SBIN
	${LN} -s host-monitoring-zmq.py ${DESTDIR}/${ICSW_SBIN}/collclient.py
	${LN} -s host-monitoring-zmq.py ${DESTDIR}/${ICSW_SBIN}/collrelay.py
	${LN} -s host-monitoring-zmq.py ${DESTDIR}/${ICSW_SBIN}/collserver.py
	${LN} -s ${ICSW_SBIN}/tls_verify.py ${DESTDIR}/${LOCALSBIN}/tls_verify.py
	${LN} -s ${PYTHON_SITE}/initat/cluster/manage.py ${DESTDIR}/${ICSW_BASE}/sbin/clustermanage.py
	${LN} -s ${ICSW_BASE}/sbin/pis/openmpi_source_post_install.py ${DESTDIR}/${ICSW_BASE}/sbin/pis/mpich_source_post_install.py
	# ICSW_BIN
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INIT}
	for file in get_cpuid.py send_command.py send_command_zmq.py ics_tools.sh ics_tools.py migrate_repos.py ; do \
		${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${ICSW_BIN}; \
	done 
	${INSTALL} ${INSTALL_OPTS} user_info.py ${DESTDIR}/${ICSW_BASE}/bin
	# pyfiles
	for bin_file in clog.py device_info.py load_firmware.sh \
		mysql_dump.sh pack_kernel.sh populate_ramdisk.py resync_config.sh \
		show_config_script.py make_image.py change_cluster_var.py ; do \
		${INSTALL} ${INSTALL_OPTS} cluster/bin/$$bin_file ${DESTDIR}/${ICSW_BASE}/bin; \
	done
	${INSTALL} ${INSTALL_OPTS} user_info.py ${DESTDIR}/${ICSW_BASE}/bin
	${INSTALL} ${INSTALL_OPTS} icinga_scripts/check_icinga_cluster.py ${DESTDIR}/${ICSW_BIN}
	${INSTALL} ${INSTALL_OPTS} license_server_tool.py ${DESTDIR}/${ICSW_BASE}/bin
	install ${INSTALL_OPTS} set_passive_checkresult.py ${DESTDIR}/${ICSW_BASE}/bin
	cp -a cdfetch.py  ${DESTDIR}${ICSW_BASE}/bin
	for file in license_progs loadsensor ; do \
	    install ${INSTALL_OPTS} $$file.py ${DESTDIR}${ICSW_BASE}/bin; \
	done
	cp -a tools/modify_object.py ${DESTDIR}/${ICSW_BASE}/bin
	if [ "${LIB_DIR}" = "lib64" ] ; then \
	    tar xzf lmutil-x64_lsb-11.12.1.0v6.tar.gz ; \
	    ${INSTALL} ${INSTALL_OPTS} lmutil ${DESTDIR}${ICSW_BASE}/bin/lmutil; \
	else \
	    tar xzf lmutil-i86_lsb-11.12.1.0v6.tar.gz ; \
	    ${INSTALL} ${INSTALL_OPTS} lmutil ${DESTDIR}${ICSW_BASE}/bin/lmutil; \
	fi
	${INSTALL} ${INSTALL_OPTS} sgestat.py ${DESTDIR}/${ICSW_BASE}/bin
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${ICSW_BASE}/bin/populate_ramdisk_local.py
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${ICSW_BASE}/bin/copy_local_kernel.sh
	${LN} -s ${ICSW_BIN}/ics_tools.sh ${DESTDIR}/${INIT}/
	${LN} -s ${PYTHON_SITE}/send_mail.py ${DESTDIR}/${ICSW_BIN}/
	${LN} -s ./compile_openmpi.py ${DESTDIR}/${ICSW_BASE}/bin/compile_mpich.py
	# /etc/init.d/
	${INSTALL} ${INSTALL_OPTS} cluster-config-server ${DESTDIR}/${INIT}/cluster-config-server
	cp -a collectd-init ${DESTDIR}/${INIT}
	${INSTALL} ${INSTALL_OPTS} discovery-server ${DESTDIR}/${INIT}/discovery-server
	${INSTALL} ${INSTALL_OPTS} logging-server.rc ${DESTDIR}/${INIT}/logging-server
	${INSTALL} ${INSTALL_OPTS} loadmodules ${DESTDIR}/${INIT}/loadmodules
	${INSTALL} ${INSTALL_OPTS} logcheck-server ${DESTDIR}/${INIT}/
	${INSTALL} ${INSTALL_OPTS} cluster-server ${DESTDIR}/${INIT}
	${INSTALL} ${INSTALL_OPTS} scripts/host-relay.rc ${DESTDIR}/${INIT}/host-relay
	${INSTALL} ${INSTALL_OPTS} scripts/host-monitoring.rc ${DESTDIR}/${INIT}/host-monitoring
	${INSTALL} ${INSTALL_OPTS} scripts/snmp-relay.rc ${DESTDIR}/${INIT}/snmp-relay
	${INSTALL} ${INSTALL_OPTS} init-license-server.rc ${DESTDIR}/${INIT}/init-license-server
	${INSTALL} ${INSTALL_OPTS} meta-server ${DESTDIR}/${INIT}
	${INSTALL} ${INSTALL_OPTS} init_scripts/hoststatus.rc ${DESTDIR}/${INIT}/hoststatus
	${INSTALL} ${INSTALL_OPTS} init_scripts/mother ${DESTDIR}${INIT}/
	${INSTALL} ${INSTALL_OPTS} init_scripts/package-server.rc ${DESTDIR}${INIT}/package-server
	${INSTALL} ${INSTALL_OPTS} init_scripts/package-client.rc ${DESTDIR}${INIT}/package-client
	cp -a rrd-grapher ${DESTDIR}/${INIT}
	install ${INSTALL_OPTS} md-config-server ${DESTDIR}/${INIT}/md-config-server
	${INSTALL} ${INSTALL_OPTS} rms-server.rc ${DESTDIR}${INIT}/rms-server
	# SGE stuff ICSW_SGE
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SGE}/init.d
	for name in sgemaster sgeexecd sgebdb ; do \
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
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/sbin
	${LN} -s ${INIT}/hoststatus ${DESTDIR}/usr/sbin/rchoststatus
	${LN} -s ${INIT}/loadmodules ${DESTDIR}/usr/sbin/rcloadmodules
	${LN} -s ${INIT}/meta-server ${DESTDIR}/usr/sbin/rcmeta-server
	${LN} -s ${INIT}/logging-server ${DESTDIR}/${USRSBIN}/rclogging-server
	${LN} -s ${INIT}/package-server ${DESTDIR}/usr/sbin/rcpackage-server
	${LN} -s ${INIT}/package-client ${DESTDIR}/usr/sbin/rcpackage-client
	${LN} -s ${INIT}/rms-server ${DESTDIR}/usr/sbin/rcrms-server
	${LN} -s ${INIT}/rrd-grapher ${DESTDIR}/usr/sbin/rcrrd-grapher
	${LN} -s ${INIT}/mother ${DESTDIR}/usr/sbin/rcmother
	${LN} -s ${INIT}/logcheck-server ${DESTDIR}/usr/sbin/rclogcheck-server
	${LN} -s ${INIT}/md-config-server ${DESTDIR}/usr/sbin/rcmd-config-server
	${LN} -s ${INIT}/init-license-server ${DESTDIR}/usr/sbin/rcinit-license-server
	${LN} -s ${INIT}/discovery-server ${DESTDIR}/usr/sbin/rcdiscovery-server
	${LN} -s ${INIT}/cluster-server ${DESTDIR}/usr/sbin/rccluster-server
	${LN} -s ${INIT}/collectd-init ${DESTDIR}/usr/sbin/rccollectd-init
	${LN} -s ${INIT}/cluster-config-server ${DESTDIR}/usr/sbin/rccluster-config-server
	${LN} -s ${INIT}/host-monitoring ${DESTDIR}/${SBIN}/rchost-monitoring
	${LN} -s ${INIT}/host-relay ${DESTDIR}/${SBIN}/rchost-relay
	${LN} -s ${INIT}/snmp-relay ${DESTDIR}/${SBIN}/rcsnmp-relay
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
		${LN} -s ${ICSW_BASE}/bin/sgestat.py ${DESTDIR}/usr/local/bin/$$link_source; \
	done
	# /usr/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/bin
	${LN} -s ${ICSW_BASE}/bin/load_firmware.sh ${DESTDIR}/usr/bin/load_firmware.sh
	# /opt/cluster/md_daemon
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/md_daemon/sql_icinga
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/md_daemon/sql_nagios
	for daemon in nagios icinga; do \
	    ${INSTALL} ${INSTALL_OPTS} sql_$${daemon}/check_database.sh ${DESTDIR}/${ICSW_BASE}/md_daemon/sql_$${daemon}; \
	    cp -a sql_$${daemon}/*.sql ${DESTDIR}/${ICSW_BASE}/md_daemon/sql_$${daemon}; \
	done
	# /opt/cluster/lcs
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/lcs
	cp -a cluster/lcs/* ${DESTDIR}${ICSW_BASE}/lcs
	# /opt/cluster/share/mother
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} *pxelinux.0 ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} *.c32 ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} memtest${MEMTEST_VERSION}.iso ${DESTDIR}/${MOTHER_DIR}
	${INSTALL} ${INSTALL_OPTS} memdisk ${DESTDIR}/${MOTHER_DIR}/syslinux
	# fixtures
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/package_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/rms_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/rrd_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/mother_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/logcheck_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/md_config_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/discovery_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/rrd_collector_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} fixtures/config_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	# examples
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/examples/sge_licenses
	cp -a examples/* ${DESTDIR}${ICSW_BASE}/examples/sge_licenses
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
	for pyf in kernel_sync_tools module_dependency_tools cluster_location ; do \
		install ${INSTALL_OPTS} $${pyf}.py ${DESTDIR}/${PYTHON_SITE}; \
	done
	install ${INSTALL_OPTS} sge_license_tools.py ${DESTDIR}/${PYTHON_SITE}
	${INSTALL} ${INSTALL_OPTS} sge_tools.py ${DESTDIR}/${PYTHON_SITE}
	${INSTALL} ${INSTALL_OPTS} license_tool.py ${DESTDIR}/${PYTHON_SITE}
	# Various
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PROFDIR}
	cp -a cluster.schema ${DESTDIR}/etc
	${INSTALL} ${INSTALL_OPTS} batchsys.sh_client ${DESTDIR}/${PROFDIR}/batchsys.sh
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${KERNEL_CONFIGS}
	${INSTALL} ${INSTALL_OPTS} src/kcompile ${DESTDIR}/${KERNEL_CONFIGS}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/log/hosts
	mkdir -p ${DESTDIR}/var/run/collectd-init
	mkdir -p ${DESTDIR}/var/run/rrd-grapher
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_TFTP}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${VARDIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/lib/logging-server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/log/cluster/sockets
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${META_DIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALL_OPTS} configs/remote_ping.test ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALL_OPTS} configs/host-monitoring ${DESTDIR}/${SYSCONF}/host-monitoring
	${INSTALL} ${INSTALL_OPTS} configs/host-relay ${DESTDIR}/${SYSCONF}/host-relay
	# uwsgi 
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/etc/uwsgi
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend-common.include ${DESTDIR}/opt/cluster/etc/uwsgi/
	${INSTALL} ${INSTALL_OPTS} nginx/${WSGI_INI} ${DESTDIR}/opt/cluster/etc/uwsgi/webfrontend.wsgi.ini
	# nginx
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend.conf ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALL_OPTS} nginx/webfrontend.nsconf ${DESTDIR}/${NGINX_CONF}
	./init_proprietary.py ${DESTDIR}



install_old_2:
	${LN} -s ${PYTHON_SITE}/send_mail.py ${DESTDIR}/${ICSW_BIN}/
	${LN} -s ${PYTHON_SITE}/check_scripts.py ${DESTDIR}/${ICSW_SBIN}/
	${LN} -s ${ICSW_BIN}/ics_tools.sh ${DESTDIR}/${INIT}/
	${LN} -s ${INIT}/loadmodules ${DESTDIR}/usr/sbin/rcloadmodules
	${LN} -s ${INIT}/meta-server ${DESTDIR}/usr/sbin/rcmeta-server
	${LN} -s ${INIT}/logging-server ${DESTDIR}/${USRSBIN}/rclogging-server
	${LN} -s ${INIT}/package-server ${DESTDIR}/usr/sbin/rcpackage-server
	${LN} -s ${INIT}/package-client ${DESTDIR}/usr/sbin/rcpackage-client
	${LN} -s ${ICSW_BASE}/sbin/pis/openmpi_source_post_install.py ${DESTDIR}/${ICSW_BASE}/sbin/pis/mpich_source_post_install.py
	${LN} -s ./compile_openmpi.py ${DESTDIR}/${ICSW_BASE}/bin/compile_mpich.py
	for link_source in sgenodestat sgejobstat sjs sns ; do \
		${LN} -s ${ICSW_BASE}/bin/sgestat.py ${DESTDIR}/usr/local/bin/$$link_source; \
	done
	${LN} -s ${INIT}/rms-server ${DESTDIR}/usr/sbin/rcrms-server
	${LN} -s ${INIT}/rrd-grapher ${DESTDIR}/usr/sbin/rcrrd-grapher
	${LN} -s ${INIT}/hoststatus ${DESTDIR}/usr/sbin/rchoststatus
	${LN} -s ${INIT}/mother ${DESTDIR}/usr/sbin/rcmother
	${LN} -s ${INIT}/logcheck-server ${DESTDIR}/usr/sbin/rclogcheck-server
	${LN} -s ${INIT}/md-config-server ${DESTDIR}/usr/sbin/rcmd-config-server
	${LN} -s ${INIT}/init-license-server ${DESTDIR}/usr/sbin/rcinit-license-server
	${LN} -s ${INIT}/discovery-server ${DESTDIR}/usr/sbin/rcdiscovery-server
	${LN} -s ${INIT}/cluster-server ${DESTDIR}/usr/sbin/rccluster-server
	${LN} -s ${INIT}/collectd-init ${DESTDIR}/usr/sbin/rccollectd-init
	${LN} -s ${INIT}/cluster-config-server ${DESTDIR}/usr/sbin/rccluster-config-server
	${LN} -s ${PYTHON_SITE}/initat/cluster/manage.py ${DESTDIR}/${ICSW_BASE}/sbin/clustermanage.py
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${ICSW_BASE}/bin/populate_ramdisk_local.py
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${ICSW_BASE}/bin/copy_local_kernel.sh
	${LN} -s ${ICSW_BASE}/bin/load_firmware.sh ${DESTDIR}/usr/bin/load_firmware.sh
	./init_proprietary.py ${DESTDIR}

install_cluster_backbone:
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SBIN}/pis
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${CONFDIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${KERNEL_CONFIGS}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/etc
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/etc/apache2/conf.d
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/etc/httpd/conf
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/etc/sysconfig/cluster
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/package_install/client
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/package_install/server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/snmp
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/snmp/handler
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/snmp/handler/instances
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/snmp/process
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INITAT27}/snmp/sink
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${INIT}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${LOCALBIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${LOCALSBIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${META_DIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/etc/extra_servers.d
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/etc/uwsgi
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/sbin/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/share/cert/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/opt/cluster/share/webcache/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/conf
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/examples/sge_licenses
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/lcs
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/md_daemon/sql_icinga
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/md_daemon/sql_nagios
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/sbin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/sbin/pis
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_BASE}/sql
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PROFDIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYINITLIB}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_config_server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server/capabilities
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server/modules
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/transfer
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/urls
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/collectd/collectd_types
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/discovery_server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/logcheck_server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/config
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/icinga_log_reader
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/special_commands
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/special_commands/instances
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/mother
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/rms
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/rrd_grapher
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SGE}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_SGE}/init.d
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/root/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SBIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SCRIPTDIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SPREFIX}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/cluster
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/init-license-server.d
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/licenses
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${SYSCONF}/logging-server.d
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${ICSW_TFTP}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/${LIB_DIR}/python/site-packages
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/local/bin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/local/sbin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/usr/sbin
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${USRSBIN}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/${VARDIR}
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/lib/logging-server
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/log/cluster/sockets
	${INSTALL} ${INSTALL_OPTS} -d ${DESTDIR}/var/log/hosts
	mkdir -p ${DESTDIR}/etc/sysconfig/cluster
	mkdir -p ${DESTDIR}/${INIT}
	mkdir -p ${DESTDIR}/${ICSW_BASE}/bin/
	mkdir -p ${DESTDIR}/${ICSW_BASE}/sbin/
	mkdir -p ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher 
	mkdir -p ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher/color_rules.d 
	mkdir -p ${DESTDIR}/${ICSW_BASE}/share/rrd_grapher/color_tables.d 
	mkdir -p ${DESTDIR}/usr/sbin/
	mkdir -p ${DESTDIR}/var/run/collectd-init
	mkdir -p ${DESTDIR}/var/run/rrd-grapher
	# various files
	for pyf in kernel_sync_tools module_dependency_tools cluster_location ; do \
		install ${INSTALL_OPTS} $${pyf}.py ${DESTDIR}/${PYTHON_SITE}; \
	done
	# stage files
	cp -a cluster/lcs/* ${DESTDIR}${ICSW_BASE}/lcs
	${INSTALL} ${INSTALL_OPTS} src/kcompile ${DESTDIR}/${KERNEL_CONFIGS}
	${INSTALL} ${INSTALL_OPTS} user_info.py ${DESTDIR}/${ICSW_BASE}/bin
	# tools
	for bin_file in clog.py device_info.py load_firmware.sh \
		mysql_dump.sh pack_kernel.sh populate_ramdisk.py resync_config.sh \
		show_config_script.py make_image.py change_cluster_var.py ; do \
		${INSTALL} ${INSTALL_OPTS} cluster/bin/$$bin_file ${DESTDIR}/${ICSW_BASE}/bin; \
	done
	# rc helper files
	for sbin_file in start_cluster.sh stop_cluster.sh start_server.sh stop_server.sh check_cluster.sh check_server.sh; do \
		${INSTALL} ${INSTALL_OPTS} cluster/bin/$$sbin_file ${DESTDIR}/${ICSW_SBIN}; \
	done

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
	${PYTHON} ./cbc-tools_setup.py clean
	${PYTHON} ./host-monitoring_setup.py clean
	${PYTHON} ./python-modules-base_setup.py clean
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
