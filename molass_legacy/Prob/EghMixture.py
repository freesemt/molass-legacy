# coding: utf-8
"""
    EghMixture.py

    Copyright (c) 2020, SAXS Team, KEK-PF
"""
import sys
import logging
import numpy as np
import scipy.stats as stats
from scipy.optimize import fsolve
from sklearn.cluster import KMeans
import DebugPlot as plt
from lmfit import minimize, Parameters

USE_MODE_AS_TR_INIT = True
USE_MODERATE_SIGMAS = True
MODERATE_SIGMAS_RATIO = 1.5
APPLY_PARAM_CONSTRAINTS = True

def egh(x, H=1, tR=0, sigma=1.0, tau=0.0):
    x_  = x - tR
    s2  = 2 * sigma**2
    z   = s2 + tau*x_
    z_neg   = z <= 0
    z_pos   = z > 0

    zero_part = np.zeros( len(x) )[z_neg]
    posi_part = H * np.exp( -x_[z_pos]**2/( s2 + tau*x_[z_pos] ) )

    if tau >= 0:
        parts = [ zero_part, posi_part ]
    else:
        parts = [ posi_part, zero_part ]

    return np.hstack( parts )

"""
Kevin Lan, James W. Jorgenson, Journal of Chromatography A, 915 (2001) 1?13
"""
A0i = np.array([4, -6.293724, 9.232834, -11.342910, 9.123978, -4.173753, 0.827797])
e0 = np.poly1d(A0i[::-1])
"""
e0(th) = a0 + a1*th + a2*th**2 + ... + am*th**m
"""
A1i = np.array([0.75, 0.033807, -0.301080, 1.200371, -1.813317, 1.279318, -0.326582])
e1 = np.poly1d(A1i[::-1])

A2i = np.array([1, -0.982254, 0.568593, 0.512587, -1.184361, 0.939222, -0.240814])
e2 = np.poly1d(A2i[::-1])

# A3i = np.array([0.5, -0.664611, 0.706192, -0.293500, -0.083980, 0.200306, -0.064264])
A3i = np.array([0.49106035, -0.45648717, -0.93606276, 5.25394258, -9.16354757, 7.36039624, -2.25720537])
e3 = np.poly1d(A3i[::-1])

SQRT_PI_8 = np.sqrt(np.pi/8)
def egh_pdf(x, tR=0, sigma=1.0, tau=0.0, scale=1):
    tau_ = abs(tau)
    th = np.arctan2(tau_, sigma)
    H_ = (sigma*SQRT_PI_8 + tau_)*e0(th)
    return egh(x, scale, tR, sigma, tau)/H_

class EghMixture:
    model_name = "EGH"

    def __init__(self, K, max_iter=100, random_state=None, anim_data=False):
        self.logger = logging.getLogger(__name__)
        self.K = K
        self.max_iter = max_iter
        self.random_state = random_state
        self.anim_data = anim_data

    def fit(self, X, bins=None):
        assert X.shape[1] == 1
        self.initilize(X, bins)

        for step in range(self.max_iter):
            self._e_step()
            self.update_params(step, self._m_step(step))

        print('result pi=', self.pi)
        print('result tR=', self.tR)
        print('result sigma=', self.sigma)
        print('result tau=', self.tau)

    def initilize(self, X, bins):
        self.N = X.shape[0]
        self.X = X
        self.X_  = X.flatten()
        self.bins = bins
        self.guess_initial_params()

    def guess_initial_params(self):
        X = self.X
        num_entire_points = X.shape[0]
        kmeans = KMeans(n_clusters= self.K, random_state=self.random_state)
        kmeans.fit(X)
        # predicted = kmeans.predict(X)
        predicted = kmeans.labels_
        labels = np.unique(predicted)
        init_params = []

        for label in labels:
            sy = X[predicted == label]

            M1 = np.mean(sy)
            if USE_MODE_AS_TR_INIT:
                # seems risky
                m, c = stats.mode(sy)
                tR = m[0,0]
            else:
                tR = M1

            num_points = sy.shape[0]
            pi = num_points/num_entire_points
            # M2 = pi*np.sum((sy - tR)**2)/num_points     # why pi* in Foley's implementation?
            M2 = np.sum((sy - M1)**2)/num_points
            sigma = np.sqrt(M2)
            # print([label], m, c, M2, np.sqrt(M2), sigma)
            init_params.append((pi, tR, sigma))

        sorted_params = np.array(sorted(init_params, key=lambda x:x[1]))

        self.pi = sorted_params[:,0]
        self.tR = sorted_params[:,1]
        self.sigma = sorted_params[:,2]
        self.tau = np.zeros(self.K)
        if False:
            print('init pi=', self.pi)
            print('init tR=', self.tR)
            print('init sigma=', self.sigma)
            print('init tau=', self.tau)
        if APPLY_PARAM_CONSTRAINTS:
            self.min_sigma = self.sigma*0.5
            self.max_sigma = self.sigma*2
            self.min_tR = np.max([np.zeros(self.K), self.tR - self.sigma], axis=0)
            self.max_tR = self.tR + self.sigma

        # assert np.sum(initial_pi) == 1
        assert abs(np.sum(self.pi) - 1) < 1e-10

        if False:
            plt.push()
            fig = plt.figure()
            ax = fig.gca()
            ax.hist(X.flatten(), bins=self.bins)
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(ymin, ymax)
            for tR in self.tR:
                ax.plot([tR, tR], [ymin, ymax], ':', color='red')
            plt.show()
            plt.pop()

        if self.anim_data:
            array_shape = (self.max_iter+1, self.K)
            self.pi_array = np.zeros(array_shape)
            self.tR_array = np.zeros(array_shape)
            self.sigma_array = np.zeros(array_shape)
            self.tau_array = np.zeros(array_shape)
            self.gamma_array = np.zeros((self.max_iter+1, self.N, self.K))
            self.set_anim_params(0)

    def set_anim_params(self, n):
        self.pi_array[n,:] = self.pi
        self.tR_array[n,:] = self.tR
        self.sigma_array[n,:] = self.sigma
        self.tau_array[n,:] = self.tau
        if n > 0:
            self.gamma_array[n,:,:] = self.gamma

    def _e_step(self):
        self.gamma = np.zeros((self.N, self.K))

        for k in range(self.K):
            # Posterior Distribution using Bayes Rule
            self.gamma[:,k] = self.pi[k] * egh_pdf(self.X_, self.tR[k], self.sigma[k], self.tau[k])

        # normalize across columns to make a valid probability
        # gamma_norm = np.sum(self.gamma, axis=1)[:,np.newaxis]
        gamma_norm = np.sum(self.gamma, axis=1)

        if False:
            print('pi=', self.pi)
            print('gamma_norm=', gamma_norm)
            plt.push()
            fig = plt.figure()
            ax = fig.gca()
            ax.plot(gamma_norm.flatten())
            plt.show()
            plt.pop()

        positive = gamma_norm > 0
        for k in range(self.K):
            self.gamma[positive,k] /= gamma_norm[positive]      # normalize only where positive

        if False:
            from .GammaVisualizer import GammaVisualizer
            print(sys.getsizeof(self.gamma))
            vis = GammaVisualizer()
            vis.show(self.gamma)

    def _m_step(self, step, pi_only=False):

        # responsibilities for each gaussian
        self.pi = np.mean(self.gamma, axis=0)

        if pi_only:
            return

        W_ = np.sum(self.gamma, axis=0)[:,np.newaxis].T
        # print('GT.shape=', GT.shape)
        # print('GT[:,0:5]=', GT[:,0:5])
        # print('W_=', W_)

        """
        2.1.1 Central Moments and their Distribution Functions
        https://www.iue.tuwien.ac.at/phd/puchner/node17.html#SECTION00811000000000000000
        2.1.2 Probability Weighted Moments and their Distribution Functions
        https://www.iue.tuwien.ac.at/phd/puchner/node18.html

        Central moment - Wikipedia
        https://en.wikipedia.org/wiki/Central_moment
        """

        debug = False

        # M1 = (np.dot(self.gamma.T, self.X) / W_.T).T
        M1 = np.sum(self.gamma * self.X, axis=0) / W_
        M2 = np.sum(self.gamma * (self.X-M1)**2, axis=0) / W_
        M3 = np.sum(self.gamma * (self.X-M1)**3, axis=0) / W_

        if debug:
            print('M1=', M1)
            print('M2=', M2)
            print('M3=', M3)

        params = []
        for k in range(self.K):
            params.append(self.solve_params(k, M1[0,k], M2[0,k], M3[0,k]))

        params_ = np.array(params)
        if debug:
            print('params_=', params_)

        return params_

    def update_params(self, step, params_):
        self.tR = params_[:,0]
        if USE_MODERATE_SIGMAS:
            self.sigma = self.moderate_sigmas(params_[:,1])
        else:
            self.sigma = params_[:,1]
        self.tau = params_[:,2]

        if self.anim_data:
            self.set_anim_params(step+1)

    def moderate_sigmas(self, sigmas):
        if self.K > 1:
            L = list(range(self.K))
            k = np.argmax(sigmas)
            del L[k]
            sigmas_ = sigmas.copy()
            sigmas_[k] = min(sigmas[k], np.average(sigmas[L]) * MODERATE_SIGMAS_RATIO)
            return sigmas_
        else:
            return sigmas

    def solve_params(self, k, m1, m2, m3):
        last_tR = self.tR[k]
        last_sigma = self.sigma[k]
        last_tau = self.tau[k]

        def equations(p):
            tR, sigma, tau = p
            tau_ = abs(tau)         # better for 2019118_3
            # tau_ = tau            # seems better for some cases such as 20181203, although abs(tau) is mentioned in the paper.
            th = np.arctan2(tau_, sigma)
            return (
                        tR + tau*e1(th) - m1,
                        (sigma**2 + sigma*tau_ + tau**2)*e2(th) - m2,
                        tau*(3*sigma**2 + 4*sigma*tau_ + 4*tau**2)*e3(th) - m3,
                   )

        x, infodict, ier, mesg = fsolve(equations, (last_tR, last_sigma, last_tau), full_output=True)
        if ier in [1, 4, 5]:
            """
            5 : The iteration is not making good progress, as measured by the
                improvement from the last ten iterations.
            4 : The iteration is not making good progress, as measured by the
                improvement from the last five Jacobian evaluations.
            """
            tR, sigma, tau = x
        else:
            print('ier=', ier)
            self.logger.warning(mesg)
            self.fsolve_error = True
            tR, sigma, tau = last_tR, last_sigma, last_tau

        if APPLY_PARAM_CONSTRAINTS:
            """
            better constraints desired
            """
            tR = max(self.min_tR[k], min(self.max_tR[k], tR))
            sigma = max(self.min_sigma[k], min(self.max_sigma[k], sigma))
            ns = sigma*3
            tau = max(-ns, min(ns, tau))

        debug = False

        if debug:
            print([k], (last_tR, '->', tR))
            print([k], (last_sigma, '->', sigma))
            print([k], (last_tau, '->', tau))

        return tR, sigma, tau

    def get_anim_components(self, x, y, n):
        gy_list = []
        ty = np.zeros(len(x))
        for k in range(len(self.pi)):
            w = self.pi_array[n,k]
            m = self.tR_array[n,k]
            s = self.sigma_array[n,k]
            t = self.tau_array[n,k]
            # print([n,k], w, m, s, t)
            gy = egh_pdf(x, m, s, t, w)
            gy_list.append([gy, m])
            ty += gy

        sorted_gy_list = sorted(gy_list, key=lambda x:x[1])

        def obj_func(params):
            S   = params['S']
            return ty*S - y

        params = Parameters()
        S_init = np.max(y)/np.max(ty)
        params.add('S', value=S_init, min=0, max=S_init*100 )
        result = minimize(obj_func, params, args=())

        scale = result.params['S'].value
        return [ ty*scale ] + [ scale*rec[0] for rec in sorted_gy_list ]

    def get_anim_C(self, x, y, n, total=False):
        gy_list = self.get_anim_components(x, y, n)
        if total:
            return np.array(gy_list[1:]), gy_list[0]
        else:
            return np.array(gy_list[1:])

    def get_peak_mean_x(self):
        return self.tR

def get_sorted_params(eghmm):
    # sort results in the order of the means
    params = zip(eghmm.tR, eghmm.sigma, eghmm.tau, eghmm.pi)
    sorted_params = sorted([ (m, s, t, w) for m, s, t, w in params], key=lambda p:p[0])
    return sorted_params

def get_curves(eghmm, x):
    sorted_params = get_sorted_params(eghmm)

    # plot the results
    gy_list = []
    ty = np.zeros(len(x))
    for m, s, t, w in sorted_params:
        gy = egh_pdf(x, m, s, t, w)
        gy_list.append(gy)
        ty += gy

    return ty, gy_list

