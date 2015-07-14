#!/usr/bin/python-init -Otu
# add to GridEngine config by adding
# -jsv /opt/sge/3rd_paryt/test_jsv_log_accept.py to sge_request

from initat.tools.jsv_base import JSVBase


class MyJSV(JSVBase):
    def on_verify(self):
        self.show_params()
        self.show_envs()
        self.accept()

MyJSV().main()
