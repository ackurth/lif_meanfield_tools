from __future__ import print_function
from scipy.integrate import quad
from scipy.special import erf
from scipy.special import zetac
import numpy as np
import math
import mpmath


from input_output import ureg


@ureg.wraps(ureg.Hz, (ureg.s, ureg.s, ureg.s, ureg.mV, ureg.mV, ureg.mV,
                      ureg.mV), strict=False)
def nu0_fb433(tau_m, tau_s, tau_r, V_th_rel, V_0_rel, mu, sigma):
    """
    Calcs stationary firing rates for exp PSCs

    Calculates the stationary firing rate of a neuron with synaptic filter of
    time constant tau_s driven by Gaussian noise with mean mu and standard
    deviation sigma, using Eq. 433 in Fourcaud & Brunel (2002) with Taylor
    expansion k = sqrt(tau_s/tau_m).

    Parameters:
    -----------
    tau_m: float
        Membrane time constant in seconds.
    tau_s: float
        Synaptic time constant in seconds.
    tau_r: float
        Refractory time in seconds.
    V_th_rel: float
        Relative threshold potential in mV.
    V_0_rel: float
        Relative reset potential in mV.
    mu: float
        Mean neuron activity in mV.
    sigma:
        Standard deviation of neuron activity in mV.

    Returns:
    --------
    float:
        Stationary firing rate in Hz.
    """
    alpha = np.sqrt(2.) * abs(zetac(0.5) + 1)
    x_th = np.sqrt(2.) * (V_th_rel - mu) / sigma
    x_r = np.sqrt(2.) * (V_0_rel - mu) / sigma

    # preventing overflow in np.exponent in Phi(s)
    if x_th > 20.0 / np.sqrt(2.):
        result = nu_0(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma)
    else:
        r = nu_0(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma)
        dPhi = Phi(x_th) - Phi(x_r)
        result = (r - np.sqrt(tau_s / tau_m) * alpha / (tau_m * np.sqrt(2))
                  * dPhi * (r * tau_m)**2)
    if math.isnan(result):
        print(mu, sigma, x_th, x_r)
    return result


def nu_0(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma):
    """
    Calculates stationary firing rates for delta shaped PSCs.

    Parameters:
    -----------
    tau_m: float
        Membrane time constant in seconds.
    tau_r: float
        Refractory time in seconds.
    V_th_rel: float
        Relative threshold potential in mV.
    V_0_rel: float
        Relative reset potential in mV.
    mu: float
        Mean neuron activity in mV.
    sigma:
        Standard deviation of neuron activity in mV.

    Returns:
    --------
    float:
        Stationary firing rate in Hz.
    """
    if mu <= V_th_rel + (0.95 * abs(V_th_rel) - abs(V_th_rel)):
        return siegert1(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma)
    else:
        return siegert2(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma)


def siegert1(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma):
    """
    Calculates stationary firing rates for delta shaped PSCs.

    Parameters:
    -----------
    tau_m: float
        Membrane time constant in seconds.
    tau_r: float
        Refractory time in seconds.
    V_th_rel: float
        Relative threshold potential in mV.
    V_0_rel: float
        Relative reset potential in mV.
    mu: float
        Mean neuron activity in mV.
    sigma:
        Standard deviation of neuron activity in mV.

    Returns:
    --------
    float:
        Stationary firing rate in Hz.
    """
    # for mu < V_th_rel
    y_th = (V_th_rel - mu) / sigma
    y_r = (V_0_rel - mu) / sigma

    def integrand(u):
        if u == 0:
            return np.exp(-y_th**2) * 2 * (y_th - y_r)
        else:
            return np.exp(-(u - y_th)**2) * (1.0 - np.exp(2 * (y_r - y_th) * u)) / u

    lower_bound = y_th
    err_dn = 1.0
    while err_dn > 1e-12 and lower_bound > 1e-16:
        err_dn = integrand(lower_bound)
        if err_dn > 1e-12:
            lower_bound /= 2

    upper_bound = y_th
    err_up = 1.0
    while err_up > 1e-12:
        err_up = integrand(upper_bound)
        if err_up > 1e-12:
            upper_bound *= 2

    # check preventing overflow
    if y_th >= 20:
        out = 0.
    if y_th < 20:
        out = 1.0 / (tau_r + np.exp(y_th**2)
                     * quad(integrand, lower_bound, upper_bound)[0] * tau_m)

    return out


def siegert2(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma):
    """
    Calculates stationary firing rates for delta shaped PSCs.

    Parameters:
    -----------
    tau_m: float
        Membrane time constant in seconds.
    tau_r: float
        Refractory time in seconds.
    V_th_rel: float
        Relative threshold potential in mV.
    V_0_rel: float
        Relative reset potential in mV.
    mu: float
        Mean neuron activity in mV.
    sigma:
        Standard deviation of neuron activity in mV.

    Returns:
    --------
    float:
        Stationary firing rate in Hz.
    """
    # for mu > V_th_rel
    y_th = (V_th_rel - mu) / sigma
    y_r = (V_0_rel - mu) / sigma

    def integrand(u):
        if u == 0:
            return 2 * (y_th - y_r)
        else:
            return (np.exp(2 * y_th * u - u**2) - np.exp(2 * y_r * u - u**2)) / u

    upper_bound = 1.0
    err = 1.0
    while err > 1e-12:
        err = integrand(upper_bound)
        upper_bound *= 2

    return 1.0 / (tau_r + quad(integrand, 0.0, upper_bound)[0] * tau_m)


def Phi(s):
    """
    where does this come from and what does it do???
    """
    return np.sqrt(np.pi / 2.) * (np.exp(s**2 / 2.) * (1 + erf(s / np.sqrt(2))))


def Phi_prime_mu(s, sigma):
    """
    where does this come from and what does it do???
    """
    return -np.sqrt(np.pi) / sigma * (s * np.exp(s**2 / 2.)
    * (1 + erf(s / np.sqrt(2)))
    + np.sqrt(2) / np.sqrt(np.pi))


@ureg.wraps(ureg.Hz*ureg.mV, (ureg.s, ureg.s, ureg.s, ureg.mV, ureg.mV, ureg.mV, ureg.mV), strict=False)
def d_nu_d_mu_fb433(tau_m, tau_s, tau_r, V_th_rel, V_0_rel, mu, sigma):
    """
    where does this come from and what does it do???

    Parameters:
    -----------
    tau_m: float
        Membrane time constant in seconds.
    tau_s: float
        Synaptic time constant in seconds.
    tau_r: float
        Refractory time in seconds.
    V_th_rel: float
        Relative threshold potential in mV.
    V_0_rel: float
        Relative reset potential in mV.
    mu: float
        Mean neuron activity in mV.
    sigma:
        Standard deviation of neuron activity in mV.

    Returns:
    --------
    float:
        Something in Hz/mV.
    """
    alpha = np.sqrt(2) * abs(zetac(0.5) + 1)
    x_th = np.sqrt(2) * (V_th_rel - mu) / sigma
    x_r = np.sqrt(2) * (V_0_rel - mu) / sigma
    integral = 1. / (nu_0(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma) * tau_m)
    prefactor = np.sqrt(tau_s / tau_m) * alpha / (tau_m * np.sqrt(2))
    dnudmu = d_nu_d_mu(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma)
    dPhi_prime = Phi_prime_mu(x_th, sigma) - Phi_prime_mu(x_r, sigma)
    dPhi = Phi(x_th) - Phi(x_r)
    phi = dPhi_prime * integral + (2 * np.sqrt(2) / sigma) * dPhi**2
    return dnudmu - prefactor * phi / integral**3


def d_nu_d_mu(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma):
    """
    where does this come from and what does it do???

    Parameters:
    -----------
    tau_m: float
        Membrane time constant in seconds.
    tau_s: float
        Synaptic time constant in seconds.
    tau_r: float
        Refractory time in seconds.
    V_th_rel: float
        Relative threshold potential in mV.
    V_0_rel: float
        Relative reset potential in mV.
    mu: float
        Mean neuron activity in mV.
    sigma:
        Standard deviation of neuron activity in mV.

    Returns:
    --------
    float:
        Something in Hz/mV.
    """
    y_th = (V_th_rel - mu)/sigma
    y_r = (V_0_rel - mu)/sigma
    nu0 = nu_0(tau_m, tau_r, V_th_rel, V_0_rel, mu, sigma)
    return (np.sqrt(np.pi) * tau_m * nu0**2 / sigma
            * (np.exp(y_th**2) * (1 + erf(y_th)) - np.exp(y_r**2)
               * (1 + erf(y_r))))


@ureg.wraps(None, (ureg.dimensionless, ureg.dimensionless), strict=False)
def Psi(z, x):
    """
    Calcs Psi(z,x)=exp(x**2/4)*U(z,x), with U(z,x) the parabolic cylinder func.
    """
    return np.exp(0.25*x**2) * complex(mpmath.pcfu(z, -x))

@ureg.wraps(None, (ureg.dimensionless, ureg.dimensionless), strict=False)
def d_Psi(z, x):
    """
    First derivative of Psi using recurrence relations.

    (Eq.: 12.8.9 in http://dlmf.nist.gov/12.8)
    """
    return (1. / 2. + z) * Psi(z + 1, x)

@ureg.wraps(None, (ureg.dimensionless, ureg.dimensionless), strict=False)
def d_2_Psi(z, x):
    """
    Second derivative of Psi using recurrence relations.

    (Eq.: 12.8.9 in http://dlmf.nist.gov/12.8)
    """
    return (1. / 2. + z) * (3. / 2. + z) * Psi(z + 2, x)

@ureg.wraps(None, (ureg.dimensionless, ureg.dimensionless, ureg.dimensionless), strict=False)
def Psi_x_r(z, x, y):
    """Difference of Psi for same first argument z."""
    return Psi(z, x) - Psi(z, y)

@ureg.wraps(None, (ureg.dimensionless, ureg.dimensionless, ureg.dimensionless), strict=False)
def dPsi_x_r(z, x, y):
    """Difference of derivatives of Psi for same first argument z."""
    return d_Psi(z, x) - d_Psi(z, y)

@ureg.wraps(None, (ureg.dimensionless, ureg.dimensionless, ureg.dimensionless), strict=False)
def d2Psi_x_r(z, x, y):
    """Difference of second derivatives of Psi for same first argument z."""
    return d_2_Psi(z, x) - d_2_Psi(z, y)