# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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


from lxml.builder import E


__all__ = [
    "StructuredContentEmitter",
    "FlatContentEmitter",
]


class StructuredContentEmitter(object):
    def emit_content(self):
        _content = [
            u"define {} {{".format(self.obj_type)
        ] + [
            u"  {} {}".format(
                act_key,
                self._build_value_string(act_key)
            ) for act_key in sorted(self.iterkeys())
        ] + [
            u"}",
            ""
        ]
        return _content

    def emit_xml(self):
        new_node = getattr(
            E, self.obj_type
        )(
            **dict(
                [
                    (
                        key,
                        self.build_value_string(key)
                    ) for key in sorted(self.iterkeys())
                ]
            )
        )
        return new_node

    def _build_value_string(self, _key):
        in_list = self[_key]
        # print self.obj_type, _key, in_list
        if in_list:
            # check for unique types
            if len(set([type(_val) for _val in in_list])) != 1:
                raise ValueError(
                    "values in list {} for key {} have different types".format(
                        str(in_list),
                        _key
                    )
                )
            else:
                _first_val = in_list[0]
                if type(_first_val) in [int, long]:
                    return ",".join(["{:d}".format(_val) for _val in in_list])
                else:
                    if "" in in_list:
                        raise ValueError(
                            "empty string found in list {} for key {}".format(
                                str(in_list),
                                _key
                            )
                        )
                    return u",".join([unicode(_val) for _val in in_list])
        else:
            return "-"


class FlatContentEmitter(object):
    def emit_content(self):
        c_lines = []
        last_key = None
        for key in sorted(self.keys()):
            if last_key:
                if last_key[0] != key[0]:
                    c_lines.append("")
            last_key = key
            value = self[key]
            if value is None:
                # for headers
                c_lines.append(key)
            else:
                if type(value) == list:
                    pass
                elif type(value) in [int, long]:
                    value = ["{:d}".format(value)]
                else:
                    value = [value]
                for act_v in value:
                    c_lines.append(u"{}={}".format(key, act_v))
        return c_lines
