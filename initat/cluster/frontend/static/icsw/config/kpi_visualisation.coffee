# Copyright (C) 2015-2017 init.at
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
    "icsw.config.kpi.visualisation",
    [
        "icsw.tools.utils", "icsw.d3", "icsw.tools", "icsw.tools.status_history_utils",
    ]
).directive("icswConfigKpiEvaluationGraph",
[
    "icswConfigKpiDataService", "d3_service", "$timeout", "$filter", "icswConfigKpiVisUtils",
(
    icswConfigKpiDataService, d3_service, $timeout, $filter, icswConfigKpiVisUtils
) ->
    return {
        restrict: "E"
        templateUrl: "icsw.config.kpi.evaluation_graph"
        scope:
            # this directive needs either a kpi index or a kpi result (for custom stuff)
            kpiIdx: '&kpiIdx'
            kpiResult: '&kpiResult'
            width: '&width'
        link: (scope, el, attrs) ->

            update_width = () ->
                # 'regular' layout has a width of 1280, scale according to that:
                effective_width = scope.width() or 1280
                scope.svg_width = effective_width * (700 / 1280)
                scope.div_width = effective_width * (480 / 1280)

            update_width()

            scope.$watch(
                () -> scope.width()
                () -> update_width()
            )

            node_height = 80

            scope.kpi_set_to_show = undefined

            top_bottom_padding = 13

            scope.tree = undefined
            d3_service.d3().then(
                (d3) ->
                    scope.svg_el = el[0].getElementsByClassName("kpi-visualisation-svg")[0]
                    scope.svg = d3.select(scope.svg_el)
                        .append("g")
                        .attr("transform", "translate(0, #{top_bottom_padding})")
                    root = d3.stratify()
                    # console.log
                    scope.tree = d3.tree()
                        # .children(
                        #     (node) ->
                        #         if node.hide_children then null else return node.origin.operands)
                        .nodeSize([330, node_height])  # this would be nice but changes layout horribly
                        #.separation((a, b) -> return 8)

            )

            scope.redraw = () ->
                if !scope.tree?
                    # wait for tree
                    $timeout(scope.redraw, 200)
                else
                    if scope.kpiIdx()? and scope.kpiResult()?
                        console.error "Both kpi index and kpi result defined for evaluation graph"

                    if scope.kpiIdx()?
                        kpi = icswConfigKpiDataService.get_kpi(scope.kpiIdx())
                        if kpi.enabled and kpi.result?  # only for enabled's
                            scope.data = kpi.result.json
                            # scope.height = 70
                            scope.update_dthree()

                    if scope.kpiResult()?
                        scope.data = scope.kpiResult()
                        scope.update_dthree()

            scope.update_dthree = () ->
                # show result
                icswConfigKpiVisUtils.sort_kpi_set(scope.data)
                scope.kpi_set_to_show = scope.data

                _get_max_depth = (node, cur_depth) ->
                    max_depth = cur_depth
                    for child in node.origin.operands
                        max_depth = Math.max(max_depth, _get_max_depth(child, cur_depth + 1))
                    return max_depth

                max_depth = _get_max_depth(scope.data, 0)
                max_depth = Math.max(max_depth, 1)

                draw_height = max_depth * node_height
                draw_width = scope.svg_width - 100  # labels grow to the right side

                scope.svg_height = draw_height + top_bottom_padding * 2
                scope.div_height = Math.max(max_depth, 3) * node_height + top_bottom_padding * 2

                scope.tree.size([draw_width, draw_height])

                # console.log scope.data
                hr_data = d3.hierarchy(scope.data, (node) -> return node.origin.operands)
                nodes = scope.tree(hr_data)
                # links = hr_data.links()
                # console.log "n,l", nodes, links
                # links = scope.tree.links(nodes)

                # fixed depth
                #nodes.forEach(
                #    (d) ->
                #        d.y = d.depth * node_height
                #)

                my_translate = (x, y) -> return [x, draw_height - y]

                diagonal = (d) ->
                    [sx, sy] = my_translate(d.x, d.y)
                    [dx, dy] = my_translate(d.parent.x, d.parent.y)
                    return "M#{sx},#{sy}C#{dx},#{sy} #{dx},#{dy} #{dx},#{dy}"

                link = scope.svg.selectAll(".link")
                    .data(hr_data.descendants().slice(1))
#
                link.enter()
                    .append("g")
                    .attr("class", "link")
                    .append("path")
                    .attr("fill", "none")
                    .attr("stroke", "#ff8888")
                    .attr("stroke-width", "1.5px")
                    .attr("d", diagonal)

                duration = 0.001  # milliseconds

                link.transition()
                    .duration(duration)
                    .select("path")
                    .attr("d", diagonal)

                link.exit().remove()

                node = scope.svg.selectAll(".node")
                    .data(hr_data.descendants())
                # console.log "n", node

                _html = (node) ->
                    d = node.data
                    # console.log "html", d
                    res = "<circle r=\"4\"></circle>"
                    if d.hide_children and d.origin.type != 'initial'
                        res += "<circle r=\"1.5\" fill=\"white\"></circle>"
                    res += "{"
                    cur_height = 3

                    if d.depth == 0
                        # result (we could also check for not having a parent)
                        res += "<text style=\"font-size: 11px\" dx=\"-8\" dy=\"#{cur_height}\" text-anchor=\"end\">kpi = </text>"

                    if d.origin.type == 'initial'
                        res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{cur_height}\"> initial data (#{d.objects.length} objects) </text>"
                    else
                        concise = d.objects.length > 3 || d.objects.length == 0

                        if concise
                            res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{cur_height}\"> #{d.objects.length} objects </text>"
                        else
                            i = 0
                            kpi_obj_height = cur_height
                            for kpi_obj in d.objects
                                if i > 2 # only 3 elems
                                    res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{kpi_obj_height}\"> ... </text>"
                                    break
                                s = icswConfigKpiVisUtils.kpi_obj_to_string(kpi_obj)
                                s = $filter('limit_text')(s, 17)
                                res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{kpi_obj_height}\"> #{s} </text>"
                                kpi_obj_height += 14
                                i += 1

                        # operation
                        res += "<text style=\"font-size: 11px; font-style: italic;\" dx=\"0\" dy=\"-22\" text-anchor=\"middle\">"

                        is_method = d.origin.type.match(/^[a-zA-Z_\-]*$/i)
                        if is_method
                            operation = "#{d.origin.type}(" + (k+"="+v for k, v of d.origin.arguments).join(", ")
                            res += $filter('limit_text')(operation, 25) + ")"
                        else  # is operator
                            res += "#{d.origin.type}"

                        res += "</text>"

                    return res

                node.enter()
                    .append("g")
                    .attr("class", "node")
                    .style("cursor", "pointer")
                    #.attr("transform", (d) -> return "translate(" + d.x + "," + d.y + ")")
                    .attr("transform", (d) ->
                        # console.log "*", d.x, d.y
                        return "translate(" + my_translate(d.x, d.y).join(",") + ")"
                    ).html(
                        (d) ->
                            return _html(d)
                    ).on("mouseenter", (node) =>
                        $timeout(
                            () ->
                                if scope._mouse_on_node == node.data
                                    icswConfigKpiVisUtils.sort_kpi_set(node.data)
                                    scope.kpi_set_to_show = node.data
                            50
                        )
                        scope._mouse_on_node = node.data
                    ).on("mouseleave", (node) =>
                        scope._mouse_on_node = undefined
                    ).on("click", (node) =>
                        # not working right now ..
                        if node.data.hide_children
                            # unhide recursively
                            unhide_rec = (node) ->
                                node.hide_children = false
                                for child in node.origin.operands
                                    unhide_rec(child)

                            unhide_rec(node.data)
                        else
                            # hide locally
                            node.data.hide_children = true

                        scope.redraw()
                    )

                node.transition()
                    .duration(duration)
                    .attr("transform", (d) -> return "translate(" + my_translate(d.x, d.y).join(",") + ")")

                node.exit().remove()


                #node.append("circle")
                #    .attr("r", 4.5)

                #node.append("text")
                #    #.attr("dx", (d) -> return if d.children then -8 else 8)
                #    .attr("dx", (d) -> return 8)
                #    .attr("dy", 3)
                #    #.style("text-anchor", (d) -> return if d.children then "end" else "start")
                #    .style("text-anchor", (d) -> return "start")

            scope.on_mouse_leave_widget = () ->
                # when mouse leaves full widget
                # to hide set:
                # scope.kpi_set_to_show = undefined
                # to show global result
                #scope.kpi_set_to_show = scope.data
                # do nothing currently

            scope.get_div_height_style = () ->
                return {'height': scope.div_height}

            scope.$watchGroup(
                [
                    () -> scope.kpiIdx()
                    () -> scope.kpiResult()
                ]
                () -> scope.redraw()
            )
    }
]).directive("icswConfigKpiShowKpiSet",
[
    "icswConfigKpiDataService", "icswConfigKpiVisUtils",
(
    icswConfigKpiDataService, icswConfigKpiVisUtils
) ->
    return {
        templateUrl: "icsw.config.kpi.show_kpi_set"
        scope: {
            kpi_set: "=kpiSet"
            show_close_attr: "&showClose"
            body_height_attr: "&bodyHeight"
            title: "@title"
        }
        link: (scope, el, attrs) ->
            icswConfigKpiVisUtils.add_to_scope(scope)
            scope.title = scope.title or "Kpi Set"
            scope.show_close = scope.show_close_attr()
            scope.body_height = scope.body_height_attr()
    }
]).directive("icswConfigKpiShowKpiObject",
[
    "icswConfigKpiDataService", "icswConfigKpiVisUtils", "status_utils_functions",
(
    icswConfigKpiDataService, icswConfigKpiVisUtils, status_utils_functions
) ->
    return {
        templateUrl: "icsw.config.kpi.show_kpi_object"
        scope: {
            kpi_obj: "=kpiObj"
        }
        replace: true
        link: (scope, el, attrs) ->
            icswConfigKpiVisUtils.add_to_scope(scope)
            scope.list_group_class = ""

            scope.update = () ->
                list_group_class_map = {
                    Ok: 'list-group-item-success'
                    Warning: 'list-group-item-warning'
                    Critical: 'list-group-item-danger'
                    #unknown:
                    #undetermined
                }

                if scope.kpi_obj.result of list_group_class_map
                    scope.list_group_class = list_group_class_map[scope.kpi_obj.result]

                time_line = undefined
                if scope.kpi_obj.aggregated_tl
                    time_line = scope.kpi_obj.aggregated_tl
                if scope.kpi_obj.detail
                    time_line = scope.kpi_obj.detail
                console.log "*", time_line

                if time_line?
                    # dict to list representation
                    status_util_compat_data = (
                        {state: st, value: val} for st, val of time_line
                    )
                    [scope.pie_data_list, scope.pie_data] = status_utils_functions.preprocess_kpi_state_data(status_util_compat_data)

            scope.$watch(
                () -> return scope.kpi_obj.kpi_id
                scope.update
            )

    }
]).service("icswConfigKpiVisUtils",
[
    "$filter",
(
    $filter
) ->
    ret = {
        kpi_obj_to_string: (kpi_obj, verbose) ->
            # verbose is currently not used
            kpi_obj_to_string_concise = (kpi_obj) ->
                parts = []
                if kpi_obj.host_name
                    parts.push kpi_obj.host_name.split(".")[0]
                if kpi_obj.service_info?
                    parts.push kpi_obj.service_info
                else if kpi_obj.check_command
                    parts.push kpi_obj.check_command

                if kpi_obj.rrd_id?
                    parts.push kpi_obj.rrd_id

                if kpi_obj.aggregated_tl?
                    # parts.push "{" + ( "#{k}: #{(v*100).toFixed(3)}%" for k, v of kpi_obj.aggregated_tl).join(", ") + "}"
                    parts.push "timeline"

                if kpi_obj.result?
                    parts.push kpi_obj.result

                if parts.length
                    return parts.join(":")
                else
                    return JSON.stringify(kpi_obj)

            kpi_obj_to_string_verbose = (kpi_obj) ->
                # unused
                parts = []
                if kpi_obj.host_name
                    parts.push "Host: #{kpi_obj.host_name.split(".")[0]}"
                if kpi_obj.service_info? # show as in status history, i.e. prefer service_info
                    parts.push "Service: #{kpi_obj.service_info}"
                else if kpi_obj.check_command
                    parts.push "Service: #{kpi_obj.check_command}"

                if kpi_obj.result?
                    parts.push "Result: #{kpi_obj.result}"


                if kpi_obj.aggregated_tl?
                    parts.push "{" + ( "#{k}: #{(v*100).toFixed(3)}%" for k, v of kpi_obj.aggregated_tl).join(", ") + "}"

                return parts.join(",")

            return if verbose then kpi_obj_to_string_verbose(kpi_obj) else kpi_obj_to_string_concise(kpi_obj)

        sort_kpi_set: (kpi_set) ->
            kpi_set.objects = $filter('orderBy')(kpi_set.objects, ['host_name', 'service_info', 'check_command', 'rrd_id'])
            return kpi_set
    }

    contents = Object.keys(ret)
    ret.add_to_scope = (scope) ->
        for c in contents
            scope[c] = ret[c]

    return ret
])
