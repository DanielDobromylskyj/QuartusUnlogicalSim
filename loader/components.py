
class Component:
    def __init__(self, component):
        self.component = component
        self.ready = False

        self.inputs = {}
        self.outputs = {}


    def __load(self):
        self.ready = True
        self.outputs = {}

        for pin_name in self.component["_simulation"]["pin_vcc"]["outputs"].keys():
            self.outputs[pin_name] = 0.0

    def __prepare(self):
        self.inputs = {}
        for pin_name, vcc in self.component["_simulation"]["pin_vcc"]["inputs"].items():
            self.inputs[pin_name] = vcc

    def __store(self):
        for pin_name in self.component["_simulation"]["pin_vcc"]["outputs"].keys():
            self.component["_simulation"]["pin_vcc"]["outputs"][pin_name] = self.outputs.get(pin_name, 0)


    def calculate_outputs(self):
        raise NotImplementedError

    def update(self):
        if not self.ready:
            self.__load()

        self.__prepare()
        self.calculate_outputs()
        self.__store()

class NAND2(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = 1 - (self.inputs["IN1"] * self.inputs["IN2"])


class NAND3(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = 1 - (self.inputs["IN1"] * self.inputs["IN2"] * self.inputs["IN3"])

class NOT(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = 1 - self.inputs["IN"]

class AND2(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = self.inputs["IN1"] * self.inputs["IN2"]

class AND3(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = self.inputs["IN1"] * self.inputs["IN2"] * self.inputs["IN3"]


class OR2(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = min(sum(self.inputs.values()), 1)

class OR3(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = min(sum(self.inputs.values()), 1)

class OR4(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = min(sum(self.inputs.values()), 1)

class OR6(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = min(sum(self.inputs.values()), 1)

class OR8(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"] = min(sum(self.inputs.values()), 1)


class DFF(Component):
    def __init__(self, component):
        super().__init__(component)

        self.internal_state = 0
        self.prev_clk = 0

    def calculate_outputs(self):
        d    = int(self.inputs.get("D", 0))
        clk  = int(self.inputs.get("CLK", 0))
        clrn = 1 - int(self.inputs.get("CLRN", None) or 0)
        prn = int(self.inputs.get("PRN", None) or 1)

        # Async controls (highest priority)
        if clrn == 0:
            self.internal_state = 0
        elif prn == 0:
            self.internal_state = 1
        elif self.prev_clk == 0 and clk == 1:
            self.internal_state = d

        else:
            # Rising edge
            if self.prev_clk == 0 and clk == 1:
                self.internal_state = d

        # Drive outputs
        self.outputs["Q"] = self.internal_state

        # Save clock
        self.prev_clk = clk


