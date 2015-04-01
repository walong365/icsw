angular.module(
    "icsw.tools.dialog",
    [
        "icsw.tools.button",
    ]
).service('icswDialogDeleteObjects',
    ['icswParseXMLResponseService', 'icswCallAjaxService', 'icswToolsSimpleModalService', 'ICSW_URLS', '$rootScope',
    '$compile', '$templateCache', 'toaster', 'blockUI', '$interval',
    (icswParseXMLResponseService, icswCallAjaxService, icswToolsSimpleModalService, ICSW_URLS, $rootScope,
    $compile, $templateCache, toaster, blockUI, $interval) ->
        # Ask whether to delete object, then deal with references (show popup querying user for actions)

        return (objects_to_delete, model, after_delete) ->
            # objects_to_delete: list of things which have 'idx' and 'name'
            # model: name in initat.cluster.backbone.models which contains the objects
            # after_delete: called after deletions have occurred, use to refresh your data

            actual_delete = (objs_to_delete, async) ->
                if async
                    #toaster.pop("info", "", "Deleting #{objs_to_delete.length} objects in background")
                    true  # just show msgs from server
                else
                    blockUI.start("Deleting #{objs_to_delete.length} objects")

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

                        icswCallAjaxService
                            url: ICSW_URLS.BASE_ADD_DELETE_REQUEST
                            data: {
                                model: model
                                obj_pks: JSON.stringify([obj_pk])
                                delete_strategies: delete_strategies
                            }
                            success: (xml) ->
                                icswParseXMLResponseService(xml)

                if regular_deletion_pks.length > 0
                    # delete regular objs in bulk

                    icswCallAjaxService
                        url: ICSW_URLS.BASE_ADD_DELETE_REQUEST
                        data: {
                            model: model
                            obj_pks: JSON.stringify(regular_deletion_pks)
                            delete_strategies: delete_strategies
                        }
                        success: (xml) ->
                            icswParseXMLResponseService(xml)


                last_msg = undefined
                interval_promise = null
                interval_fn = () ->
                    icswCallAjaxService
                        url: ICSW_URLS.BASE_CHECK_DELETION_STATUS
                        data:
                            model: model
                            obj_pks: JSON.stringify(del_pks)
                        success: (xml) ->
                            if icswParseXMLResponseService(xml)
                                # handle msg
                                msg = $(xml).find("value[name='msg']").text()
                                if async
                                    if last_msg != msg
                                        toaster.pop("info", "", msg)
                                else
                                    blockUI.message(msg)

                                last_msg = msg

                                # check if we are done
                                num_remaining = parseInt($(xml).find("value[name='num_remaining']").text())
                                if num_remaining == 0
                                    if after_delete?
                                        after_delete()

                                    if !async
                                        blockUI.stop()

                                    $interval.cancel(interval_promise)
                interval_promise = $interval(interval_fn, 1000)

                interval_fn()  # check right away as well

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
                icswCallAjaxService
                    url: ICSW_URLS.BASE_CHECK_DELETE_OBJECT
                    data: {
                        model: model
                        obj_pks: JSON.stringify((obj.idx for obj in objects_to_delete))
                    }
                    success: (xml) ->
                        blockUI.stop()
                        if icswParseXMLResponseService(xml)
                            related_objects = JSON.parse($(xml).find("value[name='related_objects']").text())
                            deletable_objects = JSON.parse($(xml).find("value[name='deletable_objects']").text())

                            # related objects contains info about undeletable objs,
                            # deletable_objs is just a list of deletable objects

                            # related_objs is dict { obj_pk : [ related_obj_info ] }

                            for k, ref_list of related_objects
                                for ref in ref_list
                                    ref.actions = []
                                    # only have default action if it is a "safe" one
                                    if ref.null
                                        ref.actions.push('set null')
                                        ref.selected_action = ref.actions[0]

                                    if ref.objects.num_refs_of_refs == 0
                                        ref.actions.push('delete object')
                                        if ! ref.selected_action?
                                            ref.selected_action = ref.actions[0]
                                    else
                                        ref.actions.push('delete cascade')

                            show_delete_dialog(related_objects, deletable_objects)



            try_delete()
])
