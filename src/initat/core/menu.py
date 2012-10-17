import re
import os
import base64
import codecs
from StringIO import StringIO
from lxml import etree
from lxml.builder import E

from django.core.urlresolvers import reverse
from django.conf import settings

from initat.core import logger


COPY_ATTRIBUTES_SS = """<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    >
    <xsl:template name="get-attribute">
        <xsl:param name="node"/>
        <xsl:param name="attrname"/>
        <xsl:param name="default"/>
        <xsl:variable name="parentattr" select="$node/parent::node()/@*[name() = $attrname]" />
        <xsl:choose>
            <xsl:when test="$parentattr">
                <xsl:value-of select="$parentattr"/>
            </xsl:when>
            <xsl:when test="$node/parent::node()">
                <xsl:call-template name="get-attribute">
                    <xsl:with-param name="node" select="$node/parent::node()"/>
                    <xsl:with-param name="attrname" select="$attrname"/>
                    <xsl:with-param name="default" select="$default"/>
                </xsl:call-template>
                </xsl:when>
            <xsl:otherwise>
                <!-- return default value if no valid parent found -->
                <xsl:value-of select="$default"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template name="copy-attribute">
        <xsl:param name="node"/>
        <xsl:param name="attrname"/>
        <xsl:param name="default"/>
        <xsl:variable name="parentattr">
            <xsl:call-template name="get-attribute">
                <xsl:with-param name="node" select="$node"/>
                <xsl:with-param name="attrname" select="$attrname"/>
                <xsl:with-param name="default" select="$default"/>
            </xsl:call-template>
        </xsl:variable>
        <xsl:variable name="nodeattr" select="$node/@*[name() = $attrname]" />
        <xsl:choose>
            <xsl:when test="$nodeattr">
                <xsl:attribute name="{$attrname}"><xsl:value-of select="$nodeattr"/></xsl:attribute>
            </xsl:when>
            <xsl:otherwise>
                <xsl:attribute name="{$attrname}"><xsl:value-of select="$parentattr"/></xsl:attribute>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="menuitem">
        <xsl:param name="node" select="."/>
        <menuitem>
            <!-- Copy all attributes to let possibly existing MML attributes pass -->
            <xsl:copy-of select="@*" />
            <!-- Menu specific attribute overrides -->
            <xsl:call-template name="copy-attribute">
                <xsl:with-param name="node" select="$node"/>
                <xsl:with-param name="attrname" select="'role'"/>
                <!--xsl:with-param name="default" select="'olim.admin'"/-->
                <xsl:with-param name="default" select="''"/>
            </xsl:call-template>
            <xsl:call-template name="copy-attribute">
                <xsl:with-param name="node" select="$node"/>
                <xsl:with-param name="attrname" select="'rolelevel'"/>
                <xsl:with-param name="default" select="'E'"/>
            </xsl:call-template>
            <xsl:call-template name="copy-attribute">
                <xsl:with-param name="node" select="$node"/>
                <xsl:with-param name="attrname" select="'undercon'"/>
                <xsl:with-param name="default" select="'0'"/>
            </xsl:call-template>
            <xsl:call-template name="copy-attribute">
                <xsl:with-param name="node" select="$node"/>
                <xsl:with-param name="attrname" select="'useragent'"/>
                <xsl:with-param name="default" select="'all'"/>
            </xsl:call-template>

            <xsl:if test="@name"><xsl:attribute name="name"><xsl:value-of select="@name"/></xsl:attribute></xsl:if>
            <xsl:if test="@de"><xsl:attribute name="de"><xsl:value-of select="@de"/></xsl:attribute></xsl:if>
            <xsl:if test="@en"><xsl:attribute name="en"><xsl:value-of select="@en"/></xsl:attribute></xsl:if>
            <xsl:if test="@ref"><xsl:attribute name="ref"><xsl:value-of select="@ref"/></xsl:attribute></xsl:if>
            <xsl:if test="@refargs"><xsl:attribute name="refargs"><xsl:value-of select="@refargs"/></xsl:attribute></xsl:if>
            <xsl:if test="@xpath"><xsl:attribute name="xpath"><xsl:value-of select="@xpath"/></xsl:attribute></xsl:if>

            <xsl:value-of select="$node/text()"/>
            <xsl:apply-templates/>
        </menuitem>
    </xsl:template>
    <xsl:template name="copy" match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    </xsl:stylesheet>
"""

FILTER_ATTRIBUTES_SS = """<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:py="http://www.init.at/xslt/functions"
    >
    <xsl:template match="menuitem">
        <xsl:if test="@undercon != '2'">
            <xsl:if test="py:filter_node(.)">
                <menuitem>
                    <xsl:copy-of select="@*"/>
                    <xsl:apply-templates/>
                </menuitem>
            </xsl:if>
        </xsl:if>
    </xsl:template>
    <xsl:template name="copy" match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    </xsl:stylesheet>
"""

TRANS_TO_HTML_SS = """<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:py="http://www.init.at/xslt/functions"
    >
    <xsl:template match="menu">
        <ul>
            <xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute>
            <xsl:attribute name="class"><xsl:value-of select="@class"/></xsl:attribute>
            <xsl:if test="$for_dynatree = '0'">
                <li>
                    <a href="javascript:show_menu()"><xsl:value-of select="$user"/></a>
                </li>
            </xsl:if>
            <xsl:apply-templates/>
        </ul>
    </xsl:template>
    <xsl:template match="menuitem">
        <li>
            <xsl:choose>
                <xsl:when test="count(child::menuitem)">
                    <xsl:if test="$for_dynatree = '1'">
                        <xsl:attribute name="class">folder</xsl:attribute>
                        <xsl:if test="@expand = '1'">
                            <xsl:attribute name="data">expand: true</xsl:attribute>
                        </xsl:if>
                    </xsl:if>
                </xsl:when>
                <xsl:when test="$for_dynatree = '1' and @expand = '1'">
                    <xsl:attribute name="data">focus: true, select: true, expand: true</xsl:attribute>
                </xsl:when>
            </xsl:choose>
            <a>
                <xsl:choose>
                    <xsl:when test="@undercon = '1' or (count(descendant::menuitem) and not(descendant::menuitem[@undercon = '0']))">
                        <xsl:text>[</xsl:text><xsl:value-of select="py:translate_node(.)"/><xsl:text>]</xsl:text>
                    </xsl:when>
                    <xsl:otherwise>
                            <xsl:attribute name="href">
                                <xsl:value-of select="py:get_href(.)"/>
                            </xsl:attribute>
                            <xsl:value-of select="py:translate_node(.)"/>
                    </xsl:otherwise>
                </xsl:choose>
            </a>
            <xsl:if test="count(child::menuitem)">
                <ul>
                    <xsl:apply-templates/>
                </ul>
            </xsl:if>
        </li>
    </xsl:template>
    <xsl:template name="copy" match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    </xsl:stylesheet>
"""


class local_resolver(etree.Resolver):
    def __init__(self, menu_obj):
        self.menu_obj = menu_obj
        super(local_resolver, self).__init__()

    def resolve(self, url, cur_id, context):  # pylint: disable-msg=W0613
        full_path = os.path.join(self.menu_obj.root_dir, url)
        if os.path.exists(full_path):
            return self.resolve_filename(full_path, context)
        else:
            raise IOError("no file named '%s' found" % (full_path))


class Menu(object):
    def __init__(self, root_dir, **kwargs):
        self.root_dir = os.path.normpath(os.path.join(settings.FILE_ROOT, root_dir))
        self._parser = etree.XMLParser(remove_comments=True, ns_clean=True)
        self._parser.resolvers.add(local_resolver(self))
        # first step: copy various attributes to complete tree
        self._first_trans = etree.XSLT(etree.parse(StringIO(COPY_ATTRIBUTES_SS), parser=self._parser),
                                       access_control=etree.XSLTAccessControl.DENY_WRITE)
        self._second_trans = etree.XSLT(etree.parse(StringIO(FILTER_ATTRIBUTES_SS), parser=self._parser),
                                        access_control=etree.XSLTAccessControl.DENY_WRITE)
        self._to_html_trans = etree.XSLT(etree.parse(StringIO(TRANS_TO_HTML_SS), parser=self._parser),
                                         access_control=etree.XSLTAccessControl.DENY_WRITE)
        my_ns = etree.FunctionNamespace("http://www.init.at/xslt/functions")
        my_ns["filter_node"] = self._filter_node
        my_ns["get_href"] = self._get_href
        my_ns["translate_node"] = self._translate_node
        self.__kwargs = kwargs
        # Attributes that contain a list of values (for filtering)
        self.list_attribs = ("role", )
        self.menu_resolvers = []
        if hasattr(settings, "MENU_XML_RESOLVERS") and isinstance(settings.MENU_XML_RESOLVERS, (tuple, list)):
            for resolver in settings.MENU_XML_RESOLVERS:
                file_name = ".".join(resolver.split(".")[0:-1])
                class_name = resolver.split(".")[-1]
                imp = __import__(file_name, globals(), locals(), [class_name, ])
                self.menu_resolvers.append(getattr(imp, class_name)())

    def process(self, menu_content, **kwargs):
        xml_doc = etree.parse(StringIO(menu_content), self._parser)
        # handle includes
        xml_doc.xinclude()
        # add xpath attributes
        for cur_node in xml_doc.xpath(".//menuitem|/menu"):
            cur_node.attrib["xpath"] = cur_node.getroottree().getpath(cur_node)
        if kwargs.get("transform", True):
            # first step: copy all attributes
            xml_doc = self._first_trans(xml_doc)
            #import pprint
            #pprint.pprint(self._first_trans.error_log)
            #print etree.tostring(xml_doc, pretty_print=True)
            # second step: filter
            xml_doc = self._second_trans(xml_doc)
        return xml_doc

    def to_html(self, in_xml, is_mobile, for_dynatree, **kwargs):
        kwargs.update({"for_dynatree": "1" if for_dynatree else "0",
                       "is_mobile": "1" if is_mobile else "0"})
        return self._to_html_trans(in_xml, **dict([(key, etree.XSLT.strparam(value)) for key, value in kwargs.iteritems()]))

    def _filter_node(self, context, node, *args):
        node = node[0]
        keep_node = True
        for filter_key, filter_value in dict([(key.split("_", 1)[1], value) for key, value in self.__kwargs.iteritems() if key.startswith("filter_")]).iteritems():
            # debug print
            # print node.attrib["name"], filter_key, filter_value, node.attrib.get(filter_key, "???")
            if not isinstance(filter_value, (list, tuple)):
                filter_value = [filter_value]
            if filter_key in node.attrib:
                # Admin roles get everything
                if filter_key == "role" and (set(filter_value) & set(settings.MML_ADMIN_ROLES)):
                    continue
                if filter_key in self.list_attribs:
                    value_list = node.attrib[filter_key].split(",")
                    if value_list == [""]:
                        continue
                    if not set(filter_value) & set(value_list):
                        keep_node = False
                elif node.attrib[filter_key] not in filter_value:
                    keep_node = False
        return keep_node

    def _get_href(self, context, node, *args):
        node = node[0]
        if "ref" in node.attrib:
            try:
                href = None
                for resolver in self.menu_resolvers:
                    href = resolver.node_to_href(node)
                    if href:
                        break
                if not href:
                    # If all registered resolvers found nothing, do standard resolving
                    href = reverse(node.attrib["ref"], args=[part.strip() for part in node.attrib.get("refargs", "").split(",") if part.strip()])
            except Exception:  # pylint: disable-msg=W0703
                logger.exception("Exception while resolving in menu")
                href = reverse("initcore:menu_folder", args=[base64.b64encode(node.attrib["xpath"])])
            else:
                pass
        else:
            href = reverse("initcore:menu_folder", args=[base64.b64encode(node.attrib["xpath"])])
        return href

    def _translate_node(self, context, node, *args):
        cur_lang = self.__kwargs.get("language_code", settings.DEFAULT_LANGUAGE)
        ret_str = ""
        for pref in [cur_lang, "de", "name", "en"]:
            if pref in node[0].attrib:
                ret_str = node[0].attrib[pref]
                break
        return ret_str.strip() or "no name set"


def get_menu_html(request, is_mobile, for_dynatree):
    #print is_mobile, for_dynatree
    if is_mobile:
        useragent_list = ["all", "mobile"]
    else:
        useragent_list = ["all", "pc"]
    if hasattr(request, "session"):
        current_role = request.session.get("OLIM_ROLE", None)
        language = request.session.get("language", settings.DEFAULT_LANGUAGE)
    else:
        current_role = None
        language = settings.DEFAULT_LANGUAGE
    my_menu = Menu(settings.MENU_XML_DIR, **{"filter_useragent": useragent_list,
                                             "language_code": language,
                                             "filter_role": current_role})
    xml_doc = my_menu.process(codecs.open(settings.MENU_XML_PATH, "r", "utf-8").read())
    if "menu_xpath" in request.session:
        menu_xpath = request.session["menu_xpath"]
    else:
        if len(xml_doc.getroot()):
            menu_xpath = xml_doc.getroot().getroottree().getpath(xml_doc.getroot())
        else:
            menu_xpath = "/"
    active_node = xml_doc.xpath(".//menuitem[@xpath='%s']|/menu[@xpath='%s']" % (menu_xpath,
                                                                                 menu_xpath))
    trace = []
    if active_node:
        active_node = active_node[0]
        while active_node is not None:
            trace.insert(0, active_node)
            active_node = active_node.getparent()
    if for_dynatree:
        for entry in trace:
            entry.attrib["expand"] = "1"
        xml_doc = xml_doc.getroot()
    else:
        if trace:
            xml_doc = None
            for entry in trace:
                new_el = getattr(E, entry.tag)(entry.text or u"", **entry.attrib)
                if xml_doc is None:
                    xml_doc = new_el
                    # add dummy entry for first menuitem
                    new_el = E.menuitem(entry.text or u"", **entry.attrib)
                    new_el.attrib["name"] = new_el.attrib.get("name", "OLIM")
                xml_doc.append(new_el)
                el_type = type(etree.Element("test"))
                new_el.extend([getattr(E, child.tag)(child.text or u"",
                                                     *[getattr(E, sub_child.tag)(sub_child.text or u"",
                                                                                 *[getattr(E, sub_sub_child.tag)(sub_sub_child.text or u"",
                                                                                                                 **sub_sub_child.attrib) for sub_sub_child in sub_child if type(sub_sub_child) == el_type],
                                                                                 **sub_child.attrib) for sub_child in child if type(sub_child) == el_type],
                                                     **child.attrib) for child in entry if type(child) == el_type])
        else:
            xml_doc = xml_doc.getroot()
    xml_doc.attrib.update({"id": "main_navigation",
                           "class": "sf-menu"})
    #print is_mobile, for_dynatree, "***", menu_xpath
    return etree.tostring(my_menu.to_html(xml_doc, is_mobile, for_dynatree,
                                          user=unicode(request.user),
                                          menu_xpath=menu_xpath))


class MenuResolverBase(object):
    """
    Base object for all menu resolvers.

    Primarily here to document the structure of a menu resolver.
    """
    def node_to_href(self, node):
        """ Take a xml node with a ref attribute and return a valid href link """
        raise NotImplementedError("You have to implement node_to_href")

    def request_to_xpath(self, request):
        raise NotImplementedError("You have to implement request_to_xpath")


class menu_direct_link_resolver(MenuResolverBase):
    """ Resolves all links of type *http|https|ftp://path* """
    def node_to_href(self, node):
        href = None
        if re.match(r'(http|https|ftp)://.*', node.attrib["ref"]):
            href = node.attrib["ref"]
        return href

    def request_to_xpath(self, request):
        return []
