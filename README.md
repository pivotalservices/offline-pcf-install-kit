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
kit you'll take into an offline environment.  The `kit/` directory itself collects
all of the artifacts, tools, pipelines, and resources you'll need to set up PCF
without any access to the internet.

The kit itself is made up of several components:

1. The product bits (VMs, tiles, and stemcells) for installing OpsMan and ERT without access to the internet.
1. The tools used to run the pipelines inside the airgapped environment.  This includes Bosh, Concourse, and Minio.
1. The Concourse pipelines and backing task docker images used to install OpsMan and ERT from offline artifacts.
1. Any additional Pivotal products, bosh releases/add-ons, and open-source tooling to be deployed in the offline environment.

The product bits are provided by Pivotal Network, GitHub, Bosh.io, and other open-source repositories.  The pipelines for packing, unpacking, and installing PCF is provided by the `pcf-pipelines` releases on Pivotal Network or from their repository on GitHub.  Supplemental pipelines for gathering up the rest of the resources are provided by this repository.

```
kit
├── s3-starter
|   |   (These are the buckets required to be on the offline S3 to use the kit)
|   |
│   ├── czero-cflinuxfs2
│   │   └── czero-cflinuxfs2-v0.16.0-sha256:b1c970742e0fa0f68b574c7fc87dd94ca0c2783f3feeb3ee20052f87af94b5a1.tar
│   ├── nsxedgegen
│   │   └── nsx-edge-gen-worker-0.0.1-sha256:d93b80e0726a28d349bfb65b4948b61fae92e124645afde0159f3525e3992b89.tar
│   └── pcf-pipelines-combined
│       ├── pcf-pipelines-combined-5.0.0.tar.gpg
│       └── version
```

# Kit Creation

## A Note on GPG Keys

You'll need a GPG key-pair to encrypt artifacts on the outside (using the public
key) and decrypt on the inside (using the private key).  This enables the organization
to provide only the public key to the outside preparer, then verify that nothing
has been tampered with during transport.

In order to generate a new key-pair, you can follow [this GitHub tutorial](https://help.github.com/articles/generating-a-new-gpg-key/) to run
the following commands:

```
# Run the interactive gen-key command, noting the real name and email provided.
gpg --gen-key

# Export the public and private keys, where NAME is the real name provided and
# EMAIL is the email provided during the call to gen-key
gpg --export -a "NAME <EMAIL>" > public.key
gpg --export-secret-key -a "NAME <EMAIL>" > public.key
```

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

**Note:  The `online-workflow.sh` script runs all of the above commands in sequence,
and can be run as a single command to download and package things up to this point.
You can run the `cleanup.sh` script to destroy the docker images, concourse data,
and volumes (but nothing in the `kit/` directory) in order to perform a clean run.**

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

Once you're inside an airgapped environment, we'll need to set up some basic tools
to prepare the environment and install PCF.  At a high level this setup includes
the following:

1. Deploy a bosh director, Concourse for running automation pipelines, and Minio
for hosting offline artifacts.
1. Uploading the offline artifacts into Minio in the required buckets.
1. Run the `unpack-pcf-pipelines-combined` pipeline to unpack the remaining artifacts.
1. Install PCF using the offline pipeline.
