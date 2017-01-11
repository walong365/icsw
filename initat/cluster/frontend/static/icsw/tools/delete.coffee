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

# tools for delayed deletion

angular.module(
    "icsw.tools.delete",
    [
        "icsw.tools.button",
    ]
).service("icswDialogDeleteService",
[
    'icswSimpleAjaxCall', 'icswToolsSimpleModalService', 'ICSW_URLS', '$rootScope',
    '$compile', '$templateCache', 'toaster', 'blockUI', 'icswDialogDeleteCheckDeletionService',
    "icswComplexModalService",
(
    icswSimpleAjaxCall, icswToolsSimpleModalService, ICSW_URLS, $rootScope,
    $compile, $templateCache, toaster, blockUI, icswDialogDeleteCheckDeletionService,
    icswComplexModalService,
) ->
    # Ask whether to delete object, then deal with references (show popup querying user for actions)

    class icswDeleteRequest
        constructor: (objects, model_name, kwargs) ->
            @objects = objects
            # pk lut for objects
            @pk_lut = {}
            for _elem in @objects
                @pk_lut[_elem.idx] = _elem
            # string
            @model_name = model_name
            # to be called after delete
            @after_delete = null
            # async delete
            @async_delete = true
            # change async delete flag
            @change_async_delete_flag = true
            if kwargs?
                for key, value of kwargs
                    if @[key]? or key in ["after_delete"]
                        @[key] = value
                    else
                        console.error "unknown key '#{key}' (#{value}) for icswDeleteRequest"

        feed_xml: (xml) =>
            _get_name = (pk) =>
                _elem = @pk_lut[pk]
                if _elem.full_name?
                    return _elem.full_name
                else if _elem.name?
                    return _elem.name
                else if _elem.$$name?
                    return _elem.$$name
                else
                    return "(pk=#{pk})"

            related_objects = angular.fromJson($(xml).find("value[name='related_objects']").text())
            deletable_objects = angular.fromJson($(xml).find("value[name='deletable_objects']").text())
            @delete_info = angular.fromJson($(xml).find("value[name='delete_info']").text())
            @delete_info.runtime = _.round(@delete_info.runtime, 3)
            @related_objects = related_objects
            @deletable_objects = (
                {
                    pk: pk
                    idx: parseInt(pk)
                    model_name: @model_name
                    delete: true
                    delete_strategies: []
                    name: _get_name(pk)
                } for pk in deletable_objects
            )
            # console.log related_objects, deletable_objects
            # related objects contains info about undeletable objs,
            # deletable_objs is just a list of deletable objects

            # related_objs is dict { obj_pk : [ related_obj_info ] }

            @$$any_related = if _.keys(@related_objects).length > 0 then true else false
            @$$any_deletable = if @deletable_objects.length > 0 then true else false
            for pk, ref_obj of related_objects
                # salt the object ref_obj with so that the structure is similar
                # to the one of the @delete_objects list (for simple deletions)
                ref_obj.pk = pk
                ref_obj.idx = parseInt(pk)
                ref_obj.model_name = @model_name
                ref_obj.name = _get_name(parseInt(pk))
                ref_list = ref_obj.list
                for ref in ref_list
                    ref.$$show_value = "show (#{ref.objects.list.length} entries)"
                    ref.$$hide_value = "hide (#{ref.objects.list.length} entries)"
                    ref.actions = [["", "please select"]]
                    # only have default action if it is a "safe" one

                    # actions are [logical name, name for user]
                    if ref.null
                        ref.actions.push(['set null', 'set reference to null'])
                        ref.selected_action = ref.actions[1][0]

                    if ref.objects.num_refs_of_refs == 0
                        ref.actions.push(['delete object', 'delete referenced object'])
                        if not ref.selected_action?
                            ref.selected_action = ref.actions[1][0]
                    else
                        ref.actions.push(['delete cascade', 'delete cascade on referenced object'])
                    if not ref.selected_action?
                        # the user has to select the cascade action
                        ref.selected_action = ref.actions[0][0]
            @update_flags()

        update_flags: () =>
            for pk, ref_obj of @related_objects
                ref_obj.$$delete_ok = _.every(
                    ref_obj.list
                    (elem) ->
                        return elem.selected_action? and elem.selected_action != ""
                )
            @$$some_deletable_objects_checked = false
            for struct in @deletable_objects
                if struct.delete
                    @$$some_deletable_objects_checked = true

        all_deleted: () =>
            if @deletable_objects.length == 0 and _.keys(@related_objects).length == 0
                return true
            else
                return false

        get_deletables_complex: (del_obj) =>
            # create smaller to_delete object
            smaller_obj = {}

            delete_strategies = []
            # collect data from gui
            for entry in del_obj.list
                strat = {}
                for key in ['field_name', 'model', 'selected_action']
                    strat[key] = entry[key]
                delete_strategies.push(strat)

            for key, value of del_obj
                if key not in ["entries_displayed", "list"]
                    smaller_obj[key] = value
            smaller_obj.delete_strategies = delete_strategies
            delete @related_objects[del_obj.pk]
            return [smaller_obj]

        get_deletables_simple: () =>
            del_list = (entry for entry in @deletable_objects when entry.delete)
            _.remove(@deletable_objects, (entry) -> return entry.delete)
            return del_list

        set_delete_pending_flags: (in_list) =>
            del_idx = (entry.idx for entry in in_list)
            for entry in @objects
                if entry.idx in del_idx
                    entry.$$delete_pending = true

    actual_delete = (del_struct, to_delete) ->
        # set $$delete_pending flag
        del_struct.set_delete_pending_flags(to_delete)
        # add to check list and handle blockUI if required
        icswDialogDeleteCheckDeletionService.add_to_check_list(del_struct, to_delete)

        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_ADD_DELETE_REQUEST
            data: {
                data: angular.toJson(to_delete)
            }
        ).then(
            (xml) ->
        )
        icswDialogDeleteCheckDeletionService.start_check()

    show_delete_dialog = (del_struct) ->
        # objects_to_delete, model, related_objects, deletable_objects, after_delete) ->
        # shows dialog if objs to delete have hard references
        # related_objs is dict { obj_pk : [ related_obj_info ] }
        # deletable_objects is [obj_pk]
        child_scope = $rootScope.$new(true)
        child_scope.del_struct = del_struct

        _check_dialog_empty = () ->
            if del_struct.all_deleted()
                child_scope.modal.close()

        child_scope.delete_deletable_action = ($event) ->
            to_delete = del_struct.get_deletables_simple()
            actual_delete(del_struct, to_delete)
            _check_dialog_empty()


        child_scope.force_delete = ($event, del_obj) ->
            to_delete = del_struct.get_deletables_complex(del_obj)
            actual_delete(del_struct, to_delete)
            _check_dialog_empty()

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.dialog.delete_popup"))(child_scope)
                title: "Delete"
                closable: true
                show_callback: (modal) =>
                    blockUI.stop()
                    child_scope.modal = modal
                hidden_callback: (modal) =>
                    child_scope.$destroy()

            }
        )

    try_delete = (del_struct) ->
        blockUI.start("Gathering deletion info for #{del_struct.objects.length} #{del_struct.model_name} ...")  # this can take up to a few seconds in bad cases
        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_CHECK_DELETE_OBJECT
            data: {
                model_name: del_struct.model_name
                obj_pks: angular.toJson((obj.idx for obj in del_struct.objects))
            }
        ).then(
            (xml) ->
                del_struct.feed_xml(xml)
                show_delete_dialog(del_struct)
            (xml) ->
                blockUI.stop()
        )


    # we have 3 functions here:
    # - try_delete: initial contact with server, check which references the objs have
    # - show_delete_dlg: shows dlg to select how to deal with references
    # - actual_delete: handles asynchr./synchr. delete

    return {
        delete: (del_req) ->
            return try_delete(del_req)
        get_delete_instance: (objects_to_delete, model, kwargs) ->
            return new icswDeleteRequest(objects_to_delete, model, kwargs)
    }
]).service('icswDialogDeleteCheckDeletionService',
[
    'ICSW_URLS', 'blockUI', 'icswSimpleAjaxCall', '$interval', 'toaster', "$timeout",
(
    ICSW_URLS, blockUI, icswSimpleAjaxCall, $interval, toaster, $timeout,
) ->
    _struct = {
        interval_promise: null
        next_delete_request_id: 0
        check_lut: {}
        blocked_by_sync: 0
    }

    add_to_check_list = (del_struct, to_delete) ->

        _struct.next_delete_request_id++
        _struct.check_lut[_struct.next_delete_request_id] = {
            del_pks: (entry.idx for entry in to_delete)
            model_name: del_struct.model_name
            async_delete: del_struct.async_delete
            after_delete: del_struct.after_delete
            last_msg: undefined
        }
        if not del_struct.async_delete
            if not _struct.blocked_by_sync
                blockUI.start("Deleting objects ....")
            _struct.blocked_by_sync++

    start_check = () ->
        if not _struct.interval_promise?
            _struct.interval_promise = $interval(interval_fn, 2000)
        # start checking
        interval_fn()

    interval_fn = () ->
        request_params = {}
        for k, v of _struct.check_lut
            request_params[k] = [v.model_name, v.del_pks]
        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_CHECK_DELETION_STATUS
            data:
                del_requests: angular.toJson(request_params)
            dataType: "json"
        ).then(
            (json) ->
                remove_list = []
                for k, check_list_entry of _struct.check_lut
                    response = json[parseInt(k)]
                    # handle msg
                    msg = response.msg
                    if msg != ""  # this is "" if the msg is not defined in case check_list here is not current
                        if check_list_entry.async_delete
                            if check_list_entry.last_msg != msg
                                toaster.pop("success", "", msg)
                        else
                            blockUI.message(msg)
                        check_list_entry.last_msg = msg
                        # check if we are done
                        num_remaining = response.num_remaining
                        # this is Nan on invalid entry, and NaN != 0, which we want here
                        if num_remaining == 0
                            if check_list_entry.after_delete
                                # call after_delete function
                                check_list_entry.after_delete(check_list_entry)
                            if not check_list_entry.async_delete
                                _struct.blocked_by_sync--
                                if not _struct.blocked_by_sync
                                    blockUI.stop()
                            remove_list.push(k)
                for k in remove_list
                    delete _struct.check_lut[k]
                if _.keys(_struct.check_lut).length == 0
                    $interval.cancel(_struct.interval_promise)
                    _struct.interval_promise = undefined
        )

    return {
        add_to_check_list: add_to_check_list
        start_check: start_check
    }
])
