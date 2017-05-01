#!/bin/bash

# repo_url="localhost:5000"
# reponame="busybox"
# username="mtthwcmpbll"
# password="password"

#
# These are used to grab the manifest file from a public docker repo
#


uploadBlob() {
    local repo_url=$1
    local reponame=$2
    local file=$3
    # local digest=$4
    # local token=$4
    local uploadURL

    # play with grabbing digest for blob
    local digest="sha256:$(cat $file | openssl dgst -sha256)"
    # local digest=$(cat $fileDir/json | jq -r '.id')
    echo "Blob digest:  $digest"

    uploadURL=$(curl -siL -X POST "$repo_url/v2/$reponame/blobs/uploads/" | grep 'Location:' | cut -d ' ' -f 2 | tr -d '[:space:]')
    echo "Upload location:  $uploadURL&digest=$digest"

    # echo "Uploading Blob of 10 Random Megabytes"
    # time curl -T $file --progress-bar -H "Authorization: Bearer $token" "$uploadURL&digest=$digest" > /dev/null
    curl -v -H "Content-Type: application/vnd.docker.image.rootfs.diff.tar.gzip" -T $file --progress-bar "$uploadURL&digest=$digest"
}

uploadManifest() {
    local repo_url=$1
    local reponame=$2
    local file=$3
    # local token=$4
    local uploadURL

    # play with grabbing digest for blob
    local digest=$(cat $file | openssl dgst -sha256)
    # local digest=$(cat $fileDir/json | jq -r '.id')
    echo "Manifest digest:  $digest"

    uploadURL="$repo_url/v2/$reponame/manifests/latest"
    echo "Upload location:  $uploadURL"
    echo "Uploading manifest:  $(cat $file)"

    curl -v -H "Content-Type: application/vnd.docker.distribution.manifest.v1+prettyjws" -T $file --progress-bar "$uploadURL"
}

uploadImage() {
  local repo_url=$1
  local reponame=$2
  local imageFile=$3
  # local token=$(getToken $reponame "push")

  # Extract the image file into a temporary directory
  local imageDir=/tmp/$3
  rm -rf $imageDir
  mkdir -p $imageDir
  tar -xf $3 -C $imageDir

  # cat $imageDir/manifest.json | jq -r '.[] | .Layers[]' >"$imageDir/layers.txt"
  cat $imageDir/manifest.json | jq -r '.fsLayers[].blobSum' >"$outputDir/layers.txt"

  echo "Uploading image layers..."
  while read layer
  do
    echo "Uploading layer $layer"
    uploadBlob $repo_url $reponame $imageDir/$layer $layer
  done < "$imageDir/layers.txt"

  echo "Uploading image manifest..."
  uploadManifest $repo_url $reponame $imageDir/manifest.json
}

uploadImage $1 $2 $3
