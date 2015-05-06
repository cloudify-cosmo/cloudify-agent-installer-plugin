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

import testtools

from worker_installer import utils


class TestUtils(testtools.TestCase):

    def test_env_to_file(self):
        file_path = utils.env_to_file({'key': 'value', 'key2': 'value2'})
        with open(file_path) as f:
            self.assertEqual(f.read(), """#!/bin/bash

export key2=value2
export key=value

""")

    def test_stringify_values(self):

        env = {
            'key': 'string-value',
            'key2': 5,
            'dict-key': {
                'key3': 10
            }
        }
        utils.stringify_values(dictionary=env)
        self.assertEqual(env['key'], 'string-value')
        self.assertEqual(env['key2'], '5')
        self.assertEqual(env['dict-key']['key3'], '10')

