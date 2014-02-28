#!/usr/bin/python-init -Otu

import argparse
import logging_tools
import os
import pprint
import process_tools
import re
import sys

REPO_DIR = "/etc/zypp/repos.d"
KV_RE = re.compile("^\s*(?P<key>\S+)\s*=\s*(?P<value>.*)\s*$")
NEW_REPOS = set(["base", "cluster", "extra"])
NO_DEVEL_REPOS = set(["extra"])
URL_RE = re.compile("^(http|dir)://.*(www.initat.org|local/packages).*/RPMs/(?P<dist>[^/]+)($|/(?P<rest>.*?)/*$)")
REPO_RE=re.compile("^(?P<name>.*?)(-(?P<version>[^-]+))*$")

class repo(dict):
    def __init__(self, name, opts):
        super(dict, self).__init__()
        self.opts = opts
        self.name = name
        self._read()
    def _read(self):
        self.content = file(self.name, "r").read().split("\n")
        # print "read %s from %s" % (
        #    logging_tools.get_plural("line", len(self.content)),
        #    name)
        self._to_dict()
        if "baseurl" not in self:
            print "no baseurl in repo %s, ingoring" % (self.name)
            return
        b_url = self["baseurl"]
        if b_url.count("www.initat.org") or (b_url.startswith("dir:///") and b_url.count("packages/RPMs")):
            url_m = URL_RE.match(b_url)
            # print b_url, url_m
            if url_m:
                rest = url_m.groupdict()["rest"]
                if self.opts.migrate and rest in ["", "", None]:
                    print "migrating repo %s to split-repo" % (self["name"])
                    # disable old
                    self._emit(self.name, enabled="0")
                    for new_repo in NEW_REPOS:
                        new_f_name = os.path.join(
                            os.path.dirname(self.name),
                            "%s_%s.repo" % (self["name"], new_repo)
                        )
                        self._emit(
                            new_f_name,
                            name="%s_%s" % (self["name"], new_repo),
                            # to no migrate to devel repos
                            baseurl=os.path.join(self["baseurl"], new_repo),
                            )
                elif self.opts.to_devel and rest and not rest.endswith("-devel"):
                    print "migrating repo %s to devel (rest is '%s')" % (self["name"], rest)
                    repo_m = REPO_RE.match(rest)
                    new_url = "%s/%s-devel" % (b_url[:-(len(rest) + 1)], repo_m.group("name"))
                    print "relacing url '%s' with '%s'" % (b_url, new_url)
                    if rest not in NO_DEVEL_REPOS:
                        self._emit(
                            self.name,
                            baseurl=new_url,
                            )
    def _to_dict(self):
        for line in self.content:
            kv_m = KV_RE.match(line)
            if kv_m:
                self[kv_m.group("key").lower()] = kv_m.group("value")
    def _emit(self, f_name, **kwargs):
        c_dict = dict([(key, kwargs.get(key, value)) for key, value in self.iteritems()])
        # pprint.pprint(c_dict)
        content = ["[%s]" % (c_dict["name"])]
        for key, value in c_dict.iteritems():
            content.append("%s=%s" % (key, value))
        file(f_name, "w").write("\n".join(content + [""]))

def main():
    arg_p = argparse.ArgumentParser()
    arg_p.add_argument("--migrate", dest="migrate", default=False, action="store_true", help="migrate repos [%(default)s]")
    arg_p.add_argument("--to-devel", dest="to_devel", default=False, action="store_true", help="rewrite repos to -devel repos [%(default)s]")
    opts = arg_p.parse_args()
    # transform repos
    for r_name in os.listdir(REPO_DIR):
        try:
            cur_repo = repo(os.path.join(REPO_DIR, r_name), opts)
        except:
            print "error reading repo %s: %s" % (
                r_name,
                process_tools.get_except_info())

if __name__ == "__main__":
    main()
