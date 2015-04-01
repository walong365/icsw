import re
import codecs

from django.core.urlresolvers import resolve
from django.conf import settings

from initat.core import logger
from initat.core.menu import Menu


reg_b = re.compile(
    r"android|avantgo|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|"
    "ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|opera m(ob|in)i|palm( os)?|"
    "phone|p(ixi|re)\\/|plucker|pocket|psp|symbian|treo|up\\.(browser|link)|"
    "vodafone|wap|windows (ce|phone)|xda|xiino", re.I | re.M)

reg_v = re.compile(
    r"1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\\-)|"
    "ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|"
    "au(di|\\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb"
    "|bw\\-(n|u)|c55\\/|capi|ccwa|cdm\\-|cell|chtm|cldc|cmd\\-|co(mp|nd)|"
    "craw|da(it|ll|ng)|dbte|dc\\-s|devi|dica|dmob|do(c|p)o|ds(12|\\-d)|"
    "el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\\-|_)|"
    "g1 u|g560|gene|gf\\-5|g\\-mo|go(\\.w|od)|gr(ad|un)|haie|hcit|hd\\-(m|p|t)|"
    "hei\\-|hi(pt|ta)|hp( i|ip)|hs\\-c|ht(c(\\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|"
    "i\\-(20|go|ma)|i230|iac( |\\-|\\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|"
    "ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\\/)|klon|kpt |kwc\\-|kyo(c|k)|"
    "le(no|xi)|lg( g|\\/(k|l|u)|50|54|e\\-|e\\/|\\-[a-w])|libw|lynx|"
    "m1\\-w|m3ga|m50\\/|ma(te|ui|xo)|mc(01|21|ca)|m\\-cr|me(di|rc|ri)|"
    "mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|"
    "n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\\-|on|tf|"
    "wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|"
    "pdxg|pg(13|\\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\\-2|po(ck|rt|se)|prox"
    "|psio|pt\\-g|qa\\-a|qc(07|12|21|32|60|\\-[2-7]|i\\-)|qtek|r380|r600|raks"
    "|rim9|ro(ve|zo)|s55\\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\\-|oo|p\\-)|sdk\\/|"
    "se(c(\\-|0|1)|47|mc|nd|ri)|sgh\\-|shar|sie(\\-|m)|sk\\-0|sl(45|id)|"
    "sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\\-|v\\-|v )|sy(01|mb)|t2(18|50)"
    "|t6(00|10|18)|ta(gt|lk)|tcl\\-|tdg\\-|tel(i|m)|tim\\-|t\\-mo|to(pl|sh)"
    "|ts(70|m\\-|m3|m5)|tx\\-9|up(\\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|"
    "vk(40|5[0-3]|\\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|"
    "w3c(\\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|xda(\\-|2|g)|"
    "yas\\-|your|zeto|zte\\-", re.I | re.M)


class check_for_mobile(object):
    def process_request(self, request):
        request.is_mobile = False
        if "HTTP_USER_AGENT" in request.META:
            user_agent = request.META['HTTP_USER_AGENT']
            b_res = reg_b.search(user_agent)
            v_res = reg_v.search(user_agent[0:4])
            request.is_mobile = bool(b_res or v_res)


class check_menu_xpath(object):
    def process_request(self, request):
        if not request.path.count("media") and not request.path in ["/favicon.ico"]:
            try:
                cur_node = resolve(request.path)
                #print request.path, cur_node
                if cur_node.url_name in ["menu_folder"]:
                    # set xpath, no need for parsing
                    pass
                else:
                    menu_obj = Menu(settings.MENU_XML_DIR)
                    xml_doc = menu_obj.process(codecs.open(settings.MENU_XML_PATH, "r", "utf-8").read(), transform=False)

                    ref_str = []
                    for resolver in menu_obj.menu_resolvers:
                        ref_str = resolver.request_to_xpath(request)
                        if ref_str:
                            break

                    if ref_str == []:
                        ref_str = ["@ref='%s'" % ("%s:%s" % (cur_node.namespace,
                                                             cur_node.url_name) if cur_node.namespace else cur_node.url_name)]
                    if ref_str:
                        if isinstance(ref_str, list):
                            if cur_node.args:
                                ref_str.append("@refargs='%s'" % (cur_node.args[0]))
                            attr_str = u" and ".join(ref_str)
                            xpath_str = ".//*[%s]" % (attr_str)
                        else:
                            xpath_str = ref_str
                        xml_nodes = xml_doc.xpath(xpath_str)
                        if len(xml_nodes):
                            xml_node = xml_nodes[0]
                            request.session.update({"menu_xpath": xml_node.getroottree().getpath(xml_node)})
                            request.session.save()
                        else:
                            pass
                            #logger.debug("No xml_nodes found for '%s'" % xpath_str)
                    else:
                        logger.error("Empty ref_str list!")
            except Exception:  # pylint: disable-msg=W0703
                #logger.exception("Unable to resolve path '%s'" % request.path)
                pass
