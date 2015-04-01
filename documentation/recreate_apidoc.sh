#!/bin/bash

PACKAGES="../src/initcore"
OUTDIR="source/api"

echo "Deleting old api docs"
rm -i $OUTDIR/*

for i in $PACKAGES; do
    sphinx-apidoc -o $OUTDIR $i
done

rm $OUTDIR/modules.rst
