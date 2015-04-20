# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

network_module = angular.module("icsw.network",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
        "icsw.tools.table", "icsw.tools.utils"
    ]
).directive('icswNetwork', ["$templateCache", ($templateCache) ->
    template: $templateCache.get("icswNetworkPage")
]).service('icswNetworkDeviceTypeService', ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url           : ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST
        delete_confirm_str : (obj) ->
            return "Really delete Network type '#{obj.description}' ?"
        edit_template      : "network.device.type.form"
        new_object: {
                "identifier"  : "eth"
                "description" : "new network device type"
                "name_re"     : "^eth.*$"
                "mac_bytes"   : 6
                "allow_virtual_interfaces" : true
        }
    }
]).service('icswNetworkTypeService', ["ICSW_URLS", (ICSW_URLS) ->
    nw_types_dict = [
        {"value":"b", "name":"boot"}
        {"value":"p", "name":"prod"}
        {"value":"s", "name":"slave"}
        {"value":"o", "name":"other"}
        {"value":"l", "name":"local"}
    ]
    return {
        rest_url            : ICSW_URLS.REST_NETWORK_TYPE_LIST
        edit_template       : "network.type.form"
        delete_confirm_str  : (obj) -> return "Really delete Network type '#{obj.description}' ?"
        new_object          : {"identifier" : "p", description : ""}
        object_created      : (new_obj) -> new_obj.description = ""
        network_types       : nw_types_dict  # for create/edit dialog
    }
]).service('icswNetworkService', ["Restangular", "$q", "icswTools", "ICSW_URLS", (Restangular, $q, icswTools, ICSW_URLS) ->

    networks_rest = Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    network_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    network_device_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object

    network_display = {}
    get_defer = (q_type) ->
        d = $q.defer()
        result = q_type.then(
           (response) ->
               d.resolve(response)
        )
        return d.promise

    hide_network =  () ->
        network_display.active_network = null
        network_display.iplist = []

    return {
        rest_handle         : networks_rest
        edit_template       : "network.form"
        networks            : networks_rest
        network_types       : network_types_rest
        network_device_types: network_device_types_rest
        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"
        new_object          : () ->
            return {
                "identifier"   : "new network",
                "network_type" : (entry["idx"] for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["identifier"] == "o")[0]
                "enforce_unique_ips" : true
                "num_ip"       : 0
                "gw_pri"       : 1
            }
        network_display     : network_display
        show_network        : (obj) ->
            if network_display.active_network == obj
                hide_network()
            else
                network_display.active_network = obj
                q_list = [
                    get_defer(Restangular.all(ICSW_URLS.REST_NET_IP_LIST.slice(1)).getList({"network" : obj.idx, "_order_by" : "ip"}))
                    get_defer(Restangular.all(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).getList({"net_ip__network" : obj.idx}))
                    get_defer(Restangular.all(ICSW_URLS.REST_DEVICE_LIST.slice(1)).getList({"netdevice__net_ip__network" : obj.idx}))
                ]
                $q.all(q_list).then((data) ->
                    iplist = data[0]
                    netdevices = icswTools.build_lut(data[1])
                    devices = icswTools.build_lut(data[2])
                    for entry in iplist
                        nd = netdevices[entry.netdevice]
                        entry.netdevice_name = nd.devname
                        entry.device_full_name = devices[nd.device].full_name
                    network_display.iplist = iplist
                )
        hide_network : hide_network
        after_reload : () ->
            hide_network()
        get_production_networks : () ->
            prod_idx = (entry for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["identifier"] == "p")[0].idx
            return (entry for key, entry of networks_rest when typeof(entry) == "object" and entry and entry.network_type == prod_idx)
        is_slave_network : (nw_type) ->
            if nw_type
                return (entry for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["idx"] == nw_type)[0].identifier == "s"
            else
                return false
        has_master_network : (edit_obj) ->
            return if edit_obj.master_network then true else false
        network_or_netmask_blur : (edit_obj) ->
            # calculate broadcast and gateway automatically

            long2ip = (long) ->
                a = (long & (0xff << 24)) >>> 24
                b = (long & (0xff << 16)) >>> 16
                c = (long & (0xff << 8)) >>> 8
                d = long & 0xff
                return [a, b, c, d].join('.')

            ip2long = (ip) ->
                b = (ip + '').split('.')
                if b.length is 0 or b.length > 4 then throw new Error('Invalid IP')
                for byte, i in b
                    if isNaN parseInt(byte, 10) then throw new Error("Invalid byte: #{byte}")
                    if byte < 0 or byte > 255 then throw new Error("Invalid byte: #{byte}")
                return ((b[0] or 0) << 24 | (b[1] or 0) << 16 | (b[2] or 0) << 8 | (b[3] or 0)) >>> 0

            # validation ensures that if it is not undefined, then it is a valid entry
            if edit_obj.network? and edit_obj.netmask?

                ip_long = ip2long(edit_obj.network)
                mask_long = ip2long(edit_obj.netmask)

                base_long = ip_long & mask_long

                base_ip = long2ip(base_long)

                # only set if there is no previous value
                if ! edit_obj.broadcast?
                    edit_obj.broadcast = base_ip
                if ! edit_obj.gateway?
                    edit_obj.gateway = base_ip
    }
])