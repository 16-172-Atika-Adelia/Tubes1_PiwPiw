from typing import Optional
import random
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position
from ..util import get_direction

# Fungsi untuk menghitung jarak dalam grid tanpa diagonal
def get_manhattan_distance(pos1: Position, pos2: Position):
    return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

# Fungsi untuk menghitung jarak ke suatu posisi melalui teleporter
def distance_via_teleporter(teleport_distance: int, destination: Position, exit_teleporter: Position):
    return teleport_distance + get_manhattan_distance(destination, exit_teleporter)

# Fungsi untuk bergerak ke arah base, mempertimbangkan apakah lebih cepat langsung atau via teleporter
def move_towards_base(direct_distance: int, teleport_distance: int, base: Position, entry_tele: Position, current: Position):
    # Jika jarak langsung ke base lebih dekat, pergi langsung
    if direct_distance <= teleport_distance:
        dx, dy = get_direction(current.x, current.y, base.x, base.y)
    else:
        # Kalau via teleport lebih cepat, pergi ke teleport dulu
        dx, dy = get_direction(current.x, current.y, entry_tele.x, entry_tele.y)

    # Jika tidak bisa memilih arah (dx == dy), acak atas/bawah agar tetap bergerak
    if dx == dy:
        dx = 0
        dy = (-1) ** random.randint(0, 1)

    return dx, dy

# Fungsi utama logika greedy untuk mencari diamond
def greedy_diamond_logic(diamonds, teleporters, red_button, base, current, props, nearest_tele_dist):
    closest_distance = float('inf')  # Jarak terdekat awalnya tak hingga
    target = base                    # Target awal default ke base
    diamond_count = 0                # Hitung total diamond di peta

    for d in diamonds:
        diamond_count += 1
        # Jika diamond merah dan diamond kita sudah >= 4, abaikan
        if not (d.properties.points == 2 and props.diamonds >= 4):
            direct_dist = get_manhattan_distance(current, d.position) #menghitung jarak langsung ke diamond
            teleport_dist = distance_via_teleporter(nearest_tele_dist, d.position, teleporters[1].position) # Hitung jarak via teleport ke diamond

            # Pilih target terdekat (langsung atau teleport)
            if direct_dist < closest_distance:
                closest_distance = direct_dist
                target = d.position
            elif teleport_dist < closest_distance:
                closest_distance = teleport_dist
                target = teleporters[0].position

    # Pertimbangkan tombol merah jika lebih dekat dari diamond
    red_btn_pos = red_button.position
    red_direct = get_manhattan_distance(current, red_btn_pos)
    red_teleport = distance_via_teleporter(nearest_tele_dist, red_btn_pos, teleporters[1].position)

    # Gunakan teleport jika lebih dekat ke tombol merah
    if red_teleport <= red_direct:
        red_btn_pos = teleporters[1].position
        red_direct = red_teleport

    # Jika jumlah diamond sedikit dan tombol merah lebih dekat, ke tombol merah
    if diamond_count <= 6 and red_direct <= closest_distance:
        target = red_btn_pos

    # Hitung arah gerakan menuju target
    dx, dy = get_direction(current.x, current.y, target.x, target.y)

    # Jika ambigu (dx == dy), acak atas/bawah agar tetap bergerak
    if dx == dy:
        dx = 0
        dy = (-1) ** random.randint(0, 1)

    return dx, dy

# Kelas utama yang menjalankan strategi Greedy
class Greedy1(BaseLogic):
    def init(self):
        self.goal_position: Optional[Position] = None

    def next_move(self, board_bot: GameObject, board: Board):
        props = board_bot.properties
        current = board_bot.position
        base = props.base

        # Inisialisasi objek-objek di sekitar
        diamonds = [] 
        bots = []
        teleporters = []
        red_button = None

        for obj in board.game_objects:
            if obj.type == "DiamondGameObject":
                diamonds.append(obj)
            elif obj.type == "BotGameObject":
                bots.append(obj)
            elif obj.type == "TeleportGameObject":
                teleporters.append(obj)
            elif obj.type == "DiamondButtonGameObject":
                red_button = obj

        # Hitung jarak ke kedua teleport, tukar posisi jika perlu supaya teleporters[0] adalah yang terdekat
        teleport_distances = [get_manhattan_distance(tp.position, current) for tp in teleporters]
        if teleport_distances[0] > teleport_distances[1]:
            nearest_tele_dist = teleport_distances[1]
            teleporters[0], teleporters[1] = teleporters[1], teleporters[0]
        else:
            nearest_tele_dist = teleport_distances[0]

        # Hitung jarak langsung dan via teleport ke base
        base_dist = get_manhattan_distance(current, base)
        base_tele_dist = distance_via_teleporter(nearest_tele_dist, base, teleporters[1].position)

        # Jika membawa diamond dan waktu hampir habis, segera pulang
        if props.diamonds > 0 and props.milliseconds_left < 10000:
            return move_towards_base(base_dist, base_tele_dist, base, teleporters[0].position, current)

        # Jika ada bot musuh dekat dan dia bawa banyak diamond, kejar!
        for bot in bots:
            if bot.properties.name != props.name:
                bot_dist = get_manhattan_distance(current, bot.position)
                if bot_dist == 1 or (bot_dist < 3 and bot.properties.diamonds > 2):
                    return get_direction(current.x, current.y, bot.position.x, bot.position.y)

        # Jika sudah bawa 5 diamond atau sudah bawa >2 dan dekat base, segera pulang
        if props.diamonds == 5 or (props.diamonds > 2 and base_dist < 2):
            return move_towards_base(base_dist, base_tele_dist, base, teleporters[0].position, current)

        # Jika tidak ada kondisi khusus, gunakan logika greedy untuk cari diamond terdekat
        return greedy_diamond_logic(diamonds, teleporters, red_button, base, current, props, nearest_tele_dist)
