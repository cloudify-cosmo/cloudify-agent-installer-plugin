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
import platform
import os
import shutil

from cloudify import utils
from cloudify.exceptions import CommandExecutionException
from worker_installer import exceptions

###############################################################
# this runner is an extension to the regular command runner
# for the purpose of using it in the worker installer logic.
# it adds the necessary methods
###############################################################


class LocalRunner(utils.LocalCommandRunner):

    def extract(self, archive, destination, strip=1):
        if not os.path.exists(destination):
            self.run('mkdir -p {0}'.format(destination))
        return self.run('tar xzvf {0} --strip={1} -C {2}'
                        .format(archive, strip, destination))

    def download(self, url, output_path=None):
        if output_path is None:
            output_path = tempfile.mkstemp()

        try:
            self.logger.info('Locating wget on the host machine')
            self.run('which wget')
            command = 'wget -T 30 {0} -O {1}'.format(url, output_path)
        except CommandExecutionException:
            try:
                self.logger.info('Locating curl on the host machine')
                self.run('which curl')
                command = 'curl {0} -O {1}'.format(url, output_path)
            except CommandExecutionException:
                raise exceptions.WorkerInstallerConfigurationError(
                    'Cannot find neither wget nor curl'
                    .format(url))
        self.run(command)
        return output_path

    @staticmethod
    def put_file(src, dst=None):
        if dst is None:
            dst = tempfile.mkstemp()[1]
        shutil.copy(src, dst)

    @staticmethod
    def machine_distribution():
        return platform.dist()
