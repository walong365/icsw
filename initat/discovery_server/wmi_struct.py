#
# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <mallinger@init.at>
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
import csv
import itertools
import logging
from io import StringIO

logger = logging.getLogger("discovery.wmi_struct")


# itertools recipe
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class WmiUtils(object):

    WMIC_BINARY = "/opt/cluster/bin/wmic"
    DELIMITER = "\01"
    DELIMITER_NEWLINE = "\02"

    @classmethod
    def get_wmic_cmd(cls, username, password, target_ip, columns, table, where_clause=""):
        # NOTE: this is an injection vulnerability
        # similar to wmi client wrapper https://pypi.python.org/pypi/wmi-client-wrapper
        return (
            cls.WMIC_BINARY,
            "--delimiter={}".format(cls.DELIMITER),
            "--user={username}%{password}".format(
                username=username,
                password=password,
            ),
            "//{host}".format(host=target_ip),
            "SELECT {} FROM {} {}".format(", ".join(columns), table, where_clause),
        )

    # NOTE: similar to wmi client wrapper https://pypi.python.org/pypi/wmi-client-wrapper

    class WmiList(object):
        def __init__(self, wmi_list):
            self.wmi_list = wmi_list

        def try_parse(self):
            """Only use if you are sure that every ',' in the input is an item separator"""
            return self.wmi_list.split(",")

        @classmethod
        def handle(cls, obj):
            if isinstance(obj, cls):
                return obj.try_parse()
            else:
                return [obj]  # wmi just returns single objects for list types if there is only one entry

    @classmethod
    def parse_wmic_output(cls, output, try_handle_lists=False):
        """
        Parses output from the wmic command and returns json.
        NOTE: Does not parse lists properly, so we by default return WmiList which you have to parse yourself, see above
        @param try_handle_lists: try to parse lists
        """
        # remove newlines and whitespace from the beginning and end
        output = output.strip()

        # Quick parser hack- make sure that the initial file or section is also
        # counted in the upcoming split.
        if output[:7] == "CLASS: ":
            output = "\n" + output

        # There might be multiple files in the output. Track how many there
        # should be so that errors can be raised later if something is
        # inconsistent.
        expected_sections_count = output.count("\nCLASS: ")

        # Split up the file into individual sections. Each one corresponds to a
        # separate csv file.
        sections = output.split("\nCLASS: ")

        # The split causes an empty string as the first member of the list and
        # it should be removed because it's junk.
        if sections[0] == "":
            sections = sections[1:]

        assert len(sections) is expected_sections_count

        items = []

        for section in sections:
            # remove the first line because it has the query class
            section = "\n".join(section.split("\n")[1:])

            section = cls._patch_newlines(section)

            strio = StringIO(section)

            moredata = list(csv.DictReader(strio, delimiter=cls.DELIMITER))
            items.extend(moredata)

        # walk the dictionaries!
        return cls._fix_dictionary_output(items, try_handle_lists=try_handle_lists)

    @classmethod
    def _patch_newlines(cls, section_text):
        # wmic does not produce valid csv since newlines are contained in text fields
        # (NTLogEvent can contain \n as well as \r\n
        # we fix this by concatenating all lines until the line has as many delimiters as a full entry
        lines = section_text.replace("\r", "").split("\n")
        num_delimiters = lines[0].count(cls.DELIMITER)
        fixed_lines = [lines[0]]
        cur_line = ""
        fixing = False
        for line, next_line in pairwise(itertools.chain(lines[1:], [None])):
            # have to add dummy last elem, else last line would never be `line`

            if cur_line != "":
                cur_line += cls.DELIMITER_NEWLINE  # add this to show where newlines would have been
            cur_line += line

            if cur_line.count(cls.DELIMITER) == num_delimiters:
                # handle newlines in last entry
                # - in that case, the num_delimiter check says yes, but actually the next line
                #   still belongs to the entry
                # find out by checking whether the next line has delimiters
                # - it cannot have them if is the the part of the last entry after a newline
                # - TODO: if the first line has newlines, that part is appended to the last entry
                if next_line is None or cls.DELIMITER in next_line:  # next line is valid line
                    fixed_lines.append(cur_line)
                    if fixing:
                        fixing = False
                    cur_line = ""
                else:
                    # just add next part in loop start
                    pass
            elif cur_line.count(cls.DELIMITER) >= num_delimiters:
                logger.error("Failed to fix line (should contain {} delimiters): {}".format(
                    num_delimiters, cur_line
                ))
                cur_line = ""
            else:
                fixing = True

        if cur_line != "":
            logger.error("Failed to fix line (should contain {} delimiters): {}".format(
                num_delimiters, cur_line
            ))

        # print "\n" * 5, 'fixed:'
        # print "\n".join(fixed_lines).replace(cls.DELIMITER, "<SEP>") + "\n"

        return "\n".join(fixed_lines) + "\n"

    @classmethod
    def _reinsert_newlines(cls, s):
        return s.replace(cls.DELIMITER_NEWLINE, "\n")

    @classmethod
    def _fix_dictionary_output(cls, incoming, try_handle_lists):
        """
        The dictionary doesn't exactly match the traditional python-wmi output.
        For example, there's "True" instead of True. Integer values are also
        quoted. Values that should be "None" are "(null)".

        This can be fixed by walking the tree.

        The Windows API is able to return the types, but here we're just
        guessing randomly. But guessing should work in most cases. There are
        some instances where a value might happen to be an integer but has
        other situations where it's a string. In general, the rule of thumb
        should be to cast to whatever you actually need, instead of hoping that
        the output will always be an integer or will always be a string..
        """
        if isinstance(incoming, list):
            output = []

            for each in incoming:
                output.append(cls._fix_dictionary_output(each, try_handle_lists))

        elif isinstance(incoming, dict):
            output = dict()

            for (key, value) in list(incoming.items()):
                if value == "(null)":
                    output[key] = None
                elif value == "True":
                    output[key] = True
                elif value == "False":
                    output[key] = False
                elif isinstance(value, str) and len(value) > 1 and value[0] == "(" and value[-1] == ")":
                    val = WmiUtils.WmiList(cls._reinsert_newlines(value[1:-1]))
                    if try_handle_lists:
                        val = val.try_parse()
                    output[key] = val
                elif isinstance(value, str):
                    output[key] = cls._reinsert_newlines(value)
                elif isinstance(value, dict):
                    output[key] = cls._fix_dictionary_output(value, try_handle_lists)
        else:
            raise RuntimeError("Invalid type in _fix_dictionary_output: {} ({})".format(type(incoming), incoming))

        return output
