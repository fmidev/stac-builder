#!/usr/bin/env python

import json
import os
import os.path
import sys
from datetime import datetime
from urllib.parse import urljoin

import rasterio
import rasterio.features
import rasterio.warp
from bs4 import BeautifulSoup


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


def stacFilePath(dim):
    return 'item/' + os.path.basename(dim).replace(".dim", "") + '.json'


# https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md
def dim2stac(inputfile, baseurl):
    def linkTo(link):
        return urljoin(baseurl, link)

    def httpLinkToS3(link):
        tmp = dataFileToS3Path(link)
        tmp = 'https://pta.data.lit.fmi.fi/' + tmp[9:]
        return tmp

    def dataFilePath(href):
        return os.path.dirname(inputfile) + '/' + href

    itemSpecFileName = os.path.basename(inputfile).replace(".dim", "") + '.json'

    with open(inputfile) as fp:
        soup = BeautifulSoup(fp, "lxml")

    identifier = soup.select("Dimap_Document > Dataset_Id > DATASET_NAME")[0].get_text()
    # title = soup.select("Dimap_Document > Dataset_Id > DATASET_SERIES")[0].get_text()
    title = soup.select("Dimap_Document > Dataset_Id > DATASET_NAME")[0].get_text() + ' ' + \
            soup.select("Dimap_Document > Production > PRODUCT_TYPE")[0].get_text()
    datafile_format = soup.select("Dimap_Document > Data_Access > DATA_FILE_FORMAT")[0].get_text()
    assets = {}

    files_to_delete = []

    for data_file in soup.select("Dimap_Document > Data_Access > Data_File"):
        idx = data_file.select("BAND_INDEX")[0].get_text()
        href = data_file.select("DATA_FILE_PATH")[0]['href']

        assets['band-' + idx] = {
            'href': httpLinkToS3(href),
            'title': 'Band ' + idx,
            'type': 'image/vnd.stac.geotiff; cloud-optimized=true'
        }

        datafile_path = dataFilePath(href)

        if not os.path.isfile(datafile_path):
            datafile_s3path = dataFileToS3Path(href)
            print('{}: does not exist, downloading from {}'.format(datafile_path, datafile_s3path))

            os.system('s3cmd get {} {}'.format(datafile_s3path, datafile_path))

            files_to_delete.append(datafile_path)

    with rasterio.open(inputfile) as dataset:
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

    for delete_this in files_to_delete:
        print('{}: removing temporary tif'.format(delete_this))
        os.remove(delete_this)

    return ret


## The beef

if __name__ == '__main__':
    catalogBaseUrl = 'https://stac.fmi.fi/stac/catalog/'

    for dim in sys.argv[1:]:

        itemFileName = stacFilePath(dim)
        if os.path.isfile(itemFileName):
            print('{}: already processed ({})'.format(dim, itemFileName))
        else:
            print('{}: processing'.format(dim))

            data = dim2stac(dim, 'https://stac.fmi.fi/stac/catalog/')
            with  open(itemFileName, 'w') as outputfile:
                outputfile.write(json.dumps(data, indent=4))
