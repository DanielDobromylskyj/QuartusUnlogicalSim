from io import StringIO
import os

from .simulator import Simulator
from .draw import Render as Renderer


def read_next_internal(file):
    if type(file) == str:
        file = StringIO(file)

    chunk = ""
    in_comment = False
    found_internal = False
    depth = 0

    while True:
        char = file.read(1)

        if char == "":
            break

        chunk += char

        if chunk.endswith("/*"):
            in_comment = True

        if in_comment and chunk.endswith("*/"):
            in_comment = False
            chunk = ""

        if not in_comment:
            if char == "(":
                found_internal = True
                depth += 1

            if char == ")":
                depth -= 1

        if found_internal and depth == 0:
            break

    return chunk.strip()[1:-1]

def split_at_spaces(text):
    text = text.replace("\t", " ")
    chunks = []
    chunk = ""

    depth = 0
    in_string = False

    for char in text:
        chunk += char

        if not in_string:
            if char == '"':
                in_string = True

            if char == " " and depth == 0:
                chunks.append(chunk.strip())
                chunk = ""

            if char == "(":
                depth += 1

            if char == ")":
                depth -= 1

        else:
            if char == '"':
                in_string = False

    chunks.append(chunk.strip())
    return chunks




class Schematic:
    def __init__(self, path):
        self.path = path

        self.components = []
        self.connections = []
        self.junctions = []

        self.sub_schematics = []

        with open(self.path, "r") as f:
            self.layout = self.__parse(f)

        self.__load_layout()


    def reload(self):
        self.components = []
        self.connections = []
        self.junctions = []

        self.sub_schematics = []

        with open(self.path, "r") as f:
            self.layout = self.__parse(f)

        self.__load_layout()

    def __extract_symbol_file_info(self, component):
        comp_name = None
        comp_instance = None

        for chunk in component["data"]:
            if type(chunk[0]) == dict and chunk[0]["type"] == "text":
                value = chunk[0]["data"]["text"]

                if comp_name is None:
                    comp_name = value

                elif comp_instance is None:
                    comp_instance = value

        return {
            "name": comp_name,
            "instance": comp_instance
        }

    def __load_layout(self):
        working_directory = os.path.dirname(self.path)

        for component in self.layout:
            if component["type"] == "junction":
                self.junctions.append(component["data"])

            if component["type"] == "connector":
                self.connections.append(component["data"])

            if component["type"] == "pin":
                self.components.append(component)

            if component["type"] == "symbol":
                info = self.__extract_symbol_file_info(component)

                possible_sub_schematic = os.path.join(working_directory, f'{info["name"]}.bdf')

                if os.path.exists(possible_sub_schematic):
                    sub_schematic = Schematic(possible_sub_schematic)

                    component["sub_schematic"] = sub_schematic
                    self.sub_schematics.append(sub_schematic)


                self.components.append(component)



    def __parse(self, f):
        layout = []
        while True:
            chunk = read_next_internal(f)

            if not chunk:
                break

            parts = split_at_spaces(chunk)
            part_type, args = parts[0], parts[1:]

            if not args:
                layout.append(part_type)
                continue

            sub_layout = []
            for arg in args:
                skip = True
                for char in list(arg):
                    if char not in "-.0123456789":
                        skip = False
                        continue

                if skip:
                    sub_layout.append(
                        arg
                    )
                else:
                    sub_layout.append(
                        self.__parse(StringIO(arg))
                    )

            if part_type == "version":
                sub_layout = sub_layout[0][0]

            if part_type == "header":
                sub_layout = {
                    "type": sub_layout[0][0],
                    "version": sub_layout[1][0]["data"],
                }

            if part_type == "rect" or part_type == "pt":
                sub_layout = [
                    int(x) if type(x) is str else int(x[0]) for x in sub_layout
                ]
            if part_type == "font_size":
                sub_layout = int(sub_layout[0])

            if part_type == "font":
                data = {
                    "name": sub_layout[0][0],
                }

                for chunk in sub_layout[1]:
                    if type(chunk) is dict:
                        if chunk["type"] == "font_size":
                            data["font_size"] = int(chunk["data"])


                sub_layout = data

            if part_type == "text":
                data = {
                    "text": sub_layout[0][0],
                }

                for chunk in sub_layout[1]:
                    if type(chunk) is dict:
                        data[chunk["type"]] = chunk["data"]

                    elif type(chunk) is str:
                        data[chunk] = True


                sub_layout = data

            if part_type == "line":
                sub_layout = [
                    sub_layout[0][0]["data"],
                    sub_layout[0][1]["data"]
                ]

            if part_type == "junction":
                sub_layout = sub_layout[0][0]

            if part_type == "connector":
                sub_layout = [
                    sub_layout[0][0],
                    sub_layout[1][0]
                ]


            if part_type == "pin" or part_type == "port":
                new_internals = {"text": [], "misc": []}

                for chunk in sub_layout:
                    if not chunk:
                        continue

                    if chunk[0] in ("input", "output"):
                        new_internals[chunk[0]] = True

                    elif type(chunk[0]) == dict:
                        if chunk[0]["type"] == "rect":
                            new_internals["rect"] = chunk[0]["data"]

                        elif chunk[0]["type"] == "text":
                            new_internals["text"].append(chunk[0]["data"])

                        elif chunk[0]["type"] == "drawing":
                            new_internals["drawing"] = chunk[0]["data"]

                        elif chunk[0]["type"] == "pt":
                            new_internals["pt"] = chunk[0]["data"]

                        elif chunk[0]["type"] == "line":
                            new_internals["line"] = chunk[0]["data"]

                        else:
                            new_internals["misc"].append(chunk)
                    else:
                        new_internals["misc"].append(chunk)

                sub_layout = new_internals

            if part_type == "port":
                new_internals = {"text": [], "misc": []}

                for chunk in sub_layout:
                    if not chunk:
                        continue

                    if chunk[0] in ("input", "output"):
                        new_internals[chunk[0]] = True



            layout.append({
                "type": part_type,
                "data": sub_layout
            })




        return layout



