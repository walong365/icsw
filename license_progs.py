#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005,2007,2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of init-license-tools
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
""" modify license settings """

from lxml import etree
import argparse
import logging_tools
import os
import process_tools
import sge_license_tools
import sys
import tempfile
import time


# dummy logger
def _log(what, level):
    print("[{:2d}] {}".format(level, what))


def _create_base_dir(opts):
    if not os.path.isdir(opts.base):
        try:
            os.makedirs(opts.base)
        except IOError:
            print("Error creating base_dir '{}': {}".format(opts.base, process_tools.get_except_info()))
            sys.exit(1)
        else:
            print("Successfully created base_dir '{}'".format(opts.base))


def _lic_show(opts, act_conf):
    elo = sge_license_tools.ExternalLicenses(opts.base, opts.site, log_com=_log)
    _xml = sge_license_tools.license_check(
        log_com=_log,
        lmutil_path=act_conf["LMUTIL_PATH"],
        license_file=act_conf["LICENSE_FILE"],
        verbose=False,
    ).check()
    elo.read()
    elo.feed_xml_result(_xml)
    out_list = logging_tools.new_form_list()
    for _t_type in ["simple", "complex"]:
        for _name in sorted(elo.licenses.keys()):
            _lic = elo.licenses[_name]
            print _lic, type(_lic), etree.tostring(_lic.get_xml())
            if _lic.license_type == _t_type:
                out_list.append(_lic.get_info_line())
    print unicode(out_list)


def _lic_fetch(opts, act_conf):
    # query license server and update licenses
    _cur_lic = sge_license_tools.license_check(
        log_com=_log,
        lmutil_path=act_conf["LMUTIL_PATH"],
        license_file=act_conf["LICENSE_FILE"],
        verbose=False,
    )
    _xml = _cur_lic.check()
    if int(_xml.attrib["state"]) > logging_tools.LOG_LEVEL_OK:
        print("error calling license server: {}".format(_xml.attrib["info"]))
    else:
        _srv_info = _xml.find(".//license_servers/server").attrib["info"]
        new_lics = {}
        for _lic in _xml.findall(".//license"):
            new_lic = sge_license_tools.sge_license(_lic, site=opts.site)
            new_lics[new_lic.name] = new_lic
        current_lics_file = sge_license_tools.text_file(
            sge_license_tools.get_site_license_file_name(opts.base, opts.site),
            ignore_missing=True,
            strip_empty=False,
            strip_hash=False,
        )
        current_lics = sge_license_tools.parse_license_lines(current_lics_file.lines, opts.site)
        print(
            "discovered {:d} licenses, {:d} of them are currently in use".format(
                len(current_lics),
                len([True for _lic in current_lics.itervalues() if _lic.is_used])
            )
        )
        for _al_key in sorted(set(new_lics) - set(current_lics)):
            _lic_to_add = new_lics[_al_key]
            _lic_to_add.added = time.ctime()
            print(
                "add new license {} ({}, {:d})".format(
                    _lic_to_add.name,
                    _lic_to_add.attribute,
                    _lic_to_add.total,
                )
            )
            current_lics[_al_key] = _lic_to_add
        for _cmp_key in sorted(set(new_lics) & set(current_lics)):
            current_lics[_cmp_key].update(new_lics[_cmp_key])
        current_lics_file.write(etree.tostring(sge_license_tools.build_license_xml(opts.site, current_lics), pretty_print=True))  # @UndefinedVariable


def _lic_addc(opts, act_conf):
    current_lics_file = sge_license_tools.text_file(
        sge_license_tools.get_site_license_file_name(opts.base, opts.site),
        ignore_missing=True,
        strip_empty=False,
        strip_hash=False,
    )
    current_lics = sge_license_tools.parse_license_lines(current_lics_file.lines, opts.site)
    if not opts.complex_name or opts.complex_name in current_lics:
        print "complex name '{}' empty or already used".format(opts.complex_name)
        sys.exit(1)
    new_lic = sge_license_tools.sge_license(
        opts.complex_name,
        license_type="complex",
        eval_str=opts.eval_str,
        site=opts.site,
        added=time.ctime()
    )
    current_lics[new_lic.name] = new_lic
    current_lics_file.write(etree.tostring(sge_license_tools.build_license_xml(opts.site, current_lics), pretty_print=True))  # @UndefinedVariable


def _lic_config(opts, act_conf):
    sge_dict = sge_license_tools.get_sge_environment()
    # complexes and complex names
    _sge_cxs, _sge_cns = sge_license_tools.get_sge_complexes(sge_dict)
    current_lics_file = sge_license_tools.text_file(
        sge_license_tools.get_site_license_file_name(opts.base, opts.site),
        ignore_missing=True,
        strip_empty=False,
        strip_hash=False,
    )
    current_lics = sge_license_tools.parse_license_lines(current_lics_file.lines, opts.site)
    sge_license_tools.handle_complex_licenses(current_lics)
    _lics_to_use = [_lic.name for _lic in current_lics.itervalues() if _lic.is_used]
    # modify complexes
    with tempfile.NamedTemporaryFile() as _tmpfile:
        form_str = "{} {} INT <= YES YES 0 0\n"
        changed = False
        for new_lic_name in _lics_to_use:
            if new_lic_name not in _sge_cns:
                changed = True
                _tmpfile.write(form_str.format(new_lic_name, new_lic_name))
        if changed:
            _tmpfile.write("\n".join(_sge_cxs) + "\n")
            # rewind
            _tmpfile.seek(0)
            sge_license_tools.call_command("{} -Mc {}".format(sge_dict["QCONF_BIN"], _tmpfile.name), 1, True)
    # modify global execution host
    # attribute string
    ac_str = ",".join(["{}={:d}".format(_lic_to_use, current_lics[_lic_to_use].total - current_lics[_lic_to_use].limit) for _lic_to_use in _lics_to_use])
    if ac_str:
        _mod_stat, _mod_out = sge_license_tools.call_command("{} -mattr exechost complex_values {} global".format(sge_dict["QCONF_BIN"], ac_str), 1, True)


def main():
    # read current sites (to determine default site)
    _act_site_file = sge_license_tools.text_file(
        os.path.join(sge_license_tools.BASE_DIR, sge_license_tools.ACT_SITE_NAME),
        ignore_missing=True,
        content=[sge_license_tools.DEFAULT_SITE],
    )
    _act_site = _act_site_file.lines
    if _act_site:
        _def_site = _act_site[0]
    else:
        _def_site = sge_license_tools.DEFAULT_SITE
        print("setting '{}' as default site".format(_def_site))
        _def_sites = [_def_site]
        _act_site_file.write(content=[_def_site])
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=str, default=sge_license_tools.BASE_DIR, help="set basedir [%(default)s]")
    parser.add_argument("--site", type=str, default=_def_site, help="select site [%(default)s], add if not already present")
    parser.add_argument("--set-as-default", default=False, action="store_true", help="set site as default site [%(default)s]")
    parser.add_argument("--create", default=False, action="store_true", help="create missing files [%(default)s]")
    _srv_group = parser.add_argument_group("server specs")
    _srv_group.add_argument("--port", default=0, type=int, help="license server port to use [%(default)s]")
    _srv_group.add_argument("--host", default="", type=str, help="license server to use [%(default)s]")
    parser.add_argument("--mode", default="show", choices=["config", "fetch", "addc", "show"], help="operation mode [%(default)s]")
    _cmp_group = parser.add_argument_group("complex handling")
    _cmp_group.add_argument("--complex-name", default="", type=str, help="name of new complex [%(default)s]")
    _cmp_group.add_argument("--eval-str", default="1", type=str, help="evaluation string for new complex [%(default)s]")
    _query_group = parser.add_argument_group("query options")
    _query_group.add_argument("--list-sites", default=False, action="store_true", help="list defined sites [%(default)s]")
    _query_group.add_argument("--show-config", default=False, action="store_true", help="show config of choosen site [%(default)s]")
    opts = parser.parse_args()
    # print "*", opts
    _create_base_dir(opts)

    if opts.site != _def_site and opts.set_as_default:
        _act_site_file.write(content=[opts.site])

    valid_sites_file = sge_license_tools.text_file(
        os.path.join(opts.base, sge_license_tools.SITE_CONF_NAME),
        create=opts.create,
        content=[sge_license_tools.DEFAULT_SITE],
    )
    valid_sites = valid_sites_file.lines
    if opts.site not in valid_sites:
        valid_sites.append(opts.site)
        print("adding '{}' to list of sites".format(opts.site))
        valid_sites_file.write(content=valid_sites)

    if opts.list_sites:
        print("{}:".format(logging_tools.get_plural("defined site", len(valid_sites))))
        for _site in valid_sites:
            print(" - {}".format(_site))

    act_conf_file = sge_license_tools.text_file(
        sge_license_tools.get_site_config_file_name(opts.base, opts.site),
        content=sge_license_tools.DEFAULT_CONFIG,
        create=True,
    )
    act_conf = act_conf_file.dict

    if opts.port and opts.host and not act_conf["LICENSE_FILE"]:
        _new_lic = "{:d}@{}".format(opts.port, opts.host)
        print("set LICENSE_FILE of config for site '{}' to {}".format(opts.site, _new_lic))
        act_conf["LICENSE_FILE"] = _new_lic
        act_conf_file.write(act_conf)

    if opts.show_config:
        print(
            "Config for site '{}' in {}:".format(
                opts.site,
                sge_license_tools.get_site_config_file_name(opts.base, opts.site),
            )
        )
        for _key in sorted(act_conf):
            print " - {:<20} = '{}'".format(_key, act_conf[_key])

    if opts.mode == "show":
        _lic_show(opts, act_conf)

    elif opts.mode == "fetch":
        _lic_fetch(opts, act_conf)

    elif opts.mode == "config":
        _lic_config(opts, act_conf)

    elif opts.mode == "addc":
        _lic_addc(opts, act_conf)

if __name__ == "__main__":
    main()
