#!/usr/bin/python-init -Otu

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.db.models import get_apps
from django.utils.datastructures import SortedDict

def sort_dependencies(app_list):
    """Sort a list of app,modellist pairs into a single list of models.

    The single list of models is sorted so that any model with a natural key
    is serialized before a normal model, and any model with a natural key
    dependency has it's dependencies serialized first.
    """
    from django.db.models import get_model, get_models
    # Process the list of models, and get the list of dependencies
    model_dependencies = []
    models = set()
    for app, model_list in app_list:
        if model_list is None:
            model_list = [cur_model for cur_model in get_models(app) if cur_model._meta.managed]
        for model in model_list:
            models.add(model)
            # Add any explicitly defined dependencies
            if hasattr(model, 'natural_key'):
                deps = getattr(model.natural_key, 'dependencies', [])
                if deps:
                    deps = [get_model(*d.split('.')) for d in deps]
            else:
                deps = []
            # Now add a dependency for any FK or M2M relation with
            # a model that defines a natural key
            for field in model._meta.fields:
                if hasattr(field.rel, 'to'):
                    rel_model = field.rel.to
                    # if hasattr(rel_model, 'natural_key'):
                    if rel_model._meta.object_name != model._meta.object_name:
                        deps.append(rel_model)
            for field in model._meta.many_to_many:
                rel_model = field.rel.to
                deps.append(rel_model)
            model_dependencies.append((model, deps))
    model_dependencies.reverse()
    # Now sort the models to ensure that dependencies are met. This
    # is done by repeatedly iterating over the input list of models.
    # If all the dependencies of a given model are in the final list,
    # that model is promoted to the end of the final list. This process
    # continues until the input list is empty, or we do a full iteration
    # over the input models without promoting a model to the final list.
    # If we do a full iteration without a promotion, that means there are
    # circular dependencies in the list.
    # pprint.pprint(model_dependencies)
    model_list = []
    while model_dependencies:
        skipped = []
        changed = False
        while model_dependencies:
            model, deps = model_dependencies.pop()
            # If all of the models in the dependency list are either already
            # on the final model list, or not on the original serialization list,
            # then we've found another model with all it's dependencies satisfied.
            found = True
            for candidate in ((d not in models or d in model_list) for d in deps):
                if not candidate:
                    found = False
            if found:
                model_list.append(model)
                changed = True
            else:
                skipped.append((model, deps))
        if not changed:
            raise SyntaxError("Can't resolve dependencies for %s in serialized app list." %
                              ', '.join('%s.%s' % (model._meta.app_label, model._meta.object_name)
                                        for model, deps in sorted(skipped, key=lambda obj: obj[0].__name__))
                              )
        model_dependencies = skipped
    return model_list

def main():
    app_dict = SortedDict([(app, None) for app in get_apps()])
    mod_list = sort_dependencies(app_dict.items())
    for mod in mod_list:
        if mod._meta.app_label == "backbone":
            print mod._meta.db_table
    print
    print " ".join([mod._meta.db_table for mod in mod_list if mod._meta.app_label == "backbone"])
        # print mod._meta.app_label, mod._meta.object_name, mod._meta

if __name__ == "__main__":
    main()
