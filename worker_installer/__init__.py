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

from functools import wraps

from cloudify import ctx
from cloudify import context
from cloudify.state import current_ctx
from cloudify.utils import LocalCommandRunner

from worker_installer.fabric_runner import FabricCommandRunner
from worker_installer import configuration
from worker_installer import utils


def init_worker_installer(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        cloudify_agent = ctx.node.properties['cloudify_agent']

        configuration.prepare_connection(cloudify_agent)
        configuration.prepare_agent(cloudify_agent)

        local = (ctx.type == context.DEPLOYMENT)
        if local:
            runner = LocalCommandRunner(logger=ctx.logger)
        else:
            runner = FabricCommandRunner(
                logger=ctx.logger,
                host=cloudify_agent.get('host'),
                user=cloudify_agent.get('user'),
                key=cloudify_agent.get('key'),
                port=cloudify_agent.get('port'),
                password=cloudify_agent.get('password'))

        agent_runner = AgentCommandRunner(runner, cloudify_agent['basedir'])

        setattr(current_ctx.get_ctx(), 'runner', runner)
        setattr(current_ctx.get_ctx(), 'agent', agent_runner)

        kwargs['cloudify_agent'] = cloudify_agent

        try:
            return func(*args, **kwargs)
        finally:
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
                 cloudify_agent_base_dir):
        self._runner = runner
        bin_path = '{0}/env/bin'.format(cloudify_agent_base_dir)
        self._prefix = ['{0}/python {0}/cloudify-agent'.format(bin_path)]

    def run(self, command, execution_env=None):
        return self._runner.run('{1} {2}'
                                .format(self._prefix,
                                        command),
                                execution_env=execution_env,
                                quiet=False)

    def sudo(self, command):
        return self._runner.sudo('{1} {2}'.format(self._prefix, command),
                                 quiet=False)
