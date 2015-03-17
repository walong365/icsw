#!/bin/sh

./extract_coffeescript_strings.sh

grunt nggettext_extract


COMBINED_FILE=po/all.pot

rm "$COMBINED_FILE"
msgcat -o "$COMBINED_FILE" `find po -name \*.pot`
