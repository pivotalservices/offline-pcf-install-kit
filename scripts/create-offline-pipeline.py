#!/bin/python

"""
Dependencies:

Python:  dpath, pyyaml
"""

import sys
import os
from os.path import join
import argparse
import re
import yaml
import dpath.util

tmp_dir = 'tmp'
try:
    os.makedirs(tmp_dir)
except: pass


def get_yaml_nodes(yml, root="/**", filter=lambda x: True):
    """
    Collects all YAML blocks that match the given filter.
    
    Keyword arguments:
    yaml -- the YAML object to filter
    filter -- the filter to select matching YAML blocks
    """
    nodes = {}
    for path, node in dpath.util.search(yml, root, yielded=True):
        if filter(node):
            nodes[path] = node
    return nodes

def load_pipeline(pipeline_path):
    """
    Loads a pipeline at the given path.
    """
    pipeline_str = open(pipeline_path).read()
    pipeline_str = re.sub('{{', '\{\{', pipeline_str)
    pipeline_str = re.sub('}}', '\}\}', pipeline_str)
    pipeline = yaml.load(pipeline_str)
    return pipeline

def process_pipeline(pipeline):
    # Op for loading docker images from S3
    replace_task_docker_images(pipeline)
    
    # Ops for replacing resources
    # resource_definitions = get_resources(pipeline)
    # handled_resources = []
    # get_resource_filter = lambda x: isinstance(x, dict) and 'get' in x
    # get_resource_blocks = get_yaml_blocks(pipeline, False, None, get_resource_filter)
    # for b in get_resource_blocks:
    #     resource_name = b['get']
    #     if 'resource' in b:
    #         resource_name = b['resource']
    #     if resource_name not in handled_resources:
    #         handle_get_resource(pipeline, b, resource_definitions[resource_name], git_repos_dir, github_releases_dir, pivnet_resources_dir, docker_images_dir)
    #         handled_resources.append(resource_name)

def replace_task_docker_images(pipeline):
    task_docker_images_filter = lambda x: isinstance(x, dict) and 'type' in x and x['type'] == 'docker-image' and 'repository' in x['source']
    task_docker_image_nodes = get_yaml_nodes(pipeline, "/jobs/**/image_resource", task_docker_images_filter)
    for path in sorted(task_docker_image_nodes.iterkeys()):
        task_docker_image_node = task_docker_image_nodes[path]
        docker_image = task_docker_image_node['source']['repository']
        s3_name = docker_image.replace("/", "-")
        
        print("""
- op: replace
  path: /%s
  value:
    type: s3
    source:
      access_key_id: {{s3_access_key_id}}
      secret_access_key: {{s3_secret_access_key}}
      endpoint: {{s3_endpoint}}
      region_name: {{s3_region}}
      bucket: {{s3_bucket}}
      regexp: "%s/%s-(.*)-.*.tar"
    params:
      unpack: true
        """ % (path, s3_name, s3_name))

def get_docker_images(pipeline):
    docker_images = set()
    docker_images_filter = lambda x: isinstance(x, dict) and 'type' in x and x['type'] == 'docker-image' and 'repository' in x['source']
    docker_image_nodes = get_yaml_nodes(pipeline, docker_images_filter)
    for docker_image_node in docker_image_nodes:
        docker_image = docker_image_node['source']['repository']
        if 'tag' in docker_image_node['source']:
            docker_image = docker_image+':'+docker_image_node['source']['tag']
        docker_images.add(docker_image)
    return docker_images

def get_resources(pipeline):
    """
    Gets a dictionary keyed on defined resource names with the resource definition as the value
    """
    resources = {}
    for _, resource in dpath.util.search(pipeline, "/resources/*", yielded=True):
        resources[resource['name']] = resource
    return resources

def main(argv):
    parser = argparse.ArgumentParser(description='Processes concourse pipeline dependencies.')
    parser.add_argument('-p --pipeline', dest='pipeline',
                        help='Path to pipelines to process')

    args = parser.parse_args(argv)

    pipeline = load_pipeline(args.pipeline)
    process_pipeline(pipeline)

if __name__ == "__main__":
    main(sys.argv[1:])
