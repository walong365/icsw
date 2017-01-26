# Copyright (C) 2012-2017 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

# network funtions

angular.module(
    "icsw.device.network",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
        "angular-ladda",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.devicenetwork")
    icswRouteExtensionProvider.add_route("main.networkoverview")
]).controller("icswDeviceNetworkCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "icswAccessLevelService", "$rootScope", "$timeout", "blockUI", "icswTools", "icswToolsButtonConfigService", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswToolsSimpleModalService", "icswDeviceTreeService", "icswNetworkTreeService",
    "icswDomainTreeService", "icswPeerInformationService", "icswDeviceTreeHelperService", "icswComplexModalService",
    "icswNetworkDeviceBackup", "toaster", "icswNetworkIPBackup", "icswPeerInformationBackup", "icswDeviceBootBackup",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, icswAccessLevelService, $rootScope, $timeout, blockUI, icswTools, icswToolsButtonConfigService, ICSW_URLS,
    icswSimpleAjaxCall, icswToolsSimpleModalService, icswDeviceTreeService, icswNetworkTreeService,
    icswDomainTreeService, icswPeerInformationService, icswDeviceTreeHelperService, icswComplexModalService,
    icswNetworkDeviceBackup, toaster, icswNetworkIPBackup, icswPeerInformationBackup, icswDeviceBootBackup,
) ->
    $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
    icswAccessLevelService.install($scope)
    $scope.show_column = {}
    # copy flags
    $scope.show_copy_button = false
    $scope.struct = {
        # data loaded
        data_loaded: false
        # device tree
        device_tree: undefined
        # network tree
        network_tree: undefined
        # domain tree
        domain_tree: undefined
        # device list
        devices: []
        # peer list
        peer_list: undefined
        # accordion flags
        device_open: true
        netdevice_open: true
        netip_open: false
        peer_open: false
        # helper objects
        local_helper_obj: undefined
        remote_helper_obj: undefined
    }

    $scope.new_devsel = (_dev_sel) ->
        $scope.struct.data_loaded = false
        dev_sel = (dev for dev in _dev_sel when not dev.is_meta_device)
        wait_list = [
            icswDeviceTreeService.load($scope.$id)
            icswNetworkTreeService.load($scope.$id)
            icswDomainTreeService.load($scope.$id)
            icswPeerInformationService.load($scope.$id, dev_sel)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.network_tree = data[1]
                $scope.struct.domain_tree = data[2]
                $scope.struct.peer_list = data[3]
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, dev_sel)
                $scope.struct.device_tree.enrich_devices(hs, ["network_info", "com_info"]).then(
                    (done) ->
                        # check if some devices have missing network_info
                        missing_list = $scope.struct.peer_list.find_missing_devices($scope.struct.device_tree)
                        defer = $q.defer()
                        if missing_list.length
                            # enrich devices with missing peer info
                            _en_devices = ($scope.struct.device_tree.all_lut[pk] for pk in missing_list)
                            # temoprary hs
                            $scope.struct.device_tree.enrich_devices(
                                icswDeviceTreeHelperService.create($scope.struct.device_tree, _en_devices)
                                ["network_info"]
                            ).then(
                                (done) ->
                                    defer.resolve("remote enriched")
                            )
                        else
                            defer.resolve("nothing missing")
                        defer.promise.then(
                            (done) ->
                                # every device in the device tree is now fully populated
                                remote = $scope.struct.peer_list.find_remote_devices($scope.struct.device_tree, dev_sel)
                                temp_hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, ($scope.struct.device_tree.all_lut[rem] for rem in remote))
                                # dummy call to enrich_devices, only used to create the lists and luts
                                $scope.struct.device_tree.enrich_devices(
                                    temp_hs
                                    ["network_info"]
                                ).then(
                                    (done) ->
                                        # everything is now in place
                                        $scope.struct.devices = dev_sel
                                        $scope.struct.local_helper_obj = hs
                                        $scope.struct.remote_helper_obj = temp_hs
                                        # salt devices
                                        $scope.struct.peer_list.enrich_device_tree($scope.struct.device_tree, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj)
                                        # console.log "network done, local_objs=", $scope.struct.local_helper_obj.devices.length
                                        $scope.struct.data_loaded = true
                                )
                        )
                )
        )

    reload_everything = (ss_id, force_network_info) ->
        # reloads everything possible, for scan and copy network calls
        d = $q.defer()
        $q.all(
            [
                # new network tree
                icswNetworkTreeService.reload(ss_id)
                # new peer infos
                icswPeerInformationService.reload(ss_id, $scope.struct.peer_list)
                # new network infos for all devices
                $scope.struct.device_tree.enrich_devices($scope.struct.local_helper_obj, ["network_info"], force_network_info)
            ]
        ).then(
            (done) ->
                # maybe some new remote devices are to add
                missing_list = $scope.struct.peer_list.find_missing_devices($scope.struct.device_tree)
                defer = $q.defer()
                if missing_list.length
                    # enrich devices with missing peer info
                    _en_devices = ($scope.struct.device_tree.all_lut[pk] for pk in missing_list)
                    # temoprary hs
                    $scope.struct.device_tree.enrich_devices(
                        icswDeviceTreeHelperService.create($scope.struct.device_tree, _en_devices)
                        ["network_info"]
                        force_network_info
                    ).then(
                        (done) ->
                            defer.resolve("remote enriched")
                    )
                else
                    defer.resolve("nothing missing")
                defer.promise.then(
                    (done) ->
                        # every device in the device tree is now fully populated
                        remote = $scope.struct.peer_list.find_remote_devices($scope.struct.device_tree, $scope.struct.devices)
                        temp_hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, ($scope.struct.device_tree.all_lut[rem] for rem in remote))
                        # dummy call to enrich_devices, only used to create the lists and luts
                        $scope.struct.device_tree.enrich_devices(
                            temp_hs
                            ["network_info"]
                        ).then(
                            (done) ->
                                # everything is now in place
                                $scope.struct.remote_helper_obj = temp_hs
                                $scope.struct.peer_list.enrich_device_tree($scope.struct.device_tree, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj)
                                console.log "done reloading"
                                d.resolve("scan ok")
                        )
                )
        )
        return d.promise

    $scope.scan_device_network = (dev, event) ->

        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = dev

        network_type_names = []
        ip_dict = {}
        for ndev in dev.netdevice_set
            for ip in ndev.net_ip_set
                nw = $scope.struct.network_tree.nw_lut[ip.network]
                nw_type = $scope.struct.network_tree.nw_type_lut[nw.network_type]
                if nw_type.identifier != "l" and not (nw.netmask == "255.0.0.0" and nw.network == "127.0.0.0")
                    nwt_d = nw_type.description
                    if nwt_d not of ip_dict
                        ip_dict[nwt_d] = []
                        network_type_names.push(nwt_d)
                    ip_dict[nwt_d].push(ip.ip)
        for key, value of ip_dict
            ip_dict[key] = _.uniq(_.sortBy(value))
        network_type_names = _.sortBy(network_type_names)

        sub_scope.ip_dict = ip_dict
        sub_scope.network_type_names = network_type_names

        sub_scope.scan_settings = {
            manual_address: ""
            # set snmp / wmi names
            snmp_community: "public"
            snmp_version: "2c"
            wmi_username: "Administrator"
            wmi_password: ""
            wmi_discard_disabled_interfaces: true
            remove_not_found: false
            strict_mode: true
            modify_peering: false
            scan_mode: "NOT_SET"
            device: dev.idx
        }
        if _.keys(ip_dict).length == 1
            nw_ip_addresses = ip_dict[Object.keys(ip_dict)[0]]
            if nw_ip_addresses.length == 1
                sub_scope.scan_settings.manual_address = nw_ip_addresses[0]
            else if nw_ip_addresses.length > 1
                # take last IP address
                sub_scope.scan_settings.manual_address = nw_ip_addresses[-1]
        else
            # preferred ip addresses
            _ip_to_use = ""
            for _pref in ["p", "o", "s", "b"]
                if _pref of $scope.struct.network_tree.nw_type_lut
                    _nwt = $scope.struct.network_tree.nw_type_lut[_pref]
                    if _nwt.description of ip_dict
                        _ip_to_use = ip_dict[_nwt.description][0]
                        break
            if _ip_to_use
                sub_scope.scan_settings.manual_address = _ip_to_use

        sub_scope.active_scan = {
            "base": false
            "hm": false
            "snmp": false
        }
        has_com_capability = (cc) ->
            return if (entry for entry in dev.com_capability_list when entry.matchcode == cc).length then true else false

        sub_scope.has_com_capability = (cc) ->
            return has_com_capability(cc)

        sub_scope.set_scan_mode = (sm) ->
            # sub_scope.$scope.scan_device.scan_mode = sm
            sub_scope.scan_settings.scan_mode = sm
            sub_scope.active_scan[sm] = true

        sub_scope.set_ip = (ip) ->
            sub_scope.scan_settings.manual_address = ip

        if dev.netdevice_set.length and has_com_capability("snmp")
            sub_scope.set_scan_mode("snmp")
        else
            sub_scope.set_scan_mode("base")

        scan_performed = false
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.network.scan.form"))(sub_scope)
                ok_label: "Scan"
                title: "Scan network of device #{dev.full_name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        blockUI.start("Starting scan")
                        scan_performed = true
                        $scope.struct.device_tree.register_device_scan(dev, sub_scope.scan_settings).then(
                            (ok) ->
                                reload_everything(sub_scope.$id, false).then(
                                    (res) ->
                                        blockUI.stop()
                                        d.resolve("reloaded")
                                )
                            (notok) ->
                                blockUI.stop()
                                d.reject("scan not ok")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "Scan window closed"
                sub_scope.$destroy()
                $scope.struct.peer_list.build_luts()
                $scope.struct.peer_list.enrich_device_tree($scope.struct.device_tree, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj)
                _salt_local_devices()
                reload_everything(sub_scope.$id, false)

                if scan_performed
                    blockUI.start("Starting scan")
                    $timeout(
                        () ->
                            $scope.struct.device_tree.register_device_scan(dev, sub_scope.scan_settings).then(
                                $scope.struct.peer_list.build_luts()
                                $scope.struct.peer_list.enrich_device_tree($scope.struct.device_tree, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj)
                                _salt_local_devices()
                                reload_everything(sub_scope.$id, true).then(
                                    (res) ->
                                        blockUI.stop()
                                )
                            )
                        5000
                    )
        )
        return

    _salt_local_devices = () ->
        $scope.struct.device_tree.enricher.build_g_luts(
            ["network_info"]
            $scope.struct.local_helper_obj
        )

    $scope.copy_network = (src_obj, event) ->

        sub_scope = $scope.$new(true)
        sub_scope.copy_coms = false
        sub_scope.settings = {
            "copy_coms": false
            "src_device": $scope.struct.devices[0]
        }
        sub_scope.copy_com_class = () ->
            if sub_scope.settings.copy_coms
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm btn-default"

        sub_scope.toggle_copy_com = () ->
            sub_scope.settings.copy_coms = !sub_scope.settings.copy_coms

        sub_scope.copy_com_value = () ->
            if sub_scope.settings.copy_coms
                return "Copy ComCapabilities and Schemes"
            else
                return "start with empty ComCapabilitiess and Schemes"

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.network.copy"))(sub_scope)
                ok_label: "Copy"
                title: "Copy network settings"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        blockUI.start()
                        icswSimpleAjaxCall(
                            url: ICSW_URLS.NETWORK_COPY_NETWORK
                            data: {
                                source_dev: sub_scope.settings.src_device.idx
                                copy_coms: sub_scope.settings.copy_coms
                                all_devs: angular.toJson((dev.idx for dev in $scope.struct.devices))
                            }
                        ).then(
                            (xml) ->
                                reload_everything(sub_scope.$id, true).then(
                                    (res) ->
                                        blockUI.stop()
                                        d.resolve("reloaded")
                                )
                                d.resolve("copied")
                            (xml) ->
                                blockUI.stop()
                                d.reject("not OK")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "Copy modifier closed"
                sub_scope.$destroy()
        )

    $scope.edit_boot_settings = ($event, obj) ->

        dbu = new icswDeviceBootBackup()
        dbu.create_backup(obj)

        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = obj

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.boot.form"))(sub_scope)
                ok_label: "Update"
                title: "Modify boot settings of #{obj.full_name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        $scope.struct.device_tree.update_boot_settings(obj).then(
                            (data) ->
                                # console.log "data", data
                                d.resolve("updated")
                            (reject) ->
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "Boot modifier closed"
                sub_scope.$destroy()
                _salt_local_devices()
        )

    $scope.edit_peer = ($event, cur_obj, obj_type, create_mode) ->
        # cur_obj is device, netdevice of ip, obj_type is 'dev', 'nd' or 'ip'
        # create or edit
        if create_mode
            edit_obj = {
                penalty: 1
                auto_created: false
                info: "new peer"
                s_spec: ""
                d_spec: ""
            }
            if obj_type == "dev"
                title = "Create new Peer on Device '#{cur_obj.full_name}'"
                edit_obj.s_netdevice = cur_obj.netdevice_set[0].idx
                edit_obj.$$s_type = "l"
                edit_obj.d_netdevice = cur_obj.netdevice_set[0].idx
                edit_obj.$$d_type = "l"
                helper_mode = "d"

            else if obj_type == "nd"
                title = "Create new Peer on Netdevice '#{cur_obj.devname}'"
                edit_obj.s_netdevice = cur_obj.idx
                edit_obj.$$s_type = "l"
                edit_obj.d_netdevice = cur_obj.idx
                edit_obj.$$d_type = "l"
                helper_mode = "n"
        else
            edit_obj = cur_obj
            dbu = new icswPeerInformationBackup()
            dbu.create_backup(edit_obj)
            title = "Edit Peer Information"
            helper_mode = "e"

        # which template to use
        template_name = "icsw.peer.form"
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = edit_obj
        sub_scope.source_helper = $scope.struct.peer_list.build_peer_helper($scope.struct.device_tree, edit_obj, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj, "s", helper_mode)
        sub_scope.dest_helper = $scope.struct.peer_list.build_peer_helper($scope.struct.device_tree, edit_obj, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj, "d", helper_mode)
        # create link
        sub_scope.create_mode = create_mode

        # add functions

        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create_mode
                            $scope.struct.peer_list.create_peer(sub_scope.edit_obj, $scope.struct.device_tree).then(
                                (new_peer) ->
                                    # check if we have to enrich the remote helper obj
                                    if new_peer.s_device of $scope.struct.local_helper_obj.device_lut
                                        # source is local, check dest
                                        _cd = new_peer.d_device
                                    else
                                        _cd = new_peer.s_device
                                    if _cd not of $scope.struct.remote_helper_obj.device_lut
                                        # we have to add a device to the struct.remote_helper_obj
                                        $scope.struct.remote_helper_obj.add_device($scope.struct.device_tree.all_lut[_cd])
                                        $scope.struct.device_tree.enrich_devices($scope.struct.remote_helper_obj, ["network_info"], true).then(
                                            (done) ->
                                                d.resolve("peer created")
                                        )
                                    else
                                        # all devices present
                                        d.resolve("peer created")
                                (notok) ->
                                    d.reject("peer not created")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_PEER_INFORMATION_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (data) ->
                                    # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                                    console.log "data", data
                                    d.resolve("save")
                                (reject) ->
                                    # ToDo, FIXME, handle rest (test?)
                                    # two possibilites: restore and continue or reject, right now we use the second path
                                    # dbu.restore_backup(obj)
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "Peer requester closed, trigger redraw"
                sub_scope.$destroy()
                # trigger rebuild of lists
                # recreate helper luts
                $scope.struct.peer_list.build_luts()
                $scope.struct.peer_list.enrich_device_tree($scope.struct.device_tree, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj)
                _salt_local_devices()
        )

    $scope.delete_peer = ($event, peer) ->
        icswToolsSimpleModalService("Really delete Peer ?").then(
            () =>
                $scope.struct.peer_list.delete_peer(peer).then(
                    () ->
                        $scope.struct.peer_list.build_luts()
                        $scope.struct.peer_list.enrich_device_tree($scope.struct.device_tree, $scope.struct.local_helper_obj, $scope.struct.remote_helper_obj)
                        _salt_local_devices()
                )
        )

    $scope.edit_netip = ($event, cur_obj, obj_type, create_mode) ->
        # cur_obj is device, netdevice of ip, obj_type is 'dev', 'nd' or 'ip'
        # create or edit
        if create_mode
            edit_obj = {
                "ip" : "0.0.0.0"
                "_changed_by_user_": false
                "network" : $scope.struct.network_tree.nw_list[0].idx
                # take first domain tree node
                "domain_tree_node" : $scope.struct.domain_tree.list[0].idx
            }
            if obj_type == "dev"
                title = "Create new IP on Device '#{cur_obj.full_name}'"
                edit_obj.netdevice = cur_obj.netdevice_set[0].idx
                dev = cur_obj
            else if obj_type == "nd"
                title = "Create new IP on Netdevice '#{cur_obj.devname}'"
                edit_obj.netdevice = cur_obj.idx
                dev = $scope.struct.device_tree.all_lut[cur_obj.device]
        else
            edit_obj = cur_obj
            dbu = new icswNetworkIPBackup()
            dbu.create_backup(edit_obj)
            title = "Edit IP #{edit_obj.ip}"
            dev = $scope.struct.device_tree.all_lut[$scope.struct.local_helper_obj.netdevice_lut[edit_obj.netdevice].device]

        # which template to use
        template_name = "icsw.net.ip.form"
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = edit_obj
        sub_scope.device = dev
        sub_scope.create_mode = create_mode
        sub_scope.struct = {
            device: dev
            network_tree: $scope.struct.network_tree
            domain_tree: $scope.struct.domain_tree
        }

        # add functions

        sub_scope.get_free_ip = ($event, obj) ->
            blockUI.start("requesting free IP...")
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_GET_FREE_IP
                data: {
                    "netip": angular.toJson(obj)
                }
                dataType: "json"
            ).then(
                (json) ->
                    blockUI.stop()
                    if json["ip"]?
                        obj.ip = json["ip"]
            )

        sub_scope.network_changed = (obj) ->
            if obj.ip == "0.0.0.0" or not obj._changed_by_user_
                sub_scope.get_free_ip(null, obj)
            if not obj._changed_by_user_
                _nw = $scope.struct.network_tree.nw_lut[obj.network]
                if _nw.preferred_domain_tree_node
                    obj.domain_tree_node = _nw.preferred_domain_tree_node

        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        nd = $scope.struct.local_helper_obj.netdevice_lut[sub_scope.edit_obj.netdevice]
                        if create_mode
                            $scope.struct.device_tree.create_netip(sub_scope.edit_obj, nd).then(
                                (ok) ->
                                    d.resolve("netip created")
                                (notok) ->
                                    d.reject("netip not created")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_NET_IP_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (data) ->
                                    # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                                    console.log "data", data
                                    d.resolve("save")
                                (reject) ->
                                    # ToDo, FIXME, handle rest (test?)
                                    # two possibilites: restore and continue or reject, right now we use the second path
                                    # dbu.restore_backup(obj)
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "NetIP requester closed, trigger redraw"
                sub_scope.$destroy()
                # trigger rebuild of lists
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                # recreate helper luts
                _salt_local_devices()
        )

    $scope.delete_netip = ($event, ip) ->
        icswToolsSimpleModalService("Really delete IP #{ip.ip} ?").then(
            () =>
                nd = $scope.struct.local_helper_obj.netdevice_lut[ip.netdevice]
                $scope.struct.device_tree.delete_netip(ip, nd).then(
                    () ->
                        _salt_local_devices()
                )
        )

    $scope.edit_netdevice = ($event, nd_obj, create_mode) ->
        # create or edit
        if create_mode
            # nd_obj is the parent device
            new_type = $scope.struct.network_tree.nw_device_type_list[0]
            mac_bytes = new_type.mac_bytes
            default_ms = ("00" for idx in [0..mac_bytes]).join(":")
            edit_obj = {
                "device": nd_obj.idx
                "devname": "eth0"
                "enabled": true
                "netdevice_speed": (entry.idx for entry in $scope.struct.network_tree.nw_speed_list when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
                "ignore_netdevice_speed": false
                "desired_status": "i"
                "penalty": 1
                "net_ip_set": []
                "ethtool_options": 0
                "ethtool_autoneg": 0
                "ethtool_speed": 0
                "ethtool_duplex": 0
                "mtu": 1500
                "macaddr": default_ms
                "fake_macaddr": default_ms
                # dummy value
                "network_device_type": new_type.idx
            }
            title = "Create new Netdevice on '#{nd_obj.full_name}'"
        else
            edit_obj = nd_obj
            dbu = new icswNetworkDeviceBackup()
            dbu.create_backup(edit_obj)
            title = "Edit netdevice #{edit_obj.devname}"
        # which template to use
        template_name = "icsw.netdevice.form"
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = edit_obj

        # set helper functions and arrays
        sub_scope.desired_stati = [
            {"short": "i", "info_string": "ignore"}
            {"short": "u", "info_string": "must be up"}
            {"short": "d", "info_string": "must be down"}
        ]
        sub_scope.update_ethtool = (ndip_obj) ->
            ndip_obj.ethtool_options = (parseInt(ndip_obj.ethtool_speed) << 4) | (parseInt(ndip_obj.ethtool_duplex) << 2) < (parseInt(ndip_obj.ethtool_autoneg))

        sub_scope.get_vlan_masters = (cur_nd) ->
            _cd = $scope.struct.device_tree.all_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and not entry.is_bridge and not entry.is_bond)

        sub_scope.get_bridge_masters = (cur_nd) ->
            _cd = $scope.struct.device_tree.all_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bridge)

        sub_scope.get_bond_masters = (cur_nd) ->
            _cd = $scope.struct.device_tree.all_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bond)

        sub_scope.has_bridge_slaves = (nd) ->
            dev = $scope.struct.device_tree.all_lut[nd.device]
            if nd.is_bridge
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx).length then true else false
            else
                return false

        sub_scope.has_bond_slaves = (nd) ->
            dev = $scope.struct.device_tree.all_lut[nd.device]
            if nd.is_bond
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bond_master == nd.idx).length then true else false
            else
                return false

        sub_scope.ethtool_autoneg = [
            {"id": 0, "option": "default"},
            {"id": 1, "option": "on"},
            {"id": 2, "option": "off"},
        ]

        sub_scope.ethtool_duplex = [
            {"id": 0, "option": "default"},
            {"id": 1, "option": "on"},
            {"id": 2, "option": "off"},
        ]

        sub_scope.ethtool_speed = [
            {"id": 0, "option": "default"},
            {"id": 1, "option": "10 MBit"},
            {"id": 2, "option": "100 MBit"},
            {"id": 3, "option": "1 GBit"},
            {"id": 4, "option": "10 GBit"},
        ]

        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create_mode
                            $scope.struct.device_tree.create_netdevice(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("netdevice created")
                                (notok) ->
                                    d.reject("netdevice not created")
                            )
                        else
                            $scope.struct.device_tree.modify_netdevice(sub_scope.edit_obj).then(
                                (new_nd) ->
                                    d.resolve("saved")
                                (reject) ->
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "NetDevice requester closed, trigger redraw"
                _salt_local_devices()
                sub_scope.$destroy()
                # trigger rebuild of lists
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                # recreate helper luts
        )

    $scope.delete_netdevice = ($event, nd) ->
        icswToolsSimpleModalService("Really delete netdevice #{nd.devname} ?").then(
            () ->
                $scope.struct.device_tree.delete_netdevice(nd).then(
                    () ->
                        _salt_local_devices()
                )
        )

]).controller("icswDeviceNetworkNetdeviceRowCtrl", ["$scope", ($scope) ->
    ethtool_options = (ndip_obj, type) ->
        if type == "a"
            eth_opt = ndip_obj.ethtool_options & 3
            return {
                0: "default"
                1: "on"
                2: "off"
            }[eth_opt]
        else if type == "d"
            eth_opt = (ndip_obj.ethtool_options >> 2) & 3
            return {
                0: "default"
                1: "on"
                2: "off"
            }[eth_opt]
        else if type == "s"
            eth_opt = (ndip_obj.ethtool_options >> 4) & 7
            return {
                0: "default"
                1: "10 MBit"
                2: "100 MBit"
                3: "1 GBit"
                4: "10 GBit"
            }[eth_opt]

    $scope.get_num_peers_nd = (nd) ->
        if nd.idx of $scope.struct.peer_list.nd_lut
            return $scope.struct.peer_list.nd_lut[nd.idx].length
        else
            return 0

    $scope.build_netdevice_tooltip = (ndev) ->
        device = $scope.struct.device_tree.all_lut[ndev.device]
        info_f = [
            "<div class='text-left'>",
            "device: #{device.full_name}<br>"
        ]
        if ndev.snmp_idx
            info_f.push(
                "SNMP: yes (#{ndev.snmp_idx})<br>"
            )
        else
            info_f.push(
                "SNMP: no<br>"
            )
        info_f.push("enabled: " + if ndev.enabled then "yes" else "no")
        info_f.push("<hr>")
        info_f.push("driver: #{ndev.driver}<br>")
        info_f.push("driver options: #{ndev.driver_options}<br>")
        info_f.push("fake MACAddress: #{ndev.fake_macaddr}<br>")
        info_f.push("force write DHCP: " + if ndev.dhcp_device then "yes" else "no")
        info_f.push("<hr>")
        info_f.push("Autonegotiation: " + ethtool_options(ndev, "a") + "<br>")
        info_f.push("Duplex: " +ethtool_options(ndev, "d") +  "<br>")
        info_f.push("Speed: " + ethtool_options(ndev, "s") + "<br>")
        info_f.push("<hr>")
        info_f.push("Monitoring: " + ndev.$$speed_info_string)
        info_f.push("</div>")
        return info_f.join("")

]).directive("icswDeviceNetworkNetdeviceRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.netdevice.row")
        controller: "icswDeviceNetworkNetdeviceRowCtrl"
    }
]).factory("icswDeviceComCapabilitiesReact",
[
    "$q",
(
    $q,
) ->
    {span, ul, i} = React.DOM
    return React.createClass(
        propTypes: {
            device: React.PropTypes.object
            detail: React.PropTypes.bool
        }

        getInitialState: () ->
            # no state
            return {}

        render: () ->
            caps = @props.device.com_capability_list
            if caps.length
                _cls = "success"
                if @props.detail
                    _text = (entry.name for entry in caps).join(", ")
                else
                    _text = (entry.matchcode for entry in caps).join(", ")
            else
                _text = "N/A"
                _cls = "danger"
            _span_list = [
                _text
            ]
            active_scans = @props.device.$$active_scan_locks
            if active_scans
                _span_list.push(" ")
                _span_list.push(
                    i(
                        {
                            key: "ladda"
                            className: "fa fa-spinner fa-spin fa-3x fa-fw"
                        }
                    )
                )
                _span_list.push(
                    active_scans
                )
            return span(
                {
                    key: "top"
                    className: "label label-#{_cls}"
                }
                _span_list
            )
    )


]).directive("icswDeviceComCapabilities",
[
    "icswDeviceTreeHelperService", "ICSW_SIGNALS", "$rootScope", "icswDeviceComCapabilitiesReact",
(
    icswDeviceTreeHelperService, ICSW_SIGNALS, $rootScope, icswDeviceComCapabilitiesReact,
) ->
    return {
        restrict : "EA"
        scope:
            device: "=icswDevice"
            detail: "=icswDetail"
        link: (scope, element, attrs) ->
            _node = ReactDOM.render(
                React.createElement(
                    icswDeviceComCapabilitiesReact
                    {
                        device: scope.device
                        detail: if scope.detail? then true else false
                    }
                )
                element[0]
            )

            _unreg = $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_SCAN_CHANGED"), (event, pk) ->
                # console.log "*** devscan", pk
                if pk == scope.device.idx
                    # console.log "* node=", _node
                    _node.forceUpdate()
            )
            scope.$on("$destroy", () ->
                _unreg()
                ReactDOM.unmountComponentAtNode(element[0])
            )
    }
]).directive("icswDeviceNetworkIpRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.ip.row")
    }
]).directive("icswDeviceNetworkDeviceRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.device.row")
    }
]).controller("icswDeviceNetworkPeerRowCtrl", ["$scope", ($scope) ->
    get_netdevice_from_peer = (peer_obj, ptype) ->
        if peer_obj["$$#{ptype}_type"] == "l"
            ho = $scope.struct.local_helper_obj
            o_ho = $scope.struct.remote_helper_obj
        else
            ho = $scope.struct.remote_helper_obj
            o_ho = $scope.struct.local_helper_obj
        _pk = peer_obj["#{ptype}_netdevice"]
        if _pk of ho.netdevice_lut
            return ho.netdevice_lut[_pk]
        else
            # undefined, may happen during edit
            # use the other helper object
            return o_ho.netdevice_lut[_pk]

    $scope.get_peer_type = (peer) ->
        _local_devs = (dev.idx for dev in $scope.struct.devices)
        r_list = []
        for c_id in [peer.s_device, peer.d_device]
            r_list.push(if (c_id in _local_devs) then "sel" else "N/S")
        return r_list.join(", ")

    $scope.get_peer_class = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        if nd.routing
            return "warning"
        else
            return ""

    $scope.get_devname_from_peer = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        dev = $scope.struct.device_tree.all_lut[nd.device]
        return dev.full_name

    $scope.get_netdevice_name_from_peer = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        return "#{nd.devname} (#{nd.penalty})"

    $scope.get_ip_list_from_peer = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        ip_list = (ip.ip for ip in nd.net_ip_set)
        if ip_list.length
            return ip_list.join(", ")
        else
            return "---"

    $scope.get_peer_cost = (peer_obj) ->
        s_nd = get_netdevice_from_peer(peer_obj, "s")
        d_nd = get_netdevice_from_peer(peer_obj, "d")
        return s_nd.penalty + peer_obj.penalty + d_nd.penalty

]).directive("icswDeviceNetworkPeerRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.peer.row")
        controller: "icswDeviceNetworkPeerRowCtrl"
    }
]).directive("icswDeviceNetworkOverview", ["$templateCache", ($templateCache) ->
    return {
        scope: true
        restrict : "EA"
        link: (scope, el, attrs) ->
            if attrs["showCopyButton"]?
                scope.show_copy_button = true
        template : $templateCache.get("icsw.device.network.overview")
        controller: "icswDeviceNetworkCtrl"
    }
]).directive("icswDeviceNetworkTotal", ["$templateCache", "$rootScope", "ICSW_SIGNALS", ($templateCache, $rootScope, ICSW_SIGNALS) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.network.total")
        link: (scope, element, attrs) ->
            scope.select_tab = (name) ->
                $rootScope.$emit(ICSW_SIGNALS("ICSW_NETWORK_TAB_SELECTED"), name)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_SVG_FULLSIZELAYOUT_SETUP"))
        controller: "icswDeviceNetworkTotalCtrl"
    }
]).directive("icswNetworkSimpleOverview", [
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.network.simple.overview")
        controller: "icswDeviceNetworkTotalCtrl"
    }
]).directive("icswNetworkListServiceTabs", [
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.network.list.service.tabs")
        controller: "icswDeviceNetworkTotalCtrl"
    }
]).controller("icswDeviceNetworkTotalCtrl", [
    "$scope", "icswNetworkListService"
(
    $scope, icswNetworkListService
) ->
    $scope.struct = {
        icsw_network_list_service: icswNetworkListService
    }
]).controller("icswDeviceNetworkClusterCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "icswAccessLevelService", "ICSW_URLS", "icswSimpleAjaxCall",
    "blockUI", "ICSW_SIGNALS", "$rootScope", "icswComplexModalService",
    "icswDeviceTreeService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, icswAccessLevelService, ICSW_URLS, icswSimpleAjaxCall,
    blockUI, ICSW_SIGNALS, $rootScope, icswComplexModalService,
    icswDeviceTreeService,
) ->
    icswAccessLevelService.install($scope)
    $scope.struct = {
        # clusters
        clusters: []
        # devices
        devices: []
    }

    $scope.new_devsel = (dev_sel) ->
        $scope.struct.devices.length = 0
        for entry in dev_sel
            $scope.struct.devices.push(entry)

    $scope.reload = () ->
        blockUI.start("loading NetworkClusters")
        icswSimpleAjaxCall(
            url: ICSW_URLS.NETWORK_GET_CLUSTERS
            dataType: "json"
        ).then(
            (json) ->
                blockUI.stop()
                $scope.struct.clusters = json
        )

    $scope.is_selected = (cluster) ->
        _sel = _.intersection(cluster.device_pks, $scope.struct.devices)
        return if _sel.length then "yes (#{_sel.length})" else "no"

    $scope.show_cluster = (cluster) ->
        icswDeviceTreeService.load($scope.$id).then(
            (device_tree) ->
                child_scope = $scope.$new(true)
                child_scope.struct = {
                    cluster: cluster
                    devices: (device_tree.all_lut[pk] for pk in cluster.device_pks)
                }
                icswComplexModalService(
                    {
                        message: $compile($templateCache.get("icsw.device.network.cluster.info"))(child_scope)
                        title: "Devices in cluster (#{child_scope.struct.cluster.device_pks.length})"
                        # css_class: "modal-wide"
                        ok_label: "Close"
                        closable: true
                        ok_callback: (modal) ->
                            d = $q.defer()
                            d.resolve("ok")
                            return d.promise
                    }
                ).then(
                    (fin) ->
                        console.log "finish"
                        child_scope.$destroy()
                )
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_NETWORK_TAB_SELECTED"), (event, name) ->
        if name == "cluster"
            $scope.reload()
    )
]).service('icswNetworkDeviceTypeService',
[
    "ICSW_URLS", "icswNetworkTreeService", "$q", "icswComplexModalService", "$compile", "$templateCache",
    "toaster", "icswNetworkDeviceTypeBackup", "icswToolsSimpleModalService",
(
    ICSW_URLS, icswNetworkTreeService, $q, icswComplexModalService, $compile, $templateCache,
    toaster, icswNetworkDeviceTypeBackup, icswToolsSimpleModalService
) ->
    nw_tree = undefined
    return {
        fetch: (scope) ->
            # console.log "start fetch"
            defer = $q.defer()
            icswNetworkTreeService.load(scope.$id).then(
                (net_tree) ->
                    nw_tree = net_tree
                    defer.resolve(net_tree.nw_device_type_list)
            )
            return defer.promise

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    "identifier"  : "eth"
                    "description" : "New Network Device Type"
                    "name_re"     : "^eth.*$"
                    "mac_bytes"   : 6
                    "allow_virtual_interfaces" : true
                }
            else
                dbu = new icswNetworkDeviceTypeBackup()
                dbu.create_backup(obj_or_parent)
            scope.edit_obj = obj_or_parent
            sub_scope = scope.$new(false)
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("network.device.type.form"))(sub_scope)
                    title: "Network Device Type"
                    css_class: "modal-wide modal-form"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "")
                            d.reject("form not valid")
                        else
                            if create
                                nw_tree.create_network_device_type(scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                scope.edit_obj.put().then(
                                    (ok) ->
                                        nw_tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        delete: (scope, event, obj) ->
            icswToolsSimpleModalService("Really delete Network DeviceType '#{obj.description}' ?").then(
                (ok) ->
                    nw_tree.delete_network_device_type(obj).then(
                        (ok) ->
                    )
            )
    }
]).service('icswNetworkTypeService',
[
    "ICSW_URLS", "icswNetworkTreeService", "$q", "icswComplexModalService", "$compile", "$templateCache",
    "toaster", "icswNetworkTypeBackup", "icswToolsSimpleModalService",
(
    ICSW_URLS, icswNetworkTreeService, $q, icswComplexModalService, $compile, $templateCache,
    toaster, icswNetworkTypeBackup, icswToolsSimpleModalService
) ->
    nw_types_dict = [
        {"value":"b", "name":"boot"}
        {"value":"p", "name":"prod"}
        {"value":"s", "name":"slave"}
        {"value":"o", "name":"other"}
        {"value":"l", "name":"local"}
    ]
    # will be set below
    nw_tree = undefined
    return {
        fetch: (scope) ->
            # console.log "start fetch"
            defer = $q.defer()
            icswNetworkTreeService.load(scope.$id).then(
                (net_tree) ->
                    nw_tree = net_tree
                    defer.resolve(net_tree.nw_type_list)
            )
            return defer.promise
        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    "identifier": "p"
                    "description": "New Network Type"
                }
            else
                dbu = new icswNetworkTypeBackup()
                dbu.create_backup(obj_or_parent)
            scope.edit_obj = obj_or_parent
            sub_scope = scope.$new(false)
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("network.type.form"))(sub_scope)
                    title: "Network Type"
                    css_class: "modal-wide modal-form"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "")
                            d.reject("form not valid")
                        else
                            if create
                                nw_tree.create_network_type(scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                scope.edit_obj.put().then(
                                    (ok) ->
                                        nw_tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )
        delete: (scope, event, obj) ->
            icswToolsSimpleModalService("Really delete NetworkType '#{obj.description}' ?").then(
                (ok) ->
                    nw_tree.delete_network_type(obj).then(
                        (ok) ->
                    )
            )
        network_types       : nw_types_dict  # for create/edit dialog
        resolve_type: (id) ->
            return (val for val in nw_types_dict when val.value == id)[0].name
    }
]).directive("icswNetworkList", [
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.network.list")
        controller: "icswNetworkListCtrl"
    }
]).controller("icswNetworkListCtrl", [
    "$scope", "$compile", "$templateCache", "$q", "icswComplexModalService", "icswConfigTreeService",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "icswUserService", "icswSimpleAjaxCall", "ICSW_URLS"
(
    $scope, $compile, $templateCache, $q, icswComplexModalService, icswConfigTreeService,
    icswDeviceTreeService, icswDeviceTreeHelperService, icswUserService, icswSimpleAjaxCall, ICSW_URLS
) ->
    $scope.perform_host_discovery_scan = (network_obj) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswConfigTreeService.load($scope.$id)
                icswUserService.load($scope.$id)
            ]
        ).then(
            (data) ->
                device_tree = data[0]
                config_tree = data[1]
                user_tree = data[2]

                device_tree.enrich_devices(
                    icswDeviceTreeHelperService.create(device_tree, device_tree.all_list)
                    ["network_info", "com_info"]
                ).then(
                     (done) ->
                            sub_scope = $scope.$new(true)

                            sub_scope.nmap_scan_devices = []
                            sub_scope.edit_obj = {}
                            sub_scope.edit_obj.$$scan_device = undefined

                            for config in config_tree.list
                                if config.name == "nmap-scan-device"
                                    for obj in config.device_config_set
                                        sub_scope.nmap_scan_devices.push(device_tree.all_lut[obj.device])

                            icswComplexModalService(
                                {
                                    message: $compile($templateCache.get("performscan.form"))(sub_scope)
                                    title: "Scan Settings"
                                    css_class: "modal-wide modal-form"
                                    ok_label: "Scan Now"
                                    closable: true
                                    ok_callback: (modal) ->
                                        d = $q.defer()
                                        icswSimpleAjaxCall(
                                            {
                                                url: ICSW_URLS.DISCOVERY_CREATE_SCHEDULE_ITEM
                                                data:
                                                    model_name: "network"
                                                    object_id: network_obj.idx
                                                    schedule_handler: "network_scan_schedule_handler"
                                                    schedule_handler_data: "" + sub_scope.edit_obj.$$scan_device
                                                    user_id: user_tree.user.idx
                                                dataType: "json"
                                            }
                                        ).then(
                                            (result) ->
                                                d.resolve("ok")
                                        )
                                        return d.promise
                                    cancel_callback: (modal) ->
                                        d = $q.defer()
                                        d.resolve("cancel")
                                        return d.promise
                                }
                            ).then(
                                (fin) ->
                                    console.log "finish"
                                    sub_scope.$destroy()
                            )
                )

        )



    $scope.show_column = {}
]).service('icswNetworkListService',
[
    "Restangular", "$q", "icswTools", "ICSW_URLS", "icswDomainTreeService", "icswSimpleAjaxCall", "blockUI",
    "icswNetworkTreeService", "icswNetworkBackup", "icswComplexModalService", "$compile", "$templateCache",
    "toaster", "icswToolsSimpleModalService", "$timeout", "icswDispatcherSettingTreeService", "icswUserService",
    "icswDeviceTreeService", "icswWebSocketService", "icswConfigTreeService", "DeviceOverviewService",
    "icswDeviceTreeHelperService"
(
    Restangular, $q, icswTools, ICSW_URLS, icswDomainTreeService, icswSimpleAjaxCall, blockUI,
    icswNetworkTreeService, icswNetworkBackup, icswComplexModalService, $compile, $templateCache,
    toaster, icswToolsSimpleModalService, $timeout, icswDispatcherSettingTreeService, icswUserService,
    icswDeviceTreeService, icswWebSocketService, icswConfigTreeService, DeviceOverviewService,
    icswDeviceTreeHelperService
) ->

    # networks_rest = Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    # network_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    # network_device_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    # domain_tree_node_list = []
    # domain_tree_node_dict = {}

    tabs = []

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

    reload_networks = (scope) ->
        # blockUI
        blockUI.start()
        icswNetworkTreeService.reload("rescan").then(
            (done) ->
                blockUI.stop()
        )

    convert_ip_str_to_int = (ip_str) ->
        dots = ip_str.split(".")

        return parseInt((dots[0] * 16777216) + (dots[1] * 65536) + (dots[2] * 256) + (dots[3]))

    salt_nmap_scan = (nmap_scan) ->
        nmap_scan.$$displayed = true
        nmap_scan.$$created = moment(nmap_scan.date).format("YYYY-MM-DD HH:mm:ss")

        if nmap_scan.devices_found == null
            nmap_scan.devices_found = "N/A"
        else
            nmap_scan.devices_found = nmap_scan.devices_found - nmap_scan.devices_ignored

        if nmap_scan.devices_ignored == null
            nmap_scan.devices_ignored = "N/A"

        if nmap_scan.devices_scanned == null
            nmap_scan.devices_scanned = "N/A"

        if nmap_scan.runtime == null
            nmap_scan.runtime = "N/A"

    salt_nmap_device = (device, ip_to_device_lut) ->
        device.$$mac = "N/A"
        if device.mac != null
            device.$$mac = device.mac

        device.$$hostname = "N/A"
        device.$$hostname_sort_hint = "-1"
        if device.hostname != null
            device.$$hostname = device.hostname
            device.$$hostname_sort_hint = device.hostname

        device.$$ip_sort_hint = convert_ip_str_to_int(device.ip)

        device.linked_devices = []
        if ip_to_device_lut[device.ip] != undefined
            device.linked_devices = ip_to_device_lut[device.ip]

        device.$$first_seen_nmap_scan_date = "N/A"
        device.$$first_seen_timestamp = 0
        if device.first_seen_nmap_scan_date != null
            moment_time = moment(device.first_seen_nmap_scan_date)
            device.$$first_seen_nmap_scan_date = moment_time.format("YYYY-MM-DD HH:mm:ss")
            device.$$first_seen_timestamp = moment_time.unix()


    # network currently displayed
    network_display = {}

    # trees
    nw_tree = undefined
    domain_tree = undefined
    dispatcher_tree = undefined
    user_tree = undefined
    device_tree = undefined
    config_tree = undefined
    dispatcher_links = undefined
    nmap_scan_to_network_lut = {}
    nmap_scan_lut = {}
    nmap_scans_websocket = undefined

    selected_button_class = "btn btn-success"
    unselected_button_class = "btn btn-default"

    return {
        get_tabs: () ->
            return tabs

        fetch: (scope) ->
            # console.log "start fetch"
            defer = $q.defer()
            $q.all(
                [
                    icswNetworkTreeService.load(scope.$id)
                    icswDomainTreeService.load(scope.$id)
                    icswDispatcherSettingTreeService.load(scope.$id)
                    icswUserService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                    icswConfigTreeService.load(scope.$id)
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.DISCOVERY_DISPATCHER_LINK_LOADER
                            data:
                                model_name: "network"
                            dataType: "json"
                        }
                    )
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.NETWORK_NMAP_SCAN_DATA_LOADER
                            data:
                                simple: 1
                            dataType: "json"
                        }
                    )
                ]
            ).then(
                (data) ->
                    nw_tree = data[0]
                    domain_tree = data[1]
                    dispatcher_tree = data[2]
                    user_tree = data[3]
                    device_tree = data[4]
                    config_tree = data[5]
                    dispatcher_links = data[6]

                    device_tree.enrich_devices(
                        icswDeviceTreeHelperService.create(device_tree, device_tree.all_list)
                        ["network_info", "com_info"]
                    )

                    for network in nw_tree.nw_list
                        nmap_scan_to_network_lut[network.idx] = []

                    for nmap_scan in data[7]
                        salt_nmap_scan(nmap_scan)
                        nmap_scan_to_network_lut[nmap_scan.network].push(nmap_scan)
                        nmap_scan_lut[nmap_scan.idx] = nmap_scan

                    nmap_scans_websocket = icswWebSocketService.register_ws("nmap_scans")
                    nmap_scans_websocket.onmessage = (data) ->
                        nmap_scan = JSON.parse(data.data)
                        salt_nmap_scan(nmap_scan)

                        $timeout(
                            () ->
                                if nmap_scan_to_network_lut[nmap_scan.network] == undefined
                                    nmap_scan_to_network_lut[nmap_scan.network] = []

                                if nmap_scan_lut[nmap_scan.idx] == undefined
                                    nmap_scan_to_network_lut[nmap_scan.network].push(nmap_scan)
                                    nmap_scan_lut[nmap_scan.idx] = nmap_scan
                                else
                                    _.extend(nmap_scan_lut[nmap_scan.idx], nmap_scan)
                            0
                        )

                    scope.$on("$destroy", () ->
                        if nmap_scans_websocket?
                            nmap_scans_websocket.close()
                            nmap_scans_websocket = undefined
                    )

                    defer.resolve(nw_tree.nw_list)
            )
            return defer.promise

        # reload

        reload_networks: () ->
            reload_networks()
            hide_network()

        # rescan

        rescan_networks: () ->
            console.log "reimplement rescan"

        # access functions

        nw_tree: () ->
            return nw_tree

        domain_tree: () ->
            return domain_tree

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    identifier: "new network",
                    network_type: (entry.idx for entry in nw_tree.nw_type_list when entry.identifier == "o")[0]
                    enforce_unique_ips: true
                    num_ip: 0
                    gw_pri: 1
                }
            else
                dbu = new icswNetworkBackup()
                dbu.create_backup(obj_or_parent)
            scope.edit_obj = obj_or_parent
            sub_scope = scope.$new(false)
            sub_scope.dispatcher_tree = dispatcher_tree
            sub_scope.nmap_scan_devices = []
            sub_scope.create_mode = create

            icswConfigTreeService.load(scope.$id).then(
                (config_tree) ->
                    # add devices that are defined as "nmap-scan-device"
                    for config in config_tree.list
                        if config.name == "nmap-scan-device"
                            for obj in config.device_config_set
                                sub_scope.nmap_scan_devices.push(device_tree.all_lut[obj.device])

                    if scope.edit_obj.$$dispatchers == undefined
                        scope.edit_obj.$$dispatchers = []

                        for link in dispatcher_links
                            if scope.edit_obj.idx == link.object_id
                                scope.edit_obj.$$dispatchers.push(link.dispatcher_setting)
                                scope.edit_obj.$$scan_device = parseInt(link.schedule_handler_data)

                    icswComplexModalService(
                        {
                            message: $compile($templateCache.get("network.form"))(sub_scope)
                            title: "Network"
                            css_class: "modal-wide modal-form"
                            ok_label: if create then "Create" else "Modify"
                            closable: true
                            ok_callback: (modal) ->
                                d = $q.defer()
                                if sub_scope.form_data.$invalid
                                    toaster.pop("warning", "form validation problem", "")
                                    d.reject("form not valid")
                                else
                                    if create
                                        nw_tree.create_network(scope.edit_obj).then(
                                            (ok) ->
                                                d.resolve("created")
                                            (notok) ->
                                                d.reject("not created")
                                        )
                                    else
                                        scope.edit_obj.put().then(
                                            (ok) ->
                                                nw_tree.reorder()
                                                icswSimpleAjaxCall(
                                                    {
                                                        url: ICSW_URLS.DISCOVERY_DISPATCHER_LINK_SYNCER
                                                        data:
                                                            model_name: "network"
                                                            object_id: scope.edit_obj.idx
                                                            dispatcher_setting_ids: (idx for idx in scope.edit_obj.$$dispatchers)
                                                            schedule_handler: "network_scan_schedule_handler"
                                                            schedule_handler_data: "" + scope.edit_obj.$$scan_device
                                                            user_id: user_tree.user.idx
                                                        dataType: "json"
                                                    }
                                                ).then(
                                                    (ok) ->
                                                        d.resolve("updated")
                                                )
                                            (not_ok) ->
                                                d.reject("not updated")
                                        )

                                return d.promise
                            cancel_callback: (modal) ->
                                if not create
                                    dbu.restore_backup(obj_or_parent)
                                d = $q.defer()
                                d.resolve("cancel")
                                return d.promise
                        }
                    ).then(
                        (fin) ->
                            console.log "finish"
                            sub_scope.$destroy()
                    )
            )

        delete: (scope, event, nw) ->
            icswToolsSimpleModalService("Really delete Network #{nw.name} ?").then(
                () =>
                    nw_tree.delete_network(nw).then(
                        () ->
                            console.log "network deleted"
                    )
            )

        get_production_networks : () ->
            prod_idx = (entry for entry in nw_tree.nw_type_list when entry.identifier == "p")[0].idx
            return (entry for entry in nw_tree.nw_list when entry.network_type == prod_idx)

        is_slave_network : (nw_type) ->
            if nw_type
                return nw_tree.nw_type_lut[nw_type].identifier == "s"
            else
                return false

        has_master_network : (edit_obj) ->
            return if edit_obj.master_network then true else false

        get_master_network_id: (edit_obj) ->
            if edit_obj.master_network
                return nw_tree.nw_lut[edit_obj.master_network].identifier
            else
                return "---"

        preferred_dtn: (edit_obj) ->
            if edit_obj.preferred_domain_tree_node
                return domain_tree.lut[edit_obj.preferred_domain_tree_node].full_name
            else
                return "---"

        get_network_device_types: (edit_obj) ->
            if edit_obj.network_device_type.length
                return (nw_tree.nw_device_type_lut[nd].identifier for nd in edit_obj.network_device_type).join(", ")
            else
                return "---"

        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"

        network_display     : network_display

        hide_network : () ->
            return hide_network()

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
                $q.all(q_list).then(
                    (data) ->
                        iplist = data[0]
                        netdevices = icswTools.build_lut(data[1])
                        devices = icswTools.build_lut(data[2])
                        for entry in iplist
                            nd = netdevices[entry.netdevice]
                            entry.netdevice_name = nd.devname
                            entry.device_full_name = devices[nd.device].full_name
                        network_display.iplist = iplist
                )

        close_tab: (to_be_closed_tab) ->
            $timeout(
                () ->
                    tabs_tmp = []

                    for tab in tabs
                        if tab != to_be_closed_tab
                            tabs_tmp.push(tab)

                    tabs.length = 0
                    for tab in tabs_tmp
                        tabs.push(tab)
                0
            )

        create_new_detail_view_tab: (obj) ->
            new_network_display = {}

            new_network_display.active_network = obj
            q_list = [
                get_defer(Restangular.all(ICSW_URLS.REST_NET_IP_LIST.slice(1)).getList({"network" : obj.idx, "_order_by" : "ip"}))
                get_defer(Restangular.all(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).getList({"net_ip__network" : obj.idx}))
                get_defer(Restangular.all(ICSW_URLS.REST_DEVICE_LIST.slice(1)).getList({"netdevice__net_ip__network" : obj.idx}))
            ]
            $q.all(q_list).then(
                (data) ->
                    iplist = data[0]
                    netdevices = icswTools.build_lut(data[1])
                    devices = icswTools.build_lut(data[2])
                    for entry in iplist
                        nd = netdevices[entry.netdevice]
                        entry.netdevice_name = nd.devname
                        entry.device_full_name = devices[nd.device].full_name
                    new_network_display.iplist = iplist

                    if nmap_scan_to_network_lut[obj.idx] == undefined
                        nmap_scan_to_network_lut[obj.idx] = []

                    tab = {
                        heading: new_network_display.active_network.identifier
                        network_display: new_network_display
                        nmap_scans: nmap_scan_to_network_lut[obj.idx]
                        sub_tabs: []
                        show_difference_text: "Show Difference (select two scans)"
                        show_difference_disabled: true
                        selected_nmap_scans: 0
                        all_scans_filter_class: selected_button_class
                        successful_scans_filter_class: unselected_button_class
                        unsuccessful_filter_class: unselected_button_class
                    }

                    reset_selection = () ->
                        tab.selected_nmap_scans = 0
                        for nmap_scan in tab.nmap_scans
                            nmap_scan.$$selected = false

                    select_filter_button = (class_name) ->
                        tab.all_scans_filter_class = unselected_button_class
                        tab.successful_scans_filter_class = unselected_button_class
                        tab.unsuccessful_filter_class = unselected_button_class

                        tab[class_name] = selected_button_class

                    tab.apply_all_scans_filter = () ->
                        select_filter_button("all_scans_filter_class")
                        reset_selection()

                        for nmap_scan in tab.nmap_scans
                            nmap_scan.$$displayed = true

                    tab.apply_successful_scans_filter_class = () ->
                        select_filter_button("successful_scans_filter_class")
                        reset_selection()

                        for nmap_scan in tab.nmap_scans
                            nmap_scan.$$displayed = false
                            if nmap_scan.error_string == null
                                nmap_scan.$$displayed = true

                    tab.apply_unsuccessful_scans_filter_class = () ->
                        select_filter_button("unsuccessful_filter_class")
                        reset_selection()

                        for nmap_scan in tab.nmap_scans
                            nmap_scan.$$displayed = false
                            if nmap_scan.error_string != null
                                nmap_scan.$$displayed = true

                    tab.build_nmap_scan_error_tooltip = (nmap_scan) ->
                        if nmap_scan.error_string != null
                            info_f = [
                                "<div class='text-left'>",
                                nmap_scan.error_string,
                                "<div>"
                            ]
                            return info_f.join("")
                        return ""

                    tab.close_sub_tab = (to_be_closed_tab) ->
                        $timeout(
                            () ->
                                tabs_tmp = []

                                for sub_tab in tab.sub_tabs
                                    if sub_tab != to_be_closed_tab
                                        tabs_tmp.push(sub_tab)

                                tab.sub_tabs.length = 0
                                for sub_tab in tabs_tmp
                                    tab.sub_tabs.push(sub_tab)
                            0
                        )

                    tab.select_nmap_scan = (nmap_scan) ->
                        if nmap_scan.$$selected == undefined
                            nmap_scan.$$selected = true
                        else
                            nmap_scan.$$selected = !nmap_scan.$$selected

                        if nmap_scan.$$selected == true
                            tab.selected_nmap_scans += 1
                        else
                            tab.selected_nmap_scans -= 1

                        if tab.selected_nmap_scans == 2
                            tab.show_difference_text = "Show Difference"
                            tab.show_difference_disabled = false
                        else
                            tab.show_difference_text = "Show Difference (select two scans)"
                            tab.show_difference_disabled = true

                    tab.delete_selected_nmap_scans = () ->
                        nmap_scan_deletion_idx_list = []
                        for nmap_scan in tab.nmap_scans
                            if nmap_scan.$$selected == true
                                nmap_scan_deletion_idx_list.push(nmap_scan.idx)

                        blockUI.start("Please wait...")
                        icswSimpleAjaxCall(
                            {
                                url: ICSW_URLS.NETWORK_NMAP_SCAN_DELETER
                                data:
                                    idx_list: nmap_scan_deletion_idx_list
                                dataType: "json"
                            }
                        ).then(
                            (data) ->
                                new_nmap_scan_list = []
                                for nmap_scan in tab.nmap_scans
                                    if !(nmap_scan.idx in nmap_scan_deletion_idx_list)
                                        new_nmap_scan_list.push(nmap_scan)

                                console.log(new_nmap_scan_list)

                                tab.nmap_scans.length = 0
                                for nmap_scan in new_nmap_scan_list
                                    tab.nmap_scans.push(nmap_scan)

                                tab.selected_nmap_scans -= nmap_scan_deletion_idx_list.length

                                blockUI.stop()
                                toaster.pop("success", "", data.deleted + " Object(s) deleted.")
                        )


                    tab.select_all_nmap_scans = () ->
                        tab.selected_nmap_scans = 0
                        for nmap_scan in tab.nmap_scans
                            nmap_scan.$$selected = true
                            tab.selected_nmap_scans += 1

                    tab.unselect_all_nmap_scans = () ->
                        tab.selected_nmap_scans = 0
                        for nmap_scan in tab.nmap_scans
                            nmap_scan.$$selected = false

                    tab.inverse_select = () ->
                        tab.selected_nmap_scans = 0
                        for nmap_scan in tab.nmap_scans
                            if nmap_scan.$$selected == undefined
                                nmap_scan.$$selected = false
                            nmap_scan.$$selected = !nmap_scan.$$selected

                    tab.open_difference_sub_tab = () ->
                        scan_id_1 = undefined
                        scan_id_2 = undefined
                        for nmap_scan in tab.nmap_scans
                            if nmap_scan.$$selected == true && scan_id_1 == undefined
                                scan_id_1 = nmap_scan.idx
                            else if nmap_scan.$$selected == true && scan_id_2 == undefined
                                scan_id_2 = nmap_scan.idx
                                break

                        if scan_id_1 > scan_id_2
                            scan_id_old = scan_id_2
                            scan_id_new = scan_id_1
                        else
                            scan_id_old = scan_id_1
                            scan_id_new = scan_id_2

                        for sub_tab in tab.sub_tabs
                            if sub_tab.sub_tab_type == 2 && sub_tab.scan_id_old == scan_id_old && sub_tab.scan_id_new == scan_id_new
                                return

                        blockUI.start("Loading Data...")
                        icswSimpleAjaxCall(
                            {
                                url: ICSW_URLS.NETWORK_NMAP_SCAN_DIFF
                                data:
                                    scan_id_1: scan_id_1
                                    scan_id_2: scan_id_2
                                dataType: "json"
                            }
                        ).then((data) ->
                            ip_to_device_lut = {}
                            for device in device_tree.all_list
                                if !device.is_meta_device
                                    if device.netdevice_set != undefined
                                        for net_device in device.netdevice_set
                                            for net_ip in net_device.net_ip_set
                                                if ip_to_device_lut[net_ip.ip] == undefined
                                                    ip_to_device_lut[net_ip.ip] = []

                                                if !(device in ip_to_device_lut[net_ip.ip])
                                                  ip_to_device_lut[net_ip.ip].push(device)

                            for nmap_device in data["lost_devices"]
                                salt_nmap_device(nmap_device, ip_to_device_lut)

                            for nmap_device in data["added_devices"]
                                salt_nmap_device(nmap_device, ip_to_device_lut)

                            new_tab = {
                                sub_tab_type: 2
                                scan_id_old: scan_id_old
                                scan_id_new: scan_id_new
                                lost_devices: data["lost_devices"]
                                added_devices: data["added_devices"]
                            }
                            tab.sub_tabs.push(new_tab)

                            blockUI.stop()
                        )

                    dupe = false
                    for old_tab in tabs
                        if tab.heading == old_tab.heading
                            dupe = true
                            break
                    if !dupe
                        tabs.push(tab)
            )

        create_new_host_discovery_detail_sub_tab: (tab, index) ->
            for sub_tab in tab.sub_tabs
                if sub_tab.nmap_scan.index == index
                    return

            blockUI.start("Loading Data...")
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.NETWORK_NMAP_SCAN_DATA_LOADER
                    data:
                        simple: 0
                        nmap_scan_id: index
                    dataType: "json"
                }
            ).then((data) ->
                ip_to_device_lut = {}
                for device in device_tree.all_list
                    if !device.is_meta_device
                        if device.netdevice_set != undefined
                            for net_device in device.netdevice_set
                                for net_ip in net_device.net_ip_set
                                    if ip_to_device_lut[net_ip.ip] == undefined
                                        ip_to_device_lut[net_ip.ip] = []

                                    if !(device in ip_to_device_lut[net_ip.ip])
                                      ip_to_device_lut[net_ip.ip].push(device)

                mac_device_lut = {}

                for device in data.devices
                    salt_nmap_device(device, ip_to_device_lut)
                    if device.mac
                        mac_device_lut[device.mac] = device

                sub_tab = {
                    nmap_scan: {
                        index: index
                        runtime: data.runtime
                        devices_scanned: data.devices_scanned
                        scan_date: moment(data.date).format("YYYY-MM-DD HH:mm:ss")
                        matrix: data.matrix
                    }
                    ignored_devices: []
                    devices: []
                    display_devices: []
                    selected_devices: 0

                    linked_devices_button_value: "All Devices"
                    linked_devices_button_class: "btn btn-default"
                    linked_devices_button_state: 0

                    sub_tab_type: 0

                    all_devices_filter_class: selected_button_class
                    linked_only_filter_class: unselected_button_class
                    unlinked_only_filter_class: unselected_button_class
                    new_devices_last_scan_class: unselected_button_class
                    new_devices_alltime_class: unselected_button_class
                    ignored_devices_class: unselected_button_class
                    ignore_text: "Ignore Selection"
                }

                for nmap_device in data.devices
                    if nmap_device.ignored == true
                        sub_tab.ignored_devices.push(nmap_device)
                    else
                        sub_tab.devices.push(nmap_device)
                        sub_tab.display_devices.push(nmap_device)

                reset_selection = () ->
                    sub_tab.selected_devices = 0
                    for device in sub_tab.ignored_devices
                        device.$$selected = false
                    for device in sub_tab.devices
                        device.$$selected = false

                select_button = (class_name) ->
                    sub_tab.all_devices_filter_class = unselected_button_class
                    sub_tab.linked_only_filter_class = unselected_button_class
                    sub_tab.unlinked_only_filter_class = unselected_button_class
                    sub_tab.new_devices_last_scan_class = unselected_button_class
                    sub_tab.new_devices_alltime_class = unselected_button_class
                    sub_tab.ignored_devices_class = unselected_button_class

                    if class_name == "ignored_devices_class"
                        sub_tab.ignore_text = "Unignore Selection"
                    else
                        sub_tab.ignore_text = "Ignore Selection"

                    sub_tab[class_name] = selected_button_class


                sub_tab.select_all_nmap_devices = () ->
                    sub_tab.selected_devices = sub_tab.display_devices.length
                    for nmap_device in sub_tab.display_devices
                        nmap_device.$$selected = true

                sub_tab.unselect_all_nmap_devices = () ->
                    sub_tab.selected_devices = 0
                    for nmap_device in sub_tab.display_devices
                        nmap_device.$$selected = false

                sub_tab.select_all_unlinked_nmap_devices = () ->
                    sub_tab.selected_devices = 0
                    for nmap_device in sub_tab.display_devices
                        nmap_device.$$selected = false
                        if nmap_device.linked_devices.length == 0
                            nmap_device.$$selected = true
                            sub_tab.selected_devices += 1

                sub_tab.select_all_linked_nmap_devices = () ->
                    sub_tab.selected_devices = 0
                    for nmap_device in sub_tab.display_devices
                        nmap_device.$$selected = false
                        if nmap_device.linked_devices.length > 0
                            nmap_device.$$selected = true
                            sub_tab.selected_devices += 1

                sub_tab.select_nmap_scan_device = (obj) ->
                    if obj.$$selected == undefined
                        obj.$$selected = true
                    else
                        obj.$$selected = !obj.$$selected

                    if obj.$$selected == true
                        sub_tab.selected_devices += 1
                    else
                        sub_tab.selected_devices -= 1


                sub_tab.show_all_devices_filter = () ->
                    select_button("all_devices_filter_class")
                    reset_selection()

                    sub_tab.display_devices.length = 0

                    for device in sub_tab.devices
                        sub_tab.display_devices.push(device)

                sub_tab.show_linked_devices_only_filter = () ->
                    select_button("linked_only_filter_class")
                    reset_selection()

                    sub_tab.display_devices.length = 0

                    for device in sub_tab.devices
                        if device.linked_devices.length > 0
                            sub_tab.display_devices.push(device)

                sub_tab.show_unlinked_devices_only_filter = () ->
                    select_button("unlinked_only_filter_class")
                    reset_selection()

                    sub_tab.display_devices.length = 0

                    for device in sub_tab.devices
                        if device.linked_devices.length == 0
                            sub_tab.display_devices.push(device)

                sub_tab.show_new_devices_since_last_scan = () ->
                    select_button("new_devices_last_scan_class")
                    reset_selection()

                    sub_tab.display_devices.length = 0
                    blockUI.start("Loading Data...")

                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.NETWORK_NMAP_SCAN_DIFF
                            data:
                                scan_id: index
                                last_scan: true
                            dataType: "json"
                        }
                    ).then((data) ->
                        for nmap_device in data
                            if !nmap_device.ignored
                                if nmap_device.mac
                                    sub_tab.display_devices.push(mac_device_lut[nmap_device.mac])
                                else
                                    salt_nmap_device(nmap_device, ip_to_device_lut)
                                    sub_tab.display_devices.push(nmap_device)

                        blockUI.stop()
                    )

                sub_tab.show_new_devices_alltime = () ->
                    select_button("new_devices_alltime_class")
                    reset_selection()

                    sub_tab.linked_devices_button_state = 0
                    sub_tab.linked_devices_button_value = "New Devices (Alltime/Never Seen)"
                    sub_tab.display_devices.length = 0
                    blockUI.start("Loading Data...")

                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.NETWORK_NMAP_SCAN_DIFF
                            data:
                                scan_id: index
                                all_time: true
                            dataType: "json"
                        }
                    ).then((data) ->
                        for nmap_device in data
                            if !nmap_device.ignored
                                if nmap_device.mac
                                    sub_tab.display_devices.push(mac_device_lut[nmap_device.mac])
                                else
                                    salt_nmap_device(nmap_device, ip_to_device_lut)
                                    sub_tab.display_devices.push(nmap_device)

                        blockUI.stop()
                    )

                sub_tab.show_ignored_devices = () ->
                    select_button("ignored_devices_class")
                    reset_selection()

                    sub_tab.display_devices.length = 0

                    for device in sub_tab.ignored_devices
                        sub_tab.display_devices.push(device)

                sub_tab.handle_selection = () ->
                    blockUI.start("Please wait...")
                    mac_list = []
                    handled_devices = []
                    for device in sub_tab.devices
                        if device.$$selected == true
                            if device.mac != null
                                mac_list.push(device.mac)
                                handled_devices.push(device)
                    for device in sub_tab.ignored_devices
                        if device.$$selected == true
                            if device.mac != null
                                mac_list.push(device.mac)
                                handled_devices.push(device)

                    ignore_mode = 0
                    if sub_tab.ignore_text == "Ignore Selection"
                        ignore_mode = 1

                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.NETWORK_HANDLE_NMAP_SCAN_DEVICE
                            data:
                                nmap_scan_idx: sub_tab.nmap_scan.index
                                mac_list: mac_list
                                ignore: ignore_mode
                            dataType: "json"
                        }
                    ).then((data) ->
                        sub_tab.display_devices = (device for device in sub_tab.display_devices when !(device in handled_devices))
                        for device in sub_tab.display_devices
                            device.$$selected = false

                        for device in handled_devices
                            if ignore_mode == 0
                                device.ignored = false
                            else
                                device.ignored = true

                        all_devices = []
                        for device in sub_tab.ignored_devices
                            all_devices.push(device)
                        for device in sub_tab.devices
                            all_devices.push(device)

                        sub_tab.ignored_devices = (device for device in all_devices when device.ignored)
                        sub_tab.devices = (device for device in all_devices when !device.ignored)
                        sub_tab.selected_devices = 0

                        sub_tab.nmap_scan.matrix = data

                        blockUI.stop()
                    )

                sub_tab.bulk_create = () ->
                    to_be_created_devices = []
                    for device in sub_tab.devices
                        if device.$$selected == true
                            to_be_created_devices.push(device)

                    for device in sub_tab.ignored_devices
                        if device.$$selected == true
                            to_be_created_devices.push(device)

                    new_sub_tab = {
                        device_info: to_be_created_devices
                        sub_tab_type: 1
                    }

                    tab.sub_tabs.push(new_sub_tab)


                sub_tab.show_device = ($event, dev) ->
                    DeviceOverviewService($event, [dev])

                tab.sub_tabs.push(sub_tab)
                blockUI.stop()
            )

        create_new_create_device_sub_tab: (tab, device_info) ->
            sub_tab = {
                device_info: [device_info]
                sub_tab_type: 1
            }

            tab.sub_tabs.push(sub_tab)

        # range functions
        autorange_set : (edit_obj) ->
            if edit_obj.start_range == "0.0.0.0" and edit_obj.end_range == "0.0.0.0"
                return false
            else
                return true

        clear_range : (edit_obj) ->
            edit_obj.start_range = "0.0.0.0"
            edit_obj.end_range = "0.0.0.0"

        enter_range : (edit_obj) ->
            # click on range field
            sr = edit_obj.start_range
            er = edit_obj.end_range
            if (not sr and not er) or (sr == "0.0.0.0" and er == "0.0.0.0")
                sr = ip2long(edit_obj.network) + 1
                er = ip2long(edit_obj.network) + (4294967295 - ip2long(edit_obj.netmask)) - 1
                # range valid, set
                if sr < er
                    edit_obj.start_range = long2ip(sr)
                    edit_obj.end_range = long2ip(er)

        range_check : (edit_obj) ->
            # check the range parameters
            sr = edit_obj.start_range
            er = edit_obj.end_range
            if sr and er
                sr = ip2long(sr)
                er = ip2long(er)
                min = ip2long(edit_obj.network) + 1
                max = ip2long(edit_obj.network) + (4294967295 - ip2long(edit_obj.netmask)) - 1
                # todo, improve checks

        # autocomplete network settings

        network_or_netmask_blur : (edit_obj) ->
            # calculate broadcast and gateway automatically

            # validation ensures that if it is not undefined, then it is a valid entry
            if edit_obj.network? and edit_obj.netmask?

                ip_long = ip2long(edit_obj.network)
                mask_long = ip2long(edit_obj.netmask)

                base_long = ip_long & mask_long
                bcast_long = (ip_long & mask_long) | (4294967295 - mask_long)

                # only set if there is no previous value
                if ! edit_obj.broadcast?
                    edit_obj.broadcast = long2ip(bcast_long)
                if ! edit_obj.gateway?
                    edit_obj.gateway = long2ip(base_long)
    }
])
