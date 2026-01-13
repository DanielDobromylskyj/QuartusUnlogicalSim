from loader import Schematic, Renderer, Simulator

from loader import simulator2

# "test_data/quartus/main.bdf"
# "test_data/quartus/Ripple-Counter_Up.bdf"

schem = Schematic("test_data/quartus/main.bdf")

"""
>> TODO LIST

- File Selection

- Robustness
  - Clock Speed Selection -> Dont allow 0 -> Errors
  
- Performance
  - Faster Zooming -> Currently redraws for every zoom change, make it do a temp zoom until user stops changing zoom

"""



simulator = simulator2.Simulator(schem)
preview = Renderer(schem, simulator)
preview.target_fps = 500

simulator.full_rescan()

while True:
    simulator.update()
    preview.update()