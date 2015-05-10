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

import copy

from cloudify.decorators import operation
from cloudify import ctx

from worker_installer import init_worker_installer
from worker_installer import env
from worker_installer import utils


@operation
@init_worker_installer
def install(cloudify_agent, **_):

    def _create_agent_env_path():
        local_env_path = utils.env_to_file(cloudify_agent.get('env', {}))
        return ctx.runner.put_file(local_env_path)

    def _create_execution_env(_agent_env_path):

        return {

            # these are variables that must be calculated on the manager
            env.CLOUDIFY_MANAGER_IP: cloudify_agent['manager_ip'],
            env.CLOUDIFY_DAEMON_QUEUE: cloudify_agent['queue'],
            env.CLOUDIFY_DAEMON_NAME: cloudify_agent['name'],

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
            env.CLOUDIFY_DAEMON_PROCESS_MANAGEMENT:
                cloudify_agent['process_management']['name'],

            env.CLOUDIFY_DAEMON_EXTRA_ENV: _agent_env_path
        }

    agent_env_path = _create_agent_env_path()
    execution_env = _create_execution_env(agent_env_path)
    execution_env = utils.purge_none_values(execution_env)
    execution_env = utils.stringify_values(execution_env)

    ctx.logger.debug('Cloudify Agent will be created using the following '
                     'environment: {0}'.format(execution_env))

    if 'source_url' in cloudify_agent:
        _download_from_source(cloudify_agent)
    else:
        _download_from_package(cloudify_agent)

    ctx.logger.info('Creating Agent...')
    ctx.agent.run('daemon create', execution_env=execution_env)
    ctx.logger.info('Configuring Agent...')

    custom_options = _create_custom_process_management_options(cloudify_agent)
    ctx.agent.run('daemon configure {0}'.format(custom_options),
                  execution_env=execution_env)
    _set_runtime_properties(cloudify_agent)


@operation
@init_worker_installer
def start(cloudify_agent, **_):
    ctx.logger.info('Starting Agent...')
    ctx.agent.sudo('daemon start --name={0}'.format(cloudify_agent['name']))


@operation
@init_worker_installer
def restart(cloudify_agent, **_):
    ctx.logger.info('Restarting Agent...')
    ctx.agent.sudo('daemon restart --name={0}'.format(cloudify_agent['name']))


@operation
@init_worker_installer
def stop(cloudify_agent, **_):
    ctx.logger.info('Stopping Agent...')
    ctx.agent.sudo('daemon stop --name={0}'.format(cloudify_agent['name']))


@operation
@init_worker_installer
def uninstall(cloudify_agent, **_):
    ctx.logger.info('Deleting Agent...')
    ctx.agent.sudo('daemon delete --name={0}'.format(cloudify_agent['name']))


def _set_runtime_properties(cloudify_agent):
    ctx.instance.runtime_properties['cloudify_agent'] = cloudify_agent


def _create_custom_process_management_options(cloudify_agent):
    options = []
    process_management = copy.deepcopy(cloudify_agent['process_management'])

    # remove the name key because it is actually passed separately via an
    # environment variable
    process_management.pop('name')
    for key, value in process_management.iteritems():
        options.append('--{0}={1}'.format(key, value))
    return ' '.join(options)


def _download_from_source(cloudify_agent):

    get_pip_url = 'https://bootstrap.pypa.io/get-pip.py'

    requirements = cloudify_agent.get('requirements')
    source_url = cloudify_agent['source_url']

    ctx.logger.info('Downloading get-pip.py from {0}'.format(get_pip_url))
    get_pip = ctx.runner.download(get_pip_url)

    if cloudify_agent['windows']:
        elevated = ctx.runner.run
    else:
        elevated = ctx.runner.sudo

    ctx.logger.info('Installing pip...')
    elevated('python {0}'.format(get_pip))
    ctx.logger.info('Installing virtualenv...')
    elevated('pip install virtualenv')

    env_path = '{0}/env'.format(cloudify_agent['agent_dir'])
    ctx.logger.info('Creating virtualenv at {0}'.format(env_path))
    ctx.runner.run('virtualenv {0}'.format(env_path))
    if requirements:
        ctx.logger.info('Installing requirements file: {0}'
                        .format(requirements))
        ctx.runner.run('{0}/bin/pip install -r {1}'
                       .format(env_path, requirements))
    ctx.logger.info('Installing Cloudify Agent from {0}...'
                    .format(source_url))
    ctx.runner.run('{0}/bin/pip install {1}'
                   .format(env_path, source_url))


def _download_from_package(cloudify_agent):
    ctx.logger.info('Downloading Agent package from {0}'
                    .format(cloudify_agent['package_url']))
    package_path = ctx.runner.download(
        url=cloudify_agent['package_url'])
    ctx.logger.info('Extracting Agent package...')
    ctx.runner.extract(archive=package_path,
                       destination=cloudify_agent['agent_dir'])

    ctx.logger.info('Auto-correcting agent virtualenv')
    ctx.agent.run('configure --relocated-env')
