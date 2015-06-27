#
# this file is part of collectd
#
# Copyright (C) 2015 Andreas Lang-Nevyjel init.at
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
""" collectd, threshold checker """

import time

from initat.tools import logging_tools
from initat.cluster.backbone.models import SensorThreshold, \
    SensorThresholdAction, device
from django.db.models import Q
from initat.icsw.service import clusterid
from django.core.mail import send_mail

from .config import global_config


class Threshold(object):
    class Meta:
        # maximum time between values (==20 minutes)
        max_diff_time = 1200
        # number of values to store
        values_to_store = 20

    def __init__(self, container, db_obj, log_com):
        self.__container = container
        self.__log_com = log_com
        self.dev_idx = db_obj.mv_value_entry.mv_struct_entry.machine_vector.device_id
        self.key = db_obj.mv_value_entry.full_key
        self.th = db_obj
        if db_obj.mv_value_entry.mv_struct_entry.se_type in ["mvl"]:
            # mvl, special handling
            self.lookup_key = "{}.{:d}".format(db_obj.mv_value_entry.mv_struct_entry.key, db_obj.mv_value_entry.rra_idx)
        else:
            self.lookup_key = self.key
        self.log("init '{}'".format(unicode(db_obj)))
        self.__cycle = 0
        self.__values = []
        self.log_info()
        self.reset_flags()
        # print unicode(_mvv.mv_struct_entry.machine_vector.device), unicode(_mvv), _mvv.full_key

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[TH {:d} {}] {}".format(self.th.idx, self.th.name, what), log_level)

    def delete(self):
        self.log("removing threshold")

    def update(self, db_obj):
        self.log("updating sensor from db")
        if self.th.lower_value != db_obj.lower_value or self.th.upper_value != db_obj.upper_value:
            _reset_flags = True
        else:
            _reset_flags = False
        self.th = db_obj
        self.log_info()
        if _reset_flags:
            self.reset_flags()

    def log_info(self):
        self.log(
            "lower threshold is {:.4f}, upper threshold is {:.4f}".format(
                self.th.lower_value,
                self.th.upper_value,
            )
        )

    def reset_flags(self):
        self.log("resetting state flags")
        # flag: value in hysteresis range
        self.__upper_triggered = False
        self.__lower_triggered = False

    def get_ut(self):
        return self.__upper_triggered

    def set_ut(self, val):
        if val != self.__upper_triggered:
            self.log("upper_triggered changes from {} to {}".format(self.__upper_triggered, val))
            if val:
                self.log_latest_values()
            self.__upper_triggered = val

    upper_triggered = property(get_ut, set_ut)

    def get_lt(self):
        return self.__lower_triggered

    def set_lt(self, val):
        if val != self.__lower_triggered:
            self.log("lower_triggered changes from {} to {}".format(self.__lower_triggered, val))
            if val:
                self.log_latest_values()
            self.__lower_triggered = val

    lower_triggered = property(get_lt, set_lt)

    def log_latest_values(self):
        _n = min(4, len(self.__values))
        self.log(
            "cycle {:d}, latest {:d} values (bounds: [{:.4f}, {:.4f}]:".format(
                self.__cycle,
                _n,
                self.th.lower_value,
                self.th.upper_value,
            )
        )
        for _time, _val in self.__values[-1:-_n - 1:-1]:
            self.log(
                "  - {:.2f} :: {:.4f} {}".format(
                    _time,
                    _val,
                    "<<" if _val < self.th.lower_value else (
                        ">>" if _val > self.th.upper_value else ""
                    ),
                )
            )

    def feed(self, value):
        self.__cycle += 1
        cur_time = time.time()
        if not self.__values:
            self.__values = [(cur_time, value)]
        else:
            if abs(self.__values[-1][0] - cur_time) > self.Meta.max_diff_time:
                self.log(
                    "time difference between values to big, discarding previous values",
                    logging_tools.LOG_LEVEL_WARN
                )
                self.reset_flags()
                self.__values = [(cur_time, value)]
            else:
                self.__values.append((cur_time, value))
        if value < self.th.lower_value:
            self.upper_triggered = False
        elif value > self.th.upper_value:
            self.lower_triggered = False
        if len(self.__values) > 1:
            _prev_value = self.__values[-2][1]
            if _prev_value <= self.th.upper_value and value > self.th.upper_value and not self.upper_triggered:
                # trigger upper
                self.trigger("upper")
            elif _prev_value >= self.th.lower_value and value < self.th.lower_value and not self.lower_triggered:
                # trigger lower
                self.trigger("lower")
        # store only latest N values
        self.__values = self.__values[-self.Meta.values_to_store:]

    def trigger(self, what):
        setattr(self, "{}_triggered".format(what), True)
        _action = getattr(self.th, "{}_sensor_action".format(what))
        _mail = getattr(self.th, "{}_mail".format(what))
        _value = getattr(self.th, "{}_value".format(what))
        _enabled = getattr(self.th, "{}_enabled".format(what))
        self.log(
            "trigger {}: action is {}, send_mail is {}, enabled: {}".format(
                what,
                unicode(_action) if _action else "none",
                _mail,
                str(_enabled),
            )
        )
        # create actionentry
        if _action is not None and _enabled:
            self.log("create SensorThresholdAction entry")
            new_sta = SensorThresholdAction(
                sensor_threshold=self.th,
                sensor_action=_action,
                action_type=what,
                mail=_mail,
                value=_value,
                device_selection=self.th.device_selection,
            )
            new_sta.save()
            for _user in self.th.notify_users.all():
                new_sta.notify_users.add(_user)
        if _mail and _enabled:
            _cluster_id = clusterid.get_cluster_id() or "N/A"
            _from = "{}@{}".format(
                global_config["FROM_NAME"],
                global_config["FROM_ADDRESS"]
            )
            _subject = "{} Threshold event from {} for {} ({})".format(
                what,
                global_config["SERVER_FULL_NAME"],
                unicode(self.th.name),
                _cluster_id,
            )
            _to_users = [_user for _user in self.th.notify_users.all() if _user.email]
            # build message
            _message = [
                "The {} event {} was triggered by device {}".format(
                    what,
                    unicode(self.th),
                    unicode(device.objects.get(Q(pk=self.dev_idx))),
                ),
                "",
                "lower_threshold: {:.4f}".format(self.th.lower_value),
                "upper_threshold: {:.4f}".format(self.th.upper_value),
                "",
                "threshold value is {:.4f}, {:d} values in cache".format(
                    _value,
                    len(self.__values),
                )
            ]
            for _time, _val in self.__values[::-1]:
                _message.append(
                    "  - {} :: {:.4f} {}".format(
                        time.ctime(_time),
                        _val,
                        "<" if _val < self.th.lower_value else (
                            ">" if _val > self.th.upper_value else "="
                        ),
                    )
                )
            _message.extend(
                [
                    "",
                    "{} to notify:".format(logging_tools.get_plural("user", _to_users))
                ]
            )
            for _user in _to_users:
                _message.append(u"   {} ({})".format(unicode(_user), _user.email))
            self.log(
                "sending email with subject '{}' to {}:".format(
                    _subject,
                    logging_tools.get_plural("recipient", len(_to_users)),
                )
            )
            for _user in self.th.notify_users.all():
                self.log(u"   {} ({})".format(unicode(_user), _user.email))
            if _to_users:
                _to_mails = [_user.email for _user in _to_users]
                send_mail(_subject, "\n".join(_message), _from, _to_mails)


class ThresholdContainer(object):
    def __init__(self, proc):
        self.proc = proc
        self.__log_com = proc.log
        self.enabled = global_config["ENABLE_SENSOR_THRESHOLDS"]
        # sync thresholds once per hour
        if self.enabled:
            self.sync = self._sync_enabled
        else:
            self.sync = self._sync_disabled
        self.proc.register_timer(self.sync, 3600)
        self.log("init")
        self.th_dict = {}
        self.sync()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[TC] {}".format(what), log_level)

    def _sync_disabled(self):
        self.log("thresholds are globally disabled, not syncing", logging_tools.LOG_LEVEL_WARN)
        self.dev_dict = {}

    def _sync_enabled(self):
        self.log("syncing thresholds")
        remove_pks = self.th_dict.keys()
        new_pks = set()
        for _th in SensorThreshold.objects.all().select_related(
            "mv_value_entry__mv_struct_entry__machine_vector__device",
        ):
            _mvv = _th.mv_value_entry
            if _th.idx in self.th_dict:
                remove_pks.remove(_th.idx)
                self.th_dict[_th.idx].update(_th)
            else:
                self.th_dict[_th.idx] = Threshold(self, _th, self.__log_com)
                new_pks.add(_th.idx)
        if new_pks:
            self.log("{} found".format(logging_tools.get_plural("new threshold", len(new_pks))))
        if remove_pks:
            self.log("{} to delete".format(logging_tools.get_plural("old threshold", len(remove_pks))))
            [self.th_dict[idx].delete() for idx in remove_pks]
            for idx in remove_pks:
                del self.th_dict[idx]
        self.dev_dict = {}
        for _th in self.th_dict.itervalues():
            self.dev_dict.setdefault(_th.dev_idx, {})[_th.lookup_key] = _th
        # pprint.pprint(self.dev_dict)

    def device_has_thresholds(self, dev_idx):
        return dev_idx in self.dev_dict

    def feed(self, dev_idx, name, value, mv_flag):
        if mv_flag:
            for _idx, _val in enumerate(value.split(":")):
                self._feed_val(dev_idx, "{}.{:d}".format(name, _idx), float(_val))
        else:
            self._feed_val(dev_idx, name, value)

    def _feed_val(self, dev_idx, key, value):
        if key in self.dev_dict.get(dev_idx, {}):
            self.dev_dict[dev_idx][key].feed(value)
            if key == "apc.ampere.used" and False:
                # test code
                _th = self.dev_dict[dev_idx][key]
                for _val in [2.5, 2.8, 3.1, 4.0, 1.0, 3.0, 3.2, 3.1, 3.05, 3.01, 3.07, 3.12, 2.9, 3.01, 3.11]:
                    time.sleep(0.1)
                    _th.feed(_val)
