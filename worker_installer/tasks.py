#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from cloudify.decorators import operation
from cloudify import ctx

from worker_installer import init_worker_installer
from worker_installer import env


@operation
@init_worker_installer
def install(cloudify_agent, **_):

    def _create_env():

        return {

            # these are variables that must be calculated on the manager
            env.CLOUDIFY_MANAGER_IP: cloudify_agent['manager_ip'],
            env.CLOUDIFY_DAEMON_QUEUE: cloudify_agent['queue'],
            env.CLOUDIFY_DAEMON_NAME: cloudify_agent['name'],
            env.CLOUDIFY_AGENT_HOST: cloudify_agent['host'],
            env.CLOUDIFY_DAEMON_WORKDIR: cloudify_agent['workdir'],

            # these are variables that have default values that will be set
            # by the agent on the remote host if not set here
            env.CLOUDIFY_DAEMON_USER: cloudify_agent.get('user'),
            env.CLOUDIFY_BROKER_IP: cloudify_agent.get('broker_ip'),
            env.CLOUDIFY_BROKER_PORT: cloudify_agent.get('broker_port'),
            env.CLOUDIFY_BROKER_URL: cloudify_agent.get('broker_url'),
            env.CLOUDIFY_DAEMON_GROUP: cloudify_agent.get('group'),
            env.CLOUDIFY_MANAGER_PORT: cloudify_agent.get('manager_port'),
            env.CLOUDIFY_DAEMON_MAX_WORKERS: cloudify_agent.get(
                'max_workers'),
            env.CLOUDIFY_DAEMON_MIN_WORKERS: cloudify_agent.get(
                'min_workers'),
            env.CLOUDIFY_DAEMON_PROCESS_MANAGEMENT: cloudify_agent.get(
                'process_management')
        }

    ctx.logger.info('Downloading Agent package from {0}'
                    .format(cloudify_agent['package_url']))
    package_path = ctx.runner.download(url=cloudify_agent['package_url'])
    ctx.logger.info('Extracting Agent package...')
    ctx.runner.untar(archive=package_path,
                     destination=cloudify_agent['basedir'])

    execution_env = _create_env()

    ctx.logger.info('Creating Agent...')
    ctx.agent.run('daemon create', execution_env=execution_env)


@operation
@init_worker_installer
def start(cloudify_agent, **_):
    ctx.logger.info('Starting Agent...')
    ctx.agent.sudo('start --name={0}'.format(cloudify_agent['name']))


@operation
@init_worker_installer
def restart(cloudify_agent, **_):
    ctx.logger.info('Restarting Agent...')
    ctx.agent.sudo('restart --name={0}'.format(cloudify_agent['name']))


@operation
@init_worker_installer
def stop(cloudify_agent, **_):
    ctx.logger.info('Stopping Agent...')
    ctx.agent.sudo('stop --name={0}'.format(cloudify_agent['name']))


@operation
@init_worker_installer
def uninstall(cloudify_agent, **_):
    ctx.logger.info('Deleting Agent...')
    ctx.agent.sudo('delete --name={0}'.format(cloudify_agent['name']))
