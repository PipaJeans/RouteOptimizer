import random
import heapq
from datetime import datetime
from app.algorithms.NN import nearest_neighbor

def genetic_algorithm(points, dist_matrix, departure_time: datetime, route_type: str, optimization_type: str = "balanced", max_driving_hours: float = 10.0):
    points_dict = {p.id: p for p in points}
    start_point = next((p for p in points if p.fixed_order == 0), points[0])
    start_id = start_point.id
    fixed_points = sorted(
        [p for p in points if p.id != start_id and p.fixed_order is not None],
        key=lambda p: p.fixed_order
    )
    fixed_position_by_id = {p.id: i + 1 for i, p in enumerate(fixed_points)}
    num_points = len(points)
    population_size = min(800, max(150, num_points * 20))
    generations = min(1500, max(300, num_points * 40))
    
    if optimization_type == "time":
        w_time = 1.0
        w_dist = 0.0001
    elif optimization_type == "distance":
        w_time = 0.0001
        w_dist = 1.0
    else:
        w_time = 1.0
        w_dist = 0.05

    departure_sec = departure_time.hour * 3600 + departure_time.minute * 60 + departure_time.second
    max_driving_seconds = max_driving_hours * 3600

    time_params = {}
    for p in points:
        time_params[p.id] = {
            'from': (p.time_from * 60) if p.time_from is not None else None,
            'to': (p.time_to * 60) if p.time_to is not None else None,
            'service': p.service_time * 60,
            'asap': p.asap
        }

    def calculate_fitness(route_ids):
        current_time = departure_sec
        total_dist = 0
        penalty = 0
        daily_driving_time = 0

        for i in range(len(route_ids) - 1):
            curr_id = route_ids[i]
            next_id = route_ids[i+1]
            t_params = time_params[next_id]
            expected_pos = i + 1
            if next_id in fixed_position_by_id and fixed_position_by_id[next_id] != expected_pos:
                penalty += 1000000
            dist, dur = dist_matrix.get(f"{curr_id}-{next_id}", (float('inf'), float('inf')))
            if dist == float('inf'):
                return float('inf'), float('inf'), float('inf')
            total_dist += dist
            if (daily_driving_time + dur) > max_driving_seconds:
                daily_driving_time = 0
                current_time += 12 * 3600
            current_time += dur
            daily_driving_time += dur
            current_day_seconds = current_time % 86400
            if t_params['from'] is not None:
                if current_day_seconds < t_params['from']:
                    current_time += t_params['from'] - current_day_seconds
                    current_day_seconds = current_time % 86400
            if t_params['to'] is not None:
                if current_day_seconds > t_params['to']:
                    penalty += (current_day_seconds - t_params['to']) * 50
            if t_params['asap']:
                penalty -= max(0, (86400 - (current_time - departure_sec)) * 0.1)
            current_time += t_params['service']
        total_time = current_time - departure_sec
        score = (total_time * w_time) + (total_dist * w_dist) + penalty
        return score, total_dist, total_time

    def create_individual():
        core_size = len(points) - 1
        core_ids = [None] * core_size
        for pid, pos in fixed_position_by_id.items():
            idx = pos - 1
            if 0 <= idx < core_size:
                core_ids[idx] = pid

        free_ids = [p.id for p in points if p.id != start_id and p.id not in fixed_position_by_id]
        random.shuffle(free_ids)
        free_iter = iter(free_ids)
        for i in range(core_size):
            if core_ids[i] is None:
                core_ids[i] = next(free_iter)

        return [start_id] + core_ids + [start_id] if route_type == 'closed' else [start_id] + core_ids

    def order_crossover(parent1, parent2):
        core1, core2 = (parent1[1:-1], parent2[1:-1]) if route_type == 'closed' else (parent1[1:], parent2[1:])
        size = len(core1)
        free_positions = [i for i in range(size) if i not in {pos - 1 for pos in fixed_position_by_id.values()}]
        if len(free_positions) < 2:
            return parent1[:]

        p1_free = [core1[i] for i in free_positions]
        p2_free = [core2[i] for i in free_positions]
        start, end = sorted(random.sample(range(len(p1_free)), 2))

        child_core = [None] * size
        for pid, pos in fixed_position_by_id.items():
            idx = pos - 1
            if 0 <= idx < size:
                child_core[idx] = pid

        child_free = [None] * len(p1_free)
        child_free[start:end] = p1_free[start:end]
        p2_filtered = [x for x in p2_free if x not in child_free]
        j = 0
        for i in range(len(child_free)):
            if child_free[i] is None:
                child_free[i] = p2_filtered[j]
                j += 1

        for idx, pos in enumerate(free_positions):
            child_core[pos] = child_free[idx]

        return [start_id] + child_core + [start_id] if route_type == 'closed' else [start_id] + child_core

    def mutate(route):
        if random.random() < 0.2:
            core = route[1:-1] if route_type == 'closed' else route[1:]
            locked_positions = {pos - 1 for pos in fixed_position_by_id.values()}
            free_positions = [i for i in range(len(core)) if i not in locked_positions]
            if len(free_positions) >= 2:
                i, j = random.sample(free_positions, 2)
                core[i], core[j] = core[j], core[i]
            if route_type == 'closed':
                route[1:-1] = core
            else:
                route[1:] = core

    population = []
    nn_route = nearest_neighbor(points_dict, start_id, dist_matrix, departure_sec, route_type, time_params)
    nn_score, nn_dist, nn_time = calculate_fitness(nn_route)
    population.append((nn_route, nn_score, nn_dist, nn_time))
    for _ in range(population_size - 1):
        ind = create_individual()
        sc, d, t = calculate_fitness(ind)
        population.append((ind, sc, d, t))
    elite_size = max(2, population_size // 10)
    for _ in range(generations):
        new_generation = heapq.nsmallest(elite_size, population, key=lambda x: x[1])
        while len(new_generation) < population_size:
            p1 = min(random.sample(population, 3), key=lambda x: x[1])[0]
            p2 = min(random.sample(population, 3), key=lambda x: x[1])[0]
            child = order_crossover(p1, p2)
            mutate(child)
            sc, d, t = calculate_fitness(child)
            new_generation.append((child, sc, d, t))
        population = new_generation
    best_route, _best_score, best_dist, best_time = min(population, key=lambda x: x[1])
    return {"route_ids": best_route, "total_distance_meters": best_dist, "total_time_seconds": best_time}