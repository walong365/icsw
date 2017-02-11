"""

ASGI config for ICSW

"""

import os

from channels.asgi import get_channel_layer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

channel_layer = get_channel_layer()
