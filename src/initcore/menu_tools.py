#!/usr/bin/python-init -Otu
import pdb
from StringIO import StringIO
from django.core.urlresolvers import reverse
import base64
import codecs
from django.conf import settings
from lxml import etree
from lxml.builder import E
import os

COPY_ATTRIBUTES_SS = """<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    >
    <xsl:template name="copy-attribute">
        <xsl:param name="node"/>
        <xsl:param name="attrname"/>
        <xsl:param name="default"/>
        <xsl:variable name="parentattr" select="$node/ancestor::*/@*[name() = $attrname]" />
        <xsl:variable name="nodeattr" select="$node/@*[name() = $attrname]" />
        <xsl:choose>
            <xsl:when test="$nodeattr">
                <xsl:attribute name="{$attrname}"><xsl:value-of select="$nodeattr"/></xsl:attribute>
            </xsl:when>
            <xsl:when test="$parentattr">
                <xsl:attribute name="{$attrname}"><xsl:value-of select="$parentattr"/></xsl:attribute>
            </xsl:when>
            <xsl:otherwise>
                <xsl:attribute name="{$attrname}"><xsl:value-of select="$default"/></xsl:attribute>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="menuitem">
        <xsl:param name="node" select="."/>
        <menuitem>
            <xsl:call-template name="copy-attribute">
                <xsl:with-param name="node" select="$node"/>
                <xsl:with-param name="attrname" select="'role'"/>
                <xsl:with-param name="default" select="'olim.admin'"/>
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
            <xsl:if test="@ref"><xsl:attribute name="ref"><xsl:value-of select="@ref"/></xsl:attribute></xsl:if>
            <xsl:if test="@refargs"><xsl:attribute name="refargs"><xsl:value-of select="@refargs"/></xsl:attribute></xsl:if>
            <xsl:if test="@xpath"><xsl:attribute name="xpath"><xsl:value-of select="@xpath"/></xsl:attribute></xsl:if>
            
            <!-- meta attributes -->
            <!-- think about a *clean* way to extract these values from inherit_attributes -->
            <xsl:if test="@id"><xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@table"><xsl:attribute name="table"><xsl:value-of select="@table"/></xsl:attribute></xsl:if>
            <xsl:if test="@table1"><xsl:attribute name="table1"><xsl:value-of select="@table1"/></xsl:attribute></xsl:if>
            <xsl:if test="@table2"><xsl:attribute name="table2"><xsl:value-of select="@table2"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@action"><xsl:attribute name="action"><xsl:value-of select="@action"/></xsl:attribute></xsl:if>
            <xsl:if test="@actionname"><xsl:attribute name="actionname"><xsl:value-of select="@actionname"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@filter"><xsl:attribute name="filter"><xsl:value-of select="@filter"/></xsl:attribute></xsl:if>
            <xsl:if test="@filter1"><xsl:attribute name="filter1"><xsl:value-of select="@filter1"/></xsl:attribute></xsl:if>
            <xsl:if test="@filter2"><xsl:attribute name="filter2"><xsl:value-of select="@filter2"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@sort"><xsl:attribute name="sort"><xsl:value-of select="@sort"/></xsl:attribute></xsl:if>
            <xsl:if test="@sort1"><xsl:attribute name="sort1"><xsl:value-of select="@sort1"/></xsl:attribute></xsl:if>
            <xsl:if test="@sort2"><xsl:attribute name="sort2"><xsl:value-of select="@sort2"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@list"><xsl:attribute name="list"><xsl:value-of select="@list"/></xsl:attribute></xsl:if>
            <xsl:if test="@nolist"><xsl:attribute name="nolist"><xsl:value-of select="@nolist"/></xsl:attribute></xsl:if>
            <xsl:if test="@list1"><xsl:attribute name="list1"><xsl:value-of select="@list1"/></xsl:attribute></xsl:if>
            <xsl:if test="@nolist1"><xsl:attribute name="nolist1"><xsl:value-of select="@nolist1"/></xsl:attribute></xsl:if>
            <xsl:if test="@list2"><xsl:attribute name="list2"><xsl:value-of select="@list2"/></xsl:attribute></xsl:if>
            <xsl:if test="@nolist2"><xsl:attribute name="nolist2"><xsl:value-of select="@nolist2"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@edit"><xsl:attribute name="edit"><xsl:value-of select="@edit"/></xsl:attribute></xsl:if>
            <xsl:if test="@noedit"><xsl:attribute name="noedit"><xsl:value-of select="@noedit"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@form"><xsl:attribute name="form"><xsl:value-of select="@form"/></xsl:attribute></xsl:if>
            <xsl:if test="@noform"><xsl:attribute name="noform"><xsl:value-of select="@noform"/></xsl:attribute></xsl:if>
            <xsl:if test="@form1"><xsl:attribute name="form1"><xsl:value-of select="@form1"/></xsl:attribute></xsl:if>
            <xsl:if test="@noform1"><xsl:attribute name="noform1"><xsl:value-of select="@noform1"/></xsl:attribute></xsl:if>
            <xsl:if test="@form2"><xsl:attribute name="form2"><xsl:value-of select="@form2"/></xsl:attribute></xsl:if>
            <xsl:if test="@noform2"><xsl:attribute name="noform2"><xsl:value-of select="@noform2"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@trail"><xsl:attribute name="trail"><xsl:value-of select="@trail"/></xsl:attribute></xsl:if>
            <xsl:if test="@notrail"><xsl:attribute name="notrail"><xsl:value-of select="@notrail"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@add"><xsl:attribute name="add"><xsl:value-of select="@add"/></xsl:attribute></xsl:if>
            <xsl:if test="@noadd"><xsl:attribute name="noadd"><xsl:value-of select="@noadd"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@addable"><xsl:attribute name="addable"><xsl:value-of select="@addable"/></xsl:attribute></xsl:if>
            <xsl:if test="@deleteable"><xsl:attribute name="deleteable"><xsl:value-of select="@deleteable"/></xsl:attribute></xsl:if>
            <xsl:if test="@editable"><xsl:attribute name="editable"><xsl:value-of select="@editable"/></xsl:attribute></xsl:if>
            
            <xsl:if test="@key"><xsl:attribute name="key"><xsl:value-of select="@key"/></xsl:attribute></xsl:if>
            <xsl:if test="@frozen"><xsl:attribute name="frozen"><xsl:value-of select="@frozen"/></xsl:attribute></xsl:if>
            
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
    def resolve(self, url, cur_id, context):
        full_path = os.path.join(self.menu_obj.root_dir, url)
        if os.path.exists(full_path):
            return self.resolve_filename(full_path, context)
        else:
            raise IOError, "no file named '%s' found" % (full_path)

class olim_menu(object):
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
        my_ns["filter_node"]    = self._filter_node
        my_ns["get_href"]       = self._get_href
        my_ns["translate_node"] = self._translate_node
        self.__kwargs = kwargs
        self.menu_resolvers = []
        if hasattr(settings, "MENU_XML_RESOLVERS") and isinstance(settings.MENU_XML_RESOLVERS, tuple):
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
            # second step: filter
            xml_doc = self._second_trans(xml_doc)
        return xml_doc
    def to_html(self, in_xml, is_mobile, for_dynatree, **kwargs):
        kwargs.update({"for_dynatree" : "1" if for_dynatree else "0",
                       "is_mobile"    : "1" if is_mobile else "0"})
        return self._to_html_trans(in_xml, **dict([(key, etree.XSLT.strparam(value)) for key, value in kwargs.iteritems()]))
    def _filter_node(self, context, node, *args):
        node = node[0]
        keep_node = True
        for filter_key, filter_value in dict([(key.split("_", 1)[1], value) for key, value in self.__kwargs.iteritems() if key.startswith("filter_")]).iteritems():
            # debug print
            # print node.attrib["name"], filter_key, filter_value, node.attrib.get(filter_key, "???")
            if type(filter_value) != type([]):
                filter_value = [filter_value]
            if filter_key in node.attrib:
                if node.attrib[filter_key] not in filter_value:
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
            except:
                href = reverse("session:menu_folder", args=[base64.b64encode(node.attrib["xpath"])])
            else:
                pass
        else:
            href = reverse("session:menu_folder", args=[base64.b64encode(node.attrib["xpath"])])
        return href
    def _translate_node(self, context, node, *args):
        return node[0].attrib.get("name", "").strip() or "no name set"

def get_menu_html(request, is_mobile, for_dynatree):
    #print is_mobile, for_dynatree
    if is_mobile:
        useragent_list = ["all", "mobile"]
    else:
        useragent_list = ["all", "pc"]
    my_menu = olim_menu(settings.MENU_XML_DIR, **{"filter_useragent" : useragent_list})
    xml_doc = my_menu.process(codecs.open(settings.MENU_XML_PATH, "r", "utf-8").read())
    if request.session.has_key("menu_xpath"):
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
    xml_doc.attrib.update({"id"    : "main_navigation",
                           "class" : "sf-menu"})
    #print is_mobile, for_dynatree, "***", menu_xpath
    return etree.tostring(my_menu.to_html(xml_doc, is_mobile, for_dynatree,
                                          user=unicode(request.user),
                                          menu_xpath=menu_xpath))
        

class menu_resolver_base(object):
    """ Base object for all menu resolvers. Primarily there to document the
    structure of of menu_resolver. """
    def node_to_href(self, node):
        """ Turn a xml node into a valid href link """
        raise NotImplementedError("You have to implement node_to_href")        
    
    def request_to_xpath(self, request):
        raise NotImplementedError("You have to implement request_to_xpath")        

class menu_direct_link_resolver(menu_resolver_base):
    """ Resolves all links of type *proto://uri* """    
    def node_to_href(self, node):
        href = None
        if re.match(r'[http|https|ftp]://.*', node.attrib["ref"]):
            href = node.attrib["ref"]
        return href
    
    def request_to_xpath(self, request):
        ref_str = []
        return ref_str
        
        