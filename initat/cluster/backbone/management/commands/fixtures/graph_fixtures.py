# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for cluster-server """


from initat.cluster.backbone import factories


def add_fixtures(**kwargs):
    for _name, _width, _height in [
        ("xsmall", 320, 200),
        ("small", 420, 200),
        ("*normal", 640, 300),
        ("big", 800, 350),
        ("bigger", 1024, 400),
        ("large", 1280, 450),
    ]:
        _new_gw = factories.GraphSettingSizeFactory(
            name=_name.replace("*", ""),
            default="*" in _name,
            width=_width,
            height=_height,
        )
    for _name, _seconds in [
        ("timeframe", 0),
        ("1 hour", 3600),
        ("1 day", 24 * 3600),
        ("1 week", 7 * 24 * 3600),
        ("1 month (31 days)", 31 * 24 * 3600),
        ("1 year (365 days)", 365 * 24 * 3600),
    ]:
        _new_ts = factories.GraphSettingTimeshiftFactory(
            name=_name,
            seconds=_seconds,
        )
