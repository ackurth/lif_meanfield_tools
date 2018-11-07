'''
Handles reading-in yaml files and converting the physical parameters, specified
in yaml files, to theoretical parameters, needed for usage of given implemented
functions (they rely on a redefinition of quantities). Handles output-writing
and provides function for creating hashes to uniquely identify output files.

Usage: io.py [options]

Options:
    -h, --help       show extensive usage information
'''

from __future__ import print_function

import numpy as np
import yaml
import hashlib as hl
import h5py_wrapper.wrapper as h5

from . import ureg

def val_unit_to_quantities(dict_of_val_unit_dicts):
    """
    Convert a dictionary of value-unit pairs to a dictionary of quantities

    Combine value and unit of each quantity and save them in a dictionary
    of the structure: {'<quantity_key1>':<quantity1>, ...}.

    Lists are converted to numpy arrays and then converted to quantities.

    Quantities or names without units, are just stored the way they are.

    Parameters:
    -----------
    dict_of_val_unit_dicts: dict
        dictionary of format {'<quantity_key1>':{'val':<value1>,
                                                 'unit':<unit1>},
                              '<quantity_key2>':<value2>,
                                                 ...}

    Returns:
    --------
    dict
        Converted dictionary of format explained above.
    """
    def formatval(val):
        """ If argument is of type list, convert to np.array. """
        if isinstance(val, list):
            return np.array(val)
        else:
            return val

    converted_dict = {}
    for key, value in dict_of_val_unit_dicts.items():
        # if dictionary with keys val and unit, convert to quantity
        if isinstance(value, dict) and set(('val', 'unit')) == value.keys():
            converted_dict[key] = (formatval(value['val']) * ureg.parse_expression(value['unit']))
        else:
            converted_dict[key] = formatval(value)
    return converted_dict


def quantities_to_val_unit(dict_of_quantities):
    """
    Convert a dictionary of quantities to a dictionary of val-unit pairs

    Split up value and unit of each quantiy and save them in a dictionary
    of the structure: {'<parameter1>:{'val':<value>, 'unit':<unit>}, ...}

    Lists of quantities are handled seperately. Anything else but quantities, is
    stored just the way it is given. 

    Parameters:
    -----------
    dict_containing_quantities: dict
        dictionary containing only quantities (pint package) of format
        {'<quantity_key1>':<quantity1>, ...}

    Returns:
    --------
    dict
        converted dictionary
    """
    converted_dict = {}
    for quantity_key, quantity in dict_of_quantities.items():
        converted_dict[quantity_key] = {}

        # lists of strings need to be treated seperately
        if isinstance(quantity, list):
            if any(isinstance(part, str) for part in quantity):
                converted_dict[quantity_key] = quantity
            elif any(isinstance(part, ureg.Quantity) for part in quantity):
                converted_dict[quantity_key]['val'] = np.stack([array.magnitude for array in quantity])
                converted_dict[quantity_key]['unit'] = str(quantity[0].units)
        # quantities are converted to val unit dictionary
        elif isinstance(quantity, ureg.Quantity):
            converted_dict[quantity_key]['val'] = quantity.magnitude
            converted_dict[quantity_key]['unit'] = str(quantity.units)
        # anything else is stored the way it is
        else:
            converted_dict[quantity_key] = quantity
    return converted_dict


def load_params(file_path):
    """
    Load and convert parameters from yaml file

    Load parameters from yaml file and convert them from value unit dictionaries
    (used in yaml file) to quantities (used in implementation of functions in
    meanfield_calcs.py).

    Parameters:
    -----------
    file_path : str
        string specifying path to yaml file containing parameters in format
        <parameter1>:
            val: <value1>
            unit: <unit1>
        ...

    Returns:
    --------
    dict
        dictionary containing all converted parameters as quantities
    """

    # try to load yaml file
    with open(file_path, 'r') as stream:
        try:
            params = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    # convert parameters to quantities
    params_converted = val_unit_to_quantities(params)

    # return converted network parameters
    return params_converted


def create_hash(params, param_keys):
    """
    Create unique hash from values of parameters specified in param_keys.

    Parameters:
    -----------
    params : dict
        Dictionary containing all network parameters.
    param_keys : list
        List specifying which parameters should be reflected in hash.

    Returns:
    --------
    str
        Hash string.
    """

    label = ''
    # add all param values to one string
    for key in sorted(list(param_keys)):
        label += str(params[key])
    # create and return hash (label must be encoded)
    return hl.md5(label.encode('utf-8')).hexdigest()


def save(results_dict, network_params, analysis_params, param_keys=[], output_name=''):
    """
    Save data and given paramters in h5 file.

    By default the output name will be <label>_<hash>.h5, where the hash is
    created using network_params. But you can either specify an ouput_name
    yourself, or specify which param_keys should be reflected in the hash.

    Parameters:
    -----------
    results_dict : dict
        Dictionary containing all calculated results.
    network_params : dict
        Dictionary containing network parameters as quantities.
    analysis_params: dict
        Dictionary containing analysis parameters as quantities.
    param_keys: list
        List of parameters used in file hash.
    output_name: str
        Optional string specifying output file name.

    Returns:
    --------
    None
    """

    # is user did not specify output name
    if not output_name:
        # collect all parameters reflected by hash in one dictionary
        hash_params = {}
        hash_params.update(network_params)
        # if user did not specify which parameters to use for hash
        if not param_keys:
            # take all parameters sorted alphabetically
            param_keys = sorted(list(hash_params.keys()))
        # crate hash from param_keys
        hash = create_hash(hash_params, param_keys)
        # default output name
        output_name = '{}_{}.h5'.format(network_params['label'], str(hash))

    # convert data and network params into format usable in h5 files
    results = quantities_to_val_unit(results_dict)
    network_params = quantities_to_val_unit(network_params)
    analysis_params = quantities_to_val_unit(analysis_params)

    output = dict(analysis_params=analysis_params, network_params=network_params, results=results)
    # save output
    h5.save(output_name, output, overwrite_dataset=True)


def load_from_h5(network_params, param_keys=[], input_name=''):
    """
    Load existing results and analysis_params for given parameters from h5 file.

    Loads results from h5 files named with the standard format
    <label>_<hash>.h5, if this file already exists. Or uses given list of
    parameters to create hash to find file. Or reads from file specified in
    input_name.

    Parameters:
    -----------
    network_params : dict
        Dictionary containing network parameters as quantities.
    param_keys: list
        List of parameters used in file hash.
    input_name: str
        optional string specifying input file name (default: <label>_<hash>.h5).

    Returns:
    --------
    analysis_params: dict
        Dictionary containing all found analysis_params.
    results: dict
        Dictionary containing all found results.
    """

    # if no input file name is specified
    if not input_name:
        # create hash from given parameters
        # collect all parameters reflected by hash in one dictionary
        hash_params = {}
        hash_params.update(network_params)
        # if user did not specify which parameters to use for hash
        if not param_keys:
            # take all parameters sorted alphabetically
            param_keys = sorted(list(hash_params.keys()))
        # crate hash from param_keys
        hash = create_hash(hash_params, param_keys)
        # default input name
        input_name = '{}_{}.h5'.format(network_params['label'], str(hash))

    # try to load file with standard name
    try:
        input_file = h5.load('{}_{}.h5'.format(network_params['label'], hash))
    # if not existing OSError is raised by h5py_wrapper, then return empty dict
    except OSError:
        return {}, {}

    # read in whats already stored
    analysis_params = input_file['analysis_params']
    results = input_file['results']

    # convert results to quantitites
    analysis_params = val_unit_to_quantities(analysis_params)
    results = val_unit_to_quantities(results)

    return analysis_params, results
