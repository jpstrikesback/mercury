import cPickle
import os
import sys

import pantheon
from fabric.api import local

def get_build_data():
    """ Return a dict of build data, messages, warnings, errors.

    """
    data = dict()
    data['build_messages'] = list()
    data['build_warnings'] = list()
    data['build_error'] = ''

    build_data_path = '/etc/pantheon/build_data.txt'
    if os.path.isfile(build_data_path):
        with open(build_data_path, 'r') as f:
            while True:
                try:
                    # Read a single item from the file, and get response type.
                    var = cPickle.load(f)
                    response_type = var.keys()[0]
                    # If it is a message, add to list of messages.
                    if response_type == 'build_message':
                        data['build_messages'].append(var.get('build_message'))
                    # If it is a warning, add to list of warnings.
                    elif response_type == 'build_warning':
                        data['build_warnings'].append(var.get('build_warning'))
                    # Can only have one error (fatal). 
                    elif response_type == 'build_error':
                        data['build_error'] = var.get('build_error')
                    # General build data. Update data dict.
                    else:
                        data.update(var)
                except (EOFError, ImportError, IndexError):
                    break
    return data

def write_build_data(response_type, data):
    """ Write pickled data to workspace for jenkins job_name.

    response_type: The type of response data (generally a job name). May not
               be the same as the initiating jenkins job (multiple responses).
    data: Info to be written to file for later retrieval in Atlas postback.

    """
    build_data_path = '/etc/pantheon/build_data.txt'

    with open(build_data_path, 'a') as f:
        cPickle.dump({response_type:data}, f)

def build_message(message):
    """Writes messages to file that will be sent back to Atlas,
    message: string. Message to send back to Atlas/user.

    """
    write_build_data('build_message', message)

def build_warning(message):
    """Writes warning to file that will be parsed at the end of a build.
    data: string. Warning message to be written to build_data file.

    Warnings will cause the Jenkins build to be marked as unstable.

    """
    write_build_data('build_warning', message)

def build_error(message):
    """Writes error message to file. Sets build as unstable. Exists Job.
    message: string. Error message that will be written to build_data file.

    """
    write_build_data('build_error', message)
    print "\nEncountered a build error. Error message:"
    print message + '\n\n'
    sys.exit(0)

