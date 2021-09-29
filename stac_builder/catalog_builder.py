import json 
import os
from dateutil import rrule
from datetime import datetime, timedelta
from calendar import monthrange
from dateutil.relativedelta import relativedelta
import copy

import helpers as h # import help functions from helpers.py


def dataset_collection_builder(conf):
    '''
    Function reads items of a dataset and builds a dataset collection.
    Finds start- and enddate, extent (bbox) and available bands of dataset collection.
    Input: configuration file of dataset.
    Output: dataset collection object.
    '''
    dataset_collection_object = {
        "extent": {
            "spatial": {
                "bbox": None
            },
            "temporal": {
                "interval": None
            }
        },
        "summaries": {
            "datetime": {
                "minimum": None,
                "maximum": None
            },
            "bands": []
        },
        "links": [
            {
                "rel": "self",
                "href": conf["destination"]["catalogBaseUrl"] + conf["datasetId"] + ".json"
            }
        ]
    }

    min_time = datetime.max 
    max_time = datetime.min 
    coords = []
    existing_bands = []
    itemsDestination = conf["destination"]["localItemPath"]

    if "selectItemsMatching" in conf["dataset"]:
        dest = list(conf["dataset"]["selectItemsMatching"].keys())[0]
        val = conf["dataset"]["selectItemsMatching"]["properties.orbit"]
        print("Choosing items where", dest, "has the value", val)
    
    for entry in os.scandir(itemsDestination):

        item_path = open(entry.path) 
        item = json.load(item_path)

        # Processing for S1 asc/desc catalogs
        if "selectItemsMatching" in conf["dataset"]:
            dest = list(conf["dataset"]["selectItemsMatching"].keys())[0]
            val = conf["dataset"]["selectItemsMatching"]["properties.orbit"]
            compare_val = copy.deepcopy(item)
            dest_list = dest.split(".")
            for key in dest_list:
                try:
                    compare_val = compare_val[key]
                except:
                    print("Error:", key, "is missing in item", item["id"])
                    continue
            if compare_val == val:
                pass # Continue with processing if rule is true
            else:
                continue

        # Find biggest starttime and smallest endtime of all items
        time = item["properties"]["datetime"]
        starttime = item["properties"]["start_datetime"]
        endtime = item["properties"]["end_datetime"]
        min_time, max_time = h.FindMinMaxTime(time, starttime, endtime, min_time, max_time)        

        # Collect all coordinate points to a list
        polygon_coordinates = item["geometry"]["coordinates"]
        for coord_list in polygon_coordinates:
            for coordinate in coord_list:
                coords.append(coordinate)

        # Write available bands to collection object
        bands = list(item["assets"].keys())
        for band in bands:
            if band not in existing_bands:
                existing_bands.append(band)
                dataset_collection_object["summaries"]["bands"].append({"name": band})
    
    bbox = h.GetBoundingBox(coords) # Find bounding box
    
    # Update object values
    dataset_collection_object["extent"]["spatial"]["bbox"] = [bbox]
    dataset_collection_object["extent"]["temporal"]["interval"] = [min_time.isoformat(timespec='seconds') + 'Z' , max_time.isoformat(timespec='seconds') + 'Z']
    dataset_collection_object["summaries"]["datetime"]["minimum"] = min_time.isoformat(timespec='seconds') + 'Z'
    dataset_collection_object["summaries"]["datetime"]["maximum"] = max_time.isoformat(timespec='seconds') + 'Z'

    # Merge with template
    dataset_template = conf["dataset"]["template"]
    dataset_collection_object_merged = h.merge(dict(dataset_template), dataset_collection_object)
    

    return dataset_collection_object_merged

def dataset_time_collection_step1(conf, dataset_collection_object):
    '''
    Function builds a first draft of dataset-time collection based on
    datasets start and endtime.
    Input: configuration file and dataset collection of a dataset.
    Output: First version of dataset-time collection. The dataset-time collection is completed in step 2.
    '''
    dataset_time_collection_list = []

    dataset_time_collection_template = {
        "extent": {
            "spatial": {
                "bbox": None
            },
            "temporal": {
                "interval": None
            }
        },
        "summaries": {
            "datetime": {
                "minimum": None,
                "maximum": None
            },
            "bands": []
        },
        "links": [
        ]
    }        
    
    collection_starttime_str = dataset_collection_object["summaries"]["datetime"]["minimum"]
    collection_starttime = datetime.strptime(collection_starttime_str, '%Y-%m-%dT%H:%M:%SZ')
    collection_endtime_str = dataset_collection_object["summaries"]["datetime"]["maximum"]
    collection_endtime = datetime.strptime(collection_endtime_str, '%Y-%m-%dT%H:%M:%SZ')
    
    # Create empty dataset-time objects based on timeframe
    timeFrame = conf["dataset-time"]["timeFrame"]

    if timeFrame == "week":
        rule = rrule.WEEKLY
        collection_starttime_iter = collection_starttime - timedelta(days=collection_starttime.weekday()) #first day of week
        collection_starttime_iter = collection_starttime_iter.replace(hour=0, minute=0, second=0)
        collection_endtime_iter = collection_endtime + timedelta(days=6) # last day of week
    elif timeFrame == "month":
        rule = rrule.MONTHLY
        collection_starttime_iter = collection_starttime.replace(day=1) # first day of month
        collection_starttime_iter = collection_starttime_iter.replace(hour=0, minute=0, second=0)
        collection_endtime_iter = collection_endtime.replace(day = monthrange(collection_endtime.year, collection_endtime.month)[1])
    elif timeFrame == "year": 
        rule = rrule.YEARLY
        collection_starttime_iter = datetime(collection_starttime.year, 1, 1) # first day of year
        collection_endtime_iter = datetime(collection_endtime.year, 12, 31) # last day of year
    else:
        raise ValueError("Unrecognized time frame in configuration file")
    
    # Add dataset-time collections to list, when iterating over time frame
    for dt in rrule.rrule(rule, dtstart=collection_starttime_iter, until=collection_endtime_iter):  
        if timeFrame == "week":
            id = conf["datasetId"] +"_"+ str(dt.year) +"-"+ '{:02d}'.format(dt.month) +"-"+ '{:02d}'.format(dt.day)
            end = dt + timedelta(days=6) # last day of week
        elif timeFrame == "month":
            id = conf["datasetId"] +"_"+ str(dt.year) +"-"+ '{:02d}'.format(dt.month)
            end = dt.replace(day = monthrange(dt.year, dt.month)[1]) # last day of month
        else: # if timeFrame == "year"
            id = conf["datasetId"] +"_"+ str(dt.year)
            end = dt + relativedelta(years=+1, days=-1) # last day of year
        
        # Update dataset-time object
        dataset_time_collection_new = copy.deepcopy(dataset_time_collection_template)
        dataset_time_collection_new["id"] = id
        dataset_time_collection_new["summaries"]["datetime"]["minimum"] = dt
        dataset_time_collection_new["summaries"]["datetime"]["maximum"] = end
        dataset_time_collection_new["extent"]["temporal"]["interval"] = [dt, end]
        link = conf["destination"]["catalogBaseUrl"] + id + ".json"
        dataset_time_collection_new["links"].append({"rel": "self", "href": link})

        # Merge with template 
        dataset_time_template = copy.deepcopy(conf["dataset-time"]["template"])
        dataset_time_object_merged = h.merge(dict(dataset_time_template), dataset_time_collection_new)

        dataset_time_collection_list.append(dataset_time_object_merged)
    
    return dataset_time_collection_list

      
def dataset_time_collection_step2(conf, dataset_time_collection_list, dataset_collection_object):
    '''
    Loops over dataset's items and adds them to correct dataset-time collection objects.
    Writes dataset-time collections to given location.
    Input: configuration file of dataset, dataset-time collection list, dataset collection object.
    Output: dataset collection object.
    '''
    itemsDestination = conf["destination"]["localItemPath"]
    
    # Loop over "empty" dataset-time collections
    for dataset_time_collection in dataset_time_collection_list:
        dataset_start = dataset_time_collection["summaries"]["datetime"]["minimum"]
        dataset_end = dataset_time_collection["summaries"]["datetime"]["maximum"]
        
        min_time = datetime.max
        max_time = datetime.min
        bands = []
        coords = []

        # Loop over  items
        for entry in os.scandir(itemsDestination):
            item_path = open(entry.path) 
            item = json.load(item_path)

            # Processing for S1 asc/desc catalogs
            if "selectItemsMatching" in conf["dataset"]:
                dest = list(conf["dataset"]["selectItemsMatching"].keys())[0]
                val = conf["dataset"]["selectItemsMatching"]["properties.orbit"]
                compare_val = copy.deepcopy(item)
                dest_list = dest.split(".")
                for key in dest_list:
                    try:
                        compare_val = compare_val[key]
                    except:
                        print("Error:", key, "is missing in item", item["id"])
                        continue
                if compare_val == val:
                    pass # Continue with processing if rule is true
                else:
                    continue
            
            assets = list(item["assets"].keys()) 
            item_start_str = item["properties"]["start_datetime"]
            item_end_str = item["properties"]["end_datetime"]
            item_date_str = item["properties"]["datetime"]
            if item_start_str:
                item_start = datetime.strptime(item_start_str, '%Y-%m-%dT%H:%M:%SZ')
                item_end = datetime.strptime(item_end_str, '%Y-%m-%dT%H:%M:%SZ')  
            elif item_date_str:
                item_start = datetime.strptime(item["properties"]["datetime"], '%Y-%m-%dT%H:%M:%SZ')
                item_end = item_start
            else:
                print("Error. All timestamps are None.")

            item_coords = item["geometry"]["coordinates"]
            
            # Add item to dataset-time collection
            if item_end >= dataset_start and item_start <= dataset_end:
                for i in item["links"]: 
                    if "self" in str(i):
                        item_link = i["href"]
                
                dataset_time_collection["links"].append({'rel': 'item', 'href': item_link, 'time': {'time_start': item_start.isoformat(timespec='seconds') + 'Z', 'time_end': item_end.isoformat(timespec='seconds') + 'Z'}})
                min_time, max_time, bands, coords = h.UpdateDatasetTime(item_start, item_end, min_time, max_time, assets, bands, item_coords, coords)
            else:
                continue # item does not fit this dataset-time collection
        
        if len(dataset_time_collection["links"]) > 2: # check if any items have been added to collection
            # Update dataset-time collection's min and max time 
            dataset_time_collection["summaries"]["datetime"]["minimum"] = min_time.isoformat(timespec='seconds') + 'Z'
            dataset_time_collection["summaries"]["datetime"]["maximum"] = max_time.isoformat(timespec='seconds') + 'Z'
            dataset_time_collection["extent"]["temporal"]["interval"] = [min_time.isoformat(timespec='seconds') + 'Z', max_time.isoformat(timespec='seconds') + 'Z']
            
            # Add info of available bands
            for band in bands:
                dataset_time_collection["summaries"]["bands"].append({"name": band}) 
            
            bbox_collection = h.GetBoundingBox(coords) # Get bbox of items in collection
            dataset_time_collection["extent"]["spatial"]["bbox"] = bbox_collection

            id = dataset_time_collection["id"]
            path = conf["destination"]["localCatalogPath"] + id + ".json"

            # Write to location
            with open(path, 'w') as outfile: 
                json.dump(dataset_time_collection, outfile)

            # Update dataset collection
            for i in dataset_time_collection["links"]: 
                if "self" in str(i):
                    child_link = i["href"]
            dataset_collection_object["links"].append({'rel': 'child', 'href': child_link, 'time':{'time_start': dataset_start.isoformat(timespec='seconds') + 'Z', 'time_end': dataset_end.isoformat(timespec='seconds') + 'Z'}})

    return dataset_collection_object
    

def main(conf):
    dataset_collection_object = dataset_collection_builder(conf)
    dataset_time_collection_list = dataset_time_collection_step1(conf, dataset_collection_object)
    dataset_collection_object = dataset_time_collection_step2(conf, dataset_time_collection_list, dataset_collection_object)

    # Write dataset -collection object
    path = conf["destination"]["localCatalogPath"] + dataset_collection_object["id"] + ".json"
    with open(path, 'w') as outfile: 
        json.dump(dataset_collection_object, outfile)
