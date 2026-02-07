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

    step_size = get_int_input(
        f'📏 Schrittweite, für nur eine Berechnung großen Wert wählen [default: {step_size_default}m]: ',
        step_size_default
    )

    print("\n📋 Verfügbare PV-Typen:")
    for i, typ in enumerate(pv_typen):
        print(f"   {i}: {typ}")

    pv_types_input = input("\n🔧 Typen auswählen (z.B. '0,3'): ")

    try:
        indices = [int(x.strip()) for x in pv_types_input.split(",")]
        selected_types = [pv_typen[i] for i in indices]
    except (ValueError, IndexError):
        selected_types = [pv_typen[0], pv_typen[3]]
        print(f"⚠️  Default: {selected_types}")

    return step_size, selected_types

