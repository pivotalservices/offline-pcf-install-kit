# Introduction

This is a set of tools and pipelines to prepare a hard drive filled with the tools
and artifacts required for installing PCF in an offline environment.

_Note:  At this point, only vSphere is targeted as the on-premises IaaS presents
the most common offline environment._

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

## On the Outside (with Internet Access)

The `docker-compose.yml` at the root of this repository spins up Concourse and Minio
locally to use during kit preparation.  You'll run a set of pipelines to prepare
the kit, and the Minio instance saves its data locally to the `kit/`.  Start up
the local docker containers:

```
docker-compose up
```

Note that the docker compose manifest configures Concourse and Minio with default
credentials (usually the service as username and `alwaysbekind` as the password).
The various pipeline parameter files are prepopulated with these values.  If you change
the usernames or passwords, you'll need to update these parameters as well.

Additionally, the externally-run pipelines are preconfigured with the URLs and ports
for these services as well, so the Concourse and Minio settings should work out of
the box if you haven't changed the docker configuration.

Log in and alias to your local tools:

```
# Log in and alias the local Concourse
fly -t kit login -c http://localhost:8080

# Log in and alias the local Minio server
mc config host add kit http://localhost:9000 minio alwaysbekind
```

### Gather PCF Installation Artifacts

Next, we'll download the PCF OpsManager and Elastic Runtime, and prepare an offline
version of `pcf-pipelines` pinned to the downloaded versions of the product.

```
fly -t kit set-pipeline -p create-offline-pinned-pipelines -c kit/repos/pcf-pipelines/create-offline-pinned-pipelines/pipeline.yml -l pipelines/create-pinned-pipelines-params.yml
fly -t kit unpause-pipeline -p create-offline-pinned-pipelines
fly -t kit trigger-job -j create-offline-pinned-pipelines/collector
```

This will take a while to run, and will populate the `kit/s3-starter` directory
with the signed tarball containing all of the required artifacts for installing
PCF in an airgapped environment.

Even though the tarball contains the `czero-cflinuxfs2` rootfs, there's a chicken-and-egg
problem where we'll need it to run the pipeline that unpacks that tarball.  Copy it
into the `s3-starter` directory to keep it around, then clean up the staging directory:

```
mkdir kit/s3-starter/czero-cflinuxfs2
cp kit/s3-starter/staging/czero-cflinuxfs2/*.tar kit/s3-starter/czero-cflinuxfs2/
rm -rf kit/s3-starter/staging
```

### Gather Additional Products, Add-ons, and Tools

Update the parameters in `pipelines/download-hdd-files/params.yml`
and fly up the pipeline to download the various products, stemcells, tools, bosh
releases, and add-ons used in a common secure offline environment.

```
fly -t kit set-pipeline -p download-hdd-files -c pipelines/download-hdd-files/pipeline.yml -l pipelines/download-hdd-files/params.yml
fly -t kit unpause-pipeline -p download-hdd-files
fly -t kit trigger-job -j download-hdd-files/tool-collector
fly -t kit trigger-job -j download-hdd-files/bosh-collector
fly -t kit trigger-job -j download-hdd-files/addon-collector
fly -t kit trigger-job -j download-hdd-files/tile-collector
```

### Save Additional Docker Images

If you're bringing in additional pipelines with tasks that are based on images other
than `czero/cflinuxfs2`, you'll need to save these in the rootfs tarball format and
then update the pipelines to pull them from S3 instead of docker on the inside.

For building an NSX environment in vSphere, you'll need to download the `nsxedgegen/nsx-edge-gen-worker`
image using the default parameters provided.  To download other images, update
the parameters in `pipelines/save-docker-image/params.yml` and fly up the pipeline
for each image you need to download.

```
# Fly up the pipeline and get it running
fly -t kit set-pipeline -p save-docker-image -c pipelines/save-docker-image/pipeline.yml -l pipelines/save-docker-image/params.yml
fly -t kit unpause-pipeline -p save-docker-image
fly -t kit trigger-job -j save-docker-image/save-docker-image
```

### Transport

You're offline installation kit is ready to go - just drop the `kit/` directory onto
a portable hard drive or disk and carry it into your offline environment.

**REMEMBER TO TAKE IN YOUR PRIVATE KEY TO DECRYPT THE TARBALL!  THIS IS THE PRIVATE
PAIR TO THE PUBLIC KEY USED TO ENCRYPT, PROVIDED IN THE `create-pinned-pipelines-params.yml`.**

## Using the Kit on the Inside

TODO
