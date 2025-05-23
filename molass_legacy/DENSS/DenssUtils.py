"""
    DenssUtils.py

    Copyright (c) 2019-2024, SAXS Team, KEK-PF

    Note that the original DENSS by T. Grant is licensed under GPL3.

    DENSS is available open source under the GPL 3.0 license.
    This means that anyone is free to download, utilize and develop the code,
    provided that any derivative code developed based on DENSS
    or its underlying algorithm is also distributed under the GPL 3.0 license
    and retains the original copyright.

"""
import numpy as np
import sys, argparse, os
import logging
from .saxstats import saxstats as saxs
from .saxstats import denssopts as dopts
from BasicUtils import Struct

MAXNUM_STEPS = 20000

def fit_data_impl(q, a, e, file, D=None, alpha=None, max_alpha=None, nes=2, extrapolate=True, gui=False):
    Iq = np.vstack( [q, a, e] ).T

    # task: update this construction automatically from bin\denss.fit_data.py
    args = Struct(
        alpha = alpha,
        units = "a",
        max_alpha = max_alpha,
        output = None,
        file = file,    # 
        dmax = D,
        nes = nes,
        n1 = None,
        n2 = None,
        q = None,
        qmax = None,
        nq = None,
        max_dmax = None,
        qfile = None,
        rfile = None,
        extrapolate = extrapolate,
        nr = None,
        plot = True,
        log = True,
        )

    """
    DENSS strongly recommends to include I(q=0).
    To conform, we are using denss.fit_data.py here processing logic
    to modify the input data

    below is the extracted default processing from denss.fit_data.py
    lines[80:175] as of ver. 1.6.6
    """
### DENSS.bin.denss.fit_data.py copy & modify BEIGN ###
    alpha = args.alpha

    if args.output is None:
        fname_nopath = os.path.basename(args.file)
        basename, ext = os.path.splitext(fname_nopath)
        output = basename
    else:
        output = args.output


    # Iq = np.genfromtxt(args.file, invalid_raise = False, usecols=(0,1,2))
    Iq = Iq[~np.isnan(Iq).any(axis = 1)]
    if len(Iq.shape) < 2:
        print("Invalid data format. Data file must have 3 columns: q, I, errors.")
        exit()
    if Iq.shape[1] < 3:
        print("Not enough columns (data must have 3 columns: q, I, errors).")
        #attempt to make a simulated errors column
        Iq2 = np.zeros((Iq.shape[0],3))
        Iq2[:,:2] = Iq
        err = Iq[:,1]*.003 #percentage of intensity for each point
        err += np.mean(Iq[:10,1])*.01 #minimum error for all points
        Iq2[:,2] = err
        Iq = Iq2
    #get rid of any data points equal to zero in the intensities or errors columns
    idx = np.where((Iq[:,1]!=0)&(Iq[:,2]!=0))
    Iq = Iq[idx]
    nes = args.nes

    if args.units == "nm":
        Iq[:,0] *= 0.1

    if args.n1 is None:
        n1 = 0
    else:
        n1 = args.n1
    if args.n2 is None:
        n2 = len(Iq[:,0])
    else:
        n2 = args.n2

    Iq_orig = np.copy(Iq)

    if args.dmax is None:
        #estimate dmax directly from data
        #note that saxs.estimate_dmax does NOT extrapolate
        #the high q data, even though by default
        #saxs.Sasrec does extrapolate.
        D, sasrec = saxs.estimate_dmax(Iq, clean_up=True)
    else:
        D = args.dmax

    if args.max_dmax is None:
        args.max_dmax = 2.*D

    if args.rfile is not None:
        r = np.loadtxt(args.rfile,usecols=(0,))
    else:
        r = None

    if args.qfile is not None:
        qc = np.loadtxt(args.qfile,usecols=(0,))
    else:
        qc = None

    print("Dmax = %.2f"%D)
    qmax = Iq[n1:n2,0].max()
    if (qc is None) and (args.extrapolate):
        qmaxc = qmax*3.0
    elif (qc is None):
        qmaxc = qmax
    else:
        qmaxc = qc.max()

    #let a user set a desired set of q values to be calculated
    #based on a given qmax and nq
    if (args.qmax is not None) or (args.nq is not None):
        if args.qmax is not None:
            qmaxc = args.qmax
        else:
            qmaxc = qmaxc
        if args.nq is not None:
            nqc = args.nq
        else:
            nqc = 501
        qc = np.linspace(0,qmaxc,nqc)
        #assume if they are giving args.qmax or args.nq, that they want to
        #disable extrapolation
        args.extrapolate = False

    nsh = qmax/(np.pi/D)
    nshc = qmaxc/(np.pi/D)
    print("Number of experimental Shannon channels: %d"%(nsh))
    print("Number of calculated Shannon channels: %d"%(nshc))
    if (nsh > 500) or (nshc>500):
        print("WARNING: Nsh > 500. Calculation may take a while. Please double check Dmax is accurate.")
        #give the user a few seconds to cancel with CTRL-C
        waittime = 10
        import time
        try:
            for i in range(waittime+1):
                sys.stdout.write("\rTo cancel, press CTRL-C in the next %d seconds. "%(waittime-i))
                sys.stdout.flush()
                time.sleep(1)
            print()
        except KeyboardInterrupt:
            print("Canceling...")
            exit()

    #calculate chi2 when alpha=0, to get the best possible chi2 for reference
    print("args.extrapolate=", args.extrapolate)
    sasrec = saxs.Sasrec(Iq[n1:n2], D, qc=qc, r=r, nr=args.nr, alpha=0.0, extrapolate=args.extrapolate)
    ideal_chi2 = sasrec.calc_chi2()

    if args.alpha is None:
        alpha = sasrec.optimize_alpha(gui=gui)
    else:
        alpha = args.alpha
    sasrec = saxs.Sasrec(Iq[n1:n2], D, qc=qc, r=r, nr=args.nr, alpha=alpha, ne=nes, extrapolate=args.extrapolate)

    #implement method of estimating Vp, Vc, etc using oversmoothing
    sasrec.estimate_Vp_etal()

### DENSS.bin.denss.fit_data.py copy  & modify  END ###

    work_info = Struct(Iq=Iq, args=args, alpha=alpha, n1=n1, n2=n2, Iq_orig=Iq_orig)
    return sasrec, work_info

def fit_data(q, a, e, D=None, extrapolate=False, return_sasrec=False):
    sasrec, work_info = fit_data_impl(q, a, e, "dummy.dat",     # "dummy.dat" is for "fname_nopath = os.path.basename(args.file)" above
                                        D=D,
                                        alpha=0,        # backward compatibility
                                        max_alpha=None,
                                        extrapolate=extrapolate)
    if return_sasrec:
        return sasrec 
    else:
        return sasrec.qc, sasrec.Ic, sasrec.Icerr, sasrec.D

def fit_data_bc(q, a, e, extrapolate=False):    # backward compatible
    sasrec, work_info = fit_data_impl(q, a, e, "dummy.dat",     # "dummy.dat" is for "fname_nopath = os.path.basename(args.file)" above
                                        D=100,
                                        alpha=0,
                                        max_alpha=10,
                                        extrapolate=extrapolate)
    return sasrec.qc, sasrec.Ic, sasrec.Icerr, sasrec.D

def get_dmax_with_datgnom(file_path):
    from Saxs.Rdf import AtsasDatGnomDdf
    ddf = AtsasDatGnomDdf(file_path)
    dmax = ddf.guess_best_dmax()
    return dmax

def run_denss_impl(qc, ac, ec, dmax, infile_name, steps=MAXNUM_STEPS, progress_cb=None, use_gpu=False, gui=False):

    q = qc
    I = ac
    sigq = ec
    isout = False   # we are using .dat type file

    sys.argv = ['dummy-script', '-f', infile_name]
    if use_gpu:
        sys.argv += ['-gpu']
    parser = argparse.ArgumentParser(description="DENSS: DENsity from Solution Scattering.\n A tool for calculating an electron density map from solution scattering data", formatter_class=argparse.RawTextHelpFormatter)
    # data_proxy should contain: q, I, sigq, file_dmax, isout
    # data_proxy should contain: q, I, sigq, Ifit, file_dmax, isfit
    data_proxy = [q, I, sigq, I, dmax, True]
    args = dopts.parse_arguments(parser, data_proxy=data_proxy)

    """
    caused an error with DENSS_GPU=True in KEK2 devel env (i.e., while not using embeddables)
    File "C:\Program Files\Python311\Lib\site-packages\cupy\cuda\compiler.py", line 233, in _jitify_prep
    ...
    RuntimeError: Runtime compilation failed
    
    task: add a coverup measure 
    """
    qdata, Idata, sigqdata, qbinsc, Imean, chis, rg, supportV, rho, side, fit, final_chi2 = saxs.denss(
        q=args.q,
        I=args.I,
        sigq=args.sigq,
        dmax=args.dmax,
        ne=args.ne,
        voxel=args.voxel,
        oversampling=args.oversampling,
        recenter=args.recenter,
        recenter_steps=args.recenter_steps,
        recenter_mode=args.recenter_mode,
        positivity=args.positivity,
        extrapolate=args.extrapolate,
        output=args.output,
        steps=args.steps,
        ncs=args.ncs,
        ncs_steps=args.ncs_steps,
        ncs_axis=args.ncs_axis,
        seed=args.seed,
        shrinkwrap=args.shrinkwrap,
        shrinkwrap_old_method=args.shrinkwrap_old_method,
        shrinkwrap_sigma_start=args.shrinkwrap_sigma_start,
        shrinkwrap_sigma_end=args.shrinkwrap_sigma_end,
        shrinkwrap_sigma_decay=args.shrinkwrap_sigma_decay,
        shrinkwrap_threshold_fraction=args.shrinkwrap_threshold_fraction,
        shrinkwrap_iter=args.shrinkwrap_iter,
        shrinkwrap_minstep=args.shrinkwrap_minstep,
        chi_end_fraction=args.chi_end_fraction,
        write_xplor_format=args.write_xplor_format,
        write_freq=args.write_freq,
        enforce_connectivity=args.enforce_connectivity,
        enforce_connectivity_steps=args.enforce_connectivity_steps,
        cutout=args.cutout,
        quiet=args.quiet,
        gui=gui,
        DENSS_GPU=args.DENSS_GPU,
        progress_cb=progress_cb)

def run_denss_impl_dummy(qc, ac, ec, dmax, infile_name):
    import time
    print("\n Step     Chi2     Rg    Support Volume")
    print(" ----- --------- ------- --------------")

    for j in range(100):
        time.sleep(0.1)
        sys.stdout.write("\r% 5i " % (j))
        sys.stdout.flush()

def get_denssfolder(parent=None):
    from molass_legacy._MOLASS.SerialSettings import get_setting
    from BasicUtils import mkdirs_with_retry

    analysis_folder = get_setting('analysis_folder')
    if analysis_folder is None or analysis_folder == "":
        return None

    denss_folder = (analysis_folder + '/DENSS').replace('\\', '/')
    if not os.path.exists(denss_folder):
        mkdirs_with_retry(denss_folder)

    return denss_folder

def get_outfolder(job_id=None, parent=None):
    denss_folder = get_denssfolder(parent=parent)
    if denss_folder is None:
        return None

    import re
    if job_id is None:
        out_folder = denss_folder + '/000'
        while True:
            if os.path.exists(out_folder):
                out_folder = re.sub(r'/(\d+)$', lambda m: '/%03d' % (int(m.group(1)) + 1), out_folder)
            else:
                break
    else:
        out_folder_init = denss_folder + '/%03d' % job_id
        out_folder = out_folder_init
        i = 0
        while True:
            if os.path.exists(out_folder):
                i += 1
                out_folder =  out_folder_init + '_%d' % i
            else:
                break

    return out_folder

def get_denss_log_items(path):
    import re
    item_re = re.compile(r'^\d+:\d+:\d+\s+Final\s+(.+):\s+(.+)$')
    ret_dict = {}
    with open(path) as log:
        for line in log:
            m = item_re.match(line)
            if m:
                ret_dict[m.group(1)] = float(m.group(2))
    return ret_dict

def run_pdb2mrc(in_file, queue=None):
    import time
    from SubProcess import Popen    # suppresses the child process window.
    from BasicUtils import get_home_folder
    print("Generating an mrc file.")
    script_path = os.path.join(get_home_folder(), r'lib\DENSS\bin\denss.pdb2mrc.py')
    python  = sys.executable.replace('pythonw.exe', 'python.exe')       # running with pythonw.exe seems inappropriate
    out_file = in_file.replace('.pdb', '')
    cmd = [python, script_path, '-f', in_file, '-o', out_file]
    # print(cmd)

    """
        currently not receiving the stdout of the child process.
        TODO: better print the progress.
    """
    p = Popen(cmd)
    while p.poll() is None:
        time.sleep(1)
        if queue is not None:
            queue.put((1, '.'))
    returncode = p.poll()

    if queue is not None:
        queue.put((1, '\n'))

    if returncode == 0:
        out_file = out_file + ".mrc"
        print("Generated %s" %  out_file)
    else:
        if queue is not None:
            queue.put((1, ret.stderr.decode() ))
        out_file = None
        print("Failed with returncode: %d" % returncode)

    return out_file
