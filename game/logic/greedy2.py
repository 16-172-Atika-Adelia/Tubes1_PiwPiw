from typing import Optional
from game.logic.base import BaseLogic
from game.models import Board, GameObject, Position
from game.util import get_direction

# Bot strategi berbasis greedy dengan tambahan logika untuk teleportasi dan red diamond
class Greedy2(BaseLogic):
    # Variabel statis untuk menyimpan tujuan dan status global antar langkah
    static_goals: list[Position] = []
    static_goal_teleport: GameObject = None
    static_temp_goals: Position = None
    static_direct_to_base_via_teleporter: bool = False

    # Konstruktor (seharusnya "__init__" bukan "_init_")
    def _init_(self) -> None:
        self.directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # Arah gerakan
        self.goal_position: Optional[Position] = None
        self.current_direction = 0
        self.distance = 0

    def next_move(self, board_bot: GameObject, board: Board):
        # Ambil informasi dari bot dan board
        props = board_bot.properties
        self.board = board
        self.board_bot = board_bot
        self.diamonds = board.diamonds
        self.bots = board.bots
        self.teleporter = [d for d in board.game_objects if d.type == "TeleportGameObject"]
        self.redButton = [d for d in board.game_objects if d.type == "DiamondButtonGameObject"]
        self.enemy = [d for d in self.bots if d.id != board_bot.id]
        self.enemyDiamond = [d.properties.diamonds for d in self.enemy]

        # Reset tujuan saat bot berada di base
        if board_bot.position == props.base:
            self.static_goals = []
            self.static_goal_teleport = None
            self.static_temp_goals = None
            self.static_direct_to_base_via_teleporter = False

        # Jika sudah mencapai tujuan teleport, hapus dari list
        if self.static_goal_teleport and board_bot.position == self.find_other_teleport(self.static_goal_teleport):
            self.static_goals.remove(self.static_goal_teleport.position)
            self.static_goal_teleport = None
        if not self.static_goal_teleport and board_bot.position in self.static_goals:
            self.static_goals.remove(board_bot.position)

        # Jika mencapai goal sementara, hapus
        if board_bot.position == self.static_temp_goals:
            self.static_temp_goals = None

        # Jika bawa 5 diamond atau waktu hampir habis, segera ke base
        if props.diamonds == 5 or (props.milliseconds_left < 5000 and props.diamonds > 1):
            self.goal_position = self.find_best_way_to_base()
            if not self.static_direct_to_base_via_teleporter:
                self.static_goals = []
                self.static_goal_teleport = None
        else:
            # Jika belum ada goal, cari diamond terdekat
            if len(self.static_goals) == 0:
                self.find_nearest_diamond()
            self.goal_position = self.static_goals[0]

        # Jika sudah dekat base dan bawa lebih dari 2 diamond, kembali
        if self.calculate_near_base() and props.diamonds > 2:
            self.goal_position = self.find_best_way_to_base()
            if not self.static_direct_to_base_via_teleporter:
                self.static_goals = []
                self.static_goal_teleport = None

        # Jika ada goal sementara, gunakan itu
        if self.static_temp_goals:
            self.goal_position = self.static_temp_goals

        current_position = board_bot.position
        if self.goal_position:
            # Cek apakah ada teleporter/red diamond menghalangi di jalur
            if not self.static_temp_goals:
                self.obstacle_on_path('teleporter', current_position.x, current_position.y, self.goal_position.x, self.goal_position.y)
            if props.diamonds == 4:
                self.obstacle_on_path('redDiamond', current_position.x, current_position.y, self.goal_position.x, self.goal_position.y)

            # Hitung arah ke tujuan
            delta_x, delta_y = get_direction(current_position.x, current_position.y, self.goal_position.x, self.goal_position.y)
        else:
            # Jika tidak ada tujuan, gerak berputar
            delta = self.directions[self.current_direction]
            delta_x, delta_y = delta
            self.current_direction = (self.current_direction + 1) % len(self.directions)

        # Jika sudah di tujuan, reset
        if delta_x == 0 and delta_y == 0:
            self.static_goals = []
            self.static_direct_to_base_via_teleporter = False
            self.static_goal_teleport = None
            self.static_temp_goals = None
            self.goal_position = None
            tempMove = self.next_move(board_bot, board)
            delta_x, delta_y = tempMove[0], tempMove[1]

        return delta_x, delta_y
    
    # Cari rute terbaik ke base: langsung atau lewat teleport
    def find_best_way_to_base(self):
        current_position = self.board_bot.position
        base = self.board_bot.properties.base
        base_position = Position(base.y, base.x)
        base_distance_direct = abs(base.x - current_position.x) + abs(base.y - current_position.y)

        nearest_teleport_position, far_teleport_position, nearest_tp = self.find_nearest_teleport()

        if nearest_teleport_position is None:
            return base_position

        base_distance_teleporter = abs(base.x - far_teleport_position.x) + abs(base.y - far_teleport_position.y) + abs(nearest_teleport_position.x - current_position.x) + abs(nearest_teleport_position.y - current_position.y)

        if base_distance_direct < base_distance_teleporter:
            return base_position
        else:
            self.static_direct_to_base_via_teleporter = True
            self.static_goal_teleport = nearest_tp
            self.static_goals = [nearest_teleport_position, base]
            return nearest_teleport_position

    # Apakah base cukup dekat untuk langsung kembali
    def calculate_near_base(self):
        current_position = self.board_bot.position
        base = self.board_bot.properties.base
        base_distance = abs(base.x - current_position.x) + abs(base.y - current_position.y)
        base_distance_teleporter = self.find_base_distance_teleporter()
        distance = min(base_distance, base_distance_teleporter)

        if distance == 0:
            return False
        return distance < self.distance

    def find_base_distance_teleporter(self):
        current_position = self.board_bot.position
        nearest_teleport_position, far_teleport_position, _ = self.find_nearest_teleport()
        if nearest_teleport_position is None:
            return float("inf")
        base = self.board_bot.properties.base
        return abs(base.x - far_teleport_position.x) + abs(base.y - far_teleport_position.y) + abs(nearest_teleport_position.x - current_position.x) + abs(nearest_teleport_position.y - current_position.y)

    # Cari diamond terdekat dari berbagai metode
    def find_nearest_diamond(self):
        direct = self.find_nearest_diamond_direct()
        teleport = self.find_nearest_diamond_teleport()
        redButton = self.find_nearest_red_button()
        if direct[0] < teleport[0] and direct[0] < redButton[0]:
            self.static_goals = [direct[1]]
            self.distance = direct[0]
        elif teleport[0] < redButton[0]:
            self.static_goals = teleport[1]
            self.static_goal_teleport = teleport[2]
            self.distance = teleport[0]
        else:
            self.static_goals = [redButton[1]]
            self.distance = redButton[0]

    def find_nearest_red_button(self):
        current_position = self.board_bot.position
        red_button_pos = self.redButton[0].position
        distance = abs(red_button_pos.x - current_position.x) + abs(red_button_pos.y - current_position.y)
        return distance, red_button_pos

    # Temukan teleport terdekat dan pasangannya
    def find_nearest_teleport(self):
        nearest, far, nearest_tp = None, None, None
        min_dist = float("inf")
        for tp in self.teleporter:
            dist = abs(tp.position.x - self.board_bot.position.x) + abs(tp.position.y - self.board_bot.position.y)
            if dist == 0:
                continue
            if dist < min_dist:
                min_dist = dist
                nearest, far = tp.position, self.find_other_teleport(tp)
                nearest_tp = tp
        return nearest, far, nearest_tp

    def find_other_teleport(self, teleport: GameObject):
        for t in self.teleporter:
            if t.id != teleport.id:
                return t.position

    # Cari diamond terdekat melalui teleport
    def find_nearest_diamond_teleport(self):
        current_position = self.board_bot.position
        nearest_tp, far_tp, tp = self.find_nearest_teleport()
        if not nearest_tp:
            return float("inf")
        min_dist = float("inf")
        nearest_diamond = None
        for diamond in self.diamonds:
            dist = abs(diamond.position.x - far_tp.x) + abs(diamond.position.y - far_tp.y) + abs(nearest_tp.x - current_position.x) + abs(nearest_tp.y - current_position.y)
            dist /= diamond.properties.points
            if dist < min_dist and ((diamond.properties.points == 2 and self.board_bot.properties.diamonds != 4) or (diamond.properties.points == 1)):
                min_dist = dist
                nearest_diamond = [nearest_tp, diamond.position]
        return min_dist, nearest_diamond, tp

    # Cari diamond terdekat secara langsung
    def find_nearest_diamond_direct(self):
        current_position = self.board_bot.position
        min_dist = float("inf")
        nearest = None
        for diamond in self.diamonds:
            dist = abs(diamond.position.x - current_position.x) + abs(diamond.position.y - current_position.y)
            dist /= diamond.properties.points
            if dist < min_dist and ((diamond.properties.points == 2 and self.board_bot.properties.diamonds != 4) or (diamond.properties.points == 1)):
                min_dist = dist
                nearest = diamond.position
        return min_dist, nearest

    # Cek apakah ada objek penghalang di jalur, dan set tujuan sementara jika ada
    def obstacle_on_path(self, type, current_x, current_y, dest_x, dest_y):
        if type == 'teleporter':
            object = self.teleporter
        elif type == 'redDiamond':
            object = [d for d in self.diamonds if d.properties.points == 2]
        elif type == 'redButton':
            object = self.redButton

        for t in object:
            if current_x == t.position.x and current_y == t.position.y:
                continue
            # Deteksi berbagai kondisi halangan dan atur goal sementara ke posisi alternatif
            if t.position.x == dest_x and (dest_y < t.position.y <= current_y or current_y <= t.position.y < dest_y):
                if dest_x != current_x:
                    self.goal_position = Position(dest_y, dest_x - 1) if dest_x > current_x else Position(dest_y, dest_x + 1)
                else:
                    self.goal_position = Position(dest_y, dest_x + 1 if dest_x <= 1 else dest_x - 1)
                self.static_temp_goals = self.goal_position
            elif t.position.y == dest_y and (dest_x < t.position.x <= current_x or current_x <= t.position.x < dest_x):
                if dest_y != current_y:
                    self.goal_position = Position(dest_y - 1 if dest_y > current_y else dest_y + 1, dest_x)
                else:
                    self.goal_position = Position(dest_y + 1 if dest_y <= 1 else dest_y - 1, dest_x)
                self.static_temp_goals = self.goal_position
            elif t.position.y == current_y and (dest_x < t.position.x <= current_x or current_x <= t.position.x < dest_x):
                if dest_y != current_y:
                    self.goal_position = Position(dest_y, current_x)
                else:
                    self.goal_position = Position(current_y + 1 if current_y <= 1 else current_y - 1, current_x)
                self.static_temp_goals = self.goal_position
