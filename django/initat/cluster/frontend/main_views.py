# main views

from django.contrib.auth.decorators import login_required

""" main views """

from initat.core.render import render_me

@login_required
def index(request):
    return render_me(request, "index.html")()
