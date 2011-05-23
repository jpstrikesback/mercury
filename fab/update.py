# vim: tabstop=4 shiftwidth=4 softtabstop=4
import datetime
import tempfile
import time
import urllib2
import optparse
import os
import traceback
import string

from pantheon import pantheon
from pantheon import postback
from pantheon import status
from pantheon import update

from fabric.api import *

def _main():
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage, description="Update pantheon code and server configurations.")
    parser.add_option('-p', '--postback', dest="postback", action="store_true", default=False, help='Postback to atlas.')
    (options, args) = parser.parse_args()

    update_pantheon()
    if options.postback:
        post_update_pantheon()

def update_pantheon(first_boot=False):
    """Update pantheon code and server configurations.

    first_boot: bool. If this is being called from the configure job. If it
    is the first boot, we don't need to wait for jenkins or send back update
    data.

    Otherwise:

    This script is run from a cron job because it may update Jenkins (and
    therefor cannot be run inside jenkins.)

    If the script is successful, a known message will be printed to
    stdout which will be redirected to a log file. The jenkins job
    post_update_pantheon will check this log file for the message to
    determine if it was successful.

    """
    #TODO: OSS: Decide how to handle upgrades (do we stomp local changes or try and merge?)
    # Find out if this server is using a testing branch.
    branch = 'master'
    if os.path.exists('/opt/branch.txt'):
        branch = open('/opt/branch.txt').read().strip() or 'master'
    # Update from repo
    with cd('/opt/pantheon'):
        local('git fetch --prune origin', capture=False)
        local('git checkout --force %s' % branch, capture=False)
        local('git reset --hard origin/%s' % branch, capture=False)
    # Update from BCFG2
    local('/usr/sbin/bcfg2 -vqed', capture=False)
    print "UPDATE COMPLETED SUCCESSFULLY"

def update_site_core(project='pantheon', keep=None):
    """Update Drupal core (from Drupal or Pressflow, to latest Pressflow).
       keep: Option when merge fails:
             'ours': Keep local changes when there are conflicts.
             'theirs': Keep upstream changes when there are conflicts.
             'force': Leave failed merge in working-tree (manual resolve).
             None: Reset to ORIG_HEAD if merge fails.
    """
    updater = update.Updater(project, 'dev')
    result = updater.core_update(keep)
    updater.drupal_updatedb()
    updater.permissions_update()

    postback.write_build_data('update_site_core', result)

    if result['merge'] == 'success':
        # Send drupal version information.
        status.drupal_update_status(project)
        status.git_repo_status(project)

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
    updater.drupal_updatedb()
    updater.permissions_update()

    # Send back repo status and drupal update status
    status.git_repo_status(project)
    status.drupal_update_status(project)

def rebuild_environment(project, environment):
    """Rebuild the project/environment with files and data from 'live'.

    """
    updater = update.Updater(project, environment)
    updater.files_update('live')
    updater.data_update('live')

def update_data(project, environment, source_env, updatedb='True'):
    """Update the data in project/environment using data from source_env.

    """
    updater = update.Updater(project, environment)
    updater.data_update(source_env)
    # updatedb is passed in as a string so we have to evaluate it
    if eval(string.capitalize(updatedb)):
        updater.drupal_updatedb()

    # The server has a 2min delay before updates to the index are processed
    with settings(warn_only=True):
        local("drush @%s_%s solr-reindex" % (project, environment))
        local("drush @%s_%s cron" % (project, environment))

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

if __name__ == '__main__':
    _main()
