#!/usr/bin/python-init -Otu
# add to GridEngine config by adding
# -jsv /opt/sge/3rd_paryt/test_jsv_log_accept.py to sge_request

from initat.tools.jsv_base import JSVBase


ACCEPT_DICT = {
    "barracuda.q": 4,
    "cachalot.q": 8,
    "fugu.q": 16,
    "narwal.q": 8,
    "shark.q": 20,
    "stingray.q": 8,
    "super.q": 8,
}


class MyJSV(JSVBase):
    def on_verify(self):
        if self.has_param("pe_name") and self.has_param("q_hard"):
            _pe_name = self.get_param("pe_name")
            _q_name = self.get_param("q_hard")
            _min_pe, _max_pe = (int(self.get_param("pe_min")), int(self.get_param("pe_max")))
            if _q_name not in ACCEPT_DICT:
                self.accept()
            else:
                if _min_pe != _max_pe:
                    self.reject("min_pe and max_pe differs")
                else:
                    _mult = ACCEPT_DICT[_q_name]
                    if int(_min_pe / _mult) * _mult != _min_pe:
                        self.reject("number of requests slots must be a multiple of {:d} ({:d})".format(_mult, _min_pe))
                    else:
                        self.accept()
        else:
            self.accept()

MyJSV().main()
