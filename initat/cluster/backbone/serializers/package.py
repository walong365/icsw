#!/usr/bin/python-init

from initat.cluster.backbone.models import package_service, package_repo, package_search, package_search_result, \
    package_device_connection, package
from rest_framework import serializers

__all__ = [
    "package_serializer",
    "package_repo_serializer",
    "package_search_serializer",
    "package_search_result_serializer",
    "package_service_serializer",
    "package_device_connection_serializer",
    "package_device_connection_wp_serializer",
]


class package_service_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_service


class package_repo_serializer(serializers.ModelSerializer):
    service_name = serializers.Field(source="get_service_name")

    class Meta:
        model = package_repo


class package_search_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_search


class package_search_result_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_search_result


class package_device_connection_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_device_connection


class package_serializer(serializers.ModelSerializer):
    target_repo_name = serializers.Field(source="target_repo_name")

    class Meta:
        model = package


class package_device_connection_wp_serializer(serializers.ModelSerializer):
    package = package_serializer()

    class Meta:
        model = package_device_connection
