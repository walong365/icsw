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

angular.module(
    "icsw.tools.table", [
        "restangular"
    ]
).directive('icswToolsTableFilteredElements', () ->
    return {
        restrict: 'E'
        require: '^stTable',
        scope: {}
        template: "{{num_filtered}}"
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                () -> return ctrl.getFilteredCollection().length
                (new_val) -> scope.num_filtered = new_val
            )
    }
).directive('icswToolsTableLeakFiltered', ["$parse", ($parse) ->
    return {
        restrict: 'EA'
        require: '^stTable',
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                ctrl.getFilteredCollection
                (new_val) ->
                    $parse(attrs.icswToolsTableLeakFiltered).assign(scope, new_val)
            )
    }
]).directive('icswToolsTableNumSelected', ["$parse", ($parse) ->
    return {
        restrict: 'EA'
        require: '^stTable',
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                ctrl.getNumberOfSelectedEntries
                (new_val) ->
                    $parse(attrs.icswToolsTableNumSelected).assign(scope, new_val)
            )
    }
]).directive('icswToolsPagination',
[
    "$templateCache", "$parse",
(
    $templateCache, $parse
) ->
    return {
        restrict: 'EA'
        require: '^stTable'
        scope: {
            stDisplayedPages: '=?'
            noNumberOfElements: '=?'
            icsw_callback: "=icswCallback"
            icsw_control: "=icswControl"
        }
        template: $templateCache.get("icsw.tools.paginator")
        link: (scope, element, attrs, ctrl) ->
            scope.stDisplayedPages = scope.stDisplayedPages or 5
            if attrs.stItemsByPage
                scope.stItemsByPage = parseInt(attrs.stItemsByPage)
            else
                scope.stItemsByPage = 10
            #if scope.icsw_callback?
            #    _settings = scope.icsw_callback()
            #    if "items_by_page" of _settings
            #        scope.stItemsByPage = _settings.items_by_page
            scope.noNumberOfElements = scope.noNumberOfElements or false
            scope.Math = Math
            # this is not nice but only needed for a minor thing (see template above)
            # the problem is that we can't access the scope of the outer directive as the st-table directive overwrites the scope
            scope.table_controller = ctrl

            if attrs.possibleItemsByPage
                scope.possibleItemsByPage = (parseInt(i) for i in attrs.possibleItemsByPage.split(","))
            else
                scope.possibleItemsByPage = [10, 20, 50, 100, 200, 500, 1000]

            scope.currentPage = 1
            scope.pages = []

            scope.$$delay_settings = false

            _copy_settings = () ->
                vals = scope.icsw_control
                # check if selectPage is already defined
                if scope.selectPage?
                    scope.$$delay_settings = false
                    # console.log "S", scope.selectPage, scope.stItemsByPage
                    if vals.items_by_page?
                        scope.stItemsByPage = vals.items_by_page
                    if vals.current_page?
                        scope.selectPage(vals.current_page)
                    if vals.sort?
                        ctrl.tableState().sort = vals.sort
                else
                    scope.$$delay_settings = true

            if attrs.icswControl?
                _copy_settings()
                scope.$watch(
                    () ->
                        return scope.icsw_control.counter
                    (_val) ->
                        _copy_settings()
                    true
                )

            sent_page = -1

            call_callback = () ->
                if scope.icsw_callback?
                    sent_page = scope.currentPage
                    scope.icsw_callback(
                        {
                            items_by_page: scope.stItemsByPage
                            current_page: scope.currentPage
                            sort: ctrl.tableState().sort
                        }
                    )

            redraw = () ->
                paginationState = ctrl.tableState().pagination
                start = 1
                scope.currentPage = Math.floor(paginationState.start / paginationState.number) + 1

                start = Math.max(start, scope.currentPage - Math.abs(Math.floor(scope.stDisplayedPages / 2)))
                end = start + scope.stDisplayedPages

                if end > paginationState.numberOfPages
                    end = paginationState.numberOfPages + 1
                    start = Math.max(1, end - scope.stDisplayedPages)

                scope.pages = []
                scope.numPages = paginationState.numberOfPages

                for i in [start..(end-1)]
                    scope.pages.push(i)
                # console.log "*", scope.$id, scope.currentPage
                # if current_page is set in icsw_control check if this page is already set
                if scope.icsw_control? and scope.icsw_control.current_page?
                    if scope.icsw_control.current_page != scope.currentPage
                        # no set it
                        _copy_settings()
                else if scope.$$delay_settings
                    # console.log "delay"
                    _copy_settings()
                # current page is reached
                if scope.icsw_control?
                    scope.icsw_control.current_page = undefined
                call_callback()

            # table state --> view
            scope.$watch(
                () ->
                    return ctrl.tableState().pagination
                redraw
                true
            )

            scope.$watch(
                () ->
                    return ctrl.tableState().sort
                () ->
                    call_callback()
                true
            )

            # scope --> table state  (--> view)
            scope.$watch('stItemsByPage', (new_val) ->
                scope.selectPage(1)
            )

            scope.$watch('stDisplayedPages', redraw)

            # view -> table state
            scope.selectPage = (page) ->
                if (page > 0 && page <= scope.numPages) 
                    ctrl.slice((page - 1) * scope.stItemsByPage, scope.stItemsByPage)
                if scope.currentPage != sent_page
                    call_callback()

            # select the first page
            ctrl.slice(0, scope.stItemsByPage)
            
            scope.get_range_info = (num) =>
                num = parseInt(num)
                s_val = (num - 1 ) * scope.stItemsByPage + 1
                e_val = s_val + scope.stItemsByPage - 1
                # removed because getNumberOfTotalEntries is no longer defined in newer st-table versions
                # if !scope.noNumberOfElements and e_val > ctrl.getNumberOfTotalEntries()
                #    e_val = ctrl.getNumberOfTotalEntries()
                return "page #{num} (#{s_val} - #{e_val})"
    }
]).directive("icswToolsRestTableNew",
[
    "Restangular", "$parse", "$injector", "$compile", "$templateCache", "icswTools",
    "icswToolsSimpleModalService", "toaster", "$timeout",
(
    Restangular, $parse, $injector, $compile, $templateCache, icswTools,
    icswToolsSimpleModalService, toaster, $timeout
) ->
    return {
        restrict: 'EA'
        scope: true
        link: (scope, element, attrs) ->
            scope.config_service = $injector.get(attrs.configService)
            if attrs.icswConfigObject?
                scope.icsw_config_object = scope.$eval(attrs.icswConfigObject)
            else
                scope.icsw_config_object = undefined

            # scope.config_service.use_modal ?= true

            if scope.config_service.many_delete?
                scope.many_delete = scope.config_service.many_delete
            else
                scope.many_delete = false

            scope.data_received = (new_data) ->
                $parse(attrs.targetList).assign(scope, new_data)
                # behold, the recommended javascript implementation of list.clear():
                # also the code below does not work if we execute it immediately, but this works:
                # fn = () ->
                #    if scope.config_service.post_reload_func?
                #        scope.config_service.post_reload_func()

                # $timeout(fn, 0)
                # NOTE: this also makes the watch below work, see below before changing this


            if scope.config_service.init_fn?
                scope.config_service.init_fn(scope)

            scope.config_service.fetch(scope).then(
                (list) ->
                    scope.data_received(list)
            )

            # interface functions to use in directive body
            scope.edit = (event, obj) ->
                scope.create_or_edit(event, false, obj)

            scope.create = (event, obj) ->
                scope.create_or_edit(event, true, obj)

            scope.create_or_edit = (event, create, obj_or_parent) ->
                scope.config_service.create_or_edit(scope, event, create, obj_or_parent)

            scope.special_fn = (event, fn_name, obj, data) ->
                # for non-specific functions
                scope.config_service.special_fn(scope, event, fn_name, obj, data)

            scope.form_error = (field_name) ->
                # temporary fix, FIXME
                # scope.form should never be undefined
                if scope.form_data?
                    if scope.form_data[field_name]?
                        if scope.form_data[field_name].$valid
                            return ""
                        else
                            return "has-error"
                    else
                        return ""
                else
                    return ""

            scope.delete = ($event, obj) ->
                if $event
                    $event.stopPropagation()
                scope.config_service.delete(scope, $event, obj)
    }
]).directive('icswToolsShowHideColumns',
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: 'EA'
        template: $templateCache.get("icsw.tools.table.show_hide")
        scope: {
            callback: "=icswCallback"
            columns: "@columns"
            columns_list: "=columnsList"
            columns_from_settings: "=columnsFromSettings"
            columns_target: "=columnsTarget"
        }
        link: (scope, element, attrs) ->
            scope.struct = {
                # current columns
                cur_columns: []
                # show columns lut
                show_column: {}
            }

            _copy_columns = () ->
                if scope.columns_target?
                    for key, value of scope.struct.show_column
                        scope.columns_target[key] = value

            set_new_columns = (new_columns) ->
                for k in _.keys(scope.struct.show_column)
                    if k not in new_columns
                        delete scope.struct.show_column[k]

                scope.struct.cur_columns.length = 0
                for entry in new_columns
                    scope.struct.cur_columns.push(entry)
                    if scope.columns_target[entry]?
                        # copy from prepopulated setting, for instance variable widget
                        scope.struct.show_column[entry] = scope.columns_target[entry]
                    else
                        # per default new columns are shown
                        scope.struct.show_column[entry] = true
                if attrs.columnsFromSettings?
                    scope.$watch(
                        "columns_from_settings"
                        (new_val) ->
                            for key, val of new_val
                                scope.struct.show_column[key] = val
                            if scope.callback?
                                scope.callback(scope.struct.show_column)
                            _copy_columns()
                    )
                if scope.callback?
                    scope.callback(scope.struct.show_column)
                _copy_columns()

            scope.toggle_column = ($event, key) ->
                scope.struct.show_column[key] = !scope.struct.show_column[key]
                if scope.callback
                    scope.callback(scope.struct.show_column)
                _copy_columns()

            if scope.columns?
                set_new_columns(scope.columns.split(" "))

            if attrs.columnsList?
                scope:$watch(
                    "columns_list"
                    (new_val) ->
                        console.log "ncls", new_val
                )
     }
]).directive("icswToolsFloatingTableHeader",
[
    "$window",
(
    $window,
) ->
    # container element contains 2 elements (head, body)
    return {
        restrict: 'EAC'
        scope: false
        link: (scope, element, attrs) ->
            header = angular.element(element.children()[0])
            body = angular.element(element.children()[1])

            fixheader = (e) ->
                menu_height = parseInt(window.getComputedStyle($window.document.body, null).paddingTop)
                rel_pos = element[0].getBoundingClientRect().top - menu_height
                if rel_pos < 0
                    # fix header
                    body[0].style.paddingTop = "#{header[0].clientHeight}px"
                    header[0].style.top = "#{menu_height}px"
                    header[0].style.position = "fixed"
                else
                    # default
                    header[0].style.position = "static"
                    body[0].style.paddingTop = 0
                    header[0].style.top = 0
            $($window).bind("scroll", fixheader)
    }
])
