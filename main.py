from loader import Schematic
from loader.draw import Render
import json

# Working:
# "test_data/quartus/traffic_lights.bdf"
# "test_data/quartus/Ripple-Counter.bdf"
# "test_data/quartus/working_interactions.bdf"

# Not Working:

schem = Schematic("test_data/quartus/main.bdf")

#print(json.dumps(schem.layout, indent=2))


app = Render(schem)

while True:
    app.update()