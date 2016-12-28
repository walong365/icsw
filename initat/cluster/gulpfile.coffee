# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

""" gulpfile for icsw """

gulp = require("gulp")
del = require("del")
concat = require("gulp-concat")
uglify = require('gulp-uglify')
gulpif = require('gulp-if')
cache = require("gulp-memory-cache")
rev = require("gulp-rev")
coffee = require("gulp-coffee")
cssnano = require("gulp-cssnano")
cssimport = require("gulp-cssimport")
htmlmin = require("gulp-htmlmin")
gzip = require("gulp-gzip")
ng_annotate = require('gulp-ng-annotate')
inject = require("gulp-inject")
minimist = require('minimist')
connect = require("gulp-connect")
middleware = require("http-proxy-middleware")
angular_filesort = require("gulp-angular-filesort")
sourcemaps = require("gulp-sourcemaps")
mod_rewrite = require("connect-modrewrite")
changed = require("gulp-changed")
run = require("gulp-run")
bg = require("gulp-bg")
rename = require("gulp-rename")
clean_dest = require("gulp-clean-dest")
del = require("del")
wait = require("gulp-wait")
strip_debug = require("gulp-strip-debug")
fs = require("fs")
plumber = require("gulp-plumber")
preprocess = require("gulp-preprocess")


use_theme = "default"

themes = {
    default : [
        "frontend/static/css/theme-default/bootstrap-dialog.css",
        "frontend/static/css/theme-default/bootstrap.css",
        "frontend/static/css/icsw_src.css",
        "frontend/static/css/theme-default/theme-fixes.css"
    ]
    cora : [
        "frontend/static/css/theme-cora/bootstrap.css",
        "frontend/static/css/icsw_src.css",
        "frontend/static/css/theme-cora/theme-fixes.css"
    ]
    sirocco : [
        "frontend/static/css/theme-sirocco/bootstrap.css",
        "frontend/static/css/icsw_src.css",
        "frontend/static/css/theme-sirocco/theme-fixes.css"
    ]
}

svg_style_default = "frontend/static/css/theme-default/svg-style.css"
svg_style_cora = "frontend/static/css/theme-cora/svg-style.css"
svg_style_sirocco = "frontend/static/css/theme-sirocco/svg-style.css"

class SourceMap
    constructor: (@name, @dest, @sources, @type, @static) ->
        for f in @sources
            if "*" not in f
                # trigger error if file does not exist
                fs.lstatSync(f)

sources = {
    css_base: new SourceMap(
        "css_base"
        "icsw.css"
        [
            "frontend/static/css/ui.fancytree.css",
            # "frontend/static/css/luna.css",
            "frontend/static/css/cropper.css",
            "frontend/static/css/angular-datetimepicker.css",
            "frontend/static/css/angular-block-ui.css",
            "frontend/static/css/select.css",
            "frontend/static/css/ladda-themeless.min.css",
            "frontend/static/css/smart-table.css",
            "frontend/static/css/font-awesome.min.css",  #before theme
            "frontend/static/css/toaster.css",
            "frontend/static/css/angular-gridster.min.css",
            "frontend/static/css/angular-bootstrap-toggle.min.css",
            "frontend/static/css/hotkeys.css",
        ]
        "css"
        true
    )
    css_theme_default: new SourceMap(
        "css_theme_default"
        "theme_default.css"
        themes.default
        "css"
        true
    )
    css_theme_cora: new SourceMap(
        "css_theme_cora"
        "theme_cora.css"
        themes.cora
        "css"
        true
    )
    css_theme_sirocco: new SourceMap(
        "css_theme_sirocco"
        "theme_sirocco.css"
        themes.sirocco
        "css"
        true
    )
    "js_query_new": new SourceMap(
        "js_query_new"
        "parta.js"
        [
            # no longer needed ... ?
            # "frontend/static/js/modernizr-2.8.1.min.js",
            "frontend/static/js/jquery-3.1.1.min.js",
            # ace editor
            "frontend/static/js/ace-noconflict.js",
            "frontend/static/js/mode-python.js",
        ]
        "js"
        true
    )
    "js_base": new SourceMap(
        "js_base"
        "partb.js"
        [
            # angular
            "frontend/static/js/angular-1.6.1.js",
            "frontend/static/js/lodash.js",
            "frontend/static/js/bootstrap.js",
            "frontend/static/js/jquery.color.js",
            "frontend/static/js/jquery.blockUI.js",
            # datetime manipulation done right
            "frontend/static/js/moment-with-locales.min.js",
            # recurring moment handling, not needed right now
            # "frontend/static/js/moment-recur.js",
            "frontend/static/js/cropper.js",
            "frontend/static/js/spin.js",
            "frontend/static/js/ladda.js",
            "frontend/static/js/angular-ladda.js",
            "frontend/static/js/hamster.js",
            "frontend/static/js/toaster.js",
            "frontend/static/js/angular-gettext.min.js",
            "frontend/static/js/angular-translate.js",
            "frontend/static/js/webfrontend_translation.js",
            "frontend/static/js/angular-gridster.js",
            "frontend/static/js/angular-promise-extras.js",
            "frontend/static/js/react-15.4.1.js",
            "frontend/static/js/react-dom-15.4.1.js",
            # not needed ?
            # "frontend/static/js/react-draggable.js",
            "frontend/static/js/hotkeys.js",
            # ace editor
            "frontend/static/js/ui-ace.js",
        ]
        "js"
        true
    )
    "js_extra1": new SourceMap(
        "js_extra1"
        "partc.js"
        [
            # "frontend/static/js/jquery-ui-timepicker-addon.js",
            "frontend/static/js/angular-route.min.js",
            "frontend/static/js/angular-resource.min.js",
            "frontend/static/js/angular-cookies.min.js",
            "frontend/static/js/angular-sanitize.min.js",
            "frontend/static/js/angular-animate.min.js",
            "frontend/static/js/angular-file-upload.js",
            "frontend/static/js/restangular.min.js",
            "frontend/static/js/angular-block-ui.js",
            "frontend/static/js/select.js",
            "frontend/static/js/ui-bootstrap-tpls-2.3.2.min.js",
            "frontend/static/js/angular-ui-router.js",
            "frontend/static/js/datetime-picker.js",
            "frontend/static/js/datetime-picker.tpls.js",
            "frontend/static/js/angular-noVNC.js",
            "frontend/static/js/FileSaver.js",
            "frontend/static/js/mousewheel.js",
            "frontend/static/js/smart-table.js",
            "frontend/static/js/angular-simple-logger.js",
            "frontend/static/js/angular-google-maps.min.js",
            "frontend/static/js/bootstrap-dialog.js",
            "frontend/static/js/angular-bootstrap-toggle.min.js",
            # should be removed, use CSV export only via server-side calls
            "frontend/static/js/ng-csv.min.js",
            "frontend/static/js/sprintf.js",
        ]
        "js"
        true
    )
    "icsw-cs": new SourceMap(
        "icsw-cs"
        "partd.js"
        [
            "frontend/static/icsw/**/*.coffee"
        ]
        "coffee"
        false
    )
    "icsw-html": new SourceMap(
        "icsw-html"
        "icsw.html"
        [
            "frontend/static/icsw/**/*.html"
        ]
        "html"
        false
    )
}

known_options = {
    default: {
        "deploy-dir": "work/icsw"
        "compile-dir": "work/compile"
        # start django server
        "django": false
        # production (==minify) mode
        "production": false
        # include addons
        "addons": false
    }
    boolean: ["django", "production", "addons"]
}

options = minimist(process.argv.slice(2), known_options)
# start with gulp <target> --production to enable production mode

COMPILE_DIR = options["compile-dir"]
DEPLOY_DIR = options["deploy-dir"]

gulp.task("clean", (cb) ->
    del(
        [
            COMPILE_DIR
            DEPLOY_DIR
        ]
    )
    cb()
)

create_task = (key) ->
    gulp.task(key, () ->
        _map = sources[key]
        _sources = _map.sources
        _dest = _map.dest
        _is_coffee = _map.type == "coffee"
        _is_css = _map.type == "css"
        _is_js = _map.type == "js"
        _is_html = _map.type == "html"
        _is_prod = options.production
        _el = gulp.src(
            _sources
            {
                since: cache.lastMtime(key)
            }
        ).pipe(
            changed(COMPILE_DIR)
        ).pipe(
            gulpif(
                (_is_coffee or _is_js or _is_html),
                preprocess({context: {DEBUG: not _is_prod}})
            )
        ).pipe(
            gulpif(_is_coffee and ! options.production, sourcemaps.init())
        ).pipe(
            gulpif(
                _is_coffee, coffee().on(
                    "error",
                    (error) ->
                        console.log "an Coffee-error happed"
                        console.log error.stack
                        # not working
                        # wait(60000).pipe(
                        #     gulp.start("stop")
                        # )
                )
            )
        ).pipe(
            gulpif(
                # remove console.log calls when in production
                _is_prod and (_is_coffee or _is_js), strip_debug()
            )
        ).pipe(
            gulpif(
                _is_prod and (_is_coffee or _is_js), uglify(
                    mangle: true
                    compress: true
                )
            )
        ).pipe(
            gulpif(_is_prod and _is_css, cssnano({zindex: false}))
        ).pipe(
            gulpif(
                _is_prod and _is_html, htmlmin(
                    collapseWhitespace: true
                    removeComments: true
                    removeTagWhitespace: true
                )
            )
        ).pipe(
            cache(key)
        ).pipe(
            concat(_dest)
        ).pipe(
            gulpif(
                _is_coffee and ! options.production, sourcemaps.write()
            )
        ).pipe(
            gulp.dest(COMPILE_DIR)
        )
        return _el
    )
    return key

gulp.task("staticbuild", gulp.parallel((create_task(key) for key of sources when sources[key].static)))

gulp.task("dynamicbuild", gulp.parallel((create_task(key) for key of sources when not sources[key].static)))

# app.js modification, needs to be done only on startup (unless the URLs change)

gulp.task("inject-urls-and-menu-and-js-to-app", (cb) ->
    # add menus and addon related code to app.js
    return gulp.src(
       "frontend/templates/js/app.js",
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    ).pipe(
        run(
            "./manage.py inject_addons --srcfile=#{DEPLOY_DIR}/app.js --modify --with-addons=#{options.addons}",
            {verbosity: 0}
        )
    )
)

# deploy task (from compile to deploy dir), needs to be done only at startup
gulp.task("deploy-css", () ->
    _is_prod = options.production
    return gulp.src(
        ["#{COMPILE_DIR}/*.css",
         "!#{COMPILE_DIR}/theme_*.css"],
    # ).pipe(
    #     gzip()
    ).pipe(
        gulpif(_is_prod, rev())
    ).pipe(
        gulp.dest(DEPLOY_DIR + "/static/")
    ).pipe(
        rev.manifest(DEPLOY_DIR + '/rev-manifest.json', { merge: true, base: DEPLOY_DIR })
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    )
)

gulp.task("deploy-js", () ->
    _is_prod = options.production
    return gulp.src(
        ["#{COMPILE_DIR}/*.js"],
    # ).pipe(
    #     gzip()
    ).pipe(
        gulpif(_is_prod, rev())
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    ).pipe(
        rev.manifest(DEPLOY_DIR + '/rev-manifest.json', { merge: true, base: DEPLOY_DIR })
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    )
)

gulp.task("deploy-html", () ->
    _is_prod = options.production
    return gulp.src(
        ["#{COMPILE_DIR}/*.html"],
    # ).pipe(
    #     gzip()
    ).pipe(
        gulpif(_is_prod, rev())
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    ).pipe(
        rev.manifest(DEPLOY_DIR + '/rev-manifest.json', { merge: true, base: DEPLOY_DIR })
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    )
)

gulp.task("deploy-addons", () ->
    return gulp.src(
        [
            "addons/liebherr/initat/cluster/work/icsw/*.js",
            "addons/licadmin/initat/cluster/work/icsw/*.js",
        ]
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    )
)

# static deployment of fonts, d3, images and gifs

gulp.task("deploy-fonts", () ->
    return gulp.src(
        "frontend/static/fonts/*"
    ).pipe(
        gulp.dest(DEPLOY_DIR + "/fonts")
    )
)

gulp.task("deploy-d3", () ->
    return gulp.src(
        [
            "frontend/static/js/d3.min.js"
            "frontend/static/js/dimple.v2.1.6.min.js"
            "frontend/static/js/topojson.js"
        ]
    ).pipe(
        gulp.dest(DEPLOY_DIR + "/static/")
    )
)

gulp.task("deploy-images", () ->
    return gulp.src(
        [   
            "frontend/static/images/*.jpg"
            "frontend/static/images/symbols/*.svg"
            "frontend/static/images/product/*.png"
            "frontend/static/css/*.gif"
        ]
    ).pipe(
        gulp.dest(DEPLOY_DIR + "/static/")
    )
)

gulp.task("deploy-svgcss-default", () ->
    return gulp.src(svg_style_default)
        .pipe(rename("svgstyle_default.css"))
        .pipe(gulp.dest(DEPLOY_DIR + "/static/")
    )
)
gulp.task("deploy-svgcss-cora", () ->
    return gulp.src(svg_style_cora)
        .pipe(rename("svgstyle_cora.css"))
        .pipe(gulp.dest(DEPLOY_DIR + "/static/")
    )
)
gulp.task("deploy-svgcss-sirocco", () ->
    return gulp.src(svg_style_sirocco)
        .pipe(rename("svgstyle_sirocco.css"))
        .pipe(gulp.dest(DEPLOY_DIR + "/static/")
    )
)

gulp.task("deploy-themes", () ->
    gulp.src("#{COMPILE_DIR}/theme_*.css")
        .pipe(gulp.dest(DEPLOY_DIR + "/static/"))
)

gulp.task("deploy-media", gulp.parallel("deploy-fonts", "deploy-images", "deploy-d3",
    "deploy-svgcss-default", "deploy-svgcss-cora", "deploy-svgcss-sirocco"))

gulp.task("transform-main", (cb) ->
    return gulp.src(
        "frontend/templates/main.html"
    ).pipe(
        inject(
            gulp.src(
                [
                    "*.js",
                    "!ext_*.js",
                    "!app.js",
                    "static/*.css",
                    "!static/theme_*.css",
                    "!static/svgstyle_*css",
                    "*.html",
                    "!main.html",
                ]
                {
                    read: false
                    cwd: "#{DEPLOY_DIR}"
                }
            )
            {
                relative: true
                addRootSlash: false
            }
        )
    ).pipe(
        inject(
            gulp.src(
                "app.js",
                {
                    read: false
                    cwd: "#{DEPLOY_DIR}"
                }
            )
            {
                relative: true
                addRootSlash: false
                starttag: '<!-- inject:app:{{ext}} -->'
            }
        )
    ).pipe(
        inject(
            gulp.src(
                [
                    "#{DEPLOY_DIR}/*.html",
                    "!#{DEPLOY_DIR}/main.html",
                ]
            )
            {
                starttag: '<!-- inject:content:{{ext}} -->'
                transform: (path, file) ->
                    return file.contents.toString("utf8")
            }
        )
    ).pipe(
        clean_dest(COMPILE_DIR)
    ).pipe(
        gulp.dest(COMPILE_DIR)
    )
)

gulp.task("fix-main-import-path", (cb) ->
    # fix relative import path in main.html
    gulp.src(
        "#{COMPILE_DIR}/main.html",
        {read: false}
    ).pipe(
        run(
            "./manage.py inject_addons --srcfile=#{COMPILE_DIR}/main.html --cleanup-path --modify --with-addons=#{options.addons}",
            {verbosity: 0}
        )
    )
)

gulp.task("inject-addons-to-main", (cb) ->
    # add addon-javascript to main.html
    gulp.src(
        "#{COMPILE_DIR}/main.html",
        {read: false}
    ).pipe(
        run(
            "./manage.py inject_addons --srcfile=#{COMPILE_DIR}/main.html --modify --with-addons=#{options.addons}",
            {verbosity: 0}
        )
    )
)

gulp.task("import_css", () ->
    gulp.src("#{COMPILE_DIR}/main.html")
        .pipe(cssimport({}))
        .pipe(gulp.dest(COMPILE_DIR))
)

gulp.task("copy-main", (cb) ->
    # add addon-javascript to main.html
    gulp.src(
        "#{COMPILE_DIR}/main.html",
    ).pipe(
        gulp.dest(DEPLOY_DIR)
    )
)

# reload task
gulp.task("reload-main", (cb) ->
    gulp.src(
        "#{DEPLOY_DIR}/main.html"
    ).pipe(
        connect.reload()
    )
    cb()
)


if options.addons
    gulp.task("modify-app-js", gulp.series("inject-urls-and-menu-and-js-to-app"))
    gulp.task("deploy-all", gulp.series("deploy-css", "deploy-js", "deploy-html", "deploy-addons", "deploy-themes"))
    gulp.task("setup-main", gulp.series("modify-app-js", "transform-main", "fix-main-import-path", "import_css"))
    gulp.task("deploy-and-transform-all", gulp.series("deploy-all", "setup-main", "inject-addons-to-main", "copy-main"))
    gulp.task("rebuild-after-watch", gulp.series("deploy-all", "transform-main", "fix-main-import-path", "inject-addons-to-main", "copy-main", "reload-main"))
else
    gulp.task("modify-app-js", gulp.series("inject-urls-and-menu-and-js-to-app"))
    gulp.task("deploy-all", gulp.series("deploy-css", "deploy-js", "deploy-html", "deploy-themes"))
    gulp.task("setup-main", gulp.series("modify-app-js", "transform-main", "fix-main-import-path", "import_css"))
    gulp.task("deploy-and-transform-all", gulp.series("deploy-all", "setup-main", "copy-main"))
    gulp.task("rebuild-after-watch", gulp.series("deploy-all", "transform-main", "fix-main-import-path", "copy-main", "reload-main"))


# watcher tasks

gulp.task("watch", (cb) ->
    gulp.watch(
        [
            "frontend/static/icsw/**/*.coffee",
            "frontend/static/icsw/**/*.html",
            # addons
            "addons/liebherr/initat/cluster/work/icsw/*.js",
            "addons/liebherr/initat/cluster/work/icsw/*.html",
            "addons/licadmin/initat/cluster/work/icsw/*.js",
            "addons/licadmin/initat/cluster/work/icsw/*.html",
        ]
        gulp.series(gulp.parallel("icsw-cs", "icsw-html"), "rebuild-after-watch")
    )
    cb()
)

if options.django
    gulp.task("serve-django", (cb) ->
        bg("./runserver.sh")
        cb()
    )
else
    gulp.task("serve-django", (cb) ->
        cb()
    )

gulp.task("serve-graphics", (cb) ->
    connect.server(
        {
            root: "/tmp/.icsw/static/graphs"
            port: 8082
        }
    )
    cb()
)

gulp.task("serve-icinga", (cb) ->
    connect.server(
        {
            root: "/opt/cluster/icinga/share/images/logos"
            port: 8083
        }
    )
    cb()
)

gulp.task("serve-main", (cb) ->
    connect.server(
        {
            root: "work"
            port: 8080
            livereload: true
            fallback: "work/icsw/main.html"
            middleware: (connect, opt) ->
                return [
                    middleware(
                        "/icsw/ws/"
                        {
                            target: "ws://localhost:8084"
                            ws: true
                        }
                    )
                    middleware(
                        "/icsw/api/v2/static/icinga/",
                        {
                            pathRewrite: {"/icsw/api/v2/static/icinga/": "/"}
                            target: "http://localhost:8083"
                        }
                    )
                    middleware(
                        "/icsw/api/v2/static/graphs/",
                        {
                            pathRewrite: {"/icsw/api/v2/static/graphs/": "/"}
                            target: "http://localhost:8082"
                        }
                    )
                    middleware(
                        "/icsw/api/v2/",
                        {
                            target: "http://localhost:8081"
                        }
                    )
                ]
            debug: true
        }
    )
    cb()
)

gulp.task(
    "create-content",
    gulp.series(
        "clean",
        gulp.parallel(
            # static media
            "deploy-media",
            # static js
            "staticbuild",
        ),
        "dynamicbuild",
        "deploy-and-transform-all"
    )
)

gulp.task(
    "serve-all",
    gulp.series(
        "create-content",
        gulp.parallel("serve-graphics", "serve-icinga", "serve-django", "serve-main", "watch")
    ), (cb) ->
        cb()
)

gulp.task("default", gulp.series("serve-all"))
