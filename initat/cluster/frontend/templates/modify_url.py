#!/usr/bin/python-init -Otu

import sys
import os

_path = os.path.abspath(__file__)
_dir = os.path.dirname(_path)

def main():
    map_lines = [_line.strip() for _line in file(os.path.join(_dir, "angular", "app.cs"), "r").read().split("\n") if _line.count("{% url ") and _line.strip().startswith("\"")]
    map_dict = {}
    for _line in map_lines:
        _var_name = _line.split(":")[0].strip().replace("\"", "")
        _url = _line.split(":", 1)[1].strip()
        map_dict[_url] = _var_name
    for mod_file in sys.argv[1:]:
        print("Operating on file '{}' ...".format(mod_file))
        _old_content = file(mod_file, "r").read()
        _replaced = 0
        _found = True
        while _found:
            _found = False
            for _src, _dest in map_dict.iteritems():
                if _old_content.count(_src):
                    _old_content = _old_content.replace(_src, "\"{{{{ ICSW_URLS.{} }}}}\"".format(_dest))
                    _found = True
                    _replaced += 1
        if _replaced:
            print("found {:d} replacements, writing new file to {}.new".format(_replaced, mod_file))
            file("{}.new".format(mod_file), "w").write(_old_content)

if __name__ == "__main__":
    main()
