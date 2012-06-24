# main views

from init.cluster.frontend import render_tools

def index(request):
    return render_tools.render_me(request, "index.html")()
