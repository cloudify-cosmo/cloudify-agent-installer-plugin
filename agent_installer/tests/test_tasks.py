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

import unittest2 as unittest
import getpass
import os
import tempfile

from mock import patch

from cloudify.workflows import local
from cloudify.utils import setup_logger

from agent_installer.tests import resources
from agent_installer.tests import file_server


class WorkerInstallerLocalTest(unittest.TestCase):

    fs = None

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger('test_tasks')
        cls.resource_base = tempfile.mkdtemp(
            prefix='file-server-resource-base')
        cls.fs = file_server.FileServer(root_path=cls.resource_base)
        cls.fs.start()

    @classmethod
    def tearDownClass(cls):
        cls.fs.stop()

    def setUp(self):
        self.original_dir = os.getcwd()
        tempdir = tempfile.mkdtemp(
            prefix='worker-installer-tasks-tests-')
        self.logger.info('Working directory: {0}'.format(tempdir))
        os.chdir(tempdir)

    def tearDown(self):
        os.chdir(self.original_dir)

    @patch('cloudify.workflows.local._validate_node')
    def test_local_agent_from_package(self, _):
        blueprint_path = resources.get_resource(
            'blueprints/agent-from-package/local-agent-blueprint.yaml')
        self.logger.info('Initiating local env')
        env = local.init_env(blueprint_path,
                             inputs={'user': getpass.getuser(),
                                     'resource_base': self.resource_base},
                             ignored_modules='plugin_installer.tasks')
        env.execute('install', task_retries=0)
        env.execute('uninstall', task_retries=0)
        self._assert_agent_running()

    @patch('cloudify.workflows.local._validate_node')
    def test_local_agent_from_source(self, _):
        blueprint_path = resources.get_resource(
            'blueprints/agent-from-source/local-agent-blueprint.yaml')
        self.logger.info('Initiating local env')
        env = local.init_env(blueprint_path,
                             ignored_modules='plugin_installer.tasks')
        env.execute('install', task_retries=0)
        env.execute('uninstall', task_retries=0)
        self._assert_agent_running()

    def _assert_agent_running(self):
        pass
