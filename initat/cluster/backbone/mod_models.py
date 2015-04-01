#!/usr/bin/python-init -Otu

def main():
    lines = file("models.py", "r").read().split("\n")
    new_lines = []
    for line in lines:
        if line.startswith("class"):
            c_name = line.split()[1].split("(")[0]
            new_s = ""
            for cur_c in c_name:
                if cur_c.lower() != cur_c:
                    if new_s and not new_s.endswith("_"):
                        new_s = "%s_" % (new_s)
                new_s = "%s%s" % (new_s, cur_c.lower())
            line = "class %s(%s" % (new_s, line.split("(")[1])
        elif line.count("primary_key=True"):
            idx_name = line.strip().split()[0]
            if idx_name != "idx":
                line = "    idx = models.IntegerField(db_column=\"%s\", primary_key=True)" % (idx_name)
        elif line.count("ForeignKey") and line.count("db_column"):
            parts = line.strip().split()
            parts.pop(-1)
            line = "    %s)" % (" ".join(parts)[:-1])
            print line
        new_lines.append(line)
    if lines != new_lines:
        print "writing to m2.py"
        file("m2.py", "w").write("\n".join(new_lines))
    else:
        print "no changes"

if __name__ == "__main__":
    main()
    