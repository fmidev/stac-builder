from datetime import datetime
import os
import re
import json 
import copy
import requests
from bs4 import BeautifulSoup

import helpers as h

def metadata_builder(conf, filename, url, url_gdal):
    '''
    Function adds information about metadata to existing items. 
    Function fetches information of the orbit (ascending/descending) from .dim -file.
    Input: configuration file, filename, URL.
    Output: writes metadata info to item.
    '''
    fileNamingConventionMeta = conf["item"]["metadata"]["fileNamingConventionMeta"]
    p = re.compile(fileNamingConventionMeta)
    m = p.search(filename)
    
    try: # Check if filename is in expected format
                    
        startdate = m.group('startdate')
        try:
            bandname = m.group('band')
            if bandname == "":
                bandname = conf["item"]["missingbandname"]
            band = bandname.lower() # lowercase
        except:
            band = None # if there is no band in filename
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
        #print(filename, "does not match file naming convention for metadata")
        return None
        
    # Create id using item.idTemplate
    id = conf["item"]["idTemplate"]

    if tile:
        id = id.replace("tile_id", tile)

    # extract dates 
    if enddate is not None: # filenames with enddate
        if len(enddate) == 2: # if year is given in two digits
            start_id = "20" + startdate
            id = id.replace("startdate", start_id)
            end_id = "20" + enddate
            id = id.replace("enddate", end_id)
        elif len(enddate) == 4: # if year is given in 4 digits
            id = id.replace("startdate", startdate)
            id = id.replace("enddate", enddate)
        elif len(enddate) == 8: # if dates are given in 8 digits
            start_id = startdate[0:4] +'-'+ startdate[4:6] +'-'+ startdate[6:8]
            id = id.replace("startdate", start_id)
            end_id = enddate[0:4] +'-'+ enddate[4:6] +'-'+ enddate[6:8]
            id = id.replace("enddate", end_id)
            
        else:
            print("Unrecognized time format in", filename)
    else: # filenames without enddate
        if len(startdate) == 2:
            start_id = "20" + startdate
            id = id.replace("startdate", start_id)
        elif len(startdate) == 4:
            id = id.replace("startdate", startdate)
        elif len(startdate) == 8:    
            start_id = startdate[0:4] +'-'+ startdate[4:6] +'-'+ startdate[6:8]    
            id = id.replace("startdate", start_id)
        elif len(startdate) == 10:
            if "_" in startdate:
                startdate = startdate.replace("_", "-")
            id = id.replace("startdate", startdate)
        else:
            print("Unrecognized time format in", filename)
        if starttime is not None:
            id = id + "_" + starttime

    # Check if item already exists
    local_item_path = conf["destination"]["localItemPath"] + id + ".json"

    if os.path.isfile(local_item_path): # if item already exists
        item_path = open(local_item_path)
        item = json.load(item_path)
        assets = list(item["assets"].keys())
        if band:
            meta_band = "metadata_" + band
        else:
            meta_band = "metadata"
        if meta_band not in assets:
            
            # Fetch orbit information
            r = requests.get(url_gdal)
            data = r.text
            soup = BeautifulSoup(data, "lxml")
            soupExtractionrules = conf["item"]["metadata"]["extractionRules"]
            for ruleset in soupExtractionrules:
                soupExtractionrule = ruleset["soupExtraction"]
                rule = ruleset["rule"]

                if rule == ".get_text()":
                    meta = soup.select_one(soupExtractionrule).get_text()
                else:
                    meta = soup.select_one(soupExtractionrule)
            
                # create dict for orbit information 
                dest = ruleset["writeToItemField"]
                old_item = copy.deepcopy(item)
                if dest == "metadata_field":
                    metadata_info = { "assets": 
                            {meta_band: {
                                "href": url,
                                "title": "metadata",
                                "roles": "metadata",
                                "metadata": [str(meta)],
                                }
                            }
                        }
                    # Merge new info into existing item
                    new_item = h.merge(old_item, metadata_info)
                
                else:
                    meta_info = h.create_nested_dict(dest, str(meta))

                    # create dict for metadata information
                    metadata_info = { "assets": 
                            {meta_band: {
                                "href": url,
                                "title": "metadata",
                                "roles": "metadata"
                                }
                            }
                        }
                            
                    # Merge new info into existing item
                    merged = h.merge(dict(old_item), meta_info)
                    new_item = h.merge(merged, metadata_info)

                # Write item json files into destination.localItemPath
                with open(local_item_path, 'w') as outfile:
                    json.dump(new_item, outfile)