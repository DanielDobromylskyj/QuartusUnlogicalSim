
class Simulator:
    def __init__(self, schematic):
        self.schematic = schematic

        self.connection_map = {}
        self.__generate_connection_map(schematic)


    def __generate_connection_map(self, schematic):
        pass

    def update(self):
        pass
