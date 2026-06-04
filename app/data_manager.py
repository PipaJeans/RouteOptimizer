import os
import json
import asyncio
import httpx
from typing import List, Dict, Tuple

from app.models import Point

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, 'data', 'cache')
COORD_FILE = os.path.join(CACHE_DIR, 'city_coordinates.json')
MATRIX_FILE = os.path.join(CACHE_DIR, 'matrix_cache.json')

OSRM_URL = os.getenv('OSRM_URL', 'http://router.project-osrm.org')
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org/search')
OSRM_MATRIX_LIMIT = int(os.getenv('OSRM_MATRIX_LIMIT', '100'))

COORD_CACHE = {}
MATRIX_CACHE = {}
NOMINATIM_LOCK = asyncio.Lock()
CACHE_WRITE_LOCK = asyncio.Lock()

def init_caches():
    """Загрузка файловых кэшей в память при запуске сервера."""
    global COORD_CACHE, MATRIX_CACHE
    if os.path.exists(COORD_FILE):
        with open(COORD_FILE, 'r', encoding='utf-8') as f:
            COORD_CACHE = json.load(f)
    if os.path.exists(MATRIX_FILE):
        with open(MATRIX_FILE, 'r', encoding='utf-8') as f:
            MATRIX_CACHE = json.load(f)
    print(f"[*] Кэш загружен в ОЗУ: {len(COORD_CACHE)} адресов, {len(MATRIX_CACHE)} путей.")


def _save_cache_to_disk_sync(file_path, data):
    """Атомарная запись через временный файл, чтобы не повредить кэш."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp_path = f"{file_path}.tmp"
    data_to_write = dict(data)
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data_to_write, f, ensure_ascii=False)
    os.replace(tmp_path, file_path)


async def save_cache_to_disk(file_path, data):
    """Неблокирующая запись кэша на диск с защитой от гонок."""
    async with CACHE_WRITE_LOCK:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save_cache_to_disk_sync, file_path, data)


async def load_coordinates(points: List[Point]):
    cache_updated = False
    headers = {'User-Agent': '1C_BTMS_App/3.0'}
    async with httpx.AsyncClient() as client:
        for point in points:
            if point.lat is not None and point.lon is not None and not (point.lat == 0 and point.lon == 0):
                continue
            if point.address in COORD_CACHE:
                point.lon, point.lat = COORD_CACHE[point.address]
                continue
            print(f"[GEO] Запрос Nominatim: {point.address}")
            try:
                async with NOMINATIM_LOCK:
                    response = await client.get(
                        NOMINATIM_URL,
                        params={'q': point.address, 'format': 'json', 'limit': 1},
                        headers=headers
                    )
                    if response.status_code == 200:
                        results = response.json()
                        if results:
                            point.lon, point.lat = float(results[0]['lon']), float(results[0]['lat'])
                            COORD_CACHE[point.address] = (point.lon, point.lat)
                            cache_updated = True
                    await asyncio.sleep(1.1)
            except Exception as e:
                print(f"[GEO Error] {e}")
    if cache_updated:
        await save_cache_to_disk(COORD_FILE, COORD_CACHE)


async def load_distance_matrix(points: List[Point], traffic_coeff: float = 1.0) -> Dict[str, Tuple[float, float]]:
    valid_points = [p for p in points if p.lat is not None and p.lon is not None and not (p.lat == 0 and p.lon == 0)]
    if len(valid_points) < 2:
        return {}
    result_matrix = {}
    points_to_fetch = []
    unique_ids = set()
    for p1 in valid_points:
        needs_fetch = False
        for p2 in valid_points:
            if p1.id == p2.id:
                continue
            cache_key = f"{p1.lat:.8f},{p1.lon:.8f}|{p2.lat:.8f},{p2.lon:.8f}"
            if cache_key in MATRIX_CACHE:
                dist, dur = MATRIX_CACHE[cache_key]
                result_matrix[f"{p1.id}-{p2.id}"] = (dist, dur * traffic_coeff)
            else:
                needs_fetch = True
        if needs_fetch and p1.id not in unique_ids:
            unique_ids.add(p1.id)
            points_to_fetch.append(p1)

    if points_to_fetch:
        if len(points_to_fetch) > OSRM_MATRIX_LIMIT:
            raise Exception(
                f"Маршрут слишком велик (более {OSRM_MATRIX_LIMIT} новых точек). "
                "Требуется локальный OSRM сервер или увеличение OSRM_MATRIX_LIMIT."
            )
        coords_str = ";".join([f"{p.lon},{p.lat}" for p in points_to_fetch])
        url = f"{OSRM_URL}/table/v1/driving/{coords_str}?annotations=duration,distance"
        print(f"[OSRM] API запрос для {len(points_to_fetch)} новых точек...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                for i, p1 in enumerate(points_to_fetch):
                    for j, p2 in enumerate(points_to_fetch):
                        if i == j:
                            continue
                        dist = data['distances'][i][j]
                        dur = data['durations'][i][j]
                        if dist is None: dist, dur = float('inf'), float('inf')
                        cache_key = f"{p1.lat:.8f},{p1.lon:.8f}|{p2.lat:.8f},{p2.lon:.8f}"
                        MATRIX_CACHE[cache_key] = (dist, dur)
                        result_matrix[f"{p1.id}-{p2.id}"] = (dist, dur * traffic_coeff)
                await save_cache_to_disk(MATRIX_FILE, MATRIX_CACHE)
            else:
                raise Exception(f"Ошибка OSRM API: Код {response.status_code}")
    else:
        print("[OSRM] RAM-Кэш: 0 запросов в сеть.")
    return result_matrix