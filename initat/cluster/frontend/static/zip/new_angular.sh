#!/bin/bash
set -x
ANG_VERS=$(ls -1 angular-1.*zip | tail -n 1 | cut -d "-" -f 2 | sed s/.zip//g)

echo "New angular version is ${ANG_VERS}"

unzip angular-${ANG_VERS}.zip

cd angular-${ANG_VERS}

TARG_DIR=../../js/

cp -a angular.js ${TARG_DIR}/angular-${ANG_VERS}.js
cp -a angular.min.js ${TARG_DIR}/angular-${ANG_VERS}.min.js
cp -a angular.min.js.map ${TARG_DIR}/

git add ${TARG_DIR}/angular-${ANG_VERS}.js
git add ${TARG_DIR}/angular-${ANG_VERS}.min.js
git add ${TARG_DIR}/angular.min.js.map

for cm in cookies resource route sanitize animate ; do
    cp -a angular-${cm}.min.js* ${TARG_DIR}
done

cd ${TARG_DIR}

rm angular.js angular.min.js

ln -s angular-${ANG_VERS}.js angular.js
ln -s angular-${ANG_VERS}.min.js angular.min.js

git add angular.js angular.min.js


