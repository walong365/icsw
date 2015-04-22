# -*- encoding: utf-8 -*-
#
# Copyright (C) 2001-2009,2013-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import email  # @UnusedImport
import email.mime  # @UnusedImport
from email.header import Header  # @UnusedImport
try:
    import email.MIMEMultipart
    import email.MIMEImage
    import email.MIMEText
    import email.MIMEMessage  # @UnusedImport
except ImportError:
    # not present for python3
    pass
import email.utils  # @UnusedImport
from initat.tools import logging_tools
import mimetypes
import os
from initat.tools import process_tools
import socket
try:
    import email.Encoders
except ImportError:
    # not present for python3
    pass
import smtplib
import sys

if sys.version_info[0] == 3:
    unicode = str  # @ReservedAssignment
    long = int  # @ReservedAssignment


class mail(object):
    def __init__(self, subject=None, from_addr=None, to_addr=None, txt=None, **args):
        self.set_server()
        self.set_subject(subject)
        self.set_from_addr(from_addr)
        self.to_addrs = []
        self.bcc_list = []
        self.add_to_address(to_addr)
        self.is_html_body = args.get("html_body", False)
        if txt:
            if isinstance(txt, basestring):
                self.text = [txt]
            else:
                self.text = txt
        else:
            self.text = []
        self.binary_objects = []

    def add_binary_object(self, what):
        self.binary_objects.append(what)

    def set_server(self, srv="localhost", srv_helo="localhost"):
        self.server, self.server_helo = (srv, srv_helo)

    def set_subject(self, sbj=None):
        self.subject = sbj or "not set"

    def set_from_addr(self, frm):
        self.from_addr = frm or "root"

    def add_to_address(self, trg):
        if isinstance(trg, basestring):
            self.to_addrs.append(trg)
        elif type(trg) == list:
            self.to_addrs.extend(trg)
        elif type(trg) == type(set()):
            for add_addr in trg:
                self.to_addrs.append(add_addr)
        else:
            print("unknown type for add_to_address: %s" % (str(type(trg))))

    def init_text(self):
        self.text = []

    def add_bcc_address(self, addr):
        self.bcc_list.append(addr)

    def append_text(self, what=None):
        if isinstance(what, basestring):
            self.text.append(what)
        elif type(what) == list:
            self.text.extend(what)
        elif what is None:
            self.text.append("root@localhost")

    def send_mail(self):
        stat, ret_f = (
            0,
            [
                "trying to send an email with %s to %s (%sfrom %s via %s)" % (
                    logging_tools.get_plural("line", len(self.text)),
                    ", ".join(self.to_addrs),
                    "bcc to %s, " % (", ".join(self.bcc_list)) if self.bcc_list else "",
                    self.from_addr,
                    self.server
                )
            ]
        )
        gen_msgs = self.generate_msg_string()
        ret_f.extend(gen_msgs)
        if gen_msgs:
            stat = 1
        else:
            ret_f.append("message has %d bytes after encoding" % (len(self.msg.as_string())))
        err_str = None
        try:
            server = smtplib.SMTP(self.server)
        except socket.gaierror:
            stat, err_str = (1, "cannot connect to SMTP-Server '%s': socket.gaierror (%s)" % (self.server, sys.exc_info()[0]))
        except socket.error:
            stat, err_str = (1, "cannot connect to SMTP-Server '%s': socket.error (%s)" % (self.server, sys.exc_info()[0]))
        except:
            stat, err_str = (1, "cannot connect to SMTP-Server '%s': connection refused (%s)" % (self.server, sys.exc_info()[0]))
        else:
            server.helo(self.server_helo)
            try:
                # print self.msg.as_string()
                server.sendmail(self.from_addr, self.to_addrs + self.bcc_list, self.msg.as_string())
            except smtplib.SMTPSenderRefused:
                stat, err_str = (1, "SMTPError: Sender '%s' refused (%s)" % (self.from_addr, sys.exc_info()[0]))
            except smtplib.SMTPRecipientsRefused:
                stat, err_str = (1, "SMTPError: Recipients '%s' refused (%s)" % (self.to_addrs, sys.exc_info()[0]))
            except:
                stat, err_str = (1, "SMTPError: Unknown error %s" % (sys.exc_info()[0]))
            else:
                err_str = "Sending mail successfull"
            server.quit()
        if isinstance(err_str, basestring):
            ret_f.append(err_str)
        elif type(err_str) == list:
            ret_f.extend(err_str)
        return stat, ret_f

    def generate_msg_string(self):
        msgs = []
        if self.is_html_body:
            # remove content-type lines
            new_text = []
            for body_str in self.text:
                lines = body_str.split("\n")
                while not lines[0]:
                    lines.pop(0)
                if lines[0].lower().startswith("content-type"):
                    lines.pop(0)
                    while not lines[0]:
                        lines.pop(0)
                new_text.append("\n".join(lines))
            if type(new_text[0]) != type(u""):
                new_text = [unicode(new_text[0], "utf-8")]
            self.msg = email.MIMEText.MIMEText(new_text[0].encode("utf-8"), "html", "utf-8")
            self.msg.set_charset("utf-8")
        else:
            self.msg = email.MIMEMultipart.MIMEMultipart("utf-8")
            self.msg.preamble = "This is a multi-part message in MIME-format."
            self.msg.attach(email.MIMEText.MIMEText("\n".join([line.encode("utf-8") for line in self.text] + [""]), "plain", "utf-8"))
        self.msg["Subject"] = self.subject
        self.msg["From"] = self.from_addr
        self.msg["To"] = ", ".join(self.to_addrs)
        if self.bcc_list:
            self.msg["Bcc"] = ", ".join(self.bcc_list)
        self.msg.preamble = ""
        self.msg.epilogue = ""
        for obj in self.binary_objects:
            if os.path.isfile(obj):
                ctype, encoding = mimetypes.guess_type(obj)
                if ctype is None or encoding is not None:
                    # No guess could be made, or the file is encoded (compressed), so
                    # use a generic bag-of-bits type.
                    ctype = "application/octet-stream"
                maintype, subtype = ctype.split("/", 1)
                if maintype == "image":
                    try:
                        self.msg.attach(email.MIMEImage.MIMEImage(file(obj, "rb").read()))
                    except:
                        msgs.append("error reading image file '%s' : %s" % (obj,
                                                                            process_tools.get_except_info()))
                else:
                    try:
                        new_msg = email.MIMEBase.MIMEBase(maintype, subtype)
                        new_msg.set_payload(file(obj, "rb").read())
                        email.Encoders.encode_base64(new_msg)
                        new_msg.add_header("Content-Disposition", "attachment", filename=os.path.basename(obj))
                        self.msg.attach(new_msg)
                    except:
                        msgs.append("error reading file '%s' : %s" % (obj,
                                                                      process_tools.get_except_info()))
            else:
                msgs.append("error file '%s' not found" % (obj))
        return msgs


def expand_html_body(body_str, **args):
    # remove content-type lines
    new_lines = []
    for line in body_str.split("\n"):
        if line.startswith("<link") and line.count("stylesheet"):
            hr_parts = [part for part in line.split() if part.startswith("href")]
            if hr_parts:
                rel_path = hr_parts[0].split('"')[1]
                if "media_root" in args and "media_path" in args:
                    abs_path = rel_path.replace(args["media_path"], args["media_root"])
                    if os.path.exists(abs_path):
                        new_lines.append("<style>")
                        new_lines.extend(file(abs_path, "r").read().split("\n"))
                        new_lines.append("</style>")
        else:
            new_lines.append(line)
    new_text = "\n".join(new_lines)
    return new_text


if __name__ == "__main__":
    print("Loadable module, exiting...")
    sys.exit(0)
