from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Point(BaseModel):
    id: str = Field(..., description="Уникальный идентификатор точки из 1С (например, GUID)")
    address: str = Field(..., description="Строка адреса или название города для геокодера")
    lat: Optional[float] = Field(None, description="Широта (если уже есть в 1С)")
    lon: Optional[float] = Field(None, description="Долгота (если уже есть в 1С)")
    time_from: Optional[int] = Field(None, description="Окно С (в минутах от 00:00)")
    time_to: Optional[int] = Field(None, description="Окно ПО (в минутах от 00:00)")
    service_time: int = Field(0, description="Время на обслуживание в точке (в минутах)")
    fixed_order: Optional[int] = Field(None, description="Жесткий порядок в маршруте (0 = старт)")
    asap: bool = Field(False, description="Приоритет: Как можно раньше")


class OptimizationRequest(BaseModel):
    departure_time: datetime = Field(..., description="Плановое время начала маршрута")
    route_type: str = Field("closed", description="Тип маршрута: 'closed' (замкнутый) или 'open' (разомкнутый)")
    traffic_coefficient: float = Field(1.0, description="Коэффициент пробок (1.0 - без пробок, 1.5 - час пик)")
    need_gpx: bool = Field(False, description="Флаг: сгенерировать и вернуть файл GPX")
    points: List[Point] = Field(..., min_length=2, description="Список точек маршрута")
    optimization_type: str = Field("balanced", description="Тип: 'time' (быстрый), 'distance' (короткий), 'balanced' (баланс)")
    max_driving_hours: float = Field(10.0, description="Максимальное время за рулем (в часах)")


class RoutePointResponse(BaseModel):
    id: str = Field(..., description="ID точки из 1С")
    address: str = Field(..., description="Адрес точки")
    arrival_time: datetime = Field(..., description="Расчетное время прибытия (ETA)")
    departure_time: datetime = Field(..., description="Расчетное время убытия (ETD)")
    wait_time_mins: int = Field(0, description="Время ожидания открытия (в минутах)")
    distance_from_prev_meters: float = Field(0.0, description="Дистанция от предыдущей точки")


class OptimizationResponse(BaseModel):
    status: str
    message: str
    matrix_size: Optional[int] = None
    total_distance_meters: Optional[float] = None
    total_time_seconds: Optional[float] = None
    points_order: Optional[List[RoutePointResponse]] = None
    route_geometry: Optional[dict] = Field(None, description="GeoJSON полилинии маршрута для отрисовки на карте")
    gpx_data: Optional[str] = Field(None, description="GPX файл в кодировке Base64")