# main views

from django.contrib.auth.decorators import login_required
import logging
import logging_tools
""" main views """

from initat.core.render import render_me
from django.views.generic import View
from django.utils.decorators import method_decorator

logger = logging.getLogger("cluster.main")

class index(View):
    @method_decorator(login_required)
    def get(self, request):
        a = 1 / 0
        return render_me(request, "index.html")()
