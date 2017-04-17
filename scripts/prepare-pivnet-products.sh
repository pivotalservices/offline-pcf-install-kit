#!/bin/bash
set -ex

PIVNET_CLI=`find ./pivnet-cli -name "*linux-amd64*"`
chmod +x $PIVNET_CLI

JQ=`find ./jq -name "*linux64*"`
chmod +x $JQ

echo "Downloading products from pivnet..."
$PIVNET_CLI login --api-token="$PIVNET_TOKEN"
$PIVNET_CLI products --format=json | $JQ



# URL="http://myriak.server:8098/buckets/mybucket/index/index_int/100/200/"
# curl -Ss  "$URL" | jq -r '.keys[] | @uri' |\
# while read key
# do
#   curl "http://myriak/buckets/mybucket/keys/$key"
# done | jq '.[] | {id}'



# docker run minio:...
#
# fill the s3 bucket
#
# export the docker container
#
# output the image as our task artifact
