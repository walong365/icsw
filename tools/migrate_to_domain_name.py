#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
""" migrates from network-based names to domain-base names """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import pprint
from django.conf import settings
from initat.cluster.backbone.models import domain_name, network, domain_name_tree

class tree_node(object):
    def __init__(self, name="", depth=0):
        self.name = name
        self.depth = depth
        self.postfix = ""
        self.sub_nodes = {}
        if not self.name:
            self.top_node = True
        else:
            self.top_node = False
    def feed_name(self, name, postfix):
        if not name.strip():
            self.postfix = postfix
            # nothing more to add or top node
            return self
        else:
            name_parts = list(name.strip().split("."))
            last_part = name_parts[-1]
            if last_part not in self.sub_nodes:
                # create new sub_node
                self.sub_nodes[last_part] = tree_node(last_part, depth=self.depth + 1)
            return self.sub_nodes[last_part].feed_name(".".join(name_parts[:-1]), postfix)
    def show_tree(self):
        return "\n".join([unicode(self)] + ["%s : %s" % (key, value.show_tree()) for key, value in self.sub_nodes.iteritems()])
    def create_db_entries(self, top_node=None):
        full_name = self.name
        if top_node and top_node.name:
            full_name = "%s.%s" % (full_name, top_node.name)
        cur_db = domain_name(
            name=self.name,
            parent=top_node.db_obj if top_node else None,
            full_name=full_name,
            node_postfix=self.postfix,
            depth=self.depth,
        )
        cur_db.save()
        self.db_obj = cur_db
        [value.create_db_entries(top_node=self) for value in self.sub_nodes.itervalues()]
    def __unicode__(self):
        return "%s (PF '%s', %d)" % (self.name or "TOP NODE", self.postfix, self.depth)
            
def main():
    # testing
    domain_name.objects.all().delete()
    cur_dns = domain_name.objects.all()
    if len(cur_dns):
        pass
    else:
        print "Migrating to domain_name system"
        net_dict = {}
        net_tree = tree_node()
        for cur_net in network.objects.all():
            dns_node = net_tree.feed_name(cur_net.name, cur_net.postfix)
            net_dict[cur_net.pk] = {
                "obj"      : cur_net,
                "dns_node" : dns_node,
                "name"     : cur_net.name,
                "parts"    : cur_net.name.strip().split("."),
                "postfix"  : cur_net.postfix,
            }
        pprint.pprint(net_dict)
        print net_tree.show_tree()
        net_tree.create_db_entries()
    
if __name__ == "__main__":
    main()
