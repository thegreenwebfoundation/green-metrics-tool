import sys
import os
import uuid
import numpy as np
import scipy.stats
from functools import cache
import faulthandler

faulthandler.enable()  # will catch segfaults and write to STDERR

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../tools')

from db import DB


METRIC_MAPPINGS = {
     'psu_co2_ac_xgboost_machine': {
        'clean_name': 'Machine CO2 (XGBoost)',
        'explanation': 'Machine CO2 calculated by formula via XGBoost estimation',
        'color': 'black',
        'icon': 'exchange alternate'
    },

     'network_energy_formula_global': {
        'clean_name': 'Network Energy',
        'explanation': 'Network Energy calculated by formula',
        'color': 'orange',
        'icon': 'exchange alternate'
    },
     'network_co2_formula_global': {
        'clean_name': 'Network CO2',
        'explanation': 'Network CO2 calculated by formula',
        'color': 'black',
        'icon': 'exchange alternate'
    },
     'lm_sensors_temperature_component': {
        'clean_name': 'CPU Temperature',
        'explanation': 'CPU Temperature as reported by lm_sensors',
        'color': 'grey',
        'icon': 'microchip'
    },
    'lm_sensors_fan_component': {
        'clean_name': 'Fan Speed',
        'explanation': 'Fan speed as reported by lm_sensors',
        'color': 'grey',
        'icon': 'circle'
    },'psu_energy_ac_powerspy2_machine': {
        'clean_name': 'Machine Energy (AC - PowerSpy2)',
        'explanation': 'Full machine energy (AC) as reported by PowerSpy2',
        'color': 'blue',
        'icon': 'battery three quarters'
    },'psu_power_ac_powerspy2_machine': {
        'clean_name': 'Machine Power (AC - PowerSpy2)',
        'explanation': 'Full machine power (AC) as reported by PowerSpy2',
        'color': 'orange',
        'icon': 'power off'
    },'psu_energy_ac_xgboost_machine': {
        'clean_name': 'Machine Energy (AC - XGBoost)',
        'explanation': 'Full machine energy (AC) as estimated by XGBoost model',
        'color': 'blue',
        'icon': 'battery three quarters'
    },'psu_power_ac_xgboost_machine': {
        'clean_name': 'Machine Power (AC - XGBoost)',
        'explanation': 'Full machine power (AC) as estimated by XGBoost model',
        'color': 'orange',
        'icon': 'power off'
    },'psu_energy_ac_ipmi_machine': {
        'clean_name': 'Machine Energy (AC -IPMI)',
        'explanation': 'Full machine energy (AC) as reported by IPMI',
        'color': 'blue',
        'icon': 'battery three quarters'
    },'psu_power_ac_ipmi_machine': {
        'clean_name': 'Machine Power (AC -IPMI)',
        'explanation': 'Full machine power (AC) as reported by IPMI',
        'color': 'orange',
        'icon': 'power off'
    },'psu_energy_dc_picolog_machine': {
        'clean_name': 'Machine Energy (DC - PicoLog)',
        'explanation': 'Full machine energy (AC) as reported by PicoLog HRDL ADC-24',
        'color': 'blue',
        'icon': 'battery three quarters'
    },'psu_power_dc_picolog_machine': {
        'clean_name': 'Machine Power (DC - PicoLog)',
        'explanation': 'Full machine power (AC) as reported by PicoLog HRDL ADC-24',
        'color': 'orange',
        'icon': 'power off'
    },


    'cpu_frequency_sysfs_core': {
        'clean_name': 'CPU Frequency',
        'explanation': 'CPU Frequency per core as reported by sysfs',
        'color': 'grey',
        'icon': 'microchip'
    },
    'ane_power_powermetrics_component': {
        'clean_name': 'ANE Power',
        'explanation': 'Apple Neural Engine',
        'color': 'orange',
        'icon': 'power off'
    },
    'ane_energy_powermetrics_component': {
        'clean_name': 'ANE Energy',
        'explanation': 'Apple Neural Engine',
        'color': 'blue',
        'icon': 'battery three quarters'
    },
    'gpu_power_powermetrics_component': {
        'clean_name': 'GPU Power',
        'explanation': 'Apple M1 GPU / Intel GPU',
        'color': 'orange',
        'icon': 'power off'
    },
    'gpu_energy_powermetrics_component': {
        'clean_name': 'GPU Energy',
        'explanation': 'Apple M1 GPU / Intel GPU',
        'color': 'blue',
        'icon': 'battery three quarters'
    },

    'cores_power_powermetrics_component': {
        'clean_name': 'CPU Power (Cores)',
        'explanation': 'Power of the cores only without GPU, ANE, GPU, DRAM etc.',
        'color': 'orange',
        'icon': 'power off'
    },
    'cores_energy_powermetrics_component': {
        'clean_name': 'CPU Energy (Cores)',
        'explanation': 'Energy of the cores only without GPU, ANE, GPU, DRAM etc.',
        'color': 'blue',
        'icon': 'battery three quarters'
    },
    'cpu_time_powermetrics_vm': {
        'clean_name': 'CPU time',
        'explanation': 'Effective execution time of the CPU for all cores combined',
        'color': 'brown',
        'icon': 'stopwatch'
    },
    'disk_io_bytesread_powermetrics_vm': {
        'clean_name': 'Bytes read (HDD/SDD)',
        'explanation': 'Effective execution time of the CPU for all cores combined',
        'color': 'violet',
        'icon': 'upload'
    },
    'disk_io_byteswritten_powermetrics_vm': {
        'clean_name': 'Bytes written (HDD/SDD)',
        'explanation': 'Effective execution time of the CPU for all cores combined',
        'color': 'violet',
        'icon': 'download'
    },
    'energy_impact_powermetrics_vm': {
        'clean_name': 'Energy impact',
        'explanation': 'macOS proprietary value for relative energy impact on device',
        'color': 'teal',
        'icon': 'cat'
    },
    'cpu_utilization_cgroup_container': {
        'clean_name': 'CPU %',
        'explanation': 'CPU Utilization per container',
        'color': 'yellow',
        'icon': 'microchip'
    },
    'memory_total_cgroup_container': {
        'clean_name': 'Memory Usage',
        'explanation': 'Memory Usage per container',
        'color': 'purple',
        'icon': 'memory'
    },
    'network_io_cgroup_container': {
        'clean_name': 'Network I/O',
        'explanation': 'Network I/O. Details on docs.green-coding.berlin/docs/measuring/metric-providers/network-io-cgroup-container',
        'color': 'olive',
        'icon': 'exchange alternate'
    },
    'cpu_energy_rapl_msr_component': {
        'clean_name': 'CPU Energy (Package)',
        'explanation': 'RAPL based CPU energy of package domain',
        'color': 'blue',
        'icon': 'batter three quarters'
    },
    'cpu_power_rapl_msr_component': {
        'clean_name': 'CPU Power (Package)',
        'explanation': 'Derived RAPL based CPU energy of package domain',
        'color': 'orange',
        'icon': 'power off'
    },
    'cpu_utilization_procfs_system': {
        'clean_name': 'CPU %',
        'explanation': 'CPU Utilization of total system',
        'color': 'purple',
        'icon': 'power off'
    },
    'memory_energy_rapl_msr_component': {
        'clean_name': 'Memory Energy (DRAM)',
        'explanation': 'RAPL based memory energy of DRAM domain',
        'color': 'blue',
        'icon': 'batter three quarters'
    },
    'memory_power_rapl_msr_component': {
        'clean_name': 'Memory Power (DRAM)',
        'explanation': 'Derived RAPL based memory energy of DRAM domain',
        'color': 'orange',
        'icon': 'power off'
    },
}


def rescale_energy_value(value, unit):
    # We only expect values to be mJ for energy!
    if unit != 'mJ':
        raise RuntimeError('Unexpected unit occured for energy rescaling: ', unit)

    energy_rescaled = [value, unit]

    # pylint: disable=multiple-statements
    if value > 1_000_000_000: energy_rescaled = [value/(10**12), 'GJ']
    elif value > 1_000_000_000: energy_rescaled = [value/(10**9), 'MJ']
    elif value > 1_000_000: energy_rescaled = [value/(10**6), 'kJ']
    elif value > 1_000: energy_rescaled = [value/(10**3), 'J']
    elif value < 0.001: energy_rescaled = [value*(10**3), 'nJ']

    return energy_rescaled

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def determine_comparison_case(ids):

    query = '''
            WITH uniques as (
                SELECT b.uri, b.usage_scenario_file, b.machine_id, b.commit_hash FROM phase_stats as a
                LEFT JOIN projects as b ON a.project_id = b.id
                WHERE project_id = ANY(%s::uuid[])
                GROUP BY b.uri, b.usage_scenario_file, b.machine_id, b.commit_hash
            )
            SELECT COUNT(DISTINCT uri ), COUNT(DISTINCT usage_scenario_file), COUNT(DISTINCT machine_id), COUNT(DISTINCT commit_hash ) from uniques
    '''

    data = DB().fetch_one(query, (ids, ))
    if data is None or data == []:
        raise RuntimeError('Could not determine compare case')

    [repos, usage_scenarios, machine_ids, commit_hashes] = data

    # If we have one or more measurement in a phase_stat it will currently just be averaged
    # however, when we allow comparing projects we will get same phase_stats but with different repo etc.
    # these cannot be just averaged. But they have to be split and then compared via t-test
    # For the moment I think it makes sense to restrict to two repositories. Comparing three is too much to handle I believe if we do not want to drill down to one specific metric

    # Currently we support five cases:
    # case = 'Repository' # Case D : RequirementsEngineering Case
    # case = 'Usage Scenario' # Case C_2 : SoftwareDeveloper Case
    # case = 'Machine' # Case C_1 : DataCenter Case
    # case = 'Commit' # Case B: DevOps Case
    # case = 'Repeated Run' # Case A: Blue Angel


    if repos == 2: # diff repos
        if usage_scenarios <= 2: # diff repo, diff usage scenarios. diff usage scenarios are NORMAL for now
            if machine_ids == 2: # diff repo, diff usage scenarios, diff machine_ids
                raise RuntimeError('Different repos & machines not supported')
            elif machine_ids == 1: # diff repo, diff usage scenarios, same machine_ids
                if commit_hashes == 2: # diff repo, diff usage scenarios, same machine_ids, diff commits_hashes
                    # for two repos we expect two different hashes, so this is actually a normal case
                    case = 'Repository' # Case D
                elif commit_hashes == 1: # diff repo, diff usage scenarios, same machine_ids, same commit_hashes
                    raise RuntimeError('Same commit hash for different repos?!?!')
                else:
                    raise RuntimeError('Different repos & multiple commits not supported')
            else:
                raise RuntimeError('3+ Machines and different repos not supported.')
        else:
            raise RuntimeError('2+ Usage scenarios for different repos not supported.')
    elif repos == 1: # same repos
        if usage_scenarios == 2: # same repo, diff usage scenarios
            if machine_ids == 2: # same repo, diff usage scenarios, diff machines
                raise RuntimeError('Different usage scenarios & machines not supported')
            else: # same repo, diff usage scenarios, same machines
                if commit_hashes > 1: # same repo, diff usage scenarios, same machines, diff commit hashes
                    raise RuntimeError('Different usage scenarios & commits not supported')
                else: # same repo, diff usage scenarios, same machines, same commit hashes
                    case = 'Usage Scenario' # Case C_2
        elif usage_scenarios == 1: # same repo, same usage scenario
            if machine_ids == 2: # same repo, same usage scenarios, diff machines
                if commit_hashes > 1: # same repo, same usage scenarios, diff machines, diff commit hashes
                    raise RuntimeError('Different machines & commits not supported')
                else: # same repo, same usage scenarios, diff machines, same commit hashes
                    case = 'Machine' # Case C_1
            elif machine_ids == 1: # same repo, same usage scenarios, same machines
                if commit_hashes > 1: # same repo, same usage scenarios, same machines, diff commit hashes
                    case = 'Commit' # Case B
                else: # same repo, same usage scenarios, same machines, same commit hashes
                    case = 'Repeated Run' # Case A
            else:
                raise RuntimeError('3+ Machines per repo not supported.')
        else:
            raise RuntimeError('3+ Usage scenarios per repo not supported.')

    else:
        # TODO: Metric drilldown has to be implemented at some point ...
        # The functionality I imagine here is, because comparing more than two repos is very complex with
        # multiple t-tests / ANOVA etc. and hard to grasp, only a focus on one metric shall be provided.
        raise RuntimeError('Multiple repos not supported for overview. Please apply metric filter.')

    return case

def get_phase_stats(ids):
    query = """
            SELECT
                a.phase, a.metric, a.detail_name, a.value, a.type, a.max_value, a.unit,
                b.uri, b.machine_id, b.usage_scenario_file, b.commit_hash
            FROM phase_stats as a
            LEFT JOIN projects as b on b.id = a.project_id
            WHERE
                a.project_id = ANY(%s::uuid[])
                AND
                a.metric NOT LIKE '%%_MAX'
            ORDER BY
                a.phase ASC,
                a.metric ASC,
                a.detail_name ASC,
                b.uri ASC,
                b.machine_id ASC,
                b.usage_scenario_file ASC,
                b.commit_hash ASC
            """
    data = DB().fetch_all(query, (ids, ))
    if data is None or data == []:
        raise RuntimeError('Data is empty')
    return data

# TODO: This method needs proper database caching
# Would be interesting to know if in an application server like gunicor @cache
# Will also work for subsequent requests ...?
'''  Object structure
    comparison_case: str
    statistics: dict
                                        // MEAN of the detailed-metric over all repos -> non-sense
                                        // MEAN of the detailed-metric over all usage_scenarios -> debateable
                                        // MEAN of the detailed-metric per machines  -> interesting
                                        // MEAN of the detailed-metric per commits -> debateable

                                        // Case A: No T-Test necessary, as only repetition. STDDEV only important
                                        // Case B: comparison as T-test betweeen every commit ???
                                        // => Technically possible, but we will most likely only have 1 commit.
                                        // => So maybe only compare last commit against all before?
                                        // => Yes, that sounds best! Still
                                        // Case C_1: comparison as T-test betweeen the two machines
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20
                                        // Case C_2: comparison as T-test betweeen the two usage scenarios
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20
                                        // Case D: comparison as T-test betweeen the two repos
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20

                                        // although we can have 2 commits on 2 repos, we do not keep
                                        // track of the multiple commits here as key
                                        // currently the system is limited to compare only two projects until we have
                                        // figured out how big our StdDev is and how many projects we can run per day
                                        // at all (and how many repetitions are needed and possbile time-wise)
                                        repo/usage_scenarios/machine/commit/:
                                            mean: // mean per commit/repo etc.
                                            stddev:
                                            ci:
                                            p_value: // Only case A for last key vs compare to the rest. one-sided t-test
                                            is_significant: // Only case A .... one-sided t-test
                                            values: [] // 1 for stats.html. 1+ for cases
                                            max_values: []


    data: dict -> key: repo/usage_scenarios/machine/commit/
        project_1: dict
        project_2: dict
        ...
        project_x : dict  -> key: phase_name
            [BASELINE]: dict
            [INSTALLATION]: dict
            ....
            [PHASE]: dict -> key: metric_name
                -mean: - // will NOT be implemented. See explanation
                    // mean of the phase for all the metrics and their details
                    // this really only makes sense for all the energy values, and then only for selected ones ...
                    // actually only really helpful if we have multiple metrics that report the same value
                    // this shall NOT be supported
                // we reserve this level for phase-level data
                // atm there is only the data key
                core_energy_powermetrics_component: dict
                ...
                ane_energy_powermetrics_component: dict
                    clean_name: str
                    icon: str
                    ....
                    mean: float
                        // mean of the metric over all details per per repo / usage_scenario etc.
                        // => Interesting for multiple docker containers
                        repo/usage_scenarios/machine/commit/: number
                        repo/usage_scenarios/machine/commit/: number
                        ...
                    stddev: float
                    p-value: float

                    data: dict -> key: detail_name
                        [COMPONENT]: dict
                        [SYSTEM]: dict
                        ...
                        [MACHINE]:
                                mean: float // mean of the metric for this detail for this phase
                                stddev: float
                                ci: float
                                max: float
                                values: list // the actual values
            ...
'''
def get_phase_stats_object(phase_stats, case):

    phase_stats_object = {
        'comparison_case': case,
        'comparison_details': [],
        'statistics': {},
        'data': {}
    }

    for phase_stat in phase_stats:
        [
            phase, metric_name, detail_name, value, metric_type, max_value, unit,
            repo, machine_id, usage_scenario_file, commit_hash
        ] = phase_stat # unpack

        phase = phase.split('_', maxsplit=1)[1] # remove the 001_ prepended stuff again, which is only for ordering

        if case == 'Repository':
            key = repo # Case D : RequirementsEngineering Case
        elif case == 'Usage Scenario':
            key = usage_scenario_file # Case C_2 : SoftwareDeveloper Case
        elif case == 'Machine':
            key = machine_id # Case C_1 : DataCenter Case
        else:
            key = commit_hash # No comparison case / Case A: Blue Angel / Case B: DevOps Case

        if key not in phase_stats_object['data']:
            phase_stats_object['data'][key] = {}
            phase_stats_object['comparison_details'].append(key)


        if phase not in phase_stats_object['data'][key]: phase_stats_object['data'][key][phase] = {}

        if metric_name not in phase_stats_object['data'][key][phase]:
            phase_stats_object['data'][key][phase][metric_name] = {
                'clean_name': METRIC_MAPPINGS[metric_name]['clean_name'],
                'explanation': METRIC_MAPPINGS[metric_name]['explanation'],
                'type': metric_type,
                'unit': unit,
                'color': METRIC_MAPPINGS[metric_name]['color'],
                'icon': METRIC_MAPPINGS[metric_name]['icon'],
                #'mean': None, # currently no use for that
                #'stddev': None,  # currently no use for that
                #'ci': None,  # currently no use for that
                #'p_value': None,  # currently no use for that
                #'is_significant': None,  # currently no use for that
                'data': {},
            }

        if detail_name not in phase_stats_object['data'][key][phase][metric_name]['data']:
            phase_stats_object['data'][key][phase][metric_name]['data'][detail_name] = {
                'name': detail_name,
                'mean': None, # this is the mean over all repetitions of the detail_name
                'max': max_value,
                'stddev': None,
                'ci': None,
                'p_value': None, # only for the last key the list compare to the rest. one-sided t-test
                'is_significant': None, # only for the last key the list compare to the rest. one-sided t-test
                'values': [],
            }

        phase_stats_object['data'][key][phase][metric_name]['data'][detail_name]['values'].append(value)

    return phase_stats_object


'''
    Here we need to traverse the object again and calculate all the averages we need
    This could have also been done while constructing the object through checking when a change
    in phase / detail_name etc. occurs.
'''
def add_phase_stats_statistics(phase_stats_object):

    ## build per comparison key stats
    for key in phase_stats_object['data']:
        for phase, phase_data in phase_stats_object['data'][key].items():
            for metric_name, metric in phase_data.items():
                for detail_name, detail in metric['data'].items():
                    # if a detail has multiple values we calculate a std.dev and the one-sided t-test for the last value

                    detail['mean'] = detail['values'][0] # default. might be overridden

                    if len(detail['values']) > 1:
                        t_stat = get_t_stat(len(detail['values']))

                        # JSON does not recognize the numpy data types. Sometimes int64 is returned
                        detail['mean'] = float(np.mean(detail['values']))
                        detail['stddev'] = float(np.std(detail['values']))
                        detail['max'] = float(np.max(detail['values']))
                        detail['ci'] = detail['stddev']*t_stat

                        if len(detail['values']) > 2:
                            data_c = detail['values'].copy()
                            pop_mean = data_c.pop()
                            _, p_value = scipy.stats.ttest_1samp(data_c, pop_mean)
                            if not np.isnan(p_value):
                                detail['p_value'] = p_value
                                if detail['p_value'] > 0.05:
                                    detail['is_significant'] = False
                                else:
                                    detail['is_significant'] = True


    ## builds stats between the keys
    if len(phase_stats_object['comparison_details']) == 2:
        # since we currently allow only two comparisons we hardcode this here
        key1 = phase_stats_object['comparison_details'][0]
        key2 = phase_stats_object['comparison_details'][1]

        # we need to traverse only one branch of the tree like structure, as we only need to compare matching metrics
        for phase, phase_data in phase_stats_object['data'][key1].items():
            phase_stats_object['statistics'][phase] = {}
            for metric_name, metric in phase_data.items():
                phase_stats_object['statistics'][phase][metric_name] = {}
                for detail_name, detail in metric['data'].items():
                    phase_stats_object['statistics'][phase][metric_name][detail_name] = {}
                    try: # other metric or phase might not be present
                        detail2 = phase_stats_object['data'][key2][phase][metric_name]['data'][detail_name]
                    except KeyError:
                        continue
                    statistics_node = phase_stats_object['statistics'][phase][metric_name][detail_name]

                    # Welch-Test because we cannot assume equal variances
                    _, p_value = scipy.stats.ttest_ind(detail['values'], detail2['values'], equal_var=False) #

                    if np.isnan(p_value):
                        statistics_node['p_value'] = None
                        statistics_node['is_significant'] = None
                    else:
                        statistics_node['p_value'] = p_value
                        if statistics_node['p_value'] > 0.05:
                            statistics_node['is_significant'] = False
                        else:
                            statistics_node['is_significant'] = True

    return phase_stats_object



@cache
def get_t_stat(length):
    #alpha = .05
    if length <= 1: return None
    dof = length-1
    t_crit = np.abs(scipy.stats.t.ppf((.05)/2,dof)) # for two sided!
    return t_crit/np.sqrt(length)
