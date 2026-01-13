
class Component:
    def __init__(self, component):
        self.component = component
        self.ready = False

        self.inputs = {}
        self.outputs = {}

        self.tick = 0


    def __load(self):
        self.ready = True
        self.outputs = self.component.outputs

    def __prepare(self):
        self.inputs = self.component.inputs

    def calculate_outputs(self):
        raise NotImplementedError

    def __clone_outputs(self):
        return [
            (int(pin.vcc), pin)
            for key, pin in self.component.outputs.items()
        ]

    def update(self):
        if not self.ready:
            self.__load()
            self.__prepare()

        cache = self.__clone_outputs()

        self.calculate_outputs()

        to_update = []
        for old_vcc, pin in cache:
            if old_vcc != pin.vcc:
                to_update.extend(pin.connections)

        return to_update



class NAND2(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = 1 - (self.inputs["IN1"].vcc * self.inputs["IN2"].vcc)


class NAND3(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = 1 - (self.inputs["IN1"].vcc * self.inputs["IN2"].vcc * self.inputs["IN3"].vcc)

class NOT(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = 1 - self.inputs["IN"].vcc

class AND2(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = self.inputs["IN1"].vcc * self.inputs["IN2"].vcc

class AND3(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = self.inputs["IN1"].vcc * self.inputs["IN2"].vcc * self.inputs["IN3"].vcc


class OR2(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = min(sum([pin.vcc for pin in self.inputs.values()]), 1)

class OR3(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = min(sum([pin.vcc for pin in self.inputs.values()]), 1)

class OR4(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = min(sum([pin.vcc for pin in self.inputs.values()]), 1)

class OR6(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = min(sum([pin.vcc for pin in self.inputs.values()]), 1)

class OR8(Component):
    def __init__(self, component):
        super().__init__(component)

    def calculate_outputs(self):
        self.outputs["OUT"].vcc = min(sum([pin.vcc for pin in self.inputs.values()]), 1)


class DFF(Component):
    def __init__(self, component):
        super().__init__(component)

        self.internal_state = 0
        self.prev_clk = 0

    def __get_vcc(self, key, default=0):
        pin = self.inputs.get(key)

        return default if pin is None else int(pin.vcc)

    def calculate_outputs(self):
        d   = self.__get_vcc("D", 0)
        clk = self.__get_vcc("CLK", 0)

        # active-low async signals
        clrn = 1 - self.__get_vcc("CLRN", 0)
        prn  = 1 - self.__get_vcc("PRN", 0)

        # --- async controls (highest priority) ---
        if clrn == 0:
            self.internal_state = 0

        elif prn == 0:
            self.internal_state = 1

        # --- rising edge ---
        elif self.prev_clk == 0 and clk == 1:
            self.internal_state = d

        # drive outputs
        self.outputs["Q"].vcc = self.internal_state

        # store clock for next edge detect
        self.prev_clk = clk



