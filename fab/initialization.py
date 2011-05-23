import os
import tempfile
from fabric.api import *
from pantheon import pantheon

def initialize():
    '''Initialize the Pantheon system.'''
    server = pantheon.PantheonServer()

    _initialize_package_manager()
    _initialize_bcfg2()
    _initialize_iptables()
    _initialize_drush()
    _initialize_solr()
    _initialize_sudoers()
    _initialize_acl()
    _initialize_jenkins()
    _initialize_apache()

def _initialize_package_manager():
    """Setup package repos and version preferences.

    """
    local('cp /opt/pantheon/fab/templates/apt.mercury.list /etc/apt/sources.list.d/mercury.list')
    #TODO: is the below still necessary?
    #local('apt-key add /opt/mercury/fab/templates/apt.ppakeys.txt')
    local('echo \'APT::Install-Recommends "0";\' >>  /etc/apt/apt.conf')
    local('apt-get -y update', capture=False)
    local('apt-get -y dist-upgrade', capture=False)

def _initialize_bcfg2():
    """Install bcfg2 client and run for the first time.

    """
    local('apt-get install -y gamin python-gamin python-genshi bcfg2 bcfg2-server')
    pantheon.copy_template(pantheon.get_template('bcfg2.conf'),
                           '/etc/bcfg2.conf')
    local('rm -f /etc/bcfg2.key bcfg2.crt')
    local('openssl req -batch -x509 -nodes -subj "/C=US/ST=California/L=San Francisco/CN=localhost" -days 1000 -newkey rsa:2048 -keyout /etc/bcfg2.key -noout')
    local('openssl req -batch -new  -subj "/C=US/ST=California/L=San Francisco/CN=localhost" -key /etc/bcfg2.key | openssl x509 -req -days 1000 -signkey /etc/bcfg2.key -out /etc/bcfg2.crt')
    local('chmod 0600 /etc/bcfg2.key')
    if os.path.isdir('/var/lib/bcfg2'):
        os.system('rm -rf /var/lib/bcfg2')
    local('ln -sf /opt/pantheon/bcfg2 /var/lib/')
    pantheon.copy_template('clients.xml', '/var/lib/bcfg2/Metadata')
    local('/etc/init.d/bcfg2-server start')

    for i in range(600):
        if _bcfg2_server_running():
            break
        time.sleep(10)
    else:
        print "Failed to start bcfg2-server"
        sys.exit(1)
    local('/usr/sbin/bcfg2 -vqed', capture=False)

def _initialize_iptables():
    """Create iptable rules from template.

    """
    local('/sbin/iptables-restore < /etc/mercury/templates/iptables')
    local('cp /etc/mercury/templates/iptables /etc/iptables.rules')

def _initialize_drush():
    """Install Drush and Drush-Make.

    """
    #TODO: OSS: upgrade drush
    #TODO: Use deb package
    local('[ ! -d drush ] || rm -rf drush')
    local('wget http://ftp.drupal.org/files/projects/drush-6.x-3.3.tar.gz')
    local('tar xvzf drush-6.x-3.3.tar.gz')
    local('rm -f drush-6.x-3.3.tar.gz')
    local('chmod 555 drush/drush')
    local('chown -R root: drush')
    local('rm -rf /opt/drush && mv drush /opt/')
    local('mkdir /opt/drush/aliases')
    local('ln -sf /opt/drush/drush /usr/local/bin/drush')
    local('drush dl drush_make')

def _initialize_solr():
    """Download Apache Solr.

    """
    temp_dir = tempfile.mkdtemp()
    with cd(temp_dir):
        local('wget http://apache.osuosl.org/lucene/solr/1.4.1/apache-solr-1.4.1.tgz')
        local('tar xvzf apache-solr-1.4.1.tgz')
        local('mkdir -p /var/solr')
        local('mv apache-solr-1.4.1/dist/apache-solr-1.4.1.war /var/solr/solr.war')
        local('chown -R tomcat6:root /var/solr/')
    local('rm -rf ' + temp_dir)

def _initialize_acl():
    """Allow the use of ACLs and ensure they remain after reboot.

    """
    local('sudo tune2fs -o acl /dev/sda1')
    local('sudo mount -o remount,acl /')
    local('sudo sed -i "s/noatime /noatime,acl /g" /etc/fstab')

def _initialize_apache():
    """Remove the default vhost and clear /var/www.

    """
    local('a2dissite default')
    local('rm -f /etc/apache2/sites-available/default*')
    local('rm -f /var/www/*')

def _bcfg2_server_running():
    return bool(local('netstat -ln | grep 6789').strip())

