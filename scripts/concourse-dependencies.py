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
try:
    os.makedirs(tmp_dir)
except: pass


def handle_get_resource(pipeline, get_resource_block, resource_definition, git_repos_dir, github_releases_dir, pivnet_resources_dir, docker_images_dir):
    """
    Downloads and saves everything required to provide this resource to the pipeline.
    """
    print("Getting "+resource_definition['type']+" resource " + get_resource_block['get'])
    if resource_definition['type'] == 'git':
        clone_git_repo(pipeline, resource_definition, git_repos_dir)
    if resource_definition['type'] == 'github-release':
        download_github_releases(resource_definition, github_releases_dir)
    elif resource_definition['type'] == 'pivnet':
        globs = '**'
        if 'params' in get_resource_block and 'globs' in get_resource_block['params']:
            globs = get_resource_block['params']['globs']
        save_pivnet_resource(resource_definition, globs, pivnet_resources_dir)
    else:
        print("Unable to get resources for unhandled resource type " + resource_definition['type'])

def process_pipeline(pipeline, git_repos_dir, github_releases_dir, pivnet_resources_dir, docker_images_dir):
    resource_definitions = get_resources(pipeline)
    handled_resources = []
    get_resource_filter = lambda x: isinstance(x, dict) and 'get' in x
    get_resource_blocks = get_yaml_blocks(pipeline, False, None, get_resource_filter)
    for b in get_resource_blocks:
        resource_name = b['get']
        if 'resource' in b:
            resource_name = b['resource']
        if resource_name not in handled_resources:
            handle_get_resource(pipeline, b, resource_definitions[resource_name], git_repos_dir, github_releases_dir, pivnet_resources_dir, docker_images_dir)
            handled_resources.append(resource_name)

    # find all docker images for this pipeline
    docker_images = get_docker_images(pipeline, git_repos_dir, pivnet_resources_dir, docker_images_dir)
    for i in docker_images:
        save_docker_image(i, docker_images_dir)

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

def get_yaml_blocks(pipeline, recursive, resource_dirs, filter=lambda x: True,):
    resources = []
    get_yaml_blocks_from_yaml(pipeline, filter, resources)
    if recursive:
        for _, referenced_yaml in get_referenced_yamls(pipeline):
            for resource_dir in resource_dirs:
                try:
                    yml_str = open(join(resource_dir, referenced_yaml)).read()
                    print("Loading referenced yaml at "+str(join(resource_dir, referenced_yaml)))
                    yml = yaml.load(yml_str)
                    get_yaml_blocks_from_yaml(yml, filter, resources)
                except:
                    print("Unable to load referenced yaml at "+str(join(resource_dir, referenced_yaml)))
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

def get_docker_images(pipeline, git_repos_dir, pivnet_resources_dir, docker_images_dir):
    docker_images = set()
    docker_images_filter = lambda x: isinstance(x, dict) and 'type' in x and x['type'] == 'docker-image' and 'repository' in x['source']
    docker_image_resources = get_yaml_blocks(pipeline, True, [tmp_dir, git_repos_dir, pivnet_resources_dir], docker_images_filter)
    for resource in docker_image_resources:
        docker_image = resource['source']['repository']
        if 'tag' in resource['source']:
            docker_image = docker_image+':'+resource['source']['tag']
        docker_images.add(docker_image)
    return docker_images

def save_docker_image(image, docker_images_dir):
    call(["docker", "pull", image])
    call(["docker", "save", image, "-o", join(docker_images_dir, image.replace('/', '_').replace(':', '_')+".tar")])

def get_git_repos(pipeline):
    resources = []
    for path, resource in dpath.util.search(pipeline, "/resources/*", yielded=True):
        if resource['type'] == 'git':
            resources.append(resource)
    return resources

def clone_git_repo(resource, git_repos_dir):
    """
    This method clones a pipeline git resource.  It currently only supports public
    and HTTPS-private with provided username+password.
    """
    # clone to a temporary directory to examine their files
    remote_uri = resource['source']['uri']
    if 'username' in resource['source'] and 'password' in resource['source']:
        remote_uri = re.sub('https://', 'https://'+resource['source']['username']+":"+resource['source']['password']+'@', remote_uri)

    repo = git.Repo.init(join(git_repos_dir, resource['name']))

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

def get_github_releases(resource_definition):
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    if 'access_token' in resource_definition['source']:
        headers['Authorization'] = 'Token '+resource_definition['source']['access_token']

    releases_url = 'https://api.github.com/repos/'+resource_definition['source']['user']+'/'+resource_definition['source']['repository']+'/releases'
    r = requests.get(releases_url, headers=headers)
    releases_json = r.json()
    print(releases_json)
    return releases_json

def download_github_releases(resource_definition, github_releases_dir):
    releases = get_github_releases(resource_definition)

    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }

    # Create the local directory to hold this release's files
    local_dir = join(github_releases_dir, resource_definition['source']['user'], resource_definition['source']['repository'], releases[0]['name'])
    try:
        os.makedirs(local_dir)
    except: pass

    # Download all assets for the most recent release
    # TODO: handle a specific version if this is specified in the resource_definition
    # TODO: handle filtering based on the glob specified as a param in the job descriptor
    for asset in releases[0]['assets']:
        local_file = join(local_dir, asset['name'])
        download_url = asset['browser_download_url']
        download_file(download_url, headers, local_file, None, True)

def get_pivnet_resources(pipeline):
    pivnet_resources_filter = lambda x: isinstance(x, dict) and 'type' in x and x['type'] == 'pivnet'
    pivnet_resources = get_yaml_blocks(pipeline, False, None, pivnet_resources_filter)
    for resource in pivnet_resources:
        save_pivnet_resource(resource)
    return pivnet_resources

def save_pivnet_resource(resource, filename_globs, pivnet_resources_dir):
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
    download_pivnet_product_release_files(token, product_slug, product_release, filename_globs, pivnet_resources_dir)

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

def get_pivnet_product_release_files(token, product_slug, release, filename_globs):
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
            if fnmatch.fnmatch(f['aws_object_key'], g):
                filename_match = True
                break
        if filename_match:
            filtered_files_json.append(f)
    # print("Pivnet product "+product_slug+", release "+str(release)+", files:")
    # for f in filtered_files_json:
    #     print(f['name'])
    return filtered_files_json

def download_pivnet_product_release_dependencies(token, product_slug, release, pivnet_resources_dir):
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Token '+token,
        'Content-Length': '0',
        'Content-Type': 'application/json'
    }
    r = requests.get('https://network.pivotal.io/api/v2/products/'+product_slug+'/releases/'+str(release)+'/dependencies', headers=headers)
    deps_json = r.json()
    for dep in deps_json['dependencies']:
        if dep['release']['product']['slug'] == 'stemcells':
            download_pivnet_product_release_files(token, 'stemcells', dep['release']['id'], '**', pivnet_resources_dir)
        else:
            # TODO update to download dependency *.pivotal products, but must disambiguate multiple versions
            continue
    return deps_json

def download_pivnet_product_release_files(token, product_slug, release_id, filename_globs, pivnet_resources_dir):
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
        pivnet_product_slug_dir = join(pivnet_resources_dir, product_slug)
        try:
            os.makedirs(pivnet_product_slug_dir)
        except: pass

        local_file = join(pivnet_product_slug_dir, os.path.basename(f['aws_object_key']))

        # only download if the file doesn't already exist or if the local sha256 differs from the pivnet-provided hash
        download_url = 'https://network.pivotal.io/api/v2/products/'+product_slug+'/releases/'+str(release_id)+'/product_files/'+str(file_id)+'/download'
        download_file(download_url, headers, local_file, f['sha256'], False)

        # A special case:  extract pcf-pipelines packaged in a tarball so we can find referenced tasks inside it
        # TODO: would love to find a way to make this general for any tarballed repo, but not sure how prevailent
        # the pattern is beyond pivnet publishing of pcf-pipelines.
        if product_slug == 'pcf-automation' and local_file.endswith(".tgz"):
            call(["tar", "-xzvf", local_file, "-C", tmp_dir])

        download_pivnet_product_release_dependencies(token, product_slug, release_id, pivnet_resources_dir)

def download_file(url, headers, local_file, sha256=None, redownload=True):
    if redownload or not os.path.isfile(local_file) or (sha256 is not None and sha256 != sha256_file(local_file)):
        r = requests.get(url, headers=headers, stream=True)
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

        if sha256 is not None:
            # Compare the downloaded file's sha256 hash with the one provided
            file_hash = sha256_file(local_file)
            if file_hash != sha256:
                raise Exception("The downloaded file "+local_file+" is corrupted.\nExpected SHA256: "+sha256+"\nDownloaded SHA256: "+file_hash)
            else:
                print("Success... downloaded file SHA256: " + file_hash)

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
    parser.add_argument('-g --git-repo-dir', dest='git_repos_dir', default='tmp/git-repos',
                        help='Output location for all cloned git repo resources')
    parser.add_argument('-r --github-releases-dir', dest='github_releases_dir', default='tmp/github-releases',
                        help='Output location for all cloned git repo resources')
    parser.add_argument('-n --pivnet-resource-dir', dest='pivnet_resources_dir', default='tmp/pivnet-resources',
                        help='Output location for all downloaded pivnet resources')
    parser.add_argument('-d --docker-images-dir', dest='docker_images_dir', default='tmp/git-repos',
                        help='Output location for all downloaded pivnet resources')
    try:
        os.makedirs(args.git_repos_dir)
    except: pass

    try:
        os.makedirs(args.github_releases_dir)
    except: pass

    try:
        os.makedirs(args.docker_images_dir)
    except: pass

    try:
        os.makedirs(args.pivnet_resource_dir)
    except: pass

    args = parser.parse_args(argv)
    params = {}
    if 'params' in args and args.params is not None:
        for params_path in args.params:
            p = open(params_path)
            curr_params = yaml.load(p)
            params.update(curr_params)

    for pipeline_path in args.pipelines:
        pipeline = load_pipeline(pipeline_path, params)
        process_pipeline(pipeline, args.git_repos_dir, args.github_releases_dir, args.pivnet_resources_dir, args.docker_images_dir)

if __name__ == "__main__":
    main(sys.argv[1:])
