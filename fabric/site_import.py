# vim: tabstop=4 shiftwidth=4 softtabstop=4
from fabric.api import *
import os
import string
import random
import tempfile

import pantheon

def import_siteurl(url, project = None, environment = None):
    filename = pantheon.getfrom_url(url)
    import_site(filename, project, environment)

def import_site(site_archive, project = None, environment = None):
    '''Import site archive into a Pantheon server'''
    archive_directory = tempfile.mkdtemp() + '/'

    if (project == None):
        print("No project selected. Using 'pantheon'")
        project = 'pantheon'
    if (environment == None):
        print("No environment selected. Using 'dev'")
        environment = 'dev'

    pantheon.unarchive(site_archive, archive_directory)
    server = pantheon.PantheonServer()
    archive = pantheon.SiteImport(archive_directory, server.webroot, project, environment)

    _setup_databases(archive)
    _setup_site_files(archive)
    _setup_settings_files(archive)
    _setup_modules(archive)
    _setup_files_directory(archive)
    _setup_permissions(server, archive)
    _run_on_sites(archive.sites, 'cc all')
    _run_on_sites(archive.sites, 'cron')
    server.restart_services()

    local("rm -rf " + archive_directory)

def _setup_databases(archive):
    # Sites are matched to databases. Replace database name with: "project_environment_sitename"
    names = list()
    for site in archive.sites:
        # MySQL allows db names up to 64 chars. Check for & fix name collisions, assuming: 
        # project (up to 16chars) and environment (up to 5chars).
        for length in range(43,0,-1):
            #TODO: Write better fix for collisions
            name = archive.project + '_' + archive.environment + '_' + \
                site.get_safe_name()[:length] + \
                str(random.randint(0,9))*(43-length)
            if name not in names:
                break
            if length == 0:
                abort("Database name collision")
        site.database.name = name
        names.append(name)
        pantheon.import_data(archive.sites)

def _setup_site_files(archive):
    #TODO: add large file size sanity check (no commits over 20mb)
    #TODO: sanity check for versions prior to 6.6 (no pressflow branch).
    #TODO: look into ignoreing files directory
    #TODO: check for conflicts (hacked core)
    if os.path.exists(archive.destination):
        local('rm -r ' + archive.destination)

    # Create vanilla drupal/pressflow branch of same version as import site
    local("git clone " + archive.drupal.branch + " " + archive.destination)

    with cd(archive.destination):
        local("git branch pantheon " + archive.drupal.revision)
        local("git checkout pantheon")

        # Import site and revert any changes to core
        #local("git import-orig " + working_dir)
        local("rm -rf " + archive.destination + "*")
        local("rsync -avz " + archive.location + " " + archive.destination)

        # Cleanup potential issues
        local("rm -f PRESSFLOW.txt")

        # Commit the imported site on top of the closest-match core
        local("git add .")
        #print(local("git status"))
        local("git commit -a -m 'Imported site.'")
        #print(local("git status"))
        
        # Merge in Latest Pressflow
        local("git checkout master")
        local("git pull git://gitorious.org/pressflow/6.git master")
        #local("git pull git://gitorious.org/pantheon-pressflow/pantheon-pressflow.git master")
        local("git checkout pantheon")
        local("git pull . master") # Fails on conflict, commits otherwise.
        
        # TODO: Check for conflicts
        
        # TODO: Is this necessary?
        #local("rm -r ./.git")

def _run_on_sites(sites, cmd):
    for site in sites:
        site.drush(cmd)

def _setup_modules(archive):

    # TODO: add CAS back into the required module list when backend working.
    required_modules = ['apachesolr', 'apachesolr_search', 'cookie_cache_bypass', 'locale', 'syslog', 'varnish']

    if not os.path.exists(archive.destination + "sites/all/modules/"):
        local("mkdir " + archive.destination + "sites/all/modules/")

    # Drush will fail if it can't find memcache within drupal install. But we use drush to download memcache. 
    # Solve race condition by downloading outside drupal install. Download other prereqs also.
    # TODO: Add CAS module here too
    temporary_directory = tempfile.mkdtemp()
    with cd(temporary_directory):
        local("drush dl -y memcache apachesolr varnish")
        local("cp -R * " + archive.destination + "sites/all/modules/")
    local("rm -rf " + temporary_directory)
    
    # Run updatedb on all sites
    _run_on_sites(archive.sites, 'updatedb')

    # Make sure all required modules exist in sites/all/modules
    with cd(archive.destination + "sites/all/modules/"):

        # Download SolrPhpClient library
        local("wget http://solr-php-client.googlecode.com/files/SolrPhpClient.r22.2009-11-09.tgz")
        local("mkdir -p ./apachesolr/SolrPhpClient/")
        local("tar xzf SolrPhpClient.r22.2009-11-09.tgz -C ./apachesolr/")
        local("rm SolrPhpClient.r22.2009-11-09.tgz")

        # Download CAS php library
        local("wget http://downloads.jasig.org/cas-clients/php/1.1.2/CAS-1.1.2.tgz")
        local("tar xzf CAS-1.1.2.tgz")
        local("mv ./CAS-1.1.2 ./cas/CAS")
        local("rm CAS-1.1.2.tgz")

    server = PantheonServer()

    for site in archive.sites:

        # Create new solr index
        solr_path = archive.project + '_' + archive.environment + '_' + site.get_safe_name()
        server.create_solr_index(solr_path)

        with cd(archive.destination + "sites/" + site.name):
           # If required modules exist in specific site directory, make sure they are on latest version.
            if os.path.exists("modules"):
                with cd("modules"):
                    if os.path.exists("apachesolr"):
                        local("drush dl -y apachesolr")
                    #if os.path.exists("cas"):
                    #    local("drush dl -y cas")
                    if os.path.exists("memcache"):
                        local("drush dl -y memcache")
                    if os.path.exists("varnish"):
                        local("drush dl -y varnish")

        # Enable all required modules
        site.drush('enable', required_modules)

        # Solr variables
        drupal_vars = {}
        drupal_vars['apachesolr_path'] = '/' + solr_path
        drupal_vars['apachesolr_port'] = 8983
        drupal_vars['apachesolr_search_make_default'] = 1
        drupal_vars['apachesolr_search_spellcheck'] = True

        # admin/settings/performance variables
        drupal_vars['cache'] = 'CACHE_EXTERNAL'
        drupal_vars['page_cache_max_age'] = 900
        drupal_vars['block_cache'] = True
        drupal_vars['page_compression'] = 0
        drupal_vars['preprocess_js'] = True
        drupal_vars['preprocess_css'] = True

        # CAS variables
        #drupal_vars['cas_server'] = 'login.getpatheon.com'
        #drupal_vars['cas_uri'] = '/cas'

        # Set Drupal variables
        with settings(warn_only=True):
            site.set_variables(drupal_vars)

def _setup_files_directory(archive):
    for site in archive.sites:
        site.file_location = site.get_file_location()
        with cd(archive.destination + "sites/" + site.name):
            # if file_directory_path is not set.
            if not site.file_location:
                site.file_location = 'sites/' + site.name + '/files'
                site.set_variables({'file_directory_path':site.file_location})
            # if file_directory_path is set, but doesn't exist, create it.
            if not os.path.exists(archive.destination + site.file_location):
                local("mkdir -p " + archive.destination + site.file_location)

def _setup_permissions(server, archive):
    local("chown -R %s:%s %s" % (server.owner, server.group, archive.destination))
    for site in archive.sites:
        site.set_site_perms(archive.destination)
        # Solr Index permissions
        with cd("/var/solr"):
            local("chown -R %s:%s *" % (server.tomcat_owner, server.tomcat_owner))

def _setup_settings_files(archive):
    slug_template = local("cat /opt/pantheon/fabric/templates/import.settings.php")
    for site in archive.sites:
        # Add project + random string as memcached prefix.
        site.database.memcache_prefix = archive.project + \
                ''.join(["%s" % random.choice(string.ascii_letters + string.digits) for i in range(8)])
        slug = string.Template(slug_template)
        slug = slug.safe_substitute(site.database.__dict__)
        with open(archive.destination + "sites/" + site.name + "/settings.php", 'a') as f:
            f.write(slug)
        f.close


