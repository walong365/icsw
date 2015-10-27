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
                (new_val) -> $parse(attrs.icswToolsTableLeakFiltered).assign(scope, new_val)
            )
    }
]).directive('icswToolsTableNumSelected', ["$parse", ($parse) ->
    return {
        restrict: 'EA'
        require: '^stTable',
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                ctrl.getNumberOfSelectedEntries
                (new_val) -> $parse(attrs.icswToolsTableNumSelected).assign(scope, new_val)
            )
    }
]).directive('icswToolsPagination', ["$templateCache", "$parse", ($templateCache, $parse) ->
    return {
        restrict: 'EA'
        require: '^stTable'
        scope: {
            stItemsByPage: '=?'
            stDisplayedPages: '=?'
            noNumberOfElements: '=?'
        }
        template: $templateCache.get("icsw.tools.paginator")
        link: (scope, element, attrs, ctrl) ->

            scope.stItemsByPage = scope.stItemsByPage or 10
            scope.stDisplayedPages = scope.stDisplayedPages or 5
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

            # table state --> view
            scope.$watch(
                () -> return ctrl.tableState().pagination
                redraw
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
]).directive('icswToolsRestTable', ["Restangular", "$parse", "$injector", "$compile", "$templateCache", "$modal", "icswTools", "icswToolsSimpleModalService", "toaster", "$timeout",
    (Restangular, $parse, $injector, $compile, $templateCache, $modal, icswTools, icswToolsSimpleModalService, toaster, $timeout) ->
        return {
            restrict: 'EA'
            scope: true
            link: (scope, element, attrs) ->
                scope.config_service = $injector.get(attrs.configService)

                scope.config_service.use_modal ?= true

                scope.many_delete = scope.config_service.many_delete

                scope.data_received = (new_data) ->
                    _list_name = attrs.targetList
                    if not scope[_list_name]?
                        # init list if not defined
                        scope[_list_name] = []
                    list = $parse(attrs.targetList)(scope)
                    # behold, the recommended javascript implementation of list.clear():
                    list.length = 0
                    # also the code below does not work if we execute it immediately, but this works:
                    fn = () ->
                        for entry in new_data
                            list.push(entry)

                    $timeout(fn, 0)

                    # NOTE: this also makes the watch below work, see below before changing this


                if scope.config_service.init_fn?
                    scope.config_service.init_fn(scope)

                if scope.config_service.rest_url?
                    scope.rest = Restangular.all(scope.config_service.rest_url.slice(1))

                    scope.reload = () ->

                        options = if scope.config_service.rest_options? then scope.config_service.rest_options else {}
                        scope.rest.getList(options).then(scope.data_received)

                    scope.reload()

                if scope.config_service.rest_handle?
                    scope.rest = scope.config_service.rest_handle

                    scope.reload = () ->

                        options = if scope.config_service.rest_options? then scope.config_service.rest_options else {}
                        scope.rest.getList(options).then(scope.data_received)

                if scope.config_service.load_promise?
                    _list_name = attrs.targetList
                    if not scope[_list_name]?
                        # init list if not defined
                        scope[_list_name] = []
                    scope.reload = () ->
                        scope.config_service.load_promise().then(
                            (new_data) ->
                                # start watch to check for length changes
                                scope.$watch(
                                    () -> new_data.length
                                    (new_d) ->
                                        if new_d
                                            scope.data_received(new_data)
                                )
                        )
                    scope.reload()

                if scope.rest?
                    # NOTE: watching on restangular does not work. if $object gets filled up, there is NO call.
                    # therefore we watch on the length, which works. this also gets called on reload because of the
                    # way it is implemented above.
                    scope.$watch(
                        () -> return scope.rest.length
                        (new_data) ->
                            # this should be called when the data is here, but we can't control that
                            if scope.config_service.after_reload
                                scope.config_service.after_reload(scope)
                    )
                    # is this correct ? changed identation, please check @BM
                    $parse(attrs.targetList).assign(scope, scope.rest)

                # interface functions to use in directive body
                scope.edit = (event, obj) ->
                    scope.pre_edit_obj = angular.copy(obj)
                    scope.create_or_edit(event, false, obj)
                scope.create = (event, parent_obj) ->
                    if typeof(scope.config_service.new_object) == "function"
                        scope.new_obj = scope.config_service.new_object(parent_obj)
                    else
                        scope.new_obj = scope.config_service.new_object
                    scope.create_or_edit(event, true, scope.new_obj)
                scope.create_or_edit = (event, create_or_edit, obj) ->
                    scope.edit_obj = obj
                    scope.create_mode = create_or_edit
                    if scope.fn and scope.fn.create_or_edit
                        scope.fn.create_or_edit(scope, scope.create_mode, obj)
                    if scope.config_service.use_modal
                        if scope.create_mode and scope.config_service.create_template?
                            _templ = scope.config_service.create_template
                        else
                            _templ = scope.config_service.edit_template
                        if typeof(_templ) == "function"
                            _templ = _templ(obj)
                        scope.edit_div = $compile($templateCache.get(_templ))(scope)
                        # default value for modal title
                        _title = scope.config_service.modal_title ? 'ICSW Modal'
                        scope.my_modal = BootstrapDialog.show
                            message: scope.edit_div
                            draggable: true
                            size: BootstrapDialog.SIZE_WIDE
                            closable: true
                            title: _title
                            animate: false
                            closeByBackdrop: false
                            cssClass: "modal-tall"
                            onhidden: () =>
                                scope.modal_active = false
                            onshow: (modal) =>
                                height = $(window).height() - 100
                                modal.getModal().find(".modal-body").css("max-height", height)
                            onshown: () =>
                                scope.modal_active = true
                    else
                        scope.modal_active = true
                scope.modify = () ->
                    if not scope.form.$invalid
                        if scope.create_mode
                            if scope.rest?
                                scope.rest.post(scope.new_obj).then((new_data) ->
                                    scope.rest.push(new_data)
                                    scope.close_modal()
                                    if scope.config_service.object_created
                                        scope.config_service.object_created(scope.new_obj, new_data, scope)
                                )
                            if scope.config_service.save_defer?
                                scope.config_service.save_defer(scope.new_obj).then(
                                    (new_data) ->
                                        scope.close_modal()
                                        if scope.config_service.object_created
                                            scope.config_service.object_created(scope.new_obj, new_data, scope)
                                    (error) ->
                                        if error
                                            toaster.pop("error", "", error)
                                )
                        else
                            if scope.config_service.pre_modify?
                                scope.config_service.pre_modify(scope.edit_obj)
                            scope.edit_obj.put().then(
                                (data) ->
                                    icswTools.handle_reset(data, scope.rest, scope.edit_obj.idx)
                                    if scope.config_service.object_modified
                                        scope.config_service.object_modified(scope.edit_obj, data, scope)
                                    scope.close_modal()
                                (resp) -> icswTools.handle_reset(resp.data, scope.rest, scope.edit_obj.idx)
                            )
                    else
                        toaster.pop("warning", "", "form validation problem")
                scope.form_error = (field_name) ->
                    # temporary fix, FIXME
                    # scope.form should never be undefined
                    if scope.form?
                        if scope.form[field_name]?
                            if scope.form[field_name].$valid
                                return ""
                            else
                                return "has-error"
                        else
                            return ""
                    else
                        return ""
                scope.hide_modal = () ->
                    # hides dummy modal
                    if not scope.fn.use_modal and scope.modal_active
                        scope.modal_active = false
                scope.close_modal = () ->
                    if scope.config_service.use_modal
                        scope.my_modal.close()
                    scope.modal_active = false
                    if scope.fn and scope.fn.modal_closed
                        scope.fn.modal_closed(scope)
                        if scope.config_settings.use_modal
                            try
                                # fixme, call digest cycle and ignore if cycle is already running
                                scope.$digest()
                            catch exc
                scope.get_action_string = () ->
                    return if scope.create_mode then "Create" else "Modify"
                scope.delete = (obj, $event) ->
                    if $event
                        $event.stopPropagation()
                    icswToolsSimpleModalService(scope.config_service.delete_confirm_str(obj)).then(
                        () ->
                            # check for a pre_delete function
                            if scope.config_service.pre_delete
                                scope.config_service.pre_delete(obj)
                            if scope.config_service.delete
                                scope.config_service.delete(scope, obj)
                            else
                                obj.remove().then(
                                    (resp) ->
                                        toaster.pop("success", "", "deleted instance")
                                        icswTools.remove_by_idx($parse(attrs.targetList)(scope), obj.idx)
                                        if scope.config_service.post_delete
                                            scope.config_service.post_delete(scope, obj)
                                )
                    )
        }
]).directive('icswToolsShowHideColumns', () ->
    return {
        restrict: 'EA'
        template: """
Show/Hide columns: <div class="btn-group btn-group-xs">
    <input type="button" ng-repeat="entry in columns" ng-attr-title="show/hide columns {{entry}}" ng-value="entry"
        ng-class="show_column[entry] && 'btn btn-success' || 'btn'" ng-click="show_column[entry] = ! show_column[entry]"></input>
</div>
"""
        scope: false
        link: (scope, element, attrs) ->
            scope.a = attrs
            if attrs.createShowColumn
                # NOTE: this object can easily end up in the wrong scope
                #       set this attribute if you know what you are doing, or else create the object yourself in your scope
                scope.show_column = {}


            set_new_columns = (new_columns) ->
                for k in Object.keys(scope.show_column)
                    if k not in new_columns
                        delete scope.show_column[k]

                scope.columns = new_columns
                for col in scope.columns
                    scope.show_column[col] = true

            scope.$watch(
                () -> attrs.columnsList
                (new_val) ->
                    if new_val? && new_val
                        set_new_columns(JSON.parse(new_val))
            )

            scope.$watch(
                () -> attrs.columns  # watch on attribute doesn't work
                (new_val) ->
                    if new_val?
                        set_new_columns(new_val.split(' '))

            )
     }
)
