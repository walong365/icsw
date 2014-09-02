from distutils.core import setup

setup(name="python-modules-base",
      version="1.10-88",
      description="Basic python modules from init.at.",
      url="http://www.init.at",
      author="Andreas Lang-Nevyjel",
      author_email="lang@init.at",
      py_modules=["configfile", "ip", "inet", "icmp", "icmp_class",
                  "cpu_database", "pci_database", "send_mail",
                  "process_tools", "logging_tools", "server_command",
                  "mail_tools", "uuid_tools", "rrd_tools",
                  "net_tools", "threading_tools", "threading_tools_ancient",
                  "ipvx_tools", "rpm_build_tools", "openssl_tools",
                  "config_tools", "check_scripts", "drbd_tools",
                  "partition_tools", "rsync_tools", "io_stream_helper",
                  "configfile_old", "libvirt_tools", "affinity_tools",
                  ],
      )
