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
from functools import wraps

from cloudify import ctx
from cloudify.state import current_ctx
from worker_installer.config import configuration
from worker_installer.runners.fabric_runner import FabricRunner
from worker_installer.runners.local_runner import LocalRunner
from worker_installer.runners.winrm_runner import WinRMRunner


def init_worker_installer(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        cloudify_agent = kwargs.get('cloudify_agent', {})

        # set connection details
        configuration.prepare_connection(cloudify_agent)

        # now we can create the runner and attach it to ctx
        if cloudify_agent['local']:
            runner = LocalRunner(logger=ctx.logger)
        elif cloudify_agent['windows']:
            runner = WinRMRunner(
                host=cloudify_agent['ip'],
                user=cloudify_agent['user'],
                password=cloudify_agent['password'],
                port=cloudify_agent.get('port'),
                protocol=cloudify_agent.get('protocol'),
                uri=cloudify_agent.get('user'),
                logger=ctx.logger)
        else:
            runner = FabricRunner(
                logger=ctx.logger,
                host=cloudify_agent['ip'],
                user=cloudify_agent['user'],
                port=cloudify_agent.get('port'),
                key=cloudify_agent.get('key'),
                password=cloudify_agent.get('password'),
                fabric_env=cloudify_agent.get('fabric_env'))
        setattr(current_ctx.get_ctx(), 'runner', runner)

        configuration.prepare_agent(cloudify_agent)
        agent_runner = AgentCommandRunner(runner, cloudify_agent['agent_dir'])
        setattr(current_ctx.get_ctx(), 'agent', agent_runner)

        kwargs['cloudify_agent'] = cloudify_agent

        try:
            return func(*args, **kwargs)
        finally:
            if isinstance(runner, FabricRunner):
                runner.close()

    return wrapper


class AgentCommandRunner(object):

    """
    class for running cloudify agent commands based on the configuration.
    this class simplifies the agent commands by automatically prefixing the
    correct virtualenv to run commands under.

    """

    def __init__(self,
                 runner,
                 agent_dir):
        self._runner = runner
        bin_path = '{0}/env/bin'.format(agent_dir)
        self._prefix = '{0}/python {0}/cfy-agent'.format(bin_path)

    def run(self, command, execution_env=None):
        response = self._runner.run(
            '{0} {1}'.format(self._prefix, command),
            execution_env=execution_env,
            quiet=False)
        if response.output:
            for line in response.output.split(os.linesep):
                ctx.logger.info(line)

    def sudo(self, command):
        response = self._runner.sudo(
            '{0} {1}'.format(self._prefix, command), quiet=False)
        if response.output:
            for line in response.output.split(os.linesep):
                ctx.logger.info(line)
