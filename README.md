# Introduction

This is a set of tools and pipelines to prepare a hard drive filled with the tools
and artifacts required for installing PCF in an airgapped environment.

_Note:  At this point, only vSphere is targetted as the on-premises IaaS presents
the most common airgapped environment._

# Kit Contents

What exactly do you need to install a full PCF foundation with no public internet
functionality?  This repository is meant to collect the full set of artifacts so
that you can just drop it on a hard drive confident you have what you'll need.  
Everything outside of the `kit/` directory is intended to be used to _prepare_ the
kit you'll take into an airgapped environment.  The `kit/` directory itself collects
all of the artifacts, tools, pipelines, and resources you'll need to set up PCF
without any access to the internet.  The contents of the kit after preparation
are as follows:

- Version-pinned offline pipeline tarball containing the installation artifacts for
OpsManager and Elastic Runtime, required stemcells, and the modified pipelines to
unpack and install everything.  See the `pcf-pipelines` repository for more information
on this tarball and how to use it.
- Useful repositories containing bosh manifests and concourse pipelines.

# Kit Creation

The `docker-compose.yml` at the root of this repository spins up Concourse and Minio
locally.  You'll run a set of pipelines to prepare the kit, and since both save
their data locally to this repository you'll end up with a `kit/` directory at the
end of it all.

1. Install Docker if you don't already have it available on your local system.
1. Generate a GPG key pair for signing the offline artifacts.  GitHub has a great
tutorial on how to do this with the `gpg` command line tool.
1. Spin up the concourse and minio services pointed at local data directories using
the provided `docker-compose.yml`: `docker-compose up`
1. Fill out the params in `pipelines/create-pinned-pipelines-params.yml`
1. Target your local Concourse with `fly -t kit login -c http://localhost:8080` and
fly up the pipeline to generate the pinned pcf-pipelines tarball with `fly -t kit 
set-pipeline -p create-pinned-pipelines -c kit/repos/pcf-pipelines/create-offline-pinned-pipelines/pipeline.yml 
-l pipelines/create-pinned-pipelines-params.yml`
1. Create the necessary S3 buckets `s3-seed` in minio using the web UI at http://localhost:9000
or with the `mc` command line tool.
