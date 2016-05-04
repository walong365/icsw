PATH = "../initat/cluster/frontend/static/icsw/"

import os.path
import re
import sys
import argparse
from enum import Enum

class Mode(Enum):
    dh_mode = 1
    cd_mode = 2
    dc_mode = 3


def main(mode):
    coffefiles = []
    htmlfiles = []
    for root, dirs, files in os.walk(PATH, topdown=False):
        coffefiles.extend([os.path.join(root, f) for f in files if f.endswith("coffee")])
        htmlfiles.extend([os.path.join(root, f) for f in files if f.endswith("html")])

    matcher = re.compile('.*(directive)\((.*)|.*(service)\((.*)|.*(controller)\((.*)')

    directives = {}
    directives_file_map = {}
    directives_type_map = {}
    type_directives_map = {}
    dname_to_html_dict = {}


    for name in coffefiles:
        f = open(name, "rb")
        s = f.read()
        h_nextl = False
        h_nextl_type = ""
        f.close()

        if name not in directives:
            directives[name] = []

        for l in s.split():
            if h_nextl:
                h_nextl = False
                s = l.replace("\"", "").replace("'", "").replace(",", "").replace("(", "").replace(")", "")
                directives[name].append((h_nextl_type, s))
                directives_file_map[s] = name
                directives_type_map[s] = h_nextl_type
                if h_nextl_type not in type_directives_map:
                    type_directives_map[h_nextl_type] = []
                type_directives_map[h_nextl_type].append(s)

            h_nextl_type = "Unknown"
            match = matcher.match(l)
            if match:
                if match.group(2):
                    s = match.group(2)
                    type = match.group(1)
                elif match.group(4):
                    s = match.group(4)
                    type = match.group(3)
                elif match.group(6):
                    s = match.group(6)
                    type = match.group(5)
                else:
                    h_nextl = True
                    if match.group(1):
                        h_nextl_type = match.group(1)
                    elif match.group(3):
                        h_nextl_type = match.group(3)
                    elif match.group(5):
                      h_nextl_type = match.group(5)
                if not h_nextl:
                    s = s.replace("\"", "").replace("'", "").replace(",", "").replace("(", "").replace(")", "")
                    directives[name].append((type, s))
                    directives_file_map[s] = name
                    directives_type_map[s] = type
                    if type not in type_directives_map:
                        type_directives_map[type] = []
                    type_directives_map[type].append(s)


    for name in htmlfiles:
        f = open(name)
        data = f.read()
        f.close()

        for dname in directives_file_map:
            if dname not in dname_to_html_dict:
                dname_to_html_dict[dname] = []
            if cameltohyphen(dname) in data:
                dname_to_html_dict[dname].append(name)
            if dname in data:
                dname_to_html_dict[dname].append(name)

    if mode == Mode.dh_mode:
        print "*" * 10
        print "Directive->HTML Map"
        print "*" * 10

        for typename in type_directives_map:
            for dname in sorted(type_directives_map[typename]):
                print "%s: %s" % (typename, dname)

                for hname in dname_to_html_dict[dname]:
                    print "\t%s" % hname

    if mode == Mode.cd_mode:
        print
        print "*" * 10
        print "Coffee->Directive Map"
        print "*" * 10

        for fname in directives:
              print fname
              for x in sorted(directives[fname], key=lambda x: x[0]):
                  print "\t%s: %s" % (x[0], x[1])

    if mode == Mode.dc_mode:
        print
        print "*" * 10
        print "Directive->Coffee Map"
        print

        for typename in type_directives_map:
            for dname in sorted(type_directives_map[typename]):
                print "%s:%s -> %s" % (typename, dname, directives_file_map[dname])

def cameltohyphen(s):
    return re.sub('(?!^)([A-Z]+)', r'-\1', s).lower()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Directive Mapper")
    parser.add_argument('--mode', help='[1|2|3] for [Directive->HTML|Coffee->Directive|Directive->Coffee] mapping')

    args = parser.parse_args()

    if not vars(args)["mode"]:
        parser.print_help()
    else:
        try:
            mode = int(vars(args)["mode"])
        except:
            parser.print_help()
            sys.exit()

        if Mode(mode) not in (Mode.cd_mode, Mode.dc_mode, Mode.dh_mode):
            parser.print_help()
            sys.exit()

        main(Mode(mode))

