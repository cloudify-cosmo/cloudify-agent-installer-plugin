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


import time
import os
import jinja2

from cloudify import amqp_client
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify.celery import celery as celery_client
from cloudify import manager
from cloudify import utils

from worker_installer import init_worker_installer
from worker_installer.utils import is_on_management_worker
from worker_installer.utils import download_resource_on_host


PLUGIN_INSTALLER_PLUGIN_PATH = 'plugin_installer.tasks'
AGENT_INSTALLER_PLUGIN_PATH = 'worker_installer.tasks'
WINDOWS_AGENT_INSTALLER_PLUGIN_PATH = 'windows_agent_installer.tasks'
WINDOWS_PLUGIN_INSTALLER_PLUGIN_PATH = 'windows_plugin_installer.tasks'
SCRIPT_PLUGIN_PATH = 'script_runner.tasks'
DEFAULT_WORKFLOWS_PLUGIN_PATH = 'cloudify.plugins.workflows'
CELERY_INCLUDES_LIST = [
    AGENT_INSTALLER_PLUGIN_PATH, PLUGIN_INSTALLER_PLUGIN_PATH,
    WINDOWS_AGENT_INSTALLER_PLUGIN_PATH, WINDOWS_PLUGIN_INSTALLER_PLUGIN_PATH,
    SCRIPT_PLUGIN_PATH, DEFAULT_WORKFLOWS_PLUGIN_PATH
]

DEFAULT_AGENT_RESOURCES = {
    'celery_config_path':
    '/packages/templates/{0}-celeryd-cloudify.conf.template',
    'celery_init_path':
    '/packages/templates/{0}-celeryd-cloudify.init.template',
    'agent_package_path':
    '/packages/agents/{0}-{1}-agent.tar.gz',
    'disable_requiretty_script_path':
    '/packages/scripts/{0}-agent-disable-requiretty.sh'
}


def get_agent_resource_url(ctx, agent_config, resource):
    """returns an agent's resource url

    The resource will be looked for in the agent's properties.
    If it isn't found, it will look for it in the default location.
    """
    if agent_config.get(resource):
        origin = utils.get_manager_file_server_blueprints_root_url() + \
            '/' + ctx.blueprint.id + '/' + agent_config[resource]
    else:
        resource_path = DEFAULT_AGENT_RESOURCES.get(resource)
        if not resource_path:
            raise NonRecoverableError('no such resource: {0}'.format(resource))
        if resource == 'agent_package_path':
            origin = utils.get_manager_file_server_url() + \
                resource_path.format(agent_config['distro'],
                                     agent_config['distro_codename'])
        else:
            origin = utils.get_manager_file_server_url() + \
                resource_path.format(agent_config['distro'])

    ctx.logger.debug('resource origin: {0}'.format(origin))
    return origin


def get_agent_resource_local_path(ctx, agent_config, resource):
    """returns an agent's resource path
    The resource will be looked for in the agent's properties.
    If it isn't found, it will look for it in the default location.
    """
    if agent_config.get(resource):
        origin = agent_config[resource]
    else:
        resource_path = DEFAULT_AGENT_RESOURCES.get(resource)
        if not resource_path:
            raise NonRecoverableError('no such resource: {0}'.format(resource))
        if resource == 'agent_package_path':
            origin = resource_path.format(agent_config['distro'],
                                          agent_config['distro_codename'])
        else:
            origin = resource_path.format(agent_config['distro'])
    ctx.logger.debug('resource origin: {0}'.format(origin))
    return origin


def get_celery_includes_list():
    return CELERY_INCLUDES_LIST


@operation
@init_worker_installer
def install(ctx, runner, agent_config, **kwargs):
    agent_package_url = get_agent_resource_url(
        ctx, agent_config, 'agent_package_path')

    ctx.logger.debug("Pinging agent installer target")
    runner.ping()

    ctx.logger.info(
        'Installing cloudify agent {0}. '
        'Connection details --> {1}'
        .format(agent_config['name'],
                connection_details(agent_config)))

    if worker_exists(runner, agent_config):
        ctx.logger.info("Worker for deployment {0} "
                        "is already installed. nothing to do."
                        .format(ctx.deployment.id))
        return

    if agent_config.get('delete_amqp_queues'):
        _delete_amqp_queues(agent_config['name'])

    ctx.logger.debug(
        'Installing celery worker [cloudify_agent={0}]'.format(agent_config))
    runner.run('mkdir -p {0}'.format(agent_config['base_dir']))

    ctx.logger.debug(
        'Downloading agent package from: {0}'.format(agent_package_url))
    download_resource_on_host(
        ctx.logger, runner, agent_package_url, '{0}/{1}'.format(
            agent_config['base_dir'], 'agent.tar.gz'))

    ctx.logger.debug('extracting agent package on host')
    runner.run(
        'tar xzvf {0}/agent.tar.gz --strip=2 -C {1}'.format(
            agent_config['base_dir'], agent_config['base_dir']))

    ctx.logger.debug('configuring virtualenv')
    for link in ['archives', 'bin', 'include', 'lib']:
        link_path = '{0}/env/local/{1}'.format(agent_config['base_dir'], link)
        try:
            runner.run('unlink {0}'.format(link_path))
            runner.run('ln -s {0}/env/{1} {2}'.format(
                agent_config['base_dir'], link, link_path))

        except Exception as e:
            ctx.logger.warn('Error processing link: {0} [error={1}] - '
                            'ignoring..'.format(link_path, str(e)))

    create_celery_configuration(
        ctx, runner, agent_config, manager.get_resource)

    runner.run('sudo chmod +x {0}'.format(agent_config['init_file']))

    # This is for fixing virtualenv included in package paths
    runner.run("sed -i '1 s|.*/bin/python.*$|#!{0}/env/bin/python|g' "
               "{0}/env/bin/*".format(agent_config['base_dir']))

    # Remove downloaded agent package
    runner.run('rm {0}/agent.tar.gz'.format(agent_config['base_dir']))

    # Disable requiretty
    if agent_config['disable_requiretty']:
        disable_requiretty_script_url = get_agent_resource_url(
            ctx, agent_config, 'disable_requiretty_script_path')
        ctx.logger.debug("Removing requiretty in sudoers file")
        disable_requiretty_script = '{0}/disable-requiretty.sh'.format(
            agent_config['base_dir'])

        download_resource_on_host(
            ctx.logger, runner, disable_requiretty_script_url,
            disable_requiretty_script)

        runner.run('chmod +x {0}'.format(disable_requiretty_script))

        runner.run('sudo {0}'.format(disable_requiretty_script))


@operation
@init_worker_installer
def uninstall(ctx, runner, agent_config, **kwargs):
    ctx.logger.info(
        'Uninstalling cloudify agent {0}. '
        'Connection details --> {1}'
        .format(agent_config['name'],
                connection_details(agent_config)))

    ctx.logger.debug(
        'Uninstalling celery worker [cloudify_agent={0}]'.format(agent_config))

    files_to_delete = [
        agent_config['init_file'], agent_config['config_file']
    ]
    folders_to_delete = [agent_config['base_dir']]
    delete_files_if_exist(ctx, agent_config, runner, files_to_delete)
    delete_folders_if_exist(ctx, agent_config, runner, folders_to_delete)


def delete_files_if_exist(ctx, agent_config, runner, files):
    missing_files = []
    for file_to_delete in files:
        if runner.exists(file_to_delete):
            runner.run("sudo rm {0}".format(file_to_delete))
        else:
            missing_files.append(file_to_delete)
    if missing_files:
        ctx.logger.debug(
            "Could not find files {0} while trying to uninstall worker {1}"
            .format(missing_files, agent_config['name']))


def delete_folders_if_exist(ctx, agent_config, runner, folders):
    missing_folders = []
    for folder_to_delete in folders:
        if runner.exists(folder_to_delete):
            runner.run('sudo rm -rf {0}'.format(folder_to_delete))
        else:
            missing_folders.append(folder_to_delete)
    if missing_folders:
        ctx.logger.debug(
            'Could not find folders {0} while trying to uninstall worker {1}'
            .format(missing_folders, agent_config['name']))


@operation
@init_worker_installer
def stop(ctx, runner, agent_config, **kwargs):
    ctx.logger.info(
        'Stopping cloudify agent {0}. '
        'Connection details --> {1}'
        .format(agent_config['name'],
                connection_details(agent_config)))

    if runner.exists(agent_config['init_file']):
        runner.run(
            "sudo service celeryd-{0} stop".format(agent_config["name"]))
    else:
        ctx.logger.debug(
            "Could not find any workers with name {0}. nothing to do."
            .format(agent_config["name"]))


@operation
@init_worker_installer
def start(ctx, runner, agent_config, **kwargs):
    ctx.logger.info(
        'Starting cloudify agent {0}. '
        'Connection details --> {1}'
        .format(agent_config['name'],
                connection_details(agent_config)))

    runner.run("sudo service celeryd-{0} start".format(agent_config["name"]))

    _wait_for_started(runner, agent_config)


@operation
@init_worker_installer
def restart(ctx, runner, agent_config, **kwargs):
    ctx.logger.info(
        'Restarting cloudify agent {0}. '
        'Connection details --> {1}'
        .format(agent_config['name'],
                connection_details(agent_config)))

    restart_celery_worker(runner, agent_config)


def get_agent_ip(ctx, agent_config):
    if is_on_management_worker(ctx):
        return utils.get_manager_ip()
    return agent_config['host']


def create_celery_configuration(ctx, runner, agent_config, resource_loader):
    create_celery_includes_file(ctx, runner, agent_config)
    loader = jinja2.FunctionLoader(resource_loader)
    env = jinja2.Environment(loader=loader)
    config_template_path = get_agent_resource_local_path(
        ctx, agent_config, 'celery_config_path')
    config_template = env.get_template(config_template_path)
    config_template_values = {
        'includes_file_path': agent_config['includes_file'],
        'celery_base_dir': agent_config['celery_base_dir'],
        'worker_modifier': agent_config['name'],
        'management_ip': utils.get_manager_ip(),
        'broker_ip': utils.get_manager_ip(),
        'agent_ip': get_agent_ip(ctx, agent_config),
        'celery_user': agent_config['user'],
        'celery_group': agent_config['user'],
        'worker_autoscale': '{0},{1}'.format(agent_config['max_workers'],
                                             agent_config['min_workers'])
    }

    ctx.logger.debug(
        'Populating celery config jinja2 template with the following '
        'values: {0}'.format(config_template_values))

    config = config_template.render(config_template_values)
    init_template_path = get_agent_resource_local_path(
        ctx, agent_config, 'celery_init_path')
    init_template = env.get_template(init_template_path)
    init_template_values = {
        'celery_base_dir': agent_config['celery_base_dir'],
        'worker_modifier': agent_config['name']
    }

    ctx.logger.debug(
        'Populating celery init.d jinja2 template with the following '
        'values: {0}'.format(init_template_values))

    init = init_template.render(init_template_values)

    ctx.logger.debug(
        'Creating celery config and init files [cloudify_agent={0}]'.format(
            agent_config))

    runner.put(agent_config['config_file'], config, use_sudo=True)
    runner.put(agent_config['init_file'], init, use_sudo=True)


def create_celery_includes_file(ctx, runner, agent_config):
    # build initial includes
    includes_list = get_celery_includes_list()
    runner.put(agent_config['includes_file'], 'INCLUDES={0}\n'.format(
        ','.join(includes_list)))

    ctx.logger.debug('Created celery includes file [file=%s, content=%s]',
                     agent_config['includes_file'],
                     includes_list)


def worker_exists(runner, agent_config):
    return runner.exists(agent_config['base_dir'])


def restart_celery_worker(runner, agent_config):
    runner.run("sudo service celeryd-{0} restart".format(
        agent_config['name']))
    _wait_for_started(runner, agent_config)


def _delete_amqp_queues(worker_name):
    # FIXME: this function deletes amqp queues that will be used by worker.
    # The amqp queues used by celery worker are determined by worker name
    # and if there are multiple workers with same name celery gets confused.
    #
    # Currently the worker name is based solely on hostname, so it will be
    # re-used if vm gets re-created by auto-heal.
    # Deleting the queues is a workaround for celery problems this creates.
    # Having unique worker names is probably a better long-term strategy.
    client = amqp_client.create_client()
    try:
        channel = client.connection.channel()

        # celery worker queue
        channel.queue_delete(worker_name)

        # celery management queue
        channel.queue_delete('celery@{0}.celery.pidbox'.format(worker_name))
    finally:
        try:
            client.close()
        except Exception:
            pass


def _verify_no_celery_error(runner, agent_config):
    celery_error_out = os.path.join(
        agent_config['base_dir'], 'work/celery_error.out')

    # this means the celery worker had an uncaught
    #  exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.run('rm {0}'.format(celery_error_out))
        raise NonRecoverableError(
            'Celery worker failed to start:\n{0}'.format(output))


def _wait_for_started(runner, agent_config):
    _verify_no_celery_error(runner, agent_config)
    worker_name = 'celery@{0}'.format(agent_config['name'])
    inspect = celery_client.control.inspect(destination=[worker_name])
    wait_started_timeout = agent_config['wait_started_timeout']
    timeout = time.time() + wait_started_timeout
    interval = agent_config['wait_started_interval']
    while time.time() < timeout:
        stats = (inspect.stats() or {}).get(worker_name)
        if stats:
            return
        time.sleep(interval)
    _verify_no_celery_error(runner, agent_config)
    celery_log_file = os.path.join(
        agent_config['base_dir'], 'work/celery.log')
    if os.path.exists(celery_log_file):
        with open(celery_log_file, 'r') as f:
            ctx.logger.error(f.read())
    raise NonRecoverableError('Failed starting agent. waited for {0} seconds.'
                              .format(wait_started_timeout))


def connection_details(cloudify_agent):

    details = {
        'user': cloudify_agent['user']
    }
    if 'host' in cloudify_agent:
        details['host'] = cloudify_agent['host']
    if 'key' in cloudify_agent:
        details['key'] = cloudify_agent['key']
    if 'password' in cloudify_agent:
        details['password'] = cloudify_agent['password']

    return details
