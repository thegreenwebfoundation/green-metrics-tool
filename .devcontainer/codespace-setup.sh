#!/bin/bash
set -euo pipefail

sudo apt update && \
sudo apt upgrade -y && \
sudo apt install -y curl git make gcc python3 python3-pip python3-venv

# we have to rename this makefile as it doesn't compile in Codespaces
if [ -f /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile ]; then
    mv /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile.bak
fi

/workspaces/green-metrics-tool/install_linux.sh -p testpw -a http://api.green-coding.internal:9142 -m http://metrics.green-coding.internal:9143 -t