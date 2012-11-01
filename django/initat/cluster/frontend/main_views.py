# main views

from initat.core.render import render_me

def index(request):
    return render_me(request, "index.html")()
