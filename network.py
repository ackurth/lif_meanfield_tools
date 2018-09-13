"""
network.py: Main class providing functions to calculate the stationary and
dynamical properties of a given circuit.

Authors: Hannah Bos, Jannis Schuecker
"""

import numpy as np
import functools

import my_io as io
ureg = io.ureg
import meanfield_calcs

class Network(object):
    """
    Network with given parameters. The class provides methods for calculating
    stationary and dynamical properties of the defined network.

    Parameters:
    -----------
    network_params: str
        specifies path to yaml file containing network parameters
    analysis_params: str
        specifies path to yaml file containing analysis parameters
    new_network_params: dict
        dictionary specifying network parameters from yaml file that should be
        overwritten. Format:
        {'<param1>:{'val':<value1>, 'unit':<unit1>},...}
    new_analysis_params: dict
        dictionary specifying analysis parameters from yaml file that should be
        overwritten. Format:
        {'<param1>:{'val':<value1>, 'unit':<unit1>},...}
    """

    def __init__(self, network_params, analysis_params, new_network_params={},
                 new_analysis_params={}):
        """
        Initiate Network class.

        Load parameters from given yaml files using input output handling
        implemented in io.py and store them as instance variables.
        Overwrite parameters specified in new_network_parms and
        new_analysis_params.
        Calculate parameters which are derived from given parameters.
        Try to load existing results.
        """

        # load network params (read from yaml and convert to quantities)
        self.network_params = io.load_params(network_params)
        # load analysis params (read from yaml and convert to quantities)
        self.analysis_params = io.load_params(analysis_params)

        # convert new params to quantities
        new_network_params_converted = io.val_unit_to_quantities(
                                                            new_network_params)
        new_analysis_params_converted = io.val_unit_to_quantities(
                                                            new_analysis_params)
        # update network parameters
        self.network_params.update(new_network_params_converted)
        # update analysis parameters
        self.analysis_params.update(new_analysis_params_converted)

        # calculate dependend network parameters
        derived_network_params = self._calculate_dependent_network_parameters()
        self.network_params.update(derived_network_params)

        # calculate dependend analysis parameters
        derived_analysis_params = self._calculate_dependent_analysis_parameters()
        self.analysis_params.update(derived_analysis_params)
        # load already existing results
        self.results = io.load_results_from_h5(self.network_params,
                                               self.network_params.keys())


    def _calculate_dependent_network_parameters(self):
        """
        Calculate all network parameters derived from parameters in yaml file

        Returns:
        --------
        dict
            dictionary containing all derived network parameters
        """

        derived_params = {}

        # convert weights in pA to weights in mV
        derived_params['J'] = (self.network_params['tau_f']
                              * self.network_params['w']
                              / self.network_params['C']).to(ureg.mV)

        # reset reference potential to 0
        derived_params['V_0'] = 0 * ureg.mV
        derived_params['V_th'] = (self.network_params['V_th']
                                 - self.network_params['V_0'])

        # standard deviation of delay of excitatory connections
        derived_params['d_e_sd'] = self.network_params['d_e']*0.5
        # standard deviation of delay of inhibitory connections
        derived_params['d_i_sd'] = self.network_params['d_i']*0.5

        # weight matrix
        # TODO: check whether w must be replaced by J
        W = np.ones((8,8))*derived_params['J']
        W[1:8:2] *= -self.network_params['g']
        W = np.transpose(W)
        # larger weight for L4E->L23E connections
        W[0][2] *= 2.0
        derived_params['W'] = W

        # delay matrix
        D = np.ones((8,8))*self.network_params['d_e']
        D[1:8:2] = np.ones(8)*self.network_params['d_i']
        D = np.transpose(D)
        derived_params['Delay'] = D

        # delay standard deviation matrix
        D = np.ones((8,8))*derived_params['d_e_sd']
        D[1:8:2] = np.ones(8)*derived_params['d_i_sd']
        D = np.transpose(D)
        derived_params['Delay_sd'] = D

        return derived_params
        # # params for power spectrum
        # new_vars = {}
        # if circ.params['tf_mode'] == 'analytical':
        #     new_vars['M'] = circ.params['I']*circ.params['W']
        #     new_vars['trans_func'] = circ.ana.create_transfer_function()
        # else:
        #     for key in ['tau_impulse', 'delta_f']:
        #         new_vars[key] = circ.params[key]
        #     new_vars['H_df'] = circ.ana.create_H_df(new_vars, 'empirical')
        #     new_vars['M'] = circ.params['I']*circ.params['W']
        #
        # # copy of full connectivity (needed when connectivity is reduced)
        # new_vars['M_full'] = new_vars['M']


    def _calculate_dependent_analysis_parameters(self):
        """
        Calculate all analysis parameters derived from parameters in yaml file

        Returns:
        --------
        dict
            dictionary containing derived parameters
        """

        derived_params = {}

        # convert regular to angular frequencies
        w_min = 2*np.pi*self.analysis_params['f_min']
        w_max = 2*np.pi*self.analysis_params['f_max']
        dw = 2*np.pi*self.analysis_params['df']

        # enable usage of quantities
        @ureg.wraps(ureg.Hz, (ureg.Hz, ureg.Hz, ureg.Hz))
        def calc_evaluated_omegas(w_min, w_max, dw):
            """ Calculates omegas at which functions are to be evaluated """
            return np.arange(w_min, w_max, dw)

        derived_params['omegas'] = calc_evaluated_omegas(w_min, w_max, dw)

        return derived_params


    def _check_and_store_results(result_key):
        """
        Decorator function that checks whether result are already existing

        This decorator serves as a wrapper for functions that calculate
        quantities which are to be stored in self.results. First it checks,
        whether the result already has been stored in self.results. If this is
        the case, it returns that result. If not, the calculation is executed,
        the result is stored in self.results and the result is returned.

        Parameters:
        -----------
        result_key: str
            specifies under which key the result should be stored

        Returns:
        --------
        func
            decorator function
        """
        def decorator_check_results(func):
            # enable accessing attributes of original function
            @functools.wraps(func)
            def wrapper_check_results(self, *args, **kwargs):
                # collect results
                results = getattr(self, 'results')
                # check if new result is already stored in self.results
                if result_key in results.keys():
                    # if so, return already calcualted result
                    return results[result_key]
                else:
                    new_result = {}
                    # if not, calculate new result
                    new_result[result_key] = func(self, *args, **kwargs)
                    # update self.results
                    results.update(new_result)
                    setattr(self, 'results', results)
                    # return new_result
                    return new_result[result_key]
            return wrapper_check_results
        return decorator_check_results


    def save(self, param_keys={}, output_name=''):
        """
        Saves results and parameters to h5 file

        Parameters:
        -----------
        param_keys: dict
            specifies which parameters are used in hash for output name
        output_name: str
            if given, this is used as output file name

        Returns:
        --------
        None
        """

        io.save(self.results, self.network_params, self.analysis_params,
                param_keys, output_name)


    def show(self):
        """ Returns which results have already been calculated """
        return self.results.keys()


    # @_check_and_store_results('th_rates')
    # def firing_rates(self):
    #     """ Calculates firing rates """
    #     return meanfield_calcs.firing_rates(tau_m=self.network_params['tau_m'],
    #                                         tau_f=self.network_params['tau_f'],
    #                                         tau_r=self.network_params['tau_r'],
    #                                         dV=self.network_params['V_th'])

    def firing_rates(self):
        return meanfield_calcs.firing_rates()

    @_check_and_store_results('mu')
    def mean(self):
        """ Calculates mean """
        nu = self.firing_rates()
        return meanfield_calcs.mean(nu,
                                    self.network_params['K'],
                                    self.network_params['W'],
                                    self.network_params['J'],
                                    self.network_params['nu_ext'],
                                    self.network_params['K_ext'])

    @_check_and_store_results('var')
    def variance(self):
        """ Calculates variance """
        nu = self.firing_rates()

        return meanfield_calcs.variance(nu,
                                        self.network_params['K'],
                                        self.network_params['W'],
                                        self.network_params['J'],
                                        self.network_params['nu_ext'],
                                        self.network_params['K_ext'])


    def working_point(self):
        """
        Calculates stationary working point of the network

        Returns:
        dict
            dictionary specifying mean, variance and firing rates
        """

        # first define functions that keep track of already existing results

        # then do calculations
        working_point = {}
        firing_rates = self.firing_rates()
        working_point['mu'] = self.mean(firing_rates)
        working_point['var'] = self.variance(firing_rates)
        working_point['th_rates'] = firing_rates

        return working_point

#     @_check_and_store_results('hallo')
#     def calc_test(self):
#         return 'berechnet'
#
if __name__ == '__main__':
    net = Network('network_params_microcircuit.yaml', 'analysis_params.yaml')
    print(net.mean())
    print(net.variance())
    print(net.results)
    # @ureg.wraps(ureg.Hz, (ureg.s, ureg.dimensionless, ureg.dimensionless,
    #                       ureg.dimensionless, ureg.dimensionless,
    #                       ureg.dimensionless))
    # def test(a, b, c, d, e, f):
    #     return b/a * c * d * e * f
    # print(test(net.network_params['tau_m'], 4*ureg.dimensionless,
    #            3 * ureg.dimensionless, 3*ureg.dimensionless,
    #            3 * ureg.dimensionless, 3*ureg.dimensionless))


"""circuit.py: Main class providing functions to calculate the stationary
and dynamical properties of a given circuit.

Authors: Hannah Bos, Jannis Schuecker
"""

import numpy as np
from setup import Setup
from analytics import Analytics


class Circuit(object):
    """Provides functions to calculate the stationary and dynamical
    properties of a given circuit.

    Arguments:
    label: string specifying circuit, options: 'microcircuit'

    Keyword Arguments:
    params: dictionary specifying parameter of the circuit, default
            parameter given in params_circuit.py will be overwritten
    analysis_type: string specifying level of analysis that is requested
                   default: 'dynamical'
                   options:
                   - None: only circuit and default analysis parameter
                     are set
                   - 'stationary': circuit and default analysis parameter
                      are set, mean and variance of input to each
                      populations as well as firing rates are calculated
                   - 'dynamical': circuit and default analysis parameter
                      are set, mean and variance of input to each
                      populations as well as firing rates are calculated,
                      variables for calculation of spectra are calculated
                      including the transfer function for all populations
    fmin: minimal frequency in Hz, default: 0.1 Hz
    fmax: maximal frequency in Hz, default: 150 Hz
    df: frequency spacing in Hz, default: 1.0/(2*np.pi) Hz
    to_file: boolean specifying whether firing rates and transfer
             functions are written to file, default: True
    from_file: boolean specifying whether firing rates and transfer
               functions are read from file, default: True
               if set to True and file is not found firing rates and
               transfer function are calculated
    """
    def __init__(self, label, params={}, **kwargs):
        """Initiates circuit class:
        Instantiates Setup and Analysis,
        checks analysis type,
        saves default for (arbitrary) analysis parameters (like minimum and maximum frequency
        considered, or increment size) as attributes,
        calculates and saves parameters that need to be calculated from analysis parameters,
        calculates and saves parameters that need to be calculated using analysis.py (but thereto
        uses instance of setup)"""
        # specifies circuit, e.g. 'microcircuit'
        self.label = label
        # instantiated Classes Setup and Analysis
        self.setup = Setup()
        self.ana = Analytics()
        # check analysis type, default is 'dynamical'
        if 'analysis_type' in kwargs:
            self.analysis_type = kwargs['analysis_type']
        else:
            self.analysis_type = 'dynamical'
        # set default analysis and circuit parameter
        self._set_up_circuit(params, kwargs)
        # set parameter derived from analysis and circuit parameter
        new_vars = self.setup.get_params_for_analysis(self)
        new_vars['label'] = self.label
        self._set_class_variables(new_vars)
        # set variables which require calculation in analytics class
        self._calc_variables()

    # updates variables of Circuit() and Analysis() classes, new variables
    # are specified in the dictionary new_vars
    def _set_class_variables(self, new_vars):
        """saves given new_vars as attributes of network class instance
        AND as attributes of the instance variable self.ana, which is an istance
        of the class Analytics itself. (two seperate places where variables are stored!)"""
        for key, value in new_vars.items():
            setattr(self, key, value)
        if 'params' in new_vars:
            for key, value in new_vars['params'].items():
                setattr(self, key, value)
        self.ana.update_variables(new_vars)

    # updates class variables of variables of Circuit() and Analysis()
    # such that default analysis and circuit parameters are known
    def _set_up_circuit(self, params, args):
        """gets default analysis parameters from setup.py (stored there)
        and circuit parameters stored in params_circuit.py are collected using setup.py
        and a hash is created via params_circuit.py and stored as Network instance variable"""
        # set default analysis parameter
        new_vars = self.setup.get_default_params(args)
        self._set_class_variables(new_vars)
        # set circuit parameter
        new_vars = self.setup.get_circuit_params(self, params)
        self._set_class_variables(new_vars)

    # quantities required for stationary analysis are calculated
    def _set_up_for_stationary_analysis(self):
        """calculates and saves working point values using setup.py, which itself
        uses the instance of Analytics to calculate these values. """
        new_vars = self.setup.get_working_point(self)
        self._set_class_variables(new_vars)

    # quantities required for dynamical analysis are calculated
    def _set_up_for_dynamical_analysis(self):
        """ calculates and saves the variables needed for the calculation of spectra
        using setup.py, which itself uses the instance of Analytics to calculate these
        valuse."""
        new_vars = self.setup.get_params_for_power_spectrum(self)
        self._set_class_variables(new_vars)

    # calculates quantities needed for analysis specified by analysis_type
    def _calc_variables(self):
        """calculates the quantities needed for analysis using the functions
        given above and ensures, that nothing unnecessary is calculated."""
        if self.analysis_type == 'dynamical':
            self._set_up_for_stationary_analysis()
            self._set_up_for_dynamical_analysis()
        elif self.analysis_type == 'stationary':
            self._set_up_for_stationary_analysis()

    def alter_params(self, params):
        """Parameter specified in dictionary params are changed.
        Changeable parameters are default analysis and circuit parameter,
        as well as label and analysis_type.

        Arguments:
        params: dictionary, specifying new parameters
        """
        self.params.update(params)
        # calculate and change new parameters for circuit
        new_vars = self.setup.get_altered_circuit_params(self, self.label)
        self._set_class_variables(new_vars)
        # use new circuit to calculate and save analysis parameters
        new_vars = self.setup.get_params_for_analysis(self)
        self._set_class_variables(new_vars)
        # calculate needed quantities again
        self._calc_variables()

#################################################################################################
    """ Here the part with the functional methods beginns"""

    def create_power_spectra(self):
        """Returns frequencies and power spectra.
        See: Eq. 9 in Bos et al. (2015)
        Shape of output: (len(self.populations), len(self.omegas))

        Output:
        freqs: vector of frequencies in Hz
        power: power spectra for all populations,
               dimension len(self.populations) x len(freqs)
        """
        power = np.asarray(list(map(self.ana.spec, self.ana.omegas)))
        return self.ana.omegas/(2.0*np.pi), np.transpose(power)

    def create_power_spectra_approx(self):
        """Returns frequencies and power spectra approximated by
        dominant eigenmode.
        See: Eq. 15 in Bos et al. (2015)
        Shape of output: (len(self.populations), len(self.omegas))

        Output:
        freqs: vector of frequencies in Hz
        power: power spectra for all populations,
               dimension len(self.populations) x len(freqs)
        """
        power = np.asarray(list(map(self.ana.spec_approx, self.ana.omegas)))
        return self.ana.omegas/(2.0*np.pi), np.transpose(power)

    def create_eigenvalue_spectra(self, matrix):
        """Returns frequencies and frequency dependence of eigenvalues of
        matrix.

        Arguments:
        matrix: string specifying the matrix, options are the effective
                connectivity matrix ('MH'), the propagator ('prop') and
                the inverse of the propagator ('prop_inv')

        Output:
        freqs: vector of frequencies in Hz
        eigs: spectra of all eigenvalues,
              dimension len(self.populations) x len(freqs)
        """
        eigs = [self.ana.eigs_evecs(matrix, w)[0] for w in self.ana.omegas]
        eigs = np.transpose(np.asarray(eigs))
        return self.ana.omegas/(2.0*np.pi), eigs

    def create_eigenvector_spectra(self, matrix, label):
        """Returns frequencies and frequency dependence of
        eigenvectors of matrix.

        Arguments:
        matrix: string specifying the matrix, options are the effective
                connectivity matrix ('MH'), the propagator ('prop') and
                the inverse of the propagator ('prop_inv')
        label: string specifying whether spectra of left or right
               eigenvectors are returned, options: 'left', 'right'

        Output:
        freqs: vector of frequencies in Hz
        evecs: spectra of all eigenvectors,
               dimension len(self.populations) x len(freqs) x len(self.populations)
        """
        # one list entry for every eigenvector, evecs[i][j][k] is the
        # ith eigenvectors at the jth frequency for the kth component
        evecs = [np.zeros((len(self.ana.omegas), self.ana.dimension),
                          dtype=complex) for i in range(self.ana.dimension)]
        for i, w in enumerate(self.ana.omegas):
            eig, vr, vl = self.ana.eigs_evecs(matrix, w)
            if label == 'right':
                v = vr
            elif label == 'left':
                v = vl
            for j in range(self.ana.dimension):
                evecs[j][i] = v[j]
        evecs = np.asarray([np.transpose(evecs[i]) for i in range(self.ana.dimension)])
        return self.ana.omegas/(2.0*np.pi), evecs

    def reduce_connectivity(self, M_red):
        """Connectivity (indegree matrix) is reduced, while the working
        point is held constant.

        Arguments:
        M_red: matrix, with each element specifying how the corresponding
               connection is altered, e.g the in-degree from population
               j to population i is reduced by 30% with M_red[i][j]=0.7
        """
        M_original = self.M_full[:]
        if M_red.shape != M_original.shape:
            raise RuntimeError('Dimension of mask matrix has to be the '
                               + 'same as the original indegree matrix.')
        self.M = M_original*M_red
        self.ana.update_variables({'M': self.M})

    def restore_full_connectivity(self):
        '''Restore connectivity to full connectivity.'''
        self.M = self.M_full
        self.ana.update_variables({'M': self.M})

    def get_effective_connectivity(self, freq):
        """Returns effective connectivity matrix.

        Arguments:
        freq: frequency in Hz
        """
        return self.ana.create_MH(2*np.pi*freq)

    def get_sensitivity_measure(self, freq, index=None):
        """Returns sensitivity measure.
        see: Eq. 21 in Bos et al. (2015)

        Arguments:
        freq: frequency in Hz

        Keyword arguments:
        index: specifies index of eigenmode, default: None
               if set to None the dominant eigenmode is assumed
        """
        MH  = self.get_effective_connectivity(freq)
        e, U = np.linalg.eig(MH)
        U_inv = np.linalg.inv(U)
        if index is None:
            # find eigenvalue closest to one
            index = np.argmin(np.abs(e-1))
        T = np.outer(U_inv[index],U[:,index])
        T /= np.dot(U_inv[index],U[:,index])
        T *= MH
        return T

    def get_transfer_function(self):
        """Returns dynamical transfer function depending on frequency.
        Shape of output: (len(self.populations), len(self.omegas))

        Output:
        freqs: vector of frequencies in Hz
        dyn_trans_func: power spectra for all populations,
                        dimension len(self.populations) x len(freqs)
        """
        dyn_trans_func = np.asarray(list(map(self.ana.create_H, self.ana.omegas)))
        return self.ana.omegas/(2.0*np.pi), np.transpose(dyn_trans_func)
