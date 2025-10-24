from Energielandschaft_Main_Version_5 import AgriPV

if __name__ == '__main__':
    app = AgriPV()

    # Beispiel-Polygon (kleines Rechteck nahe Köln, nur zu Testzwecken)
    coords = [
        (6.940, 50.930),
        (6.945, 50.930),
        (6.945, 50.935),
        (6.940, 50.935),
        (6.940, 50.930),
    ]

    app.set_custom_polygon(coords)
    app.project_to_utm()

    # Beispiel-Parameter
    Lvor = 12.0
    Bg = 6.0
    An = 0.0
    Aarbeits = 4.0
    max_area_percentage = 60.0

    app.calculate_pv_layout(Lvor, Bg, An, Aarbeits, max_area_percentage)

    out_filename = 'agri_pv_plot_test.html'
    print('Erzeuge Karte...', out_filename)
    app.export_plot_to_osm_html(offset_polygon_utm=getattr(app, 'offset_polygon_utm', None),
                                filename=out_filename,
                                show_in_browser=True,
                                line_weight_scale=max(1.0, Bg/2.0))
    print('Fertig. Datei sollte vorhanden sein:', out_filename)
