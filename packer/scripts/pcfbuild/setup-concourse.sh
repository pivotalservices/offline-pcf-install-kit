#!/bin/bash
set -ex

mkdir -p concourse/data
mkdir -p concourse/keys/web
mkdir -p concourse/keys/worker
chown -R pivotal concourse/

ssh-keygen -t rsa -f ./concourse/keys/web/tsa_host_key -N ''
ssh-keygen -t rsa -f ./concourse/keys/web/session_signing_key -N ''

ssh-keygen -t rsa -f ./concourse/keys/worker/worker_key -N ''

cp ./concourse/keys/worker/worker_key.pub ./concourse/keys/web/authorized_worker_keys
cp ./concourse/keys/web/tsa_host_key.pub ./concourse/keys/worker
