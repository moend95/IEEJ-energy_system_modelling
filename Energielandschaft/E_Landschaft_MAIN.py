'''
CODE BLÖCKE / FUNCTIONS

siehe Area_Import_OSM.py
-OSM Flächen auslesen (Koordinaten bbox eingabe -> Flächen als Rechtecke vereinfacht)
	-Mittelpunkt für PV berechnung

siehe AgriPV_Dichte.py
-PV Dichte berechnen (abhängig von Traktorbreite plus Wenderadius, jede Spalte abfahren oder jede zweite wegen wenderadius)
	- Eingabe: Traktor Breite und Länge bestimmt "freien Randbereich/Randfläche"
	- Eingabe: Traktor Breite bestimmt "Spalten-Breite plus Sicherheitsabstand"

siehe PV_Berechnung.py
-PV lib Berechnung (abhängig von PV Typ, Koordinaten der Fläche)
'''