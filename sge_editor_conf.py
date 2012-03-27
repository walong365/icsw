#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

import sys
import logging_tools

def main():
    fname = sys.argv[1]
    c_lines = [x.strip() for x in file(fname, "r").read().splitlines()]
    a_lines = []
    cont_line, act_line = (False, "")
    for line in c_lines:
        c_line = cont_line
        if line.endswith("\\"):
            line = line[:-1]
            cont_line = True
        else:
            cont_line = False
        if c_line:
            act_line += line
        else:
            act_line = line
        if not cont_line and act_line:
            a_lines += [act_line]
    content = dict([x.split(None, 1) for x in a_lines])
    try:
        new_keys = dict([x.split(None, 1) for x in [y.strip() for y in file("/tmp/.qconf_config", "r").read().splitlines()]])
    except:
        pass
    else:
        k_new, k_change = ([], [])
        for key, value in new_keys.iteritems():
            if content.has_key(key):
                old_val = ",".join([x.strip() for x in content.get(key, "").split(",")])
                new_val = ",".join([x.strip() for x in value.split(",")])
                if old_val != new_val:
                    k_change.append(key)
                    print "Altered key '%s' from '%s' to '%s'" % (key, old_val, new_val)
                    content[key] = new_val
            else:
                k_new.append(key)
                print "Set key '%s' to '%s'" % (key, value)
                content[key] = value
        k_new.sort()
        k_change.sort()
        if k_new or k_change:
            print "Set %s: %s, changed %s: %s" % (logging_tools.get_plural("key", len(k_new)),
                                                  ", ".join(k_new),
                                                  logging_tools.get_plural("key", len(k_change)),
                                                  ", ".join(k_change))
            file(fname, "w").write("\n".join(["%s %s" % (key, str(content[key])) for key in sorted(content.keys())] + [""]))
        try:
            os.unlink("/tmp/.qconf_config")
        except:
            pass
    
if __name__ == "__main__":
    main()
    
