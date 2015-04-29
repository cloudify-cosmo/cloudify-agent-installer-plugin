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
import json
import logging
import tempfile

import fabric.network
from fabric import api as fabric_api
from fabric.context_managers import settings
from fabric.context_managers import hide
from fabric.context_managers import shell_env
from fabric.contrib.files import exists

from cloudify import exceptions
from cloudify.utils import CommandExecutionResponse
from cloudify.utils import setup_logger

DEFAULT_REMOTE_EXECUTION_PORT = 22

COMMON_ENV = {
    'warn_only': True,
    'connection_attempts': 5,
    'timeout': 10,
    'forward_agent': True,
    'abort_on_prompts': True,
    'keepalive': 0,
    'linewise': False,
    'pool_size': 0,
    'skip_bad_hosts': False,
    'status': False,
    'disable_known_hosts': False,
    'combine_stderr': True,
}


class FabricCommandRunner(object):

    def __init__(self,
                 logger=None,
                 host=None,
                 user=None,
                 key=None,
                 port=None,
                 password=None,
                 validate_connection=True):

        # connection details
        self.port = port or DEFAULT_REMOTE_EXECUTION_PORT
        self.password = password
        self.user = user
        self.host = host
        self.key = key

        # logger
        self.logger = logger or setup_logger('fabric_runner')

        # silence paramiko
        logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

        # fabric environment
        self.env = self._set_env()

        self._validate_config()
        if validate_connection:
            self.test_connectivity()

    def _validate_config(self):
        if not self.host:
            raise exceptions.NonRecoverableError('Missing host')
        if not self.user:
            raise exceptions.NonRecoverableError('Missing user')
        if self.password and self.key:
            raise exceptions.NonRecoverableError(
                'Cannot specify both key and password')
        if not self.password and not self.key:
            raise exceptions.NonRecoverableError(
                'Must specify either key or password')

    def _set_env(self):
        env = {
            'host_string': self.host,
            'port': self.port,
            'user': self.user
        }
        if self.key:
            env['key_filename'] = self.key
        if self.password:
            env['password'] = self.password

        env.update(COMMON_ENV)
        return env

    def test_connectivity(self):
        self.logger.debug('Validating connection...')
        self.ping()
        self.logger.debug('Connected successfully')

    def run(self, command, execution_env=None, quiet=True):

        """
        :param command: The command to execute.

        :rtype FabricCommandExecutionResponse.
        :raise FabricCommandExecutionException.
        """

        if execution_env is None:
            execution_env = {}
        with shell_env(**execution_env):
            with settings(**self.env):
                try:
                    with hide('warnings'):
                        r = fabric_api.run(command, quiet=quiet)
                    if r.return_code != 0:
                        raise FabricCommandExecutionException(
                            command=command,
                            error=r.stdout,
                            code=r.return_code
                        )
                    return FabricCommandExecutionResponse(
                        command=command,
                        output=r.stdout,
                        code=r.return_code
                    )
                except FabricCommandExecutionException:
                    raise
                except BaseException as e:
                    raise FabricCommandExecutionError(
                        command=command,
                        error=str(e)
                    )

    def sudo(self, command):
        return self.run('sudo {0}'.format(command),
                        quiet=False)

    def run_script(self, script, args=None, quiet=True):

        if not args:
            args = []

        remote_path = self.put_file(script)
        self.run('chmod +x {0}'.format(remote_path))
        return self.run('{0} {1}'
                        .format(remote_path,
                                ' '.join(args)),
                        quiet=quiet)

    def exists(self, path):

        """
        Test if the given path exists.

        :param path: The path to tests.

        :rtype boolean
        """

        with settings(**self.env):
            return exists(path)

    def put_file(self, src, dst=None, sudo=False):

        """
        Copies a file fro the local machine to the remote machine.

        :param src: Path to a local file.
        :param dst: The remote path the file will copied to.
        :param sudo:

            indicates that this operation
            will require sudo permissions

        :rtype FabricCommandExecutionResponse.
        :raise FabricCommandExecutionException.
        """

        if not dst:
            basename = os.path.basename(src)
            tempdir = self.mkdtemp()
            dst = os.path.join(tempdir, basename)

        with settings(**self.env):
            with hide('running', 'warnings'):
                r = fabric_api.put(src, dst, use_sudo=sudo)
                if not r.succeeded:
                    raise FabricCommandExecutionException(
                        command='fabric_api.put',
                        error='Failed uploading {0} to {1}'
                        .format(src, dst),
                        code=-1
                    )
        return dst

    def get_file(self, src, dst=None):

        if not dst:
            basename = os.path.basename(src)
            tempdir = tempfile.mkdtemp()
            dst = os.path.join(tempdir, basename)

        with settings(**self.env):
            with hide('running', 'warnings'):
                response = fabric_api.get(src, dst)
            if not response:
                raise FabricCommandExecutionException(
                    command='fabric_api.get',
                    error='Failed downloading {0} to {1}'
                    .format(src, dst),
                    code=-1
                )
        return dst

    def untar(self, archive, destination, strip=1):
        if not self.exists(destination):
            self.run('mkdir -p {0}'.format(destination))
        return self.run('tar xzvf {0} --strip={1} -C {2}'
                        .format(archive, strip, destination))

    def ping(self):

        """
        Tests that the fabric connection is working.

        :rtype FabricCommandExecutionResponse.
        :raise FabricCommandExecutionException.
        """

        return self.run('echo')

    def mktemp(self, create=True, directory=False):
        flags = []
        if not create:
            flags.append('-u')
        if directory:
            flags.append('-d')
        return self.run('mktemp {0}'
                        .format(' '.join(flags))).output

    def mkdtemp(self, create=True):
        return self.mktemp(create=create, directory=True)

    def download(self, url, output_path=None):

        """
        Downloads the contents of the url.
        Following heuristic will be applied:

            1. Try downloading with 'wget' command
            2. if failed, try downloading with 'curl' command
            3. if failed, raise a NonRecoverableError

        :param url: URL to the resource.
        :param output_path:

            Path where the resource will be downloaded to.
            If not specified, a temporary file will be used.

        :rtype FabricCommandExecutionResponse.
        :raise FabricCommandExecutionException.
        :raise NonRecoverableError.
        """

        if output_path is None:
            output_path = self.run('mktemp').output

        try:
            self.logger.debug('Locating wget on the host machine')
            self.run('which wget')
            command = 'wget -T 30 {0} -O {1}'.format(url, output_path)
        except FabricCommandExecutionException:
            try:
                self.logger.debug('Locating curl on the host machine')
                self.run('which curl')
                command = 'curl {0} -O {1}'.format(url, output_path)
            except FabricCommandExecutionException:
                raise exceptions.NonRecoverableError(
                    'Cannot find neither wget nor curl'
                    .format(url))
        self.run(command)
        return output_path

    def python(self, imports_line, command):

        """
        Run a python command and return the output.

        To overcome the situation where additional info is printed
        to stdout when a command execution occurs, a string is
        appended to the output. This will then search for the string
        and the following closing brackets to retrieve the original output.

        :param imports_line: The imports needed for the command.
        :param command: The python command to run.
        """

        start = '###CLOUDIFYCOMMANDOPEN'
        end = 'CLOUDIFYCOMMANDCLOSE###'

        stdout = self.run('python -c "import sys; {0}; '
                          'sys.stdout.write(\'{1}{2}{3}\\n\''
                          '.format({4}))"'
                          .format(imports_line,
                                  start,
                                  '{0}',
                                  end,
                                  command)).output
        result = stdout[stdout.find(start) - 1 + len(end):
                        stdout.find(end)]
        return result

    def machine_distribution(self):

        """
        Retrieves the distribution information of the host using
        platform.dist()

        """

        response = self.python(
            imports_line='import platform, json',
            command='json.dumps(platform.dist())'
        )
        return json.loads(response)

    @staticmethod
    def close():

        """
        Closes all fabric connections.

        """

        fabric.network.disconnect_all()


class FabricCommandExecutionError(exceptions.CommandExecutionError):

    """
    Indicates a failure occurred while trying to execute the command.

    """

    pass


class FabricCommandExecutionException(exceptions.CommandExecutionException):

    """
    Indicates the command was executed but a failure occurred.

    """

    pass


class FabricCommandExecutionResponse(CommandExecutionResponse):

    """
    Wrapper for indicating the command was originated with fabric api.
    """

    pass
