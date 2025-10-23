import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("OutputElectrolyzer_output.csv")
df.plot(x="time", y="hydrogen production [(Kg/h)/dt]", title="H2-Produktion über Zeit")
plt.show()
