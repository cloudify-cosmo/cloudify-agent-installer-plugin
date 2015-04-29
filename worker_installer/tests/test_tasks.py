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

import os
import testtools

from cloudify.workflows import local as local_workflow
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.utils import setup_default_logger

from worker_installer import tests
from worker_installer.tests import utils
from worker_installer.tests.file_server import PORT


class WorkerInstallerLocalTest(testtools.TestCase):

    def setUp(self):
        super(WorkerInstallerLocalTest, self).setUp()
        blueprint_path = os.path.join(
            os.path.dirname(tests.__file__),
            'resources',
            'blueprints',
            'local-agent-blueprint.yaml'
        )

        self.logger = setup_default_logger('worker_installer.tests')
        self.env = local_workflow.init_env(
            blueprint_path,
            name=self._testMethodName)

    def tearDown(self):
        super(WorkerInstallerLocalTest, self).tearDown()
        self.env.execute('uninstall', task_retries=0)

    def test_agent(self):
        self.env.execute('install', task_retries=0)


class WorkerInstallerVagrantTest(testtools.TestCase):

    def setUp(self):
        super(WorkerInstallerVagrantTest, self).setUp()
        self.blueprint_path = os.path.join(
            os.path.dirname(tests.__file__),
            'resources',
            'blueprints',
            'docker-host-agent-blueprint.yaml'
        )
        self.logger = setup_default_logger('worker_installer.tests')

        agent_package_path = utils.create_agent_package(
            'iliapolo/ubuntu_trusty_agent_packager:1.0'
        )

        self.logger.info('Serving...')
        self.fs = utils.serve_agent_package(agent_package_path)
        ip = utils.get_ip_address('docker0')
        os.environ['MANAGEMENT_IP'] = ip
        os.environ['MANAGER_FILE_SERVER_URL'] = \
            'http://{0}:{1}'.format(ip, PORT)

    def tearDown(self):
        super(WorkerInstallerVagrantTest, self).tearDown()
        utils.destroy_docker('ubuntu_trusty_sshd')
        self.fs.stop()

    def test_ubuntu_trusty(self):
        self.env = local_workflow.init_env(
            self.blueprint_path,
            name=self._testMethodName,
            inputs={
                'image_name': 'rastasheep/ubuntu-sshd',
                'container_name': 'ubuntu_trusty_sshd'
            }
        )
        self.env.execute('install',
                         task_retries=0)

    def test_ubuntu_precise(self):
        local_workflow.init_env(
            self.blueprint_path,
            name=self._testMethodName,
            inputs={'machine_name': 'local_ubuntu_precise'})
        self.env.execute('install', task_retries=0)

    def test_centos64(self):
        local_workflow.init_env(
            self.blueprint_path,
            name=self._testMethodName,
            inputs={'machine_name': 'local_centos_64'})
        self.env.execute('install', task_retries=0)


@operation
def create_docker(image_name, container_name, **_):
    host_details = utils.launch_docker(image_name, container_name)
    ctx.instance.runtime_properties['password'] = host_details['password']
    ctx.instance.runtime_properties['ip'] = host_details['host']


@operation
def delete_docker(image_name, **_):
    utils.destroy_docker(image_name)
