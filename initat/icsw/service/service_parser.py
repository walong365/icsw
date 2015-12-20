#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
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

""" parser for the icsw service subcommand """

import argparse


class Parser(object):
    def link(self, sub_parser, **kwargs):
        self._add_service_parser(sub_parser)
        self._add_state_parser(sub_parser)

    def _add_service_parser(self, sub_parser):
        parser = sub_parser.add_parser("service", help="control icsw services")
        parser.set_defaults(subcom="service", execute=self._service_execute)
        child_parser = parser.add_subparsers(help="service subcommands")
        self._add_status_parser(child_parser)
        self._add_start_parser(child_parser)
        self._add_stop_parser(child_parser)
        self._add_restart_parser(child_parser)
        self._add_debug_parser(child_parser)
        self._add_reload_parser(child_parser)
        self._add_state_parser(child_parser)
        self._add_version_parser(child_parser)
        return parser

    def _add_status_parser(self, sub_parser):
        _srvc = sub_parser.add_parser("status", help="service status")
        _srvc.set_defaults(childcom="status")
        _srvc.add_argument("-i", dest="interactive", action="store_true", default=False, help="enable interactive mode [%(default)s]")
        _srvc.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview [%(default)s]")
        _srvc.add_argument("-s", dest="started", action="store_true", default=False, help="start info [%(default)s]")
        _srvc.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info [%(default)s]")
        _srvc.add_argument("-c", dest="config", action="store_true", default=False, help="show config info [%(default)s]")
        _srvc.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption [%(default)s]")
        _srvc.add_argument("-a", dest="almost_all", action="store_true", default=False, help="almost all of the above, except start and DB info [%(default)s]")
        _srvc.add_argument("-A", dest="all", action="store_true", default=False, help="all of the above [%(default)s]")
        _srvc.add_argument("-v", dest="version", default=False, action="store_true", help="show version info [%(default)s]")
        _srvc.add_argument("--with-tstate", dest="tstate", default=False, action="store_true", help="add target-state info from local meta-server [%(default)s]")
        self._add_iccs_sel(_srvc)
        # _srvc.add_argument("--mode", type=str, default="show", choices=["show", "stop", "start", "restart"], help="operation mode [%(default)s]")
        _srvc.add_argument("--failed", default=False, action="store_true", help="show only instances in failed state [%(default)s]")
        return _srvc

    def _add_start_parser(self, sub_parser):
        _act = sub_parser.add_parser("start", help="start service")
        _act.set_defaults(childcom="start")
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_version_parser(self, sub_parser):
        _act = sub_parser.add_parser("version", help="show version info")
        _act.set_defaults(childcom="version")

    def _add_debug_parser(self, sub_parser):
        _act = sub_parser.add_parser("debug", help="debug service")
        _act.set_defaults(childcom="debug")
        _act.add_argument("service", nargs=1, type=str, help="service to debug")
        _act.add_argument("debug_args", nargs="*", type=str, help="extra debug arguments")

    def _add_reload_parser(self, sub_parser):
        _act = sub_parser.add_parser("reload", help="reload service")
        _act.set_defaults(childcom="reload")
        _act.add_argument("service", nargs=1, type=str, help="service to reload")

    def _add_stop_parser(self, sub_parser):
        _act = sub_parser.add_parser("stop", help="stop service")
        _act.set_defaults(childcom="stop")
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_restart_parser(self, sub_parser):
        _act = sub_parser.add_parser("restart", help="restart service")
        _act.set_defaults(childcom="restart")
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_state_parser(self, sub_parser):
        _act = sub_parser.add_parser("state", help="state service")
        _act.set_defaults(childcom="state", execute=self._state_execute)
        ss_parser = _act.add_subparsers(help="state subcommand help")
        self._add_state_overview_parser(ss_parser)
        self._add_state_enable_parser(ss_parser)
        self._add_state_disable_parser(ss_parser)

    def _add_state_overview_parser(self, sub_parser):
        _act = sub_parser.add_parser("overview", help="state overview")
        _act.set_defaults(statecom="overview")
        _act.add_argument("--state", default=False, action="store_true", help="show states [%(default)s]")
        _act.add_argument("--action", default=False, action="store_true", help="show actions [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_state_enable_parser(self, sub_parser):
        _act = sub_parser.add_parser("enable", help="state overview")
        _act.set_defaults(statecom="enable")
        self._add_iccs_any_sel(_act)

    def _add_state_disable_parser(self, sub_parser):
        _act = sub_parser.add_parser("disable", help="state overview")
        _act.set_defaults(statecom="disable")
        self._add_iccs_any_sel(_act)

    def _add_iccs_sel(self, _parser):
        _parser.add_argument("service", nargs="*", type=str, help="list of services")

    def _add_iccs_any_sel(self, _parser):
        _parser.add_argument("service", nargs="+", type=str, help="list of services")

    def _service_execute(self, opt_ns):
        from .main import main
        # cleanup parsed args
        if opt_ns.childcom == "status":
            if opt_ns.all or opt_ns.almost_all:
                opt_ns.thread = True
                opt_ns.memory = True
                opt_ns.version = True
            if opt_ns.all:
                opt_ns.pid = True
                opt_ns.started = True
                opt_ns.config = True
        main(opt_ns)

    def _state_execute(self, opt_ns):
        from .main import main
        # cleanup parsed args
        main(opt_ns)

    @staticmethod
    def get_default_ns():
        sub_parser = argparse.ArgumentParser().add_subparsers()
        def_ns = Parser()._add_status_parser(sub_parser).parse_args([])
        def_ns.all = True
        def_ns.memory = True
        def_ns.config = True
        def_ns.pid = True
        def_ns.started = True
        def_ns.thread = True
        def_ns.tstate = True
        return def_ns
