# -*- coding: utf-8 -*-

from .icsw_parser import ICSWParser

options = ICSWParser().parse_args()
options.execute(options)
