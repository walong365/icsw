from distutils.core import setup

setup(name="host-monitoring",
      version="4.7",
      description="The host-monitoring part of the INIT(c) cluster software.",
      url="http://www.init.at",
      author="Andreas Lang-Nevyjel",
      author_email="lang@init.at",
      py_modules=["initat.snmp_relay.snmp_relay_schemes"],
      packages=["initat.host_monitoring", "initat.host_monitoring.modules", "initat.host_monitoring.exe"],
      )
