"""
    SeccolFunctions.py

    Copyright (c) 2022, SAXS Team, KEK-PF
"""
from SecTheory.ColumnConstants import SECCONF_LOWER_BOUND

def rgfit_secconf_eval(rgfit, secconf):
    if secconf > SECCONF_LOWER_BOUND:
        return max(rgfit, secconf)
    else:
        return rgfit + SECCONF_LOWER_BOUND
