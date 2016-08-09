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

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from threading import Thread
from PIL import Image as PILImage
from io import BytesIO

from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, Paragraph, Image
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet

from PollyReports import Element, Rule, Band
from PollyReports import Image as PollyReportsImage
from PollyReports import Report as PollyReportsReport

from PyPDF2 import PdfFileWriter, PdfFileReader

from initat.cluster.backbone.models import device, device_variable, AssetType, PackageTypeEnum, RunStatus, RunResult
from initat.cluster.frontend.helper_functions import xml_wrapper


logger = logging.getLogger(__name__)


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
            install_date = str(_row[12])
            update_status = str(_row[13])

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

class PDFReportGenerator(object):
    class Bookmark(object):
        def __init__(self, name, pagenum):
            self.name = name
            self.pagenum = pagenum

    def __init__(self):
        system_device = None
        for _device in device.objects.all():
            if _device.is_cluster_device_group():
                system_device = _device
                break

        report_logo = system_device.device_variable_set.filter(name="__REPORT_LOGO__")

        self.last_poll_time = None
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

        self.reports = []
        self.device_reports = []
        self.progress = 0
        self.buffer = None

    def get_report_data(self):
        if self.buffer:
            return self.buffer.getvalue()
        return ""

    def get_report_type(self):
        return "pdf"

    def __get_logo_helper(self, value):
        _tmp_file = tempfile.NamedTemporaryFile()
        self.logo_buffer.seek(0)
        _tmp_file.write(self.logo_buffer.read())
        logo = ImageReader(_tmp_file.name)
        _tmp_file.close()

        return logo

    def __config_report_helper(self, header, header_names_list, rpt, data):
        header_list = [PollyReportsImage(pos=(570, -25),
                                         width=self.logo_width,
                                         height=self.logo_height,
                                         getvalue=self.__get_logo_helper),
                       Element((0, 0), ("Times-Bold", 20), text=header)]

        detail_list = []

        # letter size
        available_width = 72 * 9

        position = 0

        for header_name, key, avail_width_percentage in header_names_list:
            header_list.append(Element((position, 24), ("Helvetica", 12), text=header_name))
            detail_list.append(Element((position, 0), ("Helvetica", 6), key=key))

            position += available_width * (avail_width_percentage / 100.0) + 10

            for _dict in data:
                s = str(_dict[key])
                s_new = ""

                wrap_idx = 0

                for i in range(len(s)):
                    width = stringWidth(s[wrap_idx:i+1], "Helvetica", 6)
                    if ((width / available_width) * 100.0) > avail_width_percentage:
                        wrap_idx = i
                        s_new += "\n"
                    s_new += s[i]
                _dict[key] = s_new

        header_list.append(Rule((0, 42), 7.5 * 90, thickness=2))
        detail_list.append(Rule((0, 0), 7.5 * 90, thickness=0.1))

        rpt.pageheader = Band(header_list)
        rpt.detailband = Band(detail_list)

    def generate_network_report(self):
        from initat.cluster.backbone.models import network

        report = GenericReport()

        _buffer = BytesIO()
        # (72 * 11, 72 * 8.5) --> letter size
        canvas = Canvas(_buffer, (72 * 11, 72 * 8.5))

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
            report.generate_bookmark("Networks")

            rpt = PollyReportsReport(data)
            rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
                                              getvalue=lambda x: x['id'][0],
                                              format=lambda x: "Networks starting with: {}".format(x)), ],
                                     getvalue=lambda x: x["id"][0])]

            header_names = [("Identifier", "id", 10.0),
                            ("Network", "network", 10.0),
                            ("Netmask", "netmask", 10.0),
                            ("Broadcast", "broadcast", 10.0),
                            ("Gateway", "gateway", 10.0),
                            ('GW Priority', "gwprio", 10.0),
                            ("#IPs", "num_ips", 10.0),
                            ("Network Type", "network_type", 20.0)]

            self.__config_report_helper("Network Overview", header_names, rpt, data)

            rpt.generate(canvas)
            canvas.save()
            report.number_of_pages += rpt.pagenumber
            report.add_to_report(_buffer)
            self.reports.append(report)

    def generate_device_report(self, _device, report_settings):
        report = DeviceReport(_device, report_settings)
        self.device_reports.append(report)

        # create generic overview page
        self.generate_overview_page(report)

        # search latest assetbatch and generate
        if _device.assetbatch_set.all():
            asset_batch = sorted(_device.assetbatch_set.all(), key=lambda ab: ab.idx)[-1]
            self.generate_report_for_asset_batch(asset_batch, report)

    def generate_overview_page(self, report):
        _device = report.device

        report.generate_bookmark("Overview")

        _buffer = BytesIO()
        doc = SimpleDocTemplate(_buffer, pagesize=landscape(letter), rightMargin=25, leftMargin=25, topMargin=0,
                                bottomMargin=25)
        doc.pagesize = landscape(letter)
        elements = []

        style_sheet = getSampleStyleSheet()

        paragraph_header = Paragraph('<font face="times-bold" size="22">Overview for {}</font>'.format(
            _device.name), style_sheet["BodyText"])

        logo = Image(self.logo_buffer)
        logo.drawHeight = self.logo_height
        logo.drawWidth = self.logo_width

        data = [[paragraph_header, logo]]

        t_head = Table(data, colWidths=(570, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        body_data = []

        # FQDN
        data = [[_device.full_name]]

        text_block = Paragraph('<b>FQDN:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )
        body_data.append((text_block, t))

        # Device Groups
        data = [[_device.device_group_name()]]

        text_block = Paragraph('<b>DeviceGroup:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # Device Class
        data = [[_device.device_class.name]]

        text_block = Paragraph('<b>DeviceGroup:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # ComCapabilites

        str_to_use = ""

        for com_cap in _device.com_capability_list.all():
            if not str_to_use:
                str_to_use = com_cap.name
            else:
                str_to_use += ", {}".format(com_cap.name)
        data = [[str_to_use]]

        text_block = Paragraph('<b>ComCapabilities:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # Ip info
        str_to_use = ""
        for _ip in _device.all_ips():
            if not str_to_use:
                str_to_use = str(_ip)
            else:
                str_to_use += ", {}".format(str(_ip))
        data = [[str_to_use]]

        text_block = Paragraph('<b>IP Info:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # SNMP Schemes
        str_to_use = ""
        for _snmp_scheme in _device.snmp_schemes.all():
            if not str_to_use:
                str_to_use = str(_snmp_scheme)
            else:
                str_to_use += ", {}".format(str(_snmp_scheme))
        data = [[str_to_use]]

        text_block = Paragraph('<b>SNMP Scheme:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # SNMP Info
        str_to_use = ""
        data = [[str_to_use]]

        text_block = Paragraph('<b>SNMP Info:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        # Device Categories
        str_to_use = ""
        for _category in _device.categories.all():
            if not str_to_use:
                str_to_use = _category.name
            else:
                str_to_use += ", {}".format(_category.name)
        data = [[str_to_use]]

        text_block = Paragraph('<b>Categories:</b>', style_sheet["BodyText"])
        t = Table(data, colWidths=(200 * mm),
                  style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                         ('BOX', (0, 0), (-1, -1), 2, colors.black),
                         ]
                  )

        body_data.append((text_block, t))

        t_body = Table(body_data, colWidths=(100, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        elements.append(t_head)
        elements.append(Spacer(1, 30))
        elements.append(t_body)

        try:
            doc.build(elements, onFirstPage=report.increase_page_count, onLaterPages=report.increase_page_count)
            report.add_to_report(_buffer)
        except Exception as e:
            import traceback, sys
            print '-' * 60
            traceback.print_exc(file=sys.stdout)
            print '-' * 60

    def generate_report_for_asset_batch(self, asset_batch, report):
        _buffer = BytesIO()

        # (72 * 11, 72 * 8.5) --> letter size
        canvas = Canvas(_buffer, (72 * 11, 72 * 8.5))

        assetruns = asset_batch.assetrun_set.all()
        row_collector = RowCollector()

        # Hardware report is generated last
        hardware_report_ar = None

        for ar in sorted(assetruns, key=lambda _ar: _ar.run_type):
            row_collector.reset()
            row_collector.current_asset_type = AssetType(ar.run_type)
            generate_csv_entry_for_assetrun(ar, row_collector.collect)

            if AssetType(ar.run_type) == AssetType.UPDATE:
                if not report.report_settings['installed_updates_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['update_status'])

                report.generate_bookmark("Installed Updates")

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
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

                header_names = [("Update Name", "update_name", 70.0),
                                ("Install Date", "install_date", 15.0),
                                ("Install Status", "update_status", 15.0)]

                self.__config_report_helper("Installed Updates", header_names, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.LICENSE:
                if not report.report_settings['licenses_selected']:
                    continue

                data = row_collector.rows_dict[1:]

                report.generate_bookmark("Available Licenses")

                rpt = PollyReportsReport(data)

                if not data:
                    mock_object = {
                        "license_name": "",
                        "license_key": ""
                    }
                    data.append(mock_object)

                header_names = [("License Name", "license_name", 50.0),
                                ("License Key", "license_key", 50.0)]

                self.__config_report_helper("Available Licenses", header_names, rpt, data)

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

                report.generate_bookmark("Installed Packages")

                data = [package.get_as_row() for package in packages]
                data = sorted(data, key=lambda k: k['package_name'])

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
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

                header_names = [("Name", "package_name", 20.0),
                                ("Version", "package_version", 20.0),
                                ("Release", "package_release", 20.0),
                                ("Size", "package_size", 20.0),
                                ("Install Date", "package_install_date", 20.0)]

                self.__config_report_helper("Installed Packages", header_names, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PENDING_UPDATE:
                if not report.report_settings['avail_updates_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['update_name'])

                report.generate_bookmark("Available Updates")

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
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

                header_names = [("Update Name", "update_name", 33.33),
                                ("Version", "update_version", 33.33),
                                ("Optional", "update_optional", 33.33)]

                self.__config_report_helper("Available Updates", header_names, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.HARDWARE:
                if not report.report_settings['lstopo_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['hardware_depth'])

                report.generate_bookmark("Lstopo Information")

                rpt = PollyReportsReport(data)

                if not data:
                    mock_object = {
                        "hardware_node_type": "",
                        "hardware_depth": "",
                        "hardware_attributes": "",
                    }
                    data.append(mock_object)

                header_names = [("Node Type", "hardware_node_type", 15.00),
                                ("Depth", "hardware_depth", 15.00),
                                ("Attributes", "hardware_attributes", 70.00)]

                self.__config_report_helper("Lstopo Information", header_names, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PROCESS:
                if not report.report_settings['process_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['process_name'])

                report.generate_bookmark("Process Information")

                rpt = PollyReportsReport(data)

                if data:
                    rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
                                                      getvalue=lambda x: x['process_name'][0],
                                                      format=lambda x: "Updates starting with: {}".format(x)), ],
                                             getvalue=lambda x: x["process_name"][0]), ]
                else:
                    mock_object = {
                        "process_name": "",
                        "process_id": "",
                    }
                    data.append(mock_object)

                header_names = [("Process Name", "process_name", 50.0),
                                ("PID", "process_id", 50.0)]

                self.__config_report_helper("Process Information", header_names, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.DMI:
                if not report.report_settings['dmi_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]

                report.generate_bookmark("DMI Information")

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

                header_names = [("Handle", "handle", 20.0),
                                ("Type", "dmi_type", 20.0),
                                ("Header", "header", 20.0),
                                ("Key", "key", 20.0),
                                ("Value", "value", 20.0)]

                self.__config_report_helper("DMI Information", header_names, rpt, data)

                rpt.generate(canvas)
                report.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PCI:
                if not report.report_settings['pci_report_selected']:
                    continue

                data = row_collector.rows_dict[1:]

                report.generate_bookmark("PCI Information")

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

                header_names = [("Domain", "domain", 10.0),
                                ("Bus", "bus", 10.0),
                                ("Slot", "slot", 10.0),
                                ("Func", "func", 10.0),
                                ("Position", "position", 10.0),
                                ("Subclass", "subclass", 10.0),
                                ("Vendor", "vendor", 10.0),
                                ("Device", "device", 20.0)]

                self.__config_report_helper("PCI Information", header_names, rpt, data)

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
        # from reportlab.pdfbase import pdfmetrics
        # from reportlab.pdfbase.ttfonts import TTFont
        #
        # pdfmetrics.registerFont(TTFont('Forque', '/home/kaufmann/Forque.ttf'))

        report.generate_bookmark("Hardware Report")

        _buffer = BytesIO()
        doc = SimpleDocTemplate(_buffer, pagesize=landscape(letter), rightMargin=25, leftMargin=25, topMargin=00,
                                bottomMargin=25)
        doc.pagesize = landscape(letter)
        elements = []

        style_sheet = getSampleStyleSheet()

        data = [["Name", "Cores"]]
        for cpu in hardware_report_ar.cpus.all():
            data.append([Paragraph(str(cpu.cpuname), style_sheet["BodyText"]),
                         Paragraph(str(cpu.numberofcores), style_sheet["BodyText"])])

        p0_1 = Paragraph('<b>CPUs:</b>', style_sheet["BodyText"])

        t_1 = Table(data,
                    colWidths=(100 * mm, 100 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black)])

        data = [["Name", "Driver Version"]]
        for gpu in hardware_report_ar.gpus.all():
            data.append([Paragraph(str(gpu.gpuname), style_sheet["BodyText"]),
                         Paragraph(str(gpu.driverversion), style_sheet["BodyText"])])

        p0_2 = Paragraph('<b>GPUs:</b>', style_sheet["BodyText"])
        t_2 = Table(data,
                    colWidths=(100 * mm, 100 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [["Name", "Serialnumber", "Size"]]
        for hdd in hardware_report_ar.hdds.all():
            data.append([Paragraph(str(hdd.name), style_sheet["BodyText"]),
                         Paragraph(str(hdd.serialnumber), style_sheet["BodyText"]),
                         Paragraph(sizeof_fmt(hdd.size), style_sheet["BodyText"])])

        p0_3 = Paragraph('<b>HDDs:</b>', style_sheet["BodyText"])
        t_3 = Table(data,
                    colWidths=(66 * mm, 67 * mm, 67 * mm),
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
                    colWidths=(50 * mm, 50 * mm, 50 * mm, 50 * mm),
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
                    colWidths=(40 * mm, 40 * mm, 40 * mm, 40 * mm, 40 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [[p0_1, t_1],
                [p0_2, t_2],
                [p0_3, t_3],
                [p0_4, t_4],
                [p0_5, t_5]]

        t_body = Table(data, colWidths=(100, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        p_h = Paragraph('<font face="times-bold" size="22">Hardware Report for {}</font>'.format(
            hardware_report_ar.device.name), style_sheet["BodyText"])

        logo = Image(self.logo_buffer)
        logo.drawHeight = self.logo_height
        logo.drawWidth = self.logo_width

        data = [[p_h, logo]]

        t_head = Table(data, colWidths=(570, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

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

        # 1. Pass: Generate pdf, structure is group_name -> device -> report,
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

                for _device in _device_reports:
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

        for i in reversed(range(toc_pdf.getNumPages())):
            output_pdf.insertPage(toc_pdf.getPage(i))

        # 2. Pass: Add page numbers
        output_pdf.write(output_buffer)
        output_pdf = self.__add_page_numbers(output_buffer, toc_pdf_page_num, page_num_prefix_dict)
        self.progress = 100

        # 3. Pass: Generate Bookmarks
        current_page_number = toc_pdf_page_num

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

                for _device in _device_reports:
                    device_bookmark = output_pdf.addBookmark(_device.full_name, current_page_number,
                                                             parent=group_bookmark)

                    for _report in _device_reports[_device]:
                        for _bookmark in _report.bookmarks:
                            output_pdf.addBookmark(_bookmark.name, current_page_number + _bookmark.pagenum,
                                                   parent=device_bookmark)
                        current_page_number += _report.number_of_pages

        output_buffer = BytesIO()
        output_pdf.write(output_buffer)
        self.buffer = output_buffer
        self.progress = -1

    def __get_toc_pages(self, page_num_headings):
        style_sheet = getSampleStyleSheet()

        paragraph_header = Paragraph('<font face="times-bold" size="22">Contents</font>', style_sheet["BodyText"])

        logo = Image(self.logo_buffer)
        logo.drawHeight = self.logo_height
        logo.drawWidth = self.logo_width

        data = [[paragraph_header, logo]]

        t_head = Table(data, colWidths=(570, None), style=[('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        _buffer = BytesIO()
        can = Canvas(_buffer, pagesize=landscape(letter))

        can.setFont("Helvetica", 14)

        width, heigth = landscape(letter)

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

                heading_str_width = stringWidth(heading_str, "Helvetica", 14)

                dots = "."
                while (25 * indent) + heading_str_width + stringWidth(dots, "Helvetica", 14) < (width - 150):
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
                        can.setFont("Helvetica", 14)
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
            # user closed the browser windows or switched to a different view
            if self.last_poll_time and (datetime.datetime.now() - self.last_poll_time).seconds > 5:
                break

            self.progress = int((page_number / float(num_pages)) * 90) + 10
            page = existing_pdf.getPage(page_number)

            if page_number >= toc_offset_num:
                page_num_buffer = BytesIO()
                can = Canvas(page_num_buffer, pagesize=landscape(letter))

                str_to_draw = "{}".format(page_number + 1)
                can.drawString(25, 25, str_to_draw)

                if (page_number - toc_offset_num) in page_num_prefix_dict:
                    str_to_draw = "({})".format(page_num_prefix_dict[page_number - toc_offset_num])

                    can.drawString(700, 25, str_to_draw)

                can.save()
                page_num_buffer.seek(0)
                page_num_pdf = PdfFileReader(page_num_buffer)
                page.mergePage(page_num_pdf.getPage(0))

            output.addPage(page)

        return output


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
        report_generator_id = int(request.POST["id"])

        report_data = ""
        report_type = "unknown"

        if report_generator_id in REPORT_GENERATORS:
            report_generator = REPORT_GENERATORS[report_generator_id]
            report_data = report_generator.get_report_data()
            report_type = report_generator.get_report_type()
            del REPORT_GENERATORS[report_generator_id]

        data_b64 = base64.b64encode(report_data)

        return HttpResponse(
            json.dumps(
                {
                    report_type: data_b64
                }
            )
        )

class GenerateReportPdf(View):
    @method_decorator(login_required)
    def post(self, request):
        pk_settings, _devices, current_time = _init_report_settings(request)

        pdf_report_generator = PDFReportGenerator()
        pdf_report_generator.timestamp = current_time
        REPORT_GENERATORS[id(pdf_report_generator)] = pdf_report_generator

        Thread(target=generate_pdf, args=(_devices, pk_settings, pdf_report_generator)).start()

        return HttpResponse(
            json.dumps(
                {
                    'id': id(pdf_report_generator)
                }
            )
        )

from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

class XlsxReportGenerator(object):
    def __init__(self, settings, _devices):
        self.data = ""
        self.settings = settings
        self.devices = _devices
        self.progress = 0

    def get_report_data(self):
        return self.data

    def get_report_type(self):
        return "xlsx"

    def generate_report(self):
        data_generated = False

        workbook = Workbook()
        workbook.remove_sheet(workbook.active)

        idx = 1
        for _device in self.devices:
            device_report = DeviceReport(_device, self.settings[_device.idx])
            if _device.assetbatch_set.all():
                asset_batch = sorted(_device.assetbatch_set.all(), key=lambda ab: ab.idx)[-1]
                asset_runs = asset_batch.assetrun_set.all()

                for ar in asset_runs:
                    if not device_report.module_selected(ar):
                        continue
                    sheet = workbook.create_sheet()
                    _title = _device.full_name + " " + AssetType(ar.run_type).name

                    # xlsx limited to max 31 chars in title
                    if len(_title) > 31:
                        _title = _title[:31]

                    sheet.title = _title

                    generate_csv_entry_for_assetrun(ar, sheet.append)
                    data_generated = True

            self.progress = int(round((float(idx) / len(self.devices)) * 100))
            idx += 1

        if data_generated:
            self.data = save_virtual_workbook(workbook)
        self.progress = -1

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

        meta_devices = []

        device_group_disabled = {}

        pk_setting_dict = {}
        if idx_list:
            for pk in idx_list:
                pk = int(pk)
                _device = device.objects.get(idx=pk)

                if _device.is_meta_device:
                    meta_devices.append(_device)
                    continue

                disabled = True
                if _device.assetbatch_set.all():
                    disabled = False

                pk_setting_dict[pk] = disabled

                if _device.device_group in device_group_disabled:
                    if device_group_disabled[_device.device_group]:
                        device_group_disabled[_device.device_group] = disabled
                else:
                    device_group_disabled[_device.device_group] = disabled

            for _device in meta_devices:
                if _device.device_group in device_group_disabled:
                    pk_setting_dict[_device.idx] = device_group_disabled[_device.device_group]
                else:
                    pk_setting_dict[_device.idx] = True

        return HttpResponse(
            json.dumps(
                {
                    'pk_setting_dict': pk_setting_dict,
                }
            )
        )


def generate_pdf(_devices, pk_settings, pdf_report_generator):
    # general report settings stored with pk -1
    general_settings = pk_settings[-1]

    try:
        if general_settings["network_report_overview_module_selected"]:
            pdf_report_generator.generate_network_report()

        idx = 1
        for _device in _devices:
            if pdf_report_generator.last_poll_time and \
                            (datetime.datetime.now() - pdf_report_generator.last_poll_time).seconds > 5:
                return
            pdf_report_generator.generate_device_report(_device, pk_settings[_device.idx])
            pdf_report_generator.progress = int((float(idx) / len(_devices)) * 10)
            idx += 1

        pdf_report_generator.progress = 10

        pdf_report_generator.finalize_pdf()
    except Exception as e:
        import traceback, sys
        print '-'*60
        traceback.print_exc(file=sys.stdout)
        print '-'*60
        logger.info("PDF Generation failed, error was: {}".format(str(e)))
        pdf_report_generator.buffer = BytesIO()
        pdf_report_generator.progress = -1

def _generate_report(report_generator):
    report_generator.generate_report()


def sizeof_fmt(num, suffix='B'):
    if num is None:
        return "N/A"
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


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
            value = True if valuelist[0] == "true" else False

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