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

import unittest
import getpass
import tempfile

from cloudify.workflows import local

from worker_installer.tests import resources
from worker_installer.tests import file_server


class WorkerInstallerLocalTest(unittest.TestCase):

    fs = None

    @classmethod
    def setUpClass(cls):
        cls.resource_base = tempfile.mkdtemp(
            prefix='file-server-resource-base')
        cls.fs = file_server.FileServer(root_path=cls.resource_base)
        cls.fs.start()

    @classmethod
    def tearDownClass(cls):
        cls.fs.stop()

    def test_local_agent(self):
        blueprint_path = resources.get_resource(
            'blueprints/local-agent-blueprint.yaml')
        env = local.init_env(blueprint_path,
                             inputs={'user': getpass.getuser(),
                                     'resource_base': self.resource_base})
        env.execute('install', task_retries=0)
        env.execute('uninstall', task_retries=0)
        self._assert_agent_running()

    def _assert_agent_running(self):
        pass
