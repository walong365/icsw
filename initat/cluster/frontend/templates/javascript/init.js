{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

remove_from_array = (in_array, from, to) ->
    rest = in_array.slice((to | from) + 1 || in_array.length)
    in_array.length = if from < 0 then in_array.length + from else from
    return in_array.push.apply(in_array, rest)

remove_by_idx = (in_array, idx) ->
    for c_idx, val of in_array
        if val.idx == idx
            remove_from_array(in_array, c_idx)
            break

class ajax_struct
    constructor: (@top_div_name) ->
        @ajax_uuid = 0
        @ajax_dict = {}
        @top_div = undefined
    new_connection: (settings) =>
        cur_id = @ajax_uuid
        if not @top_div
            @top_div = $(@top_div_name)
        if not @top_div.find("ul").length
            @top_div.append($("<ul>"))
        ai_ul = @top_div.find("ul")
        title_str = settings.title or "pending..."
        {% if debug %}
        title_str = "(#{cur_id}) #{title_str}"
        {% endif %}
        ai_ul.append(
            $("<li>").attr({
                "id" : cur_id
            }).text(title_str)
        )
        @ajax_dict[cur_id] = {
            "state" : "pending"
            "start" : new Date()
        }
        @ajax_uuid++
        return cur_id
    close_connection: (xhr_id) =>
        if xhr_id?
            @ajax_dict[xhr_id]["state"]   = "done"
            @ajax_dict[xhr_id]["runtime"] = new Date() - @ajax_dict[xhr_id]["start"]
            @top_div.find("li##{xhr_id}").remove()
        
my_ajax_struct = new ajax_struct("div#ajax_info")

call_ajax = (in_dict) ->
    default_ajax_dict = 
        type       : "POST"
        timeout    : 50000
        dataType   : "xml"
        headers    : { "X-CSRFToken" : '{{ csrf_token }}'}
        beforeSend : (xhr, settings) ->
            if not settings.hidden
                xhr.inituuid = my_ajax_struct.new_connection(settings)
        complete   : (xhr, textstatus) ->
            my_ajax_struct.close_connection(xhr.inituuid)
        dataFilter : (data, data_type) ->
            return data
        error      : (xhr, status, except) ->
            if status == "timeout"
                alert("timeout")
            else
                if xhr.status 
                    # if status is != 0 an error has occured
                    alert("*** #{status} ***\nxhr.status : #{xhr.status}\nxhr.statusText : #{xhr.statusText}")
            return false
    for key of default_ajax_dict
        if key not of in_dict
            in_dict[key] = default_ajax_dict[key]
    cur_xhr = $.ajax(in_dict)
    return cur_xhr

parse_xml_response = (xml, min_level, show_error=true) ->
    success = false
    if $(xml).find("response header").length
        ret_state = $(xml).find("response header").attr("code")
        if parseInt(ret_state) < (if min_level then min_level else 40)
            success = true
        $(xml).find("response header messages message").each (idx, cur_mes) ->
            cur_mes = $(cur_mes)
            cur_level = parseInt(cur_mes.attr("log_level"))
            if cur_level < 30
                noty({"text" : cur_mes.text()})
            else if cur_level == 30
                noty({"text" : cur_mes.text(), "type" : "warning"})
            else
                if show_error
                    noty({"text" : cur_mes.text(), "type" : "error", "timeout" : false})
    else
        if xml != null
            noty({"text" : "error parsing response", "type" : "error", "timeout" : false})
    return success

root.parse_xml_response = parse_xml_response
root.my_ajax_struct     = my_ajax_struct
root.remove_by_idx      = remove_by_idx
root.remove_from_array  = remove_from_array
root.call_ajax          = call_ajax

{% endinlinecoffeescript %}

</script>
