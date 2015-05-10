########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from mock import patch

from cloudify.workflows import local
from cloudify.utils import setup_logger

from system_tests import resources
from cosmo_tester.framework import testenv


import os
os.environ['HANDLER_CONFIGURATION'] = '/home/elip/dev/system-tests-handlers/lab-openstack-eli-handler.yaml'


class AgentInstallerPluginTest(testenv.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger('test_tasks')

    @patch('cloudify.workflows.local._validate_node')
    def test_agent_installer_plugin(self, _):

        self.addCleanup(self.cleanup)

        blueprint_path = resources.get_resource(
            'install-agent-from-source-blueprint/'
            'install-agent-from-source-blueprint.yaml')
        self.logger.info('Initiating local env')

        inputs = {
            'prefix': self._testMethodName,
            'external_network': self.env.external_network_name,
            'os_username': self.env.keystone_username,
            'os_password': self.env.keystone_password,
            'os_tenant_name': self.env.keystone_tenant_name,
            'os_region': self.env.region,
            'os_auth_url': self.env.keystone_url,
            'image_id': self.env.ubuntu_trusty_image_id,
            'flavor': self.env.medium_flavor_id,
            'key_pair_path': '{0}/{1}-keypair.pem'
            .format(self.workdir, self._testMethodName)
        }

        self.local_env = local.init_env(
            blueprint_path=blueprint_path,
            ignored_modules='plugin_installer.tasks',
            inputs=inputs)

        self.local_env.execute('install', task_retries=10)
        self._assert_agent_running()

    def _assert_agent_running(self):
        pass

    def cleanup(self):
        self.local_env.execute(
            'uninstall',
            task_retries=5,
            task_retry_interval=10)
