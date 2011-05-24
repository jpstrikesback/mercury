#!/bin/bash

# Setup apt sources.
cp /opt/mercury/templates/apt.mercury.list /etc/apt/sources.list.d/mercury.list
apt-key add /opt/mercury/fab/templates/apt.ppakeys.txt
echo 'APT::Install-Recommends "0";' >>  /etc/apt/apt.conf

# Update package information and get necessary packages for bcfg/server.
apt-get -y update
apt-get -y dist-upgrade
apt-get install -y gamin python-gamin python-genshi bcfg2 bcfg2-server

# Setup bcfg2-server
cp /opt/mercury/templates/bcfg2.conf /etc/bcfg2.conf
openssl req -batch -x509 -nodes -subj "/C=US/ST=California/L=San Francisco/CN=localhost" -days 1000 -newkey rsa:2048 -keyout /etc/bcfg2.key -noout
openssl req -batch -new  -subj "/C=US/ST=California/L=San Francisco/CN=localhost" -key /etc/bcfg2.key | openssl x509 -req -days 1000 -signkey /etc/bcfg2.key -out /etc/bcfg2.crt
chmod 0600 /etc/bcfg2.key
rm -rf /var/lib/bcfg2
ln -sf /opt/mercury/bcfg2 /var/lib/
cp /opt/mercury/templates/clients.xml /var/lib/bcfg2/Metadata
/etc/init.d/bcfg2-server start

# Setup iptable rules
/sbin/iptables-restore < /opt/mercury/templates/iptables.rules
cp /opt/mercury/templates/iptables /etc/iptables.rules

# Install Drush and Drush Make
wget http://ftp.drupal.org/files/projects/drush-7.x-4.4.tar.gz
tar xzf drush-7.x-4.4.tar.gz
rm -f drush-7.x-4.4.tar.gz
chmod 555 drush/drush
chown -R root: drush
mv drush /opt/
mkdir /opt/drush/aliases
ln -sf /opt/drush/drush /usr/local/bin/drush
drush dl drush_make

# Download Solr
wget http://apache.osuosl.org/lucene/solr/1.4.1/apache-solr-1.4.1.tgz
tar xvzf apache-solr-1.4.1.tgz
mkdir -p /var/solr
mv apache-solr-1.4.1/dist/apache-solr-1.4.1.war /var/solr/solr.war
chown -R tomcat6:root /var/solr/
rm -rf apache-solr-1.4.1

# Setup ACLs
#TODO: OSS: make this linod friendly
tune2fs -o acl /dev/sda1
mount -o remount,acl /
sed -i "s/noatime /noatime,acl /g" /etc/fstab

# Run BCFG2
bcfg2 -vqed

# Apache Cleanup
a2dissite default
rm -f /etc/apache2/sites-available/default*
rm -f /var/www/*

#Install pip and fabric
#TODO: OSS: make code compatible with latest version of fabric
# pip install fabric

# Run configure
#TODO: OSS: Give the option to stop at this point if making images.
cd /opt/mercury/fab && fab configure

