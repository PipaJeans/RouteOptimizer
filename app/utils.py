import os
import base64
import httpx
import gpxpy
import gpxpy.gpx
from typing import List, Dict


OSRM_URL = os.getenv('OSRM_URL', 'http://router.project-osrm.org')


async def get_route_geometry(ordered_points: List) -> Dict:
    coords = ";".join([f"{p.lon},{p.lat}" for p in ordered_points])
    url = f"{OSRM_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'routes' in data and len(data['routes']) > 0:
                return data['routes'][0]['geometry']
        else:
            print(f"[OSRM Route Error] Код: {response.status_code}, Ответ: {response.text}")
    except Exception as e:
        print(f"[OSRM Route Error] Ошибка запроса: {e}")
    return None


def generate_gpx_base64(ordered_points: List, schedule: List, geometry_geojson: Dict) -> str:
    gpx = gpxpy.gpx.GPX()
    for i, (p, sched_p) in enumerate(zip(ordered_points, schedule)):
        if i == 0:
            point_name = f"СТАРТ: {sched_p.address}"
        elif i == len(schedule) - 1 and p.id == ordered_points[0].id:
            point_name = f"ФИНИШ: {sched_p.address}"
        else:
            point_name = f"Остановка {i}: {sched_p.address}"
        wp = gpxpy.gpx.GPXWaypoint(
            latitude=p.lat,
            longitude=p.lon,
            name=point_name
        )
        arr = sched_p.arrival_time.strftime('%H:%M')
        dep = sched_p.departure_time.strftime('%H:%M')
        wp.description = f"Прибытие: {arr}\nУбытие: {dep}"
        gpx.waypoints.append(wp)

    if geometry_geojson and 'coordinates' in geometry_geojson:
        gpx_track = gpxpy.gpx.GPXTrack(name="Маршрут VRPTW")
        gpx.tracks.append(gpx_track)
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        for lon, lat in geometry_geojson['coordinates']:
            gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
    xml_string = gpx.to_xml()
    return base64.b64encode(xml_string.encode('utf-8')).decode('utf-8')