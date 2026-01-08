from loader import Schematic, Renderer, Simulator


schem = Schematic("test_data/quartus/main.bdf")

preview = Renderer(schem)
simulator = Simulator(schem)

while True:
    simulator.update()
    preview.update()