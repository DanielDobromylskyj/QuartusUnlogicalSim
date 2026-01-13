import time
from collections import deque

from . import components



"""
Simulator V2

>>   Possible Optimisations   <<

Replace dicts with lists / tuples where possible
  - Pin Name -> Pin ID


"""

GLOBAL_CLOCK_SPEED = 60  # Flips every X ticks

class IntegrityError(Exception):
    pass


class SimulatorWire:
    def __init__(self, output_comp, pin_out, input_comp, pin_in):
        self.input_comp = input_comp
        self.output_comp = output_comp

        self.pin_in_name = pin_in
        self.pin_out_name = pin_out



class ComponentPin:
    def __init__(self, xy):
        self.connections = []

        self.last_clk = 0
        self.settings = {
            "is_clock": False,
            "clock_speed_hz": 0,
            "is_toggle": True,
        }

        self.vcc = 0.0
        self.xy = xy


class SimulatorComponent:
    def __init__(self, component):
        self.component = component
        self.component_name = None

        self.is_input = None
        self.internal_component = None
        self.rect = None
        self.has_sub_schematic = False

        self.simulator_tick = 0
        self.last_hash = -1

        self.tick = 0

        self.inputs = {}
        self.outputs = {}

        self.__load()

    def __str__(self):
        if self.component_name == "pin.generic":
            pins = self.outputs if self.is_input else self.inputs
            pin_name = list(pins.keys())[0]

            return f"pin.{'input' if self.is_input else 'output'}.{pin_name}"

        if isinstance(self.internal_component, Simulator):
            return "symbol.schematic"

        return f"symbol.{self.internal_component.__class__.__name__}"



    def get_input_hash(self):
        """
            If this becomes a bottleneck look into hashing with cpython like:
            hash(tuple(pin.vcc for pin in self.inputs.values()))

            :return:
        """
        hv = 0
        for pin in self.inputs.values():
            hv = (hv << 1) ^ int(pin.vcc)
        return hv

    def __load(self):
        if self.component["type"] == "pin":
            self.component_name = "pin.generic"
            name = self.component["data"]["text"][1]["text"]
            self.is_input = "input" in self.component["data"]

            rect = self.component["data"]["rect"]
            self.rect = rect
            local_xy = self.component["data"]["pt"]

            xy = ( rect[0] + local_xy[0], rect[1] + local_xy[1] )

            # If this component is an input, then it will output a value, so we set a pin for that.
            if self.is_input:
                self.outputs[str(name)] = ComponentPin(xy)
            else:
                self.inputs[str(name)] = ComponentPin(xy)

        elif self.component["type"] == "symbol":
            comp_name = self.component["data"][1][0]["data"]["text"]
            self.component_name = comp_name

            if "sub_schematic" in self.component:
                self.internal_component = Simulator(self.component["sub_schematic"], auto_gen=True, is_root=False)
                self.has_sub_schematic = True

            elif hasattr(components, comp_name):
                self.internal_component = getattr(components, comp_name)(self)

            else:
                print(f"[WARNING] Unknown Schematic / Component:", comp_name)

            rect = None
            for [chunk] in self.component["data"]:
                if type(chunk) is dict and chunk["type"] == "rect":
                    rect = chunk["data"]

                if type(chunk) is dict and chunk["type"] == "port":
                    is_input = "input" in chunk["data"]
                    pin_name = chunk["data"]["text"][0]["text"]

                    if rect is None:
                        raise IntegrityError("Failed to load symbol: Created port before declaring component rect")

                    local_xy = chunk["data"]["pt"]
                    self.rect = rect

                    xy = ( rect[0] + local_xy[0], rect[1] + local_xy[1] )

                    if is_input:
                        self.inputs[str(pin_name)] = ComponentPin(xy)
                    else:
                        self.outputs[str(pin_name)] = ComponentPin(xy)

        else:
            raise NotImplementedError(f"Cannot load SimulatorComponent of type: '{self.component['type']}'")

    def get_pin_vcc(self, pin_name: str, is_input: bool):
        if is_input:
            return self.inputs[pin_name].vcc
        else:
            return self.outputs[pin_name].vcc

    def set_pin_vcc(self, pin_name: str, is_input: bool, vcc: float | int):
        if is_input:
            self.inputs[pin_name].vcc = vcc
        else:
            self.outputs[pin_name].vcc = vcc

    def get_pin_coord_map(self):
        """ Medium computational cost, Should only be called once when building """
        pin_map = {}

        for pin_name, pin_in in self.inputs.items():
            pin_map[pin_in.xy] = [{
                "component": self, "pin": pin_name, "is_input": True
            }]

        for pin_name, pin_out in self.outputs.items():
            pin_map[pin_out.xy] = [{
                "component": self, "pin": pin_name, "is_input": False
            }]

        return pin_map

    def needs_update(self):
        return True # self.get_input_hash() != self.last_hash

    def update(self):
        if self.internal_component:
            return self.internal_component.update()

        dirty_components = []
        if self.component_name == "pin.generic":
            if self.is_input:
                pin: ComponentPin = self.outputs[list(self.outputs.keys())[0]]
                dirty_components.extend(pin.connections)

        self.last_hash = self.get_input_hash()
        return dirty_components


class Simulator:
    def __init__(self, schematic, auto_gen=False, is_root=True):
        self.schematic = schematic

        self.connection_map = {}
        self.wire_vcc_lookup = {}

        self.simulation_tick = 0
        self.built = False
        self.status = "Off"

        self.dirty_components = []
        self.last_hash = -1

        self.components = []
        self.wires = []

        self.pin_inputs = []
        self.pin_outputs = []

        self.inputs = {}
        self.outputs = {}

        self.clocks = []

        self.is_root = is_root

        if auto_gen: # Should run 2 update cycles and everything will be initialised
            max_calls, call = 10, 0
            while (not self.status.startswith("On")) and call < max_calls:
                self.update()
                call += 1

            if call >= max_calls:
                raise IntegrityError("Simulator failed to build, Unknown reason.")

        self.full_rescan()

    def build(self):
        """ This is run once at run time to avoid expensive trace calculations every frame """
        pin_lookup = {}
        wire_lookup = {}

        for component in self.schematic.components:
            comp = SimulatorComponent(component)
            self.components.append(comp)

            if comp.component_name == "pin.generic":
                if comp.is_input:
                    pin_name = list(comp.outputs.keys())[0]
                    self.pin_inputs.append((comp, pin_name))
                    self.inputs[pin_name] = comp

                else:
                    pin_name = list(comp.inputs.keys())[0]
                    self.pin_outputs.append((comp, pin_name))
                    self.outputs[pin_name] = comp


            # Generate a pin map
            for xy, values in comp.get_pin_coord_map().items():
                if xy not in pin_lookup:
                    pin_lookup[xy] = []

                pin_lookup[xy].extend(values)

        # Generate a 2-way wire map
        for wire in self.schematic.connections:
            xy1, xy2 = tuple(wire[0]["data"]), tuple(wire[1]["data"])

            if xy1 not in wire_lookup:
                wire_lookup[xy1] = []

            if xy2 not in wire_lookup:
                wire_lookup[xy2] = []

            wire_lookup[xy1].append(xy2)
            wire_lookup[xy2].append(xy1)

        def search_connection(start_xy, last_xy=None, start_comp=None):
            """ Returns a list of connected component IDs"""
            used_wires = [start_xy]
            results = []

            if start_xy in pin_lookup:
                for result in pin_lookup[start_xy]:
                    if result["component"] != start_comp:
                        results.append(result)

            if start_xy in wire_lookup:
                connections = wire_lookup[start_xy]
                for next_xy in connections:
                    if next_xy != last_xy:
                        search, wires = search_connection(next_xy, start_xy, start_comp)

                        results.extend(search)
                        used_wires.extend(wires)

            return results, used_wires


        # Generate connections
        for pin_xy, pins in pin_lookup.items():

            for pin_data in pins:
                component1 = pin_data["component"]

                results, wires = search_connection(tuple(pin_xy), start_comp=component1)

                if len(results) > 0:
                    is_input1 = pin_data["is_input"]
                    pin_name1 = pin_data["pin"]

                    for wire in wires:
                        pins = component1.inputs if is_input1 else component1.outputs
                        self.wire_vcc_lookup[wire] = pins[pin_name1]

                    for result in results:
                        component2 = result["component"]
                        is_input2 = result["is_input"]
                        pin_name2 = result["pin"]

                        wire = SimulatorWire(component1, pin_name1, component2, pin_name2)
                        self.wires.append(wire)

                        pins1 = component1.inputs if is_input1 else component1.outputs
                        pin2 = component2.inputs if is_input2 else component2.outputs

                        pins1[pin_name1].connections.append((component2, pin_name1, pin_name2))
                        pin2[pin_name2].connections.append((component1, pin_name2, pin_name1))


    def get_wire_vcc(self, start_xy):
        if start_xy not in self.wire_vcc_lookup:
            return None

        return self.wire_vcc_lookup[start_xy].vcc

    def update_input_pin(self, component, vcc):
        pins = list(component.outputs.keys())

        if len(pins) == 0:
            return

        pin_name = pins[0]
        pin_comp = component.outputs[pin_name]
        self.dirty_components.append(component)

        if pin_comp.settings["is_toggle"]:
            if vcc == 1:
                pin_comp.vcc = 1 - pin_comp.vcc
        else:
            pin_comp.vcc = vcc

    def full_rescan(self):
        for component in self.components:
            self.dirty_components.append(component)

    def get_input_hash(self):
        """
            If this becomes a bottleneck look into hashing with cpython like:
            hash(tuple(pin.vcc for pin in self.inputs.values()))

            :return:
        """
        hv = 0
        for component, pin_name in self.pin_inputs:
            hv = (hv << 1) ^ int(component.outputs[pin_name].vcc)
        return hv

    def needs_update(self):
        return self.last_hash != self.get_input_hash()


    def clone_outputs(self):
        return [
            (int(component.inputs[pin_name].vcc), component)
            for component, pin_name in self.pin_outputs
        ]

    def copy_to_component_inputs(self, component):
        simulator = component.internal_component

        for pin_name, pin_comp in component.inputs.items():
            vcc = pin_comp.vcc
            simulator.inputs[pin_name].outputs[pin_name].vcc = vcc

            simulator.dirty_components.append(simulator.inputs[pin_name])


    def copy_from_component_outputs(self, component):
        simulator = component.internal_component
        changed_outputs = []

        for pin_name, pin_comp in component.outputs.items():
            vcc = simulator.outputs[pin_name].inputs[pin_name].vcc

            if pin_comp.vcc != vcc:
                changed_outputs.extend(pin_comp.connections)

            pin_comp.vcc = vcc

        return changed_outputs

    def update_clocks(self):
        current_time = time.time()
        for component, pin_comp in self.clocks:  # Component should be an input pin ONLY
            speed = pin_comp.settings["clock_speed_hz"]

            if speed == 0:
                continue

            ms = 1 / speed

            if current_time - ms > pin_comp.last_clk:
                pin_comp.last_clk = current_time
                pin_comp.vcc = 1 - pin_comp.vcc

                self.dirty_components.append(component)

    def update_simulation(self):
        self.update_clocks()

        queue = deque(self.dirty_components)
        self.dirty_components.clear()

        while queue:
            component = queue.popleft()

            if not component.needs_update():
                continue

            if component.has_sub_schematic:
                self.copy_to_component_inputs(component)

            changed_outputs = component.update()

            if component.has_sub_schematic:
                changed_outputs = self.copy_from_component_outputs(component)

            for next_comp, output_pin, input_pin in changed_outputs:
                if next_comp.tick < self.simulation_tick and component.outputs[output_pin].vcc != next_comp.inputs[input_pin].vcc:
                    next_comp.inputs[input_pin].vcc = component.outputs[output_pin].vcc
                    queue.append(next_comp)


        self.last_hash = self.get_input_hash()
        self.simulation_tick += 1

        return None


    def update(self):
        if not self.built and self.status == "Off":
            self.status = "Building"

        elif not self.built and self.status == "Building":
            start = time.time()
            self.build()
            end = time.time()
            self.status = f"Building (built in {round((end - start) * 1000)}ms)"
            self.built = False

        elif self.status.startswith("Building"):
            start = time.time()

            self.update_simulation()
            self.full_rescan()

            end = time.time()
            self.status = f"On (Restarted in {round((end - start) * 1000)}ms)"
            self.built = True
        else:
            return self.update_simulation()

        return None

    def clear_cache(self):
        pass  # We don't have any caches at the moment

    def reload(self):
        start = time.time()
        self.connection_map = {}
        self.wire_vcc_lookup = {}
        self.clocks = []
        self.dirty_components = []
        self.last_hash = -1
        self.components = []
        self.wires = []
        self.pin_inputs = []
        self.pin_outputs = []
        self.inputs = {}
        self.outputs = {}
        self.simulation_tick = 0
        self.built = False
        self.status = "Off"

        self.schematic.reload()

        self.build()

        self.update_simulation()
        self.full_rescan()

        end = time.time()
        self.status = f"On (Restarted in {round((end - start) * 1000)}ms)"