from distutils.core import setup

setup(name="host-monitoring",
      version="4.4",
      description="The host-monitoring part of the INIT(c) cluster software.",
      url="http://www.init.at",
      author="Andreas Lang-Nevyjel",
      author_email="lang@init.at",
      py_modules=["snmp_relay_schemes"],
      packages=["host_monitoring", "host_monitoring.modules"],
      )
