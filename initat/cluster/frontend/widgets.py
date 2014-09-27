from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
import pprint  # @UnusedImport

__all__ = [
    "ui_select_widget",
    "ui_select_multiple_widget",
]


# class
class ui_select_base(Widget):
    def ui_render(self, name, value, attrs=None, choices=(), multi=False):
        _fin = self.build_attrs(attrs, name=name)
        # pprint.pprint(_fin)
        _readonly = _fin.get("readonly", "false")
        if _readonly.lower() in ["false", "true"]:
            _readonly = _readonly.lower()
        if multi:
            show_null = False
        else:
            if "null" in _fin:
                if _fin["null"].lower()[0] in ["1", "y", "t"]:
                    show_null = True
                else:
                    show_null = False
            else:
                show_null = False
        # pprint.pprint(_fin)
        _style = "max-width:400px; min-width:240px;"
        _templ = _fin.get(
            "listtemplate",
            "<div ng-bind-html='{}.{} | highlight: $select.search'></div>".format(
                _fin.get("repeatvar", "value"),
                _fin["display"]
            ),
        )
        if show_null:
            _out_list = [
                "<div class='input-group' style='{}'>".format(_style),
                "<ui-select ng-model='{}' ng-disabled='{}'>".format(
                    _fin["ng-model"],
                    _readonly,
                )
            ]
        else:
            _out_list = [
                "<ui-select {} ng-model='{}' style='{}' ng-disabled='{}'>".format(
                    "multiple" if multi else "",
                    _fin["ng-model"],
                    _style,
                    _readonly,
                )
            ]
        if multi:
            _out_list.extend(
                [
                    "<ui-select-match placeholder='{}'>{{{{$item.{}}}}}</ui-select-match>".format(
                        _fin.get("placeholder", "..."),
                        _fin["display"],
                    ),
                ]
            )
        else:
            _out_list.extend(
                [
                    "<ui-select-match placeholder='{}'>{{{{$select.selected.{}}}}}</ui-select-match>".format(
                        _fin.get("placeholder", "..."),
                        _fin["display"],
                    ),
                ]
            )
        _out_list.extend(
            [
                "<ui-select-choices repeat='{}{}'{}>".format(
                    _fin["repeat"],
                    "| props_filter:{}".format(_fin["filter"]) if "filter" in _fin else "",
                    " group-by='{}'".format(_fin["groupby"]) if "groupby" in _fin else "",
                ),
                _templ,
                # #"<div ng-bind-html='{}.{} | highlight: $select.search'></div>".format(
                #    _fin.get("repeatvar", "value"),
                #    _fin["display"]
                # ),
                "</ui-select-choices>",
                "</ui-select>",
            ]
        )
        if show_null:
            _out_list.extend(
                [
                    "<span class='input-group-btn'>",
                    '<button type="button" ng-click="{} = undefined" class="btn btn-default">'.format(_fin["ng-model"]),
                    '<span class="glyphicon glyphicon-trash"></span>',
                    '</button>',
                    "</span>",
                    "</div>",
                ]
            )
        return mark_safe(
            "\n".join(
                _out_list
            )
        )


class ui_select_widget(ui_select_base):
    def render(self, name, value, attrs=None, choices=()):
        return self.ui_render(name, value, attrs, choices, multi=False)


class ui_select_multiple_widget(ui_select_base):
    def render(self, name, value, attrs=None, choices=()):
        return self.ui_render(name, value, attrs, choices, multi=True)
