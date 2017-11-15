#!/usr/bin/env bash

set -ex

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

PCF_PIPELINES=$HOME/projects/mtthwcmpbll/pcf-pipelines
ONLINE_PIPELINE=$PCF_PIPELINES/install-pcf/aws/pipeline.yml
OFFLINE_PIPELINE=$PCF_PIPELINES/install-pcf/aws/offline/pipeline.yml

# Check if the required tooling is in place
command -v steamroll >/dev/null 2>&1 || { echo >&2 "steamroll command not available. See https://github.com/krishicks/concourse-pipeline-steamroller for installation instructions."; exit 1; }
command -v yaml-patch >/dev/null 2>&1 || { echo >&2 "yaml-patch command not available. See https://github.com/krishicks/yaml-patch for installation instructions."; exit 1; }

echo "Creating offline version of $ONLINE_PIPELINE..."
OFFLINE_PARENT_DIR="$(dirname "$OFFLINE_PIPELINE")"
mkdir -p $OFFLINE_PARENT_DIR

# Generate steamroll mapping configuration for target pipeline resources
cat > steamroll_config.yml <<EOF
resource_map:
  "pcf-pipelines": $PCF_PIPELINES
EOF

# Steamroll the online pipeline to get a flattened all-in-one YAML file
steamroll -p $ONLINE_PIPELINE -c steamroll_config.yml > $OFFLINE_PIPELINE.steamrolled

# Generate the offline patch for the pipeline
python $DIR/create-offline-pipeline.py -p $OFFLINE_PIPELINE.steamrolled > $OFFLINE_PIPELINE.patch

cat $OFFLINE_PIPELINE.steamrolled | yaml-patch -o $OFFLINE_PIPELINE.patch > flattened-offline-pipeline.yml
fly format-pipeline -c flattened-offline-pipeline.yml > $OFFLINE_PIPELINE
rm flattened-offline-pipeline.yml
