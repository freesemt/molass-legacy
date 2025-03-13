"""

    Version.py

    Copyright (c) 2016-2024, SAXS Team, KEK-PF

"""
import platform

def get_version_string(cpuid=False):
    if cpuid:
        from molass_legacy.KekLib.MachineTypes import get_cpuid
        cpuid = ' cpuid:' + str(get_cpuid())
    else:
        cpuid = ''

    return '_MOLASS 3.3.9 (2025-03-11 07:23:11 python %s %s%s)' % (
                platform.python_version(), platform.architecture()[0], cpuid )

def molass_version_for_publication():
    import re
    version = get_version_string()
    return re.sub(r"\s+\(.+", "", version)

def is_developing_version():
    return get_version_string().find(":") > 0
