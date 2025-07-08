'''
-PV Dichte berechnen (abhängig von Traktorbreite plus Wenderadius, jede Spalte abfahren oder jede zweite wegen wenderadius)
	- Eingabe: Traktor Breite und Länge bestimmt "freien Randbereich/Randfläche"
	- Eingabe: Traktor Breite bestimmt "Spalten-Breite plus Sicherheitsabstand"

Input: Flächen aus OSM (Area_Import_OSM), Traktor Breite (und Länge?), Sicherheitsfaktor (wenn nicht intern vorgegeben)
Output: Map Plot mit Linien eingezeichnet, Anzahl an PV Modulen, Flächennutzung Anteile
'''