# pylint: disable=import-error,wrong-import-position,protected-access

import sys
import os

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../..')

from metric_providers.base import BaseMetricProvider


class CpuTimeCgroupSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="cpu_time_cgroup_system",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="us",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )


if __name__ == '__main__':
    import time
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('container_id', help='Please provide the container_id')
    args = parser.parse_args()

    o = CpuTimeCgroupSystemProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling({args.container_id: 'test'})
    time.sleep(2)
    o.stop_profiling()
    print('Done, check ', o._filename)
