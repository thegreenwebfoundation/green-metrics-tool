#pylint: disable=import-error,wrong-import-position
import sys
import os
import faulthandler
from datetime import datetime

faulthandler.enable()  # will catch segfaults and write to STDERR

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

import email_helpers
import error_helpers
from db import DB
from global_config import GlobalConfig
from phase_stats import build_and_store_phase_stats

def insert_job(job_type, project_id=None, machine_id=None):
    query = """
            INSERT INTO
                jobs (type, failed, running, created_at, project_id, machine_id)
            VALUES
                (%s, FALSE, FALSE, NOW(), %s, %s) RETURNING id;
            """
    params = (job_type, project_id, machine_id,)
    job_id = DB().fetch_one(query, params=params)[0]
    return job_id

# do the first job you get.
def get_job(job_type):
    clear_old_jobs()
    query = """
        SELECT id, type, project_id
        FROM jobs
        WHERE failed=false AND type=%s AND (machine_id IS NULL or machine_id = %s)
        ORDER BY created_at ASC
        LIMIT 1
    """

    return DB().fetch_one(query, (job_type, GlobalConfig().config['machine']['id']))


def delete_job(job_id):
    query = "DELETE FROM jobs WHERE id=%s"
    params = (job_id,)
    DB().query(query, params=params)

# if there is no job of that type running, set this job to running


def check_job_running(job_type, job_id):
    query = "SELECT FROM jobs WHERE running=true AND type=%s"
    params = (job_type,)
    data = DB().fetch_one(query, params=params)
    if data:
        # No email here, only debug
        error_helpers.log_error('Job was still running: ', job_type, job_id)
        sys.exit(1)  # is this the right way to exit here?
    else:
        query_update = "UPDATE jobs SET running=true, last_run=NOW() WHERE id=%s"
        params_update = (job_id,)
        DB().query(query_update, params=params_update)


def clear_old_jobs():
    query = "DELETE FROM jobs WHERE last_run < NOW() - INTERVAL '20 minutes' AND failed=false"
    DB().query(query)


def get_project(project_id):
    data = DB().fetch_one(
        """SELECT p.name, p.uri, p.email, p.branch, p.filename, m.description
           FROM projects as p
           LEFT JOIN machines AS m ON p.machine_id = m.id
           WHERE p.id = %s LIMIT 1""", (project_id, ))

    if data is None or data == []:
        raise RuntimeError(f"couldn't find project w/ id: {project_id}")

    return data


def process_job(job_id, job_type, project_id, skip_system_checks=False, docker_prune=False, full_docker_prune=False):

    try:
        if job_type == 'email':
            _do_email_job(job_id, project_id)
        elif job_type == 'project':
            _do_project_job(job_id, project_id, skip_system_checks, docker_prune, full_docker_prune)
        else:
            raise RuntimeError(
                f"Job w/ id {job_id} has unknown type: {job_type}.")
    except Exception as exc:
        DB().query("UPDATE jobs SET failed=true, running=false WHERE id=%s", params=(job_id,))
        raise exc


# should not be called without enclosing try-except block
def _do_email_job(job_id, project_id):
    check_job_running('email', job_id)

    [name, _, email, _, _, machine] = get_project(project_id)

    config = GlobalConfig().config
    if (config['admin']['notify_admin_for_own_project_ready'] or config['admin']['email'] != email):
        email_helpers.send_report_email(email, project_id, name, machine=machine)

    delete_job(job_id)


# should not be called without enclosing try-except block
def _do_project_job(job_id, project_id, skip_system_checks=False, docker_prune=False, full_docker_prune=False):
    #pylint: disable=import-outside-toplevel
    from runner import Runner

    check_job_running('project', job_id)

    [_, uri, _, branch, filename, _] = get_project(project_id)

    runner = Runner(
        uri=uri,
        uri_type='URL',
        pid=project_id,
        filename=filename,
        branch=branch,
        skip_unsafe=True,
        skip_system_checks=skip_system_checks,
        full_docker_prune=full_docker_prune,
        docker_prune=docker_prune,
    )
    try:
        # Start main code. Only URL is allowed for cron jobs
        runner.run()
        build_and_store_phase_stats(project_id, runner._sci)
        insert_job('email', project_id=project_id)
        delete_job(job_id)
    except Exception as exc:
        raise exc

# pylint: disable=redefined-outer-name
def handle_job_exception(exce, p_id):
    project_name = None
    client_mail = None
    if p_id:
        [project_name, _, client_mail, _, _, machine] = get_project(p_id)

    error_helpers.log_error('Base exception occurred in jobs.py: ', exce)
    email_helpers.send_error_email(GlobalConfig().config['admin']['email'], error_helpers.format_error(
        'Base exception occurred in jobs.py: ', exce), project_id=p_id, name=project_name, machine=machine)

    # reduced error message to client
    if client_mail and GlobalConfig().config['admin']['email'] != client_mail:
        email_helpers.send_error_email(client_mail, exce, project_id=p_id, name=project_name, machine=machine)

if __name__ == '__main__':
    #pylint: disable=broad-except,invalid-name

    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('type', help='Select the operation mode.', choices=['email', 'project'])
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')
    parser.add_argument('--skip-system-checks', action='store_true', default=False, help='Skip system checks')
    parser.add_argument('--full-docker-prune', action='store_true', default=False, help='Prune all images and build caches on the system')
    parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')

    args = parser.parse_args()  # script will exit if type is not present

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        if not Path(f"{CURRENT_DIR}/../{args.config_override}").is_file():
            parser.print_help()
            error_helpers.log_error(f"Could not find config override file on local system.\
                Please double check: {CURRENT_DIR}/../{args.config_override}")
            sys.exit(1)
        GlobalConfig(config_name=args.config_override)

    p_id = None
    try:
        job = get_job(args.type)
        if job is None or job == []:
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'No job to process. Exiting')
            sys.exit(0)
        p_id = job[2]
        process_job(job[0], job[1], job[2], args.skip_system_checks, args.docker_prune, args.full_docker_prune)
        print('Successfully processed jobs queue item.')
    except Exception as exce:
        handle_job_exception(exce, p_id)
