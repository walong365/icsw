#!/bin/bash

cat $1 | tr "\"" "\n" | grep url | while read line ; do
    var_name=$(echo $line |cut -d "'" -f 2 | tr ":" "_" |tr [:lower:] [:upper:] )
    echo \ \ \ \ \"$var_name\": \"$line\"
done | sort
