#!/usr/bin/env python

import geohash
import json


with open("foo.json") as fp:
    feature = json.load(fp)


## READ: https://github.com/hkwi/python-geohash/wiki/GeohashReference


print('Coords:', feature["geometry"]["coordinates"][0][0][1], feature["geometry"]["coordinates"][0][0][0])
h = geohash.encode(feature["geometry"]["coordinates"][0][0][1], feature["geometry"]["coordinates"][0][0][0])
print('Geohash for coordinates[0][0]:', h)

h = h[0:3]

print('Exact coordinates for:',h, geohash.decode_exactly(h))
print('Bbox for:',h, geohash.bbox(h))


from polygon_geohasher.polygon_geohasher import polygon_to_geohashes
from shapely import geometry

print(polygon_to_geohashes(geometry.Polygon(feature["geometry"]["coordinates"][0]), 3, False))

###
#
#print 'Geohash for 42.6, -5.6:', geohash.encode(42.6, -5.6)
#
#print 'Coordinate for Geohash ezs42:', geohash.decode('ezs42')
#
#print 'Exact coordinate for Geohash ezs42:\n', geohash.decode_exactly('ezs42')