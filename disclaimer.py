#!/usr/bin/python-init -Otu

from email.parser import FeedParser
from lxml import etree  # @UnresolvedImport
import email
import logging_tools
import os
import process_tools
import subprocess
import codecs
import sys
import tempfile
import re
from StringIO import StringIO

SENDMAIL_BIN = process_tools.find_file("sendmail")
SPAMC_BIN = process_tools.find_file("spamc")


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
        self._read_user_info()

    def _read_user_info(self):
        # has to be UTF-8 encoded
        _ui_name = "/etc/postfix/user_info.xml"
        try:
            _parser = etree.XMLParser(recover=False, encoding="utf-8")  # @UndefinedVariable
            self.ui_tree = etree.parse(StringIO(codecs.open(_ui_name, "r", "utf-8").read()), _parser)  # @UndefinedVariable
        except:
            self.log(
                "error reading ui_tree {}: {}".format(
                    _ui_name,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            self.ui_tree = None
        else:
            self.log("read user_info from {} ({})".format(
                _ui_name,
                logging_tools.get_plural("entry", len(self.ui_tree.findall(".//user"))),
            ))

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

    def _parse_from_to(self, _email):
        _rewrite, _from_address = (False, "")
        try:
            _from_list = [email.utils.parseaddr(_email["From"])]  # @UndefinedVariable
            _to_list = [email.utils.parseaddr(_value) for _value in _email["To"].split(",")]  # @UndefinedVariable
            if _email["Cc"]:
                _cc_list = [email.utils.parseaddr(_value) for _value in _email["Cc"].split(",")]  # @UndefinedVariable
                self.log("cc list: {}".format(_cc_list))
            else:
                _cc_list = []
        except:
            self.log("cannot parse from and / or to field: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            if len(_from_list) and len(_to_list):
                self.log("to ({:d}) is {}".format(len(_to_list), ", ".join(["'{}' / '{}'".format(_val[0], _val[1]) for _val in _to_list])))
                _from = _from_list[0]
                self.log("from is '{}' / '{}'".format(_from[0], _from[1]))
                _from_domains = set([_from[1].split("@")[1] for _from in _from_list])
                _to_domains = set([_to[1].split("@")[1] for _to in _to_list])
                _cc_domains = set([_cc[1].split("@")[1] for _cc in _cc_list])
                self.log("domain list of cc: {}".format(_cc_domains))
                self.log("from / to domains: {}, {}".format(", ".join(_from_domains), ", ".join(_to_domains)))
                if _from_domains == _to_domains:
                    self.log("same domains, no rewrite")
                    if _cc_domains and _from_domains != _cc_domains:
                        _rewrite = True
                        _from_address = _from[1]
                        self.log("enable rewriting with from address '{}'".format(_from_address))
                    else:
                        self.log("same domains in cc, no rewrite")
                else:
                    _rewrite = True
                    _from_address = _from[1]
                    self.log("enable rewriting with from address '{}'".format(_from_address))
            else:
                self.log("from and / or to fields are empty", logging_tools.LOG_LEVEL_WARN)
            self.log("rewrite variable is {}".format(_rewrite))
        return _rewrite, _from_address

    def _find_user(self, _from_address):
        _found = None
        for _user in self.ui_tree.findall(".//user[@match]"):
            _re_m = re.compile(_user.attrib["match"])
            if _re_m.match(_from_address):
                _found = _user
                break
        return _found

    def process(self):
        my_parser = FeedParser()
        my_parser.feed(self.src_mail)
        self.dst_mail = self.src_mail
        _email = my_parser.close()
        _do_rewrite, _from_address = self._parse_from_to(_email)
        if _do_rewrite:
            user_xml = self._find_user(_from_address)
            if user_xml is None:
                self.log("no matching user found, no rewrite", logging_tools.LOG_LEVEL_WARN)
            else:
                self.do_rewrite(_email, user_xml)
        return

    def disclaimer_html(self, user_xml):
        src_html = codecs.open("/etc/postfix/default.html", "rb", "utf-8").read()
        return self.disclaimer_rewrite(src_html, user_xml)

    def disclaimer_text(self, user_xml):
        src_text = codecs.open("/etc/postfix/default.txt", "rb", "utf-8").read()
        return self.disclaimer_rewrite(src_text, user_xml)

    def disclaimer_rewrite(self, in_text, user_xml):
        match_re = re.compile("^(?P<pre_text>.*?)({(?P<code>.*)\})(?P<post_text>.*)")
        out_lines = []
        for _line in in_text.split("\n"):
            _cur_m = match_re.match(_line)
            if _cur_m is None:
                out_lines.append(_line)
            else:
                _code = _cur_m.group("code")
                _ccc = _code.count(":::")
                _add_dict = {
                    "pre": "",
                    "post": "",
                    "notfound": "",
                }
                if _ccc:
                    _parts = _code.split(":::")
                    _code = _parts.pop(0)
                    for _part in _parts:
                        if _part.count("="):
                            _key, _value = _part.split("=", 1)
                            _add_dict[_key] = _value
                self.log(
                    u"found code tag '{}' in line '{}' ({})".format(
                        _code,
                        _line,
                        ", ".join(["{}='{}'".format(_key, _value) for _key, _value in _add_dict.iteritems()])
                    )
                )
                s_str = "{}".format(
                    {
                        "mobile": "phone[@type='mobile']",
                        "tel": "phone[@type='office']",
                        "link": "link",
                        "name": "name",
                        "position": "department",
                        "mail":  "email",
                    }.get(_code, _code)
                )
                try:
                    _found_el = user_xml.find(s_str)
                except:
                    self.log("error in XML find ({}): {}".format(s_str, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    _found_el = None
                if _found_el is None:
                    rep_str = _add_dict["notfound"]
                    self.log(" ... not found, using '{}'".format(rep_str), logging_tools.LOG_LEVEL_ERROR)
                else:
                    raw_rep_str = _found_el.text
                    rep_str = u"{}{}{}".format(_add_dict["pre"], raw_rep_str, _add_dict["post"])
                    self.log(
                        u"found replacement for code {} ({}): '{}' ({})".format(
                            _code,
                            s_str,
                            rep_str,
                            raw_rep_str,
                        )
                    )
                out_lines.append(
                    u"{}{}{}".format(
                        _cur_m.group("pre_text"),
                        rep_str,
                        _cur_m.group("post_text")
                    )
                )
        return u"\n".join(out_lines)

    def do_rewrite(self, _email, user_xml):
        _tmpdir = tempfile.mkdtemp()
        self.log("tempdir is {}".format(_tmpdir))
        _src_mail = os.path.join(_tmpdir, "in")
        _dis_html = os.path.join(_tmpdir, "dis.html")
        _dis_text = os.path.join(_tmpdir, "dis.txt")
        open(_src_mail, "wb").write(self.src_mail)
        codecs.open(_dis_html, "wb", "utf-8").write(self.disclaimer_html(user_xml))
        codecs.open(_dis_text, "wb", "utf-8").write(self.disclaimer_text(user_xml))
        self.log("size of mail before processing is {}".format(logging_tools.get_size_str(len(self.src_mail))))
        _call_args = [
            "/usr/local/bin/altermime",
            "--input={}".format(_src_mail),
            "--disclaimer={}".format(_dis_text),
            "--disclaimer-html={}".format(_dis_html),
            # "--force-for-bad-html",
            # "--force-into-b64",
        ]
        self.log("call_args are {}".format(" ".join(_call_args)))
        _result = subprocess.call(
            _call_args
        )
        self.log("result is {:d}".format(_result))
        # rewind
        self.dst_mail = file(_src_mail, "r").read()
        self.log("size of mail after processing is {}".format(logging_tools.get_size_str(len(self.dst_mail))))
        # os.unlink(_tmpfile.name)

    def send_via_sendmail(self):
        _sm_args = [SENDMAIL_BIN] + self.args[1:]
        self.log("calling sendmail with '{}'".format(" ".join(_sm_args)))
        sm_proc = subprocess.Popen(_sm_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _stdout, _stderr = sm_proc.communicate(input=self.dst_mail)
        self._result = sm_proc.wait()
        self.log("sendmail process ended with {}".format(self._result))
        self.log("stdout / stderr : '{}' / '{}'".format(_stdout, _stderr))

    def send_via_spamc(self):
        _sm_args = [SPAMC_BIN] + self.args[1:]
        self.log("calling spamc with '{}'".format(" ".join(_sm_args)))
        sm_proc = subprocess.Popen(_sm_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _stdout, _stderr = sm_proc.communicate(input=self.dst_mail)
        self._result = sm_proc.wait()
        self.log("spamc process ended with {}".format(self._result))
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
        _exc_info = process_tools.exception_info()
        for _line in _exc_info.log_lines:
            my_disc.log("error processing: {}".format(_line), logging_tools.LOG_LEVEL_CRITICAL)
    my_disc.send_via_spamc()
    my_disc.close()
    return my_disc._result

if __name__ == "__main__":
    sys.exit(main())
