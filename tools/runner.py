#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json
import os
import signal
import time
import traceback
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
from import_stats import import_stats # local file import
from save_notes import save_notes # local file import
from setup_functions import get_db_connection, get_config

# TODO:
# - Exception Logic is not really readable. Better encapsulate docker calls and fetch exception there
# - MAke function for arg reading and checking it's presence. More readable than el.get and exception and bottom
# - No cleanup is currently done if exception fails. System is in unclean state
# - No checks for possible command injections are done at the moment

def end_error(*errors):
    log_error(*errors)
    exit(2)

def log_error(*errors):
    print("Error: ", *errors)
    traceback.print_exc()
    # TODO: log to file

config = get_config()
conn = get_db_connection(config)

parser = argparse.ArgumentParser()
parser.add_argument("mode", help="Select the operation mode. Select `manual` to supply a directory or url on the command line. Or select `cron` to process database queue. For database mode the config.yml file will be read", choices=['manual', 'cron'])
parser.add_argument("--url", type=str, help="The url to download the repository with the usage_scenario.json from. Will only be read in manual mode.")
parser.add_argument("--name", type=str, help="A name which will be stored to the database to discern this run from others. Will only be read in manual mode.")
parser.add_argument("--folder", type=str, help="The folder that contains your usage scenario as local path. Will only be read in manual mode.")

args = parser.parse_args() # script will exit if url is not present

if(args.folder is not None and args.url is not None):
        print('Please supply only either --folder or --url\n')
        parser.print_help()
        exit(2)

if args.mode == 'manual' :
    if(args.folder is None and args.url is None):
        print('In manual mode please supply --folder as folder path or --url as URI\n')
        parser.print_help()
        exit(2)

    if(args.name is None):
        print('In manual mode please supply --name\n')
        parser.print_help()
        exit(2)

    folder = args.folder
    url = args.url
    name = args.name

    cur = conn.cursor()
    cur.execute('INSERT INTO "projects" ("name","url","email","crawled","last_crawl","created_at") \
                VALUES \
                (%s,%s,\'manual\',TRUE,NOW(),NOW()) RETURNING id;', (name,url or folder))
    conn.commit()
    project_id = cur.fetchone()[0]

    cur.close()

elif args.mode == 'cron':

    cur = conn.cursor()
    cur.execute("SELECT id,url,email FROM projects WHERE crawled = False ORDER BY created_at ASC LIMIT 1")
    data = cur.fetchone()

    if(data is None or data == []):
        print("No job to process. Exiting")
        exit(1)

    project_id = data[0]
    url = data[1]
    email = data[2]
    cur.close()

    # set to crawled = 1, so we don't error loop
    cur = conn.cursor()
    cur.execute("UPDATE projects SET crawled = True WHERE id = %s", (project_id,))
    conn.commit()
    cur.close()

else:
    raise Exception('Unknown mode: ', args.mode)


containers = []
networks = []
pids_to_kill = []

try:
    # always remove the folder, cause -v directory binding always creates it
    # no check cause might fail when directory might be missing due to manual delete
    ps = subprocess.run(["rm", "-R", "/tmp/green-metrics-tool/repo"])

    if url is not None :
        subprocess.run(["git", "clone", url, "/tmp/green-metrics-tool/repo"], check=True, capture_output=True, encoding='UTF-8') # always name target-dir repo according to spec
        folder = '/tmp/green-metrics-tool/repo'

    with open(folder+'/usage_scenario.json') as fp:
        obj = json.load(fp)

    print("Having Usage Scenario ", obj['name'])
    print("From: ", obj['author'])
    print("Version ", obj['version'], "\n")

    ps = subprocess.run(["uname", "-s"], check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
    output = ps.stdout.strip().lower()

    if obj.get('architecture') is not None and output != obj['architecture']:
        raise Exception("Specified architecture does not match system architecture: system (%s) != specified (%s)", output, obj['architecture'])

    for el in obj['setup']:
        if el['type'] == 'container':
            containers.append(el['name'])
            container_name = el['name']

            print("Resetting container")
            subprocess.run(['docker', 'stop', container_name]) # often not running. so no check=true
            subprocess.run(['docker', 'rm', container_name]) # often not running. so no check=true

            print("Creating container")
            # We are attaching the -it option here to keep STDIN open and a terminal attached.
            # This helps to keep an excecutable-only container open, which would otherwise exit
            # This MAY break in the future, as some docker CLI implementation do not allow this and require
            # the command args to be passed on run only
            docker_run_string = ['docker', 'run', '-it', '-d', '--name', container_name, '-v', f'{folder}:/tmp/repo:ro']

            if 'env' in el:
                import re
                for docker_env_var in el['env']:
                    if re.search("^[A-Z_]+$", docker_env_var[0]) is None:
                        raise Exception(f"Docker container setup env var key had wrong format. Only ^[A-Z_]+$ allowed: {docker_env_var[0]}")
                    if re.search("^[a-zA-Z_]+[a-zA-Z0-9_]*$", docker_env_var[1]) is None:
                        raise Exception(f"Docker container setup env var value had wrong format. Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {docker_env_var[1]}")

                    docker_run_string.append('-e')
                    docker_run_string.append(f"{docker_env_var[0]}={docker_env_var[1]}")


            if 'portmapping' in el:
                docker_run_string.append('-p')
                docker_run_string.append(el['portmapping'])

            if 'network' in el:
                docker_run_string.append('--net')
                docker_run_string.append(el['network'])

            docker_run_string.append(el['identifier'])

            print(f"Running docker run with: {docker_run_string}")

            ps = subprocess.run(
                docker_run_string,
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding="UTF-8"
            )
            print("Stdout:", ps.stdout)

            if "setup-commands" not in el.keys(): continue # setup commands are optional
            print("Running commands")
            for cmd in el['setup-commands']:
                print("Running command: docker exec ", cmd)
                ps = subprocess.run(
                    ['docker', 'exec', container_name, *cmd.split()],
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding="UTF-8"
                )
                print("Stdout:", ps.stdout)
        elif el['type'] == 'network':
            print("Creating network: ", el['name'])
            subprocess.run(['docker', 'network', 'rm', el['name']]) # remove first if present to not get error
            subprocess.run(['docker', 'network', 'create', el['name']])
            networks.append(el['name'])
        elif el['type'] == 'Dockerfile':
            raise NotImplementedError("Green Metrics Tool can currently not consume Dockerfiles. This will be a premium feature, as it creates a lot of server usage and thus slows down Tests per Minute for our server.")
        elif el['type'] == 'Docker-Compose':
            raise NotImplementedError("Green Metrics Tool will not support that, because we wont support all features from docker compose, like for instance volumes and binding arbitrary directories")
        else:
            raise Exception("Unknown type detected in setup: ", el.get('type', None))

    # --- setup finished

    # start the measurement

    print("Starting measurement provider docker stats")
    ps = subprocess.run(["rm", "-R", "/tmp/green-metrics-tool/docker_stats.log"]) # no check cause file might be missing
    stats_process = subprocess.Popen(
        ["docker stats --no-trunc --format '{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.NetIO}}' " + ' '.join(containers) + "  > /tmp/green-metrics-tool/docker_stats.log &"],
        shell=True,
        preexec_fn=os.setsid,
        encoding="UTF-8"
    )

    pids_to_kill.append(stats_process.pid)

    notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

    print("Pre-idling containers")
    time.sleep(5) # 5 seconds buffer at the start to idle container

    print("Current known containers: ", containers)

    # run the flows
    for el in obj['flow']:
        print("Running flow: ", el['name'])
        for inner_el in el['commands']:

            if inner_el['type'] == 'console':
                print("Console command", inner_el['command'], "on container", el['container'])

                docker_exec_command = ['docker', 'exec']


                if inner_el.get('detach', None) == True :
                    print("Detaching")
                    docker_exec_command.append('-d')

                docker_exec_command.append(el['container'])
                docker_exec_command.extend( inner_el['command'].split(' ') )

                ps = subprocess.Popen(
                    " ".join(docker_exec_command),
                    shell=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding="UTF-8",
                    preexec_fn=os.setsid
                )

                docker_exec_stderr = ps.stderr.read()
                if docker_exec_stderr != '':
                    raise Exception('Docker exec returned an error: ', docker_exec_stderr)

                if inner_el.get('detach', None) == True :
                    pids_to_kill.append(ps.pid)

                print("Output of command ", inner_el['command'], "\n", ps.stdout.read())
            else:
                raise Exception('Unknown command type in flows: ', inner_el['type'])

            if "note" in inner_el: notes.append({"note" : inner_el['note'], 'container_name' : el['container'], "timestamp": time.time_ns()})

    print("Re-idling containers")
    time.sleep(5) # 5 seconds buffer at the end to idle container

    for pid in pids_to_kill:
        print("Killing: ", pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass # process may have already ended

    print("Parsing stats")
    import_stats(conn, project_id, "/tmp/green-metrics-tool/docker_stats.log")
    save_notes(conn, project_id, notes)

    if args.mode == 'manual':
        print(f"Please access your report with the ID: {project_id}")
    else:
        from send_report_email import send_report_email # local file import
        send_report_email(config, email, project_id)

except FileNotFoundError as e:
    log_error("Docker command failed.", e)
except subprocess.CalledProcessError as e:
    log_error("Docker command failed")
    log_error("Stdout:", e.stdout)
    log_error("Stderr:", e.stderr)
except KeyError as e:
    log_error("Was expecting a value inside the JSON file, but value was missing: ", e)
except BaseException as e:
    log_error("Base exception occured: ", e)
finally:
    for container_name in containers:
        subprocess.run(['docker', 'stop', container_name])
        subprocess.run(['docker', 'rm', container_name])

    for network_name in networks:
        subprocess.run(['docker', 'network', 'rm', network_name])

    ps = subprocess.run(["rm", "-R", "/tmp/green-metrics-tool/repo"])
    ps = subprocess.run(["rm", "-R", "/tmp/green-metrics-tool/docker_stats.log"])

    for pid in pids_to_kill:
        print("Killing: ", pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass # process may have already ended

    exit(2)


