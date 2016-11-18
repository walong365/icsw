"""

ASGI config for cluster project.

"""

from __future__ import unicode_literals, print_function

import os

from channels.asgi import get_channel_layer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

channel_layer = get_channel_layer()
