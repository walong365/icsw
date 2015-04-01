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
""" content emitter for config of md-config-server """


__all__ = [
    "content_emitter",
]


class content_emitter(object):
    def ignore_content(self, in_dict):
        return False

    def _emit_content(self, dest_type, in_dict):
        if self.ignore_content(in_dict):
            return []
        _content = [
            "define {} {{".format(dest_type)
        ] + [
            "  {} {}".format(
                act_key,
                self._build_value_string(act_key, in_dict[act_key])
            ) for act_key in sorted(in_dict.iterkeys())
        ] + [
            "}", ""
        ]
        return _content

    def _build_value_string(self, _key, in_list):
        if in_list:
            # check for unique types
            if len(set([type(_val) for _val in in_list])) != 1:
                raise ValueError("values in list {} for key {} have different types".format(str(in_list), _key))
            else:
                _first_val = in_list[0]
                if type(_first_val) in [int, long]:
                    return ",".join(["{:d}".format(_val) for _val in in_list])
                else:
                    if "" in in_list:
                        raise ValueError("empty string found in list {} for key {}".format(str(in_list), _key))
                    return u",".join([unicode(_val) for _val in in_list])
        else:
            return "-"
