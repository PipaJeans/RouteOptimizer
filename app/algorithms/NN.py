def nearest_neighbor(points_dict, start_id, dist_matrix, departure_ts, route_type, time_params):
    unvisited = list(points_dict.keys())
    unvisited.remove(start_id)
    fixed_points = sorted(
        [p for pid, p in points_dict.items() if pid != start_id and p.fixed_order is not None],
        key=lambda p: p.fixed_order
    )
    fixed_position_by_id = {p.id: i + 1 for i, p in enumerate(fixed_points)}

    route = [start_id]
    current_time = departure_ts
    while unvisited:
        last_id = route[-1]
        best_next = None
        best_score = float('inf')
        expected_index = len(route)
        fixed_candidates = [
            pid for pid in unvisited
            if fixed_position_by_id.get(pid) == expected_index
        ]
        if fixed_candidates:
            best_next = fixed_candidates[0]
        else:
            for pid in unvisited:
                p = points_dict[pid]
                if fixed_position_by_id.get(pid, 0) > expected_index:
                    continue
                dist, dur = dist_matrix.get(f"{last_id}-{pid}", (float('inf'), float('inf')))
                arrival_time = current_time + dur
                arrival_day_seconds = arrival_time % 86400
                t_from = time_params[pid]['from']
                wait_time = 0
                if t_from is not None and arrival_day_seconds < t_from:
                    wait_time = t_from - arrival_day_seconds
                score = dur + wait_time
                t_to = time_params[pid]['to']
                arrival_after_wait_day_seconds = (arrival_time + wait_time) % 86400
                if t_to is not None and arrival_after_wait_day_seconds > t_to:
                    score += (arrival_after_wait_day_seconds - t_to) * 50
                if score < best_score:
                    best_score = score
                    best_next = pid

        if best_next is None:
            fixed_unvisited = [pid for pid in unvisited if pid in fixed_position_by_id]
            if fixed_unvisited:
                best_next = min(fixed_unvisited, key=lambda pid: fixed_position_by_id[pid])
            else:
                best_next = unvisited[0]

        route.append(best_next)
        unvisited.remove(best_next)
        _, dur = dist_matrix.get(f"{last_id}-{best_next}", (0, 0))
        arrival = current_time + dur
        arrival_day_seconds = arrival % 86400
        t_from = time_params[best_next]['from']
        wait = 0
        if t_from is not None and arrival_day_seconds < t_from:
            wait = t_from - arrival_day_seconds
        current_time = arrival + wait + time_params[best_next]['service']
    if route_type == 'closed':
        route.append(start_id)

    return route