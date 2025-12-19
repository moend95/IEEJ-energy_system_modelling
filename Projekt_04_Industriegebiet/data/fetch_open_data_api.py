# %%
#data from: https://opendata.ffe.de/dataset/real-sampled-charging-profiles-for-electric-vehicles-within-the-project-munich-electrified-germany/






import requests

url = "https://api.opendata.ffe.de"
params = {
    "id_opendata": 59,
    "internal_id_1": 5,
}
print(params['internal_id_1'])

# check if the API is available by making a GET request to the /health endpoint
response = requests.get(url + '/health')
if not response.status_code == 200:
    print(f"API not available. Status code: {response.status_code}")
    print(response.json())
    exit()

print('API available.')

# fetch the data by making a GET request to the 'opendata' endpoint
# using the previously defined parameters
response = requests.get(url + '/opendata', params=params)

# check if the request was successful
if not response.status_code == 200:
    print(f"Request failed. Status code: {response.status_code}.")
    print(response.json())
    exit()

print('Request successful.')

# get the response as a dictionary
data = response.json()

# print some of the metadata
print(f"id_opendata: {data['id_opendata']}")
print(f"title: {data['title']}")

# print the first three data entries
for data_entry in data['data'][:3]:
    print(data_entry)


import json
open_data_internal_id = params['internal_id_1']
file_name = f'open_data_{open_data_internal_id}'

# Beispiel: Daten in 'ffe_data.json' speichern
with open(f"{file_name}.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)



import pandas as pd

df = pd.DataFrame(data["data"])
df.to_csv(f"{file_name}.csv", index=False)


