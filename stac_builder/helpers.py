import json
import shapely
from shapely import wkt
from osgeo import ogr, osr, gdal
from shapely.geometry import MultiPoint, mapping
from datetime import datetime

TGT_SRS = osr.SpatialReference()
TGT_SRS.ImportFromWkt('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]]')

# https://gis.stackexchange.com/a/57837

def get_extent(gt, cols, rows):
    """ Return list of corner coordinates from a geotransform
        @type gt:   C{tuple/list}
        @param gt: geotransform
        @type cols:   C{int}
        @param cols: number of columns in the dataset
        @type rows:   C{int}
        @param rows: number of rows in the dataset
        @rtype:    C{[float,...,float]}
        @return:   coordinates of each corner
    """

    ext = []
    xarr = [0, cols]
    yarr = [0, rows]

    for px in xarr:
        for py in yarr:
            x = gt[0] + (px * gt[1]) + (py * gt[2])
            y = gt[3] + (px * gt[4]) + (py * gt[5])
            ext.append([x, y])
        yarr.reverse()
    return ext

def get_geom_and_bbox_from_ds(ds):
    src_srs = osr.SpatialReference()
    src_srs.ImportFromWkt(ds.GetProjection())
    transformation = osr.CoordinateTransformation(src_srs, TGT_SRS)

    extent = get_extent(ds.GetGeoTransform(), ds.RasterXSize, ds.RasterYSize)
    extent_geom = ogr.CreateGeometryFromJson(json.dumps(mapping(MultiPoint(extent).envelope)))
    extent_geom.Transform(transformation)

    exact_geom = shapely.wkt.loads(extent_geom.ExportToWkt())

    geom = shapely.wkt.loads(
        shapely.wkt.dumps(exact_geom, rounding_precision=6))

    bbox = exact_geom.bounds
    return mapping(geom), bbox
 

def GetBoundingBox(coords):
    """
    Finds a 2D bounding box from list of coordinates.
    Input: List of X/Y coordinates.
    Output: Bounding box coordinates.
    Inspired by: https://techoverflow.net/2017/02/23/computing-bounding-box-for-a-list-of-coordinates-in-python/
    """
    if len(coords) == 0:
        raise ValueError("Can't compute bounding box of empty list. Check if there are any items in this dataset.")
    minx, miny = float("inf"), float("inf")
    maxx, maxy = float("-inf"), float("-inf")
    for x, y in coords:
        # Set min coords
        if x < minx:
            minx = x
        if y < miny:
            miny = y
        # Set max coords
        if x > maxx:
            maxx = x
        elif y > maxy:
            maxy = y
   
    return minx, miny, maxx, maxy

def FindMinMaxTime(time, starttime, endtime, min_time, max_time):
    """
    Finds smallest starttime and largest endtime.
    In other words, finds the temporal extent of a collection.
    """
    if time is not None:
        time_datetime = datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ')
        if time_datetime < min_time:
            min_time = time_datetime
        if time_datetime > max_time:
            max_time = time_datetime
    if time is None:
        starttime_datetime = datetime.strptime(starttime, '%Y-%m-%dT%H:%M:%SZ')
        endtime_datetime = datetime.strptime(endtime, '%Y-%m-%dT%H:%M:%SZ')
        if starttime_datetime < min_time:
            min_time = starttime_datetime
        if endtime_datetime > max_time:
            max_time = endtime_datetime
    
    return min_time, max_time

def UpdateDatasetTime(item_start, item_end, min_time, max_time, assets, bands, item_coords, coords):
    '''
    Help function for updating of dataset-time collection variables.
    '''
    if item_start < min_time:
        min_time = item_start
    if item_end > max_time:
        max_time = item_end
    for asset in assets:
        if asset not in bands:
            bands.append(asset)
    for coord_list in item_coords:
        for coordinate in coord_list:
            coords.append(coordinate)
    return min_time, max_time, bands, coords


def merge(a, b):
    '''
    Merges two dictionaries, merges b into a.
    Returns merged dictionary.
    Inspired by: https://stackoverflow.com/questions/7204805/how-to-merge-dictionaries-of-dictionaries/7205107#7205107
    '''
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key])
            elif a[key] == b[key]: # same leaf value
                pass 
            else: # conflict
                a[key] = a[key] + b[key]
        else:
            a[key] = b[key]
    return a

def create_nested_dict(dest, val):
    '''
    Creates a nested dictionary.
    Input: destination (point-separated string), value.
    Output: nested dictionary.
    '''
    dest_list = dest.split(".")
    dest_list.reverse()
    nest_dict = {dest_list.pop(0): val}
    for item in dest_list:
        nest_dict = {item: nest_dict}
    return nest_dict
