# Start up the Concourse and Minio docker containers
docker-compose up -d

sleep 20

# Log in and alias the local Concourse
fly -t kit login -c http://localhost:8080

# Log in and alias the local Minio server
mc config host add kit http://localhost:9000 minio alwaysbekind

# Gather PCF Installation Artifacts
mc mb kit/s3-starter; true;
fly -t kit set-pipeline -p create-offline-pinned-pipelines -c kit/repos/pcf-pipelines/create-offline-pinned-pipelines/pipeline.yml -l pipelines/create-pinned-pipelines-params.yml -l ~/concourse-secrets.yml
fly -t kit unpause-pipeline -p create-offline-pinned-pipelines
fly -t kit trigger-job -j create-offline-pinned-pipelines/collector

# Save the czero-cflinuxfs2 rootfs
mkdir kit/s3-starter/czero-cflinuxfs2
cp kit/s3-starter/staging/czero-cflinuxfs2/*.tar kit/s3-starter/czero-cflinuxfs2/

# Clean up the staging directory
rm -rf kit/s3-starter/staging

# Gather Additional Products, Add-ons, and Tools
fly -t kit set-pipeline -p download-hdd-files -c pipelines/download-hdd-files/pipeline.yml -l pipelines/download-hdd-files/params.yml -l ~/concourse-secrets.yml
fly -t kit unpause-pipeline -p download-hdd-files
fly -t kit trigger-job -j download-hdd-files/tool-collector
fly -t kit trigger-job -j download-hdd-files/bosh-collector
fly -t kit trigger-job -j download-hdd-files/addon-collector
fly -t kit trigger-job -j download-hdd-files/tile-collector
