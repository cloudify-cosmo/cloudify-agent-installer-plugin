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
import getpass
import pwd
import os
import platform
from mock import patch, MagicMock

from cloudify.context import BootstrapContext

from worker_installer.configuration import cloudify_agent_property
from worker_installer.configuration import prepare_agent
from worker_installer.configuration import prepare_connection
from worker_installer.fabric_runner import FabricCommandRunner


def mock_context(properties=None,
                 runtime_properties=None,
                 agent_context=None):
    if not properties:
        properties = {}
    if 'cloudify_agent' not in properties:
        properties['cloudify_agent'] = {}
    if not runtime_properties:
        runtime_properties = {}
    context = MagicMock()
    context.task_name = 'cloudify.interfaces.lifecycle.start'
    context.node.properties = properties
    context.node.name = 'test_node'
    context.instance.runtime_properties = runtime_properties
    context.deployment.id = 'deployment_id'
    if agent_context is None:
        context.bootstrap_context.cloudify_agent = None
    else:
        context.bootstrap_context.cloudify_agent = \
            BootstrapContext.CloudifyAgent(agent_context)
    setattr(context, 'runner', MagicMock())
    return context


class TestCloudifyAgentProperty(testtools.TestCase):

    @patch('worker_installer.configuration.ctx',
           mock_context())
    def test_in_invocation_before(self):

        @cloudify_agent_property('prop')
        def prop(_):
            pass

        cloudify_agent = {'prop': 'value'}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['prop'], 'value')

    @patch('worker_installer.configuration.ctx',
           mock_context())
    def test_in_invocation_after(self):

        @cloudify_agent_property('prop')
        def prop(_):
            _['prop'] = 'value'

        cloudify_agent = {}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['prop'], 'value')

    @patch('worker_installer.configuration.ctx',
           mock_context(properties={'cloudify_agent': {'prop': 'value'}}))
    def test_in_properties(self):

        @cloudify_agent_property('prop')
        def prop(_):
            pass

        cloudify_agent = {}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['prop'], 'value')

    @patch('worker_installer.configuration.ctx',
           mock_context(agent_context={'user': 'value'}))
    def test_in_agent_context(self):

        @cloudify_agent_property('user')
        def prop(_):
            pass

        cloudify_agent = {}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['user'], 'value')

    @patch('worker_installer.configuration.ctx',
           mock_context(properties={'cloudify_agent': {'prop': 'value'}}))
    def test_invocation_overrides_properties(self):

        @cloudify_agent_property('prop')
        def prop(_):
            pass

        cloudify_agent = {'prop': 'value-overridden'}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['prop'], 'value-overridden')

    @patch('worker_installer.configuration.ctx',
           mock_context(agent_context={'prop': 'value'}))
    def test_invocation_overrides_context(self):

        @cloudify_agent_property('prop')
        def prop(_):
            pass

        cloudify_agent = {'prop': 'value-overridden'}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['prop'], 'value-overridden')

    @patch('worker_installer.configuration.ctx',
           mock_context(properties={'cloudify_agent': {'prop': 'value-overridden'}},
                        agent_context={'prop': 'value'}))
    def test_properties_override_context(self):

        @cloudify_agent_property('prop')
        def prop(_):
            pass

        cloudify_agent = {}
        prop(cloudify_agent)

        self.assertEqual(cloudify_agent['prop'], 'value-overridden')


class TestConfiguration(testtools.TestCase):

    def setUp(self):
        super(TestConfiguration, self).setUp()
        os.environ['MANAGER_FILE_SERVER_URL'] = 'localhost'
        os.environ['MANAGEMENT_IP'] = 'localhost'

    @patch('worker_installer.configuration.ctx',
           mock_context(
               properties={
                   'ip': '127.0.0.1'
               },
               agent_context={
                   'user': 'test_user',
                   'agent_key_path': 'key',
                   'remote_execution_port': 22
               }
           ))
    def test_prepare_connection(self):
        cloudify_agent = {}
        prepare_connection(cloudify_agent)
        expected = {
            'user': 'test_user',
            'key': 'key',
            'port': 22,
            'host': '127.0.0.1'
        }
        self.assertEqual(expected, cloudify_agent)

    @patch('worker_installer.configuration.ctx',
           mock_context(
               runtime_properties={
                   'ip': '127.0.0.1'
               },
               agent_context={
                   'user': 'test_user',
                   'agent_key_path': 'key',
                   'remote_execution_port': 22
               }
           ))
    def test_prepare_connection_ip_in_runtime(self):
        cloudify_agent = {}
        prepare_connection(cloudify_agent)
        expected = {
            'user': 'test_user',
            'key': 'key',
            'port': 22,
            'host': '127.0.0.1'
        }
        self.assertEqual(expected, cloudify_agent)

    @patch('worker_installer.configuration.ctx',
           mock_context(
               agent_context={
                   'min_workers': 0,
                   'max_workers': 5
               },
               properties={
                   'cloudify_agent': {
                       'distro': 'distro',
                       'distro_codename': 'distro_codename',
                       'workdir': 'workdir',
                       'home_dir': 'homedir',
                       'basedir': 'basedir'
                   }
               }))
    def test_prepare_agent(self):
        user = getpass.getuser()
        cloudify_agent = {'user': user}
        prepare_agent(cloudify_agent)
        expected = {
            'distro': 'distro',
            'distro_codename': 'distro_codename',
            'basedir': 'basedir',
            'workdir': 'workdir',
            'name': 'deployment_id',
            'manager_ip': 'localhost',
            'home_dir': 'homedir',
            'queue': 'deployment_id',
            'max_workers': 5,
            'user': user,
            'min_workers': 0,
            'package_url': 'localhost/packages/agents/'
                           'distro-distro_codename-agent.tar.gz'
        }
        self.assertEqual(expected, cloudify_agent)
