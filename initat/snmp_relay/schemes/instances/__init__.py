# Copyright (C) 2009-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
""" SNMP schemes for SNMP relayer """

import os
import inspect
from initat.tools import process_tools
from ..base import SNMPRelayScheme

_path = os.path.dirname(__file__)

snmp_schemes = []
import_errors = []

for mod_name in [
    _entry.split(".")[0] for _entry in os.listdir(_path) if _entry.endswith(".py") and _entry not in ["__init__.py"]
]:
    try:
        new_mod = __import__(mod_name, globals(), locals())
    except:
        exc_info = process_tools.exception_info()
        import_errors.extend(
            [
                (mod_name, "import", _line) for _line in exc_info.log_lines
            ]
        )
    else:
        for _key in dir(new_mod):
            _obj = getattr(new_mod, _key)
            if inspect.isclass(_obj) and issubclass(_obj, SNMPRelayScheme) and _obj != SNMPRelayScheme:
                if _key.endswith("_scheme"):
                    snmp_schemes.append((_key[:-7], _obj))
                else:
                    import_errors.append(
                        (
                            mod_name,
                            "parser", "'{}' is an SNMPRelayScheme instance but has wrong name".format(
                                _key
                            )
                        )
                    )
