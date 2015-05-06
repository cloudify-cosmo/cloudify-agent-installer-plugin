#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import tempfile
import os


def env_to_file(env_variables, destination_path=None):

    """

    :param env_variables: environment variables
    :type env_variables: dict

    :param destination_path: destination path of a file where the
    environment variables will be stored. the stored variables will be a
    bash script you can then source.
    :type destination_path: str

    :return: path to the file containing the env variables
    :rtype `str`
    """

    if not destination_path:
        destination_path = tempfile.mkstemp(suffix='env')[1]

    with open(destination_path, 'w') as f:
        f.write('#!/bin/bash')
        f.write(os.linesep)
        f.write(os.linesep)
        for key, value in env_variables.iteritems():
            f.write('export {0}={1}'.format(key, value))
            f.write(os.linesep)
        f.write(os.linesep)

    return destination_path


def stringify_values(dictionary):

    for key, value in dictionary.iteritems():
        if isinstance(value, dict):
            stringify_values(value)
        else:
            dictionary[key] = str(value)