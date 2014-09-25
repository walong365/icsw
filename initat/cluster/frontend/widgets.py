from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
import pprint  # @UnusedImport


class ui_select_widget(Widget):
    def render(self, name, value, attrs=None, choices=()):
        _fin = self.build_attrs(attrs, name=name)
        if "null" in _fin:
            if _fin["null"].lower()[0] in ["1", "y", "t"]:
                show_null = True
            else:
                show_null = False
        else:
            show_null = False
        # pprint.pprint(_fin)
        _style = "max-width:400px; min-width:240px;"
        if show_null:
            _out_list = [
                "<div class='input-group' style='{}'>".format(_style),
                "<ui-select ng-model='{}'>".format(
                    _fin["ng-model"],
                )
            ]
        else:
            _out_list = [
                "<ui-select ng-model='{}' style='{}'>".format(
                    _fin["ng-model"],
                    _style,
                )
            ]
        _out_list.extend(
            [
                "<ui-select-match placeholder='{}'>{{{{$select.selected.{}}}}}</ui-select-match>".format(
                    _fin.get("placeholder", "..."),
                    _fin["display"],
                ),
                "<ui-select-choices repeat='{}{}'{}>".format(
                    _fin["repeat"],
                    "| props_filter:{}".format(_fin["filter"]) if "filter" in _fin else "",
                    " group-by='{}'".format(_fin["groupby"]) if "groupby" in _fin else "",
                ),
                "<div ng-bind-html='{}.{} | highlight: $select.search'></div>".format(
                    _fin.get("repeatvar", "value"),
                    _fin["display"]
                ),
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


class ui_select_multiple_widget(Widget):
    def render(self, name, value, attrs=None, choices=()):
        _fin = self.build_attrs(attrs, name=name)
        _style = "max-width:400px; min-width:240px;"
        _out_list = [
            "<ui-select multiple ng-model='{}' style='{}'>".format(
                _fin["ng-model"],
                _style,
            ),
            "<ui-select-match placeholder='{}'>{{{{$item.{}}}}}</ui-select-match>".format(
                _fin.get("placeholder", "..."),
                _fin["display"],
            ),
            "<ui-select-choices repeat='{}{}'>".format(
                _fin["repeat"],
                "| props_filter:{}".format(_fin["filter"]) if "filter" in _fin else "",
            ),
            "<div ng-bind-html='{}.{} | highlight: $select.search'></div>".format(
                _fin.get("repeatvar", "value"),
                _fin["display"],
            ),
            "</ui-select-choices>",
            "</ui-select>",
        ]
        return mark_safe(
            "\n".join(
                _out_list
            )
        )
