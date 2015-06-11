# -*- coding: utf-8 -*-

from .icsw_parser import ICSWParser

if __name__ == '__main__':
    options = ICSWParser().parse_args()
    options.execute(options)
