#!/usr/bin/python-init -Ot

import logging
import logging.handlers
import socket
import cPickle
import struct
from initat.tools import logging_tools
import os

class my_adapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).setdefault("host", os.uname()[1])
        return msg, kwargs
    def log(self, level, what, *args, **kwargs):
        if type(level) == type(""):
            logging.LoggerAdapter.log(self, what, level, *args, **kwargs)
        else:
            logging.LoggerAdapter.log(self, level, what, *args, **kwargs)
            
#rootLogger = logging.getLogger("init.at.host_monitor.sub.a.b.c")
#socketHandler = logging_tools.local_uds_handler("/var/lib/logging-server/py_log")
#rootLogger.addHandler(socketHandler)
#my_logger = rootLogger
#my_logger = my_adapter(rootLogger, {})
my_logger = logging_tools.get_logger("init.at.host_monitor.sub.a.b.c", "uds:/var/lib/logging-server/py_log")
# don't bother with a formatter, since a socket handler sends the event as
# an unformatted pickle

# Now, we can log to the root logger, or any other logger. First the root...
my_logger.log(logging_tools.LOG_LEVEL_ERROR, "Jackdaws love my big sphinx of quartz.")
my_logger.log("Jackdaws love mxy big sphinx of quartz.", logging_tools.LOG_LEVEL_ERROR)

# Now, define a couple of other loggers which might represent areas in your
# application:

#logger1 = logging.getLogger('myapp.area1')
#logger2 = logging.getLogger('myapp.area2')

#logger1.debug('Quick zephyrs blow, vexing daft Jim.')
#logger1.info('How quickly daft jumping zebras vex.')
#logger2.warning('Jail zesty vixen who grabbed pay from quack.')
#logger2.error('The five boxing wizards jump quickly.')
