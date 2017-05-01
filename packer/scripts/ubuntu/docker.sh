#!/bin/bash

set -e
set -x

sudo apt-get update
sudo apt-get install -y software-properties-common python-software-properties apt-transport-https
sudo apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D
sudo apt-add-repository 'deb https://apt.dockerproject.org/repo ubuntu-xenial main'
sudo apt-get update
sudo apt-get install -y docker-engine docker-compose
sudo service docker restart

# Add the pivotal user to the docker group to make sure it can run without sudo
sudo usermod -aG docker pivotal
sudo shutdown -r now
