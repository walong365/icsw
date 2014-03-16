{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

remove_by_idx = (in_array, idx) ->
    for c_idx, val of in_array
        if val.idx == idx
            remove_from_array(in_array, c_idx)
            break

remove_from_array = (in_array, from, to) ->
    rest = in_array.slice((to | from) + 1 || in_array.length)
    in_array.length = if from < 0 then in_array.length + from else from
    return in_array.push.apply(in_array, rest)

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

default_ajax_dict = 
    type       : "POST"
    timeout    : 50000
    dataType   : "xml"
    headers    : { "X-CSRFToken" : $.cookie("csrftoken") }
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

call_ajax = (in_dict) ->
    for key of default_ajax_dict
        if key not of in_dict
            in_dict[key] = default_ajax_dict[key]
    $.ajax(in_dict)

parse_xml_response = (xml, min_level) ->
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
                noty({"text" : cur_mes.text(), "type" : "error", "timeout" : false})
    else
        if xml != null
            noty({"text" : "error parsing response", "type" : "error", "timeout" : false})
    return success

# create a dictionary from a list of elements
create_dict_unserialized = (top_el, id_prefix, use_name=false, django_save=false) ->
    in_list = top_el.find("input[id^='#{id_prefix}'], select[id^='#{id_prefix}'], textarea[id^='#{id_prefix}']")
    out_dict = {}
    in_list.each (idx, cur_el) ->
        cur_el = $(cur_el)
        if use_name
            key = cur_el.attr("name")
        else
            key = cur_el.attr("id")
        if cur_el.prop("tagName") == "TEXTAREA"
            if cur_el.is(":visible")
                out_dict[key] = cur_el.val()
            else
                out_dict[key] = cur_el.text()
        else if cur_el.is(":checkbox")
            if django_save
                if cur_el.is(":checked")
                    out_dict[key] = "1"
            else
                out_dict[key] = if cur_el.is(":checked") then "1" else "0"
        else if cur_el.prop("tagName") == "SELECT" and cur_el.attr("multiple")
            sel_field = []
            cur_el.find("option:selected").each (idx, opt_field) ->
                sel_field.push($(opt_field).attr("value"))
            if django_save
                out_dict[key] = sel_field
            else
                out_dict[key] = sel_field.join("::")
        else
            out_dict[key] = cur_el.attr("value")
    return out_dict
    
create_dict = (top_el, id_prefix, use_name=false, django_save=false) ->
    out_dict = create_dict_unserialized(top_el, id_prefix, use_name, django_save)
    return $.param(out_dict, traditional=true)

store_user_var = (var_name, var_value, var_type="str") -> 
    call_ajax
        url  : "{% url 'user:set_user_var' %}"
        data : 
            key   : var_name
            value : var_value
            type  : var_type
            
load_user_var = (var_name) ->
    ret_dict = {}
    call_ajax
        url     : "{% url 'user:get_user_var' %}"
        data    :
            var_name : var_name
        async   : false
        success : (xml) ->
            if parse_xml_response(xml)
                #console.log xml
                $(xml).find("user_variable").each (idx, cur_var) =>
                    cur_var = $(cur_var)
                    var_name = cur_var.attr("name")
                    var_type = cur_var.attr("type")
                    switch var_type
                        when "s"
                            ret_dict[var_name] = cur_var.text()
                        when "i"
                            ret_dict[var_name] = parseInt(cur_var.text())
                        when "b"
                            ret_dict[var_name] = if cur_var.text() == "True" then true else false
                    # very important for CS
                    true
    return ret_dict

root.parse_xml_response       = parse_xml_response
root.store_user_var           = store_user_var
root.load_user_var            = load_user_var
root.create_dict              = create_dict
root.create_dict_unserialized = create_dict_unserialized
root.my_ajax_struct           = my_ajax_struct
root.call_ajax                = call_ajax
root.remove_by_idx = remove_by_idx

{% endinlinecoffeescript %}

</script>
