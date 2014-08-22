#!/usr/bin/python-init -Otu

import sys
import logging_tools
import process_tools
import subprocess
import os
import email
from email.parser import FeedParser
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import email.mime.multipart
import mimetypes

SENDMAIL_BIN = process_tools.find_file("sendmail")


class disclaimer_handler(object):
    def __init__(self):
        self._log_template = logging_tools.get_logger(
            "disclaimer",
            "uds:/var/lib/logging-server/py_log_zmq",
            zmq=True
        )
        self.args = sys.argv
        self.log("{:d} args: {}".format(len(self.args), ", ".join(self.args)))
        self.log("sendmail is at {}".format(SENDMAIL_BIN))

    def recv_mail(self):
        self.src_mail = sys.stdin.read()
        self.log("src mail has {}".format(logging_tools.get_size_str(len(self.src_mail))))
        self.dst_mail = self.src_mail

    def log_mail(self, prefix, _mail):
        self.log("email structure {} processing".format(prefix))
        self.log("content type is {}".format(_mail.get_content_type()))
        self.log("is_multipart: {}".format("yes" if _mail.is_multipart() else "no"))
        _dict = {}
        for _idx, _part in enumerate(_mail.walk(), 1):
            self.log("part {:<3d} has type {}".format(_idx, _part.get_content_type()))

    def process(self):
        my_parser = FeedParser()
        my_parser.feed(self.src_mail)
        _email = my_parser.close()
        _from = email.utils.parseaddr(_email["From"])
        _to = [email.utils.parseaddr(_value) for _value in _email["To"].split(",")]
        self.log("to ({:d}) is {}".format(len(_to), ", ".join(["'{}' / '{}'".format(_val[0], _val[1]) for _val in _to])))
        self.log("from is '{}' / '{}'".format(_from[0], _from[1]))
        # fixme
        # _to = _email.get_all("To", [])
        self.log_mail("before", _email)
        self.log("{:d} defects: {}".format(len(_email.defects), ", ".join([str(_val) for _val in _email.defects]) or "---"))
        if not _email.is_multipart():
            _payload = _email.get_payload()
            # self.log("*** {}".format(_email.get_payload()))
            # self.log("{}".format(type(_email.get_payload())))
            _text = MIMEText(_email.get_payload())
            # print _text, type(_text)
            _email.set_payload([_text])
            self.log("changing content-type to multipart/mixed")
            _email.set_type("multipart/mixed")
            # self.log(str(_email.get_params()))
        for add_file in ["disclaimer.txt", "default.html"]:
            _path = os.path.join("/etc/postfix", add_file)
            if os.path.isfile(_path):
                _m_type, _s_type = mimetypes.guess_type(_path)[0].split("/")
                self.log("guessed mimetype for {}: {} / {}".format(_path, _m_type, _s_type))
                if _m_type == "text":
                    _attach = MIMEText(file(_path, "rb").read(), _s_type)
                elif _m_type == "image":
                    _attach = MIMEImage(file(_path, "rb").read(), _s_type)
                else:
                    _attach = MIMEBase(_m_type, _s_type)
                    _attach.set_payload(file(_path, "rb").read())
                    email.encoders.encode_base64(_attach)
                _email.attach(_attach)
            else:
                self.log("attachment {} not found".format(add_file), logging_tools.LOG_LEVEL_ERROR)
        _map_list = [("multipart/alternative", "multipart/mixed"), ]
        for _src, _dst in _map_list:
            if _email.get_content_type().lower() == _src:
                self.log("rewriting content_type from {} to {}".format(_src, _dst))
                _email.set_type(_dst)
        # _email.add_header("X-INIT-FOOTER-ADDED", "yes")
        self.log_mail("after", _email)
        self.dst_mail = _email.as_string()
        self.log("dst mail has {}".format(logging_tools.get_size_str(len(self.dst_mail))))

    def send_mail(self):
        _sm_args = [SENDMAIL_BIN] + self.args[1:]
        self.log("calling sendmail with '{}'".format(" ".join(_sm_args)))
        sm_proc = subprocess.Popen(_sm_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _stdout, _stderr = sm_proc.communicate(input=self.dst_mail)
        self._result = sm_proc.wait()
        self.log("sendmail process ended with {}".format(self._result))
        self.log("stdout / stderr : '{}' / '{}'".format(_stdout, _stderr))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self._log_template.log(log_level, what)

    def close(self):
        self._log_template.close()


def main():
    my_disc = disclaimer_handler()
    my_disc.recv_mail()
    try:
        my_disc.process()
    except:
        my_disc.log("error processing: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
    my_disc.send_mail()
    my_disc.close()
    return my_disc._result

if __name__ == "__main__":
    sys.exit(main())

