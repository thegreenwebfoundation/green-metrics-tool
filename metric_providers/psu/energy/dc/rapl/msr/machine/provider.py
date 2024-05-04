import os

from metric_providers.base import BaseMetricProvider

class PsuEnergyDcRaplMsrMachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='psu_energy_dc_rapl_msr_machine',
            metrics={'time': int, 'value': int, 'psys_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._extra_switches = ['-p']

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        call_string = f"{self._current_dir}/{self._metric_provider_executable}"
        super().check_system(check_command=[f"{call_string}", '-c', '-p'])
