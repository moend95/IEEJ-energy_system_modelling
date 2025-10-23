# -*- coding: utf-8 -*-
"""
Created on Thu Jul 11 16:00:36 2024

@author: pister
"""

import math

# Funktion zur Umwandlung von Längen- und Breitengraden in xy-Koordinaten
def lat_lon_to_xy(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius der Erde in Metern
    x = R * math.radians(lon2 - lon1) * math.cos(math.radians(lat1))
    y = R * math.radians(lat2 - lat1)
    return x, y

# Funktion zur Umwandlung einer Liste von Längen- und Breitengraden in eine Liste von xy-Koordinaten
def convert_coordinates(lat_lon_list):
    xy_list = []
    for i in range(len(lat_lon_list)):
        if i == 0:
            xy_list.append((0, 0))
        else:
            x, y = lat_lon_to_xy(lat_lon_list[0][0], lat_lon_list[0][1], lat_lon_list[i][0], lat_lon_list[i][1])
            xy_list.append((x, y))
    return xy_list

# Eingabeaufforderung für den Nutzer
print("Bitte geben Sie die Koordinaten als Liste von Tupeln ein (z.B. [(51.078558, 6.484447), (51.079871, 6.490275), (51.073527, 6.494424), (51.072446, 6.489946)]):")
user_input = input()
try:
    # Umwandlung der Eingabe in ein Listenformat
    lat_lon_list = eval(user_input)
    # Umwandlung der Liste von Längen- und Breitengraden in eine Liste von xy-Koordinaten
    xy_list = convert_coordinates(lat_lon_list)
    # Ausgabe der Liste von xy-Koordinaten
    print("Hier die Koordinaten als Liste von Tupeln:", xy_list)
except:
    print("Fehler bei der Eingabe. Bitte stellen Sie sicher, dass Ihre Eingabe korrekt formatiert ist.")
