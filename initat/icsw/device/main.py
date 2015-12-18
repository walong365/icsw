#
# Copyright (C) 2001-2006,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to cluster-backbone-tools
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

import re
import os
import datetime

from django.db.models import Q
from initat.cluster.backbone import routing
from initat.cluster.backbone.models import device, device_group
from initat.cluster.backbone.models.functions import to_system_tz
from initat.tools import logging_tools, net_tools, server_command, process_tools
from initat.icsw.service.instance import InstanceXML


class JoinedLogs(object):
    def __init__(self):
        self._records = {}

    def feed(self, what, dev, log_list):
        for _log in log_list:
            self._records.setdefault(what, []).append((_log.date, dev, _log))

    def show(self):
        if not self._records:
            print("no log records found")
        else:
            for _key in sorted(self._records.keys()):
                print("{} records ({})".format(_key, logging_tools.get_plural("entry", len(self._records[_key]))))
                _prev_day = None
                for _entry in sorted(self._records[_key]):
                    _cur_day = datetime.date(_entry[0].year, _entry[0].month, _entry[0].day)
                    if _cur_day != _prev_day:
                        _prev_day = _cur_day
                        print("")
                        print(_cur_day.strftime("%a, %d. %b %Y"))
                        print("")
                    self.show_record(_key, _entry)

    def format_boot_record(self, entry, device=None):
        return "  {} {}kernel: {}, image: {}".format(
            to_system_tz(entry.date),
            "dev={:<30s}".format(unicode(device)) if device else "",
            ", ".join(
                [
                    "{} ({}, {})".format(
                        unicode(_kernel.kernel.name),
                        _kernel.full_version,
                        _kernel.timespan,
                    ) for _kernel in entry.kerneldevicehistory_set.all()
                ]
            ) or "---",
            ", ".join(
                [
                    "{} ({}, {})".format(
                        unicode(_image.image.name),
                        _image.full_version,
                        _image.timespan,
                    ) for _image in entry.imagedevicehistory_set.all()
                ]
            ) or "---",
        )

    def show_record(self, ltype, entry):
        if ltype == "boot":
            print(self.format_boot_record(entry[2], device=entry[1]))
        else:
            print("unknown record type '{}'".format(ltype))


def device_info(opt_ns, cur_dev, j_logs):
    print(u"Information about device '{}' (full name {}, devicegroup {})".format(
        unicode(cur_dev),
        unicode(cur_dev.full_name),
        unicode(cur_dev.device_group))
    )
    print("UUID is '{}', database-ID is {:d}".format(cur_dev.uuid, cur_dev.pk))
    if opt_ns.ip:
        net_devs = cur_dev.netdevice_set.all().order_by("devname")
        if len(net_devs):
            for cur_nd in net_devs:
                print(
                    "    {}".format(
                        cur_nd.devname,
                    )
                )
                for cur_ip in cur_nd.net_ip_set.all().order_by("ip"):
                    print(
                        "        IP {} in network {}".format(
                            cur_ip.ip,
                            unicode(cur_ip.network),
                        )
                    )
        print("")
    if opt_ns.boot:
        if opt_ns.join_logs:
            j_logs.feed("boot", cur_dev, cur_dev.deviceboothistory_set.all())
        else:
            if cur_dev.deviceboothistory_set.count():
                _brs = cur_dev.deviceboothistory_set.all()
                print("found {}".format(logging_tools.get_plural("boot record", len(_brs))))
                for _entry in _brs:
                    print(j_logs.format_boot_record(_entry))
            else:
                print("device has no boot history records")


def device_syslog(opt_ns, cur_dev, j_logs):
    print(u"Information about device '{}' (full name {}, devicegroup {})".format(
        unicode(cur_dev),
        unicode(cur_dev.full_name),
        unicode(cur_dev.device_group))
    )
    print("UUID is '{}', database-ID is {:d}".format(cur_dev.uuid, cur_dev.pk))
    _cr = routing.SrvTypeRouting(force=True, ignore_errors=True)
    _ST = "logcheck-server"
    if _ST in _cr.service_types:
        _inst_xml = InstanceXML(quiet=True)
        # get logcheck-server IP
        _ls_ip = _cr[_ST][0][1]
        # get logcheck-server Port
        _ls_port = _inst_xml.get_port_dict(_ST, ptype="command")
        _sc = server_command.srv_command(
            command="get_syslog",
        )
        _sc["devices"] = _sc.builder(
            "devices",
            *[
                _sc.builder(
                    "device",
                    pk="{:d}".format(cur_dev.pk),
                    lines="{:d}".format(opt_ns.loglines),
                    minutes="{:d}".format(opt_ns.minutes),
                )
            ]
        )
        _conn_str = "tcp://{}:{:d}".format(_ls_ip, _ls_port)
        _result = net_tools.zmq_connection(
            "icsw_state_{:d}".format(os.getpid())
        ).add_connection(
            _conn_str,
            _sc,
        )
        if _result is not None:
            _dev = _result.xpath(".//ns:devices/ns:device[@pk]")[0]
            _lines = _result.xpath("ns:lines", start_el=_dev)[0]
            _rates = _result.xpath("ns:rates", start_el=_dev)
            if _rates:
                _rates = {int(_el.get("timeframe")): float(_el.get("rate")) for _el in _rates[0]}
                print(
                    "rate info: {}".format(
                        ", ".join(
                            [
                                "{:.2f} lines/sec in {}".format(
                                    _rates[_seconds],
                                    logging_tools.get_diff_time_str(_seconds)
                                ) for _seconds in sorted(_rates)
                            ]
                        )
                    )
                )
            else:
                print("no rate info found")
                print _rates
            _out_lines = logging_tools.new_form_list()
            for _entry in process_tools.decompress_struct(_lines.text):
                _out_lines.append(
                    [
                        logging_tools.form_entry(_entry["line_id"], header="idx"),
                        logging_tools.form_entry(
                            "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                                *_entry["line_datetime_parsed"]
                            ),
                            header="Timestamp",
                        ),
                    ] + [
                        logging_tools.form_entry(_entry[_key], header=_key) for _key in [
                            "hostname", "priority", "facility", "tag"
                        ]
                    ] + [
                        logging_tools.form_entry(_entry["text"], header="text"),
                    ]
                )
            print unicode(_out_lines)
        else:
            print("got no result from {} ({})".format(_conn_str, _ST))
    else:
        print("No logcheck-server found, skipping syslog display")


def show_vector(_dev):
    _mv = _dev.machinevector_set.all().prefetch_related(
        "mvstructentry_set",
        "mvstructentry_set__mvvalueentry_set",
    )[0]
    print
    print("showing {} ({:d} structural entries)".format(unicode(_mv), len(_mv.mvstructentry_set.all())))
    for _struct in _mv.mvstructentry_set.all():
        _key = _struct.key
        print(" {:<40s}  + {}".format(_key, unicode(_struct)))
        for _value in _struct.mvvalueentry_set.all():
            if _value.key:
                _fkey = "{}.{}".format(_key, _value.key)
            else:
                _fkey = _key
            print("   {:<40s}   - {}".format(_fkey, unicode(_value)))


def remove_graph(_dev, opt_ns):
    del_re = re.compile(opt_ns.key_re)
    _mv = _dev.machinevector_set.all().prefetch_related(
        "mvstructentry_set",
        "mvstructentry_set__mvvalueentry_set",
    )[0]
    _to_delete = []
    for _struct in _mv.mvstructentry_set.all():
        _key = _struct.key
        if del_re.match(_key):
            _to_delete.append(_struct)
    if _to_delete:
        print(
            "Found {} to delete: {}".format(
                logging_tools.get_plural("entry", len(_to_delete)),
                ", ".join([unicode(_v) for _v in _to_delete]),
            )
        )
        if opt_ns.doit:
            [_struct.delete() for _struct in _to_delete]


def dev_main(opt_ns):
    # resolve devices
    dev_dict = {
        _dev.name: _dev for _dev in device.objects.filter(Q(name__in=opt_ns.dev))
    }
    if opt_ns.groupname:
        for _dev in device.objects.filter(Q(device_group__name__in=opt_ns.groupname.split(","))):
            dev_dict[_dev.name] = _dev
    _unres = set(opt_ns.dev) - set(dev_dict.keys())
    print(
        "{}: {}{}".format(
            logging_tools.get_plural("device", len(opt_ns.dev)),
            ", ".join(sorted(opt_ns.dev)),
            ", unresolvable: {}".format(
                ", ".join(sorted(list(_unres)))
            ) if _unres else ""
        )
    )
    j_logs = JoinedLogs()
    for dev_name in sorted(dev_dict.keys()):
        cur_dev = dev_dict[dev_name]
        if opt_ns.childcom == "info":
            device_info(opt_ns, cur_dev, j_logs)
        elif opt_ns.childcom == "graphdump":
            show_vector(cur_dev)
        elif opt_ns.childcom == "removegraph":
            remove_graph(cur_dev, opt_ns)
        elif opt_ns.childcom == "syslog":
            device_syslog(opt_ns, cur_dev, j_logs)
        else:
            print(
                "unknown action {} for device {}".format(
                    opt_ns.childcom,
                    unicode(cur_dev),
                )
            )
    if opt_ns.childcom == "info":
        j_logs.show()


def overview_main(opt_ns):
    if opt_ns.name:
        try:
            _dev = device.objects.get(Q(name=opt_ns.name))
        except:
            print("0")
        else:
            print(_dev.pk)
    else:
        print("Group structure")
        for _devg in device_group.objects.all().prefetch_related("device_group"):
            print(
                "G [pk={:4d}] {}, {}".format(
                    _devg.pk,
                    unicode(_devg),
                    logging_tools.get_plural("device", _devg.device_group.all().count()),
                )
            )
            if opt_ns.devices:
                for _dev in _devg.device_group.all():
                    print(
                        "    D [pk={:4d}] {}".format(
                            _dev.pk,
                            unicode(_dev),
                        )
                    )
