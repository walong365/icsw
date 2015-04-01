#!/usr/bin/python-init -Otu                                                                                                                                                                                                                                                    

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.cluster.backbone.models import group, user
import csv

def main():
    c_group = csv.DictReader(file("group.csv", "r"))
    c_user = csv.DictReader(file("user.csv", "r"))
    g_dict, u_dict = (
        {
            _g.groupname: _g for _g in group.objects.all()
        },
        {
            _u.login: _u for _u in user.objects.all()
        }
    )
    _gp_idx = {}
    for _g in c_group:  
        _gp_idx[int(_g["ggroup_idx"])] = _g["ggroupname"]
        if _g["ggroupname"] not in g_dict:
            new_g = group.objects.create(
                groupname=_g["ggroupname"],
                homestart=_g["homestart"],
                comment=_g["groupcom"],
                gid=int(_g["gid"]),
            )
            _g[new_g.groupname] = new_g
    for _u in c_user:
        if _u["login"] not in u_dict:
            new_u = user.objects.create(
                uid=int(_u["uid"]),
                email=_u["useremail"],
                lm_password=_u["lm_password"],
                nt_password=_u["nt_password"],
                group=g_dict[_gp_idx[int(_u["ggroup"])]],
                password=_u["password"],
                login=_u["login"],
            )
            _u[new_u.login] = new_u

if __name__ == "__main__":
    main()

