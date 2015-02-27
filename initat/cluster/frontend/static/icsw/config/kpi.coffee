
angular.module(
    "icsw.config.kpi",
    [
        "icsw.config.category_tree"
    ]
).controller("icswConfigKpiCtrl", [
    "$scope", "ICSW_URLS", "icswConfigKpiDataService"
    ($scope, ICSW_URLS, icswConfigKpiDataService) ->
        edit_kpi = { # TODO: these should return rest objs
            device_categories: [{idx: 12, name:"dev mock 2"}, {idx: 13, name:"dev mock 1"}]
            monitoring_categories: [{idx: 9, name:"mon mock 1"}, {idx: 6, name:"mon mock 2"}]
            # TODO: links between dev an monitoring
        }
        this.cur_edit_kpi = edit_kpi
]).directive("icswConfigKpi", [() ->
    return {
        restrict : "E"
        templateUrl: "icsw.config.kpi"
        controller: 'icswConfigKpiCtrl'
    }
]).directive("icswConfigKpiConfigure", [() ->
    return {
        restrict : "E"
        templateUrl: "icsw.config.kpi.configure"
        require: "^icswConfigKpi"
        link: (scope, el, attrs, kpi_ctrl) ->
            scope.monitoring_categories = ["base", "http", "mail"]
            scope.device_categories = ["firewall devices", "ökotex devices"]
    }
]).directive("icswConfigKpiDevMonSelection", ['icswConfigKpiDataService', (icswConfigKpiDataService) ->
    return {
        restrict : "E"
        require  : "^icswConfigKpi"
        template : """
<tree treeconfig="device_category_tree"></tree>
<tree treeconfig="monitoring_category_tree"></tree>
"""
        link: (scope, el, attrs, kpi_ctrl) ->

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
                    @clear_active()
                    cat = entry.obj
                    if cat.depth > 1
                        @scope.edit_obj(cat, event)
                    else if cat.depth == 1
                        @scope.create_new(event, cat.full_name.split("/")[1])
                selection_changed: (entry) =>
                    # update selection in model
                    if entry.selected
                        @get_category_list().push(entry.obj)
                    else
                        _.remove(@get_category_list(), (rem_item) -> return rem_item.idx == entry.obj.idx)

            class device_category_tree_config extends base_tree_config
                get_category_list: () ->
                    return kpi_ctrl.cur_edit_kpi.device_categories
            class monitoring_category_tree_config extends base_tree_config
                get_category_list: () ->
                    return kpi_ctrl.cur_edit_kpi.monitoring_categories

            scope.device_category_tree = new device_category_tree_config()
            scope.monitoring_category_tree = new monitoring_category_tree_config()

            scope.$watch(
                () -> icswConfigKpiDataService.category_list.length
                () ->
                    roots = []
                    lut = {}
                    for entry in icswConfigKpiDataService.category_list
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
                                add_to_tree_rec(scope.device_category_tree, entry, (dev_cat.idx for dev_cat in kpi_ctrl.cur_edit_kpi.device_categories))
                            if entry.name == 'mon'
                                add_to_tree_rec(scope.monitoring_category_tree, entry, (mon_cat.idx for mon_cat in kpi_ctrl.cur_edit_kpi.monitoring_categories))
            )
    }
]).directive("icswConfigKpiDevMonLinker", ['icswConfigKpiDataService', (icswConfigKpiDataService) ->
    return {
        restrict : "E"
        require  : "^icswConfigKpi"
        templateUrl: "icsw.config.kpi.dev_mon_linker"
        link: (scope, el, attrs, kpi_ctrl) ->
            scope.get_device_categories = () ->
                return kpi_ctrl.cur_edit_kpi.device_categories
            scope.get_monitoring_categories = () ->
                return kpi_ctrl.cur_edit_kpi.monitoring_categories
    }
]).service("icswConfigKpiDataService", ["Restangular", "ICSW_URLS", "$rootScope", (Restangular, ICSW_URLS, $rootScope) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object

    category_list = get_rest(ICSW_URLS.REST_CATEGORY_LIST.slice(1))


    return {
        category_list: category_list
    }
])

