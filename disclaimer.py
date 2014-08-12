#!/usr/bin/python-init -Otu

import sys
import logging_tools
import process_tools
import subprocess
import os
import email
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
        self.log("email structure {}".format(prefix))
        self.log("is_multipart: {}".format("yes" if _mail.is_multipart() else "no"))
        _dict = {}
        self._parse_mail(_dict, _mail)
    def _parse_mail(self, _dict, _mail):
        _type = _mail.get_content_type()
        print _mail, _type
        for _i, _part in enumerate(_mail.walk()):
            if _part.get_main_type() == "multipart":
                continue
            self.log("part {:<3d} has content_type {} (len {:d})".format(_i, _part.get_content_type(), len(_part)))
            #self.log(str(_part))
    def process(self):
        _email = email.message_from_string(
            self.src_mail,
            email.mime.multipart.MIMEMultipart,
        )
        _from = email.utils.parseaddr(_email["From"])
        self.log("from is '{}' / '{}'".format(_from[0], _from[1]))
        # fixme
        #_to = _email.get_all("To", [])
        self.log("to is '{}'".format(_email["To"]))
        self.log_mail("before", _email)
        if not _email.is_multipart():
            _payload = _email.get_payload()
            
            #_sub_mail = email.message_from_string()
            #print "pl", _sub_mail.get_payload(), _sub_mail.is_multipart()
            self.log("*** {}".format(_email.get_payload()))
            self.log("{}".format(type(_email.get_payload())))
            _text = MIMEText(_email.get_payload())
            #print _text, type(_text)
            _email.set_payload([_text])
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
    my_disc.process()
    my_disc.send_mail()
    my_disc.close()
    return my_disc._result

if __name__ == "__main__":
    sys.exit(main())

