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

root.remove_by_idx = remove_by_idx

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

$.ajaxSetup
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

get_value = (cur_el) ->
    if cur_el.is(":checkbox")
        el_value = if cur_el.is(":checked") then "1" else "0"
    else if cur_el.prop("tagName") == "TEXTAREA"
        is_textarea = true
        if cur_el.is(":visible")
            # normal elements (not wrapped in codemirror)
            el_value = cur_el.val()
        else
            # wrapped in codemirror
            el_value = cur_el.text()
    else if cur_el.prop("tagName") == "SELECT" and cur_el.attr("multiple")
        el_value = ($(element).attr("value") for element in cur_el.find("option:selected")).join("::")
    else
        el_value = cur_el.attr("value")
    return el_value

set_value = (el_id, el_value) ->
    $("#" + el_id).val(el_value)

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

get_xml_value = (xml, key) ->
    ret_value = undefined
    $(xml).find("response values value[name='#{key}']").each (idx, val) ->
        value_xml = $(val)
        if value_xml.attr("type") == "integer"
            ret_value = parseInt(value_xml.text())
        else
            ret_value = value_xml.text()
    return ret_value

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

replace_xml_element = (master_xml, xml) ->
    # replace element in master_xml
    xml.find("value[name='object'] > *").each (idx, new_el) ->
        new_el = $(new_el)
        if master_xml
            master_xml.find("[key='" + new_el.attr("key") + "']").replaceWith(new_el)

class submitter
    constructor: (kwargs) ->
        kwargs = kwargs ? {}
        @modify_data_dict = kwargs.modify_data_dict ? undefined
        @master_xml = kwargs.master_xml ? undefined
        @success_callback = kwargs.success_callback ? undefined
        @error_callback = kwargs.error_callback ? undefined
        @callback = kwargs.callback ? undefined
    submit: (event) =>
        cur_el = $(event.target)
        is_textarea = false
        el_value = get_value(cur_el)
        data_field = {
            "id"         : cur_el.attr("id")
            "checkbox"   : cur_el.is(":checkbox")
            "value"      : el_value,
            "ignore_nop" : 1
        }
        if @modify_data_dict
            @modify_data_dict(data_field)
        if data_field.lock_list
            lock_list = $(data_field.lock_list.join(", ")).attr("disabled", "disabled")
        else
            lock_list = undefined
        $.ajax
            url     : "{% url 'base:change_xml_entry' %}"
            data    : data_field
            success : (xml) =>
                if parse_xml_response(xml)
                    replace_xml_element(@master_xml, $(xml))
                    if @callback
                        @callback(cur_el)
                    else
                        # set values
                        $(xml).find("changes change").each (idx, cur_os) ->
                            cur_os = $(cur_os)
                            set_value(cur_os.attr("id"), cur_os.text())
                        if @success_callback
                            @success_callback(cur_el)
                else
                    # set back to previous value 
                    if is_textarea
                        $(cur_el).text(get_xml_value(xml, "original_value"))
                    else if $(cur_el).is(":checkbox")
                        if get_xml_value(xml, "original_value") == "False"
                            $(cur_el).removeAttr("checked")
                        else
                            $(cur_el).attr("checked", "checked")
                    else
                        $(cur_el).attr("value", get_xml_value(xml, "original_value"))

store_user_var = (var_name, var_value, var_type="str") -> 
    $.ajax
        url  : "{% url 'user:set_user_var' %}"
        data : 
            key   : var_name
            value : var_value
            type  : var_type
            
load_user_var = (var_name) ->
    ret_dict = {}
    $.ajax
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

root.get_value                = get_value
root.set_value                = set_value
root.parse_xml_response       = parse_xml_response
root.get_xml_value            = get_xml_value
root.replace_xml_element      = replace_xml_element
root.submitter                = submitter
root.store_user_var           = store_user_var
root.load_user_var            = load_user_var
root.create_dict              = create_dict
root.create_dict_unserialized = create_dict_unserialized
root.my_ajax_struct           = my_ajax_struct

{% endinlinecoffeescript %}

</script>
