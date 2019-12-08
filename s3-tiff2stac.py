#!/usr/bin/env python
import configparser
import json
import os
from argparse import ArgumentParser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sh
import boto3
import distro
from osgeo import gdal

import datasetUtils

#PRODUCTS = ["ndvi", "ndbi", "ndti", "ndsi", "ndmi"]
PRODUCTS = ["a550", "air_pressure", "altitude", "amin", "cloud_flags", "ozone", "saa", 
"sdr_oa01_err", "sdr_oa01", "sdr_oa02_err", "sdr_oa02", "sdr_oa03_err", "sdr_oa03", "sdr_oa04_err", "sdr_oa04", 
"sdr_oa05_err", "sdr_oa05", "sdr_oa06_err", "sdr_oa06", "sdr_oa07_err", "sdr_oa07", "sdr_oa08_err", "sdr_oa08", 
"sdr_oa09_err", "sdr_oa09", "sdr_oa10_err", "sdr_oa10", "sdr_oa11_err", "sdr_oa11", "sdr_oa12_err", "sdr_oa12", 
"sdr_oa16_err", "sdr_oa16", "sdr_oa17_err", "sdr_oa17", "sdr_oa18_err", "sdr_oa18", "sdr_oa21_err", "sdr_oa21", 
"sdr_s1n_err", "sdr_s1n", "sdr_s1o_err", "sdr_s1o", "sdr_s2n_err", "sdr_s2n", "sdr_s2o_err", "sdr_s2o", 
"sdr_s3n_err", "sdr_s3n", "sdr_s3o_err", "sdr_s3o", "sdr_s5n_err", "sdr_s5n", "sdr_s5o_err", "sdr_s5o", 
"sdr_s6n_err", "sdr_s6n", "sdr_s6o_err", "sdr_s6o", "syn_flags", "sza", "t550_err", "t550", "water_vapour"]

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


def list_products(bucket, http_url, prefix):
    def get_date(image):
        idates = image.split('_')
        isyn = idates.index('syn')
        if idates.count('syn') == 1:
            fdate = idates[isyn+1]
        else :
            fdate = idates[isyn+3]
        return fdate
#        return image[-21:-4]

    def flatten(image_products):
        res = defaultdict(dict)
        [res[v[0]].update(**v[1]) for v in image_products]
        return res

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

    product_images = [
        (get_date(url), {product: url})
        for product in PRODUCTS for url in
        map(lambda content: http_url + content["Key"],
            client.list_objects(Bucket=bucket, Prefix="{}_{}/".format(prefix, product)).get("Contents", [])
            )]

    return flatten(product_images)


def stac_file_path(date_range):
    return "item/S3s_{}.json".format(date_range)


def tiff_to_stac(item_file_name, dates, products, baseurl):
    def link_to(link):
        return os.path.join(baseurl, link)

    identifier = "S3s_{}".format(dates)
    title = "Sentinel 3 synergy - {}".format(dates)

    assets = {
        product_name: {
            'href': url,
            'title': product_name.upper(),
            'type': 'image/vnd.stac.geotiff; cloud-optimized=true'
        } for product_name, url in products.items()
    }

    if len(dates) > 8:
        time = datetime.strptime(dates.split('_')[0], '%Y%m%d')
        time = datetime.strftime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
        time_end = datetime.strptime(dates.split('_')[1], '%Y%m&d')
        time_end = datetime.strftime(time_end, '%Y-%m-%dT%H:%M:%S.%fZ')
    else:
        time = datetime.strptime(dates, '%Y%m%d')
        time = datetime.strftime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
        time_end = datetime.strptime(dates, '%Y%m%d')
        time_end = datetime.strftime(time_end, '%Y-%m-%dT%H:%M:%S.%fZ')
   
    ds = gdal.Open("/vsicurl/" + list(products.values())[0])

    geom, bbox = datasetUtils.get_geom_and_bbox_from_ds(ds)

    ret = {
        'id': identifier,
        'type': 'Feature',
        'geometry': geom,
        'bbox': bbox,
        'properties': {
            'datetime': time,
            'title': title,
            'dtr:start_datetime': time,
            'dtr:end_datetime': time_end
        },
        'links': [{
            'href': link_to(item_file_name),
            'rel': 'self'
        }],
        'assets': assets
    }

    return ret


if __name__ == '__main__':
    args = parse_args()
    set_environment()

    tiffs = list_products(args.b, args.h_url, args.s3_prefix)
    overwrite = True

    for dates, products in tiffs.items():
        item_file_name = stac_file_path(dates)
        if not overwrite and os.path.isfile(item_file_name):
            print('{}: already processed ({})'.format(dates, item_file_name))
        else:
            print('{}: processing'.format(dates))
            data = tiff_to_stac(item_file_name, dates, products, args.b_url)
            with open(item_file_name, "w") as outputfile:
                outputfile.write(json.dumps(data, indent=2))
