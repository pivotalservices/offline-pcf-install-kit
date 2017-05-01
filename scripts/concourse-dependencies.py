#!/bin/python

"""
Dependencies:

System:  git, docker, pivnet-cli
Python:  GitPython, dpath, pyyaml
"""

import sys
from subprocess import call
import os
from os.path import join
import fnmatch
import argparse
import re
import hashlib
import yaml
import dpath.util
import git
import requests

tmp_dir = 'tmp'

tmp_resource_dir = join(tmp_dir, 'resources')
try:
    os.makedirs(tmp_resource_dir)
except: pass

docker_images_dir = join(tmp_dir, 'docker_images')
try:
    os.makedirs(docker_images_dir)
except: pass

pivnet_resource_dir = join(tmp_dir, 'pivnet-resources')
try:
    os.makedirs(pivnet_resource_dir)
except: pass


def handle_get_resource(pipeline, get_resource_block, resource_definition):
    """
    Downloads and saves everything required to provide this resource to the pipeline.
    """
    print("Getting "+resource_definition['type']+" resource " + get_resource_block['get'])
    if resource_definition['type'] == 'git':
        clone_git_repo(pipeline, resource_definition)
    elif resource_definition['type'] == 'pivnet':
        globs = '**'
        if 'params' in get_resource_block and 'globs' in get_resource_block['params']:
            globs = get_resource_block['params']['globs']
        save_pivnet_resource(resource_definition, globs)
    else:
        print("Unable to get resources for unhandled resource type " + resource_definition['type'])

def process_pipeline(pipeline):
    resource_definitions = get_resources(pipeline)
    handled_resources = []
    get_resource_filter = lambda x: isinstance(x, dict) and 'get' in x
    get_resource_blocks = get_yaml_blocks(pipeline, get_resource_filter, False)
    for b in get_resource_blocks:
        resource_name = b['get']
        if 'resource' in b:
            resource_name = b['resource']
        if resource_name not in handled_resources:
            handle_get_resource(pipeline, b, resource_definitions[resource_name])
            handled_resources.append(resource_name)

    # # Clone any git repositories so that we can find things in their YAML files as well
    # for resource in get_git_repos(pipeline):
    #     print(yaml.dump(resource))
    #
    # # Download all of the pivnet resources and their dependencied (other pivnet products and stemcells)
    # for resource in get_pivnet_resources(pipeline):
    #     print(yaml.dump(resource))

    # find all docker images for this pipeline
    docker_images = get_docker_images(pipeline)
    for i in docker_images:
        print(i)

def load_pipeline(pipeline_path, params):
    """
    Loads a pipeline at the given path and replaces any instances of Fly's variable
    {{...}} with the value in the params dictionary.
    """
    print("Loading pipeline " + pipeline_path)
    pipeline_str = open(pipeline_path).read()
    for param, value in params.iteritems():
        if value is None:
            value = ''
        pipeline_str = re.sub('{{'+param+'}}', str(value), pipeline_str)
    pipeline = yaml.load(pipeline_str)
    return pipeline

def get_referenced_yamls(pipeline):
    """
    Finds all referenced YAML files in this pipeline.  This allows us to look for
    these files in any loaded resources as well as this directory to process dependencies.
    """
    return dpath.util.search(pipeline, "/**", afilter=lambda x: isinstance(x, basestring) and x.endswith('.yml'), yielded=True)

def get_yaml_blocks(pipeline, filter=lambda x: True, recursive=True):
    resources = []
    get_yaml_blocks_from_yaml(pipeline, filter, resources)
    if recursive:
        for _, referenced_yaml in get_referenced_yamls(pipeline):
            yml_str = open(join(tmp_resource_dir, referenced_yaml)).read()
            yml = yaml.load(yml_str)
            get_yaml_blocks_from_yaml(yml, filter, resources)
    return resources

def get_yaml_blocks_from_yaml(yml, filter, resources):
    for path, resource in dpath.util.search(yml, "/**", yielded=True):
        if filter(resource):
            resources.append(resource)

def get_resources(pipeline):
    """
    Gets a dictionary keyed on defined resource names with the resource definition as the value
    """
    resources = {}
    for _, resource in dpath.util.search(pipeline, "/resources/*", yielded=True):
        resources[resource['name']] = resource
    return resources

def get_docker_images(pipeline):
    docker_images = []
    docker_images_filter = lambda x: isinstance(x, dict) and 'type' in x and x['type'] == 'docker-image' and 'repository' in x['source']
    docker_image_resources = get_yaml_blocks(pipeline, docker_images_filter)
    for resource in docker_image_resources:
        docker_image = resource['source']['repository']
        if 'tag' in resource['source']:
            docker_image = docker_image+':'+resource['source']['tag']
        docker_images.append(docker_image)
        save_docker_image(docker_image)
    return docker_images

def save_docker_image(image):
    call(["docker", "pull", image])
    call(["docker", "save", image, "-o", join(docker_images_dir, image.replace('/', '_').replace(':', '_')+".tar")])

def get_git_repos(pipeline):
    resources = []
    for path, resource in dpath.util.search(pipeline, "/resources/*", yielded=True):
        if resource['type'] == 'git':
            resources.append(resource)
            clone_git_repo(pipeline, resource)
    return resources

def clone_git_repo(resource):
    """
    This method clones a pipeline git resource.  It currently only supports public
    and HTTPS-private with provided username+password.
    """
    # clone to a temporary directory to examine their files
    remote_uri = resource['source']['uri']
    if 'username' in resource['source'] and 'password' in resource['source']:
        remote_uri = re.sub('https://', 'https://'+resource['source']['username']+":"+resource['source']['password']+'@', remote_uri)

    repo = git.Repo.init(join(tmp_resource_dir, resource['name']))

    try:
        origin = repo.create_remote('origin', remote_uri)
    except:
        origin = repo.remotes.origin

    assert origin.exists()
    assert origin == repo.remotes.origin == repo.remotes['origin']
    origin.fetch()
    # Setup a local tracking branch of a remote branch
    branch = 'master'
    if 'branch' in resource['source']:
        branch = resource['source']['branch']
    repo.create_head(branch, origin.refs[branch])  # create local branch branch from remote branch
    repo.heads[branch].set_tracking_branch(origin.refs[branch])  # set local branch to track remote branch
    repo.heads[branch].checkout()  # checkout local branch to working tree
    origin.pull()

def get_pivnet_resources(pipeline):
    pivnet_resources_filter = lambda x: isinstance(x, dict) and 'type' in x and x['type'] == 'pivnet'
    pivnet_resources = get_yaml_blocks(pipeline, pivnet_resources_filter, False)
    for resource in pivnet_resources:
        save_pivnet_resource(resource)
    return pivnet_resources

def save_pivnet_resource(resource, filename_globs=['**']):
    print("Downloading pivnet resource: "+yaml.dump(resource))
    token = resource['source']['api_token']
    product_slug = resource['source']['product_slug']
    product_version = '**'
    if 'product_version' in resource['source']:
        product_version = resource['source']['product_version']

    # get the release ID of the latest release matching the version glob in the pipeline resource
    product_releases = get_pivnet_product_releases(token, product_slug, product_version)
    product_release = product_releases[0]['id']

    get_pivnet_product_accept_eula(token, product_slug, product_release)
    download_pivnet_product_release_files(token, product_slug, product_release, filename_globs)

def get_pivnet_products(token):
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    r = requests.get('https://network.pivotal.io/api/v2/products', headers=headers)
    products_json = r.json()
    print(products_json)
    return products_json

def get_pivnet_product(token, product_slug):
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    r = requests.get('https://network.pivotal.io/api/v2/products/'+product_slug, headers=headers)
    products_json = r.json()
    print(products_json)
    return products_json

def get_pivnet_product_releases(token, product_slug, version_glob='**'):
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    r = requests.get('https://network.pivotal.io/api/v2/products/'+product_slug+'/releases', headers=headers)
    releases_json = r.json()
    filtered_releases_json = []
    for r in releases_json['releases']:
        version_match = fnmatch.fnmatch(r['version'], version_glob)
        if version_match:
            filtered_releases_json.append(r)
    # print("Pivnet product "+product_slug+", releases:")
    # for r in filtered_releases_json:
    #     print(r['version'])
    return filtered_releases_json

def get_pivnet_product_accept_eula(token, product_slug, release):
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    r = requests.post('https://network.pivotal.io/api/v2/products/'+product_slug+'/releases/'+str(release)+"/eula_acceptance", headers=headers)
    if r.status_code != 200:
        print(str(r))
        raise Exception("There was a problem accepting the EULA for product "+product_slug+" release " + release)

def get_pivnet_product_release_files(token, product_slug, release, filename_globs=['**']):
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    r = requests.get('https://network.pivotal.io/api/v2/products/'+product_slug+'/releases/'+str(release)+'/product_files', headers=headers)
    files_json = r.json()
    filtered_files_json = []
    # wrap a single string glob as a 1-element list
    if isinstance(filename_globs, basestring):
        filename_globs = [ filename_globs ]
    for f in files_json['product_files']:
        filename_match = False
        for g in filename_globs:
            print("Checking if file "+f['aws_object_key']+" matches pattern " + g)
            if fnmatch.fnmatch(f['aws_object_key'], g):
                filename_match = True
                break
        if filename_match:
            filtered_files_json.append(f)
    # print("Pivnet product "+product_slug+", release "+str(release)+", files:")
    # for f in filtered_files_json:
    #     print(f['name'])
    return filtered_files_json

def download_pivnet_product_release_files(token, product_slug, release_id, filename_globs=['**']):
    print("Downloding pivnet product "+product_slug+" release "+str(release_id)+" files matching " + str(filename_globs))
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    for f in get_pivnet_product_release_files(token, product_slug, release_id, filename_globs):
        file_id = f['id']
        print(str(f))
        pivnet_product_slug_dir = join(pivnet_resource_dir, product_slug)
        try:
            os.makedirs(pivnet_product_slug_dir)
        except: pass

        local_file = join(pivnet_product_slug_dir, os.path.basename(f['aws_object_key']))

        # only download if the file doesn't already exist or if the local sha256 differs from the pivnet-provided hash
        if not os.path.isfile(local_file) or sha256_file(local_file) != f['sha256']:
            # Download the file from pivnet
            r = requests.get('https://network.pivotal.io/api/v2/products/'+product_slug+'/releases/'+str(release_id)+'/product_files/'+str(file_id)+'/download', headers=headers, stream=True)
            total_length = r.headers.get('content-length')
            total_length = int(total_length)
            bytes_read = 0
            with open(local_file, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=4096):
                    bytes_read += len(chunk)
                    fd.write(chunk)
                    progress = int(50 * bytes_read / total_length)
                    sys.stdout.write("\r[%s%s]" % ('=' * progress, ' ' * (50-progress)))
                    sys.stdout.flush()

            # Compare the downloaded file's sha256 hash with the one provided by pivnet itself
            file_hash = sha256_file(local_file)
            if file_hash != f['sha256']:
                raise Exception("The file for product "+product_slug+" release "+str(release_id)+" file "+str(file_id)+" is corrupted.\nExpected SHA256: "+f['sha256']+"\nDownloaded SHA256: "+sha256.hexdigest())
            else:
                print("Success... SHA256: " + file_hash)

def sha256_file(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as fd:
        for block in iter(lambda: fd.read(65536), b''):
            sha256.update(block)
    return sha256.hexdigest()

def main(argv):
    parser = argparse.ArgumentParser(description='Processes concourse pipeline dependencies.')
    parser.add_argument('-p --pipelines', dest='pipelines', nargs='+',
                        help='Path to pipelines to process')
    parser.add_argument('-l --with-vars', dest='params', nargs='*',
                        help='Path to params YAML files to replace Fly {{..}} values')

    args = parser.parse_args(argv)

    params = {}
    if 'params' in args and args.params is not None:
        for params_path in args.params:
            p = open(params_path)
            curr_params = yaml.load(p)
            params.update(curr_params)

    for pipeline_path in args.pipelines:
        pipeline = load_pipeline(pipeline_path, params)
        process_pipeline(pipeline)

if __name__ == "__main__":
    main(sys.argv[1:])
