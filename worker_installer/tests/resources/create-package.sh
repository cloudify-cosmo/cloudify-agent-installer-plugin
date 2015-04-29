#!/bin/bash

CONFIG=$1

virtualenv /tmp/cloudify-agent-packager-env
source /tmp/cloudify-agent-packager-env/bin/activate

pip install https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/agent-refactoring-project.zip
mkdir -p /tmp/cloudify-agent-packager-work
cd /tmp/cloudify-agent-packager-work
cfy-ap -c ${CONFIG} -f -v
