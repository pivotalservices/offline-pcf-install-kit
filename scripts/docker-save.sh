#!/bin/bash

#
# These are used to grab the manifest file from a public docker repo
#


# username="mtthwcmpbll"
# password="password"

getToken() {
    local reponame=$1
    local actions=$2
    local headers
    local response

    if [ -n "$username" ]; then
        headers="Authorization: Basic $(echo -n "${username}:${password}" | base64)"
    fi

    response=$(curl -s -H "$headers" "https://auth.docker.io/token?service=registry.docker.io&scope=repository:$reponame:$actions")

    echo $response | jq '.token' | xargs echo
}

getPublicImageManifest() {
  local reponame=$1
  local reference=$2
  local outputDir=$3
  local token=$(getToken $reponame "pull")
  curl -s -H "Authorization: Bearer $token" "https://registry-1.docker.io/v2/$reponame/manifests/$reference" >"$outputDir/manifest.json"
}

downloadPublicBlob() {
  local reponame=$1
  local blobDigest=$2
  local outputDir=$3
  local token=$(getToken $reponame "pull")
  mkdir -p $outputDir/$blobDigest
  curl -v -L --progress-bar -H "Authorization: Bearer $token" "https://registry-1.docker.io/v2/$reponame/blobs/$blobDigest" > $outputDir/$blobDigest/layer.tar
}

downloadPublicImage() {
  local reponame=$1
  local reference=$2
  local outputDir=$3

  mkdir -p $outputDir

  getPublicImageManifest $reponame $reference $outputDir
  # echo -n $manifest | jq -c '.' >"$outputDir/manifest.json"
  # echo $manifest | jq -r 'del(.signatures)' >"$outputDir/manifest.json"

  cat $outputDir/manifest.json | jq -r '.fsLayers[].blobSum' >"$outputDir/layers.txt"

  echo "Downloading image layers..."
  while read layer
  do
    echo "Downloading layer $layer"
    downloadPublicBlob $reponame $layer $outputDir
  done < "$outputDir/layers.txt"
}

rm $3
rm -rf /tmp/docker_image
downloadPublicImage $1 $2 /tmp/docker_image
tar -cvf $3 -C /tmp/docker_image .
