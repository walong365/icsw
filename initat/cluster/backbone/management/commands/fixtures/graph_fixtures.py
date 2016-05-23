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
""" creates fixtures for graph """


from initat.cluster.backbone import factories
from initat.cluster.backbone.models import GraphForecastModeEnum


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

    for _name, _seconds, _mode in [
        ("simple linear for timeframe", 0, GraphForecastModeEnum.simple_linear),
    ]:
        _new_fc = factories.GraphSettingForecastFactory(
            name=_name,
            seconds=_seconds,
            mode=_mode.value,
        )

    for _name, _rtn, _ar, _seconds, _base_tf, _tfo in [
        ("last 24 hours", True, True, 3600 * 24, "h", 0),
        ("today", False, True, 3600 * 24, "d", 0),
        ("this week", False, True, 3600 * 24 * 7, "w", 0),
        ("this month", False, True, 3600 * 24 * 31, "m", 0),
        ("this year", False, True, 3600 * 24 * 365, "y", 0),
        ("this decade", False, True, 3600 * 24 * 365 * 10, "D", 0),
        # according to BM last is more common then past
        ("last day", False, False, 3600 * 24, "d", -1),
        ("last week", False, False, 3600 * 24 * 7, "w", -1),
        ("last month", False, False, 3600 * 24 * 31, "m", -1),
        ("last year", False, False, 3600 * 24 * 365, "y", -1),
        ("last decade", False, False, 3600 * 24 * 365 * 10, "D", -1),
    ]:
        _new_tf = factories.GraphTimeFrameFactory(
            name=_name,
            relative_to_now=_rtn,
            auto_refresh=_ar,
            seconds=_seconds,
            base_timeframe=_base_tf,
            timeframe_offset=_tfo,
        )
