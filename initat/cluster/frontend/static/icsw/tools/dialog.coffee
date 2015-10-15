angular.module(
    "icsw.tools.dialog",
    [
        "icsw.tools.button",
    ]
).service('icswDialogDeleteObjects',
    ['icswSimpleAjaxCall', 'icswToolsSimpleModalService', 'ICSW_URLS', '$rootScope',
    '$compile', '$templateCache', 'toaster', 'blockUI', 'icswDialogDeleteCheckDeletionService',
    (icswSimpleAjaxCall, icswToolsSimpleModalService, ICSW_URLS, $rootScope,
    $compile, $templateCache, toaster, blockUI, icswDialogDeleteCheckDeletionService) ->
        # Ask whether to delete object, then deal with references (show popup querying user for actions)

        # we have 3 functions here:
        # - try_delete: initial contact with server, check which references the objs have
        # - show_delete_dlg: shows dlg to select how to deal with references
        # - actual_delete: handles asynchr./synchr. delete

        return (objects_to_delete, model, after_delete) ->
            # objects_to_delete: list of things which have 'idx' and 'name'
            # model: name in initat.cluster.backbone.models which contains the objects
            # after_delete: called after deletions have occurred, use to refresh your data

            actual_delete = (objs_to_delete, async) ->
                if async
                    #toaster.pop("info", "", "Deleting #{objs_to_delete.length} objects in background")
                    true  # just show msgs from server
                else
                    blockUI.start("Deleting")

                del_pks = []
                regular_deletion_pks = []
                for obj in objs_to_delete
                    if angular.isNumber(obj)
                        regular_deletion_pks.push(obj)
                        del_pks.push(obj)
                    else
                        # delete special ones right away (these only come in singles anyway)
                        obj_pk = obj.obj_pk
                        delete_strategies = JSON.stringify(obj.delete_strategies)

                        del_pks.push(obj_pk)

                        icswSimpleAjaxCall(
                            url: ICSW_URLS.BASE_ADD_DELETE_REQUEST
                            data: {
                                model: model
                                obj_pks: JSON.stringify([obj_pk])
                                delete_strategies: delete_strategies
                            }
                        ).then((xml) ->
                        )

                if regular_deletion_pks.length > 0
                    # delete regular objs in bulk

                    icswSimpleAjaxCall(
                        url: ICSW_URLS.BASE_ADD_DELETE_REQUEST
                        data: {
                            model: model
                            obj_pks: JSON.stringify(regular_deletion_pks)
                            delete_strategies: delete_strategies
                        }
                    ).then((xml) ->
                    )

                icswDialogDeleteCheckDeletionService.add_to_check_list(del_pks, model, async, after_delete)

                # refresh page right away
                if async && after_delete?
                    after_delete()

            show_delete_dialog = (related_objects, deletable_objects) ->
                # shows dialog if objs to delete have hard references
                # related_objs is dict { obj_pk : [ related_obj_info ] }
                # deletable_objects is [obj_pk]
                child_scope = $rootScope.$new()

                _check_dialog_empty = () ->
                    if child_scope.deletable_objects.length == 0 && Object.keys(child_scope.related_objects).length == 0
                        child_scope.modal.close()

                child_scope.async_delete = true
                child_scope.related_objects = related_objects
                child_scope.deletable_objects = deletable_objects

                child_scope.delete_deletable_dict = {}
                for pk in deletable_objects
                    child_scope.delete_deletable_dict[pk] = true
                child_scope.delete_deletable_action = () ->
                    to_delete = []
                    for k, v of child_scope.delete_deletable_dict
                        if v
                            k_int = parseInt(k)  # yay, javascript!
                            to_delete.push(k_int)
                            # remove from gui
                            _.remove(child_scope.deletable_objects, (elem) -> return elem == k_int)
                            delete child_scope.delete_deletable_dict[k_int]
                            _check_dialog_empty()

                    actual_delete(to_delete, child_scope.async_delete)


                child_scope.some_deletable_object_checked = () ->
                    for pk in deletable_objects
                        if child_scope.delete_deletable_dict[pk]
                            return true
                    return false

                child_scope.all_actions_defined = (obj_pk) ->
                    return _.all(related_objects[obj_pk], (elem) -> return elem.selected_action?)
                child_scope.force_delete = (obj_pk) ->
                    delete_strategies = []
                    # collect data from gui
                    for entry in related_objects[obj_pk]
                        strat = {}
                        for key in ['field_name', 'model', 'selected_action']
                            strat[key] = entry[key]

                        delete_strategies.push(strat)

                    actual_delete(
                        [{obj_pk: obj_pk, delete_strategies: delete_strategies}]
                        child_scope.async_delete
                    )

                    delete related_objects[obj_pk]
                    _check_dialog_empty()

                child_scope.get_object_by_idx = (idx) ->
                    idx = parseInt(idx)
                    return _.find(objects_to_delete, (elem) -> return elem.idx == idx)
                child_scope.is_empty_object = (obj) -> return Object.keys(obj).length == 0
                edit_div = $compile($templateCache.get("icsw.dialog.delete_popup"))(child_scope)
                edit_div.on("$destroy", () ->
                    child_scope.$destroy()
                )
                modal = BootstrapDialog.show
                    title: "Delete"
                    message: edit_div
                    draggable: true
                    closable: true
                    closeByBackdrop: false
                    size: BootstrapDialog.SIZE_WIDE
                    type: BootstrapDialog.TYPE_DANGER
                    onshow: (modal) =>
                        height = $(window).height() - 100
                        modal.getModal().find(".modal-body").css("max-height", height)
                child_scope.modal = modal


            try_delete = () ->
                blockUI.start()  # this can take up to a few seconds in bad cases
                icswSimpleAjaxCall(
                    url: ICSW_URLS.BASE_CHECK_DELETE_OBJECT
                    data: {
                        model: model
                        obj_pks: JSON.stringify((obj.idx for obj in objects_to_delete))
                    }
                ).then(
                    (xml) ->
                        blockUI.stop()
                        related_objects = JSON.parse($(xml).find("value[name='related_objects']").text())
                        deletable_objects = JSON.parse($(xml).find("value[name='deletable_objects']").text())

                        # related objects contains info about undeletable objs,
                        # deletable_objs is just a list of deletable objects

                        # related_objs is dict { obj_pk : [ related_obj_info ] }

                        for k, ref_list of related_objects
                            for ref in ref_list
                                ref.actions = []
                                # only have default action if it is a "safe" one

                                # actions are [logical name, name for user]
                                if ref.null
                                    ref.actions.push(['set null', 'set reference to null'])
                                    ref.selected_action = ref.actions[0][0]

                                if ref.objects.num_refs_of_refs == 0
                                    ref.actions.push(['delete object', 'delete referenced object'])
                                    if ! ref.selected_action?
                                        ref.selected_action = ref.actions[0][0]
                                else
                                    ref.actions.push(['delete cascade', 'delete cascade on referenced object'])

                        show_delete_dialog(related_objects, deletable_objects)
                    (xml) ->
                        blockUI.stop()
                )

            try_delete()
]).service('icswDialogDeleteCheckDeletionService',
    ['ICSW_URLS', 'blockUI', 'icswSimpleAjaxCall', '$interval', 'toaster', '$rootScope'
    (ICSW_URLS, blockUI, icswSimpleAjaxCall, $interval, toaster, $rootScope) ->

        check_list = {}
        next_delete_request_id = 0
        interval_promise = null
        add_to_check_list = (del_pks, model, async, after_delete) ->
            # this can also be used for sync delete, but then no other entry must
            # be added to the check list while this is running, else there are issues with blockUI

            if Object.keys(check_list).length == 0
                # start checking
                interval_promise = $interval(interval_fn, 1000)
            # add entry with unique id
            next_delete_request_id += 1
            check_list[next_delete_request_id] = {
                del_pks: del_pks
                model: model
                async: async
                after_delete: after_delete
                last_msg: undefined
            }
            # also check right away
            interval_fn()

        interval_fn = () ->
            request_params = {}
            for k, v of check_list
                request_params[k] = [v.model, v.del_pks]
            icswSimpleAjaxCall(
                url: ICSW_URLS.BASE_CHECK_DELETION_STATUS
                data:
                    del_requests: JSON.stringify(request_params)
            ).then((xml) ->
                remove_list = []
                for k, check_list_entry of check_list
                    # handle msg
                    msg = $(xml).find("value[name='msg_#{k}']").text()
                    if msg != ""  # this is "" if the msg is not defined in case check_list here is not current
                        if check_list_entry.async
                            if check_list_entry.last_msg != msg
                                toaster.pop("success", "", msg)
                        else
                            blockUI.message(msg)
                        check_list_entry.last_msg = msg
                        # check if we are done
                        num_remaining = parseInt($(xml).find("value[name='num_remaining_#{k}']").text())
                        # this is Nan on invalid entry, and NaN != 0, which we want here
                        if num_remaining == 0
                            if check_list_entry.after_delete?
                                $rootScope.$apply(
                                    check_list_entry.after_delete()
                                )
                            if !check_list_entry.async
                                blockUI.stop()
                            remove_list.push(k)
                for k in remove_list
                    delete check_list[k]
                if Object.keys(check_list).length == 0
                    $interval.cancel(interval_promise)
            )
        return {
            add_to_check_list: add_to_check_list
        }
])
