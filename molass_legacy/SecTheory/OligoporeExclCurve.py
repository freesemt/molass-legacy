"""
    SecTheory.OligoporeExclCurve.py

    Copyright (c) 2023-2024, SAXS Team, KEK-PF
"""
import os
import sys
import numpy as np
from matplotlib.gridspec import GridSpec
from scipy.interpolate import UnivariateSpline
from scipy.optimize import minimize, basinhopping

def compute_confpoints_impl(x, rgv, proportions, poresizes, N, T, x0, me, mp):
    import molass_legacy.KekLib.DebugPlot as plt
    from SecTheory.SecCF import gec_polypore_phi
    from SecTheory.SecPDF import FftInvPdf

    polypore_pdf = FftInvPdf(gec_polypore_phi)

    proportions_ = proportions/np.sum(proportions)

    nt_pairs = []
    for rp, p in zip(poresizes, proportions_):
        rho = rgv/rp
        rho[rho > 1] = 1
        n_ = p*N*(1 - rho)**me
        t_ = T*(1 - rho)**mp
        nt_pairs.append((n_, t_))

    nt_pairs = np.array(nt_pairs)

    confpoints = []
    for k in range(len(rgv)):
        y = polypore_pdf(x, nt_pairs[:,:,k], x0)
        j = np.argmax(y)
        confpoints.append((x[j], rgv[k]))
        if False:
            with plt.Dp():
                fig, ax = plt.subplots()
                ax.set_title("[%d] polypore_pdf debug" % k)
                ax.plot(x, y)
                ax.plot(x[j], y[j], "o", color="red")
                fig.tight_layout()
                plt.show()

    confpoints = np.array(confpoints)
    return confpoints

def create_spline(confpoints, devel=True):
    if devel:
        from importlib import reload
        import SecTheory.ExclCurveUtils
        reload(SecTheory.ExclCurveUtils)
    from SecTheory.ExclCurveUtils import safely_create_spline_from_points
    return safely_create_spline_from_points(confpoints)

def compute_excurve_impl(x, *args):
    confpoints = compute_confpoints_impl(x, *args)
    spline = create_spline(confpoints)
    return spline(x)

def estimate_polypore_exclcurve(fig, ax, axpsd, optimizer, lrf_info, new_params, num_pores=5, niter=5):
    import molass_legacy.KekLib.DebugPlot as plt
    from molass_legacy.SerialAnalyzer.DataUtils import get_in_folder
    from Experiment.ColumnTypes import get_columnname

    x = optimizer.xr_curve.x
    xr_params = optimizer.separate_params[0]
    # sec_rg_params = optimizer.separate_params[2]
    seccol_params = optimizer.separate_params[7]
    lrf_rg_params = lrf_info.rg_params
    opt_weights = lrf_info.rg_qualities
    print("estimate_exclusion_curve")
    print("\tseccol_params=", seccol_params)
    print("\tlrf_rg_params=", lrf_rg_params)
    print("\topt_weights=", opt_weights)

    Npc, rp, tI, t0, P, m = seccol_params

    trs = xr_params[:,1]

    def objective(p, return_confpoints=False):
        confpoints = compute_confpoints_impl(x, lrf_rg_params, p[0:num_pores], p[num_pores:num_pores*2], *p[num_pores*2:])
        if return_confpoints:
            return confpoints
        return np.sum(opt_weights*(confpoints[:,0] - trs)**2)

    N = P
    T = 1
    x0 = x[0]
    me = 1.5
    mp = 0.1

    rpv = np.linspace(rp*2, rp/2, num_pores)
    init_params = np.concatenate([np.ones(num_pores)/num_pores, rpv, [N, T, x0, me, mp]])
    print("init_params=", init_params)

    last_fun = objective(init_params)

    best_fun = None
    best_params = None

    bounds = [(0, 1)]*num_pores + [(0, 300)]*num_pores + [(0, 2000), (0, 100), (-500, trs[0]), (0, 3), (0, 3)]
    minimizer_kwargs=dict(method='Nelder-Mead', bounds=bounds)

    for k in range(niter):
        print([k], "optmizing ...")
        ret = basinhopping(objective, init_params, minimizer_kwargs=minimizer_kwargs)
        print("ret.success=", ret.success)
        print("ret.x=", ret.x)
        if best_fun is None or ret.fun < best_fun:
            best_fun = ret.fun
            best_params = ret.x
            if best_fun < last_fun:
                init_params = best_params
                last_fun = best_fun

    np.savetxt("best_params.txt", best_params)

    # init_confpoints = objective(init_params, return_confpoints=True)
    opt_confpoints = objective(best_params, return_confpoints=True)

    y = optimizer.xr_curve.y

    in_folder = get_in_folder()
    ax.set_title("Oligopore Exclusion Curve on %s with %s" % (in_folder, get_columnname()), fontsize=20)
    ax.set_ylabel("Intensity")

    axt = ax.twinx()
    axt.grid(False)
    axt.set_ylabel("$R_g$")

    axis_info = [fig, (None, ax, None, axt)]    # fig, (ax1, ax2, ax3, axt)
    optimizer.objective_func(new_params, plot=True, axis_info=axis_info)

    opt_proportions = best_params[0:num_pores]
    opt_poresizes = best_params[num_pores:num_pores*2]
    opt_extraparams = best_params[num_pores*2:]
    opt_x0 = opt_extraparams[2]

    maxrg = np.max(lrf_rg_params)*1.1
    minrg = 15

    rgv = np.arange(maxrg, minrg, -1)
    confpoints = compute_confpoints_impl(x, rgv, opt_proportions, opt_poresizes, *opt_extraparams)

    if False:
        cwd = os.getcwd()
        print("cwd=", cwd)

        np.savetxt("confpoints.txt", confpoints)

        with plt.Dp():
            fig_, ax_ = plt.subplots()
            ax_.set_title("confpoints debug")
            ax_.plot(*confpoints.T, "o")
            fig_.tight_layout()
            plt.show()

    spline = create_spline(confpoints)
    x_ = x[x > opt_x0]
    r_ = spline(x_)
    r__ = r_[r_ > minrg]
    x__ = x_[r_ > minrg]

    axt.plot(x__, r__, color="cyan", markersize=1, lw=3, label="polypore exclusion curve")

    # axt.plot(*init_confpoints.T, "o", color="blue")
    axt.plot(*opt_confpoints.T, "o", color="red", label="elution points")
    axt.set_ylim(0, maxrg)
    axt.legend(bbox_to_anchor=(0.7, 1), loc="upper center")

    opt_proportions = opt_proportions/np.sum(opt_proportions)

    print("opt_poresizes=", opt_poresizes)
    print("opt_proportions=", opt_proportions)

    axpsd.set_title("Poresize Distribution", fontsize=20)
    axpsd.bar(opt_poresizes, opt_proportions, width=10)
    axpsd.set_xlim(0, 300)

def demo():
    import molass_legacy.KekLib.DebugPlot as plt

    x = np.arange(200)
    rp = 120

    rgv = np.flip(np.linspace(0, rp-1, 50))

    x0 = 50
    N = 171
    T = 0.63
    me = 1.5
    mp = 0.1

    proportions3 = np.ones(3)/3
    poresizes3_1 = np.array([rp, rp, rp])
    poresizes3_2 = np.array([rp*2, rp, rp/2])

    y3 = compute_excurve_impl(x, rgv, proportions3, poresizes3_1, N, T, x0, me, mp)
    y4 = compute_excurve_impl(x, rgv, proportions3, poresizes3_2, N, T, x0, me, mp)

    valid = np.logical_and(x > x0, y3 > 0)
    x_ = x[valid]
    y3_ = y3[valid]
    y4_ = y4[valid]

    with plt.Dp():
        fig, ax = plt.subplots()

        ax.plot(x_, y3_, label=str(poresizes3_1))
        ax.plot(x_, y4_, label=str(poresizes3_2))

        ax.legend()
        fig.tight_layout()
        plt.show()

if __name__ == '__main__':
    this_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.dirname(this_dir)
    sys.path.append(lib_dir)

    import seaborn
    seaborn.set()
    import molass_legacy.KekLib

    demo()
