# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel
#
# Send feedback to: <g.kaufmann@init.at>, <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" report views """

import base64
import json
import logging
import datetime
import tempfile
import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from threading import Thread
from PIL import Image as PILImage
from io import BytesIO

from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, Paragraph, Image
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.pagesizes import landscape, letter, A4, A3
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from PollyReports import Element, Rule, Band
from PollyReports import Image as PollyReportsImage
from PollyReports import Report as PollyReportsReport

from PyPDF2 import PdfFileWriter, PdfFileReader

from initat.cluster.backbone.models import device, device_variable, AssetType, PackageTypeEnum, RunStatus, RunResult
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.cluster.backbone.models.asset import ASSET_DATETIMEFORMAT
from initat.cluster.backbone.models.report import ReportHistory
from initat.cluster.backbone.models import user, group
from initat.cluster.backbone.models.user import AC_READONLY, AC_MODIFY, AC_CREATE, AC_FULL

from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

from django.utils import timezone

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from initat.cluster.settings import FILE_ROOT, REPORT_DATA_STORAGE_DIR

pdfmetrics.registerFont(TTFont('Open-Sans', os.path.join(FILE_ROOT, "frontend", "static", "fonts", "open-sans.regular.ttf")))
pdfmetrics.registerFont(TTFont('Open-Sans-Bold', os.path.join(FILE_ROOT, "frontend", "static", "fonts", "open-sans.bold.ttf")))

logger = logging.getLogger(__name__)


########################################################################################################################
# Report Generator Classes / Functions
########################################################################################################################

class RowCollector(object):
    def __init__(self):
        self.rows_dict = []
        self.row_info = []
        self.current_asset_type = None

    def reset(self):
        self.rows_dict = []
        self.row_info = []
        self.current_asset_type = None

    def collect(self, _row):
        self.row_info = _row[0:8]

        if self.current_asset_type == AssetType.UPDATE:
            update_name = str(_row[8])
            # update_version = str(_row[9])
            # update_release = str(_row[10])
            # update_kb_idx = str(_row[11])
            install_date = _row[12]
            # update_install_date = str(_row[12])
            update_status = str(_row[13])
            # update_installed = str(_row[15])


            if type(install_date) != str:
                install_date = install_date.strftime(ASSET_DATETIMEFORMAT)

            o = {
                'update_name': update_name,
                'install_date': install_date,
                'update_status': update_status,
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.LICENSE:
            license_name = str(_row[8])
            license_key = str(_row[9])

            o = {
                'license_name': license_name,
                'license_key': license_key
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.PENDING_UPDATE:
            update_name = str(_row[8])
            # update_version = str(_row[9])
            # update_release = str(_row[10])
            # update_kb_idx = str(_row[11])
            # update_install_date = str(_row[12])
            # update_status = str(_row[13])
            update_optional = str(_row[14])
            # update_installed = str(_row[15])
            update_new_version = str(_row[16])

            o = {
                'update_name': update_name,
                'update_version': update_new_version if update_new_version else "N/A",
                'update_optional': update_optional
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.PROCESS:
            process_name = str(_row[8])
            process_id = str(_row[9])

            o = {
                'process_name': process_name,
                'process_id': process_id
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.HARDWARE:
            hardware_node_type = str(_row[8])
            hardware_depth = str(_row[9])
            hardware_attributes = str(_row[10])

            o = {
                'hardware_node_type': hardware_node_type,
                'hardware_depth': hardware_depth,
                'hardware_attributes': hardware_attributes,
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.PACKAGE:
            package_name = _row[8]
            package_version = _row[9]
            package_release = _row[10]
            package_size = _row[11]
            package_install_date = _row[12]
            package_type = _row[13]

            if package_size and isinstance(package_size, int):
                if package_type == PackageTypeEnum.WINDOWS.name:
                    package_size_str = sizeof_fmt(package_size * 1024)
                else:
                    package_size_str = sizeof_fmt(package_size)

            else:
                package_size_str = "N/A"

            if type(package_install_date) != str:
                package_install_date = package_install_date.strftime(ASSET_DATETIMEFORMAT)

            o = {
                'package_name': package_name,
                'package_version': package_version if package_version else "N/A",
                'package_release': package_release if package_release else "N/A",
                'package_size': package_size_str,
                'package_install_date': str(package_install_date),
                'package_type': package_type
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.PRETTYWINHW:
            pass

        elif self.current_asset_type == AssetType.DMI:
            handle = str(_row[8])
            dmi_type = str(_row[9])
            header = str(_row[10])
            key = str(_row[11])
            value = str(_row[12])

            o = {
                'handle': handle,
                'dmi_type': dmi_type,
                'header': header,
                'key': key,
                'value': value
            }

            self.rows_dict.append(o)

        elif self.current_asset_type == AssetType.PCI:
            domain = _row[8]
            bus = _row[9]
            slot = _row[10]
            func = _row[11]
            position = _row[12]
            subclass = _row[13]
            vendor = _row[14]
            _device = _row[15]
            revision = _row[16]

            o = {
                'domain': domain,
                'bus': bus,
                'slot': slot,
                'func': func,
                'position': position,
                'subclass': subclass,
                'vendor': vendor,
                'device': _device,
                'revision': revision
            }

            self.rows_dict.append(o)


class GenericReport(object):
    def __init__(self):
        self.bookmarks = []
        self.number_of_pages = 0
        self.pdf_buffers = []

    def generate_bookmark(self, name):
        bookmark = PDFReportGenerator.Bookmark(name, self.number_of_pages)
        self.bookmarks.append(bookmark)
        return bookmark

    def add_to_report(self, _buffer):
        self.pdf_buffers.append(_buffer)

    def increase_page_count(self, canvas, doc):
        self.number_of_pages += 1

class DeviceReport(GenericReport):
    def __init__(self, _device, report_settings):
        super(DeviceReport, self).__init__()

        self.device = _device

        # default settings
        self.report_settings = {
            "packages_selected": True,
            "licenses_selected": True,
            "installed_updates_selected": True,
            "avail_updates_selected": True,
            "hardware_report_selected": True,
            "lstopo_report_selected": True,
            "process_report_selected": True,
            "dmi_report_selected": True,
            "pci_report_selected": True
        }

        # update default settings with new settings
        for setting in report_settings:
            self.report_settings[setting] = report_settings[setting]

    def module_selected(self, assetrun):
        if AssetType(assetrun.run_type) == AssetType.PACKAGE:
            return self.report_settings["packages_selected"]
        elif AssetType(assetrun.run_type) == AssetType.HARDWARE:
            return self.report_settings["lstopo_report_selected"]
        elif AssetType(assetrun.run_type) == AssetType.LICENSE:
            return self.report_settings["licenses_selected"]
        elif AssetType(assetrun.run_type) == AssetType.UPDATE:
            return self.report_settings["installed_updates_selected"]
        elif AssetType(assetrun.run_type) == AssetType.SOFTWARE_VERSION:
            return True
        elif AssetType(assetrun.run_type) == AssetType.PROCESS:
            return self.report_settings["process_report_selected"]
        elif AssetType(assetrun.run_type) == AssetType.PENDING_UPDATE:
            return self.report_settings["avail_updates_selected"]
        elif AssetType(assetrun.run_type) == AssetType.DMI:
            return self.report_settings["dmi_report_selected"]
        elif AssetType(assetrun.run_type) == AssetType.PCI:
            return self.report_settings["pci_report_selected"]
        elif AssetType(assetrun.run_type) == AssetType.PRETTYWINHW:
            return self.report_settings["hardware_report_selected"]


class ReportGenerator(object):
    def __init__(self, settings, _devices):
        self.data = ""

        # general settings stored under special key -1
        self.general_settings = settings[-1]
        self.device_settings = settings

        self.devices = _devices
        self.progress = 0
        self.last_poll_time = None

        self.report_history = ReportHistory()
        self.report_history.save()
        self.report_id = self.report_history.idx

        self.creation_date = datetime.datetime.now()

    def get_progress(self):
        return self.progress

    def get_report_data(self):
        return self.data

    def get_report_type(self):
        pass

    def _get_data_for_user_group_overview(self):
        users = user.objects.all()
        data = []

        ac_to_str_dict = {
            AC_READONLY: "Read-only",
            AC_MODIFY: "Modify",
            AC_CREATE: "Modify, Create",
            AC_FULL: "Modify, Create, Delete"
        }

        for _user in users:
            o = {
                'login': _user.login,
                'uid': _user.uid,
                'firstname': _user.first_name,
                'lastname': _user.last_name,
                'email': _user.email,
                'group': _user.group.groupname
            }

            secondary_groups_str = _user.group.groupname

            for _group in _user.secondary_groups.all():
                secondary_groups_str += ", {}".format(_group.groupname)

            permission_str = "N/A"

            index = 1
            for user_permission in _user.user_permission_set.all():
                permission_name = user_permission.csw_permission.name

                new_permission_str = "{}. {}: {}".format(index, permission_name, ac_to_str_dict[user_permission.level])

                if permission_str == "N/A":
                    permission_str = new_permission_str
                else:
                    permission_str += "\n{}".format(new_permission_str)

                index += 1

            for user_object_permission in _user.user_object_permission_set.all():
                permission_name = user_object_permission.csw_object_permission.csw_permission.name
                object_pk = user_object_permission.csw_object_permission.object_pk

                content_type = user_object_permission.csw_object_permission.csw_permission.content_type
                object = content_type.get_object_for_this_type(pk=object_pk)


                new_permission_str = "{}: {} for {}".format(index, permission_name,
                                                            ac_to_str_dict[user_permission.level],
                                                            str(object))

                if permission_str == "N/A":
                    permission_str = new_permission_str
                else:
                    permission_str += "\n{}".format(new_permission_str)

                index += 1

            allowed_device_group_str = "All/Any"
            for allowed_device_group in _user.allowed_device_groups.all():
                new_allowed_device_group_str = "{}".format(allowed_device_group.name)

                if allowed_device_group_str == "All/Any":
                    allowed_device_group_str = new_allowed_device_group_str
                else:
                    allowed_device_group_str = "{}, {}".format(allowed_device_group_str, new_allowed_device_group_str)


            o['secondary_groups'] = secondary_groups_str
            o['permissions'] = permission_str
            o['allowed_device_groups'] = allowed_device_group_str

            data.append(o)

        return data


class PDFReportGenerator(ReportGenerator):
    class Bookmark(object):
        def __init__(self, name, pagenum):
            self.name = name
            self.pagenum = pagenum

    def __init__(self, settings, _devices):
        super(PDFReportGenerator, self).__init__(settings, _devices)

        ## logo and styling options/settings
        system_device = None
        for _device in device.objects.all():
            if _device.is_cluster_device_group():
                system_device = _device
                break

        report_logo = system_device.device_variable_set.filter(name="__REPORT_LOGO__")
        self.logo_width = None
        self.logo_height = None
        self.logo_buffer = BytesIO()
        if report_logo:
            report_logo = report_logo[0]
            data = base64.b64decode(report_logo.val_blob)
            self.logo_buffer.write(data)
            im = PILImage.open(self.logo_buffer)
            self.logo_width = im.size[0]
            self.logo_height = im.size[1]

            drawheight_max = 45
            drawwidth_max = 105

            ratio = float(self.logo_width) / float(self.logo_height)

            while self.logo_width > drawwidth_max or self.logo_height > drawheight_max:
                self.logo_width -= ratio * 1
                self.logo_height -= 1

        else:
            # generate a simple placeholder image
            self.logo_height = 42
            self.logo_width = 103
            logo = PILImage.new('RGB', (255, 255), "black")  # create a new black image
            logo.save(self.logo_buffer, format="BMP")

        self.page_format = eval(self.general_settings["pdf_page_format"])
        self.margin = 36

        self.standard_font = "Open-Sans"
        self.bold_font = "Open-Sans-Bold"

        self.cluster_id = "Unknown"
        cluster_id_var = system_device.device_variable_set.filter(name="CLUSTER_ID")
        if cluster_id_var:
            cluster_id_var = cluster_id_var[0]
            self.cluster_id = cluster_id_var.val_str

        ## Storage dicts / lists
        self.sections = {}
        self.reports = []
        self.device_reports = []
        self.current_page_num = 0

    def get_report_type(self):
        return "pdf"

    def __generate_section_number(self, *sections):
        root_section = self.sections

        version_str = ""

        for section in sections:
            if section not in root_section:
                root_section[section] = {}

            version_str += ".{}".format(len(root_section))

            root_section = root_section[section]

        return version_str[1:]

    def __get_logo_helper(self, value):
        _tmp_file = tempfile.NamedTemporaryFile()
        self.logo_buffer.seek(0)
        _tmp_file.write(self.logo_buffer.read())
        logo = ImageReader(_tmp_file.name)
        _tmp_file.close()

        return logo

    def __config_report_helper(self, header, header_names_left, header_names_right, rpt, data, _device=None):
        available_width = self.page_format[0] - (self.margin * 2)

        header_list = [PollyReportsImage(pos=(available_width - self.logo_width, -25),
                                         width=self.logo_width,
                                         height=self.logo_height,
                                         getvalue=self.__get_logo_helper),
                       Element((0, 0), (self.bold_font, 16), text=header)]

        detail_list = []

        position = 0

        for header_name, key, avail_width_percentage in header_names_left:
            header_list.append(Element((position, 24), (self.standard_font, 12), text=header_name))
            detail_list.append(Element((position, 0), (self.standard_font, 6), key=key))

            position += available_width * (avail_width_percentage / 100.0)

            for _dict in data:
                s = str(_dict[key])

                s_new_comps = ""

                comps = s.split("\n")
                for comp in comps:
                    s_new = ""
                    wrap_idx = 0

                    for i in range(len(comp)):
                        width = stringWidth(s[wrap_idx:i+1], self.standard_font, 6)
                        if ((width / available_width) * 101.5) > avail_width_percentage:
                            wrap_idx = i
                            s_new += "\n"
                        s_new += comp[i]

                    if s_new_comps:
                        s_new_comps += "\n{}".format(s_new)
                    else:
                        s_new_comps = s_new

                _dict[key] = s_new_comps

        position = self.page_format[0] - (self.margin * 2)

        for header_name, key, avail_width_percentage in reversed(header_names_right):
            header_list.append(Element((position, 24), (self.standard_font, 12), text=header_name, align="right"))
            detail_list.append(Element((position, 0), (self.standard_font, 6), key=key, align="right"))

            position -= available_width * (avail_width_percentage / 100.0)

            for _dict in data:
                s = str(_dict[key])

                s_new_comps = ""

                comps = s.split("\n")
                for comp in comps:
                    s_new = ""
                    wrap_idx = 0

                    for i in range(len(comp)):
                        width = stringWidth(s[wrap_idx:i+1], self.standard_font, 6)
                        if ((width / available_width) * 101.5) > avail_width_percentage:
                            wrap_idx = i
                            s_new += "\n"
                        s_new += comp[i]

                    if s_new_comps:
                        s_new_comps += "\n{}".format(s_new)
                    else:
                        s_new_comps = s_new

                _dict[key] = s_new_comps

        header_list.append(Rule((0, 42), self.page_format[0] - (self.margin * 2), thickness=2))
        detail_list.append(Rule((0, 0), self.page_format[0] - (self.margin * 2), thickness=0.1))

        rpt.pageheader = Band(header_list)
        rpt.detailband = Band(detail_list)

    def __generate_general_device_overview_report(self):
        report = GenericReport()

        _buffer = BytesIO()
        canvas = Canvas(_buffer, self.page_format)

        data = _generate_hardware_info_data_dict(self.devices, self.general_settings["assetbatch_selection_mode"])

        data = sorted(data, key=lambda k: k['group'])
        if data:
            section_number = self.__generate_section_number("General", "Device Overview")
            report.generate_bookmark("Device Overview")

            rpt = PollyReportsReport(data)
            rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                              getvalue=lambda x: x['group'],
                                              format=lambda x: "Group: {}".format(x)), ],
                                     getvalue=lambda x: x["group"])]

            header_names_left = [("Device Name", "name", 10.0),
                                 ("CPU Info", "cpu", 18.0),
                                 ("GPU Info", "gpu", 18.0),
                                 ("Memory Info", "memory", 18.0),
                                 ("HDD Info", "hdd", 18.0),
                                 ("Partition Info", "partition", 18.0)
                                 ]
            header_names_right = []

            self.__config_report_helper("{} Device Overview".format(section_number), header_names_left,
                                        header_names_right, rpt, data)

            rpt.generate(canvas)
            canvas.save()
            report.number_of_pages += rpt.pagenumber
            report.add_to_report(_buffer)
            self.reports.append(report)
            self.current_page_num += rpt.pagenumber

    def __generate_network_report(self):
        from initat.cluster.backbone.models import network

        report = GenericReport()

        _buffer = BytesIO()
        canvas = Canvas(_buffer, (self.page_format))

        networks = network.objects.all()
        data = []

        for _network in networks:
            o = {
                'id': _network.identifier,
                'network': _network.network,
                'netmask': _network.netmask,
                'broadcast': _network.broadcast,
                'gateway': _network.gateway,
                'gwprio': _network.gw_pri,
                'num_ips': _network.num_ip(),
                'network_type': _network.network_type.description
            }

            data.append(o)

        data = sorted(data, key=lambda k: k['id'])
        if data:
            section_number = self.__generate_section_number("General", "Networks")
            report.generate_bookmark("Networks")

            rpt = PollyReportsReport(data)
            rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                              getvalue=lambda x: x['id'][0],
                                              format=lambda x: "Networks starting with: {}".format(x)), ],
                                     getvalue=lambda x: x["id"][0])]

            header_names_left = [("Identifier", "id", 12.5),
                            ("Network", "network", 12.5),
                            ("Netmask", "netmask", 12.5),
                            ("Broadcast", "broadcast", 12.5),
                            ("Gateway", "gateway", 12.5),
                            ('GW Priority', "gwprio", 12.5),
                            ("#IPs", "num_ips", 12.5),
                            ("Network Type", "network_type", 12.5)]

            header_names_right = []

            self.__config_report_helper("{} Network Overview".format(section_number),
                                        header_names_left,
                                        header_names_right, rpt, data)

            rpt.generate(canvas)
            canvas.save()
            report.number_of_pages += rpt.pagenumber
            report.add_to_report(_buffer)
            self.reports.append(report)
            self.current_page_num += rpt.pagenumber

    def __generate_device_report(self, _device, report_settings):
        device_report = DeviceReport(_device, report_settings)
        self.device_reports.append(device_report)

        # create generic overview page
        self.generate_overview_page(device_report)

        selected_runs = _select_assetruns_for_device(_device, self.general_settings["assetbatch_selection_mode"])

        self.generate_report_for_assetruns(selected_runs, device_report)

    def generate_overview_page(self, report):
        _device = report.device

        section_number = self.__generate_section_number("Device Reports", _device.device_group_name(), _device.full_name, "Overview")
        report.generate_bookmark("Overview")

        _buffer = BytesIO()
        doc = SimpleDocTemplate(_buffer,
                                pagesize=self.page_format,
                                rightMargin=25,
                                leftMargin=25,
                                topMargin=0,
                                bottomMargin=25)
        elements = []

        style_sheet = getSampleStyleSheet()

        available_width = self.page_format[0] - (self.margin * 2)

        paragraph_header = Paragraph('<font face="{}" size="16">{} Overview for {}</font>'.format(
            self.bold_font, section_number, _device.name), style_sheet["BodyText"])

        logo = Image(self.logo_buffer)
        logo.drawHeight = self.logo_height
        logo.drawWidth = self.logo_width

        data = [[paragraph_header, logo]]

        t_head = Table(data, colWidths=(available_width - self.logo_width, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        body_data = []

        # FQDN
        data = [[_device.full_name]]

        text_block = Paragraph('<b>FQDN:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )
        body_data.append((text_block, t))

        # Device Groups
        data = [[_device.device_group_name()]]

        text_block = Paragraph('<b>DeviceGroup:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # Device Class
        data = [[_device.device_class.name]]

        text_block = Paragraph('<b>DeviceClass:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # ComCapabilites
        str_to_use = "N/A"

        for com_cap in _device.com_capability_list.all():
            if str_to_use == "N/A":
                str_to_use = com_cap.name
            else:
                str_to_use += ", {}".format(com_cap.name)
        data = [[str_to_use]]

        text_block = Paragraph('<b>ComCapabilities:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # Ip info
        str_to_use = "N/A"
        for _ip in _device.all_ips():
            if str_to_use == "N/A":
                str_to_use = str(_ip)
            else:
                str_to_use += ", {}".format(str(_ip))
        data = [[str_to_use]]

        text_block = Paragraph('<b>IP Info:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # SNMP Schemes
        str_to_use = "N/A"
        for _snmp_scheme in _device.snmp_schemes.all():
            if str_to_use == "N/A":
                str_to_use = str(_snmp_scheme)
            else:
                str_to_use += ", {}".format(str(_snmp_scheme))
        data = [[str_to_use]]

        text_block = Paragraph('<b>SNMP Scheme:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # SNMP Info
        str_to_use = "N/A"
        data = [[str_to_use]]

        text_block = Paragraph('<b>SNMP Info:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # Device Categories
        str_to_use = "N/A"
        for _category in _device.categories.all():
            if str_to_use == "N/A":
                str_to_use = _category.name
            else:
                str_to_use += ", {}".format(_category.name)
        data = [[str_to_use]]

        text_block = Paragraph('<b>Categories:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 1, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        t_body = Table(body_data, colWidths=(available_width * 0.15, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        elements.append(t_head)
        elements.append(Spacer(1, 30))
        elements.append(t_body)

        doc.build(elements, onFirstPage=report.increase_page_count, onLaterPages=report.increase_page_count)
        report.add_to_report(_buffer)

    def generate_report_for_assetruns(self, assetruns, report):
        _buffer = BytesIO()

        _device = report.device

        canvas = Canvas(_buffer, self.page_format)

        row_collector = RowCollector()

        # Hardware report is generated last
        hardware_report_ar = None

        sorted_runs = {}

        for ar in assetruns:
            if AssetType(ar.run_type) == AssetType.PACKAGE:
                sorted_runs[0] = ar
            elif AssetType(ar.run_type) == AssetType.LICENSE:
                sorted_runs[1] = ar
            elif AssetType(ar.run_type) == AssetType.UPDATE:
                sorted_runs[2] = ar
            elif AssetType(ar.run_type) == AssetType.PENDING_UPDATE:
                sorted_runs[3] = ar
            elif AssetType(ar.run_type) == AssetType.PROCESS:
                sorted_runs[4] = ar
            elif AssetType(ar.run_type) == AssetType.PRETTYWINHW:
                sorted_runs[5] = ar
            elif AssetType(ar.run_type) == AssetType.DMI:
                sorted_runs[6] = ar
            elif AssetType(ar.run_type) == AssetType.PCI:
                sorted_runs[7] = ar
            elif AssetType(ar.run_type) == AssetType.HARDWARE:
                sorted_runs[8] = ar


        for idx in sorted_runs:
            ar = sorted_runs[idx]

            row_collector.reset()
            row_collector.current_asset_type = AssetType(ar.run_type)
            generate_csv_entry_for_assetrun(ar, row_collector.collect)

            if AssetType(ar.run_type) == AssetType.UPDATE:
                if not report.report_settings['installed_updates_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['update_status'])

                heading = "System Updates" # "Installed Updates"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                                      getvalue=lambda x: x['update_status'],
                                                      format=lambda x: "Updates with status: {}".format(x)), ],
                                             getvalue=lambda x: x["update_status"]), ]
                else:
                    mock_object = {
                        "update_name": "",
                        "install_date": "",
                        "update_status": "",
                    }
                    data.append(mock_object)

                header_names_left = [("Update Name", "update_name", 70.0),
                                     ("Install Status", "update_status", 15.0)]
                header_names_right = [("Install Date", "install_date", 15.0)]

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.LICENSE:
                if not report.report_settings['licenses_selected']:
                    continue

                data = row_collector.rows_dict[1:]

                heading = "Active Licenses" # "Available Licenses"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if not data:
                    mock_object = {
                        "license_name": "",
                        "license_key": ""
                    }
                    data.append(mock_object)

                header_names_left = [("License Name", "license_name", 50.0),
                                     ("License Key", "license_key", 50.0)]
                header_names_right = []

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PACKAGE:
                if not report.report_settings['packages_selected']:
                    continue

                from initat.cluster.backbone.models import asset

                try:
                    packages = asset.get_packages_for_ar(ar)
                except Exception as e:
                    logger.info("PDF generation for packages failed, error was: {}".format(str(e)))
                    packages = []

                heading = "Installed Software" # "Installed Packages"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                data = [package.get_as_row() for package in packages]
                data = sorted(data, key=lambda k: k['package_name'])

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                                      getvalue=lambda x: x['package_name'][0],
                                                      format=lambda x: "Packages starting with: {}".format(x)), ],
                                             getvalue=lambda x: x["package_name"][0]), ]
                else:
                    mock_object = {
                        "package_name": "",
                        "package_version": "",
                        "package_release": "",
                        "package_size": "",
                        "package_install_date": ""
                    }
                    data.append(mock_object)

                header_names_left = [("Name", "package_name", 40.0),
                                     ("Version", "package_version", 15.00),
                                     ("Release", "package_release", 15.00)]
                header_names_right = [("Size", "package_size", 15.00),
                                     ("Install Date", "package_install_date", 15.00)]

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PENDING_UPDATE:
                if not report.report_settings['avail_updates_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['update_name'])

                heading = "Updates ready for install" # "Available Updates"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)

                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                                      getvalue=lambda x: x['update_name'][0].upper(),
                                                      format=lambda x: "Updates starting with: {}".format(x)), ],
                                             getvalue=lambda x: x["update_name"][0].upper()), ]
                else:
                    mock_object = {
                        "update_name": "",
                        "update_version": "",
                        "update_optional": ""
                    }
                    data.append(mock_object)

                header_names_left = [("Update Name", "update_name", 33.33),
                                     ("Version", "update_version", 33.33),
                                     ("Optional", "update_optional", 33.33)]
                header_names_right = []

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.HARDWARE:
                if not report.report_settings['lstopo_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['hardware_depth'])

                heading = "Lstopo Information"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if not data:
                    mock_object = {
                        "hardware_node_type": "",
                        "hardware_depth": "",
                        "hardware_attributes": "",
                    }
                    data.append(mock_object)

                header_names_left = [("Node Type", "hardware_node_type", 15.00),
                                     ("Depth", "hardware_depth", 15.00),
                                     ("Attributes", "hardware_attributes", 70.00)]
                header_names_right = []

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PROCESS:
                if not report.report_settings['process_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['process_name'])

                heading = "Process Information"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                                      getvalue=lambda x: x['process_name'][0],
                                                      format=lambda x: "Processes starting with: {}".format(x)), ],
                                             getvalue=lambda x: x["process_name"][0]), ]
                else:
                    mock_object = {
                        "process_name": "",
                        "process_id": "",
                    }
                    data.append(mock_object)

                header_names_left = [("Process Name", "process_name", 50.0),
                                     ("PID", "process_id", 50.0)]
                header_names_right = []

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.DMI:
                if not report.report_settings['dmi_report_selected']:
                    continue

                heading = "Hardware Details" #"DMI Information"

                data = row_collector.rows_dict[1:]

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if not data:
                    mock_object = {
                        "handle": "",
                        "dmi_type": "",
                        "header": "",
                        "key": "",
                        "value": ""
                    }
                    data.append(mock_object)

                header_names_left = [("Handle", "handle", 8.0),
                                     ("Type", "dmi_type", 8.0),
                                     ("Header", "header", 15.0),
                                     ("Key", "key", 15.0),
                                     ("Value", "value", 54.0)]
                header_names_right = []

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PCI:
                if not report.report_settings['pci_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]

                heading = "PCI Details"

                section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                                _device.full_name, heading)
                report.generate_bookmark(heading)

                rpt = PollyReportsReport(data)

                if not data:
                    mock_object = {
                        'domain': "",
                        'bus': "",
                        'slot': "",
                        'func': "",
                        'position': "",
                        'subclass': "",
                        'vendor': "",
                        'device': "",
                        'revision': ""
                    }

                    data.append(mock_object)

                header_names_left = [("Domain", "domain", 7.5),
                                     ("Bus", "bus", 5.0),
                                     ("Slot", "slot", 5.0),
                                     ("Func", "func", 5.0),
                                     ("Position", "position", 10.0),
                                     ("Subclass", "subclass", 10.0),
                                     ("Vendor", "vendor", 28.75),
                                     ("Device", "device", 28.75)]
                header_names_right = []

                self.__config_report_helper("{} {} for {}".format(section_number, heading, _device.full_name),
                                            header_names_left, header_names_right, rpt, data, _device)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif ar.run_type == AssetType.PRETTYWINHW:
                if not report.report_settings['hardware_report_selected']:
                    continue

                hardware_report_ar = ar
                continue

        canvas.save()
        report.add_to_report(_buffer)

        if hardware_report_ar:
            self.generate_hardware_report(hardware_report_ar, report)

    def generate_hardware_report(self, hardware_report_ar, report):
        _device = report.device

        section_number = self.__generate_section_number("Device Reports", _device.device_group_name(),
                                                        _device.full_name, "Hardware Report")
        report.generate_bookmark("Hardware Report".format(section_number))

        _buffer = BytesIO()
        doc = SimpleDocTemplate(_buffer,
                                pagesize=self.page_format,
                                rightMargin=25,
                                leftMargin=25,
                                topMargin=0,
                                bottomMargin=25)
        elements = []

        style_sheet = getSampleStyleSheet()
        style_sheet.add(ParagraphStyle(name='courier',
                                       fontName='Courier',
                                       fontSize=12))

        available_width = self.page_format[0] - (self.margin * 2)

        data = [["Name", "Cores"]]
        for cpu in hardware_report_ar.cpus.all():
            data.append([Paragraph(str(cpu.cpuname), style_sheet["BodyText"]),
                         Paragraph(str(cpu.numberofcores), style_sheet["BodyText"])])

        p0_1 = Paragraph('<b>CPUs:</b>', style_sheet["BodyText"])

        t_1 = Table(data,
                    colWidths=(available_width * 0.90 * 0.50,
                               available_width * 0.90 * 0.50),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black)])

        data = [["Name", "Driver Version"]]
        for gpu in hardware_report_ar.gpus.all():
            data.append([Paragraph(str(gpu.gpuname), style_sheet["BodyText"]),
                         Paragraph(str(gpu.driverversion), style_sheet["BodyText"])])

        p0_2 = Paragraph('<b>GPUs:</b>', style_sheet["BodyText"])
        t_2 = Table(data,
                    colWidths=(available_width * 0.90 * 0.50,
                               available_width * 0.90 * 0.50),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [["Name", "Serialnumber", "Size"]]
        for hdd in hardware_report_ar.hdds.all():
            data.append([Paragraph(str(hdd.name), style_sheet["BodyText"]),
                         Paragraph(str(hdd.serialnumber), style_sheet["courier"]),
                         Paragraph(sizeof_fmt(hdd.size), style_sheet["BodyText"])])

        p0_3 = Paragraph('<b>HDDs:</b>', style_sheet["BodyText"])
        t_3 = Table(data,
                    colWidths=(available_width * 0.90 * 0.33,
                               available_width * 0.90 * 0.34,
                               available_width * 0.90 * 0.33),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [["Name", "Size", "Free", "Graph"]]
        for partition in hardware_report_ar.partitions.all():
            d = Drawing(10, 10)
            r = Rect(0, 0, 130, 12)
            r.fillColor = colors.red
            d.add(r)

            if partition.size is not None and partition.free is not None:
                free_length = int((float(partition.free) / float(partition.size)) * 130)
                free_start = 130 - free_length

                r = Rect(free_start, 0, free_length, 12)
                r.fillColor = colors.green
                d.add(r)
            else:
                d = Paragraph("N/A", style_sheet["BodyText"])

            data.append([Paragraph(str(partition.name), style_sheet["BodyText"]),
                         Paragraph(sizeof_fmt(partition.size), style_sheet["BodyText"]),
                         Paragraph(sizeof_fmt(partition.free), style_sheet["BodyText"]),
                         d])

        p0_4 = Paragraph('<b>Partitions:</b>', style_sheet["BodyText"])
        t_4 = Table(data,
                    colWidths=(available_width * 0.90 * 0.25,
                               available_width * 0.90 * 0.25,
                               available_width * 0.90 * 0.25,
                               available_width * 0.90 * 0.25),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [["Banklabel", "Formfactor", "Memorytype", "Manufacturer", "Capacity"]]
        for memory_module in hardware_report_ar.memory_modules.all():

            data.append([Paragraph(str(memory_module.banklabel), style_sheet["BodyText"]),
                         Paragraph(str(memory_module.get_name_of_form_factor()), style_sheet["BodyText"]),
                         Paragraph(str(memory_module.get_name_of_memory_type()), style_sheet["BodyText"]),
                         Paragraph(str(memory_module.manufacturer), style_sheet["BodyText"]),
                         Paragraph(sizeof_fmt(memory_module.capacity), style_sheet["BodyText"])])

        p0_5 = Paragraph('<b>Memory Modules:</b>', style_sheet["BodyText"])
        t_5 = Table(data,
                    colWidths=(available_width * 0.90 * 0.2,
                               available_width * 0.90 * 0.2,
                               available_width * 0.90 * 0.2,
                               available_width * 0.90 * 0.2,
                               available_width * 0.90 * 0.2),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [[p0_1, t_1],
                [p0_2, t_2],
                [p0_3, t_3],
                [p0_4, t_4],
                [p0_5, t_5]]

        t_body = Table(data, colWidths=(available_width * 0.10, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        p_h = Paragraph('<font face="{}" size="16">{} Hardware Report for {}</font>'.format(self.bold_font, section_number,
            hardware_report_ar.device.name), style_sheet["BodyText"])

        logo = Image(self.logo_buffer)
        logo.drawHeight = self.logo_height
        logo.drawWidth = self.logo_width

        data = [[p_h, logo]]

        t_head = Table(data, colWidths=(available_width - self.logo_width, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        elements.append(t_head)
        elements.append(Spacer(1, 30))
        elements.append(t_body)

        doc.build(elements, onFirstPage=report.increase_page_count, onLaterPages=report.increase_page_count)

        report.add_to_report(_buffer)

    def finalize_pdf(self):
        output_buffer = BytesIO()
        output_pdf = PdfFileWriter()

        # Sort reports by device group name
        group_report_dict = {}
        for _report in self.device_reports:
            _group_name = _report.device.device_group_name()
            if _group_name not in group_report_dict:
                group_report_dict[_group_name] = []

            group_report_dict[_group_name].append(_report)

        current_page_number = 0
        page_num_headings = {}

        # 1. Pass: Generate pdf, structure is group_name -> device -> report (except for general reports)
        # generate table of contents and bookmark Headings to page number mapping
        if self.reports:
            page_num_headings[current_page_number] = []
            page_num_headings[current_page_number].append(("General Reports", 0))

            for _report in self.reports:
                for _bookmark in _report.bookmarks:
                    if current_page_number + _bookmark.pagenum not in page_num_headings:
                        page_num_headings[current_page_number + _bookmark.pagenum] = []
                    page_num_headings[current_page_number + _bookmark.pagenum].append((_bookmark.name, 1))

                for _buffer in _report.pdf_buffers:
                    sub_pdf = PdfFileReader(_buffer)
                    [output_pdf.addPage(sub_pdf.getPage(page_num)) for page_num in range(sub_pdf.numPages)]
                current_page_number += _report.number_of_pages

        if self.device_reports:
            page_num_headings[current_page_number] = []
            page_num_headings[current_page_number].append(("Device Reports", 0))

            for _group_name in group_report_dict:
                if current_page_number not in page_num_headings:
                    page_num_headings[current_page_number] = []
                page_num_headings[current_page_number].append((_group_name, 1))

                _device_reports = {}
                for _report in group_report_dict[_group_name]:
                    if _report.device not in _device_reports:
                        _device_reports[_report.device] = []
                    _device_reports[_report.device].append(_report)

                for _device in sorted(_device_reports, key=lambda _device: _device.full_name):
                    if current_page_number not in page_num_headings:
                        page_num_headings[current_page_number] = []
                    page_num_headings[current_page_number].append((_device.full_name, 2))
                    for _report in _device_reports[_device]:
                        for _buffer in _report.pdf_buffers:
                            sub_pdf = PdfFileReader(_buffer)
                            [output_pdf.addPage(sub_pdf.getPage(page_num)) for page_num in range(sub_pdf.numPages)]

                        for _bookmark in _report.bookmarks:
                            if not (current_page_number + _bookmark.pagenum) in page_num_headings:
                                page_num_headings[(current_page_number + _bookmark.pagenum)] = []
                            page_num_headings[(current_page_number + _bookmark.pagenum)].append((_bookmark.name, 3))

                        current_page_number += _report.number_of_pages

        toc_buffer, page_num_prefix_dict = self.__get_toc_pages(page_num_headings)
        toc_pdf = PdfFileReader(toc_buffer)
        toc_pdf_page_num = toc_pdf.getNumPages()

        for i in reversed(range(toc_pdf_page_num)):
            output_pdf.insertPage(toc_pdf.getPage(i))

        frontpage_buffer = self.__generate_front_page()
        frontpage_pdf = PdfFileReader(frontpage_buffer)
        frontpage_page_num = frontpage_pdf.getNumPages()

        for i in reversed(range(frontpage_page_num)):
            output_pdf.insertPage(frontpage_pdf.getPage(i))

        number_of_pre_content_sites = frontpage_page_num + toc_pdf_page_num

        # 2. Pass: Add page numbers
        output_pdf.write(output_buffer)
        output_pdf = self.__add_page_numbers(output_buffer, number_of_pre_content_sites, page_num_prefix_dict)
        self.progress = 100

        # 3. Pass: Generate Bookmarks
        current_page_number = number_of_pre_content_sites

        if self.reports:
            general_reports_bookmark = output_pdf.addBookmark("General Reports", current_page_number)

            for _report in self.reports:
                for _bookmark in _report.bookmarks:
                    output_pdf.addBookmark(_bookmark.name, current_page_number + _bookmark.pagenum,
                                           parent=general_reports_bookmark)
                current_page_number += _report.number_of_pages

        if self.device_reports:
            device_reports_bookmark = output_pdf.addBookmark("Device Reports", current_page_number)
            for _group_name in group_report_dict:
                group_bookmark = output_pdf.addBookmark(_group_name, current_page_number,
                                                        parent=device_reports_bookmark)

                _device_reports = {}

                for _report in group_report_dict[_group_name]:
                    if _report.device not in _device_reports:
                        _device_reports[_report.device] = []
                    _device_reports[_report.device].append(_report)

                for _device in sorted(_device_reports, key=lambda _device: _device.full_name):
                    device_bookmark = output_pdf.addBookmark(_device.full_name, current_page_number,
                                                             parent=group_bookmark)

                    for _report in _device_reports[_device]:
                        for _bookmark in _report.bookmarks:
                            output_pdf.addBookmark(_bookmark.name, current_page_number + _bookmark.pagenum,
                                                   parent=device_bookmark)
                        current_page_number += _report.number_of_pages

        output_buffer = BytesIO()
        output_pdf.write(output_buffer)
        self.data = output_buffer.getvalue()

        # create report history entry
        _user = user.objects.get(idx=self.general_settings["user_idx"])
        self.report_history.created_by_user = _user
        self.report_history.created_at_time = timezone.make_aware(self.creation_date, timezone.get_current_timezone())
        self.report_history.number_of_pages = output_pdf.getNumPages()
        self.report_history.size = len(self.data)
        self.report_history.type = self.get_report_type()
        self.report_history.generate_filename()
        self.report_history.save()

        self.report_history.write_data(self.data)

        self.progress = -1

    def __generate_front_page(self):
        _buffer = BytesIO()
        doc = SimpleDocTemplate(_buffer,
                                pagesize=self.page_format,
                                rightMargin=0,
                                leftMargin=0,
                                topMargin=0,
                                bottomMargin=0)
        elements = []

        style_sheet = getSampleStyleSheet()
        style_sheet.add(ParagraphStyle(name='red font', textColor=colors.red))
        style_sheet.add(ParagraphStyle(name='green font', textColor=colors.green))

        available_width = self.page_format[0] - (self.margin * 2)

        data = [["Report #{}".format(self.report_id)]]

        t_head = Table(data, colWidths=(available_width),
                       style=[('FONTSIZE', (0, 0), (-1, -1), 22),
                              ('TEXTFONT', (0, 0), (-1, -1), self.standard_font),
                              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                              ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (-1, -1), 0)])

        # body content
        _user = user.objects.get(idx=self.general_settings["user_idx"])
        _user_str = str(_user)

        _creation_str = self.creation_date.strftime(ASSET_DATETIMEFORMAT)

        body_data = []

        data = [[self.report_id]]

        text_block = Paragraph('<b>ReportID:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[]
                  )
        body_data.append((text_block, t))

        data = [[self.cluster_id]]

        text_block = Paragraph('<b>ClusterID:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[]
                  )

        body_data.append((text_block, t))

        data = [[_creation_str]]

        text_block = Paragraph('<b>CreationDate:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[]
                  )

        body_data.append((text_block, t))

        data = [[_user_str]]

        text_block = Paragraph('<b>Requested by user:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[]
                  )

        body_data.append((text_block, t))

        data = [[self.general_settings['hostname']]]

        text_block = Paragraph('<b>Requested by host:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(available_width * 0.85),
                  style=[]
                  )

        body_data.append((text_block, t))

        t_body = Table(body_data, colWidths=(available_width * 0.15, available_width * 0.85),
                       style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (-1, -1), 0)]
                       )


        # config matrix
        config_data = []


        header_row = [Paragraph('Device', style_sheet["BodyText"]),
                      Paragraph('Installed Packages', style_sheet["BodyText"]),
                      Paragraph('Available Licenses', style_sheet["BodyText"]),
                      Paragraph('Installed Updates', style_sheet["BodyText"]),
                      Paragraph('Available Updates', style_sheet["BodyText"]),
                      Paragraph('Process Information', style_sheet["BodyText"]),
                      Paragraph('Hardware Report', style_sheet["BodyText"]),
                      Paragraph('DMI Information', style_sheet["BodyText"]),
                      Paragraph('PCI Information', style_sheet["BodyText"]),
                      Paragraph('LSTOPO Information', style_sheet["BodyText"])]



        config_data.append(header_row)

        device_group_to_devices_dict = {}

        for idx in self.device_settings:
            if idx < 0:
                continue

            _device = device.objects.get(idx=idx)
            _device_group = _device.device_group.name
            if _device_group not in device_group_to_devices_dict:
                device_group_to_devices_dict[_device_group] = []

            device_group_to_devices_dict[_device_group].append(_device)


        for _device_group in device_group_to_devices_dict:
            for _device in device_group_to_devices_dict[_device_group]:
                row = [Paragraph(_device.full_name, style_sheet["BodyText"])]

                for i in range(1, 10):
                    if i == 1:
                        if self.device_settings[_device.idx]["packages_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 2:
                        if self.device_settings[_device.idx]["licenses_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 3:
                        if self.device_settings[_device.idx]["installed_updates_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 4:
                        if self.device_settings[_device.idx]["avail_updates_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 5:
                        if self.device_settings[_device.idx]["process_report_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 6:
                        if self.device_settings[_device.idx]["hardware_report_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 7:
                        if self.device_settings[_device.idx]["dmi_report_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 8:
                        if self.device_settings[_device.idx]["pci_report_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))
                    if i == 9:
                        if self.device_settings[_device.idx]["lstopo_report_selected"]:
                            row.append(Paragraph('On', style_sheet["green font"]))
                        else:
                            row.append(Paragraph('Off', style_sheet["red font"]))

                config_data.append(row)

        t_config = Table(config_data, colWidths=[available_width * (float(1) / len(header_row)) for _ in range(len(header_row))],
                         style=[('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                                ('BOX', (0, 0), (-1, -1), 0.5, colors.black)
                                ]
                         )

        config_data = []
        header_row = [Paragraph('Network Overview', style_sheet["BodyText"]),
                      Paragraph('Device Overview', style_sheet["BodyText"]),
                      Paragraph('User/Group Overview', style_sheet["BodyText"])]

        row = []

        if self.general_settings['network_report_overview_module_selected']:
            row.append(Paragraph('On', style_sheet["green font"]))
        else:
            row.append(Paragraph('Off', style_sheet["red font"]))

        if self.general_settings['general_device_overview_module_selected']:
            row.append(Paragraph('On', style_sheet["green font"]))
        else:
            row.append(Paragraph('Off', style_sheet["red font"]))

        if self.general_settings['user_group_overview_module_selected']:
            row.append(Paragraph('On', style_sheet["green font"]))
        else:
            row.append(Paragraph('Off', style_sheet["red font"]))

        config_data.append(header_row)
        config_data.append(row)
        t_config_2 = Table(config_data, colWidths=[available_width * (float(1) / len(header_row)) for _ in range(len(header_row))],
                         style=[('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                                ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
                                ]
                         )


        elements.append(t_head)
        elements.append(Spacer(1, 30))
        elements.append(t_body)
        elements.append(Spacer(1, 30))
        elements.append(t_config_2)


        if self.devices:
            elements.append(Spacer(1, 30))
            elements.append(t_config)

        doc.build(elements)

        return _buffer


    def __get_toc_pages(self, page_num_headings):
        style_sheet = getSampleStyleSheet()

        paragraph_header = Paragraph('<font face="{}" size="16">Contents</font>'.format(self.bold_font),
                                     style_sheet["BodyText"])

        logo = Image(self.logo_buffer)
        logo.drawHeight = self.logo_height
        logo.drawWidth = self.logo_width

        data = [[paragraph_header, logo]]

        available_width = self.page_format[0] - (self.margin * 2)

        t_head = Table(data,
                       colWidths=(available_width - self.logo_width, None),
                       style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        _buffer = BytesIO()
        can = Canvas(_buffer, pagesize=self.page_format)
        can.setFont(self.standard_font, 14)

        width, heigth = self.page_format

        t_head.wrapOn(can, 0, 0)
        t_head.drawOn(can, 25, heigth - 50)

        vertical_x_limit = 32
        vertical_x = 1
        num_pages = 1

        for page_num in sorted(page_num_headings.keys()):
            for _, _ in page_num_headings[page_num]:
                vertical_x += 1
                if vertical_x > vertical_x_limit:
                    vertical_x = 1
                    num_pages += 1

        vertical_x = 1
        prefix_0 = 1
        prefix_1 = 1
        prefix_2 = 1
        prefix_3 = 1

        top_margin = 75

        number_of_entries = 0
        number_of_entries_generated = 0
        for page_num in page_num_headings.keys():
            number_of_entries += len(page_num_headings[page_num])

        page_num_prefix_dict = {}

        for page_num in sorted(page_num_headings.keys()):
            for heading, indent in page_num_headings[page_num]:
                if indent == 0:
                    prefix_1 = 1
                    prefix_2 = 1

                    prefix = "{}.".format(prefix_0)
                    prefix_0 += 1
                elif indent == 1:
                    prefix_2 = 1
                    prefix = "{}.{}".format(prefix_0 - 1, prefix_1)
                    prefix_1 += 1
                elif indent == 2:
                    prefix_3 = 1
                    prefix = "{}.{}.{}".format(prefix_0 - 1, prefix_1 - 1, prefix_2)
                    prefix_2 += 1
                else:
                    prefix = "{}.{}.{}.{}".format(prefix_0 - 1, prefix_1 - 1, prefix_2 - 1, prefix_3)
                    prefix_3 += 1

                page_num_prefix_dict[page_num] = prefix

                heading_str = "{} {}".format(prefix, heading)

                can.drawString(25 + (25 * indent), heigth - (top_margin + (15 * vertical_x)), heading_str)

                heading_str_width = stringWidth(heading_str, self.standard_font, 14)

                dots = "."
                while (25 * indent) + heading_str_width + stringWidth(dots, self.standard_font, 14) < (width - 150):
                    dots += "."

                can.drawString(35 + (25 * indent) + heading_str_width, heigth - (top_margin + (15 * vertical_x)), dots)

                can.drawString(width - 75, heigth - (top_margin + (15 * vertical_x)),
                               "{}".format(page_num + num_pages + 1))
                vertical_x += 1
                number_of_entries_generated += 1
                if vertical_x > vertical_x_limit:
                    vertical_x = 1
                    if number_of_entries_generated < number_of_entries:
                        can.showPage()
                        can.setFont(self.standard_font, 14)
                        t_head.wrapOn(can, 0, 0)
                        t_head.drawOn(can, 25, heigth - 50)

        can.save()

        return _buffer, page_num_prefix_dict

    def __add_page_numbers(self, pdf_buffer, toc_offset_num, page_num_prefix_dict):
        output = PdfFileWriter()
        existing_pdf = PdfFileReader(pdf_buffer)
        num_pages = existing_pdf.getNumPages()

        for page_number in range(num_pages):
            # this loop might take a long time -> kill this loop if no polling happend in the last few seconds (i.e the
            # user closed the browser window or switched to a different view
            if self.last_poll_time and (datetime.datetime.now() - self.last_poll_time).seconds > 5:
                break

            self.progress = int((page_number / float(num_pages)) * 90) + 10
            page = existing_pdf.getPage(page_number)

            if page_number >= toc_offset_num:
                page_num_buffer = BytesIO()
                can = Canvas(page_num_buffer, pagesize=self.page_format)
                can.setFont(self.standard_font, 8)

                creationdate_str = self.creation_date.strftime(ASSET_DATETIMEFORMAT)
                str_to_draw = "Page: {} | ReportId: {} | ClusterId: {} | Generated: {}".format(page_number + 1,
                                                                                               self.report_id,
                                                                                               self.cluster_id, creationdate_str)
                can.drawString(25, 15, str_to_draw)

                # if (page_number - toc_offset_num) in page_num_prefix_dict:
                #     str_to_draw = "({})".format(page_num_prefix_dict[page_number - toc_offset_num])
                #
                #     can.drawString(self.page_format[0] - self.margin - stringWidth(str_to_draw, self.standard_font, 14),
                #                    25,
                #                    str_to_draw)

                can.save()
                page_num_buffer.seek(0)
                page_num_pdf = PdfFileReader(page_num_buffer)
                page.mergePage(page_num_pdf.getPage(0))

            output.addPage(page)

        return output

    def __generate_user_group_overview_report(self):
        report = GenericReport()

        _buffer = BytesIO()
        canvas = Canvas(_buffer, (self.page_format))

        data = self._get_data_for_user_group_overview()

        data = sorted(data, key=lambda k: (k['group'], k['login']))
        if data:
            section_number = self.__generate_section_number("General", "Userlist")
            report.generate_bookmark("Users")

            rpt = PollyReportsReport(data)
            rpt.groupheaders = [Band([Element((0, 4), (self.bold_font, 10),
                                              getvalue=lambda x: x['group'],
                                              format=lambda x: "Group: {}".format(x)), ],
                                     getvalue=lambda x: x["group"])]

            header_names_left = [("Login", "login", 10.0),
                                 ("UID", "uid", 10.0),
                                 ("First name", "firstname", 10.0),
                                 ("Last name", "lastname", 10.0),
                                 ("Email", "email", 10.0),
                                 ("Groups", "secondary_groups", 10.0),
                                 ("Permissions", "permissions", 20.0),
                                 ("Allowed Device Groups", "allowed_device_groups", 20.0)]

            header_names_right = []

            self.__config_report_helper("{} Userlist".format(section_number),
                                        header_names_left,
                                        header_names_right, rpt, data)

            rpt.generate(canvas)
            canvas.save()
            report.number_of_pages += rpt.pagenumber
            report.add_to_report(_buffer)
            self.reports.append(report)
            self.current_page_num += rpt.pagenumber


    def generate_report(self):
        if self.general_settings["network_report_overview_module_selected"]:
            self.__generate_network_report()

        if self.general_settings["general_device_overview_module_selected"]:
            self.__generate_general_device_overview_report()

        if self.general_settings["user_group_overview_module_selected"]:
            self.__generate_user_group_overview_report()

        group_device_dict = {}
        for _device in self.devices:
            _group_name = _device.device_group_name()
            if _group_name not in group_device_dict:
                group_device_dict[_group_name] = []

            group_device_dict[_group_name].append(_device)

        idx = 1
        for _group_name in group_device_dict:
            for _device in sorted(group_device_dict[_group_name], key=lambda _device: _device.full_name):
                if self.last_poll_time and (datetime.datetime.now() - self.last_poll_time).seconds > 5:
                    return
                self.__generate_device_report(_device, self.device_settings[_device.idx])
                self.progress = int((float(idx) / len(self.devices)) * 10)
                idx += 1

        self.progress = 10

        self.finalize_pdf()


class XlsxReportGenerator(ReportGenerator):
    def get_report_type(self):
        return "xlsx"

    def generate_report(self):
        workbooks = []

        if self.general_settings['network_report_overview_module_selected']:
            workbook = self.__generate_network_report()

            workbooks.append((workbook, "Network_Overview"))

        if self.general_settings['general_device_overview_module_selected']:
            workbook = self.__generate_general_device_overview_report()

            workbooks.append((workbook, "Device_Overview"))

        if self.general_settings['user_group_overview_module_selected']:
            workbook = self.__generate_user_group_overview_report()

            workbooks.append((workbook, "User_Group_Overview"))

        idx = 1
        for _device in self.devices:
            workbook = Workbook()
            workbook.remove_sheet(workbook.active)

            self.__generate_device_overview(_device, workbook)
            device_report = DeviceReport(_device, self.device_settings[_device.idx])

            selected_runs = _select_assetruns_for_device(_device,
                                                         self.general_settings["assetbatch_selection_mode"])

            for ar in selected_runs:
                if not device_report.module_selected(ar):
                    continue
                sheet = workbook.create_sheet()
                _title = AssetType(ar.run_type).name

                # xlsx limited to max 31 chars in title
                if len(_title) > 31:
                    _title = _title[:31]

                sheet.title = _title

                generate_csv_entry_for_assetrun(ar, sheet.append)

            self.progress = int(round((float(idx) / len(self.devices)) * 100))
            idx += 1

            workbooks.append((workbook, _device.full_name))

        from zipfile import ZipFile
        buffer = BytesIO()
        zipfile = ZipFile(buffer, "w")

        for workbook, workbook_name in workbooks:
            s = save_virtual_workbook(workbook)

            zipfile.writestr("{}.xlsx".format(workbook_name), s)

        zipfile.close()

        self.data = buffer.getvalue()

        _user = user.objects.get(idx=self.general_settings["user_idx"])
        self.report_history.created_by_user = _user
        self.report_history.created_at_time = timezone.make_aware(self.creation_date, timezone.get_current_timezone())
        self.report_history.number_of_pages = 0
        self.report_history.size = len(self.data)
        self.report_history.type = self.get_report_type()
        self.report_history.generate_filename()
        self.report_history.save()
        self.report_history.write_data(self.data)

        self.progress = -1

    def __generate_user_group_overview_report(self):
        workbook = Workbook()
        workbook.remove_sheet(workbook.active)

        sheet = workbook.create_sheet()
        sheet.title = "Network Overview"

        header_row = ["Login",
                      "UID",
                      "First Name",
                      "Last Name",
                      "Email",
                      "Groups",
                      "Permissions",
                      "Allowed Device Groups"
                      ]

        sheet.append(header_row)

        data = self._get_data_for_user_group_overview()

        for entry in data:
            row = [
                entry['login'],
                entry['uid'],
                entry['firstname'],
                entry['lastname'],
                entry['email'],
                entry['secondary_groups'],
                entry['permissions'],
                entry['allowed_device_groups']
            ]

            sheet.append(row)

        return workbook

    def __generate_device_overview(self, _device, workbook):
        sheet = workbook.create_sheet()

        _title = _device.full_name

        # xlsx limited to max 31 chars in title
        if len(_title) > 31:
            _title = _title[:31]

        sheet.title = _title

        header_row = ["FQDN",
                      "DeviceGroup",
                      "DeviceClass",
                      "ComCapabilities",
                      "IP Info",
                      "SNMP Scheme",
                      "SNMP Info",
                      "Device Categories"
                      ]

        sheet.append(header_row)

        data_rows = {}

        idx = 0
        if idx not in data_rows:
            data_rows[idx] = ['' for _ in range(len(header_row))]

        data_rows[idx][0] = _device.full_name
        data_rows[idx][1] = _device.device_group_name()
        data_rows[idx][2] = _device.device_class.name

        idx = 0
        for com_cap in _device.com_capability_list.all():
            if idx not in data_rows:
                data_rows[idx] = ['' for _ in range(len(header_row))]
            data_rows[idx][3] = com_cap.name
            idx += 1

        idx = 0
        for _ip in _device.all_ips():
            if idx not in data_rows:
                data_rows[idx] = ['' for _ in range(len(header_row))]
            data_rows[idx][4] = str(_ip)
            idx += 1

        idx = 0
        for _snmp_scheme in _device.snmp_schemes.all():
            if idx not in data_rows:
                data_rows[idx] = ['' for _ in range(len(header_row))]
            data_rows[idx][5] = str(_snmp_scheme)
            idx += 1

        idx = 0
        for _snmp_scheme in _device.snmp_schemes.all():
            if idx not in data_rows:
                data_rows[idx] = ['' for _ in range(len(header_row))]
            data_rows[idx][7] = str(_snmp_scheme)
            idx += 1

        for i in range(len(data_rows)):
            sheet.append(data_rows[i])

    def __generate_network_report(self):
        from initat.cluster.backbone.models import network

        workbook = Workbook()
        workbook.remove_sheet(workbook.active)

        networks = network.objects.all()

        if networks:
            sheet = workbook.create_sheet()
            sheet.title = "Network Overview"

            header_row = ["Identifier",
                          "Network",
                          "Netmask",
                          "Broadcast",
                          "Gateway",
                          "GW Priority",
                          "#IPs",
                          "Network Type"]


            sheet.append(header_row)

            for _network in networks:
                row = [
                    _network.identifier,
                    _network.network,
                    _network.netmask,
                    _network.broadcast,
                    _network.gateway,
                    _network.gw_pri,
                    _network.num_ip(),
                    _network.network_type.description
                ]

                sheet.append(row)

        return workbook

    def __generate_general_device_overview_report(self):
        workbook = Workbook()


        data = _generate_hardware_info_data_dict(self.devices, self.general_settings["assetbatch_selection_mode"])

        if data:
            workbook.remove_sheet(workbook.active)

            sheet = workbook.create_sheet("General Device Overview")
            sheet.title = "General Device Overview"

            header_row = ["Name", "Group", "CPU Info", "GPU Info", "Memory Info", "HDD Info", "Partition Info"]

            sheet.append(header_row)

            for _row in data:
                row = [
                    _row['name'],
                    _row['group'],
                    _row['cpu'],
                    _row['gpu'],
                    _row['memory'],
                    _row['hdd'],
                    _row['partition']
                ]

                sheet.append(row)


        return workbook

########################################################################################################################
# Views
########################################################################################################################
REPORT_GENERATORS = {}
REPORT_TIMEOUT_SECONDS = 1800


class GetProgress(View):
    @method_decorator(login_required)
    def post(self, request):
        report_generator_id = int(request.POST["id"])

        progress = 0
        if report_generator_id in REPORT_GENERATORS:
            report_generator = REPORT_GENERATORS[report_generator_id]
            progress = report_generator.progress

            report_generator.last_poll_time = datetime.datetime.now()

        return HttpResponse(
            json.dumps(
                {
                    'progress': progress
                }
            )
        )


class GetReportData(View):
    @method_decorator(login_required)
    def post(self, request):
        data_b64 = ""
        report_type = "unknown"
        report_id = None

        if "report_generator_id" in request.POST:
            report_generator_id = int(request.POST["report_generator_id"])
            report_data = ""

            if report_generator_id in REPORT_GENERATORS:
                report_generator = REPORT_GENERATORS[report_generator_id]
                report_data = report_generator.get_report_data()
                report_type = report_generator.get_report_type()
                report_id = report_generator.report_id
                del REPORT_GENERATORS[report_generator_id]

            data_b64 = base64.b64encode(report_data)
        elif "report_id" in request.POST:
            report_id = int(request.POST["report_id"])

            report_history = ReportHistory.objects.get(idx=report_id)
            report_type = report_history.type
            data = report_history.get_data()
            data_b64 = base64.b64encode(data)

        return HttpResponse(
            json.dumps(
                {
                    report_type: data_b64,
                    "report_id": report_id
                }
            )
        )

    @method_decorator(login_required)
    def get(self, request):
        report_id = int(request.GET["report_id"])

        report_history = ReportHistory.objects.get(idx=report_id)
        report_type = report_history.type
        data = report_history.get_data()
        data_b64 = base64.b64encode(data)


        return HttpResponse(
            json.dumps(
                {
                    report_type: data_b64,
                }
            )
        )


class GenerateReportPdf(View):
    @method_decorator(login_required)
    def post(self, request):
        pk_settings, _devices, current_time = _init_report_settings(request)

        if 'HOSTNAME' in request.META:
            pk_settings[-1]['hostname'] = request.META['HOSTNAME']
        else:
            pk_settings[-1]['hostname'] = "unknown"


        pdf_report_generator = PDFReportGenerator(pk_settings, _devices)
        pdf_report_generator.timestamp = current_time
        REPORT_GENERATORS[id(pdf_report_generator)] = pdf_report_generator

        Thread(target=_generate_report, args=[pdf_report_generator]).start()

        return HttpResponse(
            json.dumps(
                {
                    'id': id(pdf_report_generator)
                }
            )
        )


class UploadReportGfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _file = request.FILES[request.FILES.keys()[0]]
        if _file.content_type in ["image/png", "image/jpeg"]:
            system_device = None
            for _device in device.objects.all():
                if _device.is_cluster_device_group():
                    system_device = _device
                    break

            if system_device:
                report_logo_tmp = system_device.device_variable_set.filter(name="__REPORT_LOGO__")
                if report_logo_tmp:
                    report_logo_tmp = report_logo_tmp[0]

                else:
                    report_logo_tmp = device_variable.objects.create(device=system_device, is_public=False,
                                                                     name="__REPORT_LOGO__",
                                                                     inherit=False,
                                                                     protected=True,
                                                                     var_type="b")
                report_logo_tmp.val_blob = base64.b64encode(_file.read())
                report_logo_tmp.save()


class GetReportGfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        val_blob = ""
        system_device = None
        for _device in device.objects.all():
            if _device.is_cluster_device_group():
                system_device = _device
                break

        if system_device:
            report_logo_tmp = system_device.device_variable_set.filter(name="__REPORT_LOGO__")

            if report_logo_tmp:
                val_blob = report_logo_tmp[0].val_blob

        return HttpResponse(
            json.dumps(
                {
                    'gfx': val_blob
                }
            )
        )


class GenerateReportXlsx(View):
    @method_decorator(login_required)
    def post(self, request):
        pk_settings, _devices, current_time = _init_report_settings(request)

        xlsx_report_generator = XlsxReportGenerator(pk_settings, _devices)
        xlsx_report_generator.timestamp = current_time
        REPORT_GENERATORS[id(xlsx_report_generator)] = xlsx_report_generator

        Thread(target=_generate_report, args=[xlsx_report_generator]).start()

        return HttpResponse(
            json.dumps(
                {
                    'id': id(xlsx_report_generator)
                }
            )
        )


class ReportDataAvailable(View):
    @method_decorator(login_required)
    def post(self, request):
        idx_list = None
        for item in request.POST.iterlists():
            key, _list = item
            if key == "idx_list[]":
                idx_list = _list
                break

        assetbatch_selection_mode = int(request.POST['assetbatch_selection_mode'])

        pk_setting_dict = {}

        meta_devices = []

        group_selected_runs = {}


        for idx in idx_list:
            idx = int(idx)
            _device = device.objects.get(idx=idx)

            if _device.is_meta_device:
                meta_devices.append(_device)
                continue

            selected_runs = _select_assetruns_for_device(_device, assetbatch_selection_mode)
            selected_run_info_array = [(ar.run_type, str(ar.run_start_time), ar.asset_batch.idx)  for ar in selected_runs]

            if _device.device_group_name() not in group_selected_runs:
                group_selected_runs[_device.device_group_name()] = []

            for run_type in [ar.run_type for ar in selected_runs]:
                if run_type not in group_selected_runs[_device.device_group_name()]:
                    group_selected_runs[_device.device_group_name()].append(run_type)

            pk_setting_dict[idx] = selected_run_info_array

        for _device in meta_devices:
            if _device.device_group_name() in group_selected_runs:
                pk_setting_dict[_device.idx] = group_selected_runs[_device.device_group_name()]

        return HttpResponse(
            json.dumps(
                {
                    'pk_setting_dict': pk_setting_dict,
                }
            )
        )

class ReportHistoryAvailable(View):
    @method_decorator(login_required)
    def post(self, request):
        data = {}
        report_ids = []

        for report_history in ReportHistory.objects.all():
            if not report_history.created_by_user:
                continue
            if not report_history.created_at_time:
                continue

            o = {
                'report_id': str(report_history.idx),
                'created_by_user': str(report_history.created_by_user),
                'created_at_time': str(report_history.created_at_time),
                'number_of_pages': str(report_history.number_of_pages),
                'size': sizeof_fmt(report_history.size),
                'raw_size': report_history.b64_size,
                'type': str(report_history.type),
                'number_of_downloads': str(report_history.number_of_downloads)
            }

            report_ids.append(report_history.idx)
            data[report_history.idx] = o

        return HttpResponse(
            json.dumps(
                {
                    'report_ids': list(reversed(sorted(report_ids))),
                    'report_history': data
                }
            )
        )

class UpdateDownloadCount(View):
    @method_decorator(login_required)
    def post(self, request):
        idx = int(request.POST["idx"])

        report_history = ReportHistory.objects.get(idx=idx)

        report_history.number_of_downloads += 1
        report_history.save()

        return HttpResponse(
            json.dumps(
                {
                    'download_count': report_history.number_of_downloads
                }
            )
        )


########################################################################################################################
# Helper Functions
########################################################################################################################

def _init_report_settings(request):
    current_time = datetime.datetime.now()
    # remove references of old report generators
    for report_generator_id in REPORT_GENERATORS.keys():
        if (current_time - REPORT_GENERATORS[report_generator_id].timestamp).seconds > REPORT_TIMEOUT_SECONDS:
            del REPORT_GENERATORS[report_generator_id]

    settings_dict = {}

    for key in request.POST.iterkeys():
        valuelist = request.POST.getlist(key)
        # look for pk in key

        index = key.split("[")[1][:-1]
        if index not in settings_dict:
            settings_dict[index] = {}

        if key[::-1][:4] == ']kp[':
            settings_dict[index]["pk"] = int(valuelist[0])
        else:
            if valuelist[0] == "true":
                value = True
            elif valuelist[0] == "false":
                value = False
            else:
                value = valuelist[0]

            settings_dict[index][key.split("[")[-1][:-1]] = value

    pk_settings = {}

    for setting_index in settings_dict:
        pk = settings_dict[setting_index]['pk']
        pk_settings[pk] = {}

        for key in settings_dict[setting_index]:
            if key != 'pk':
                pk_settings[pk][key] = settings_dict[setting_index][key]

    _devices = []
    for _device in device.objects.filter(idx__in=[int(pk) for pk in pk_settings.keys()]):
        if not _device.is_meta_device:
            _devices.append(_device)

    return pk_settings, _devices, current_time


# asset_batch_selection_mode
# 0 == latest only, 1 == latest fully working, 2 == mixed runs from multiple assetbatches
def _select_assetruns_for_device(_device, asset_batch_selection_mode=0):
    selected_asset_runs = []

    asset_batch_selection_mode = int(asset_batch_selection_mode)
    assert (asset_batch_selection_mode <= 2 and asset_batch_selection_mode >= -1)

    # search latest assetbatch and generate
    if _device.assetbatch_set.all():
        for assetbatch in reversed(sorted(_device.assetbatch_set.all(), key=lambda ab: ab.idx)):
            if asset_batch_selection_mode == 0:
                for assetrun in assetbatch.assetrun_set.all():
                    if assetrun.has_data():
                        selected_asset_runs.append(assetrun)
                break
            elif asset_batch_selection_mode == 1:
                if assetbatch.num_runs == assetbatch.num_completed and assetbatch.num_runs_error == 0:
                    selected_asset_runs = assetbatch.assetrun_set.all()
            elif asset_batch_selection_mode == 2:
                for assetrun in assetbatch.assetrun_set.all():
                    if assetrun.has_data():
                        if AssetType(assetrun.run_type) not in [AssetType(ar.run_type) for ar in selected_asset_runs]:
                            selected_asset_runs.append(assetrun)

    sorted_runs = {}

    for ar in selected_asset_runs:
        if AssetType(ar.run_type) == AssetType.PACKAGE:
            sorted_runs[0] = ar
        elif AssetType(ar.run_type) == AssetType.LICENSE:
            sorted_runs[1] = ar
        elif AssetType(ar.run_type) == AssetType.UPDATE:
            sorted_runs[2] = ar
        elif AssetType(ar.run_type) == AssetType.PENDING_UPDATE:
            sorted_runs[3] = ar
        elif AssetType(ar.run_type) == AssetType.PROCESS:
            # disabled for now
            pass
            #sorted_runs[4] = ar
        elif AssetType(ar.run_type) == AssetType.PRETTYWINHW:
            sorted_runs[5] = ar
        elif AssetType(ar.run_type) == AssetType.DMI:
            sorted_runs[6] = ar
        elif AssetType(ar.run_type) == AssetType.PCI:
            sorted_runs[7] = ar
        elif AssetType(ar.run_type) == AssetType.HARDWARE:
            # disabled for now
            pass
            #sorted_runs[8] = ar

    return [sorted_runs[idx] for idx in sorted_runs]


def generate_csv_entry_for_assetrun(ar, row_writer_func):
    base_header = [
        'Asset Type',
        'Batch Id',
        'Start Time',
        'End Time',
        'Total Run Time',
        'device',
        'status',
        'result'
    ]

    if ar.run_start_time and ar.run_end_time:
        ar_run_time = str((ar.run_end_time - ar.run_start_time).total_seconds())
    else:
        ar_run_time = "N/A"

    base_row = [AssetType(ar.run_type).name,
                str(ar.asset_batch.idx),
                str(ar.run_start_time),
                str(ar.run_end_time),
                ar_run_time,
                str(ar.device.full_name),
                RunStatus(ar.run_status).name,
                RunResult(ar.run_result).name]

    if ar.run_type == AssetType.PACKAGE:
        base_header.extend([
            'package_name',
            'package_version',
            'package_release',
            'package_size',
            'package_install_date',
            'package_type'])

        row_writer_func(base_header)

        for package_version in ar.packages.select_related("asset_package").all():
            row = base_row[:]

            row.append(package_version.asset_package.name)
            row.append(package_version.version)
            row.append(package_version.release)
            row.append(package_version.size)
            row.append(package_version.created)
            row.append(PackageTypeEnum(package_version.asset_package.package_type).name)

            row_writer_func(row)

    elif ar.run_type == AssetType.HARDWARE:
        base_header.extend([
            'hardware_node_type',
            'hardware_depth',
            'hardware_attributes',
            'hardware_info'])

        row_writer_func(base_header)

        for hardware_item in ar.assethardwareentry_set.all():
            row = base_row[:]

            row.append(hardware_item.type)
            row.append(hardware_item.depth)
            row.append(hardware_item.attributes)
            row.append(hardware_item.info_list)

            row_writer_func(row)

    elif ar.run_type == AssetType.LICENSE:
        base_header.extend(
            [
                'license_name',
                'license_key'
            ]
        )

        row_writer_func(base_header)

        for _license in ar.assetlicenseentry_set.all():
            row = base_row[:]

            row.append(_license.name)
            row.append(_license.license_key)

            row_writer_func(row)

    elif ar.run_type == AssetType.UPDATE:
        base_header.extend([
            'update_name',
            'update_version',
            'update_release',
            'update_kb_idx',
            'update_install_date',
            'update_status',
            'update_optional',
            'update_installed'
        ])

        row_writer_func(base_header)

        for update in ar.assetupdateentry_set.all():
            row = base_row[:]

            row.append(update.name)
            row.append(update.version)
            row.append(update.release)
            row.append(update.kb_idx)
            row.append(update.install_date)
            row.append(update.status)
            row.append(update.optional)
            row.append(update.installed)

            row_writer_func(row)

    elif ar.run_type == AssetType.PROCESS:
        base_header.extend([
            'process_name',
            'process_id'
        ])

        row_writer_func(base_header)

        for process in ar.assetprocessentry_set.all():
            row = base_row[:]

            row.append(str(process.name))
            row.append(str(process.pid))

            row_writer_func(row)

    elif ar.run_type == AssetType.PENDING_UPDATE:
        base_header.extend([
            'update_name',
            'update_version',
            'update_release',
            'update_kb_idx',
            'update_install_date',
            'update_status',
            'update_optional',
            'update_installed',
            'update_new_version'
        ])

        row_writer_func(base_header)

        for update in ar.assetupdateentry_set.all():
            row = base_row[:]

            row.append(update.name)
            row.append(update.version)
            row.append(update.release)
            row.append(update.kb_idx)
            row.append(update.install_date)
            row.append(update.status)
            row.append(update.optional)
            row.append(update.installed)
            row.append(update.new_version)

            row_writer_func(row)

    elif ar.run_type == AssetType.PCI:
        base_header.extend([
            'domain',
            'bus',
            'slot',
            'func',
            'position',
            'subclass',
            'vendor',
            'device',
            'revision'
        ])

        row_writer_func(base_header)

        for pci_entry in ar.assetpcientry_set.all():
            row = base_row[:]

            # row.append(str(pci_entry))
            row.append(str(pci_entry.domain))
            row.append(str(pci_entry.bus))
            row.append(str(pci_entry.slot))
            row.append(str(pci_entry.func))
            row.append("{:04x}:{:02x}:{:02x}.{:x}".format(pci_entry.domain, pci_entry.bus,
                                                          pci_entry.slot, pci_entry.func))
            row.append(str(pci_entry.subclassname))
            row.append(str(pci_entry.vendorname))
            row.append(str(pci_entry.devicename))
            row.append(str(pci_entry.revision))

            row_writer_func(row)

    elif ar.run_type == AssetType.DMI:
        base_header.extend([
            'handle',
            'dmi_type',
            'header',
            'key',
            'value'
        ])

        row_writer_func(base_header)

        for dmi_head in ar.assetdmihead_set.all():
            for dmi_handle in dmi_head.assetdmihandle_set.all():
                handle = dmi_handle.handle
                dmi_type = dmi_handle.dmi_type
                header = dmi_handle.header

                for dmi_value in dmi_handle.assetdmivalue_set.all():
                    key = dmi_value.key
                    value = dmi_value.value

                    row = base_row[:]

                    row.append(handle)
                    row.append(dmi_type)
                    row.append(header)
                    row.append(key)
                    row.append(value)

                    row_writer_func(row)

    elif ar.run_type == AssetType.PRETTYWINHW:
        base_header.extend([
            'entry'
        ])

        row_writer_func(base_header)

        for cpu in ar.cpus.all():
            row = base_row[:]

            row.append(str(cpu))

            row_writer_func(row)

        for memorymodule in ar.memory_modules.all():
            row = base_row[:]

            row.append(str(memorymodule))

            row_writer_func(row)

        for gpu in ar.gpus.all():
            row = base_row[:]

            row.append(str(gpu))

            row_writer_func(row)

        for hdd in ar.hdds.all():
            row = base_row[:]

            row.append(str(hdd))

            row_writer_func(row)

        for partition in ar.partitions.all():
            row = base_row[:]

            row.append(str(partition))

            row_writer_func(row)

        for display in ar.displays.all():
            row = base_row[:]

            row.append(str(display))

            row_writer_func(row)


def sizeof_fmt(num, suffix='B'):
    if num is None:
        return "N/A"
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def _generate_report(report_generator):
    try:
        report_generator.generate_report()
    except Exception as e:
        import traceback, sys
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        print '-'*60
        logger.info("Report Generation failed, error was: {}".format(str(e)))
        report_generator.data = ""
        report_generator.progress = -1


def _generate_hardware_info_data_dict(_devices, assetbatch_selection_mode):
    data = []

    for _device in _devices:
        selected_runs = _select_assetruns_for_device(_device, assetbatch_selection_mode)

        cpu_str = "N/A"
        gpu_str = "N/A"
        hdd_str = "N/A"
        partition_str = "N/A"
        memory_str = "N/A"

        for assetrun in selected_runs:
            if AssetType(assetrun.run_type) == AssetType.PRETTYWINHW:
                for cpu in assetrun.cpus.all():
                    if cpu_str != "N/A":
                        cpu_str += "\n{}".format(str(cpu))
                    else:
                        cpu_str = str(cpu)

                for gpu in assetrun.gpus.all():
                    if gpu_str != "N/A":
                        gpu_str += "\n{}".format(str(gpu))
                    else:
                        gpu_str = str(gpu)

                for hdd in assetrun.hdds.all():
                    if hdd_str != "N/A":
                        hdd_str += "\n{}".format(str(hdd))
                    else:
                        hdd_str = str(hdd)

                for partition in assetrun.partitions.all():
                    if partition_str != "N/A":
                        partition_str += "\n{}".format(str(partition))
                    else:
                        partition_str = str(partition)

                for memory_module in assetrun.memory_modules.all():
                    if memory_str != "N/A":
                        memory_str += "\n{}".format(str(memory_module))
                    else:
                        memory_str = str(memory_module)

        o = {
            'name': _device.full_name,
            'group': _device.device_group_name(),
            'cpu': cpu_str,
            'gpu': gpu_str,
            'hdd': hdd_str,
            'partition': partition_str,
            'memory': memory_str
        }

        data.append(o)

    return data