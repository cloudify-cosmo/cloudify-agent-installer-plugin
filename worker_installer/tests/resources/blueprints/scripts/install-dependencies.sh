#!/bin/bash

agent_packager_source=$(ctx properties agent_packager_source)
virtualenv_directory=$(ctx properties virtualenv_directory)

source ${virtualenv_directory}/bin/activate
pip install ${agent_packager_source}
