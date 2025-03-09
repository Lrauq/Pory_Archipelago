from location_ids import location_flag_ids
from id_data import location_names_to_id

# Using the values of the flag ids and the keys of the location names, print the matching location names
for flag in location_flag_ids:
    value = location_flag_ids[flag]
    if location_names_to_id.get(value):
        print(value)
        
print(len(location_flag_ids))