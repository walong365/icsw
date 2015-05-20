
module.exports = function (grunt) {

    // use grunt for html and other shellscript for coffeescript
    grunt.initConfig({
      nggettext_extract: {
        pot: {
          files: {
            'po/template_html.pot': ['../initat/cluster/frontend/static/icsw/*/*.html']
          }
        },
      },
      nggettext_compile: {
        all: {
          files: {
              '../initat/cluster/frontend/static/js/webfrontend_translation.js': ['po/*.po']
          }
        },
      },
    })
    
    grunt.loadNpmTasks('grunt-angular-gettext');
}
