#!/usr/bin/python-init

from rest_framework import serializers
from initat.cluster.backbone.models import domain_tree_node, category

__all__ = [
    "domain_tree_node_serializer",
    "category_serializer",
]


class domain_tree_node_serializer(serializers.ModelSerializer):
    tree_info = serializers.Field(source="__unicode__")

    class Meta:
        model = domain_tree_node


class category_serializer(serializers.ModelSerializer):
    allow_add_remove = True
    num_refs = serializers.Field(source="get_references")

    class Meta:
        model = category
