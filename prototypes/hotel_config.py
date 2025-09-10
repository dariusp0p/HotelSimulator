import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QGraphicsView, QGraphicsScene, QLineEdit,
    QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem
)
from PyQt6.QtGui import QBrush, QColor, QPen, QPainter
from PyQt6.QtCore import Qt, QPointF

from src.db.database_manager import DatabaseManager
from src.service.hotel_service import HotelService
from collections import defaultdict, namedtuple



TILE_SIZE = 50
GRID_WIDTH = 10
GRID_HEIGHT = 10
Room = namedtuple("Room", ["id", "x", "y", "type", "status"])


class RoomItem(QGraphicsRectItem):
    def __init__(self, scene, graph, room_id, x, y):
        super().__init__(0, 0, TILE_SIZE, TILE_SIZE)
        self.scene = scene
        self.graph = graph
        self.room_id = room_id
        self.setBrush(QBrush(QColor(100, 200, 250)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(0)
        self.setPos(x * TILE_SIZE, y * TILE_SIZE)
        self.graph.add_room(room_id, x, y, "room", "free")

    def mouseReleaseEvent(self, event):
        new_pos = self.pos()
        snapped_x = round(new_pos.x() / TILE_SIZE)
        snapped_y = round(new_pos.y() / TILE_SIZE)
        self.setPos(QPointF(snapped_x * TILE_SIZE, snapped_y * TILE_SIZE))
        self.graph.move_room(self.room_id, snapped_x, snapped_y)
        self.scene.update_connections()
        super().mouseReleaseEvent(event)



class FloorPlanGraph:
    def __init__(self):
        self.nodes = {}
        self.adjacency = defaultdict(set)

    def add_room(self, room_id, x, y, type_, status):
        self.nodes[room_id] = Room(room_id, x, y, type_, status)

    def move_room(self, room_id, x, y):
        room = self.nodes[room_id]
        self.nodes[room_id] = room._replace(x=x, y=y)

    def clear_connections(self):
        self.adjacency = defaultdict(set)

    def connect_rooms(self, room1_id, room2_id):
        self.adjacency[room1_id].add(room2_id)
        self.adjacency[room2_id].add(room1_id)



class FloorPlanScene(QGraphicsScene):
    def __init__(self, graph):
        super().__init__(0, 0, GRID_WIDTH * TILE_SIZE, GRID_HEIGHT * TILE_SIZE)
        self.graph = graph
        self.room_items = {}
        self.connection_lines = []
        self.draw_grid()

    def draw_grid(self):
        pen = QPen(QColor(200, 200, 200))
        for x in range(GRID_WIDTH + 1):
            self.addLine(x * TILE_SIZE, 0, x * TILE_SIZE, GRID_HEIGHT * TILE_SIZE, pen)
        for y in range(GRID_HEIGHT + 1):
            self.addLine(0, y * TILE_SIZE, GRID_WIDTH * TILE_SIZE, y * TILE_SIZE, pen)

    def add_room(self, room_id, x, y):
        room = RoomItem(self, self.graph, room_id, x, y)
        self.addItem(room)
        self.room_items[room_id] = room
        self.update_connections()

    def update_connections(self):
        for line in self.connection_lines:
            self.removeItem(line)
        self.connection_lines.clear()
        self.graph.clear_connections()

        for id1, room1 in self.graph.nodes.items():
            for id2, room2 in self.graph.nodes.items():
                if id1 == id2:
                    continue
                dx = abs(room1.x - room2.x)
                dy = abs(room1.y - room2.y)
                if (dx == 1 and dy == 0) or (dx == 0 and dy == 1):
                    self.graph.connect_rooms(id1, id2)

        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(3)
        for room_id, neighbors in self.graph.adjacency.items():
            for neighbor_id in neighbors:
                if room_id > neighbor_id:
                    continue
                p1 = self.room_center(self.room_items[room_id])
                p2 = self.room_center(self.room_items[neighbor_id])
                line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
                line.setPen(pen)
                line.setZValue(1)
                self.addItem(line)
                self.connection_lines.append(line)

    def room_center(self, item):
        rect = item.rect()
        pos = item.pos()
        return QPointF(pos.x() + rect.width() / 2, pos.y() + rect.height() / 2)



class MainWindow(QWidget):
    def __init__(self, service: HotelService):
        super().__init__()
        self.setWindowTitle("Hotel Floor Editor")
        self.service = service
        self.graph = FloorPlanGraph()
        self.scene = FloorPlanScene(self.graph)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.init_ui()
        self.load_floors()

        if self.floor_list.count() > 0:
            self.floor_list.setCurrentRow(0)
            self.update_floor_plan(self.floor_list.currentItem().text())


    def init_ui(self):
        main_layout = QHBoxLayout()
        side_bar = QVBoxLayout()

        # Floor list and label
        side_bar.addWidget(QLabel("Floors:"))
        self.floor_list = QListWidget()
        self.floor_list.currentItemChanged.connect(self.on_floor_selected)
        side_bar.addWidget(self.floor_list)

        # Floor input controls
        floor_input_layout = QHBoxLayout()
        self.floor_name_input = QLineEdit()
        self.floor_name_input.setPlaceholderText("Floor name")
        add_floor_btn = QPushButton("Add Floor")
        add_floor_btn.clicked.connect(self.add_floor)

        floor_input_layout.addWidget(self.floor_name_input)
        floor_input_layout.addWidget(add_floor_btn)
        side_bar.addLayout(floor_input_layout)

        # Room type hotbar
        hotbar = QHBoxLayout()
        for label in ["Room", "Staircase", "Hallway"]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, l=label.lower(): self.add_element(l))
            hotbar.addWidget(btn)

        central_layout = QVBoxLayout()
        central_layout.addWidget(self.view)
        central_layout.addLayout(hotbar)

        main_layout.addLayout(side_bar)
        main_layout.addLayout(central_layout)

        self.setLayout(main_layout)
        self.setFixedSize(800, 600)

    def load_floors(self):
        self.floor_list.clear()
        for floor_name in self.service.get_floors():
            self.floor_list.addItem(floor_name)

    def on_floor_selected(self, current, previous):
        if current:
            floor_name = current.text()
            self.update_floor_plan(floor_name)

    def update_floor_plan(self, floor_name):
        # Clear current floor plan
        self.scene.clear()
        self.graph = FloorPlanGraph()
        self.scene.graph = self.graph
        self.scene.room_items = {}
        self.scene.connection_lines = []
        self.scene.draw_grid()

        # Get floor grid from service
        try:
            grid = self.service.get_floor_grid(floor_name)
            for pos, element in grid.items():
                x, y = pos
                element_id = element.element_id
                element_type = element.element_type

                # Add element to the scene
                room = RoomItem(self.scene, self.graph, element_id, x, y)

                # Set different colors based on element type
                if element_type == "staircase":
                    room.setBrush(QBrush(QColor(255, 165, 0)))  # Orange
                elif element_type == "hallway":
                    room.setBrush(QBrush(QColor(200, 200, 200)))  # Gray
                else:  # room
                    room.setBrush(QBrush(QColor(100, 200, 250)))  # Blue

                self.scene.addItem(room)
                self.scene.room_items[element_id] = room

            self.scene.update_connections()
        except Exception as e:
            print(f"Error loading floor plan: {e}")

    def add_element(self, element_type):
        if self.floor_list.currentItem():
            floor_name = self.floor_list.currentItem().text()
            floor_id = self.service.get_floor_id(floor_name)

            # Get a reasonable position (could be improved)
            x, y = 1, 1

            element_data = {
                "element_type": element_type,
                "floor_id": floor_id,
                "capacity": 0 if element_type != "room" else 2,
                "position": (x, y)
            }

            try:
                self.service.add_element(element_data)
                self.update_floor_plan(floor_name)
            except Exception as e:
                print(f"Error adding element: {e}")

    def add_floor(self):
        floor_name = self.floor_name_input.text().strip()
        if not floor_name:
            floor_name = f"Floor {self.floor_list.count() + 1}"

        try:
            self.service.add_floor(floor_name)
            self.floor_list.addItem(floor_name)
            self.floor_name_input.clear()
            print(f"Floor {floor_name} added")
        except Exception as e:
            print(f"Error adding floor: {e}")





def main():
    app = QApplication(sys.argv)
    from src.repository.hotel_repository import HotelRepository

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "../..", "data", "db")

    db_manager = DatabaseManager(
        reservations_db=os.path.join(data_dir, "reservations.db"),
        hotel_db=os.path.join(data_dir, "hotel.db"),
    )

    db_manager.initialize_databases()

    hotel_connection = db_manager.hotel_conn

    hotel_repository = HotelRepository(hotel_connection)
    hotel_service = HotelService(hotel_repository)


    window = MainWindow(hotel_service)

    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
