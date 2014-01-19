#!/usr/bin/env python

import os
import sys
import time
import yaml
import shutil
import filecmp
import argparse
import tempfile
import traceback
import subprocess

from termcolor import cprint

verbose = False
trust_cert = False
local_cache = False
SAE_SVN_SERVER = 'https://svn.sinaapp.com/'
LOCAL_CACHE_FOLDER = os.path.expanduser('~/.saedeploy')


class SVNError(Exception):
    def __init__(self, subcommand):
        self.subcommand = subcommand

    def __repr__(self):
        return 'SVNError: ' + self.subcommand + ' went wrong!'


def retry(times, init_delay=10):
    def decorator(func):
        def retried_func(*args):
            delay = init_delay
            for i in range(times - 1):
                try:
                    return func(*args)
                except Exception:
                    cprint(traceback.format_exc(), 'red')
                    cprint('Retrying in ' + str(delay) + ' seconds...', 'red')
                    time.sleep(delay)
                    delay *= 2
            return func(*args)  # do not capture exceptions anymore
        return retried_func
    return decorator


@retry(times=5)
def svn_command(subcommand, *args):
    command = ['svn', '--non-interactive']
    # if not local_cache:
    #     command.append('--no-auth-cache')
    command.append('--no-auth-cache')
    if trust_cert:
        command.append('--trust-server-cert')
    command.append(subcommand)

    if not verbose and subcommand not in ('info', 'cleanup'):
        command.append('-q')
    command.extend(args)

    if verbose:
        if '--username' in command or '--password' in command:
            filtered_command = []
            for i in range(len(command)):
                # remove username and password from logging
                user_pass = ('--username', '--password')
                if command[i] in user_pass or \
                        (i > 0 and command[i - 1] in user_pass):
                    continue
                filtered_command.append(command[i])
            cprint('>>> ' + ' '.join(filtered_command), 'cyan')
        else:
            cprint('>>> ' + ' '.join(command), 'cyan')

    if subprocess.call(command) != 0:
        raise SVNError(subcommand)


class SAEDeploy:
    def __init__(self, app_path, username, password, ignore):
        self.app_path = app_path
        self.username = username
        self.password = password
        self.ignore_list = ignore

        yaml_path = os.path.join(self.app_path, 'config.yaml')
        configs = yaml.load(file(yaml_path, 'r'))
        self.app_name = str(configs['name'])
        self.version = str(configs['version'])

        if local_cache:
            self.temp_folder = LOCAL_CACHE_FOLDER
        else:
            self.temp_folder = tempfile.mkdtemp()
        self.temp_app_folder = os.path.join(self.temp_folder, self.app_name)
        # the sub folder containing the specific version
        self.temp_version_folder = os.path.join(self.temp_app_folder,
                                                self.version)

    def _download_files(self):
        cprint('Downloading remote files to the local folder...', 'yellow')
        cprint(self.temp_app_folder, 'yellow')
        if not os.path.exists(self.temp_app_folder):
            svn_command('checkout',
                        SAE_SVN_SERVER + self.app_name, self.temp_app_folder,
                        '--username', self.username,
                        '--password', self.password)
        else:
            svn_command('cleanup', self.temp_app_folder)
            svn_command('update', self.temp_app_folder,
                        '--username', self.username,
                        '--password', self.password)

    def _update_files(self):
        cprint('Updating modified files...', 'yellow')
        if not os.path.exists(self.temp_version_folder):
            if verbose:
                cprint('>>> Copying the entire folder from '
                       + self.app_path + ' to ' + self.temp_version_folder,
                       'cyan')
            shutil.copytree(self.app_path, self.temp_version_folder,
                            ignore=shutil.ignore_patterns('.*'))
            svn_command('add', self.temp_version_folder)
            return

        # this part is basically the same as http://goo.gl/ujByK5
        queue_folders = ['', ]
        while len(queue_folders) > 0:
            folder = queue_folders.pop(0)
            src = os.path.join(self.app_path, folder)
            dst = os.path.join(self.temp_version_folder, folder)
            dcmp = filecmp.dircmp(src, dst,
                                  ignore=['.svn', '.git'] + self.ignore_list)
            assert len(dcmp.common_funny) == 0  # FIXME
            assert len(dcmp.funny_files) == 0  # FIXME

            for f in dcmp.left_only:  # new files
                if f.startswith('.') \
                        or f.endswith('.pyc') or f.endswith('.wsgic'):  # XXX
                    continue
                src_file = os.path.join(src, f)
                dst_file = os.path.join(dst, f)
                if verbose:
                    cprint('>>> Copying the new file/folder from '
                           + src_file + ' to ' + dst_file, 'cyan')
                if os.path.isdir(src_file):
                    shutil.copytree(src_file, dst_file)
                else:
                    shutil.copy2(src_file, dst_file)
                svn_command('add', dst_file)

            for f in dcmp.right_only:  # removed files/folders
                if f.startswith('.'):
                    continue
                dst_file = os.path.join(dst, f)
                if verbose:
                    cprint('>>> Removing the file/folder ' + dst_file, 'cyan')
                if os.path.isdir(dst_file):
                    shutil.rmtree(dst_file)
                else:
                    os.remove(dst_file)
                svn_command('delete', dst_file)

            for f in dcmp.diff_files:  # changed files
                if f.startswith('.'):
                    continue
                src_file = os.path.join(src, f)
                dst_file = os.path.join(dst, f)
                if verbose:
                    cprint('>>> Updating the changed file from '
                           + src_file + ' to ' + dst_file, 'cyan')
                shutil.copy2(src_file, dst_file)

            for f in dcmp.common_dirs:
                if f.startswith('.'):
                    continue
                queue_folders.append(os.path.join(folder, f))

    def _upload_files(self):
        cprint('Uploading files to the SAE server...', 'yellow')
        if verbose:
            svn_command('status', self.temp_app_folder)
        svn_command('commit', self.temp_app_folder, '-mx',
                    '--username', self.username, '--password', self.password)

    def _clean_up(self):
        cprint('Cleaning up...', 'yellow')
        if hasattr(self, 'temp_folder') and \
                not local_cache and \
                self.temp_folder != LOCAL_CACHE_FOLDER:
            if verbose:
                cprint('>>> Deleting ' + self.temp_folder, 'cyan')
            shutil.rmtree(self.temp_folder)

    def deploy(self, verbose=True):
        succeeded = False
        cprint('Deploying ' +
               self.version + '.' + self.app_name + '.sinaapp.com...',
               'yellow')
        try:
            self._download_files()
            self._update_files()
            self._upload_files()
            succeeded = True
        except Exception:
            cprint(traceback.format_exc(), 'red')
        finally:
            self._clean_up()
            if succeeded:
                cprint('All done.', 'yellow')
                return 0
            else:
                cprint("The deployment isn't complete!", 'red')
                return -1


def main():
    try:
        subprocess.check_call(['svn', '--version'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, OSError):
        cprint('Please install Subversion first and try again.', 'red')
        sys.exit(-1)

    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?',
                        help='the folder containing config.yaml, which is ' +
                        'the current folder by default')
    parser.add_argument('-u', '--username', dest='username')
    parser.add_argument('-p', '--password', dest='password')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true')
    parser.add_argument(
        '--trust-cert', dest='trust_cert', action='store_true',
        help="always trust the SAE SVN server's TLS certificate")
    parser.add_argument(
        '--local-cache', dest='local_cache', action='store_true',
        help='cache remote files locally to speed up deployment')
    parser.add_argument(
        '--ignore', dest='ignore',
        help='files or folders to be ignored, ' +
             'separated by commas, such as --ignore=tmp,log,test')

    # first need to get path in order to look up .saedeploy
    args = parser.parse_args()
    if args.path is None:
        app_path = os.getcwd()  # the current folder by default
    else:
        app_path = os.path.abspath(args.path)

    args_in_file = []
    try:
        with open(os.path.join(app_path, '.saedeploy'), 'r') as f:
            for line in f.readlines():
                line = line.strip()
                if line.startswith('-'):
                    # ignore the lines not starting with '-' or '--'
                    args_in_file.extend(line.split())
    except IOError:
        pass

    # rebuild a list with arguments in .saedeploy
    sys_argv = args_in_file + list(sys.argv[1:])
    # the arguments in later positions have higher priorities

    def has_arg(lis, arg):
        if arg.startswith('--'):
            for v in lis:
                if v == arg or v.startswith(arg + '='):
                    return True
            return False
        elif arg.startswith('-'):
            for v in lis:
                if v.startswith(arg):  # '-v', '-v123', '-v=123'
                    return True
            return False
        else:
            cprint('Should not reach here.', 'red')
            return False

    # obtain username and password from environment variables
    if not has_arg(sys.argv, '-u') and not has_arg(sys.argv, '--username') \
            and 'SAEDEPLOY_USERNAME' in os.environ:
        sys_argv.extend(['--username', os.environ['SAEDEPLOY_USERNAME']])
    if not has_arg(sys.argv, '-p') and not has_arg(sys.argv, '--password') \
            and 'SAEDEPLOY_PASSWORD' in os.environ:
        sys_argv.extend(['--password', os.environ['SAEDEPLOY_PASSWORD']])
    args = parser.parse_args(sys_argv)
    # print args
    # sys.exit()

    global verbose, trust_cert, local_cache
    verbose = args.verbose
    trust_cert = args.trust_cert
    local_cache = args.local_cache

    # only app_path doesn't need to be updated
    if args.username is None or args.password is None:
        cprint('Please provide your SAE SVN username and password.\n',
               'yellow')
        parser.print_help()
        sys.exit(2)
    if args.ignore is None:
        ignore = []
    else:
        ignore = args.ignore.split(',')

    sae_app = SAEDeploy(app_path, args.username, args.password, ignore)
    ret_code = sae_app.deploy()
    sys.exit(ret_code)


if __name__ == '__main__':
    main()
