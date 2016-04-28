# coding=utf-8
# -----------------------------------------------------------------------------
#                     The CodeChecker Infrastructure
#   This file is distributed under the University of Illinois Open Source
#   License. See LICENSE.TXT for details.
# -----------------------------------------------------------------------------

"""Setup for the package tests."""

import json
import multiprocessing
import os
import subprocess
import sys
import time
import uuid

# sys.path modification needed so nosetests can load the test_utils package
sys.path.append(os.path.abspath(os.environ['TEST_TESTS_DIR']))
from test_utils import get_free_port

# Because of the nature of the python-env loading of nosetests, we need to
# add the codechecker_gen package to the pythonpath here, so it is available
# for the actual test cases.
__PKG_ROOT = os.path.abspath(os.environ['TEST_CODECHECKER_DIR'])
__LAYOUT_FILE_PATH = os.path.join(__PKG_ROOT, 'config', 'package_layout.json')
with open(__LAYOUT_FILE_PATH) as layout_file:
    __PACKAGE_LAYOUT = json.load(layout_file)
sys.path.append(os.path.join(
    __PKG_ROOT, __PACKAGE_LAYOUT['static']['codechecker_gen']))

# stopping event for CodeChecker server
__STOP_SERVER = multiprocessing.Event()


def setup_package():
    """Setup the environment for the tests. Check the test project twice,
    then start the server."""
    pkg_root = os.path.abspath(os.environ['TEST_CODECHECKER_DIR'])

    env = os.environ.copy()
    env['PATH'] = os.path.join(pkg_root, 'bin') + ':' + env['PATH']

    tmp_dir = os.path.abspath(os.environ['TEST_CODECHECKER_PACKAGE_DIR'])
    workspace = os.path.join(tmp_dir, 'workspace')
    if not os.path.exists(workspace):
        os.makedirs(workspace)

    test_project_path = os.path.join(
        os.path.abspath(os.environ['TEST_TESTS_DIR']),
        'test_projects',
        'test_files')

    clang_version = os.environ.get('TEST_CLANG_VERSION', 'stable')

    use_postgresql = os.environ.get('TEST_USE_POSTGRESQL', '') == 'true'

    pg_db_config = {}
    if use_postgresql:
        pg_db_config['dbaddress'] = 'localhost'
        pg_db_config['dbname'] = 'testDb'
        if os.environ.get('TEST_DBUSERNAME', False):
            pg_db_config['dbusername'] = os.environ['TEST_DBUSERNAME']
        if os.environ.get('TEST_DBPORT', False):
            pg_db_config['dbport'] = os.environ['TEST_DBPORT']

    project_info = \
        json.load(open(os.path.realpath(env['TEST_TEST_PROJECT_CONFIG'])))

    test_config = {
        'CC_TEST_SERVER_PORT': get_free_port(),
        'CC_TEST_SERVER_HOST': 'localhost',
        'CC_TEST_VIEWER_PORT': get_free_port(),
        'CC_TEST_VIEWER_HOST': 'localhost'
    }

    test_project_clean_cmd = project_info['clean_cmd']
    test_project_build_cmd = project_info['build_cmd']

    # setup env vars for test cases
    os.environ['CC_TEST_VIEWER_PORT'] = str(test_config['CC_TEST_VIEWER_PORT'])
    os.environ['CC_TEST_SERVER_PORT'] = str(test_config['CC_TEST_SERVER_PORT'])
    os.environ['CC_TEST_PROJECT_INFO'] = \
        json.dumps(project_info['clang_' + clang_version])
    # -------------------------------------------------------------------------

    # generate suppress file
    suppress_file = os.path.join(tmp_dir, 'suppress_file')
    if os.path.isfile(suppress_file):
        os.remove(suppress_file)
    _generate_suppress_file(suppress_file)

    skip_list_file = os.path.join(test_project_path, 'skip_list')

    shared_test_params = {
        'suppress_file': suppress_file,
        'env': env,
        'use_postgresql': use_postgresql,
        'workspace': workspace,
        'pg_db_config': pg_db_config
    }

    # first check
    _clean_project(test_project_path, test_project_clean_cmd, env)
    test_project_1_name = project_info['name'] + '_' + uuid.uuid4().hex

    _run_check(shared_test_params, skip_list_file, test_project_build_cmd,
               test_project_1_name, test_project_path)

    time.sleep(5)

    # second check
    _clean_project(test_project_path, test_project_clean_cmd, env)

    test_project_2_name = project_info['name'] + '_' + uuid.uuid4().hex

    _run_check(shared_test_params, skip_list_file, test_project_build_cmd,
               test_project_2_name, test_project_path)

    time.sleep(5)

    # start the CodeChecker server
    _start_server(shared_test_params, test_config)


def teardown_package():
    """Stop the CodeChecker server."""
    __STOP_SERVER.set()

    time.sleep(10)


def _pg_db_config_to_cmdline_params(pg_db_config):
    """Format postgres config dict to CodeChecker cmdline parameters"""
    params = []

    for key, value in pg_db_config.iteritems():
        params.append('--' + key)
        params.append(str(value))

    return params


def _clean_project(test_project_path, clean_cmd, env):
    """Clean the test project."""
    command = ['bash', '-c', clean_cmd]

    try:
        subprocess.check_call(command, cwd=test_project_path, env=env)
    except subprocess.CalledProcessError as perr:
        raise perr


def _generate_suppress_file(suppress_file):
    """
    Create a dummy supppress file just to check if the old and the new
    suppress format can be processed.
    """
    import calendar
    import hashlib
    import random

    hash_version = '1'
    suppress_stuff = []
    for _ in range(10):
        curr_time = calendar.timegm(time.gmtime())
        random_integer = random.randint(1, 9999999)
        suppress_line = str(curr_time) + str(random_integer)
        suppress_stuff.append(
            hashlib.md5(suppress_line).hexdigest() + '#' + hash_version)

    s_file = open(suppress_file, 'w')
    for k in suppress_stuff:
        s_file.write(k + '||' + 'idziei éléáálk ~!@#$#%^&*() \n')
        s_file.write(
            k + '||' + 'test_~!@#$%^&*.cpp' +
            '||' 'idziei éléáálk ~!@#$%^&*(\n')
        s_file.write(
            hashlib.md5(suppress_line).hexdigest() + '||' +
            'test_~!@#$%^&*.cpp' + '||' 'idziei éléáálk ~!@#$%^&*(\n')

    s_file.close()


def _generate_skip_list_file(skip_list_file):
    """
    Create a dummy skip list file just to check if it can be loaded.
    Skip files without any results from checking.
    """
    skip_list_content = []
    skip_list_content.append("-*randtable.c")
    skip_list_content.append("-*blocksort.c")
    skip_list_content.append("-*huffman.c")
    skip_list_content.append("-*decompress.c")
    skip_list_content.append("-*crctable.c")

    s_file = open(skip_list_file, 'w')
    for k in skip_list_content:
        s_file.write(k + '\n')

    s_file.close()


def _run_check(shared_test_params, skip_list_file, test_project_build_cmd,
               test_project_name, test_project_path):
    """Check a test project."""
    check_cmd = []
    check_cmd.append('CodeChecker')
    check_cmd.append('check')
    check_cmd.append('-w')
    check_cmd.append(shared_test_params['workspace'])
    check_cmd.append('--suppress')
    check_cmd.append(shared_test_params['suppress_file'])
    check_cmd.append('--skip')
    check_cmd.append(skip_list_file)
    check_cmd.append('-n')
    check_cmd.append(test_project_name)
    check_cmd.append('-b')
    check_cmd.append(test_project_build_cmd)
    check_cmd.append('--analyzers')
    check_cmd.append('clangsa')
    if shared_test_params['use_postgresql']:
        check_cmd.append('--postgresql')
        check_cmd += _pg_db_config_to_cmdline_params(
            shared_test_params['pg_db_config'])

    try:
        subprocess.check_call(
            check_cmd,
            cwd=test_project_path,
            env=shared_test_params['env'])
    except subprocess.CalledProcessError as perr:
        raise perr


def _start_server(shared_test_params, test_config):
    """Start the CodeChecker server."""
    def start_server_proc(event, server_cmd, checking_env):
        """Target function for starting the CodeChecker server."""
        proc = subprocess.Popen(server_cmd, env=checking_env)

        # Blocking termination until event is set.
        event.wait()

        # If proc is still running, stop it.
        if proc.poll() is None:
            proc.terminate()
    # -------------------------------------------------------------------------

    server_cmd = []
    server_cmd.append('CodeChecker')
    server_cmd.append('server')
    server_cmd.append('--check-port')
    server_cmd.append(str(test_config['CC_TEST_SERVER_PORT']))
    server_cmd.append('--view-port')
    server_cmd.append(str(test_config['CC_TEST_VIEWER_PORT']))
    server_cmd.append('-w')
    server_cmd.append(shared_test_params['workspace'])
    server_cmd.append('--suppress')
    server_cmd.append(shared_test_params['suppress_file'])
    if shared_test_params['use_postgresql']:
        server_cmd.append('--postgresql')
        server_cmd += _pg_db_config_to_cmdline_params(
            shared_test_params['pg_db_config'])

    server_proc = multiprocessing.Process(
        name='server',
        target=start_server_proc,
        args=(__STOP_SERVER, server_cmd, shared_test_params['env']))

    server_proc.start()

    # wait for server to start and connect to database
    time.sleep(10)