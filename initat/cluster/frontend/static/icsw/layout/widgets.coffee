# Copyright (C) 2017 init.at
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

angular.module(
    "icsw.layout.widgets",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).component("icswWidget", {
    template: ["$templateCache", ($templateCache) -> return $templateCache.get("icsw.layout.widgets")]
    controller: "icswWidgetCtrl as ctrl"
    bindings: {}
}).controller("icswWidgetCtrl",
[
    "$timeout", "icswComplexModalService", "$controller",
    "$rootScope", "$compile", "$templateCache", "$q",
    "icswActiveSelectionService",
(
    $timeout, icswComplexModalService, $controller,
    $rootScope, $compile, $templateCache, $q,
    icswActiveSelectionService,
) ->
    @OV_STRUCT = {
        monitoring: {
            name: "Monitoring"
            ctrl: "icswMonitoringControlInfoCtrl"
            template: "icsw.monitoring.control.info"
            title: "Monitoring Control"
            send_selection: false
        }
        variables: {
            name: "Variables"
            ctrl: "icswDeviceVariableCtrl"
            template: "icsw.device.variable.overview"
            title: "Device Variables"
            send_selection: true
            css_class: "modal-tall modal-wide"
            show_callback: (scope) ->
                # hack, disable certain columns per default
                scope.show_column.source = false
                scope.show_column.uuid = false
        }
    }
    @show_overlay = ($event, name) ->
        $event.preventDefault()
        $event.stopPropagation()
        if not _.some(entry.name == name for entry in @struct.open)
            _def = @OV_STRUCT[name]
            # check rights ?
            @struct.open.push({name: name})
            sub_scope = $rootScope.$new(true)
            $controller(_def.ctrl, {$scope: sub_scope})
            msg = $compile($templateCache.get(_def.template))(sub_scope)
            icswComplexModalService(
                title: _def.title
                message: msg
                closeable: true
                ok_label: "close"
                css_class: _def.css_class
                shown_callback: () ->
                    if _def.show_callback?
                        _def.show_callback(sub_scope)
                    if _def.send_selection
                        _cur = icswActiveSelectionService.current()
                        sub_scope.new_devsel(_cur.resolve_devices(_cur.tot_dev_sel))
                    return null
                ok_callback: () ->
                    _defer = $q.defer()
                    _defer.resolve("close")
                    return _defer.promise
            ).then(
                (done) =>
                    # console.log @
                    sub_scope.$destroy()
                    _.remove(@struct.open, (entry) -> return entry.name == name)
            )
            @struct.menu_open = false

    @$onInit = () ->
        @struct = {
            open: []
            menu_open: false
        }
    return null
]).service("icswTableFilterService",
[
    "$q",
(
    $q,
) ->

    class icswFilterEntry
        constructor: (@multiple, @filterObj, @name, @placeholder, @cmp_func, @pre_sort_func) ->
            @choices = []
            # lut for id -> entry
            @lut = {}
            if @multiple
                @selected = []
            else
                @selected = undefined
            @clear_choices()

        add_choice: (choice_id, choice_str, choice_val, is_def) ->
            if choice_id not of @lut
                _new_entry = {
                    id: choice_id
                    string: choice_str
                    value: choice_val
                    default: is_def
                }
                @lut[_new_entry.id] = _new_entry
                @choices.push(_new_entry)
                if is_def
                    if @multiple
                        @selected.push(_new_entry)
                    else
                        if not @selected
                            @selected = _new_entry
            return @

        clear_choices: () ->
            _.remove(@choices, (entry) -> return not entry.default)
            # rebuild lut
            @lut = {}
            for entry in @choices
                @lut[entry.id] = entry
            _defs = (entry for entry in @choices when entry.default)
            if @multiple
                @selected.length = 0
                for _e in _defs
                    @selected.push(_e)
            else
                if _defs.length
                    @selected = _defs[0]
                else
                    @selected = undefined
            return @

        pre_sort_call: () ->
            if @pre_sort_func?
                @pre_sort_func(@selected)
            @selected_idxs = (entry.value for entry in @selected)

        filter: (entry) ->
            if @multiple
                return @cmp_func(entry, @selected_idxs)
            else
                return @cmp_func(entry, @selected)

    class icswFilter
        constructor: () ->
            @_filter_list = []
            @_filter_lut = {}
            @notifier = $q.defer()
            @source_list = []
            # redraw list trigger counter
            @redraw_list = 0

        add: (name, placeholder, cmp_func, pre_sort_func) =>
            _nf = new icswFilterEntry(false, @, name, placeholder, cmp_func, pre_sort_func)
            @_filter_list.push(_nf)
            @_filter_lut[_nf.name] = _nf
            return _nf

        add_mult: (name, placeholder, cmp_func, pre_sort_func) =>
            _nf = new icswFilterEntry(true, @, name, placeholder, cmp_func, pre_sort_func)
            @_filter_list.push(_nf)
            @_filter_lut[_nf.name] = _nf
            return _nf

        get: (name) ->
            return @_filter_lut[name]

        update: ($event) ->
            @notifier.notify("update")

        close: () ->
            @notifier.reject("close")

        filter: (in_list) ->
            @source_list.length = 0
            (_fe.pre_sort_call() for _fe in @_filter_list)

            for entry in in_list
                _add = true
                for _fe in @_filter_list
                    _add = _fe.filter(entry)
                    if not _add
                        break
                if _add
                    @source_list.push(entry)
            @redraw_list++

    return {
        get_instance: () ->
            return new icswFilter()
    }
]).component("icswTableFilter", {
    template: ["$templateCache", "$element", "$attrs", ($templateCache, $element, $attrs) ->
        return $templateCache.get("icsw.layout.table.filter")
    ]
    controller: "icswTableFilterCtrl as ctrl"
    bindings: {
        filter: "<icswTableFilter"
        name: "@icswFilterName"
    }
}).component("icswTableFilterMult", {
    template: [
        "$templateCache", "$element", "$attrs", ($templateCache, $element, $attrs) ->
            return $templateCache.get("icsw.layout.table.filter.mult")
    ]
    controller: "icswTableFilterCtrl as ctrl"
    bindings: {
        filter: "<icswTableFilter"
        name: "@icswFilterName"
    }
}).controller("icswTableFilterCtrl",
[
    "$q",
(
    $q,
) ->
    @$onChanges = (changes) ->
        if changes.filter
            @entry = @filter.get(@name)

    @$onInit = () ->

    return null
])
