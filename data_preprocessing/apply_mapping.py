import json
import os

def apply_mapping():
    mapping_file = 'model_build_outputs/stop_id_mapping.json'
    
    if not os.path.exists(mapping_file):
        print(f"Error: {mapping_file} not found. Run stop_id_mapping.py first.")
        return

    print("Loading stop ID mapping...")
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)

    # Dictionary of (source_file, output_file, remapping_logic)
    files_to_process = [
        # Build Inputs
        # ('model_build_inputs/route_data.json', 'model_build_inputs_remapped/route_data.json', 'route_data'),
        # ('model_build_inputs/actual_sequences.json', 'model_build_inputs_remapped/actual_sequences.json', 'actual_sequences'),
        # ('model_build_inputs/package_data.json', 'model_build_inputs_remapped/package_data.json', 'package_data'),
        ('model_build_inputs/travel_times.json', 'model_build_inputs_remapped/travel_times.json', 'travel_times'),
        # Apply Inputs
        # ('model_apply_inputs/new_route_data.json', 'model_apply_inputs_remapped/new_route_data.json', 'route_data'),
        # ('model_apply_inputs/new_travel_times.json', 'model_apply_inputs_remapped/new_travel_times.json', 'travel_times'),
        # # Score Inputs
        # ('model_score_inputs/new_actual_sequences.json', 'model_score_inputs_remapped/new_actual_sequences.json', 'actual_sequences')
    ]

    for src, dst, logic in files_to_process:
        if not os.path.exists(src):
            print(f"Skipping {src} (not found)")
            continue
            
        print(f"Processing {src} -> {dst}...")
        
        # For very large files, we might want to process by route to save memory
        # But let's try standard load first as structure is a single large object
        with open(src, 'r') as f:
            data = json.load(f)
            
        remapped_data = {}
        total_routes = len(data)
        processed_count = 0
        
        for route_id, route_content in data.items():
            processed_count += 1
            if processed_count % 1000 == 0:
                print(f"  Processed {processed_count}/{total_routes} routes...")
                
            route_map = mapping.get(route_id, {})
            
            if logic == 'route_data':
                # route_content['stops'] keys need remapping
                new_stops = {}
                for local_code, stop_info in route_content['stops'].items():
                    global_id = route_map.get(local_code, local_code)
                    new_stops[global_id] = stop_info
                route_content['stops'] = new_stops
                remapped_data[route_id] = route_content
                
            elif logic == 'actual_sequences':
                # route_content['actual'] keys need remapping
                new_actual = {}
                for local_code, rank in route_content['actual'].items():
                    global_id = route_map.get(local_code, local_code)
                    new_actual[global_id] = rank
                route_content['actual'] = new_actual
                remapped_data[route_id] = route_content
                
            elif logic == 'package_data':
                # route_content keys are local_codes
                new_route_content = {}
                for local_code, packages in route_content.items():
                    global_id = route_map.get(local_code, local_code)
                    new_route_content[global_id] = packages
                remapped_data[route_id] = new_route_content
                
            elif logic == 'travel_times':
                # route_content[from][to] keys need remapping
                new_route_content = {}
                for from_code, to_map in route_content.items():
                    from_id = route_map.get(from_code, from_code)
                    new_to_map = {}
                    for to_code, time in to_map.items():
                        to_id = route_map.get(to_code, to_code)
                        new_to_map[to_id] = time
                    new_route_content[from_id] = new_to_map
                remapped_data[route_id] = new_route_content

        # Ensure output directory exists
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        
        with open(dst, 'w') as f:
            json.dump(remapped_data, f)
            
    print("All files processed successfully.")

if __name__ == "__main__":
    apply_mapping()
