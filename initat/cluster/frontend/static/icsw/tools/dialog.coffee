angular.module(
    "icsw.tools.dialog",
    [
        "icsw.tools.button",
    ]
).service('icswDialogDeleteObjects',
    ['icswParseXMLResponseService', 'icswCallAjaxService', 'icswToolsSimpleModalService', 'ICSW_URLS', '$rootScope',
    '$compile', '$templateCache',
    (icswParseXMLResponseService, icswCallAjaxService, icswToolsSimpleModalService, ICSW_URLS, $rootScope,
    $compile, $templateCache) ->
        # Ask whether to delete object, then deal with references (show popup querying user for actions)

        return (objects_to_delete, model, after_delete) ->
            # objects_to_delete: list of things which have 'idx' and 'name'
            # model: name in initat.cluster.backbone.models which contains the objects
            # after_delete: called after deletions have occurred, use to refresh your data

            show_delete_dialog = (related_objects) ->
                # shows dialog if objs to delete have hard references
                # related_objs is dict { obj_pk : [ related_obj_info ] }
                child_scope = $rootScope.$new()

                child_scope.related_objects = related_objects
                child_scope.all_actions_defined = (obj_idx) ->
                    return _.all(related_objects[obj_idx], (elem) -> return elem.selected_action?)
                child_scope.force_delete = (obj_idx) ->
                    delete_strategies = []
                    # collect data from gui
                    for entry in related_objects[obj_idx]
                        strat = {}
                        for key in ['field_name', 'model', 'selected_action']
                            strat[key] = entry[key]

                        delete_strategies.push(strat)

                    icswCallAjaxService
                        url: ICSW_URLS.BASE_FORCE_DELETE_OBJECT
                        data: {
                            model: model
                            obj_pk: obj_idx
                            delete_strategies: JSON.stringify(delete_strategies)
                        }
                        success: (xml) ->
                            if icswParseXMLResponseService(xml)
                                if after_delete?
                                    after_delete()
                                delete related_objects[obj_idx]
                                # close if all objects are gone now
                                if Object.keys(related_objects).length == 0
                                    child_scope.modal.close()


                child_scope.get_object_by_idx = (idx) ->
                    idx = parseInt(idx)
                    return _.find(objects_to_delete, (elem) -> return elem.idx == idx)
                edit_div = $compile($templateCache.get("icsw.dialog.delete_popup"))(child_scope)
                edit_div.on("$destroy", () ->
                    child_scope.$destroy()
                )
                modal = BootstrapDialog.show
                    title: "Objects are referenced in the database"
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
                objects_string = if objects_to_delete.length == 1 then objects_to_delete[0].name else objects_to_delete.length+" objects"
                icswToolsSimpleModalService("Really delete #{ objects_string }?").then(() ->
                    icswCallAjaxService
                        url: ICSW_URLS.BASE_DELETE_OBJECT
                        data: {
                            model: model
                            obj_pks: JSON.stringify((obj.idx for obj in objects_to_delete))
                        }
                        success: (xml) ->
                            if icswParseXMLResponseService(xml)
                                related_objects = JSON.parse($(xml).find("value[name='related_objects']").text())

                                if after_delete? and Object.keys(related_objects).length != objects_to_delete.length
                                    after_delete()

                                for k, ref_list of related_objects
                                    for ref in ref_list
                                        ref.actions = []
                                        if ref.null
                                            ref.actions.push('set null')
                                            ref.selected_action = ref.actions[0]
                                        ref.actions.push('delete cascade')
                                        # only have default action if it is a safe one

                                # related_objs is dict { obj_pk : [ related_obj_info ] }
                                # check we there were some which we couldn't delete
                                if Object.keys(related_objects).length > 0
                                    show_delete_dialog(related_objects)
                )

            try_delete()
])
