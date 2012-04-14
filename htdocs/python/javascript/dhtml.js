/* DHTML-Bibliothek */
/* slightly modified by Andreas Lang 06.04.2007 */

var browser_dhtml = false;
var browser_dom = false;
var browser_msie4 = false;
var browser_ns4 = false;
var browser_opera = false;

if (document.getElementById) {
    browser_dhtml = true;
    browser_dom = true;
} else {
    if (document.all) {
        browser_dhtml = true;
        browser_msie4 = true;
    } else {
        if (document.layers) {
            browser_dhtml = true;
            browser_ns4 = true;
        }
    }
}
if (window.opera) {
    browser_opera = true;
}

function get_element(mode, identifier, element_number) {
    var element;
    var element_list;
    if (browser_dom) {
        if (mode.toLowerCase() == "id") {
            element = document.getElementById(identifier);
            if (!element) {
                element = false;
            }
            return element;
        }
        if (mode.toLowerCase() == "name") {
            element_list = document.getElementsByName(identifier);
            element = element_list[element_number];
            if (!element) {
                element = false;
            }
            return element;
        }
        if (mode.toLowerCase() == "tagname") {
            element_list = document.getElementsByTagName(identifier);
            element = element_list[element_number];
            if (!element) {
                element = false;
            }
            return element;
        }
        return false;
    }
    if (browser_msie4) {
        if (mode.toLowerCase() == "id" || mode.toLowerCase() == "name") {
            element = document.all(identifier);
            if (!element) {
                element = false;
            }
            return element;
        }
        if (mode.toLowerCase() == "tagname") {
            element_list = document.all.tags(identifier);
            element = element_list[element_number];
            if (!element) {
                element = false;
            }
            return element;
        }
        return false;
    }
    if (browser_ns4) {
        if (mode.toLowerCase() == "id" || mode.toLowerCase() == "name") {
            element = document[identifier];
            if (!element) {
                element = document.anchors[identifier];
            }
            if (!element) {
                element = false;
            }
            return element;
        }
        if (mode.toLowerCase() == "layerindex") {
            element = document.layers[identifier];
            if (!element) {
                element = false;
            }
            return element;
        }
        return false;
    }
    return false;
}

function get_attribute(mode, identifier, element_number, attribute_name) {
    var attribute;
    var element = get_element(mode, identifier, element_number);
    if (!element) {
        return false;
    }
    if (browser_dom || browser_msie4) {
        attribute = element.getAttribute(attribute_name);
        return attribute;
    }
    if (browser_ns4) {
        attribute = element[attribute_name] ;
	if (!attribute) {
	    attribute = false;
	}
        return attribute;
    }
    return false;
}

function get_content(mode, identifier, element_number) {
    var content;
    var element = get_element(mode, identifier, element_number);
    if (!element) {
        return false;
    }
    if (browser_dom && element.firstChild) {
        if (Element.firstChild.nodeType == 3) {
            content = element.firstChild.nodeValue;
        } else {
            content = "";
        }
        return content;
    }
    if (browser_msie4) {
        content = element.innerText;
        return content;
    }
    return false;
}

function set_content(mode, identifier, element_number, text) {
    var element = get_element(mode, identifier, element_number);
    if (!element) {
        return false;
    }
    if (browser_dom && element.firstChild) {
        element.firstChild.nodeValue = text;
        return true;
    }
    if (browser_msie4) {
        element.innerText = text;
        return true;
    }
    if (browser_ns4) {
        element.document.open();
        element.document.write(text);
        element.document.close();
        return true;
    }
}
