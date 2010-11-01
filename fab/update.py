# vim: tabstop=4 shiftwidth=4 softtabstop=4
import datetime
import tempfile
import os
import sys

from pantheon import gittools
from pantheon import pantheon
from pantheon import postback
from pantheon import update

from fabric.api import *

def update_pantheon():
       print("Updating Pantheon from Launchpad")
       local('/etc/init.d/bcfg2-server stop')
       local('cd /opt/pantheon; bzr up')
       pantheon.restart_bcfg2()
       local('/usr/sbin/bcfg2 -vq', capture=False)
       print("Pantheon Updated")

def update_site_core(project='pantheon', keep=None):
    """Update Drupal core (from Drupal or Pressflow, to latest Pressflow).
       keep: Option when merge fails:
             'ours': Keep local changes when there are conflicts.
             'theirs': Keep upstream changes when there are conflicts.
             'force': Leave failed merge in working-tree (manual resolve).
             None: Reset to ORIG_HEAD if merge fails.
    """
    updater = update.Updater(project)
    result = updater.core_update(keep)

    postback.write_build_data('update_site_core', result)

    if result['merge'] == 'success':
        drupal_update_status(project)

def update_code(project, environment, tag=None, message=None):
    """ Update the working-tree for project/environment.

    """
    if not tag:
        tag = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    if not message:
        message = 'Tagging as %s for release.' % tag

    updater = update.Updater(project, environment)
    updater.test_tag(tag)
    updater.code_update(tag, message)
    updater.permissions_update()

    # Send back repo status.
    git_repo_status(project)


def post_receive_update(project, dev_update=True):
    """Update development environment with changes pushed from remote.
    project: project name
    dev_update: if the development environment should be updated.

    """
    # if coming from fabric, update could be string. Make bool.
    dev_update = eval(str(dev_update))
    updater = update.Updater(project, 'dev')
    if dev_update:
        updater.permissions_update()
    else:
        # Let hudson post back the gitstatus, but do no processing.
        pass

def rebuild_environment(project, environment):
    """Rebuild the project/environment with files and data from 'live'.

    """
    updater = update.Updater(project, environment)
    updater.files_update('live')
    updater.data_update('live')

def update_data(project, environment, source_env):
    """Update the data in project/environment using data from source_env.

    """
    updater = update.Updater(project, environment)
    updater.data_update(source_env)

def update_files(project, environment, source_env):
    """Update the files in project/environment using files from source_env.

    """
    updater = update.Updater(project, environment)
    updater.files_update(source_env)

def git_diff(project, environment, revision_1, revision_2=None):
    """Return git diff

    """
    updater = update.Updater(project, environment)
    if not revision_2:
           updater.run_command('git diff %s' % revision_1)
    else:
           updater.run_command('git diff %s %s' % (revision_1, revision_2))

def git_status(project, environment):
    """Return git status

    """
    updater = update.Updater(project, environment)
    updater.run_command('git status')

def git_repo_status(project):
    """Post back to Atlas with the status of the project Repo.

    """
    repo = gittools.GitRepo(project)
    status = repo.get_repo_status()

    postback.write_build_data('git_repo_status', {'status': status})

def drupal_update_status(project):
    """Return whether or not there's a core update available.
    This will post back directly rather than using a post-build action.

    """
    drushrc = project +'_dev';
    status = local("drush @%s -n -p upc" % drushrc).rstrip().split('\n')

    postback.write_build_data('drupal_update_status', {'status': status})

