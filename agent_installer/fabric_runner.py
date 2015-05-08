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
import platform
import shutil

import fabric.network
from fabric import api as fabric_api
from fabric.context_managers import settings
from fabric.context_managers import hide
from fabric.context_managers import shell_env
from fabric.contrib.files import exists

from cloudify.utils import LocalCommandRunner
from cloudify.utils import CommandExecutionResponse
from cloudify.exceptions import CommandExecutionException
from cloudify.exceptions import CommandExecutionError
from cloudify.utils import setup_logger

from agent_installer import exceptions

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
                 validate_connection=True,
                 local=False):

        # logger
        self.logger = logger or setup_logger('fabric_runner')

        # silence paramiko
        logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

        if local:
            self.local = True
            self.local_runner = LocalCommandRunner(logger)
        else:
            self.local = False
            # connection details
            self.port = port or DEFAULT_REMOTE_EXECUTION_PORT
            self.password = password
            self.user = user
            self.host = host
            self.key = key

            # fabric environment
            self.env = self._set_env()

            self._validate_ssh_config()
            if validate_connection:
                self.logger.debug('Validating connection...')
                self.ping()
                self.logger.debug('Connected successfully')

    def _validate_ssh_config(self):
        if not self.host:
            raise exceptions.WorkerInstallerConfigurationError('Missing host')
        if not self.user:
            raise exceptions.WorkerInstallerConfigurationError('Missing user')
        if self.password and self.key:
            raise exceptions.WorkerInstallerConfigurationError(
                'Cannot specify both key and password')
        if not self.password and not self.key:
            raise exceptions.WorkerInstallerConfigurationError(
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

    def run(self, command, execution_env=None, quiet=True):

        """
        Execute a command.

        :param command: The command to execute.
        :type command: str
        :param execution_env: environment variables to be applied before
                              running the command
        :type execution_env: dict
        :param quiet: run the command silently
        :type quiet: bool

        :return: a response object containing information
                 about the execution
        :rtype: worker_installer.fabric_runner.FabricCommandExecutionResponse
        :rtype: cloudify.utils.LocalCommandExecutionResponse
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        if execution_env is None:
            execution_env = {}

        if self.local:
            return self.local_runner.run(
                command=command,
                quiet=quiet,
                execution_env=execution_env
            )

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

    def sudo(self, command, quiet=False):

        """
        Execute a command under sudo.

        :param command: The command to execute.
        :type command: str

        :return: a response object containing information
                 about the execution
        :rtype: worker_installer.fabric_runner.FabricCommandExecutionResponse
        :rtype: cloudify.utils.LocalCommandExecutionResponse
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        if self.local:
            return self.local_runner.sudo(command)
        return self.run('sudo {0}'.format(command),
                        quiet=quiet)

    def run_script(self, script, args=None, quiet=True):

        """
        Execute a script.

        :param script: The path to the script to execute.
        :type script: str
        :param args: arguments to the script
        :type args: bytearray
        :param quiet: run the command silently
        :type quiet: bool


        :return: a response object containing information
                 about the execution
        :rtype: worker_installer.fabric_runner.FabricCommandExecutionResponse
        :rtype: cloudify.utils.LocalCommandExecutionResponse
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        ########################################################
        # local case is handled internally in the run function #
        ########################################################

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
        :type path: str

        :return: true if the path exists, false otherwise
        :rtype boolean
        """

        if self.local:
            return os.path.exists(path)
        with settings(**self.env):
            return exists(path)

    def put_file(self, src, dst=None, sudo=False):

        """
        Copies a file from the src path to the dst path.
        if case the runner is in a remote mode, the `dst` is a path on the
        remote host, and fabric.put method will be used. in case the runner
        is in local mode, both paths are local paths, and a regular copy is
        executed.

        :param src: Path to a local file.
        :type src: str
        :param dst: The remote path the file will copied to.
        :type dst: str
        :param sudo: indicates that this operation
                     will require sudo permissions
        :type sudo: bool

        :return: the destination path
        :rtype: str
        """

        if not dst:
            basename = os.path.basename(src)
            tempdir = self.mkdtemp()
            dst = os.path.join(tempdir, basename)

        if self.local:
            self.logger.debug('Copying {0} to {1}'.format(src, dst))
            shutil.copy(src=src, dst=dst)
        else:
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

        """
        Copies a file from the src path to the dst path.
        if case the runner is in a remote mode, the `src` is a path on the
        remote host, and fabric.get method will be used. in case the runner
        is in local mode, both paths are local paths, and a regular copy is
        executed.

        :param src: Path to a local file.
        :type src: str
        :param dst: The remote path the file will copied to.
        :type dst: str

        :return: the destination path
        :rtype: str
        """

        if not dst:
            basename = os.path.basename(src)
            tempdir = tempfile.mkdtemp()
            dst = os.path.join(tempdir, basename)

        if self.local:
            shutil.copy(src=src, dst=dst)
        else:
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

        """
        Un-tars an archive. internally this will use the 'tar' command line,
        so any archive supported by it is ok.

        :param archive: path to the archive.
        :type archive: str
        :param destination: destination directory
        :type destination: str
        :param strip: the strip count.
        :type strip: int

        :return: a response object containing information
                 about the execution
        :rtype: worker_installer.fabric_runner.FabricCommandExecutionResponse
        :rtype: cloudify.utils.LocalCommandExecutionResponse
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        ########################################################
        # local case is handled internally in the run function #
        # and in the exists function                           #
        ########################################################

        if not self.exists(destination):
            self.run('mkdir -p {0}'.format(destination))
        return self.run('tar xzvf {0} --strip={1} -C {2}'
                        .format(archive, strip, destination))

    def ping(self):

        """
        Tests that the connection is working.

        :return: a response object containing information
                 about the execution
        :rtype: worker_installer.fabric_runner.FabricCommandExecutionResponse
        :rtype: cloudify.utils.LocalCommandExecutionResponse
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        ########################################################
        # local case is handled internally in the run function #
        ########################################################

        return self.run('echo')

    def mktemp(self, create=True, directory=False):

        """
        Creates a temporary path.

        :param create: actually create the file or just construct the path
        :type create: bool
        :param directory: path should be a directory or not.
        :type directory: bool

        :return: the temporary path
        :rtype: str
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        ########################################################
        # local case is handled internally in the run function #
        ########################################################

        flags = []
        if not create:
            flags.append('-u')
        if directory:
            flags.append('-d')
        return self.run('mktemp {0}'
                        .format(' '.join(flags))).output.rstrip()

    def mkdtemp(self, create=True):

        """
        Creates a temporary directory path.

        :param create: actually create the file or just construct the path
        :type create: bool

        :return: the temporary path
        :rtype: str
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        ########################################################
        # local case is handled internally in the mktemp       #
        # function                                             #
        ########################################################

        return self.mktemp(create=create, directory=True)

    def download(self, url, output_path=None):

        """
        Downloads the contents of the url.
        Following heuristic will be applied:

            1. Try downloading with 'wget' command
            2. if failed, try downloading with 'curl' command
            3. if failed, raise a NonRecoverableError

        :param url: URL to the resource.
        :type url: str
        :param output_path: Path where the resource will be downloaded to.
                            If not specified, a temporary file will be used.

        :return: the output path.
        :rtype: str
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        ########################################################
        # local case is handled internally in the run function #
        ########################################################

        if output_path is None:
            output_path = self.mktemp()

        try:
            self.logger.debug('Locating wget on the host machine')
            self.run('which wget')
            command = 'wget -T 30 {0} -O {1}'.format(url, output_path)
        except CommandExecutionResponse:
            try:
                self.logger.debug('Locating curl on the host machine')
                self.run('which curl')
                command = 'curl {0} -O {1}'.format(url, output_path)
            except CommandExecutionResponse:
                raise exceptions.WorkerInstallerConfigurationError(
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
        :type imports_line: str
        :param command: The python command to run.
        :type command: str

        :return: the string representation of the return value of
                 the python command
        :rtype: str
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException
        """

        start = '###CLOUDIFYCOMMANDOPEN'
        end = 'CLOUDIFYCOMMANDCLOSE###'

        ########################################################
        # local case is handled internally in the run function #
        ########################################################

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
        Retrieves the distribution information of the host.

        :return: dictionary of the platform distribution as returned from
        'platform.dist()'

        :rtype: dict
        :raise: worker_installer.fabric_runner.FabricCommandExecutionException
        :raise: cloudify.exceptions.LocalCommandExecutionException

        """

        if self.local:
            return platform.dist()
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


class FabricCommandExecutionError(CommandExecutionError):

    """
    Indicates a failure occurred while trying to execute the command.

    """

    pass


class FabricCommandExecutionException(CommandExecutionException):

    """
    Indicates the command was executed but a failure occurred.

    """

    pass


class FabricCommandExecutionResponse(CommandExecutionResponse):

    """
    Wrapper for indicating the command was originated with fabric api.
    """

    pass
