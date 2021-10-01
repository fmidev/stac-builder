from datetime import datetime
import os
import re
import json 
import osgeo
from osgeo import gdal
import boto3
import time
import isodate
import copy
import requests
from bs4 import BeautifulSoup

import helpers as h
import cloud_optimized_geotiff_validator as geotiff_validator
import metadata_builder

def item_builder(conf, s3client):
    '''
    Function reads urls from S3 and creates items. Items are collections of assets/bands. 
    Input: configuration file of dataset and of s3 information.
    Output: writes items to specified location.
    '''
    
    fileNamingConvention = conf["item"]["fileNamingConvention"]
    idTemplate = conf["item"]["idTemplate"]
    blacklist = conf["blacklist"]
    
    s3Bucket = conf["source"]["s3Bucket"]
    s3Prefixes = conf["source"]["s3Prefixes"]
    publicUrlPrefix = conf["source"]["publicUrlPrefix"]

    for s3Prefix in s3Prefixes:
        nextToken = ''

        while True:
            try:
                response = s3client.list_objects_v2(Bucket=s3Bucket, Prefix=s3Prefix, ContinuationToken=nextToken)
                contents = response['Contents']
            except:
                print("An error occurred with prefix", s3Prefix)
                break

            for file in contents:
                url = publicUrlPrefix + file['Key']
                
                # Check if url is in blacklist
                if url in blacklist: 
                    continue

                # Extract filename from url
                filename = url.split("/")[-1] 
                print("Processing", filename)

                if "gdalUrlPrefix" in conf["source"]:
                    url_gdal = conf["source"]["gdalUrlPrefix"] + file['Key']
                else:
                    url_gdal = publicUrlPrefix + file['Key']

                # Metadata processing
                if "metadata" in conf["item"]: # add Sentinel-1 metadata
                    metadata_builder.metadata_builder(conf, filename, url, url_gdal)
                    continue
                                        
                # Find date and band from filename using fileNameConvention
                # and regular expressions (regex: https://docs.python.org/3/howto/regex.html)
                p = re.compile(fileNamingConvention)
                m = p.search(filename)
                
                try: # Check if filename is in expected format
                    
                    startdate = m.group('startdate')
                    try:
                        bandname = m.group('band')
                        if bandname == "":
                            bandname = conf["item"]["missingbandname"]
                        band = bandname.lower() # lowercase
                    except:
                        band = conf["item"]["bandname"] # if there is no band in filename
                    try:
                        enddate = m.group('enddate')
                    except IndexError: # if the filename does not contain an enddate
                        enddate = None
                        end = None  
                    try:
                        starttime = m.group('starttime')
                        endtime = m.group('endtime')
                    except IndexError:
                        starttime = None
                        endtime = None
                    try:
                        tile = m.group('tile')
                    except:
                        tile = None
                        
                except AttributeError: # if filename does not match expected format
                    print(filename, "does not match file naming convention")
                    continue

                # Create id using item.idTemplate
                id = idTemplate

                if tile:
                    id = id.replace("tile_id", tile)
                
                # extract dates 
                if enddate is not None: # filenames with enddate
                    if len(enddate) == 2: # if year is given in two digits
                        start_id = "20" + startdate
                        id = id.replace("startdate", start_id)
                        start = datetime(int(start_id), 1, 1, 0,0,0)
                        start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                        end_id = "20" + enddate
                        id = id.replace("enddate", end_id)
                        end = datetime(int(end_id), 12, 31, 23,59,59)
                        end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                        date_isoformat = None
                    elif len(enddate) == 4: # if year is given in 4 digits
                        id = id.replace("startdate", startdate)
                        id = id.replace("enddate", enddate)
                        start = datetime(int(startdate), 1, 1, 0,0,0)
                        start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                        end = datetime(int(enddate), 12, 31, 23,59,59)
                        end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                        date_isoformat = None
                    elif len(enddate) == 8: # if dates are given in 8 digits
                        start_id = startdate[0:4] +'-'+ startdate[4:6] +'-'+ startdate[6:8]
                        id = id.replace("startdate", start_id)
                        end_id = enddate[0:4] +'-'+ enddate[4:6] +'-'+ enddate[6:8]
                        id = id.replace("enddate", end_id)
                        if starttime: # with hours, minutes and seconds
                            start = datetime(int(startdate[0:4]), int(startdate[4:6]), int(startdate[6:8], int(starttime[0:2]), int(starttime[2:4]), int(starttime[4:6])))
                            start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                            end = datetime(int(enddate[0:4]), int(enddate[4:6]), int(enddate[6:8]), int(endtime[0:2]), int(endtime[2:4]), int(endtime[4:6]))
                            end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                        else:
                            start = datetime(int(startdate[0:4]), int(startdate[4:6]), int(startdate[6:8]), 0, 0, 0)
                            start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                            end = datetime(int(enddate[0:4]), int(enddate[4:6]), int(enddate[6:8]), 23,59,59)
                            end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                        date_isoformat = None
                    else:
                        print("Unrecognized time format in", filename)
                        continue
                else: # filenames without enddate
                    if len(startdate) == 2:
                        start_id = "20" + startdate
                        id = id.replace("startdate", start_id)
                        start = datetime(int(start_id), 1, 1, 0,0,0)
                        end = datetime(int(start_id), 12, 31, 23,59,59)
                        date_isoformat = None
                        start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                        end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                    elif len(startdate) == 4:
                        id = id.replace("startdate", startdate)
                        start = datetime(int(startdate), 1, 1, 0,0,0)
                        end = datetime(int(startdate), 12, 31, 23,59,59)
                        date_isoformat = None
                        start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                        end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                    elif len(startdate) == 8:    
                        start_id = startdate[0:4] +'-'+ startdate[4:6] +'-'+ startdate[6:8]    
                        id = id.replace("startdate", start_id)
                        
                        if endtime: # with start and endtime
                            start = datetime(int(startdate[0:4]), int(startdate[4:6]), int(startdate[6:8]), int(starttime[0:2]), int(starttime[2:4]), int(starttime[4:6]))
                            start_isoformat = start.isoformat(timespec='seconds') + 'Z'
                            end = datetime(int(startdate[0:4]), int(startdate[4:6]), int(startdate[6:8]), int(endtime[0:2]), int(endtime[2:4]), int(endtime[4:6]))
                            end_isoformat = end.isoformat(timespec='seconds') + 'Z'
                            date_isoformat = None
                        else: # only date
                            date = datetime(int(startdate[0:4]), int(startdate[4:6]), int(startdate[6:8]), 0, 0, 0)
                            date_isoformat = date.isoformat(timespec='seconds') + 'Z'
                            start_isoformat = None
                            end_isoformat = None
                    elif len(startdate) == 10:
                        if "_" in startdate:
                            startdate = startdate.replace("_", "-")
                        id = id.replace("startdate", startdate)
                        date = datetime(int(startdate[0:4]), int(startdate[5:7]), int(startdate[8:10]))
                        date_isoformat = date.isoformat(timespec='seconds') + 'Z'
                        start_isoformat = None
                        end_isoformat = None
                    else:
                        print("Unrecognized time format in", filename)
                        continue
                    if starttime is not None:
                        id = id + "_" + starttime

                self_link = conf["destination"]["itemBaseUrl"] + id + ".json"
                
                if "gdalUrlPrefix" in conf["source"]:
                    url_gdal = conf["source"]["gdalUrlPrefix"] + file['Key']
                else:
                    url_gdal = publicUrlPrefix + file['Key']
                
                # Check if item already exists
                local_item_path = conf["destination"]["localItemPath"] + id + ".json"
            
                if os.path.isfile(local_item_path): # if item already exists
                    item_path = open(local_item_path)
                    item = json.load(item_path)
                    assets = list(item["assets"].keys())
                    if band in assets: # if band already exists
                        continue # do nothing
                    else: # if band does not exist
                        
                        # Read the dataset
                        download_tries = 5
                        while download_tries > 0 :
                            ds = gdal.Open("/vsicurl/" + url_gdal)
                            if ds == None: # if there is an error while reading
                                download_tries = download_tries - 1
                                time.sleep(1)
                                continue
                            else:
                                break # success in dowloading
                        if download_tries == 0:
                            break # if cannot download go to "for file in response" -loop
                        
                        # check media type
                        try:
                            geotiff_validator.validate(ds, check_tiled=True, full_check=False)
                            media_type = "image/tiff; application=geotiff; profile=cloud-optimized" 
                        except:
                            media_type = "image/tiff; application=geotiff" 
                        
                        # add asset information to item
                        new_asset = {"assets": {band: {
                            "href": url,
                            "title": band,
                            "type": media_type,
                            "roles": conf["item"]["roles"]}}}
                        old_item = copy.deepcopy(item)
                        merged = h.merge(dict(old_item), new_asset)

                        # Write item json files into destination.localItemPath
                        with open(local_item_path, 'w') as outfile: # change w to x when works
                            json.dump(merged, outfile)
                
                else: # if item does not exist already, create new item
                    # Check mosaicDuration 
                    if conf["item"]["mosaicDuration"]:
                        mosaicDuration_min = isodate.parse_duration(conf["item"]["mosaicDuration"]["min"])
                        mosaicDuration_max = isodate.parse_duration(conf["item"]["mosaicDuration"]["max"])
                        duration_item = end - start
                        if not mosaicDuration_min <= duration_item <= mosaicDuration_max:
                            # mosaicDuration does not match item's timeinterval
                            continue
                    
                    # Read the dataset
                    download_tries = 5
                    while download_tries > 0 :
                        ds = gdal.Open("/vsicurl/" + url_gdal)
                        if ds == None: # if there is an error while reading
                            download_tries = download_tries - 1
                            time.sleep(1)
                            continue
                        else:
                            break # success in dowloading
                    if download_tries == 0:
                        break # if cannot download go to "for file in response" -loop

                    # Get geometry and bbox    
                    try:
                        geom, bbox = h.get_geom_and_bbox_from_ds(ds) # use function in helpers.py
                    except:
                        print("Could not get bbox of", url)
                        continue
                    
                    try:
                        geotiff_validator.validate(ds, check_tiled=True, full_check=False)
                        media_type = "image/tiff; application=geotiff; profile=cloud-optimized" #cloud-optimized GeoTIFF
                    except:
                        media_type = "image/tiff; application=geotiff" #GeoTIFF with standardized georeferencing metadata

                    # Create asset object
                    asset_object = {
                        "id": id,
                        "bbox": bbox,
                        "geometry": geom,
                        "properties": {
                            "datetime": date_isoformat,
                            "start_datetime": start_isoformat,
                            "end_datetime": end_isoformat
                        },
                        "collection": conf["datasetId"],
                        "links": [
                            {
                            "rel": "self",
                            "href": self_link
                            },
                            {
                            "rel": "collection",
                            "href": conf["destination"]["catalogBaseUrl"] + conf["datasetId"] +".json"
                            }
                        ],
                        "assets": {}
                    }
                    asset_object["assets"][band] = {
                        "href": url,
                        "title": band,
                        "type": media_type,
                        "roles": conf["item"]["roles"]
                    }

                    item_template = copy.deepcopy(conf["item"]["template"])   
                    merged = h.merge(dict(item_template), asset_object) # merge asset object with item template
                    destinationPath = conf["destination"]["localItemPath"]
                    filename = destinationPath + merged["id"] + ".json"
                    with open(filename, 'w') as outfile: 
                        json.dump(merged, outfile)

            if 'NextContinuationToken' in response:
                nextToken = response['NextContinuationToken']
            else:
                break
                        
def main(conf, s3_conf):
    client = boto3.client('s3', 
        aws_access_key_id = s3_conf['aws_access_key_id'],
        aws_secret_access_key = s3_conf['aws_secret_access_key'],
        endpoint_url = s3_conf['endpoint_url']
    )
    if conf["source"] is None:
        print("There is no source information. Skipping item builder. ")
        print("This should happen when building catalog for Sentinel-1 osakuvat ascending / descending images.")
        
    else:
        item_builder(conf, client)


