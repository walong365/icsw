#!/usr/bin/python3-init -Ot
#
# Copyright (C) 2001-2008,2012-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes

import datetime
import socket


def create_ca():
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )

    with open("cakey.pem", "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "AT"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Vienna"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "init.at"),
        x509.NameAttribute(NameOID.COMMON_NAME, "{}_ca".format(socket.getfqdn())),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
    ).add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).sign(key, hashes.SHA256(), default_backend())

    with open("cacert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def create_certificate():
    with open("cacert.pem", "rb") as f:
        cacert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with open("cakey.pem", "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )

    with open("certkey.pem", "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "AT"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Vienna"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "init.at"),
        x509.NameAttribute(NameOID.COMMON_NAME, "{}".format(socket.getfqdn())),
    ])


    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        cacert.subject
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(u"mysite.com"),
            x509.DNSName(u"www.mysite.com"),
            x509.DNSName(u"subdomain.mysite.com"),
        ]), critical=False
    ).sign(ca_key, hashes.SHA256(), default_backend())

    with open("certcert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))



if __name__ == "__main__":
    create_ca()
    create_certificate()
