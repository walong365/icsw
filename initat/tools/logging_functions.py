# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

""" high-level helper functions for logging """

import logging
import os
from initat.tools import logging_tools


SEP_STR = "-" * 50


def get_logger(cs, handle_name, logger_name):
    full_name = os.path.join(cs["log.logdir"], handle_name)
    base_dir, base_name = (
        os.path.dirname(full_name),
        os.path.basename(full_name)
    )
    logger = logging.getLogger(logger_name)
    # print "*", logger_name, h_name
    logger.propagate = 0
    # print logging.root.manager.loggerDict.keys()
    # print dir(base_logger)
    # print "***", logger_name, base_logger, logger
    form = logging_tools.my_formatter(
        cs["log.format.line"],
        cs["log.format.date"],
    )
    logger.setLevel(logging.DEBUG)
    full_name = full_name.encode("ascii", errors="replace")
    # create dirs
    _dir, _fname = os.path.split(full_name)
    if not os.path.isdir(_dir):
        os.makedirs(_dir)
    new_h = logging_tools.logfile(
        full_name,
        max_bytes=cs["log.max.size.logs"],
        max_age_days=cs["log.max.age.logs"],
    )
    form.set_max_line_length(cs["log.max.line.length"])
    new_h.setFormatter(form)
    logger.addHandler(new_h)
    logger.info(SEP_STR)
    logger.info(
        "opened {} (file {} in {}) by pid {}".format(
            full_name,
            base_name,
            base_dir,
            os.getpid()
        )
    )
    return logger
