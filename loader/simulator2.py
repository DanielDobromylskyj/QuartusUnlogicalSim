import time
import sys
from . import components

sys.setrecursionlimit(5000)


GLOBAL_CLOCK_SPEED = 60  # Flips every X ticks

class IntegrityError(Exception):
    pass


class Simulator:
    def __init__(self, schematic, auto_gen=False, is_root=True):
        self.schematic = schematic

        self.connection_map = {}
        self.wire_vcc_lookup = {}

        self.simulation_tick = 0
        self.built = False
        self.status = "Off"

        self.inputs = {}
        self.outputs = {}

        self.pin_inputs = []
        self.pin_outputs = []

        self.global_clock_tick = GLOBAL_CLOCK_SPEED
        self.is_root = is_root

        if auto_gen: # Should run 2 update cycles and everything will be initialised
            max_calls, call = 10, 0
            while (not self.status.startswith("On")) and call < max_calls:
                self.update()
                call += 1

            if call >= max_calls:
                raise IntegrityError("Simulator failed to build, Unknown reason.")


    def __generate_connection_map(self, schematic):
        pin_lookup = {}  # Stores a coord to (id, is_input, extra) lookup
        wire_lookup = {} # Stores a list of other connected wires

        for i, component in enumerate(schematic.components):
            component["_simulation"] = {
                "id": i,
                "tick": 0,
                "connections": {
                    "inputs": {},
                    "outputs": {}
                },
                "pin_vcc": {
                    "inputs": {},
                    "outputs": {}
                }
            }

            if "sub_schematic" in component:
                sub_simulation = Simulator(component["sub_schematic"], auto_gen=True, is_root=False)
                component["_simulation"]["sim"] = sub_simulation

            else:
                if component["type"] == "pin":
                    pass  # If input pin -> Allow changing?

                elif component["type"] == "symbol":
                    component_name = component["data"][1][0]["data"]["text"]

                    if hasattr(components, component_name):
                        component_sim = getattr(components, component_name)
                        component["_simulation"]["sim"] = component_sim(component)

                    else:
                        print(
                            f"[WARNING] Component '{component_name}' is not implemented, any logic connected will not update")

                else:
                    print(f"[WARNING] Unknown component type, cant generate sub-schematic: {component['type']}")

            if component["type"] == "pin":
                pin_name = component["data"]["text"][1]["text"]
                rect = component["data"]["rect"]
                rel = component["data"]["pt"]

                # This bool is then inverted as if our pin is an output, it must have an input. (Stops the sim breaking)
                is_input = "input" in component["data"]

                search = (rect[0] + rel[0], rect[1] + rel[1])
                if search not in pin_lookup:
                    pin_lookup[search] = [(i, not is_input, {"pin_name": pin_name})]
                else:
                    pin_lookup[search].append((i, not is_input, {"pin_name": pin_name}))

                pin_data = {
                    "component": component,
                    "pin_name": pin_name,
                }

                if is_input:
                    self.pin_inputs.append(pin_data)
                else:
                    self.pin_outputs.append(pin_data)


            if component["type"] == "symbol":
                relatives = []
                rect = None
                for [chunk] in component["data"]:
                    if type(chunk) is dict and chunk["type"] == "rect":
                        rect = chunk["data"]

                    if type(chunk) is dict and chunk["type"] == "port":
                        pin_name = chunk["data"]["text"][1]["text"]
                        rel = chunk["data"]["pt"]
                        relatives.append(
                            (rel, "input" in chunk["data"], pin_name)
                        )

                for rel, pin_mode, pin_name in relatives:
                    search = (rect[0] + rel[0], rect[1] + rel[1])
                    if search not in pin_lookup:
                        pin_lookup[search] = [(i, pin_mode, {"pin_name": pin_name})]
                    else:
                        pin_lookup[search].append((i, pin_mode, {"pin_name": pin_name}))

        for wire in schematic.connections:
            xy1, xy2 = tuple(wire[0]["data"]), tuple(wire[1]["data"])

            if xy1 not in wire_lookup:
                wire_lookup[xy1] = []

            if xy2 not in wire_lookup:
                wire_lookup[xy2] = []

            wire_lookup[xy1].append(xy2)
            wire_lookup[xy2].append(xy1)

        def search_connection(start_xy, last_xy=None):
            """ Returns a list of connected component IDs"""
            used_wires = [start_xy]
            results = []

            if start_xy in pin_lookup:
                results.extend([
                    (sub[0], sub[2])
                    for sub in pin_lookup[start_xy]
                ])

            if start_xy in wire_lookup:
                connections = wire_lookup[start_xy]
                for next_xy in connections:
                    if next_xy != last_xy:
                        search, wires = search_connection(next_xy, start_xy)

                        results.extend(search)
                        used_wires.extend(wires)

            return results, used_wires


        # Generate connections
        for pin_xy, pins in pin_lookup.items():
            for (comp_id, is_input, extra) in pins:
                res, wires = search_connection(tuple(pin_xy))

                if len(res) > 0:
                    sim_data = schematic.components[comp_id]["_simulation"]
                    direction = "inputs" if is_input else "outputs"
                    pin_name = str(extra["pin_name"])

                    if pin_name in sim_data["connections"][direction]:
                        raise IntegrityError("Failed to build connection map, Two or more pins share the same name.")

                    sim_data["pin_vcc"][direction][pin_name] = 0.00
                    sim_data["connections"][direction][pin_name] = res

                    if is_input:
                        for wire in wires:
                            self.wire_vcc_lookup[wire] = (comp_id, pin_name, direction)


    def get_wire_vcc(self, xy1):
        if xy1 not in self.wire_vcc_lookup:
            return None

        comp_id, pin_name, direction = self.wire_vcc_lookup[xy1]
        return self.schematic.components[comp_id]["_simulation"]["pin_vcc"][direction][pin_name]


    def __update_component(self, component):
        """ Cascade update all inputs then compute our outputs """
        sim_data = component["_simulation"]

        # Update component inputs
        for pin_name, data in sim_data["connections"]["inputs"].items():
            for (comp_id, pin_data) in data:
                if sim_data["id"] == comp_id:
                    continue

                next_component = self.schematic.components[comp_id]
                self.__update_pin({
                    "component": next_component,
                    "pin_name": pin_name,
                })

        # Update component internals  - This Fucking TANKS
        if "sim" in component["_simulation"]:
            sim = component["_simulation"]["sim"]

            if isinstance(sim, Simulator):  # Set up its inputs
                for sim_input in sim.pin_inputs:
                    pin_name = sim_input["pin_name"]

                    vcc = component["_simulation"]["pin_vcc"]["inputs"][pin_name]

                    if pin_name in sim_input["component"]["_simulation"]["pin_vcc"]["outputs"]:
                        sim_input["component"]["_simulation"]["pin_vcc"]["outputs"][pin_name] = vcc

            sim.update()

            if isinstance(sim, Simulator):  # Extract its outputs
                for sim_output in sim.pin_outputs:
                    pin_name = str(sim_output["pin_name"])


                    vcc = sim_output["component"]["_simulation"]["pin_vcc"]["inputs"][pin_name]
                    component["_simulation"]["pin_vcc"]["outputs"][pin_name] = vcc

    def __update_pin(self, output_pin):
        """ Recursively search to all inputs, then work back from inputs to outputs """
        sim_data = output_pin["component"]["_simulation"]

        if sim_data["tick"] >= self.simulation_tick:
            return

        sim_data["tick"] = self.simulation_tick
        for pin_name, connections in sim_data["connections"]["inputs"].items():
            for (comp_id, pin_data) in connections:
                component = self.schematic.components[comp_id]
                self.__update_component(component)

                # update vcc(s) down the chain
                output_voltages = component["_simulation"]["pin_vcc"]["outputs"]
                for output_pin, output_connections in component["_simulation"]["connections"]["outputs"].items():
                    pin_voltage = output_voltages[output_pin]

                    for output_connection in output_connections:
                        next_component = self.schematic.components[output_connection[0]]
                        next_pin_name = str(output_connection[1]["pin_name"])

                        if next_pin_name in next_component["_simulation"]["pin_vcc"]["inputs"]:
                            next_component["_simulation"]["pin_vcc"]["inputs"][next_pin_name] = pin_voltage


    def update_inputs(self):
        self.global_clock_tick -= 1

        for pin_input in self.pin_inputs:
            if 'CLK' in pin_input["component"]["_simulation"]["pin_vcc"]["outputs"]:
                if self.global_clock_tick == 0:
                    value = pin_input["component"]["_simulation"]["pin_vcc"]["outputs"]["CLK"]
                    pin_input["component"]["_simulation"]["pin_vcc"]["outputs"]["CLK"] = 1 - value

        # Update Clocks
        if self.global_clock_tick == 0:
            self.global_clock_tick = GLOBAL_CLOCK_SPEED


    def update_simulation(self):
        if self.is_root:
            self.update_inputs()

        for output_pin in self.pin_outputs:
            self.__update_pin(output_pin)

        self.simulation_tick += 1


    def update(self):
        if not self.built and self.status == "Off":
            self.status = "Building"

        elif not self.built and self.status == "Building":
            start = time.time()
            self.__generate_connection_map(self.schematic)
            end = time.time()
            self.status = f"On (built in {round((end - start) * 1000)}ms)"
            self.built = True

        else:
            self.update_simulation()