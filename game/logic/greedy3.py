from typing import Optional, List
from game.logic.base import BaseLogic
from game.models import Board, GameObject, Position
from game.util import get_direction

class Greedy3(BaseLogic):
    # Target jangka panjang yang dipilih berdasarkan efisiensi diamond
    persistent_goals: List[Position] = []

    # Target sementara untuk menghindari rintangan seperti teleport/red diamond
    temporary_goal: Optional[Position] = None

    # Urutan gerakan jika tidak ada target (untuk mencegah diam di tempat)
    move_cycle = [(1, 0), (0, 1), (-1, 0), (0, -1)]

    # Target aktif saat ini (bisa persistent atau temporary)
    current_target: Optional[Position] = None

    # Pointer untuk menentukan arah rotasi saat tidak ada target
    direction_pointer = 0

    def next_move(self, bot: GameObject, board: Board):
        # Simpan referensi bot dan board untuk digunakan di metode lain
        self.bot = bot
        self.board = board
        self.diamonds = board.diamonds

        # Kumpulkan teleport dan red button di papan
        self.teleporters = [obj for obj in board.game_objects if obj.type == "TeleportGameObject"]
        self.red_buttons = [obj for obj in board.game_objects if obj.type == "DiamondButtonGameObject"]

        # Hapus goal yang sudah tercapai
        if bot.position in self.persistent_goals:
            self.persistent_goals.remove(bot.position)
        if self.temporary_goal == bot.position:
            self.temporary_goal = None

        props = bot.properties

        # Jika diamond sudah 5, langsung kembali ke base
        if props.diamonds == 5:
            self.current_target = props.base
            self.persistent_goals.clear()

        # Jika sedang menghindari rintangan, kejar temporary goal dulu
        elif self.temporary_goal:
            self.current_target = self.temporary_goal

        else:
            # Jika tidak punya goal jangka panjang, pilih diamond paling efisien
            if not self.persistent_goals:
                self.select_best_diamond_efficiency()

            # Pilih goal terdekat dari daftar persistent
            self.current_target = self.closest_persistent_goal()

        pos = bot.position

        if self.current_target:
            # Arah gerakan ke target
            dx, dy = get_direction(pos.x, pos.y, self.current_target.x, self.current_target.y)

            # Cek apakah ada rintangan di jalur, jika tidak sedang dalam temporary goal
            if not self.temporary_goal:
                self.check_path_for_obstacle(pos, self.current_target, 'teleporter')
            if not self.temporary_goal:
                self.check_path_for_obstacle(pos, self.current_target, 'redButton')
            if props.diamonds == 4 and not self.temporary_goal:
                self.check_path_for_obstacle(pos, self.current_target, 'redDiamond')
        else:
            # Jika tidak ada target sama sekali, berputar
            dx, dy = self.move_cycle[self.direction_pointer]
            self.direction_pointer = (self.direction_pointer + 1) % len(self.move_cycle)

        return dx, dy

    def closest_persistent_goal(self) -> Optional[Position]:
        # Cari goal jangka panjang terdekat dari posisi saat ini
        pos = self.bot.position
        closest = None
        shortest = float('inf')
        for goal in self.persistent_goals:
            dist = abs(pos.x - goal.x) + abs(pos.y - goal.y)
            if dist < shortest:
                shortest = dist
                closest = goal
        return closest

    def select_best_diamond_efficiency(self):
        # Pilih diamond berdasarkan efisiensi (poin / jarak)
        pos = self.bot.position
        candidates = []

        for diamond in self.diamonds:
            # Hindari red diamond jika bot sudah bawa 4 diamond (biar ga kebanyakan)
            if diamond.properties.points == 2 and self.bot.properties.diamonds == 4:
                continue

            # Hitung jarak Manhattan
            distance = abs(pos.x - diamond.position.x) + abs(pos.y - diamond.position.y)
            if distance == 0:
                continue  # skip posisi saat ini

            efficiency = diamond.properties.points / distance
            candidates.append((efficiency, diamond.position))

        # Urutkan berdasarkan efisiensi tertinggi
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Simpan semua posisi diamond dengan efisiensi terbaik
        if candidates:
            best_efficiency = candidates[0][0]
            self.persistent_goals = [pos for eff, pos in candidates if eff == best_efficiency]
        elif self.red_buttons:
            # Jika tidak ada diamond, kejar red button
            self.persistent_goals = [self.red_buttons[0].position]

    def check_path_for_obstacle(self, pos: Position, target: Position, obstacle_type: str):
        # Cek apakah ada rintangan (teleport/red diamond/red button) di jalur lurus
        if obstacle_type == 'teleporter':
            obstacles = self.teleporters
        elif obstacle_type == 'redDiamond':
            obstacles = [d for d in self.diamonds if d.properties.points == 2]
        elif obstacle_type == 'redButton':
            obstacles = self.red_buttons
        else:
            return

        for obstacle in obstacles:
            obs_pos = obstacle.position
            # Jika rintangan ada di jalur vertikal
            if obs_pos.x == target.x and self._between(obs_pos.y, pos.y, target.y):
                self._set_temporary_goal(pos, target, obstacle_type, obs_pos, vertical=True)
                return
            # Jika rintangan ada di jalur horizontal
            if obs_pos.y == target.y and self._between(obs_pos.x, pos.x, target.x):
                self._set_temporary_goal(pos, target, obstacle_type, obs_pos, vertical=False)
                return

    def _between(self, val, start, end):
        # Cek apakah val berada di antara start dan end (inklusif arah)
        return (start < val <= end) or (end <= val < start)

    def _set_temporary_goal(self, current: Position, destination: Position, obstacle_type: str, obstacle_pos: Position, vertical: bool):
        # Buat target sementara agar bisa menghindar dari obstacle
        if vertical:
            new_x = destination.x - 1 if destination.x > current.x else destination.x + 1
            new_x = max(0, min(new_x, self.board.width - 1))
            new_pos = Position(new_x, obstacle_pos.y)
        else:
            new_y = destination.y - 1 if destination.y > current.y else destination.y + 1
            new_y = max(0, min(new_y, self.board.height - 1))
            new_pos = Position(obstacle_pos.x, new_y)

        self.current_target = new_pos
        self.temporary_goal = new_pos
