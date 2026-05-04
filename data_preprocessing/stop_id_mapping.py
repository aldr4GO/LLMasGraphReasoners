import json
import os
from collections import defaultdict

def create_mapping():
    # File paths
    build_route_file = 'model_build_inputs/route_data.json'
    apply_route_file = 'model_apply_inputs/new_route_data.json'
    
    output_mapping_file = 'model_build_outputs/stop_id_mapping.json'
    output_canonical_file = 'model_build_outputs/canonical_stop_ids.json'
    
    # Storage
    # (rounded_lat, rounded_lng) -> STOP_ID
    coord_to_id = {}
    # STOP_ID -> {lat, lng, zone_id, type}
    id_to_metadata = {}
    # route_id -> local_code -> STOP_ID
    route_stop_mapping = defaultdict(dict)
    
    stop_counter = 0

    def process_file(filepath):
        nonlocal stop_counter
        print(f"Processing {filepath}...")
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        for route_id, route_info in data.items():
            for stop_code, stop_details in route_info['stops'].items():
                lat = stop_details['lat']
                lng = stop_details['lng']
                # Round to 5 decimal places for ~1.1m precision
                coord_key = (round(lat, 5), round(lng, 5))
                
                if coord_key not in coord_to_id:
                    stop_counter += 1
                    stop_id = f"STOP_{stop_counter:06d}"
                    coord_to_id[coord_key] = stop_id
                    id_to_metadata[stop_id] = {
                        "lat": coord_key[0],
                        "lng": coord_key[1],
                        "zone_id": stop_details.get('zone_id'),
                        "type": stop_details.get('type')
                    }
                
                route_stop_mapping[route_id][stop_code] = coord_to_id[coord_key]

    # Run processing
    if os.path.exists(build_route_file):
        process_file(build_route_file)
    else:
        print(f"Warning: {build_route_file} not found")
        
    if os.path.exists(apply_route_file):
        process_file(apply_route_file)
    else:
        print(f"Warning: {apply_route_file} not found")

    print(f"Total unique physical stops identified: {len(id_to_metadata)}")
    
    # Save results
    print(f"Saving mappings to model_build_outputs/...")
    with open(output_mapping_file, 'w') as f:
        json.dump(route_stop_mapping, f, indent=2)
        
    with open(output_canonical_file, 'w') as f:
        json.dump(id_to_metadata, f, indent=2)
    
    print("Done!")

if __name__ == "__main__":
    create_mapping()
