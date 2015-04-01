#!/usr/bin/python-init -Otu

import sys
import os

IGNORE_TABLES = ["config_type"]

class handle_insert_line(object):
    def __init__(self, in_line):
        parts = in_line.split(None, 4)
        t_name = parts[2]
        values = parts[-1][1:-2].split("),(")
        values = "(%s)" % ("),(".join([self.handle(sub_value) for sub_value in values]))
        self.line = "INSERT INTO %s VALUES %s;" % (t_name, values)
    def handle(self, sub_value):
        return "_overwrite_handle"
        
class handle_network_network_device_type(handle_insert_line):
    def handle(self, sub_value):
        sub_parts = sub_value.split(",")
        if len(sub_parts) == 4:
            sub_parts.pop(-1)
        return ",".join(sub_parts)

class handle_user(handle_insert_line):
    def handle(self, sub_value):
        sub_parts = sub_value.split(",")
        if len(sub_parts) == 21:
            # nt/lm_password missing
            sub_parts = sub_parts[:20] + ["''", "''"] + [sub_parts[20]]
        return ",".join(sub_parts)

def main():
    for line in sys.stdin.readlines():
        line = line.rstrip()
        if line.lower().startswith("insert into"):
            ins_table = line.lower().strip().split()[2][1:-1]
            if ins_table == "network_network_device_type":
                line = handle_network_network_device_type(line).line
            if ins_table == "user":
                line = handle_user(line).line
            elif ins_table in IGNORE_TABLES:
                # ignore inserts into config_type
                line = None
        elif line.lower().startswith("lock tables"):
            ins_table = line.lower().strip().split()[2][1:-1]
            if ins_table in IGNORE_TABLES:
                # ignore locks of config_type
                line = None
        elif line.startswith("/*") and line.endswith("*/;"):
            if line.count("`") == 2:
                table_name = line.split("`")[1]
                if table_name in IGNORE_TABLES:
                    line = None
            
        if line is not None:
            print line

if __name__ == "__main__":
    main()
    