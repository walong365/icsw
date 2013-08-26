from distutils.core import setup

setup(name="host-monitoring",
<<<<<<< HEAD
      version="5.0",
=======
      version="4.7",
>>>>>>> 486fcf45ef39859b9de60be9b92f18f870abdc9d
      description="The host-monitoring part of the INIT(c) cluster software.",
      url="http://www.init.at",
      author="Andreas Lang-Nevyjel",
      author_email="lang@init.at",
      py_modules=["initat.snmp_relay.snmp_relay_schemes"],
      packages=["initat.host_monitoring", "initat.host_monitoring.modules", "initat.host_monitoring.exe"],
      )
