import os
from os.path import join as pjoin
from subprocess import call
from distutils.core import setup
from distutils.command.install_data import install_data as _install_data

DOCDIR = "/usr/share/doc/packages/init.at/host-monitoring"
CONFDIR = "/etc/sysconfig/host-monitoring.d"
SCRIPTDIR = "/usr/bin"
CLUSTERBIN = "/opt/cluster/sbin"
CPROGS = ["ccollclientzmq", "csnmpclientzmq"]
INIT = "/etc/init.d"

SYMLINKS = [
    (pjoin(CLUSTERBIN, "host-monitoring-zmq.py"),
     pjoin(CLUSTERBIN, "collclient.py")),

    (pjoin(CLUSTERBIN, "host-monitoring-zmq.py"),
     pjoin(CLUSTERBIN, "collrelay.py")),

    (pjoin(CLUSTERBIN, "host-monitoring-zmq.py"),
     pjoin(CLUSTERBIN, "collserver.py")),
]

# Compile c progs for inclusion in binary package
call(["make", "-C", "c_clients", "clean"])
for cprog in CPROGS:
    call(["make", "-C", "c_clients", cprog])


class install_data(_install_data):
    def _remove_slash(self, path):
        """
        Turn an absolute path into a "relative" one by removing the
        leading slash.
        """
        return path[1:] if path.startswith("/") else path

    def _install_symlinks(self):
        for src, dst in SYMLINKS:
            #src = os.path.join(self.root, self._remove_slash(src))
            dst = os.path.join(self.root, self._remove_slash(dst))
            print "creating symlink %s -> %s" % (src, dst)
            os.symlink(src, dst)

    def run(self):
        # super cannot be used with old-style classes
        _install_data.run(self)
        self._install_symlinks()


setup(cmdclass={"install_data": install_data},
      name="host-monitoring",
      version="4.4",
      description="The host-monitoring part of the INIT(c) cluster software.",
      url="http://www.init.at",
      author="Andreas Lang-Nevyjel",
      author_email="lang@init.at",
      py_modules=["snmp_relay_schemes"],
      packages=["host_monitoring", "host_monitoring.modules"],
      data_files=[
          (DOCDIR, ["docs/LICENSE.GPL", "docs/README"]),
          (CONFDIR, ["configs/remote_ping.test"]),
          (SCRIPTDIR, ["scripts/register_file_watch", "scripts/unregister_file_watch"]),
          (CLUSTERBIN, ["scripts/start_node.sh", "scripts/disable_node.sh",
                        "scripts/check_node.sh", "scripts/stop_node.sh",
                        "host-monitoring-zmq.py", "snmp-relay.py",
                        "tls_verify.py"] + [pjoin("c_clients", prog) for prog in CPROGS]),

           ],
      )
