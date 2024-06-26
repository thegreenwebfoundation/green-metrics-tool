#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import decimal
from io import StringIO

from lib.global_config import GlobalConfig
from lib.db import DB


def generate_csv_line(run_id, metric, detail_name, phase_name, value, value_type, max_value, min_value, unit):
    return f"{run_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{round(max_value) if max_value is not None else ''},{round(min_value) if min_value is not None else ''},{unit},NOW()\n"

def build_and_store_phase_stats(run_id, sci=None):
    config = GlobalConfig().config

    query = """
            SELECT metric, unit, detail_name
            FROM measurements
            WHERE run_id = %s
            GROUP BY metric, unit, detail_name
            ORDER BY metric ASC -- we need this ordering for later, when we read again
            """
    metrics = DB().fetch_all(query, (run_id, ))

    query = """
        SELECT phases
        FROM runs
        WHERE id = %s
        """
    phases = DB().fetch_one(query, (run_id, ))

    csv_buffer = StringIO()

    machine_power_idle = None
    machine_power_runtime = None
    machine_energy_runtime = None

    for idx, phase in enumerate(phases[0]):
        network_io_bytes_total = [] # reset; # we use array here and sum later, because checking for 0 alone not enough

        cpu_utilization_containers = {} # reset
        cpu_utilization_machine = None
        machine_co2_in_ug = None # reset
        network_io_co2_in_ug = None

        select_query = """
            SELECT SUM(value), MAX(value), MIN(value), AVG(value), COUNT(value)
            FROM measurements
            WHERE run_id = %s AND metric = %s AND detail_name = %s AND time > %s and time < %s
        """

        duration = phase['end']-phase['start']
        csv_buffer.write(generate_csv_line(run_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", duration, 'TOTAL', None, None, 'us'))

        # now we go through all metrics in the run and aggregate them
        for (metric, unit, detail_name) in metrics: # unpack
            # -- saved for future if I need lag time query
            #    WITH times as (
            #        SELECT id, value, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
            #        FROM measurements
            #        WHERE run_id = %s AND metric = %s
            #        ORDER BY detail_name ASC, time ASC
            #    ) -- Backlog: if we need derivatives / integrations in the future

            results = DB().fetch_one(select_query,
                (run_id, metric, detail_name, phase['start'], phase['end'], ))

            value_sum = 0
            max_value = 0
            min_value = 0
            avg_value = 0
            value_count = 0

            value_sum, max_value, min_value, avg_value, value_count = results

            # no need to calculate if we have no results to work on
            # This can happen if the phase is too short
            if value_count == 0: continue

            if metric in (
                'lm_sensors_temperature_component',
                'lm_sensors_fan_component',
                'cpu_utilization_procfs_system',
                'cpu_utilization_mach_system',
                'cpu_utilization_cgroup_container',
                'memory_total_cgroup_container',
                'cpu_frequency_sysfs_core',
            ):
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value, 'MEAN', max_value, min_value, unit))

                if metric in ('cpu_utilization_procfs_system', 'cpu_utilization_mach_system'):
                    cpu_utilization_machine = avg_value
                if metric in ('cpu_utilization_cgroup_container', ):
                    cpu_utilization_containers[detail_name] = avg_value

            elif metric == 'network_io_cgroup_container':
                # These metrics are accumulating already. We only need the max here and deliver it as total
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", max_value-min_value, 'TOTAL', None, None, unit))
                # No max here
                # But we need to build the energy
                network_io_bytes_total.append(max_value-min_value)

            elif metric == 'energy_impact_powermetrics_vm':
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value, 'MEAN', max_value, min_value, unit))

            elif "_energy_" in metric and unit == 'mJ':
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, unit))
                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently
                power_avg = (value_sum * 10**6) / duration
                power_max = (max_value * 10**6) / (duration / value_count)
                power_min = (min_value * 10**6) / (duration / value_count)
                csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_avg, 'MEAN', power_max, power_min, 'mW'))

                if metric.endswith('_machine'):
                    machine_co2_in_ug = decimal.Decimal((value_sum / 3_600) * config['sci']['I'])
                    csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_co2_')}", detail_name, f"{idx:03}_{phase['name']}", machine_co2_in_ug, 'TOTAL', None, None, 'ug'))

                    if phase['name'] == '[IDLE]':
                        machine_power_idle = power_avg
                    else:
                        machine_energy_runtime = value_sum
                        machine_power_runtime = power_avg

            else:
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', max_value, min_value, unit))
        # after going through detail metrics, create cumulated ones
        if network_io_bytes_total:
            # build the network energy
            # network via formula: https://www.green-coding.io/co2-formulas/
            # pylint: disable=invalid-name
            network_io_in_kWh = (sum(network_io_bytes_total) / 1_000_000_000) * 0.002651650429449553
            network_io_in_mJ = network_io_in_kWh * 3_600_000_000
            csv_buffer.write(generate_csv_line(run_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_in_mJ, 'TOTAL', None, None, 'mJ'))
            # co2 calculations
            network_io_co2_in_ug = decimal.Decimal(network_io_in_kWh * config['sci']['I'] * 1_000_000)
            csv_buffer.write(generate_csv_line(run_id, 'network_co2_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_co2_in_ug, 'TOTAL', None, None, 'ug'))
        else:
            network_io_co2_in_ug = decimal.Decimal(0)


        duration_in_years = duration / (1_000_000 * 60 * 60 * 24 * 365)
        embodied_carbon_share_g = (duration_in_years / (config['sci']['EL']) ) * config['sci']['TE'] * config['sci']['RS']
        embodied_carbon_share_ug = decimal.Decimal(embodied_carbon_share_g * 1_000_000)
        csv_buffer.write(generate_csv_line(run_id, 'embodied_carbon_share_machine', '[SYSTEM]', f"{idx:03}_{phase['name']}", embodied_carbon_share_ug, 'TOTAL', None, None, 'ug'))

        if phase['name'] == '[RUNTIME]' and machine_co2_in_ug is not None and sci is not None \
                         and sci.get('R', None) is not None and sci['R'] != 0:
            csv_buffer.write(generate_csv_line(run_id, 'software_carbon_intensity_global', '[SYSTEM]', f"{idx:03}_{phase['name']}", (machine_co2_in_ug + embodied_carbon_share_ug + network_io_co2_in_ug) / sci['R'], 'TOTAL', None, None, f"ugCO2e/{sci['R_d']}"))

        if machine_power_idle and cpu_utilization_machine and cpu_utilization_containers:
            surplus_power_runtime = machine_power_runtime - machine_power_idle
            surplus_energy_runtime = machine_energy_runtime - (machine_power_idle * decimal.Decimal(duration / 10**6))
            total_container_utilization = sum(cpu_utilization_containers.values())
            if int(total_container_utilization) == 0:
                continue

            for detail_name, container_utilization in cpu_utilization_containers.items():
                csv_buffer.write(generate_csv_line(run_id, 'psu_energy_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_energy_runtime * (container_utilization / total_container_utilization), 'TOTAL', None, None, 'mJ'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_power_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_power_runtime * (container_utilization / total_container_utilization), 'TOTAL', None, None, 'mW'))


    csv_buffer.seek(0)  # Reset buffer position to the beginning
    DB().copy_from(
        csv_buffer,
        table='phase_stats',
        sep=',',
        columns=('run_id', 'metric', 'detail_name', 'phase', 'value', 'type', 'max_value', 'min_value', 'unit', 'created_at')
    )
    csv_buffer.close()  # Close the buffer


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', help='Run ID', type=str)

    args = parser.parse_args()  # script will exit if type is not present

    build_and_store_phase_stats(args.run_id)
