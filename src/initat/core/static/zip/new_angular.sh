#!/bin/bash

ANG_VERS=$(ls -1 angular*zip | cut -d "-" -f 2 | sed s/.zip//g)

echo "New angular version is ${ANG_VERS}"

unzip angular-${ANG_VERS}.zip

cd angular-${ANG_VERS}

TARG_DIR=../../js/libs

cp -a angular.min.js ${TARG_DIR}/angular-${ANG_VERS}.min.js
cp -a angular.min.js.map ${TARG_DIR}/

git add ${TARG_DIR}/angular-${ANG_VERS}.min.js
git add ${TARG_DIR}/angular.min.js.map

for cm in cookies resource route sanitize animate ; do
    cp -a angular-${cm}.min.js* ${TARG_DIR}
done

cd ${TARG_DIR}

rm angular.min.js

ln -s angular-${ANG_VERS}.min.js angular.min.js

git add angular.min.js


