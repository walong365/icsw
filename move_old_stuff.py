#!/usr/bin/python-init -Ot

import os
import sys
import pprint
import shutil

OLD_DIR_NAME = ".old"

def main():
    if len(sys.argv) != 2:
        print "Need directory"
        sys.exit(-1)
    start_dir = sys.argv[1]
    if not os.path.isdir(start_dir):
        print "'%s' is not a directory" % (start_dir)
        sys.exit(-2)
    for dir_name, dir_list, file_list in os.walk(start_dir):
        if dir_name.endswith(OLD_DIR_NAME):
            # skip .old-dirs
            pass
        else:
            if OLD_DIR_NAME not in dir_list:
                os.mkdir("%s/%s" % (dir_name, OLD_DIR_NAME))
            rpm_dict = {}
            # get rpm-list
            for file_name in file_list:
                if os.path.isfile("%s/%s" % (dir_name, file_name)):
                    if file_name.endswith(".rpm"):
                        file_parts = file_name.split(".")
                        if file_parts[-1] == "rpm":
                            file_parts.pop(-1)
                        if file_parts[-1] in ["i386", "i586", "i686", "noarch", "x86_64", "x86-64", "src"]:
                            act_arch = file_parts.pop(-1)
                        else:
                            act_arch = "au"
                        #rel_part = ".".join(file_parts.pop(-1).split(".")[:-2])
                        #ver_part = file_parts.pop(-1)
                        file_parts = (".".join(file_parts)).split("-")
                        if len(file_parts) >= 3:
                            act_rel = file_parts.pop(-1)
                            act_ver = file_parts.pop(-1)
                            if act_ver[-1].isdigit() and act_ver[0].isdigit() and act_rel.isdigit():
                                act_name = "-".join(file_parts)
                                rpm_dict.setdefault(act_name, {}).setdefault(act_arch, []).append(([int(part) if part.isdigit() else part for part in act_ver.split(".")], int(act_rel), file_name))
            for rpm_name, arch_dict in rpm_dict.iteritems():
                for act_arch, rpm_list in arch_dict.iteritems():
                    rpm_list.sort()
                    while len(rpm_list) > 3:
                        ver_stuff, rel_stuff, full_name = rpm_list.pop(0)
                        shutil.move("%s/%s" % (dir_name,
                                               full_name),
                                    "%s/.old/%s" % (dir_name,
                                                    full_name))
                        pyi_file = "%s/%s.pyi" % (dir_name, full_name)
                        if os.path.isfile(pyi_file):
                            os.unlink(pyi_file)

if __name__ == "__main__":
    main()
    
