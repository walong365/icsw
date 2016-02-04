#!/bin/bash

# as root: npm install --global gulp-cli

/opt/cluster/bin/npm install --save-dev gulp gulp-rev gulp-concat gulp-uglify \
    gulp-if gulp-ng-annotate coffee-script del gulp-coffee gulp-sourcemaps \
    gulp-cssnano gulp-htmlmin gulp-gzip gulp-inject gulp-angular-filesort \
    gulp-webserver connect-modrewrite http-proxy-middleware gulp-exec
