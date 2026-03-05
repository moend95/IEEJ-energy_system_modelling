


def get_int_input(prompt, default):
    """Fragt Float mit Default ab"""
    try:
        user_input = input(prompt).strip()
        return int(user_input) if user_input else default
    except ValueError:
        print(f"⚠️  Ungültige Eingabe! Nutze default: {default}")
        return default


# hilfsfunktionen.py
def get_pv_configuration(step_size_default, pv_typen):
    """Abfrage aller PV-Parameter"""
    print("\n" + "=" * 50)
    print("PV-SYSTEM KONFIGURATION")
    print("=" * 50)

    # Schrittweite
    step_size = step_size_default
    #SCHRITTWEITEN ABFRAGE gerade ausgeschaltet...
    #step_size = get_int_input(f'📏 Schrittweite für PV Berechnung [default: {step_size_default}m]: ',step_size_default)

    # PV-Typen auswählen
    print("\n📋 Verfügbare PV-Typen:")
    for i, typ in enumerate(pv_typen):
        print(f"   {typ}")  # ← +1 bei der Anzeige! {i + 1}:

    pv_types_input = input("\n🔧 Typen auswählen (z.B. '1,4' für mehrere): ").strip()

    try:
        # Indizes parsen und -1 rechnen (weil Nutzer 1-basiert eingibt)
        indices = [int(x.strip()) - 1 for x in pv_types_input.split(",")]

        # Validierung: sind alle Indizes gültig?
        if all(0 <= i < len(pv_typen) for i in indices):
            selected_types = [pv_typen[i] for i in indices]
            #print(f"✅ Gewählte Typen: {selected_types}")
        else:
            raise ValueError("Index außerhalb des Bereichs")

    except (ValueError, IndexError):
        # Default: erste und letzte (Windschutzwand & Böschung)
        selected_types = [pv_typen[0], pv_typen[3]]
        print(f"⚠️  Ungültig! Default: {selected_types}")

    return step_size, selected_types
