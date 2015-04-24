# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

from initat.cluster.backbone.models import mon_device_templ, mon_service_templ
from initat.tools import logging_tools


__all__ = [
    "device_templates", "service_templates",
]


class device_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = None
        for dev_templ in mon_device_templ.objects.all().select_related("host_check_command"):
            self[dev_templ.pk] = dev_templ
            if dev_templ.is_default:
                self.__default = dev_templ
        self.log(
            "Found {} ({})".format(
                logging_tools.get_plural("device_template", len(self.keys())),
                ", ".join([cur_dt.name for cur_dt in self.itervalues()])
            )
        )
        if self.__default:
            self.log(
                "Found default device_template named '%s'" % (self.__default.name)
            )
        else:
            if self.keys():
                self.__default = self.values()[0]
                self.log(
                    "No default device_template found, using '%s'" % (self.__default.name),
                    logging_tools.LOG_LEVEL_WARN
                )
            else:
                self.log(
                    "No device_template founds, skipping configuration....",
                    logging_tools.LOG_LEVEL_ERROR
                )

    def is_valid(self):
        return self.__default and True or False

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[device_templates] %s" % (what), level)

    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if act_key not in self:
            self.log(
                "key {} not known, using default {} ({:d})".format(
                    str(act_key),
                    unicode(self.__default),
                    self.__default.pk,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            act_key = self.__default.pk
        return super(device_templates, self).__getitem__(act_key)


class service_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = 0
        for srv_templ in mon_service_templ.objects.all().prefetch_related(
            "mon_device_templ_set",
            "mon_contactgroup_set"
        ):
            # db_rec["contact_groups"] = set()
            # generate notification options
            not_options = []
            for long_name, short_name in [
                ("nrecovery", "r"), ("ncritical", "c"), ("nwarning", "w"), ("nunknown", "u"), ("nflapping", "f"), ("nplanned_downtime", "s")
            ]:
                if getattr(srv_templ, long_name):
                    not_options.append(short_name)
            if not not_options:
                not_options.append("n")
            srv_templ.notification_options = not_options
            self[srv_templ.pk] = srv_templ
            self[srv_templ.name] = srv_templ
            srv_templ.contact_groups = list(set(srv_templ.mon_contactgroup_set.all().values_list("name", flat=True)))
        if self.keys():
            self.__default = self.keys()[0]
        self.log("Found %s (%s)" % (
            logging_tools.get_plural("device_template", len(self.keys())),
            ", ".join([cur_v.name for cur_v in self.values()])))

    def is_valid(self):
        return True

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[service_templates] %s" % (what), level)

    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if act_key not in self:
            self.log(
                "key {} not known, using default {} ({:d})".format(
                    str(act_key),
                    unicode(self.__default),
                    self.__default.pk,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            act_key = self.__default.pk
        return super(service_templates, self).__getitem__(act_key)
