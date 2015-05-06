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

import shutil
import tempfile
import os
import json
import socket
import fcntl
import struct

from cloudify.utils import LocalCommandRunner

from worker_installer.fabric_runner import FabricCommandRunner
from worker_installer import tests
from worker_installer.tests.file_server import FileServer


def launch_docker(image_name, container_name):
    runner = LocalCommandRunner()
    runner.run('docker run -d -P --name {0} {1}'
               .format(container_name, image_name))
    inspect = runner.run('docker inspect {0}'
                         .format(container_name)).output
    inspect = json.loads(inspect)
    ip_address = inspect[0]['NetworkSettings']['IPAddress']

    return {
        'user': 'root',
        'password': 'root',
        'host': ip_address
    }


def destroy_docker(container_name):
    runner = LocalCommandRunner()
    runner.run('docker stop {0}'.format(container_name))
    runner.run('docker rm {0}'.format(container_name))


def create_agent_package():

    script = os.path.join(
        os.path.dirname(tests.__file__),
        'resources',
        'create-package.sh'
    )
    config = os.path.join(
        os.path.dirname(tests.__file__),
        'resources',
        'package.yaml'
    )




    return agent_package_path


def serve_agent_package(agent_package_path):
    tempdir = tempfile.mkdtemp(prefix='file_server_root')
    agent_package_dir = os.path.join(
        tempdir, 'packages', 'agents'
    )
    os.makedirs(agent_package_dir)

    shutil.copy(src=agent_package_path,
                dst=os.path.join(agent_package_dir,
                                 'ubuntu-trusty-agent.tar.gz'))
    return start_file_server(tempdir)


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,
        struct.pack('256s', ifname[:15])
    )[20:24])


def start_file_server(root):
    process = FileServer(root)
    process.start()
    return process