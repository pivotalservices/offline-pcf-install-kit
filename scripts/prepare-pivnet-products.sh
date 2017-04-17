#!/bin/bash
set -ex

# PIVNET_CLI=`find ./pivnet-cli -name "*darwin-amd64*"`
PIVNET_CLI=`find ./pivnet-cli -name "*linux-amd64*"`
chmod +x $PIVNET_CLI

# JQ=`find ./jq -name "*osx-amd64*"`
JQ=`find ./jq -name "*linux64*"`
chmod +x $JQ

MC=`find ./minio-client -name "mc"`
chmod +x $MC

rm -rf tmp
mkdir -p tmp

echo "Finding requested products $PIVNET_PRODUCT_SLUGS..."
$PIVNET_CLI login --api-token="$PIVNET_TOKEN"
$PIVNET_CLI products --format=json |\
  $JQ -r --argjson slugs "$PIVNET_PRODUCT_SLUGS" '.[] | select(.slug | match($slugs[])) | .slug' > tmp/products.txt

while read product_slug
do
  echo "Finding requested versions for $product_slug..."
  $PIVNET_CLI releases -p $product_slug --format=json |\
    $JQ -r --argjson versions "$PIVNET_PRODUCT_VERSIONS" '.[] | select(.version | match($versions[])) | .version' >"tmp/$product_slug-releases.txt"

  while read product_version
  do
    echo "Finding product files for $product_slug version $product_version..."
    $PIVNET_CLI product-files -p $product_slug -r $product_version --format=json |\
      $JQ -r --argjson files "$PIVNET_PRODUCT_FILES" '.[] | select(.aws_object_key | match($files[])) | "\(.id) \(.aws_object_key)"' >"tmp/$product_slug-$product_version-files.txt"

    echo "Downloading product files for $product_slug version $product_version..."
    while read product_file_id product_aws_key
    do
      product_bucket=$(dirname "${product_aws_key}")
      mkdir -p "minio_data/$product_bucket"
      $PIVNET_CLI download-product-files -p $product_slug -r $product_version -i $product_file_id -d "minio_data/$product_bucket" --accept-eula
    done < "tmp/$product_slug-$product_version-files.txt"

  done < "tmp/$product_slug-releases.txt"

done < "tmp/products.txt"


# At this point, minio_data/... is populated with the pivnet artifacts we want to
# provide in an offline repository.
