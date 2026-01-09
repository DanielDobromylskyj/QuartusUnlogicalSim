from loader import Schematic, Renderer, Simulator

from loader import simulator2

# "test_data/quartus/main.bdf"
# "test_data/quartus/Ripple-Counter_Up.bdf"

schem = Schematic("test_data/quartus/Limited_Ripple-Counter_Up.bdf")


simulator = simulator2.Simulator(schem)
preview = Renderer(schem, simulator)
preview.target_fps = 500

while True:
    simulator.update()
    preview.update()