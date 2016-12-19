#!/bin/bash

# as root: npm install --global gulp-cli

# move to gulp 4:
#
# as root:
#
# npm uninstall -g gulp
# /opt/cluster/bin/npm install -g "gulpjs/gulp-cli#4.0"
# /opt/cluster/bin/npm install -g typescript

# as user:
# /opt/cluster/bin/npm uninstall gulp --save-dev
# /opt/cluster/bin/npm install gulpjs/gulp#4.0 --save-dev

/opt/cluster/bin/npm install --save-dev "gulpjs/gulp#4.0" gulp-rev gulp-concat gulp-uglify \
    gulp-if gulp-ng-annotate coffee-script del gulp-coffee gulp-sourcemaps \
    gulp-cssnano gulp-htmlmin gulp-gzip gulp-inject gulp-angular-filesort \
    gulp-webserver connect-modrewrite http-proxy-middleware gulp-run \
    gulp-changed gulp-remember gulp-cache gulp-bg gulp-rename gulp-clean-dest del \
    gulp-wait gulp-strip-debug gulp-cached gulp-remember gulp-memory-cache \
    gulp-plumber gulp-connect gulp-preprocess gulp-cjsx gulp-typescript typescript \
    gulp-cssimport
