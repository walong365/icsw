#!/bin/sh

# collect as C-code, works for gettext("to translate")
xgettext ../initat/cluster/frontend/static/icsw/*/*.coffee -LPython --omit-header -o po/template_coffee.pot
