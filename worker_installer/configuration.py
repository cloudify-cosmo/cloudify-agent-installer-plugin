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

from cloudify import exceptions
from cloudify import ctx
from cloudify import utils


def cloudify_agent_property(agent_property=None,
                            context_attribute=None,
                            mandatory=True):

    if context_attribute is None:
        context_attribute = agent_property

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            invocation = args[0]
            node_properties = ctx.node.properties['cloudify_agent']
            agent_context = ctx.bootstrap_context.cloudify_agent

            # if the property was given in the invocation, use it.
            if agent_property in invocation:
                return

            # if the property is declared on the node, use it
            if agent_property in node_properties:
                invocation[agent_property] = node_properties[agent_property]
                return

            # if the property is inside the bootstrap context, use it
            if hasattr(agent_context, context_attribute):
                invocation[agent_property] = getattr(agent_context,
                                                     context_attribute)
                return

            # apply the function, perhaps it will set this property
            value = function(*args, **kwargs)
            if value is not None:
                invocation[agent_property] = value

            # if there is no value, and the property is mandatory
            if agent_property not in invocation and mandatory:
                inputs_path = '{0}.interfaces.[{1}].inputs.cloudify_agent'\
                    .format(ctx.node.name, ctx.task_name)
                properties_path = '{0}.properties.cloudify_agent'.format(
                    ctx.node.name
                )
                context_path = 'bootstrap_context.cloudify_agent'
                raise exceptions.NonRecoverableError(
                    '{0} was not found in any of '
                    'the following: 1. {1}; 2. {2}; 3. {3}'
                    .format(agent_property,
                            inputs_path,
                            properties_path,
                            context_path)
                )

        return wrapper

    return decorator


def prepare_connection(cloudify_agent):
    _set_user(cloudify_agent)
    _set_key(cloudify_agent)
    _set_password(cloudify_agent)
    _set_port(cloudify_agent)
    _set_host(cloudify_agent)


def prepare_agent(cloudify_agent):
    _set_name(cloudify_agent)
    _set_home_dir(cloudify_agent)
    _set_basedir(cloudify_agent)
    _set_workdir(cloudify_agent)
    _set_min_workers(cloudify_agent)
    _set_max_workers(cloudify_agent)
    _set_queue(cloudify_agent)
    _set_distro(cloudify_agent)
    _set_distro_codename(cloudify_agent)
    _set_package_url(cloudify_agent)
    _set_manager_ip(cloudify_agent)


@cloudify_agent_property(agent_property='port',
                         context_attribute='remote_execution_port')
def _set_port(_):
    pass


@cloudify_agent_property('user')
def _set_user(_):
    pass


@cloudify_agent_property(agent_property='key',
                         context_attribute='agent_key_path',
                         mandatory=False)
def _set_key(_):
    pass


@cloudify_agent_property('password',
                         mandatory=False)
def _set_password(_):
    pass


@cloudify_agent_property('min_workers')
def _set_min_workers(_):
    pass


@cloudify_agent_property('max_workers')
def _set_max_workers(_):
    pass


@cloudify_agent_property('distro')
def _set_distro(_):
    dist = ctx.runner.machine_distribution()
    return dist[0].lower()


@cloudify_agent_property('distro_codename')
def _set_distro_codename(_):
    dist = ctx.runner.machine_distribution()
    return dist[2].lower()


@cloudify_agent_property('package_url')
def _set_package_url(cloudify_agent):
    return '{0}/packages/agents/{1}-{2}-agent.tar.gz'.format(
        utils.get_manager_file_server_url(),
        cloudify_agent['distro'],
        cloudify_agent['distro_codename']
    )


@cloudify_agent_property('host')
def _set_host(_):
    ip = None
    if ctx.node.properties.get('ip'):
        ip = ctx.node.properties['ip']
    if ctx.instance.runtime_properties.get('ip'):
        ip = ctx.instance.runtime_properties['ip']
    return ip


@cloudify_agent_property('name')
def _set_name(cloudify_agent):
    workflows_worker = cloudify_agent.get('workflows_worker', False)
    suffix = '_workflows' if workflows_worker else ''
    name = '{0}{1}'.format(ctx.deployment.id, suffix)
    return name


@cloudify_agent_property('basedir')
def _set_basedir(cloudify_agent):
    return os.path.join(
        cloudify_agent['home_dir'],
        cloudify_agent['name']
    )


@cloudify_agent_property('queue')
def _set_queue(cloudify_agent):
    return cloudify_agent['name']


@cloudify_agent_property('home_dir')
def _set_home_dir(cloudify_agent):
    return ctx.runner.python(
        imports_line='import pwd',
        command='pwd.getpwnam(\'{0}\').pw_dir'
        .format(cloudify_agent['user']))


@cloudify_agent_property('workdir')
def _set_workdir(cloudify_agent):
    return os.path.join(
        cloudify_agent['basedir'],
        'work'
    )


@cloudify_agent_property('manager_ip')
def _set_manager_ip(_):
    return utils.get_manager_ip()
