#!/usr/bin/python-init -OtB
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" image information and modify """

import os
import sys


class Parser(object):
    def link(self, sub_parser, **kwargs):
        if kwargs["server_mode"]:
            return self._add_image_parser(sub_parser)

    def _add_image_parser(self, sub_parser):
        parser = sub_parser.add_parser("image", help="image information and modification")
        parser.set_defaults(subcom="image", execute=self._execute)
        from initat.cluster.backbone.models import image
        _images = [_img.name for _img in image.objects.all().order_by("name")]
        if len(_images):
            parser.add_argument("--mode", default="list", type=str, choices=["list", "build", "scan", "take"], help="image action [%(default)s]")
            parser.add_argument("--image", default=_images[0], type=str, choices=_images, help="image to operate on [%(default)s]")
            parser.add_argument("--verbose", default=False, action="store_true", help="be verbose [%(default)s]")
            parser.add_argument("--ignore-errors", "-i", default=False, action="store_true", help="ignore missing packages [%(default)s]")
            parser.add_argument("--override", default=False, action="store_true", help="override build lock [%(default)s]")
            parser.add_argument("--skip-cleanup", default=False, action="store_true", help="skip image cleanup task [%(default)s]")
        else:
            parser.add_argument("--mode", default="scan", type=str, choices=["scan", "take"])
        parser.add_argument("--image-name", default="", type=str, help="image name from scan command [%(default)s]")
        # self._add_reboot_parser(child_parser)
        return parser

    def _execute(self, opt_ns):
        print opt_ns
        if not hasattr(opt_ns, "mode"):
            print("No images defined")
            # sys.exit(0)
        from .main import main
        main(opt_ns)
