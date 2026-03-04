# pvlib module types 

from pvlib import pvsystem

cec_modules = pvsystem.retrieve_sam('CECMod')
sandia_modules = pvsystem.retrieve_sam('SandiaMod')

print(list(cec_modules.columns)[:10])
print(list(sandia_modules.columns)[:10])

from pvlib import pvsystem
import pandas as pd

# CEC-Moduldatenbank laden
cec_modules = pvsystem.retrieve_sam('CECMod')

# Transponieren: Module als Zeilen, Parameter als Spalten
cec_modules_t = cec_modules.T

# Optional: Index (Modulname) als reguläre Spalte führen
cec_modules_t.reset_index(inplace=True)
cec_modules_t.rename(columns={'index': 'module_name'}, inplace=True)

# CSV-Datei speichern
cec_modules_t.to_csv('cec_modules_full_database.csv', 
                     index=False, 
                     sep=';', 
                     decimal='.')

from pvlib import pvsystem
import pandas as pd

# Sandia-Moduldatenbank laden
sandia_modules = pvsystem.retrieve_sam('SandiaMod')

# Transponieren: Module als Zeilen, Parameter als Spalten
sandia_modules_t = sandia_modules.T

# Modulname als eigene Spalte führen
sandia_modules_t.reset_index(inplace=True)
sandia_modules_t.rename(columns={'index': 'module_name'}, inplace=True)

# CSV-Datei speichern
sandia_modules_t.to_csv('sandia_modules_full_database.csv',
                        index=False,
                        sep=';',
                        decimal='.')




