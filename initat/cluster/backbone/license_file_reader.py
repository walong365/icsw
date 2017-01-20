# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" license file reader """

import base64
import datetime
import glob
import os

import dateutil.parser
from lxml import etree

from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.license import LicenseState, LIC_FILE_RELAX_NG_DEFINITION, \
    ICSW_XML_NS_MAP, LICENSE_USAGE_GRACE_PERIOD
from initat.constants import CLUSTER_DIR
from initat.tools import process_tools, server_command, logging_tools

CERT_DIR = os.path.join(CLUSTER_DIR, "share/cert")


class LicenseFileReader(object):

    class InvalidLicenseFile(RuntimeError):
        def __init__(self, msg=None):
            super(LicenseFileReader.InvalidLicenseFile, self).__init__(
                msg if msg is not None else "Invalid license file format"
            )

    def __init__(self, file_content, file_name=None, license=None, cluster_id=None, current_fingerprint=None, log_com=None):
        from initat.cluster.backbone.models import device_variable

        self.__log_com = log_com
        self.file_name = file_name
        # contains the license-file tag, i.e. information relevant for program without signature
        self.content_xml = self._read_and_parse(file_content, license)
        if cluster_id is None:
            self.cluster_id = device_variable.objects.get_cluster_id()
        else:
            self.cluster_id = cluster_id
        self.current_fp = current_fingerprint
        self._check_fingerprint()
        self._check_eggs()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[LFR] {}".format(what), log_level)
        else:
            print("[LFR][{}] {}".format(logging_tools.get_log_level_str(log_level), what))

    @property
    def current_fingerprint(self):
        if not self.current_fp:
            from initat.tools import hfp_tools
            self.current_fp = hfp_tools.get_server_fp(serialize=True)
        return self.current_fp

    def _check_eggs(self):
        gp_q = "//icsw:package-list/icsw:package/icsw:cluster-id[@id='{}']/icsw:package-parameter".format(
            self.cluster_id,
        )
        _g_paras = self.content_xml.xpath(gp_q, namespaces=ICSW_XML_NS_MAP)

    def _check_fingerprint(self):
        fp_q = "//icsw:package-list/icsw:package/icsw:cluster-id[@id='{}']/icsw:hardware-finger-print/text()".format(
            self.cluster_id,
        )
        fp_node = self.content_xml.xpath(fp_q, namespaces=ICSW_XML_NS_MAP)
        if len(fp_node):
            self.__fingerprint_valid = fp_node[0] == self.current_fingerprint
        else:
            self.__fingerprint_valid = True

    @property
    def fingerprint_ok(self):
        return self.__fingerprint_valid

    def _read_and_parse(self, file_content, license):
        # read content and parse some basic maps, raise an error if
        # - wrong format (decompression problem)
        # - XML not valid
        # - invalid signature
        try:
            signed_content_str = server_command.decompress(file_content)
        except:
            self.log(
                "Error reading uploaded license file: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            raise LicenseFileReader.InvalidLicenseFile()

        signed_content_xml = etree.fromstring(signed_content_str)

        # noinspection PyUnresolvedReferences
        ng = etree.RelaxNG(LIC_FILE_RELAX_NG_DEFINITION)
        if not ng.validate(signed_content_xml):
            raise LicenseFileReader.InvalidLicenseFile("Invalid license file structure")

        content_xml = signed_content_xml.find('icsw:license-file', ICSW_XML_NS_MAP)
        signature_xml = signed_content_xml.find('icsw:signature', ICSW_XML_NS_MAP)

        signature_ok = self.verify_signature(content_xml, signature_xml, license)

        if not signature_ok:
            raise LicenseFileReader.InvalidLicenseFile("Invalid signature")

        # notes about the XML:
        # - one or more packages
        # - packages may have the same UUID
        # - only the packags with the highest date (when having the same UUID) is valid
        # print(etree.tostring(content_xml))
        # print(ICSW_XML_NS_MAP)
        # print(content_xml.xpath(".//icsw:package-name/text()", namespaces=ICSW_XML_NS_MAP))
        # print(content_xml.xpath(".//icsw:package-uuid/text()", namespaces=ICSW_XML_NS_MAP))

        # create mapping values

        # uuid -> struct
        package_uuid_map = {}
        customer_xml = content_xml.find("icsw:customer", namespaces=ICSW_XML_NS_MAP)

        for pack_xml in content_xml.xpath("//icsw:package-list/icsw:package", namespaces=ICSW_XML_NS_MAP):
            _uuid = pack_xml.findtext("icsw:package-meta/icsw:package-uuid", namespaces=ICSW_XML_NS_MAP)
            _version = int(
                pack_xml.findtext(
                    "icsw:package-meta/icsw:package-version",
                    namespaces=ICSW_XML_NS_MAP,
                )
            )
            _date = dateutil.parser.parse(
                pack_xml.findtext(
                    "icsw:package-meta/icsw:package-date",
                    namespaces=ICSW_XML_NS_MAP,
                )
            )
            if _uuid in package_uuid_map:
                # print(new_version, map_version, map_date, new_date)
                if _version > package_uuid_map[_uuid]["version"]:
                    _replace = True
                elif _version == package_uuid_map[_uuid]["version"] and _date > package_uuid_map[_uuid]["date"]:
                    _replace = True
                else:
                    _replace = False
                if _replace:
                    package_uuid_map[_uuid]["xml"] = pack_xml
                    package_uuid_map[_uuid]["version"] = _version
                    package_uuid_map[_uuid]["date"] = _date
            else:
                package_uuid_map[_uuid] = {
                    "pack_xml": pack_xml,
                    "version": _version,
                    "date": _date,
                    "idx": license.idx,
                    "customer_xml": customer_xml,
                    "reader": self,
                }
        # build hashes
        for _uuid, _struct in package_uuid_map.items():
            # compare hash
            _struct["hash"] = (_struct["version"], _struct["date"], _struct["idx"])
        self.package_uuid_map = package_uuid_map
        return content_xml

    @staticmethod
    def get_pure_data(lic_content):
        def _clean(_xml):
            for _sig in _xml.xpath(".//icsw:signature|.//icsw:license-file-meta/icsw:creation-datetime", namespaces=ICSW_XML_NS_MAP):
                _sig.text = ""
        _lic_xml = etree.fromstring(server_command.decompress(lic_content))
        _clean(_lic_xml)
        _lic_stream = server_command.compress(etree.tostring(_lic_xml))
        return _lic_stream

    @staticmethod
    def _get_state_from_license_xml(lic_xml):
        """
        only check if the license is valid by examining the given timeframe, do not check fingerprint violations
        """
        parse_date = lambda date_str: datetime.date(*(int(i) for i in date_str.split("-")))

        valid_from = parse_date(lic_xml.find("icsw:valid-from", ICSW_XML_NS_MAP).text)
        valid_to = parse_date(lic_xml.find("icsw:valid-to", ICSW_XML_NS_MAP).text)
        valid_to_plus_grace = valid_to + LICENSE_USAGE_GRACE_PERIOD
        today = datetime.date.today()

        # semantics: valid_from is from 00:00:00 of that day, valid to is till 23:59:59 of that day

        # return LicenseState.fp_mismatch
        if today < valid_from:
            return LicenseState.valid_in_future
        elif today > valid_to_plus_grace:
            return LicenseState.expired
        elif today > valid_to:
            return LicenseState.grace
        else:
            return LicenseState.valid

    def get_referenced_cluster_ids(self):
        q = "//icsw:package-list/icsw:package/icsw:cluster-id"
        return set(elem.get('id') for elem in self.content_xml.xpath(q, namespaces=ICSW_XML_NS_MAP))

    def has_license(self, license):
        # check if the license is present in this readers
        q = "//icsw:package-list/icsw:package/icsw:cluster-id[@id='{}']/icsw:license[icsw:id/text()='{}']".format(
            self.cluster_id,
            license.name,
        )
        return True if len(self.content_xml.xpath(q, namespaces=ICSW_XML_NS_MAP)) else False

    def get_license_state(self, license, parameters=None):
        """
        Returns a LicenseState for the local cluster_id and the given license combination
        for the current point in time, or LicenseState.none if no license exists.

        NOTE: Does not consider license violations. This is handled by the db (i.e. License).

        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: quantity} of required parameters
        """
        if not self.fingerprint_ok:
            return LicenseState.fp_mismatch
        # check parameters via xpath
        license_parameter_check = ["icsw:id/text()='{}'".format(license.name)]
        if parameters is not None:
            for lic_param_type, value in parameters.items():
                license_parameter_check.append(
                    "icsw:parameters/icsw:parameter[@id='{}']/text() >= {}".format(
                        lic_param_type.name,
                        value,
                    )
                )

        q = "//icsw:package-list/icsw:package/icsw:cluster-id[@id='{}']/icsw:license[{}]".format(
            self.cluster_id,
            " and ".join(license_parameter_check),
        )

        state = LicenseState.none
        for lic_xml in self.content_xml.xpath(q, namespaces=ICSW_XML_NS_MAP):
            # these licenses match id and parameter, check if they are also valid right now

            s = self._get_state_from_license_xml(lic_xml)
            if s > state:
                state = s

        return state

    def get_valid_licenses(self):
        """
        Returns licenses which are currently valid as license id string list. Does not consider license violations!
        """
        ret = []
        for lic_id in set(
            lic_xml.find(
                "icsw:id",
                namespaces=ICSW_XML_NS_MAP
            ).text for lic_xml in self.content_xml.xpath(
                "//icsw:license",
                namespaces=ICSW_XML_NS_MAP
            ) if self._get_state_from_license_xml(lic_xml).is_valid()
        ):
            try:
                ret.append(LicenseEnum[lic_id])
            except KeyError:
                self.log(
                    "Invalid license in LicensFiles: {}".format(lic_id),
                    logging_tools.LOG_LEVEL_ERROR
                )
        return ret

    def get_valid_parameters(self):
        """
        :return:
         Returns all package-parameters (==ova) which are currently
         valid as list (num, from_date, to_date)
        """
        ret = []
        for para_xml in [
            _el_xml for _el_xml in self.content_xml.xpath(
                "//icsw:package-parameter",
                namespaces=ICSW_XML_NS_MAP
            ) if self._get_state_from_license_xml(_el_xml).is_valid()
        ]:
            if para_xml is not None:
                # print("*", etree.tostring(para_xml))
                _from = datetime.datetime.strptime(
                    para_xml.findtext(".//icsw:valid-from", namespaces=ICSW_XML_NS_MAP),
                    "%Y-%m-%d"
                )
                _to = datetime.datetime.strptime(
                    para_xml.findtext(".//icsw:valid-to", namespaces=ICSW_XML_NS_MAP),
                    "%Y-%m-%d"
                )
                ret.append(
                    (
                        int(
                            para_xml.findtext(".//icsw:value", namespaces=ICSW_XML_NS_MAP)
                        ),
                        _from,
                        _to,
                    )
                )
        return ret

    @classmethod
    def merge_license_maps(cls, license_readers):
        # merge all maps for the given license readers
        _res_map = {}
        for _reader in license_readers:
            for _uuid, _struct in _reader.package_uuid_map.items():
                if _uuid not in _res_map:
                    _add = True
                elif _struct["hash"] > _res_map[_uuid]["hash"]:
                    _add = True
                else:
                    _add = False
                if _add:
                    _res_map[_uuid] = _struct
        return _res_map

    @classmethod
    def get_license_packages(cls, license_readers):
        from initat.tools import hfp_tools
        # this has to be called on all license readers to work out (packages can be contained in multiple files and some
        # might contain deprecated versions)
        # map with only the latest valid readers
        package_uuid_map = cls.merge_license_maps(license_readers)
        # print("*", package_uuid_map)

        def extract_parameter_data(cluster_xml):
            # print etree.tostring(cluster_xml)
            _r_list = []
            for lic_xml in cluster_xml.xpath("icsw:package-parameter", namespaces=ICSW_XML_NS_MAP):
                try:
                    _add_dict = {
                        'id': lic_xml.findtext("icsw:id", namespaces=ICSW_XML_NS_MAP),
                        'valid_from': dateutil.parser.parse(lic_xml.findtext("icsw:valid-from", namespaces=ICSW_XML_NS_MAP)),
                        'valid_to': dateutil.parser.parse(lic_xml.findtext("icsw:valid-to", namespaces=ICSW_XML_NS_MAP)),
                        "value": int(lic_xml.findtext("icsw:value", namespaces=ICSW_XML_NS_MAP)),
                        # cannot serialize enum so the following line is commented out
                        # "parameter": getattr(LicenseParameterTypeEnum, lic_xml.findtext("icsw:id", namespaces=ICSW_XML_NS_MAP)),
                    }
                except:
                    pass
                else:
                    _r_list.append(_add_dict)
            return _r_list

        def extract_package_data(pack_xml, customer_xml):
            return {
                'name': pack_xml.findtext("icsw:package-meta/icsw:package-name", namespaces=ICSW_XML_NS_MAP),
                'date': pack_xml.findtext("icsw:package-meta/icsw:package-date", namespaces=ICSW_XML_NS_MAP),
                "version": pack_xml.findtext("icsw:package-meta/icsw:package-version", namespaces=ICSW_XML_NS_MAP),
                "uuid": pack_xml.findtext("icsw:package-meta/icsw:package-uuid", namespaces=ICSW_XML_NS_MAP),
                'customer': customer_xml.findtext("icsw:name", namespaces=ICSW_XML_NS_MAP),
                'type_name': pack_xml.findtext("icsw:package-meta/icsw:package-type-name", namespaces=ICSW_XML_NS_MAP),
                # attention: the following structure is also used in webfrontend / license.coffee:67ff
                "lic_info": {
                    cluster_xml.get("id"): {
                        "licenses": extract_cluster_data(
                            cluster_xml
                        ),
                        "fp_info": extract_fp_data(
                            cluster_xml
                        ),
                        "parameters": extract_parameter_data(
                            cluster_xml
                        )
                    } for cluster_xml in pack_xml.xpath(
                        "icsw:cluster-id",
                        namespaces=ICSW_XML_NS_MAP
                    )
                }
            }

        def extract_fp_data(cluster_xml):
            def get_cluster_id(_xml):
                return _xml.findtext("icsw:id", namespaces=ICSW_XML_NS_MAP)

            fp_q = ".//icsw:hardware-finger-print/text()"

            fp_node = cluster_xml.xpath(fp_q, namespaces=ICSW_XML_NS_MAP)

            if len(fp_node):
                return {
                    "info": "present",
                    "valid": fp_node[0] == hfp_tools.get_server_fp(serialize=True)
                }
            else:
                return {
                    "info": "not present",
                    "valid": False
                }

        def extract_cluster_data(cluster_xml):
            def int_or_none(x):
                try:
                    return int(x)
                except ValueError:
                    return None

            def parse_parameters(parameters_xml):
                return {
                    LicenseParameterTypeEnum.id_string_to_user_name(
                        param_xml.get('id')
                    ): int_or_none(param_xml.text) for param_xml in parameters_xml.xpath("icsw:parameter", namespaces=ICSW_XML_NS_MAP)
                }

            def get_cluster_id(_xml):
                return _xml.findtext("icsw:id", namespaces=ICSW_XML_NS_MAP)

            # for lic_xml in cluster_xml.xpath("icsw:license", namespaces=ICSW_XML_NS_MAP):
            #     print cls._get_state_from_license_xml(lic_xml)
            _r_list = [
                {
                    'id': get_cluster_id(lic_xml),
                    'valid_from': dateutil.parser.parse(lic_xml.findtext("icsw:valid-from", namespaces=ICSW_XML_NS_MAP)),
                    'valid_to': dateutil.parser.parse(lic_xml.findtext("icsw:valid-to", namespaces=ICSW_XML_NS_MAP)),
                    'parameters': parse_parameters(lic_xml.find("icsw:parameters", namespaces=ICSW_XML_NS_MAP)),
                    # "state": cls._get_state_from_license_xml(lic_xml).name
                } for lic_xml in cluster_xml.xpath("icsw:license", namespaces=ICSW_XML_NS_MAP)
            ]
            return _r_list
        return [extract_package_data(_struct["pack_xml"], _struct["customer_xml"]) for _struct in package_uuid_map.values()]

    def verify_signature(self, lic_file_xml, signature_xml, license):
        # import pem
        from cryptography import x509
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        """
        :return: True if signature is fine
        :rtype : bool
        """
        backend = default_backend()
        signed_string = LicenseFileReader._extract_string_for_signature(lic_file_xml)
        # print(len(signed_string))
        signature = base64.b64decode(signature_xml.text.encode("ascii"))
        # print("V" * 50)
        # print("*", signature_xml.text)
        # print(".", signature)

        cert_files = glob.glob("{}/*.pem".format(CERT_DIR))
        # print(cert_files)

        result = -1

        if not cert_files:
            # raise Exception("No certificate files in certificate dir {}.".format(CERT_DIR))
            # currently it's not clear whether this is only bad or actually critical
            self.log(
                "No certificate files in certificate dir {}.".format(CERT_DIR),
                logging_tools.LOG_LEVEL_ERROR
            )

        for cert_file in cert_files:
            short_cert_file = os.path.basename(cert_file)
            try:
                # print("*" * 20)
                cert = x509.load_pem_x509_certificate(
                    open(cert_file, "rb").read(),
                    backend,
                )
            except:
                # print(process_tools.get_except_info())
                self.log(
                    "Failed to read certificate file {}: {}".format(
                        cert_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
            else:
                # print(cert)
                # only use certs which are currently valid
                now = datetime.datetime.now()  # tz=pytz.timezone(TIME_ZONE))
                # print("*", str(cert.get_not_before())
                if cert.not_valid_before <= now <= cert.not_valid_after:
                    # print("ok")
                    verifier = cert.public_key().verifier(
                        signature,
                        padding.PSS(
                            mgf=padding.MGF1(hashes.SHA512()),
                            salt_length=padding.PSS.MAX_LENGTH,
                        ),
                        hashes.SHA512(),
                    )
                    verifier.update(signed_string.encode("utf-8"))
                    try:
                        verifier.verify()
                    except InvalidSignature:
                        result = 0
                    else:
                        result = 1
                    # Result of verification: 1 for success, 0 for failure, -1 on other error.

                    if result != 1:
                        self.log(
                            "Cert file {} verification result for '{}': {}".format(
                                short_cert_file,
                                str(license) if license else "N/A",
                                result,
                            ),
                            logging_tools.LOG_LEVEL_WARN,
                        )

                else:
                    self.log(
                        "Cert file {} is not valid at this point in time".format(short_cert_file),
                        logging_tools.LOG_LEVEL_ERROR
                    )

        return result == 1

    @staticmethod
    def _extract_string_for_signature(content):
        def dict_to_str(d):
            return ";".join(
                "{}:{}".format(k, v) for k, v in d.items()
            )
        return "_".join(
            (
                "{}/{}/{}".format(
                    el.tag,
                    dict_to_str(el.attrib),
                    el.text.strip() if el.text is not None else ""
                ) for el in content.iter()
            )
        )

    def __repr__(self):
        return "LicenseFileReader(file_name={})".format(self.file_name)

    @property
    def raw_license_info(self):
        return LicenseFileReader.get_license_packages([self])

    @property
    def license_info(self):
        _lic_info = self.raw_license_info
        _num_packs = len(_lic_info)
        _cluster_ids = set()
        # not unique
        _num = {"lics": 0, "paras": 0}
        for _list in [_lic_info]:
            for _lic_entry in _list:
                _cl_info = list(_lic_entry["lic_info"].keys())
                for _cl_name in _cl_info:
                    _cluster_ids.add(_cl_name)
                    _cl_struct = _lic_entry["lic_info"][_cl_name]
                    for _skey, _dkey in [("licenses", "lics"), ("parameters", "paras")]:
                        for _entry in _cl_struct.get(_skey, []):
                            # print _entry
                            _num[_dkey] += 1
        return "{} and {} in {} for {}".format(
            logging_tools.get_plural("license", _num["lics"]),
            logging_tools.get_plural("global parameter", _num["paras"]),
            logging_tools.get_plural("package", _num_packs),
            logging_tools.get_plural("Cluster", len(_cluster_ids)),
        )
