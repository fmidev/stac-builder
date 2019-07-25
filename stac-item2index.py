#!/usr/bin/env python

import json
import os

import geojson

GEOHASH_ACCURACY = 2
CATALOG_BASEURI = 'https://pta.data.lit.fmi.fi/stac/catalog/'
ITEM_BASEURI = 'https://pta.data.lit.fmi.fi/stac/item/'


def identifyDatasets(f):
    if 'id' not in f:
        return None

    id = f['id']
    i = id.find('_')
    if i == -1:
        return None

    return [id[0:i]]


def identifyLocations(f):
    from polygon_geohasher.polygon_geohasher import polygon_to_geohashes
    from shapely import geometry

    if 'geometry' not in f:
        return None

    geom = f['geometry']

    if 'type' not in geom:
        return None

    geometry_type = geom['type']

    if geometry_type != 'Polygon':
        print('Unknown geometry type:', geometry_type)
        return None

    poly_coords = geom['coordinates'][0]

    return list(polygon_to_geohashes(geometry.Polygon(poly_coords), GEOHASH_ACCURACY, False))


def identifyTimes(f):
    if 'properties' not in f:
        return None

    props = f['properties']

    if 'datetime' not in props:
        return None

    datetime = props['datetime']

    i = datetime.find('T')
    if i == -1:
        return None

    return [datetime[0:i]]


class Catalog:
    """
    Defines a single STAC catalogue that links to child catalogs and items
    """

    # name
    # children # Map String -> Catalog
    # items # Array of Items
    # parent # parent catalog
    # extent # geographical extent

    def __init__(self, name, parent=None, dimension=None):
        self.name = name
        self.children = {}
        self.items = []
        self.parent = parent
        self.extent = None
        self.timeStart = None
        self.timeEnd = None
        self.dimension = dimension

    def childCatalog(self, name, dimension=None):
        if name not in self.children:
            self.children[name] = Catalog(name, self, dimension)

        return self.children[name]

    def childCatalogs(self):
        return self.children.values()

    def extendWithItem(self, item):
        ## Extend bbox
        if self.extent is None:
            self.extent = item.bbox
        else:
            tmp = [None, None, None, None]
            tmp[0] = min(self.extent[0], item.bbox[0])
            tmp[1] = min(self.extent[1], item.bbox[1])
            tmp[2] = max(self.extent[2], item.bbox[2])
            tmp[3] = max(self.extent[3], item.bbox[3])
            self.extent = tmp

        dtStart = None
        dtEnd = None

        if 'dtr:start_datetime' in item.properties:
            dtStart = item.properties['dtr:start_datetime']
        elif 'datetime' in item.properties:
            dtStart = item.properties['datetime']

        if 'dtr:end_datetime' in item.properties:
            dtEnd = item.properties['dtr:end_datetime']
        elif 'datetime' in item.properties:
            dtEnd = item.properties['datetime']

        if dtStart is not None:
            if self.timeStart is None:
                self.timeStart = dtStart
            else:
                self.timeStart = min(dtStart, self.timeStart)

        if dtEnd is not None:
            if self.timeEnd is None:
                self.timeEnd = dtEnd
            else:
                self.timeEnd = max(dtEnd, self.timeEnd)

        if self.parent is not None:
            self.parent.extendWithItem(item)

    def addItem(self, item):
        self.items.append(item)
        self.extendWithItem(item)

    def toJson(self, description=None):
        ret = {'stac_version': '0.7.0', 'id': self.name, 'links': [], 'bbox': self.extent, 'properties': {}}
        if description is not None:
            ret['description'] = description

        root = None
        t = self.parent
        while t is not None:
            root = t
            t = t.parent

        ret['links'].append({'rel': 'self', 'href': CATALOG_BASEURI + self.name + '.json'})

        if root is not None:
            ret['links'].append({'rel': 'root', 'href': CATALOG_BASEURI + root.name + '.json'})

        if self.parent is not None and self.parent != root:
            ret['links'].append({'rel': 'parent', 'href': CATALOG_BASEURI + self.parent.name + '.json'})

        for child in self.children.values():
            tmp = {'rel': 'child', 'href': CATALOG_BASEURI + child.name + '.json'}
            if child.dimension is not None:
                tmp['dimension'] = child.dimension

            ret['links'].append(tmp)

        for item in self.items:
            ret['links'].append({'rel': 'item', 'href': ITEM_BASEURI + item.id + '.json'})

        ret['properties']['dtr:start_datetime'] = self.timeStart
        ret['properties']['dtr:end_datetime'] = self.timeEnd
        if self.dimension is not None:
            ret['properties']['dimension'] = self.dimension

        return ret

    def writeToFile(self, path, description=None):
        with open(path + '/' + self.name + '.json', 'w') as outfile:
            json.dump(self.toJson(description), outfile, sort_keys=False, indent=4)


def processStac(file, rootCatalogue):
    with open(file) as fp:
        item = json.load(fp)
    with open(file) as fp:
        geoj = geojson.load(fp)

    datasets = identifyDatasets(item)
    locations = identifyLocations(item)
    times = identifyTimes(item)

    if datasets is None or locations is None or times is None:
        print(file + ': unable to categorize')
        return

    for dataset in datasets:
        dataset_catalog = rootCatalogue.childCatalog('dataset-' + dataset)
        for location in locations:
            location_catalog = dataset_catalog.childCatalog('dataset-' + dataset + '-location-' + location,
                                                            {'axis': 'geohash', 'value': location})
            for time in times:
                time_catalog = location_catalog.childCatalog(
                    'dataset-' + dataset + '-location-' + location + '-time-' + time, {'axis': 'time', 'value': time})
                time_catalog.addItem(geoj)


if __name__ == '__main__':
    catalog = Catalog('root')

    input_dir = './item/'
    for file in os.listdir(input_dir):
        if file.endswith('.json'):
            processStac(input_dir + file, catalog)

    catalog.writeToFile('catalog/', 'FMI Sentinel catalog')

    for dataset in catalog.childCatalogs():
        dataset.writeToFile('catalog/', 'FMI Sentinel catalog - ' + dataset.name)
        for location in dataset.childCatalogs():
            location.writeToFile('catalog/', 'FMI Sentinel catalog - ' + location.name)
            for time in location.childCatalogs():
                time.writeToFile('catalog/', 'FMI Sentinel catalog - ' + time.name)
