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
import socket
import os
import tempfile

from cloudify.utils import setup_default_logger
from cloudify import exceptions

from worker_installer.fabric_runner import FabricCommandRunner
from worker_installer.fabric_runner import FabricCommandExecutionException
from worker_installer.tests import utils
from worker_installer.tests.file_server import FileServer
from worker_installer import tests
from worker_installer.tests.file_server import PORT


class TestDefaults(testtools.TestCase):

    def test_default_port(self):
        runner = FabricCommandRunner(validate_connection=False,
                              user='user',
                              host='host',
                              password='password')
        self.assertTrue(runner.port, 22)


class TestValidations(testtools.TestCase):

    def test_no_host(self):
        try:
            FabricCommandRunner(validate_connection=False,
                         user='user',
                         password='password')
            self.fail('Expected error due to missing host')
        except exceptions.NonRecoverableError as e:
            self.assertIn('Missing host', str(e))

    def test_no_user(self):
        try:
            FabricCommandRunner(validate_connection=False,
                         host='host',
                         password='password')
            self.fail('Expected error due to missing user')
        except exceptions.NonRecoverableError as e:
            self.assertIn('Missing user', str(e))

    def test_key_and_password(self):
        try:
            FabricCommandRunner(validate_connection=False,
                         host='host',
                         user='user',
                         password='password',
                         key='key')
            self.fail('Expected error due to specifying key and password')
        except exceptions.NonRecoverableError as e:
            self.assertIn('Cannot specify both key and password', str(e))

    def test_no_key_no_password(self):
        try:
            FabricCommandRunner(validate_connection=False,
                         host='host',
                         user='password')
            self.fail('Expected error due to not specifying key and password')
        except exceptions.NonRecoverableError as e:
            self.assertIn('Must specify either key or password', str(e))


class FabricRunnerTest(testtools.TestCase):

    """
    Base class for fabric runner tests. Tests that are common for
    both remote fabric runner and local fabric runner should be placed
    here.
    """

    fs = None

    @classmethod
    def setUpClass(cls):
        super(FabricRunnerTest, cls).setUpClass()
        cls.logger = setup_default_logger(cls.__name__)
        details = utils.launch_docker(image_name='rastasheep/ubuntu-sshd',
                                      container_name='test_fabric_runner')
        cls.runner = FabricCommandRunner(logger=cls.logger,
                                  validate_connection=False,
                                  **details)
        resources = os.path.join(
            os.path.dirname(tests.__file__),
            'resources'
        )
        cls.fs = FileServer(resources)
        cls.fs.start()

    @classmethod
    def tearDownClass(cls):
        super(FabricRunnerTest, cls).tearDownClass()
        utils.destroy_docker('test_fabric_runner')
        cls.fs.stop()

    def test_ping(self):
        self.runner.ping()

    def test_run_bad_command(self):
        try:
            self.runner.run('bad')
        except FabricCommandExecutionException as e:
            self.assertIn('not found', e.error)

    def test_run_good_command(self):
        response = self.runner.run('echo hello')
        self.assertIn('hello', response.output)

    def test_run_script(self):

        script = tempfile.mktemp()

        with open(script, 'w') as f:
            f.write('#!/bin/bash')
            f.write(os.linesep)
            f.write('echo hello')
            f.write(os.linesep)

        response = self.runner.run_script(script=script)
        self.assertEqual('hello', response.output)

    def test_exists(self):
        response = self.runner.exists('~/.bashrc')
        self.assertTrue(response)

    def test_get_non_existing_file(self):
        try:
            self.runner.get_file(src='non-exiting')
        except FabricCommandExecutionException as e:
            self.assertIn('not found', e.error)

    def test_put_get_file(self):

        src = tempfile.mktemp()

        with open(src, 'w') as f:
            f.write('test_put_get_file')

        remote_path = self.runner.put_file(src=src)
        local_path = self.runner.get_file(src=remote_path)

        with open(local_path) as f:
            self.assertEqual('test_put_get_file',
                             f.read())

    def test_download(self):

        ip = utils.get_ip_address('wlan0')
        output_path = self.runner.download(
            url='http://{0}:{1}/archive.tar.gz'.format(ip, PORT))
        self.assertTrue(self.runner.exists(path=output_path))

    def test_untar(self):
        temp_folder = self.runner.mkdtemp()
        ip = utils.get_ip_address('wlan0')
        output_path = self.runner.download(
            url='http://{0}:{1}/archive.tar.gz'.format(ip, PORT))
        self.runner.untar(archive=output_path, destination=temp_folder)
        self.assertTrue(self.runner.exists(
            os.path.join(temp_folder, 'dsl_parser'))
        )

    def test_machine_distribution(self):
        dist = self.runner.machine_distribution()
        self.assertEqual('Ubuntu', dist[0])
        self.assertEqual('14.04', dist[1])
        self.assertEqual('trusty', dist[2])
