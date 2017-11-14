# This script stops the local Concourse and Minio docker containers and cleans
# up all state to do a fresh run of the kit.

# Destroy the docker images
docker-compose kill
docker-compose rm

# Clean up orphaned docker volumes to clear up space in Docker VM
docker volume rm `docker volume ls -q -f dangling=true`

# Delete the concourse database data
rm -rf concourse/data
