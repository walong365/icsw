#!/usr/bin/python-init
# -*- coding: utf-8 -*-

import argparse
import base64

from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
from M2Crypto import EVP

PRIVATE_KEY = \
"""
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA4p6JXKFMDbUpe45HhGZs/fBsQQki80YqQzgeRB42f0waKKqT
oia929RcMil1g4JRmpOu6IAWaKTthuueIKjeB1bnXYZhHKwod4Bmp6cooU3A1i+6
2F6AHqLJQvmaxK6UPMWyAvX6BPqJKdRcyH+XtFXGXEDnokfxzI1Cxgm1hYtpRwvh
inERFOl1BVNgKRJD3QoYcztHDpRf58eO7i/Eglk1qrAYb+COX14ighkhQrUZ8Q3W
cOMuUvEjupUCOiBTVIU5XTMnaggmdBZETg7q2V6hjXVdEVg7PBYpwcGFS2TQY8g8
2Di6nERR4LNEAsvUX/8tRzNokOBsjSfcSWShGwIDAQABAoIBAFB1QQemLL5hJ406
gqG7S88M4SJmAAanTrH25qgAohCoEFGH3kqfvqCh0OnuVk6OojJjZKIfd9VHWR2h
4c5upgWtEQ/fefMYHHXxHIFBk+dRF7nz0D6prosx+IrS2+Qgp3i8J+ttMYs6+B/l
ydtVkaLxIS/3y0WOjYa2UJLHN69lmLnANGKv6emUmrCiSGS2kAJJKFwnjvw3tej0
K+nuAd2SrUIi0LM5hVfUlxzBavqRUYk5Isl2JEvl/E+z0isammtCw6DIpRSA1DAL
o76M3qqCX2rf0mmYNV0sUzdo9K8S1KSxf0E7PRZYMh2YTzQtDjN6rK316Rb1idYv
GMaWPKECgYEA9Jjrzu2cJi0086ytzMVCZ5WleIOcRLqPEpApLiJZ1aDvUYW+rFIF
X5iIFC8r5k53WxjLPJrTGm2TCndqN+e+X0LvlIGmvLHVUnLJpiJfBNP5mNPOTlk8
LaxJW0BpiU7kBJP+/7D3z3np9MKBBmYIyVgOyFB5So+EQIteWhbEepcCgYEA7S8P
rYlJ176pPGom0ZXn1l9SMyztLa3yALcjoKyRdRzGlj1SvSidKvohGlLVNE8Shw62
vYr5LHl5/3+iTErCtlj/f2k11K4wAQQ/8hJUyWDKMH7dcDo3Ff8JOgWh9lpV4/pR
tg9UTQliw67e94t2qVNF0GHyxGS/ULanUzjA8h0CgYBN/t1i1L3wJoY2FaAuJdCw
+zUSotUXzW2F+9ZF0cpXpsPpeP5+MIFqJFdwKEKVY/wHXnagUrZyPPKgacfDH/DC
q7N95YHntcVSTywh/9/QyE9U/mVQ8n+QCNozcOy2TiPDmfW8TxAWZsfFtqgyBCNV
IPFFyvOCZRVFB6wEijII7QKBgQCsSGbm8rZElCVx0Nlpm63PNWYL7jJJ3/PNOToT
18XAf6pwLxMOe5XOReoNqOVdHaKjn7h1baEZARPw1tEZAaT1tye/cLi9R9luo5uf
Rll3/WpgV4aZom+o9pvJHZZLz8pb0tPPnsrpOkwXP8qNnSwQSoCHoN4qcdPV2Rcp
iCv+sQKBgQCJ7LH2+xkfSRGDhyByMci1SNFLebDe64nEDIW2YPcnK8qRNGCXDsaP
qqKkd4Z694W+GSryGBf+tUo/mtgoSX8lYRfWTvPEyPiq1aEQveX27G6J/me6OCK5
RJFfUw9Ll0BI4y0xE+RV9MLkyVKbvn4KdeflTrU0b71GnF2DVji9GQ==
-----END RSA PRIVATE KEY-----
"""

class Signature(object):
    def __init__(self, private_key=PRIVATE_KEY):
        self.key = EVP.load_key_string(private_key)

    def _sign(self, data):
        """ Create the signature """
        self.key.sign_init()
        self.key.sign_update(data)
        return self.key.sign_final()

    def sign(self, data, no_xml=False, no_base64=False):
        signature = self._sign(data)

        if not no_xml:
            signature = base64.encodestring(signature)
            res = E.result(E.data(data), E.signature("\n" + signature))
        else:
            if no_base64 is False:
                signature = base64.encodestring(signature)
            res = signature
        return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sign data with the private "
                                     "key for monit license data")
    parser.add_argument("data", type=str, help="The data you want signed!")
    parser.add_argument("--no-xml", action="store_true", help="Don't output "
                        "the XML structure, just output the signature")
    parser.add_argument("--no-base64", action="store_true", help="Don't "
                        "base64 encode the signature")
    args = parser.parse_args()
    result = Signature().sign(args.data, no_xml=args.no_xml,
                              no_base64=args.no_base64)

    if isinstance(result, etree._Element):
        print etree.tostring(result, pretty_print=True)
    else:
        print result
