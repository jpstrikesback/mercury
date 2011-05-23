#!/bin/bash

packages=( 
    python-configobj 
    python-dev
    python-m2crypto
    python-mysqldb
    python-paramiko
    python-pip
    python-crypto
    python-setuptools
)

for package in ${packages[@]}
do
    apt-get install -y $package
done

#TODO: OSS: make code compatible with latest version of fabric
# pip install fabric
cd /opt/pantheon/fab && fab initialize
cd /opt/pantheon/fab && fab configure

