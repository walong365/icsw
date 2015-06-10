# Copyright (C) 2015 init.at
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

angular.module(
    "icsw.config.kpi",
    [
        "icsw.tools.utils", "icsw.d3", "icsw.config.kpi_visualisation", "angular-ladda"
    ]
).controller("icswConfigKpiCtrl", [
    "$scope", "ICSW_URLS", "icswConfigKpiDataService", "$timeout", "access_level_service"
    ($scope, ICSW_URLS, icswConfigKpiDataService, $timeout, access_level_service) ->
        access_level_service.install($scope)

        cur_edit_kpi = undefined

        $scope.get_cur_edit_kpi = () ->
            return cur_edit_kpi
        this.get_cur_edit_kpi = $scope.get_cur_edit_kpi

        $scope.load_kpi = (idx) ->
            # load kpi from db into cur_edit_kpi
            cur_edit_kpi = $scope.get_kpi(idx)
            cur_edit_kpi.selected_device_monitoring_category_tuple = []

            for entry in _.filter(icswConfigKpiDataService.selected_device_monitoring_category_tuple, (elem) -> return elem.kpi == idx)
                cur_edit_kpi.selected_device_monitoring_category_tuple.push(
                    [entry.device_category, entry.monitoring_category]
                )

        #$timeout(
        #    () -> $scope.load_kpi(18)
        #    2000
        #)

        icswConfigKpiDataService.add_to_scope($scope)

]).directive("icswConfigKpi",
    ["$compile", "$templateCache", "icswConfigKpiDataService", "icswConfigKpiDialogService",
    ($compile, $templateCache, icswConfigKpiDataService, icswConfigKpiDialogService) ->
        return {
            restrict : "E"
            templateUrl: "icsw.config.kpi"
            controller: 'icswConfigKpiCtrl'
            link: (scope, el, attrs) ->
                scope.create_new_kpi = () ->
                    icswConfigKpiDialogService.show_create_kpi_dlg(scope)
    }
]).directive("icswConfigKpiDevMonSelection", ['icswConfigKpiDataService', (icswConfigKpiDataService) ->
    return {
        restrict : "E"
        templateUrl: "icsw.config.kpi.dev_mon_selection"
        scope: false
        link: (scope, el, attrs) ->
            scope.show_all_selected_categories = () ->
                for tup in scope.cur_edit_kpi.selected_device_monitoring_category_tuple
                    if ! _.contains(scope.cur_edit_kpi.available_device_categories, tup[0])
                        scope.cur_edit_kpi.available_device_categories.push(tup[0])
                    if ! _.contains(scope.cur_edit_kpi.available_monitoring_categories, tup[1])
                        scope.cur_edit_kpi.available_monitoring_categories.push(tup[1])
                scope._rebuild_tree()

            class base_tree_config extends tree_config
                constructor: (@scope, args) ->
                    super(args)
                    @show_selection_buttons = false
                    @show_icons = false
                    @show_select = true
                    @show_descendants = true
                    @show_childs = false
                get_name : (t_entry) ->
                    cat = t_entry.obj
                    if cat.depth > 1
                        r_info = "#{cat.full_name} (#{cat.name})"
                    else if cat.depth
                        r_info = cat.full_name
                    else
                        r_info = "TOP"
                    return r_info
                handle_click: (entry, event) =>
                    return  # TODO: also select?
                selection_changed: (entry) =>
                    # update selection in model
                    if entry.selected
                        # entry might already be contained if gui information is not present
                        if !_.contains(@get_category_list(), entry.obj.idx)
                            @get_category_list().push(entry.obj.idx)
                    else
                        _.remove(@get_category_list(), (rem_item) -> return rem_item == entry.obj.idx)

            class device_category_tree_config extends base_tree_config
                get_category_list: () ->
                    return scope.cur_edit_kpi.available_device_categories
            class monitoring_category_tree_config extends base_tree_config
                get_category_list: () ->
                    return scope.cur_edit_kpi.available_monitoring_categories

            scope.device_category_tree = new device_category_tree_config()
            scope.monitoring_category_tree = new monitoring_category_tree_config()

            scope.$watch(
                () -> icswConfigKpiDataService.category.length
                () -> scope._rebuild_tree()
            )

            scope._rebuild_tree = () ->
                scope.device_category_tree.clear_root_nodes()
                scope.monitoring_category_tree = new monitoring_category_tree_config()
                roots = []
                lut = {}
                for entry in icswConfigKpiDataService.category
                    lut[entry.idx] = entry
                    entry.children = []
                    if entry.parent
                        lut[entry.parent].children.push(entry)
                    else
                        roots.push(entry)

                add_to_tree_rec = (tree, node, sel_list) ->
                    _do_add_to_tree = (tree, node) ->
                        t_entry = tree.new_node({folder:false, obj:node, expand: true, selected: node.idx in sel_list})
                        for child in node.children
                            t_child = _do_add_to_tree(tree, child)
                            t_entry.add_child(t_child)
                        return t_entry
                    t_root = _do_add_to_tree(tree, node)
                    tree.add_root_node(t_root)

                for root in roots
                    # first level of children are relevant 'roots', i.e. devices, mon, loc, etc
                    for entry in root.children
                        if entry.name == 'device'
                            add_to_tree_rec(scope.device_category_tree, entry, scope.cur_edit_kpi.available_device_categories)
                        if entry.name == 'mon'
                            add_to_tree_rec(scope.monitoring_category_tree, entry, scope.cur_edit_kpi.available_monitoring_categories)
    }
]).directive("icswConfigKpiDevMonLinker", ['icswConfigKpiDataService', (icswConfigKpiDataService) ->
    return {
        restrict : "E"
        templateUrl: "icsw.config.kpi.dev_mon_linker"
        link: (scope, el, attrs) ->
    }
]).directive("icswConfigKpiConfigurationTable",
    ["icswConfigKpiDataService", "icswConfigKpiDialogService", "icswToolsSimpleModalService", "blockUI",
    (icswConfigKpiDataService, icswConfigKpiDialogService, icswToolsSimpleModalService, blockUI) ->
        return {
            restrict : "E"
            templateUrl: "icsw.config.kpi.configuration_table"
            link: (scope, el, attrs) ->
                icswConfigKpiDataService.add_to_scope(scope)
                blockUI.start()
                icswConfigKpiDataService.get_initial_load_promise().then(() ->
                    blockUI.stop()
                )
                scope.modify_kpi = (kpi) ->
                    icswConfigKpiDialogService.show_modify_kpi_dlg(scope, kpi)
                scope.delete_kpi = (kpi) ->
                    icswToolsSimpleModalService("Do you really want to delete the kpi #{kpi.name}?").then(() ->
                        delete kpi.result  # results is a circular structure
                        kpi.remove().then(() ->
                            _.remove(icswConfigKpiDataService.kpi, kpi)
                        )
                    )
                scope.get_result_from_kpi_entry = (kpi) ->
                    if kpi.result and kpi.result.json.objects.length > 0
                        results = []
                        for kpi_obj in kpi.result.json.objects
                            if kpi_obj.result?
                                results.push(kpi_obj.result)
                        return results.join(",")
                    else
                        return "unknown"
        }

]).service("icswConfigKpiDialogService",
    ["$compile", "$templateCache", "icswConfigKpiDataService", "icswCallAjaxService", "ICSW_URLS", "icswParseXMLResponseService",
    ($compile, $templateCache, icswConfigKpiDataService, icswCallAjaxService, ICSW_URLS, icswParseXMLResponseService) ->

        KPI_DLG_MODE_CREATE = 'create'
        KPI_DLG_MODE_MODIFY = 'modify'

        show_kpi_dlg = (scope, orig_kpi, mode) ->
            if mode == KPI_DLG_MODE_CREATE
                cur_edit_kpi = orig_kpi
            else if mode == KPI_DLG_MODE_MODIFY
                cur_edit_kpi = angular.copy(orig_kpi)
            else
                console.error 'invalid mode', mode

            child_scope = scope.$new()
            child_scope.mode = mode
            child_scope.cur_edit_kpi = cur_edit_kpi

            child_scope.editorOptions = {
                lineWrapping : false
                lineNumbers: true
                mode:
                    name : "python"
                    version : 2
                matchBrackets: true
                styleActiveLine: true
                indentUnit : 4
            }

            update_kpi_data_source = () ->
                icswCallAjaxService
                    url: ICSW_URLS.BASE_GET_KPI_SOURCE_DATA
                    data:
                        dev_mon_cat_tuples: JSON.stringify(cur_edit_kpi.selected_device_monitoring_category_tuple)
                        time_range: JSON.stringify(cur_edit_kpi.time_range)
                        time_range_parameter: JSON.stringify(cur_edit_kpi.time_range_parameter)
                    success: (xml) ->
                        if icswParseXMLResponseService(xml)
                            res = angular.fromJson($(xml).find("value[name='response']").text())
                            scope.selected_cats_kpi_set = res
            update_kpi_data_source()

            child_scope.on_data_source_tab_selected = () ->
                update_kpi_data_source()

            child_scope.is_checked = (dev_cat_id, mon_cat_id) ->
                return _.some(cur_edit_kpi.selected_device_monitoring_category_tuple, (elem) -> return elem[0] == dev_cat_id and elem[1] == mon_cat_id)
            child_scope.toggle_dev_mon_cat = (dev_cat_id, mon_cat_id) ->
                elem = [dev_cat_id, mon_cat_id]
                if child_scope.is_checked(dev_cat_id, mon_cat_id)
                    _.remove(cur_edit_kpi.selected_device_monitoring_category_tuple, elem)
                else
                    cur_edit_kpi.selected_device_monitoring_category_tuple.push(elem)

                update_kpi_data_source()

            child_scope.submit_kpi = () ->
                create_data_source_tuple = (obj, tup) ->
                    return {
                        kpi: obj.idx
                        device_category: tup[0]
                        monitoring_category: tup[1]
                    }

                cur_edit_kpi.gui_selected_categories = JSON.stringify({
                    dev_cat: cur_edit_kpi.available_device_categories
                    mon_cat: cur_edit_kpi.available_monitoring_categories
                })

                if mode == KPI_DLG_MODE_CREATE
                    icswConfigKpiDataService.kpi.post(cur_edit_kpi).then((obj) ->
                        icswConfigKpiDataService.kpi.push(obj)

                        for tup in cur_edit_kpi.selected_device_monitoring_category_tuple
                            entry = create_data_source_tuple(obj, tup)
                            icswConfigKpiDataService.kpi_data_source_tuple.post(entry, {silent: 1}).then(
                                (obj) -> icswConfigKpiDataService.kpi_data_source_tuple.push(obj)
                            )
                    )
                else if mode == KPI_DLG_MODE_MODIFY
                    for new_tup in cur_edit_kpi.selected_device_monitoring_category_tuple
                        if _.find(orig_kpi.selected_device_monitoring_category_tuple, new_tup) == undefined
                            entry = create_data_source_tuple(cur_edit_kpi, new_tup)
                            icswConfigKpiDataService.kpi_data_source_tuple.post(entry, {silent: 1}).then(
                                (obj) -> icswConfigKpiDataService.kpi_data_source_tuple.push(obj)
                            )

                    for old_tup in orig_kpi.selected_device_monitoring_category_tuple
                        if _.find(cur_edit_kpi.selected_device_monitoring_category_tuple, old_tup) == undefined
                            rest_elem = _.find(icswConfigKpiDataService.kpi_data_source_tuple,
                                              (elem) -> return elem.device_category == old_tup[0] && elem.monitoring_category == old_tup[1])
                            if rest_elem?
                                rest_elem.remove()
                                _.remove(icswConfigKpiDataService.kpi_data_source_tuple, rest_elem)

                    # put seems to only work on original obj, but we want to update data here anyway
                    for k, v of cur_edit_kpi
                        orig_kpi[k] = v

                    delete orig_kpi.result  # don't want to put this, possibly remove it from here
                    #delete orig_kpi.selected_device_monitoring_category_tuple
                    orig_kpi.put()

                else
                    console.error "invalid mode: ", mode

                child_scope.modal.close()

            child_scope.kpi_set = undefined


            set_kpi_result_to_default = () ->
                child_scope.kpi_result = {
                    kpi_set: undefined
                    kpi_error_report: undefined
                    loading: false
                }
            set_kpi_result_to_default()

            child_scope.calculate_kpi = () ->
                kpi_serialized = {}
                key_obj = if cur_edit_kpi.plain? then cur_edit_kpi.plain() else cur_edit_kpi
                for k in Object.keys(key_obj)
                    # use keys of plain() object, but values from actual object
                    # this is because plain() resets all values to the ones sent by the server
                    # if it's the initial object, it does not have plain yet and we can use the actual obj

                    if k != 'result'  # result would cause circular structure error
                        kpi_serialized[k] = cur_edit_kpi[k]

                kpi_serialized = JSON.stringify(kpi_serialized)
                set_kpi_result_to_default()
                child_scope.kpi_result.loading = true
                icswCallAjaxService
                    url: ICSW_URLS.BASE_CALCULATE_KPI
                    timeout: 120 * 1000
                    data:
                        kpi_serialized: kpi_serialized
                        dev_mon_cat_tuples: JSON.stringify(cur_edit_kpi.selected_device_monitoring_category_tuple)
                    success: (xml) ->
                        if icswParseXMLResponseService(xml)
                            child_scope.kpi_result.kpi_set = angular.fromJson($(xml).find("value[name='kpi_set']").text())

                            kpi_error_report = angular.fromJson($(xml).find("value[name='kpi_error_report']").text())
                            if  kpi_error_report?
                                #child_scope.kpi_result.kpi_error_report = "<pre>" + kpi_error_report.join("<br/>") + "</pre>"
                                child_scope.kpi_result.kpi_error_report = "<tt>" + kpi_error_report.join("<br/>").replace(/\ /g, "&nbsp;") + "</tt>"
                            child_scope.kpi_result.loading = false

            # parameters as understood by KpiData.parse_kpi_time_range
            child_scope.kpi_time_ranges = [
                {id_str: 'none', display_str: 'Only current data'},
                {id_str: 'yesterday', display_str: 'Yesterday'},
                {id_str: 'last week', display_str: 'Last week'},
                {id_str: 'last month', display_str: 'Last month'},
                {id_str: 'last year', display_str: 'Last year'},
                {id_str: 'last n days', display_str: 'Last days ...'},
            ]

            edit_div = $compile($templateCache.get("icsw.config.kpi.edit_dialog"))(child_scope)

            modal = BootstrapDialog.show
                title: if mode == 'create' then "Create KPI" else "Edit KPI"
                message: edit_div
                draggable: true
                closable: true
                closeByBackdrop: false
                closeByKeyboard: false,
                size: BootstrapDialog.SIZE_WIDE
                type: BootstrapDialog.TYPE_DANGER
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
            child_scope.modal = modal
        ret = {}
        ret.show_create_kpi_dlg = (scope) ->
            base_name = "kpi-"
            is_unique = false
            num = 0
            while ! is_unique
                num++
                unique_name = base_name + num
                is_unique = _.find(icswConfigKpiDataService.kpi, (elem) -> return elem.name == unique_name) == undefined

            new_edit_kpi = {
                name: unique_name
                available_device_categories: []
                available_monitoring_categories: []
                selected_device_monitoring_category_tuple: []
                time_range: 'none'
                time_range_parameter: 1
                enabled: true
                soft_states_as_hard_states: true
                formula: "kpi = initial_data"
            }
            show_kpi_dlg(scope, new_edit_kpi, KPI_DLG_MODE_CREATE)
        ret.show_modify_kpi_dlg = (scope, kpi) ->
            if kpi.gui_selected_categories != ""
                sel_cat = JSON.parse(kpi.gui_selected_categories)
                kpi.available_device_categories = sel_cat.dev_cat
                kpi.available_monitoring_categories = sel_cat.mon_cat
            else
                kpi.available_device_categories = []
                kpi.available_monitoring_categories = []

            kpi.selected_device_monitoring_category_tuple = []
            for entry in _.filter(icswConfigKpiDataService.kpi_data_source_tuple, (elem) -> return elem.kpi == kpi.idx)
                kpi.selected_device_monitoring_category_tuple.push(
                    [entry.device_category, entry.monitoring_category]
                )
            show_kpi_dlg(scope, kpi, KPI_DLG_MODE_MODIFY)
        return ret

]).directive("icswConfigKpiEvaluationTable",
    ["icswConfigKpiDataService", "icswConfigKpiDialogService",  "d3_service",
    (icswConfigKpiDataService, icswConfigKpiDialogService, d3_service) ->
        return {
            restrict : "E"
            templateUrl: "icsw.config.kpi.evaluation_table"
            link: (scope, el, attrs) ->
                icswConfigKpiDataService.add_to_scope(scope)
        }
]).service("icswConfigKpiDataService", ["Restangular", "ICSW_URLS", "$q", (Restangular, ICSW_URLS, $q) ->
    promises = []
    get_rest = (url, opts={}) ->
        promise = Restangular.all(url).getList(opts)
        promises.push(promise)
        return promise.$object

    ret = {
        category: get_rest(ICSW_URLS.REST_CATEGORY_LIST.slice(1))
        kpi: get_rest(ICSW_URLS.REST_KPI_LIST.slice(1))
        kpi_data_source_tuple: get_rest(ICSW_URLS.REST_KPI_DATA_SOURCE_TUPLE_LIST.slice(1))
    }

    ret.get_initial_load_promise = () ->
        return $q.all(promises)
    ret.get_kpi = (idx) ->
        return _.find(ret.kpi, (elem) -> return elem.idx == idx)
    ret.get_cat = (idx) ->
        return _.find(ret.category, (elem) -> return elem.idx == idx)
    ret.get_cat_name = (idx) ->
         return ret.get_cat(idx).name

    regular_keys = Object.keys(ret)

    ret.add_to_scope = (scope) ->
        for f in regular_keys
            scope[f] = ret[f]

    return ret
])

