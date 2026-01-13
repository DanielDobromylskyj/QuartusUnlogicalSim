import os.path
import random

import pygame
import math

from .simulator2 import Simulator

DEFAULT_FONT_SIZE = 8

pygame.init()

def point_to_angle(px, py, cx, cy):
    return math.atan2(py - cy, px - cx)


def draw_arc(surface, color, p1, p2, rect_data, width=2, steps=48):
    x1, y1, x2, y2 = rect_data

    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    rx = abs(x2 - x1) / 2
    ry = abs(y2 - y1) / 2

    # --- correct geometric ellipse angle ---
    def ellipse_angle(px, py):
        return math.atan2(
            (py - cy) * rx,
            (px - cx) * ry
        )

    a1 = ellipse_angle(*p1)
    a2 = ellipse_angle(*p2)

    delta = a2 - a1

    # force clockwise
    if delta > 0:
        delta -= math.tau

    # --- sample arc ---
    points = []
    for i in range(steps + 1):
        t = i / steps
        a = a1 + delta * t
        x = cx + math.cos(a) * rx
        y = cy + math.sin(a) * ry
        points.append((x, y))

    pygame.draw.lines(surface, color, False, points, width)

class Render:
    BACKGROUND_COLOUR = (10, 10, 10)
    COMPONENT_COLOUR = (230, 230, 230)
    ACTIVE_COLOUR = (240, 30, 30)
    UNACTIVE_COLOUR = (100, 30, 30)
    NO_CONNECTION_COLOUR = (30, 30, 150)
    DEBUG_GREEN = (30, 250, 30)
    DEBUG_DARK_GREEN = (30, 100, 30)

    def __init__(self, schematic, simulator):
        self.screen = pygame.display.set_mode((1920, 1080))
        self.clock = pygame.time.Clock()

        self.schematics = [schematic]
        self.simulator = simulator

        self.static_components = []
        self.__pregenerate()

        self.pan_offset = [0, 0]
        self.zoom = 1.0
        self.MIN_ZOOM = 0.2
        self.MAX_ZOOM = 5.0

        self.mouse_dragging = False
        self.target_fps = 120

        self.font = pygame.sysfont.SysFont("Consolas", 16)

    def blit_scaled(self, surface, xy):
        # We no longer scale it here, but I cba to remove this function
        sx, sy = self.world_to_screen(*xy)

        self.screen.blit(surface, (sx, sy))

    def screen_to_world(self, x, y):
        return (
            (x - self.pan_offset[0]) / self.zoom,
            (y - self.pan_offset[1]) / self.zoom
        )

    def world_to_screen(self, x, y):  # Surely if I use the same function for everything it will work - WRONG
        return (
            (x * self.zoom) + self.pan_offset[0],
            (y * self.zoom) + self.pan_offset[1]
        )

    @property
    def schematic(self):
        return self.schematics[-1]

    def back_one_schematic(self):
        if len(self.schematics) > 1:
            self.schematics.pop(-1)
            self.__pregenerate()

    def add_one_schematic(self, schematic):
        self.schematics.append(schematic)
        self.__pregenerate()

    def __pregenerate(self):
        self.pan_offset = [0, 0]
        self.static_components = []
        self.zoom = 1

        self.display_loading_screen(0, None)
        components = self.schematic.components

        for i, component in enumerate(components):
            comp = self.generate_component(component)
            self.static_components.append(comp)

            self.display_loading_screen(i / len(components), comp)

    def __fast_generate(self):
        self.static_components = [
            self.generate_component(component, zoom=self.zoom)
            for component in self.schematic.components
        ]

    def get_rect(self, component):
        if component["type"] == "pin":
            return component["data"]["rect"]

        if component["type"] == "symbol":
            return component["data"][0][0]["data"]

        raise NotImplementedError(f"Unknown component type, cant get rect: {component['type']}")

    def generate_component(self, component, zoom=1.0):
        flags = []
        width = max(1, int(zoom))

        if component["type"] == "pin":
            rect = component["data"]["rect"]
            drawing_data = component["data"]["drawing"]

        elif component["type"] == "symbol":
            rect = component["data"][0][0]["data"]
            drawing_data = None

            for chunk in component["data"]:
                if type(chunk[0]) is str:
                    flags.append(chunk)

                elif chunk[0]["type"] == "drawing":
                    drawing_data = chunk[0]["data"]
                    continue

        else:
            raise NotImplementedError(f"Unknown component type: {component['type']}")

        size = ((rect[2] - rect[0]) * zoom, (rect[3] - rect[1]) * zoom)


        surface = pygame.Surface(size)
        surface.fill(self.BACKGROUND_COLOUR)

        for raw in drawing_data:
            if not raw:
                continue

            task = raw[0]

            if task["type"] == "line":
                pygame.draw.line(
                    surface,
                    self.COMPONENT_COLOUR,
                    (task["data"][0][0] * zoom, task["data"][0][1] * zoom),
                    (task["data"][1][0] * zoom, task["data"][1][1] * zoom),
                    width=width
                )

            elif task["type"] == "arc":
                p1 = task["data"][0][0]["data"]
                p2 = task["data"][0][1]["data"]
                rect_data = task["data"][0][2]["data"]

                p1 = (p1[0] * zoom, p1[1] * zoom)
                p2 = (p2[0] * zoom, p2[1] * zoom)
                rect_data = [x * zoom for x in rect_data]

                draw_arc(
                    surface,
                    self.COMPONENT_COLOUR,
                    p1,
                    p2,
                    rect_data,
                    width=width
                )

            elif task["type"] == "circle":
                x1, y1, x2, y2 = task["data"][0][0]["data"]

                pygame.draw.ellipse(
                    surface,
                    self.COMPONENT_COLOUR,
                    pygame.Rect(x1 * zoom, y1 * zoom, (x2 - x1) * zoom, (y2 - y1) * zoom),
                    width=width
                )

            elif task["type"] == "rectangle":
                x1, y1, x2, y2 = task["data"][0][0]["data"]

                pygame.draw.rect(
                    surface,
                    self.COMPONENT_COLOUR,
                    pygame.Rect(x1 * zoom, y1 * zoom, (x2 - x1) * zoom, (y2 - y1) * zoom),
                    width=width
                )

            else:
                print("[WARNING] Unknown render task:", task["type"])

        # See if we have some extra rendering to do
        if component["type"] == "symbol":
            for chunk in component["data"]:
                if type(chunk[0]) is dict:
                    if chunk[0]["type"] == "port":
                        data = chunk[0]["data"]  # This has a bunch of text that I cba to add rn

                        pygame.draw.line(
                            surface,
                            self.COMPONENT_COLOUR,
                            (data["line"][0][0] * zoom, data["line"][0][1] * zoom),
                            (data["line"][1][0] * zoom, data["line"][1][1] * zoom),
                            width=width
                        )

                        for text in data["text"]:
                            x, y, tw, th = text["rect"]

                            font = pygame.sysfont.SysFont(text["font"]["name"],
                                                          int(text["font"].get("size", DEFAULT_FONT_SIZE) * self.zoom))
                            text_surf = font.render(text["text"], True, self.COMPONENT_COLOUR)

                            surface.blit(text_surf, (x * zoom, y * zoom))


                    if chunk[0]["type"] == "text":
                        data = chunk[0]["data"]
                        x, y, tw, th = data["rect"]

                        font = pygame.sysfont.SysFont(data["font"]["name"], int(data["font"].get("size", DEFAULT_FONT_SIZE) * self.zoom))
                        text_surf = font.render(data["text"], True, self.COMPONENT_COLOUR)


                        surface.blit(text_surf, (x * zoom, y * zoom))

        if component["type"] == "pin":
            for data in component["data"]["text"]:
                font = pygame.sysfont.SysFont(data["font"]["name"],
                                              int(data["font"].get("size", DEFAULT_FONT_SIZE) * self.zoom))
                text_surf = font.render(data["text"], True, self.COMPONENT_COLOUR)

                x, y, tw, th = data["rect"]
                surface.blit(text_surf, (x * zoom, y * zoom))


        return surface


    def display_loading_screen(self, percent_completed: float, preview):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

        self.screen.fill((0, 0, 0))

        pygame.draw.rect(
            self.screen,
            (130, 130, 130),
            pygame.Rect(
                20, (self.screen.get_height() // 2) - 20, self.screen.get_width() - 40, 40
            )
        )

        pygame.draw.rect(
            self.screen,
            (10, 250, 10),
            pygame.Rect(
                21, (self.screen.get_height() // 2) - 19, (self.screen.get_width() - 38) * percent_completed, 38
            )
        )

        if preview:
            self.screen.blit(preview, ((self.screen.get_width() - preview.get_width()) // 2, (self.screen.get_height() // 2) + 25))

        pygame.display.flip()
        self.clock.tick(120)

    def update(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    self.back_one_schematic()

                if event.key == pygame.K_r:
                    self.simulator.full_rescan()

            if event.type == pygame.MOUSEMOTION:
                if event.buttons[0]:
                    self.pan_offset[0] += event.rel[0]
                    self.pan_offset[1] += event.rel[1]
                    self.mouse_dragging = True

            if event.type == pygame.MOUSEBUTTONUP:
                if self.mouse_dragging:
                    self.mouse_dragging = False
                    continue

                # Duh, gotta account for zoom here too. Silly me
                x = (event.pos[0] - self.pan_offset[0]) / self.zoom
                y = (event.pos[1] - self.pan_offset[1]) / self.zoom

                if event.button == 1 and not self.mouse_dragging:
                    for component in self.simulator.components:
                        rect = component.rect

                        if (rect[0] < x < rect[2]) and (rect[1] < y < rect[3]):
                            if component.component_name != "pin.generic":
                                if isinstance(component.internal_component, Simulator):
                                    self.add_one_schematic(component.internal_component.schematic)


                if event.button == 1:
                    for component in self.simulator.components:
                        rect = component.rect

                        if (rect[0] < x < rect[2]) and (rect[1] < y < rect[3]):
                            self.simulator.update_input_pin(component, 0)

            if event.type == pygame.MOUSEBUTTONDOWN:
                x = (event.pos[0] - self.pan_offset[0]) / self.zoom
                y = (event.pos[1] - self.pan_offset[1]) / self.zoom

                if event.button == 1:
                    for component in self.simulator.components:
                        rect = component.rect

                        if (rect[0] < x < rect[2]) and (rect[1] < y < rect[3]):
                            self.simulator.update_input_pin(component, 1)

            if event.type == pygame.MOUSEWHEEL:
                old_zoom = self.zoom

                if event.y > 0:
                    self.zoom *= 1.1
                else:
                    self.zoom *= 0.9

                self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom))
                self.zoom = round(self.zoom, 2)

                # Zoom toward mouse otherise it looks fucking shit
                mx, my = pygame.mouse.get_pos()
                self.pan_offset[0] = int(mx - (mx - self.pan_offset[0]) * (self.zoom / old_zoom))
                self.pan_offset[1] = int(my - (my - self.pan_offset[1]) * (self.zoom / old_zoom))

                self.__fast_generate()

        self.screen.fill(self.BACKGROUND_COLOUR)

        for i, component in enumerate(self.schematic.components):
            rect = self.get_rect(component)
            surface = self.static_components[i]

            x, y = rect[0:2]
            self.blit_scaled(surface, (x, y))

        for junction in self.schematic.junctions:
            x, y = junction["data"]
            pygame.draw.circle(
                self.screen,
                self.COMPONENT_COLOUR,
                self.world_to_screen(x, y),
                max(1, int(3 * self.zoom))
            )

        for wire in self.schematic.connections:
            x1, y1 = wire[0]["data"]
            x2, y2 = wire[1]["data"]



            vcc = self.simulator.get_wire_vcc((x1, y1))

            colour = self.UNACTIVE_COLOUR
            if vcc is None:
                colour = self.NO_CONNECTION_COLOUR

            elif vcc > 0.5:
                colour = self.ACTIVE_COLOUR

            pygame.draw.line(
                self.screen,
                colour,
                self.world_to_screen(x1, y1),
                self.world_to_screen(x2, y2),
                max(1, int(self.zoom))
            )


        # Render overlay
        fps = str(round(self.clock.get_fps()))

        debug_text = (
            f"Path: {os.path.basename(self.schematic.path)}",
            f"FPS: {fps}{' ' * (len(str(self.target_fps)) - len(fps))} Target: {self.target_fps}",
            f"Simulation: {self.simulator.status}"
        )
        y = 5
        for line in debug_text:
            surf = self.font.render(line, True, self.COMPONENT_COLOUR)
            self.screen.blit(surf, (5, y))
            y += surf.get_height() + 2

        pygame.display.flip()
        self.clock.tick(self.target_fps)
