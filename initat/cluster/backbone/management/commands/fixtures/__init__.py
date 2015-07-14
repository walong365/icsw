import os
from .config_catalog_fixtures import get_sys_conf_cat

get_sys_conf_cat()


def add_fixtures(**kwargs):
    _path = os.path.dirname(__file__)
    for _file in os.listdir(_path):
        if _file.endswith(".py") and _file not in ["__init__.py"]:
            new_mod = __import__(_file.split(".")[0], globals(), locals())
            if "add_fixtures" in dir(new_mod):
                new_mod.add_fixtures(**kwargs)
