import asyncio
import math
import httpx
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Response

from app import data_manager, utils
from app.algorithms.GA import genetic_algorithm
from app.models import OptimizationRequest, OptimizationResponse, RoutePointResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    data_manager.init_caches()
    yield
    process_pool.shutdown()


app = FastAPI(
    title="VRPTW API для 1С",
    description="Business Trip Management System Backend",
    version="3.0.0",
    lifespan=lifespan,
)
process_pool = ProcessPoolExecutor()

@app.get("/1cmapclick")
def map_click_dummy():
    """Глушитель кликов для 1С. Предотвращает стирание карты браузером."""
    return Response(status_code=204)

@app.get("/api/v1/reverse-geocode")
async def reverse_geocode(lat: float, lon: float):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            async with data_manager.NOMINATIM_LOCK:
                resp = await client.get(url, headers=headers)
                await asyncio.sleep(1.1)
            if resp.status_code == 200:
                data = resp.json()
                if "display_name" in data:
                    addr = data.get("address", {})
                    region = addr.get("state", addr.get("region", addr.get("county", "")))
                    return {"address": data["display_name"], "region": region}
        except Exception as e:
            print(f"[Reverse Geocode Error] {e}")

    return {"address": f"Точка: {lat:.6f}, {lon:.6f}"}


def heavy_computation_task(points, dist_matrix, departure_time, route_type, optimization_type, max_driving_hours):
    return genetic_algorithm(
        points=points,
        dist_matrix=dist_matrix,
        departure_time=departure_time,
        route_type=route_type,
        optimization_type=optimization_type,
        max_driving_hours=max_driving_hours
    )

@app.post("/api/v1/optimize", response_model=OptimizationResponse)
async def optimize_route(request: OptimizationRequest):
    try:
        await data_manager.load_coordinates(request.points)
        missing_coords = [
            p.address for p in request.points
            if p.lat is None or p.lon is None or (p.lat == 0 and p.lon == 0)
        ]
        if missing_coords:
            raise HTTPException(status_code=400, detail=f"Нет координат: {', '.join(missing_coords)}")

        dist_matrix = await data_manager.load_distance_matrix(
            points=request.points,
            traffic_coeff=request.traffic_coefficient
        )
        loop = asyncio.get_running_loop()
        ga_result = await loop.run_in_executor(
            process_pool,
            heavy_computation_task,
            request.points,
            dist_matrix,
            request.departure_time,
            request.route_type,
            request.optimization_type,
            request.max_driving_hours
        )
        route_ids = ga_result["route_ids"]
        points_dict = {p.id: p for p in request.points}
        final_route = []
        current_dt = request.departure_time
        daily_driving_seconds = 0
        max_driving_seconds = request.max_driving_hours * 3600
        for i in range(len(route_ids)):
            curr_id = route_ids[i]
            p = points_dict[curr_id]
            if i == 0:
                dist, dur = 0, 0
            else:
                prev_id = route_ids[i-1]
                dist, dur = dist_matrix.get(f"{prev_id}-{curr_id}", (0, 0))
            if i > 0 and (daily_driving_seconds + dur) > max_driving_seconds:
                daily_driving_seconds = 0
                current_dt += timedelta(hours=12)
            daily_driving_seconds += dur
            arrival_dt = current_dt + timedelta(seconds=dur)
            wait_time_mins = 0
            if p.time_from is not None:
                arrival_day_seconds = (
                    arrival_dt.hour * 3600 + arrival_dt.minute * 60 + arrival_dt.second
                )
                open_seconds = p.time_from * 60
                if arrival_day_seconds < open_seconds:
                    wait_seconds = open_seconds - arrival_day_seconds
                    wait_time_mins = int(wait_seconds // 60)
                    arrival_dt += timedelta(seconds=wait_seconds)
            departure_dt = arrival_dt + timedelta(minutes=p.service_time)
            final_route.append(RoutePointResponse(
                id=curr_id,
                address=p.address,
                arrival_time=arrival_dt,
                departure_time=departure_dt,
                wait_time_mins=wait_time_mins,
                distance_from_prev_meters=dist
            ))
            current_dt = departure_dt

        ordered_points_obj = [points_dict[pid] for pid in route_ids]
        route_geometry = None
        try:
            route_geometry = await utils.get_route_geometry(ordered_points_obj)
        except Exception as e:
            print(f"[OSRM Route Error] Не удалось получить геометрию маршрута: {e}")
        gpx_data = None
        if request.need_gpx:
            try:
                gpx_data = utils.generate_gpx_base64(ordered_points_obj, final_route, route_geometry)
            except Exception as e:
                print(f"[GPX Error] Не удалось сформировать GPX: {e}")
        total_dist = ga_result["total_distance_meters"]
        if math.isinf(total_dist):
            raise HTTPException(status_code=400, detail="К одной из точек нет автомобильной дороги.")
        return OptimizationResponse(
            status="success",
            message="Оптимальный маршрут успешно рассчитан!",
            matrix_size=len(dist_matrix),
            total_distance_meters=round(total_dist, 2),
            total_time_seconds=round(ga_result["total_time_seconds"], 2),
            points_order=final_route,
            route_geometry=route_geometry,
            gpx_data=gpx_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")
