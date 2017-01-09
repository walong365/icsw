# Copyright (C) 2016 init.at
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

# asset related backend functions

device_asset_module = angular.module(
    "icsw.backend.asset",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ngCsv"
    ]
).service("icswAssetPackageTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswAssetHelperFunctions", "icswTools",
(
    $q, Restangular, ICSW_URLS, icswAssetHelperFunctions, icswTools,
) ->
    class icswAssetPackageTree
        constructor: (list) ->
            @list = []
            @version_list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            @version_list.length = 0
            for entry in list
                @list.push(entry)
                for vers in entry.assetpackageversion_set
                    @version_list.push(vers)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @version_lut = _.keyBy(@version_list, "idx")
            @link()

        link: () =>
            # DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            # _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @list
                entry.$$num_versions = entry.assetpackageversion_set.length
                entry.$$package_type = icswAssetHelperFunctions.resolve("package_type", entry.package_type)
                entry.$$expanded = false
                entry.$$created = moment(entry.created).format("YYYY-MM-DD HH:mm:ss")
                for vers in entry.assetpackageversion_set
                    vers.$$release = "N/A"
                    if vers.release
                        vers.$$release = vers.release
                    vers.$$info = "N/A"
                    if vers.info
                        vers.$$info = vers.info
                    vers.$$package = entry
                    vers.$$created = moment(vers.created).format("YYYY-MM-DD HH:mm:ss")
                    vers.$$size = icswTools.get_size_str(vers.size, 1024, "Byte")


]).service("icswAssetPackageTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswTools",
    "icswAssetPackageTree", "icswTreeBase",
(
    $q, Restangular, ICSW_URLS, $window, icswTools,
    icswAssetPackageTree, icswTreeBase,
) ->
    rest_map = [
        # asset packages
        ICSW_URLS.ASSET_GET_ALL_ASSET_PACKAGES
    ]
    return new icswTreeBase(
        "AssetPackageTree"
        icswAssetPackageTree
        rest_map
        ""
    )
]).service("icswAssetHelperFunctions",
[
    "$q",
(
    $q,
) ->
    info_dict = {
        asset_type: [
            [1, "Package", ""]
            [2, "Hardware", ""]
            [3, "License", ""]
            [4, "Update", ""]
            [5, "LSHW", ""]
            [6, "Process", ""]
            [7, "Pending update", ""]
            [8, "DMI", ""],
            [9, "PCI", ""],
            [10, "Windows Hardware", ""]
        ]
        package_type: [
            [1, "Windows", ""]
            [2, "Linux", ""]
        ]
        run_status: [
            [1, "Planned", ""]
            [2, "Running", "success"]
            [3, "Ended", ""]
        ]
        run_result: [
            [1, "Unknown", "warning"]
            [2, "Success", "success"]
            [3, "Success", "success"]
            [4, "Failed", "danger"]
            [5, "Canceled", "warning"]
        ]
        schedule_source: [
            [1, "SNMP", ""]
            [2, "ASU", ""]
            [3, "IPMI", ""]
            [4, "Package", ""]
            [5, "Hardware", ""]
            [6, "License", ""]
            [7, "Update", ""]
            [8, "Software Version", ""]
            [9, "Process", ""]
            [10, "Pending update", ""]
        ]
    }

    # create forward and backward resolves

    res_dict = {}
    for name, _list of info_dict
        res_dict[name] = {}
        for [_idx, _str, _class] in _list
            # forward resolve
            res_dict[name][_idx] = [_str, _class]
            # backward resolve
            res_dict[name][_str] = [_idx, _class]
            res_dict[name][_.lowerCase(_str)] = [_idx, _class]

    _resolve = (name, key, idx) ->
        if name of res_dict
            if key of res_dict[name]
                return res_dict[name][key][idx]
            else
                console.error "unknown key '#{key}' for name '#{name}' in resolve()"
                return "???"
        else
            console.error "unknown name '#{name}' in resolve()"
            return "????"

    return {
        resolve: (name, key) ->
            return _resolve(name, key, 0)

        get_class: (name, key) ->
            return _resolve(name, key, 1)
    }
]).service("icswStaticAssetTemplateTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswTools", "icswSimpleAjaxCall", "icswStaticAssetFunctions",
(
    $q, Restangular, ICSW_URLS, icswTools, icswSimpleAjaxCall, icswStaticAssetFunctions,
) ->
    class icswStaticAssetTemplateTree
        constructor: (list) ->
            @list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            # field lut
            @field_lut = {}
            @static_asset_type_lut = {}

            for static_asset_template in @list
                if @static_asset_type_lut[static_asset_template.type] == undefined
                    @static_asset_type_lut[static_asset_template.type] = []

                @static_asset_type_lut[static_asset_template.type].push(static_asset_template)

            for _template in @list
                for _field in _template.staticassettemplatefield_set
                    @field_lut[_field.idx] = _field
            @static_asset_type_keys = _.keys(@static_asset_type_lut)
            @static_asset_type_keys.sort()
            # list of (type, template_list) tuples
            @static_assets = []
            for _key in @static_asset_type_keys
                @static_assets.push([_key, @static_asset_type_lut[_key]])
            @num_enabled = (true for entry in @list when entry.enabled).length
            @link()

        link: () =>
            # DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            # _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @list
                @salt_template(entry)

        salt_template: (entry) =>
            # console.log(entry)
            entry.$$num_fields = entry.staticassettemplatefield_set.length
            entry.refs_content = "..."
            entry.num_refs = 0
            entry.$$created = moment(entry.date).format("YYYY-MM-DD HH:mm:ss")
            for field in entry.staticassettemplatefield_set
                @salt_field(field)
            @reorder_template(entry)

        move_field: (template, field, up) =>
            defer = $q.defer()
            cur_idx = field.ordering
            if up
                new_idx = cur_idx - 1
            else
                new_idx = cur_idx + 1
            swap_field = (_field for _field in template.staticassettemplatefield_set when _field.ordering == new_idx)[0]
            swap_field.ordering = cur_idx
            field.ordering = new_idx
            @reorder_template(template)
            Restangular.all(ICSW_URLS.ASSET_REORDER_TEMPLATE_FIELDS.slice(1)).post(
                {
                    field1: field.idx
                    field2: swap_field.idx
                }
            ).then(
                (done) =>
                    @reorder_template(template)
                    defer.resolve("done")
            )
            return defer.promise

        reorder_template: (entry) =>
            # sort fields according to ordering
            icswTools.order_in_place(
                entry.staticassettemplatefield_set
                ["ordering"]
                ["asc"]
            )

        salt_field: (field) =>
            # salt static asset template field
            field.$$field_type = icswStaticAssetFunctions.resolve("field_type", field.field_type)
            if field.field_type == 1 and field.consumable
                field.$$monitor_ok = true
            else if field.field_type == 3 and field.date_check
                field.$$monitor_ok = true
            else
                field.$$monitor_ok = false
            if field.has_bounds and not field.value_int_lower_bound?
                field.value_int_lower_bound = 0
                field.value_int_upper_bound = 1
            if field.consumable and not field.consumable_start_value?
                field.consumable_start_value = 10
                field.consumable_warn_value = 4
                field.consumable_critical_value = 4
            icswStaticAssetFunctions.get_default_value(field)

        add_references: () =>
            Restangular.all(ICSW_URLS.ASSET_GET_STATIC_TEMPLATE_REFERENCES.slice(1)).getList().then(
                (data) =>
                    _info_dict = {}
                    for entry in data
                        if entry.static_asset_template not of _info_dict
                            _info_dict[entry.static_asset_template] = []
                        _info_dict[entry.static_asset_template].push(entry.device_name)
                    for key, value of _info_dict
                        @lut[key].num_refs = value.length
                        @lut[key].refs_content = value.join(", ")
            )

        copy_template: (src_obj, new_obj, create_user) =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.ASSET_COPY_STATIC_TEMPLATE
                    data:
                        new_obj: angular.toJson(new_obj)
                        src_idx: src_obj.idx
                        user_idx: create_user.idx
                    dataType: "json"
                }
            ).then(
                (result) =>
                    console.log "Result", result
                    @list.push(result)
                    @build_luts()
                    defer.resolve("created")
                (error) ->
                    defer.reject("not created")
            )
            return defer.promise

        create_template: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.ASSET_CREATE_STATIC_ASSET_TEMPLATE.slice(1)).post(new_obj).then(
                (created) =>
                    @list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_template: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@list, (entry) -> return entry.idx == del_obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        delete_field: (template, field) =>
            d = $q.defer()
            #noinspection JSUnresolvedVariable
            Restangular.restangularizeElement(null, field, ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_FIELD_DETAIL.slice(1).slice(0, -2))
            field.remove(null, {"Content-Type": "application/json"}).then(
                (ok) =>
                    _.remove(template.staticassettemplatefield_set, (entry) -> return entry.idx == field.idx)
                    @salt_template(template)
                    d.resolve("ok")
                (notok) ->
                    d.reject("not ok")
            )
            return d.promise

        update_field: (template, field) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, field, ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_FIELD_DETAIL.slice(1).slice(0, -2))
            field.put(null, {"Content-Type": "application/json"}).then(
                (new_field) =>
                    _.remove(template.staticassettemplatefield_set, (entry) -> return entry.idx == field.idx)
                    template.staticassettemplatefield_set.push(new_field)
                    @field_lut[new_field.idx] = new_field
                    @salt_template(template)
                    d.resolve("ok")
                (notok) ->
                    d.reject("not ok")
            )
            return d.promise

        create_field: (template, field) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_FIELD_CALL.slice(1)).post(field).then(
                (new_field) =>
                    template.staticassettemplatefield_set.push(new_field)
                    @salt_template(template)
                    d.resolve("ok")
                (notok) ->
                    d.reject("not ok")
            )
            return d.promise

        # device related calls
        build_asset_struct: (device, asset_struct) =>
            if asset_struct.to_remove?
                # already init, reset
                asset_struct.to_remove.length = 0
                asset_struct.to_add_single.length = 0
                asset_struct.to_add_multi.length = 0
            else
                # not init, add fields
                # staticassets which can be removed
                asset_struct.to_remove = []
                # templates which can be added (single instance)
                asset_struct.to_add_single = []
                # templates which can be added (multiple instance)
                asset_struct.to_add_multi = []
            # number of assets set
            asset_struct.num_set = 0
            # number available (not set or templates which allow multiple instances)
            asset_struct.num_available = 0
            # return populated asset struture
            _asset_lut = {}
            for _as in device.staticasset_set
                asset_struct.num_set++
                # salt it
                @salt_device_asset(_as)
                _as_idx = _as.static_asset_template
                if _as_idx not of _asset_lut
                    # for static asset templates where multiple instances are allowed
                    _asset_lut[_as_idx] = []
                _asset_lut[_as_idx].push(_as)
                asset_struct.to_remove.push(_as)
            # console.log "* asset_struct=", asset_struct

            for _asset in @list
                # console.log "a=", _asset
                if _asset.enabled
                    if _asset.multi
                        asset_struct.to_add_multi.push(_asset)
                        asset_struct.num_available++
                    else if _asset.idx not of _asset_lut
                        asset_struct.to_add_single.push(_asset)
                        asset_struct.num_available++

        salt_device_asset: (as) =>
            # salts StaticAsset of device
            as.$$static_asset_template = @lut[as.static_asset_template]
            as.$$template_name = as.$$static_asset_template.name
            as.$$template_type = as.$$static_asset_template.type
            _used_fields = []
            for _f in as.staticassetfieldvalue_set
                _f.$$field = @field_lut[_f.static_asset_template_field]
                _f.$$ordering = _f.$$field.ordering
                # console.log _f.static_asset_template_field, _f.$$field.name, _f.$$field.fixed, _f.$$field.show_in_overview
                _f.$$field_type_str = icswStaticAssetFunctions.resolve("field_type", _f.$$field.field_type)
                _used_fields.push(_f.$$field.idx)
            _unused_fields = []
            for _f in @lut[as.static_asset_template].staticassettemplatefield_set
                if _f.optional and _f.idx not in _used_fields
                    _unused_fields.push(_f)
            as.$$unused_fields = _unused_fields
            # order
            icswTools.order_in_place(
                as.staticassetfieldvalue_set
                ["$$ordering"]
                ["asc"]
            )

            info_f = []
            for _f in as.staticassetfieldvalue_set
                if _f.$$field.show_in_overview
                    info_f.push(_f.$$field.name + "=" + @get_field_display_value(_f, _f.$$field))
            if info_f.length
                as.$$field_info = info_f.join(", ")
            else
                as.$$field_info = "---"

        remove_device_asset_field: (asset, field) =>
            defer = $q.defer()
            Restangular.restangularizeElement(null, field, ICSW_URLS.ASSET_DEVICE_ASSET_FIELD_DETAIL.slice(1).slice(0, -2))
            field.remove().then(
                (ok) =>
                    _.remove(asset.staticassetfieldvalue_set, (entry) -> return entry.idx == field.idx)
                    @salt_device_asset(asset)
                    defer.resolve("deleted")
            )
            return defer.promise

        get_field_display_value: (field, temp_field) =>
            # console.log icswStaticAssetFunctions.resolve("field_type", temp_field.field_type)
            if temp_field.field_type == 1
                # integer
                return "#{field.value_int}"
            else if temp_field.field_type == 2
                # string
                return field.value_str
            else if temp_field.field_type == 3
                return moment(field.value_date).format("DD.MM.YYYY")
            else if temp_field.field_type == 4
                return field.value_text
            else
                return "Unknown field type #{temp_field.field_type}"

]).service("icswStaticAssetTemplateTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswTools",
    "icswStaticAssetTemplateTree", "$rootScope", "ICSW_SIGNALS", "icswTreeBase",
(
    $q, Restangular, ICSW_URLS, $window, icswTools,
    icswStaticAssetTemplateTree, $rootScope, ICSW_SIGNALS, icswTreeBase,
) ->
    rest_map = [
        ICSW_URLS.ASSET_GET_STATIC_TEMPLATES
    ]
    return new icswTreeBase(
        "StaticAssetTemplateTree"
        icswStaticAssetTemplateTree
        rest_map
        ""
    )
])
