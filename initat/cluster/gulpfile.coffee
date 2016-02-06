gulp = require("gulp")
del = require("del")
concat = require("gulp-concat")
uglify = require('gulp-uglify')
gulpif = require('gulp-if')
rev = require("gulp-rev")
coffee = require("gulp-coffee")
cssnano = require("gulp-cssnano")
htmlmin = require("gulp-htmlmin")
gzip = require("gulp-gzip")
ngAnnotate = require('gulp-ng-annotate')
inject = require("gulp-inject")
minimist = require('minimist')
connect = require("gulp-connect")
middleware = require("http-proxy-middleware")
angular_filesert = require("gulp-angular-filesort")
sourcemaps = require("gulp-sourcemaps")
mod_rewrite = require("connect-modrewrite")
changed = require("gulp-changed")
exec = require("gulp-exec")
bg = require("gulp-bg")

class SourceMap
    constructor: (@name, @dest, @sources, @type) ->

sources = {
    "css_base": new SourceMap(
        "css_base"
        "icsw.css"
        [
            "frontend/static/css/smoothness/jquery-ui-1.10.2.custom.min.css",
            "frontend/static/css/ui.fancytree.css",
            "frontend/static/css/codemirror.css",
            "frontend/static/css/bootstrap.css",
            "frontend/static/css/jquery.Jcrop.min.css",
            "frontend/static/css/angular-datetimepicker.css",
            "frontend/static/css/angular-block-ui.css",
            "frontend/static/css/select.css",
            "frontend/static/css/ladda.min.css",
            "frontend/static/css/tooltip.css",
            "frontend/static/css/smart-table.css",
            "frontend/static/css/font-awesome.min.css",
            "frontend/static/css/icsw.css",
            "frontend/static/css/toaster.css",
            "frontend/static/css/bootstrap-dialog.css",
            "frontend/static/css/angular-gridster.min.css",
            "frontend/static/css/main.css",
        ]
        "css"
    )
    "js_query_new": new SourceMap(
        "js_query_new"
        "parta.js"
        [
            "frontend/static/js/modernizr-2.8.1.min.js",
            "frontend/static/js/jquery-2.2.0.min.js",
        ]
        "js"
    )
    "js_base": new SourceMap(
        "js_base"
        "partb.js"
        [
            "frontend/static/js/jquery-ui-1.10.2.custom.js",
            # angular
            "frontend/static/js/angular-1.4.9.js",
            "frontend/static/js/lodash.js",
            "frontend/static/js/bluebird.js",
            "frontend/static/js/codemirror/codemirror.js",
            "frontend/static/js/bootstrap.js",
            "frontend/static/js/jquery.color.js",
            "frontend/static/js/jquery.blockUI.js",
            "frontend/static/js/moment-with-locales.js",
            "frontend/static/js/jquery.Jcrop.min.js",
            "frontend/static/js/spin.js",
            "frontend/static/js/ladda.js",
            "frontend/static/js/angular-ladda.js",
            "frontend/static/js/hamster.js",
            "frontend/static/js/toaster.js",
            "frontend/static/js/angular-gettext.min.js",
            "frontend/static/js/webfrontend_translation.js",
            "frontend/static/js/angular-gridster.min.js",
            "frontend/static/js/angular-promise-extras.js",
            "frontend/static/js/react-0.14.7.js",
            "frontend/static/js/react-dom-0.14.7.js",
        ]
        "js"
    )
    "js_extra1": new SourceMap(
        "js_extra1"
        "partc.js"
        [
            "frontend/static/js/codemirror/addon/selection/active-line.js",
            "frontend/static/js/codemirror/mode/python/python.js",
            "frontend/static/js/codemirror/mode/xml/xml.js",
            "frontend/static/js/codemirror/mode/shell/shell.js",
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
            "frontend/static/js/ui-bootstrap-tpls.min.js",
            "frontend/static/js/angular-ui-router.js",
            # must use minified version, otherwise the minifier destroys injection info
            "frontend/static/js/ui-codemirror.js",
            "frontend/static/js/angular-datetimepicker.js",
            # "frontend/static/js/angular-strap.min.js",
            # "frontend/static/js/angular-strap.tpl.min.js",
            "frontend/static/js/angular-noVNC.js",
            "frontend/static/js/FileSaver.js",
            "frontend/static/js/mousewheel.js",
            "frontend/static/js/smart-table.js",
            "frontend/static/js/angular-simple-logger.js",
            "frontend/static/js/angular-google-maps.min.js",
            "frontend/static/js/bootstrap-dialog.js",
        ]
        "js"
    )
    "icsw_cs": new SourceMap(
        "icsw_cs"
        "partd.js"
        [
            "frontend/static/icsw/**/*.coffee"
        ]
        "coffee"
    )
    "icsw_html": new SourceMap(
        "icsw_html"
        "icsw.html"
        [
            "frontend/static/icsw/**/*.html"
        ]
        "html"
    )
}

known_options = {
    default: {
        "deploy-dir": "work/icsw"
        "compile-dir": "work/compile"
    }
}

options = minimist(process.argv.slice(2), known_options)

if not options.production
    options.production = false

COMPILE_DIR = options["compile-dir"]
DEPLOY_DIR = options["deploy-dir"]

gulp.task("clean", () ->
    return del(
        [
            DEPLOY_DIR,
            COMPILE_DIR
        ]
    )
)

create_task = (key) ->
    gulp.task(key, ["clean"], () ->
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
        ).pipe(
            changed(
                COMPILE_DIR
            )
        ).pipe(
            gulpif(
                _is_coffee and ! options.production, sourcemaps.init()
            )
        ).pipe(
            gulpif(
                _is_coffee, coffee().on(
                    "error",
                    (error) ->
                        console.log "an Coffee-error happed"
                        console.log error.stack
                        gulp.start("stop")
                )
            )
        ).pipe(
            concat(
                _dest
            )
        ).pipe(
            gulpif(
                _is_prod and (_is_coffee or _is_js), uglify(
                    mangle: true
                    compress: true
                )
            )
        ).pipe(
            gulpif(
                _is_prod and _is_css, cssnano()
            )
        ).pipe(
            gulpif(
                _is_prod and _is_html, htmlmin(
                    collapseWhitespace: true
                    removeComments: true
                    removeTagWhitespace: true
                )
            )
        ).pipe(
            gulpif(
                _is_coffee and ! options.production, sourcemaps.write()
            )
        ).pipe(
            gulp.dest(
                COMPILE_DIR
            )
        )
        return _el
    )
    return key

_build_names = (
    create_task(key) for key of sources
)

gulp.task("basebuild", _build_names)

gulp.task("app", ["basebuild", "allurls"], () ->
    # add urls to app_gulp.js
    return gulp.src(
       "frontend/templates/js/app.js",
    ).pipe(
        inject(
            gulp.src(
                "frontend/templates/all_urls.html",
            )
            {
                starttag: '<!-- inject:urls:{{ext}} -->'
                transform: (path, file) ->
                    return file.contents.toString("utf8")
            }
        )
    ).pipe(
        gulp.dest(
            "#{DEPLOY_DIR}"
        )
    )

)

gulp.task("allurls", () ->
    return gulp.src("all_urls.html", {read: false}).pipe(
        exec(
            [
                "./manage.py show_icsw_urls",
            ]
            {
                pipeStdout: true
            }
        )
    ).pipe(
        gulp.dest(
            "frontend/templates"
        )
    )
)

gulp.task("css",  ["basebuild"], () ->
    return gulp.src(
        ["#{COMPILE_DIR}/*.css"],
    # ).pipe(
    #      gzip()
    ).pipe(
        rev()
    ).pipe(
        gulp.dest(
            DEPLOY_DIR + "/static/"
        )
    ).pipe(
        rev.manifest(
            merge: true
        )
    ).pipe(
        gulp.dest(
            DEPLOY_DIR
        )
    )
)

gulp.task("js", ["app", "css"], () ->
    return gulp.src(
        ["#{COMPILE_DIR}/*.js", "#{COMPILE_DIR}/*.html"],
    # ).pipe(
    #      gzip()
    ).pipe(
        rev()
    ).pipe(
        gulp.dest(
            DEPLOY_DIR
        )
    ).pipe(
        rev.manifest(
            merge: true
        )
    ).pipe(
        gulp.dest(
            DEPLOY_DIR
        )
    )
)

gulp.task("media", ["fonts", "images", "gifs"])

gulp.task("fonts", ["clean"], () ->
    return gulp.src(
        "frontend/static/fonts/*"
    ).pipe(
        gulp.dest(
            DEPLOY_DIR + "/fonts"
        )
    )
)

gulp.task("images", ["clean"], () ->
    return gulp.src(
        "frontend/static/images/product/*.png"
    ).pipe(
        gulp.dest(
            DEPLOY_DIR + "/static/"
        )
    )
)

gulp.task("gifs", ["clean"], () ->
    return gulp.src(
        "frontend/static/css/*.gif"
    ).pipe(
        gulp.dest(
            DEPLOY_DIR + "/static/"
        )
    )
)

gulp.task("index", ["js", "app", "media"], () ->
    target = gulp.src("frontend/templates/main.html")
    return target.pipe(
        inject(
            gulp.src(
                [
                    "*.js",
                    "!app.js",
                    "static/*.css",
                    "*.html",
                ]
                {
                    read: false
                    cwd: "#{DEPLOY_DIR}"
                }
            )
            {
                addRootSlash: false
                # relative: true
                # addSuffix: "icsw"
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
                addRootSlash: false
                starttag: '<!-- inject:app:{{ext}} -->'
            }
        )
    ).pipe(
        inject(
            gulp.src(
                "#{DEPLOY_DIR}/*.html",
            )
            {
                starttag: '<!-- inject:content:{{ext}} -->'
                transform: (path, file) ->
                    return file.contents.toString("utf8")
            }
        )
    ).pipe(
        gulp.dest(
            DEPLOY_DIR
        )
    )

)

gulp.task("watch", ["index"], () ->
    gulp.watch(
        [
            "frontend/static/icsw/*/*.coffee",
            "frontend/static/icsw/*/*.html",
        ]
        ["index"]
    )
)

bgtask = bg("./runserver.sh")
gulp.task("django", bgtask)

gulp.task("stop", () ->
    bgtask.stop()
)

gulp.task("serve", ["watch", "django"], () ->
    connect.server(
        {
            root: "work"
            port: 8080
            fallback: "work/icsw/main.html"
            middleware: (connect, opt) ->
                return [
                    middleware(
                        "/icsw/api/v2/",
                        {
                            target: "http://localhost:8081"
                        }
                    )
                ]
        }
    )
)
