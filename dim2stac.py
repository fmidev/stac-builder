#!/usr/bin/env python

import json
import os
import os.path
import sys
import re
import distro

import configparser
from argparse import ArgumentParser
from pathlib import Path

from datetime import datetime
import urllib
from urllib.parse import urljoin
from urllib.request import urlretrieve

import tempfile

import boto3
import rasterio
import rasterio.features
import rasterio.warp
from bs4 import BeautifulSoup


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--s3cfg', default=str(Path.home()) + '/.s3cfg',
                        help='S3 config file location (default: %(default)s)')
    parser.add_argument('-b', default='bucket', help='S3 bucket (default: %(default)s)')
    parser.add_argument('--b_url', default='s3.amazonaws.com',
                        help='Catalog base url (default: %(default)s)')
    parser.add_argument('--h_url', default='https://base.url',
                        help='Http base url for S3 files (default: %(default)s)')
    parser.add_argument('--s3_prefix', default='prefix',
                        help='S3 prefix for products to be listed (default: %(default)s)')
    parser.add_argument('--node', default='1/1', help='which node out of how many nodes (default: %(default)s)')
    parser.set_defaults(all=True)

    return parser.parse_args()

def set_environment():
    # https://github.com/mapbox/rasterio/commit/b621d92c51f7c2021f89cd4487cecdd7c201f320
    if distro.linux_distribution(full_distribution_name=False)[0] == 'ubuntu':
        print("Using ubuntu")
        os.environ["CURL_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
    # https://trac.osgeo.org/gdal/wiki/CloudOptimizedGeoTIFF
    os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "YES"
    os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = "tif"


def dataFileToS3Path(href):
    if 'VH_db.hdr' in href:
        prefix = 's3://pta/sen1/s1_grd_vv_prep/'
        postfix = '_VV.tif'
    elif 'VV_db.hdr' in href:
        prefix = 's3://pta/sen1/s1_grd_vh_prep/'
        postfix = '_VH.tif'
    else:
        raise Exception('Cannot figure out S3 path for ' + href)

    basename = href[0:href.index('.')]
    return prefix + basename + postfix


def stacFilePath(dataset, dim):
    return 'item/' + os.path.basename(dim).replace(".dim", "") + '_' + dataset + '.json'

def identifyS1Dim(dim):
    tmp = re.search('sen1/(s1_[^/]*)/([^/]*.dim)', dim)
    return tmp.group(1), tmp.group(2)

# https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md
def dim2stac(inputfile, input_uri, baseurl, args):
    def linkTo(link):
        return urljoin(baseurl, link)

    def httpLinkToS3(link):
        tmp = args.h_url
        if tmp[-1] != '/':
            tmp += '/'
        tmp += link[5:]
        return tmp

    itemSpecFileName = os.path.basename(inputfile)

    previous_cwd = os.getcwd()

    try:
        temp = tempfile.NamedTemporaryFile(suffix=".dim")
        urlretrieve(input_uri, temp.name)
    
        with open(temp.name) as fp:
            soup = BeautifulSoup(fp, "lxml")

        identifier = soup.select("Dimap_Document > Dataset_Id > DATASET_NAME")[0].get_text()
        # title = soup.select("Dimap_Document > Dataset_Id > DATASET_SERIES")[0].get_text()
        title = soup.select("Dimap_Document > Dataset_Id > DATASET_NAME")[0].get_text() + ' ' + \
                soup.select("Dimap_Document > Production > PRODUCT_TYPE")[0].get_text()
        datafile_format = soup.select("Dimap_Document > Data_Access > DATA_FILE_FORMAT")[0].get_text()
        assets = {}

        with open(temp.name, 'r') as file :
          dim_xml = file.read()

        # Create STAC assets and modify DIM asset hrefs to HTTPS links
        for data_file in soup.select("Dimap_Document > Data_Access > Data_File"):
            idx = data_file.select("BAND_INDEX")[0].get_text()
            href = data_file.select("DATA_FILE_PATH")[0]['href']
            datafile_uri = httpLinkToS3(href)
            assets['band-' + idx] = {
                'href': datafile_uri,
                'title': 'Band ' + idx,
                'type': 'image/vnd.stac.geotiff; cloud-optimized=true'
            }

            # Replace href in the XML (dirty, but works in this case as the DIMs are homogenous in this sense)
            dim_xml = dim_xml.replace('"{}"'.format(href), '"/vsicurl/{}"'.format(datafile_uri))

        # Write the modified file
        with open(temp.name, 'w') as file:
          file.write(dim_xml)

        os.chdir(os.path.dirname(temp.name))
        with rasterio.open(os.path.basename(temp.name)) as dataset:
            # dataset.count = number of raster bands in dataset
            time = dataset.tags()['PRODUCT_SCENE_RASTER_START_TIME']

            time = datetime.strptime(time, '%d-%b-%Y %H:%M:%S.%f')
            time = datetime.strftime(time, '%Y-%m-%dT%H:%M:%S.%fZ')

            timeEnd = dataset.tags()['PRODUCT_SCENE_RASTER_STOP_TIME']

            timeEnd = datetime.strptime(timeEnd, '%d-%b-%Y %H:%M:%S.%f')
            timeEnd = datetime.strftime(timeEnd, '%Y-%m-%dT%H:%M:%S.%fZ')

            # TODO: ensure that this creates proper polygons and does not just transform corner points
            geom = None
            for g, val in rasterio.features.shapes(dataset.dataset_mask(), transform=dataset.transform):
                geom = rasterio.warp.transform_geom(dataset.crs, 'EPSG:4326', g, precision=6)

            bbox = rasterio.warp.transform_bounds(dataset.crs, 'EPSG:4326', dataset.bounds[0], dataset.bounds[1],
                                                  dataset.bounds[2], dataset.bounds[3])
            ret = {
                'id': identifier,
                'type': 'Feature',
                'geometry': geom,
                'bbox': bbox,
                'properties': {
                    'datetime': time,
                    'title': title,
                    'dtr:start_datetime': time,
                    'dtr:end_datetime': timeEnd
                },
                'links': [{
                    'href': linkTo(itemSpecFileName),
                    'rel': 'self'
                }],
                'assets': assets
            }

    finally:
        temp.close()
        os.chdir(previous_cwd)

    return ret

def list_dims(bucket, http_url, prefix):
    config = configparser.ConfigParser()
    config.read(args.s3cfg)
    access_key = config['default']['access_key']
    secret_key = config['default']['secret_key']
    endpoint_url = config['default']['host_base']

    client = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url='https://' + endpoint_url
    )

    start_after_key = None

    paginator = client.get_paginator('list_objects')
    pages = paginator.paginate(Bucket=bucket, Prefix="{}/".format(prefix))

    ret = []

    for page in pages:
        ret = ret + list(map(lambda obj : obj.get("Key"), page.get("Contents", [])))

    return ret


## The beef

if __name__ == '__main__':
    args = parse_args()
    set_environment()

    catalogBaseUrl = args.b_url
    if catalogBaseUrl[-1] != '/':
        catalogBaseUrl += '/'

    catalogBaseUrl += 'catalog/'

    node_regex = re.match('^([0-9]+)/([0-9]+)$', args.node)
    if node_regex is None:
        raise Exception('{}: illegal value for --node'.format(args.node))

    this_node = int(node_regex.group(1))
    nodes_total = int(node_regex.group(2))


    skiplist = []
    try:
        with open("skiplist", 'r') as file:
            line = file.readline()
            while line:
                try:
                    i = line.index('#')
                    line = line[0:i]
                except ValueError:
                    pass

                line = line.strip()

                skiplist.append(line)

                # Read next line
                line = file.readline()
    except FileNotFoundError:
        pass

    def dimNumber(dim):
        match = re.match('^.*_([0-9A-Za-z]+).dim$', dim)
        if match is None:
            return 0
        return int(match.group(1), 16)

    dims = list_dims(args.b, args.h_url, args.s3_prefix)

    #dims = [ 'sen1/s1_grd_meta_prep/S1_processed_20181012_160705_160730_024105_02A29E.dim' ]

    #print('dims',dims)
    #print('skiplist', skiplist)

    # Filter the ones for this processing node
    dims = list(filter(lambda dim : (dimNumber(dim) % nodes_total) == (this_node-1), dims))

    #print('---- dims for this node', dims)

    dims = [dim for dim in dims if dim not in skiplist]

    #print('---- dims without skiplist', dims)

    #dims = [ 'sen1/s1_grd_meta_prep/S1_processed_20170801_150845_151000_006748_00BDFA.dim' ]

    #dims = [ 'sen1/s1_grd_meta_prep/S1_processed_20171103_152305_152420_008119_00E585.dim' ]

    #dims = [ 'sen1/s1_grd_meta_prep/S1_processed_20181013_150922_151037_024119_02A30E.dim' ]

    dims_to_process = []

    for dim in dims:
        dataset, dim_file = identifyS1Dim(dim)
        itemFileName = stacFilePath(dataset, dim_file)
        
        if os.path.isfile(itemFileName):
            print('{}: already processed ({})'.format(dim, itemFileName))
        else:
            dims_to_process.append(dim)

    print('Processing {} DIM files from S3 (out of {})'.format(len(dims_to_process), len(dims)))

    for dim in dims_to_process:
        try:
            dataset, dim_file = identifyS1Dim(dim)

            dim_uri = args.h_url + dim

            itemFileName = stacFilePath(dataset, dim_file)

            data = dim2stac(itemFileName, dim_uri, catalogBaseUrl, args)

            with open(itemFileName, 'w') as outputfile:
                outputfile.write(json.dumps(data, indent=4))

            print('{}: processed'.format(dim))

        except KeyboardInterrupt:
            raise

        except rasterio.errors.RasterioIOError as e:
            err_msg = str(e);
            if err_msg == 'HTTP response code: 403':
                print("{}: HTTP 403 error, adding to skiplist".format(dim))
                with open("skiplist", 'a') as file:
                    file.write(dim+"\n")

        except Exception as e:
            print("{}: could not process, {}".format(dim, e))

