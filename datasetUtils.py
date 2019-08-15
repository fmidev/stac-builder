import json

import shapely.wkt
from osgeo import ogr, osr
from shapely.geometry import MultiPoint, mapping

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
