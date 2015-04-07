include Makefile.globals

CLUSTERBIN=${PREFIX_CLUSTER}/bin
CLUSTERSBIN=${PREFIX_CLUSTER}/sbin
CONFDIRROOT=/etc/sysconfig
CONFDIR_HM=${CONFDIRROOT}/host-monitoring.d
CONFIGS=/usr/src/configs/
ETC=/etc
INITD=/etc/init.d
LN=ln
LOCALBIN=/usr/local/bin
LOCALSBIN=/usr/local/sbin
MEMTEST_VERSION=86+-5.01
META_DIR=/var/lib/meta-server
MOTHER_DIR=${PREFIX_CLUSTER}/share/mother
NGINX_CONF=/etc/nginx/sites-enabled/localhost
PROFDIR=/etc/profile.d
PY_FILES=rms-server.py
PYINITLIB=${PYINIT}/lib
PYINIT=/opt/python-init
RMS_DIST_DIR=${PREFIX_CLUSTER}/sge
SBIN=/usr/sbin
SCRIPTDIR=/usr/bin
SGE_FILES=sge_editor_conf.py modify_sge_config.sh add_logtail.sh sge_request sge_qstat create_sge_links.py build_sge6x.sh post_install.sh
SPREFIX=${PREFIX_CLUSTER}/sbin
TFTP=/opt/cluster/system/tftpboot
USRSBIN=/usr/sbin
VARDIR=/var/lib/cluster/package-client
VERSION_SYSLINUX=6.02

ifeq (${DIST_TYPE}, debian)
	WSGI_INI=webfrontend.wsgi.ini-deb
endif
ifeq (${DIST_TYPE}, suse)
	WSGI_INI=webfrontend.wsgi.ini-suse
endif
ifeq (${DIST_TYPE}, centos)
	WSGI_INI=webfrontend.wsgi.ini-centos
endif

build:
	${MAKE} -C c_progs_collectd
	${MAKE} -C c_progs
	${MAKE} -C c_clients
	${PYTHON} ./cbc-tools_setup.py build
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

install: install_cluster_backbone install_cluster_backbone_sql install_cluster_config_server install_collectd_init install_cluster_server install_discovery_server install_init_license_tools install_init_snmp_libs install_md_config_server install_logcheck_server install_mother install_rrd_grapher install_webfrontend install_rms_tools install_rms_tools_base install_cbc_tools install_package_install install_logging_server install_meta_server install_host_monitoring install_loadmodules install_python_modules_base
	:
	${LN} -s ${PYTHON_SITE}/send_mail.py ${DESTDIR}/${CLUSTERBIN}/
	${LN} -s ${PYTHON_SITE}/check_scripts.py ${DESTDIR}/${CLUSTERSBIN}/
	${LN} -s ${CLUSTERBIN}/ics_tools.sh ${DESTDIR}/${INITD}/
	${LN} -s ${INITD}/loadmodules ${DESTDIR}/usr/sbin/rcloadmodules
	${LN} -s ${INITD}/meta-server ${DESTDIR}/usr/sbin/rcmeta-server
	${LN} -s ${INITD}/logging-server ${DESTDIR}/${USRSBIN}/rclogging-server
	${LN} -s ${INITD}/package-server ${DESTDIR}/usr/sbin/rcpackage-server
	${LN} -s ${INITD}/package-client ${DESTDIR}/usr/sbin/rcpackage-client
	${LN} -s ${PREFIX_CLUSTER}/sbin/pis/openmpi_source_post_install.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin/pis/mpich_source_post_install.py
	${LN} -s ./compile_openmpi.py ${DESTDIR}/${PREFIX_CLUSTER}/bin/compile_mpich.py
	for link_source in sgenodestat sgejobstat sjs sns ; do \
		${LN} -s ${PREFIX_CLUSTER}/bin/sgestat.py ${DESTDIR}/usr/local/bin/$$link_source; \
	done
	${LN} -s ${INITD}/rms-server ${DESTDIR}/usr/sbin/rcrms-server
	${LN} -s ${INITD}/rrd-grapher ${DESTDIR}/usr/sbin/rcrrd-grapher
	${LN} -s ${INITD}/hoststatus ${DESTDIR}/usr/sbin/rchoststatus
	${LN} -s ${INITD}/mother ${DESTDIR}/usr/sbin/rcmother
	${LN} -s ${INITD}/logcheck-server ${DESTDIR}/usr/sbin/rclogcheck-server
	${LN} -s ${INITD}/md-config-server ${DESTDIR}/usr/sbin/rcmd-config-server
	${LN} -s ${INITD}/init-license-server ${DESTDIR}/usr/sbin/rcinit-license-server
	${LN} -s ${INITD}/discovery-server ${DESTDIR}/usr/sbin/rcdiscovery-server
	${LN} -s ${INITD}/cluster-server ${DESTDIR}/usr/sbin/rccluster-server
	${LN} -s ${INITD}/collectd-init ${DESTDIR}/usr/sbin/rccollectd-init
	${LN} -s ${INITD}/cluster-config-server ${DESTDIR}/usr/sbin/rccluster-config-server
	${LN} -s ${PYTHON_SITE}/initat/cluster/manage.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin/clustermanage.py
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${PREFIX_CLUSTER}/bin/populate_ramdisk_local.py
	${LN} -s ./populate_ramdisk.py ${DESTDIR}/${PREFIX_CLUSTER}/bin/copy_local_kernel.sh
	${LN} -s ${PREFIX_CLUSTER}/bin/load_firmware.sh ${DESTDIR}/usr/bin/load_firmware.sh
	./init_proprietary.py ${DESTDIR}

install_cluster_backbone:
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${CLUSTERBIN}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${CLUSTERSBIN}/pis
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${CONFDIR}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${CONFIGS}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${ETC}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/etc/apache2/conf.d
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/etc/httpd/conf
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/etc/sysconfig/cluster
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/package_install/client
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/package_install/server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/snmp
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/snmp/handler
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/snmp/handler/instances
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/snmp/process
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITAT27}/snmp/sink
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${INITD}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${LOCALBIN}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${LOCALSBIN}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${META_DIR}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/opt/cluster/etc/extra_servers.d
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/opt/cluster/etc/uwsgi
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/opt/cluster/sbin/
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/opt/cluster/share/cert/
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/opt/cluster/share/webcache/
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/bin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/conf
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/examples/sge_licenses
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/lcs
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/md_daemon/sql_icinga
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/md_daemon/sql_nagios
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/sbin/pis
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PREFIX_CLUSTER}/sql
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PROFDIR}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYINITLIB}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_config_server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server/capabilities
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server/modules
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/transfer
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/cluster/urls
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/collectd/collectd_types
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/discovery_server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/logcheck_server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/config
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/icinga_log_reader
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/special_commands
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/special_commands/instances
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/mother
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/rms
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${PYTHON_SITE}/initat/rrd_grapher
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${RMS_DIST_DIR}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${RMS_DIST_DIR}/init.d
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/root/bin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SBIN}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SCRIPTDIR}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SPREFIX}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SYSCONF}/cluster
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SYSCONF}/init-license-server.d
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SYSCONF}/licenses
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${SYSCONF}/logging-server.d
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${TFTP}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/usr/bin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/usr/${LIB_DIR}/python/site-packages
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/usr/local/bin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/usr/local/sbin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/usr/sbin
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${USRSBIN}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/${VARDIR}
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/var/lib/logging-server
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/var/log/cluster/sockets
	${INSTALL} ${INSTALLOPTS} -d ${DESTDIR}/var/log/hosts
	mkdir -p ${DESTDIR}/etc/sysconfig/cluster
	mkdir -p ${DESTDIR}/${INITD}
	mkdir -p ${DESTDIR}/${PREFIX_CLUSTER}/bin/
	mkdir -p ${DESTDIR}/${PREFIX_CLUSTER}/sbin/
	mkdir -p ${DESTDIR}/${PREFIX_CLUSTER}/share/rrd_grapher 
	mkdir -p ${DESTDIR}/${PREFIX_CLUSTER}/share/rrd_grapher/color_rules.d 
	mkdir -p ${DESTDIR}/${PREFIX_CLUSTER}/share/rrd_grapher/color_tables.d 
	mkdir -p ${DESTDIR}/usr/sbin/
	mkdir -p ${DESTDIR}/var/run/collectd-init
	mkdir -p ${DESTDIR}/var/run/rrd-grapher
	
	for pyf in kernel_sync_tools module_dependency_tools cluster_location ; do \
		install ${INSTALL_OPTS} $${pyf}.py ${DESTDIR}/${PYTHON_SITE}; \
	done
	
	cp -a cluster/lcs/* ${DESTDIR}${PREFIX_CLUSTER}/lcs
	${INSTALL} ${INSTALL_OPTS} src/kcompile ${DESTDIR}/${CONFIGS}
	${INSTALL} ${INSTALL_OPTS} user_info.py ${DESTDIR}/${PREFIX_CLUSTER}/bin
	
	for bin_file in clog.py device_info.py load_firmware.sh \
		mysql_dump.sh pack_kernel.sh populate_ramdisk.py resync_config.sh \
		show_config_script.py make_image.py change_cluster_var.py ; do \
		${INSTALL} ${INSTALL_OPTS} cluster/bin/$$bin_file ${DESTDIR}/${PREFIX_CLUSTER}/bin; \
	done
	
	for sbin_file in start_cluster.sh stop_cluster.sh start_server.sh stop_server.sh check_cluster.sh check_server.sh; do \
		${INSTALL} ${INSTALL_OPTS} cluster/bin/$$sbin_file ${DESTDIR}/${PREFIX_CLUSTER}/sbin; \
	done
	

install_cluster_backbone_sql:
	cp -a initat/cluster/ ${DESTDIR}/${INITAT27}
	${INSTALL} ${INSTALL_OPTS} clustershell ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	
	for shf in post_install server_installed ; do \
	    ${INSTALL} ${INSTALL_OTPS} tools/$${shf}.sh ${DESTDIR}/${PREFIX_CLUSTER}/sbin/pis ; \
	done
	
	for shf in migrate_to_django restore_database remove_noctua remove_noctua_simple ; do  \
	    cp -a tools/$${shf}.sh ${DESTDIR}/${PREFIX_CLUSTER}/sbin; \
	done
	
	for pyf in db_magic check_local_settings create_django_users setup_cluster restore_user_group fix_models ; do \
	    ${INSTALL} ${INSTALL_OPTS} tools/$${pyf}.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin ; \
	done
	cp -a tools/modify_object.py ${DESTDIR}/${PREFIX_CLUSTER}/bin
	cp -a db.cf ${DESTDIR}/etc/sysconfig/cluster/db.cf.sample

install_cluster_config_server:
	for name in cluster-config-server.py fetch_ssh_keys.py ; do \
		${INSTALL} ${INSTALLOPTS} $${name} ${DESTDIR}/${PREFIX_CLUSTER}/sbin; \
	done
	
	for name in initat/cluster_config_server/*.py; do \
		${INSTALL} ${INSTALLOPTS} $${name} ${DESTDIR}/${PYTHON_SITE}/initat/cluster_config_server ; \
	done
	
	${INSTALL} ${INSTALLOPTS} cluster-config-server ${DESTDIR}/${INITD}/cluster-config-server
	${INSTALL} ${INSTALLOPTS} cluster-config-server.cf ${DESTDIR}/${SYSCONF}/cluster-config-server
	${INSTALL} ${INSTALLOPTS} fixtures/config_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/

install_collectd_init:
	cp -a collectd-init ${DESTDIR}/${INITD}
	cp -a cdfetch.py  ${DESTDIR}${PREFIX_CLUSTER}/bin
	cp -a collectd-init.py  ${DESTDIR}${PREFIX_CLUSTER}/sbin 
	install ${INSTALLOPTS} initat/collectd/*.py ${DESTDIR}/${PYTHON_SITE}/initat/collectd
	install ${INSTALLOPTS} initat/collectd/collectd_types/*.py ${DESTDIR}/${PYTHON_SITE}/initat/collectd/collectd_types
	cp -a c_progs_collectd/send_collectd_zmq ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} fixtures/rrd_collector_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	touch ${DESTDIR}/etc/sysconfig/cluster/.disable_rrdcached_start

install_cluster_server:
	${INSTALL} ${INSTALLOPTS} fixtures/server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	for mod in initat/cluster_server/*.py; do \
		${INSTALL} ${INSTALL_OPTS} $$mod ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server; \
	done
	${INSTALL} ${INSTALL_OPTS} initat/cluster_server/*.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server
	${INSTALL} ${INSTALL_OPTS} initat/cluster_server/modules/*.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server/modules/
	${INSTALL} ${INSTALL_OPTS} initat/cluster_server/capabilities/*.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster_server/capabilities/
	${INSTALL} ${INSTALL_OPTS} cluster-server.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALL_OPTS} cluster-server ${DESTDIR}/${INITD}; \
	cp -a cluster.schema ${DESTDIR}/etc

install_discovery_server:
	${INSTALL} ${INSTALLOPTS} fixtures/discovery_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALLOPTS} discovery-server.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	for name in initat/discovery_server/*.py ; do  \
		${INSTALL} ${INSTALLOPTS} $${name} ${DESTDIR}/${PYTHON_SITE}/initat/discovery_server ; \
	done
	${INSTALL} ${INSTALLOPTS} discovery-server ${DESTDIR}/${INITD}/discovery-server
	${INSTALL} ${INSTALLOPTS} discovery-server.cf ${DESTDIR}/${SYSCONF}/discovery-server

install_init_license_tools:
	if [ "${LIB_DIR}" = "lib64" ] ; then \
	    tar xzf lmutil-x64_lsb-11.12.1.0v6.tar.gz ; \
	    ${INSTALL} ${INSTALL_OPTS} lmutil ${DESTDIR}${PREFIX_CLUSTER}/bin/lmutil; \
	else \
	    tar xzf lmutil-i86_lsb-11.12.1.0v6.tar.gz ; \
	    ${INSTALL} ${INSTALL_OPTS} lmutil ${DESTDIR}${PREFIX_CLUSTER}/bin/lmutil; \
	fi
	${INSTALL} ${INSTALLOPTS} license_server_tool.py ${DESTDIR}/${PREFIX_CLUSTER}/bin
	${INSTALL} ${INSTALLOPTS} license_tool.py ${DESTDIR}/${PYTHON_SITE}
	${INSTALL} ${INSTALLOPTS} init-license-server.rc ${DESTDIR}/${INITD}/init-license-server
	cp -a examples/* ${DESTDIR}${PREFIX_CLUSTER}/examples/sge_licenses
	
	install ${INSTALL_OPTS} sge_license_tools.py ${DESTDIR}/${PYTHON_SITE}; \
	for file in license_progs loadsensor ; do \
	    install ${INSTALL_OPTS} $$file.py ${DESTDIR}${PREFIX_CLUSTER}/bin; \
	done
	${INSTALL} ${INSTALLOPTS} init-license-server.cf ${DESTDIR}/${SYSCONF}/init-license-server
	${INSTALL} ${INSTALLOPTS} test_license ${DESTDIR}/${SYSCONF}/init-license-server.d

install_init_snmp_libs:
	${INSTALL} ${INSTALLOPTS} initat/snmp/*.py ${DESTDIR}/${INITAT27}/snmp
	${INSTALL} ${INSTALLOPTS} initat/snmp/handler/*.py ${DESTDIR}/${INITAT27}/snmp/handler
	${INSTALL} ${INSTALLOPTS} initat/snmp/process/*.py ${DESTDIR}/${INITAT27}/snmp/process
	${INSTALL} ${INSTALLOPTS} initat/snmp/handler/instances/*.py ${DESTDIR}/${INITAT27}/snmp/handler/instances
	${INSTALL} ${INSTALLOPTS} initat/snmp/sink/*.py ${DESTDIR}/${INITAT27}/snmp/sink

install_md_config_server: 
	install ${INSTALLOPTS} set_passive_checkresult.py ${DESTDIR}/${PREFIX_CLUSTER}/bin
	install ${INSTALLOPTS} initat/md_config_server/*.py ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server
	install ${INSTALLOPTS} initat/md_config_server/config/*.py ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/config
	install ${INSTALLOPTS} initat/md_config_server/icinga_log_reader/*.py ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/icinga_log_reader
	install ${INSTALLOPTS} initat/md_config_server/special_commands/*.py ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/special_commands
	install ${INSTALLOPTS} initat/md_config_server/special_commands/instances/*.py ${DESTDIR}/${PYTHON_SITE}/initat/md_config_server/special_commands/instances
	for daemon in nagios icinga; do \
	    ${INSTALL} ${INSTALLOPTS} sql_$${daemon}/check_database.sh ${DESTDIR}/${PREFIX_CLUSTER}/md_daemon/sql_$${daemon}; \
	    cp -a sql_$${daemon}/*.sql ${DESTDIR}/${PREFIX_CLUSTER}/md_daemon/sql_$${daemon}; \
	done
	install ${INSTALLOPTS} md-config-server.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	install ${INSTALLOPTS} md-config-server ${DESTDIR}/${INITD}/md-config-server
	install ${INSTALLOPTS} md-config-server.cf ${DESTDIR}/${SYSCONF}/md-config-server
	${INSTALL} ${INSTALLOPTS} fixtures/md_config_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/

install_logcheck_server:
	${INSTALL} ${INSTALLOPTS} logcheck-server.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} logcheck-server ${DESTDIR}/${INITD}/
	${INSTALL} ${INSTALLOPTS} logcheck-server.cf ${DESTDIR}/${SYSCONF}/logcheck-server
	${INSTALL} ${INSTALLOPTS} initat/logcheck_server/*.py ${DESTDIR}/${INITAT27}/logcheck_server
	touch ${DESTDIR}/${INITAT27}/logcheck_server/__init__.py
	${INSTALL} ${INSTALLOPTS} fixtures/logcheck_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/

install_mother:
	${INSTALL} ${INSTALLOPTS} *pxelinux.0 ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALLOPTS} *.c32 ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALLOPTS} memdisk ${DESTDIR}/${MOTHER_DIR}/syslinux
	${INSTALL} ${INSTALLOPTS} mother.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	${INSTALL} ${INSTALLOPTS} initat/mother/*.py ${DESTDIR}/${PYTHON_SITE}/initat/mother
	make -C c_progs DESTDIR=${DESTDIR} install
	${INSTALL} ${INSTALLOPTS} init_scripts/hoststatus.rc ${DESTDIR}/${INITD}/hoststatus
	${INSTALL} ${INSTALLOPTS} init_scripts/mother ${DESTDIR}${INITD}/
	${INSTALL} ${INSTALLOPTS} configs/mother.cf ${DESTDIR}/${SYSCONF}/mother
	${INSTALL} ${INSTALLOPTS} fixtures/mother_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	${INSTALL} ${INSTALLOPTS} memtest${MEMTEST_VERSION}.iso ${DESTDIR}/${MOTHER_DIR}

install_rrd_grapher:
	cp -a rrd-grapher ${DESTDIR}/${INITD}
	cp -a rrd-grapher.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin
	cp -a color_rules.xml ${DESTDIR}/${PREFIX_CLUSTER}/share/rrd_grapher
	cp -a color_tables.xml ${DESTDIR}/${PREFIX_CLUSTER}/share/rrd_grapher 
	install ${INSTALLOPTS} initat/rrd_grapher/*.py ${DESTDIR}/${PYTHON_SITE}/initat/rrd_grapher
	${INSTALL} ${INSTALLOPTS} fixtures/rrd_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/

install_webfrontend:
	${INSTALL} ${INSTALLOPTS} nginx/webfrontend.conf ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALLOPTS} nginx/webfrontend.nsconf ${DESTDIR}/${NGINX_CONF}
	${INSTALL} ${INSTALLOPTS} nginx/webfrontend-common.include ${DESTDIR}/opt/cluster/etc/uwsgi/
	${INSTALL} ${INSTALLOPTS} nginx/${WSGI_INI} ${DESTDIR}/opt/cluster/etc/uwsgi/webfrontend.wsgi.ini
	${INSTALL} ${INSTALLOPTS} nginx/webfrontend_pre_start.sh ${DESTDIR}/opt/cluster/sbin
	${INSTALL} ${INSTALLOPTS} nginx/webfrontend_post_install.sh ${DESTDIR}/opt/cluster/sbin
	${INSTALL} ${INSTALLOPTS} cert/* ${DESTDIR}/opt/cluster/share/cert
	cp -a initat/cluster/* ${DESTDIR}/${PYTHON_SITE}/initat/cluster/

install_rms_tools:
	${INSTALL} ${INSTALLOPTS} fixtures/rms_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/
	for file in ${PY_FILES} ; do \
	    install ${INSTALL_OPTS} $${file} ${DESTDIR}/${SPREFIX}; \
	done
	for file in ${SGE_FILES} ; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}/${RMS_DIST_DIR}; \
	done
	
	for file in proepilogue.py qlogin_wrapper.sh sge_starter.sh; do \
	    ${INSTALL} ${INSTALL_OPTS} $${file} ${DESTDIR}${RMS_DIST_DIR}; \
	done
	for file in initat/rms/*.py ; do \
	    ${INSTALL} ${INSTALL_OTPS} $${file} ${DESTDIR}${PYTHON_SITE}/initat/rms ; \
	done
	echo ${SGE_FILES} > ${DESTDIR}/${RMS_DIST_DIR}/.sge_files
	echo "proepilogue.py qlogin_wrapper.sh sge_starter.sh" > ${DESTDIR}/${RMS_DIST_DIR}/.party_files

	${INSTALL} ${INSTALL_OPTS} batchsys.sh_client ${DESTDIR}/${RMS_DIST_DIR}
	${INSTALL} ${INSTALL_OPTS} batchsys.sh_client ${DESTDIR}/${PROFDIR}/batchsys.sh
	${INSTALL} ${INSTALL_OPTS} rms-server.rc ${DESTDIR}${INITD}/rms-server
	for name in sgemaster sgeexecd sgebdb ; do \
	    ${INSTALL} ${INSTALL_OPTS} $$name ${DESTDIR}${RMS_DIST_DIR}/init.d; \
	done

install_rms_tools_base:
	${INSTALL} ${INSTALL_OPTS} sgestat.py ${DESTDIR}/${PREFIX_CLUSTER}/bin
	${INSTALL} ${INSTALL_OPTS} sge_tools.py ${DESTDIR}/${PYTHON_SITE}

install_cbc_tools:
	${PYTHON} ./cbc-tools_setup.py install --root="${DESTDIR}" --install-scripts=${PREFIX_CLUSTER}/bin
	${INSTALL} ${INSTALLOPTS} openmpi_source_post_install.py ${DESTDIR}/${PREFIX_CLUSTER}/sbin/pis

install_package_install:
	for file in package-server.py package-client.py; do \
	    ${INSTALL} ${INSTALLOPTS} $${file} ${DESTDIR}/${SPREFIX}; \
	done
	touch ${DESTDIR}/${INITAT27}/package_install/__init__.py
	${INSTALL} ${INSTALLOPTS} initat/package_install/server/*.py ${DESTDIR}/${INITAT27}/package_install/server/
	${INSTALL} ${INSTALLOPTS} initat/package_install/client/*.py ${DESTDIR}/${INITAT27}/package_install/client/ 
	for file in install_package.py package_status.py make_package.py insert_package_info.py ; do \
	    ${INSTALL} ${INSTALLOPTS} $${file} ${DESTDIR}/${SPREFIX}; \
	done
	${INSTALL} ${INSTALLOPTS} init_scripts/package-server.rc ${DESTDIR}${INITD}/package-server
	${INSTALL} ${INSTALLOPTS} init_scripts/package-client.rc ${DESTDIR}${INITD}/package-client
	${INSTALL} ${INSTALLOPTS} packagestatus.sh ${DESTDIR}/${SPREFIX}
	${INSTALL} ${INSTALLOPTS} fixtures/package_server_fixtures.py ${DESTDIR}/${PYTHON_SITE}/initat/cluster/backbone/management/commands/fixtures/

install_logging_server:
	for file in logging-server.py log_error.py logging-client.py ; do \
		${INSTALL} ${INSTALLOPTS} $${file} ${DESTDIR}/${CLUSTERSBIN}; \
	done
	
	${INSTALL} ${INSTALLOPTS} logwatch.py ${DESTDIR}/${CLUSTERSBIN}
	${INSTALL} ${INSTALLOPTS} initat/logging_server/__init__.py ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALLOPTS} initat/logging_server/main.py ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALLOPTS} initat/logging_server/server.py ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALLOPTS} initat/logging_server/config.py ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALLOPTS} initat/logging_server/version.py ${DESTDIR}/${INITAT27}/logging_server
	${INSTALL} ${INSTALLOPTS} logging-server.rc ${DESTDIR}/${INITD}/logging-server
	${INSTALL} ${INSTALLOPTS} logging-server.cf ${DESTDIR}/${SYSCONF}/logging-server
	
	touch ${DESTDIR}/${SYSCONF}/logging-server.d/tail

install_meta_server:
	${PYTHON} ./meta-server_setup.py install --root "${DESTDIR}"
	${INSTALL} ${INSTALLOPTS} meta-server.py ${DESTDIR}/${SPREFIX}
	${INSTALL} ${INSTALLOPTS} meta-server ${DESTDIR}/${INITD}

install_host_monitoring:
	${PYTHON} ./host-monitoring_setup.py install --root "${DESTDIR}"
	${MAKE} -C c_clients DESTDIR=${DESTDIR} install
	${INSTALL} ${INSTALLOPTS} scripts/register_file_watch ${DESTDIR}/${SCRIPTDIR}
	${INSTALL} ${INSTALLOPTS} scripts/unregister_file_watch ${DESTDIR}/${SCRIPTDIR}
	for script in start_node.sh stop_node.sh check_node.sh disable_node.sh; do \
		${INSTALL} ${INSTALLOPTS} scripts/$$script ${DESTDIR}/${CLUSTERSBIN}; \
	done
	for script in host-monitoring-zmq.py tls_verify.py snmp-relay.py logscan/openvpn_scan.py ; do \
		${INSTALL} ${INSTALLOPTS} $$script ${DESTDIR}/${CLUSTERSBIN}; \
	done
	${INSTALL} ${INSTALLOPTS} scripts/host-relay.rc ${DESTDIR}/${INITD}/host-relay
	${INSTALL} ${INSTALLOPTS} scripts/host-monitoring.rc ${DESTDIR}/${INITD}/host-monitoring
	${INSTALL} ${INSTALLOPTS} scripts/snmp-relay.rc ${DESTDIR}/${INITD}/snmp-relay
	${INSTALL} ${INSTALLOPTS} icinga_scripts/check_icinga_cluster.py ${DESTDIR}/${CLUSTERBIN}
	${INSTALL} ${INSTALLOPTS} configs/remote_ping.test ${DESTDIR}/${CONFDIR_HM}
	${INSTALL} ${INSTALLOPTS} configs/host-monitoring ${DESTDIR}/${CONFDIRROOT}/host-monitoring
	${INSTALL} ${INSTALLOPTS} configs/host-relay ${DESTDIR}/${CONFDIRROOT}/host-relay
	${LN} -s host-monitoring-zmq.py ${DESTDIR}/${CLUSTERSBIN}/collclient.py
	${LN} -s host-monitoring-zmq.py ${DESTDIR}/${CLUSTERSBIN}/collrelay.py
	${LN} -s host-monitoring-zmq.py ${DESTDIR}/${CLUSTERSBIN}/collserver.py
	${LN} -s ${INITD}/host-monitoring ${DESTDIR}/${SBIN}/rchost-monitoring
	${LN} -s ${INITD}/host-relay ${DESTDIR}/${SBIN}/rchost-relay
	${LN} -s ${INITD}/snmp-relay ${DESTDIR}/${SBIN}/rcsnmp-relay
	${LN} -s ${CLUSTERSBIN}/tls_verify.py ${DESTDIR}/${LOCALSBIN}/tls_verify.py

install_loadmodules:
	${INSTALL} ${INSTALLOPTS} loadmodules ${DESTDIR}/${INITD}/loadmodules

install_python_modules_base:
	${PYTHON} ./python-modules-base_setup.py install --root="${DESTDIR}"
	touch ${DESTDIR}/${INITAT27}/__init__.py
	${INSTALL} ${INSTALLOPTS} configs/rc.status ${DESTDIR}/${ETC}/rc.status_suse
	${INSTALL} ${INSTALLOPTS} configs/pci.ids ${DESTDIR}/${PYTHON_SITE}/
	for file in find_group_id.sh find_user_id.sh force_redhat_init_script.sh lse check_rpm_lists.py; do \
		${INSTALL} ${INSTALLOPTS} $${file} ${DESTDIR}/${CLUSTERSBIN}/$${file}; \
	done
	for file in get_cpuid.py send_command.py send_command_zmq.py ics_tools.sh ics_tools.py migrate_repos.py ; do \
		${INSTALL} ${INSTALLOPTS} $${file} ${DESTDIR}/${CLUSTERBIN}; \
	done 
	${INSTALL} ${INSTALLOPTS} modify_service.sh ${DESTDIR}/${CLUSTERSBIN}/pis
	${INSTALL} ${INSTALLOPTS} get_pids_from_meta.py ${DESTDIR}/${CLUSTERSBIN}/

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

