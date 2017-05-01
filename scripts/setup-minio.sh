#!/bin/bash
set -ex

mkdir -p minio/data
mkdir -p minio/config
chown -R pivotal minio/
