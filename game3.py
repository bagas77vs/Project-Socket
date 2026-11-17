import pygame
import sys
import random

# ── Config ──────────────────────────────────────────────
WIDTH, HEIGHT = 480, 640
FPS = 60

BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
GREEN  = (0,   255, 70)
RED    = (220, 30,  30)
YELLOW = (255, 230, 0)
CYAN   = (0,   220, 255)
GRAY   = (60,  60,  60)

PLAYER_SPEED  = 5
BULLET_SPEED  = 7
ALIEN_ROWS    = 4
ALIEN_COLS    = 10
ALIEN_SPEED   = 1
ALIEN_DROP    = 20
SHOOT_COOLDOWN = 25   # frames

pygame.init()
font_big  = pygame.font.SysFont("Consolas", 36, bold=True)
font_mid  = pygame.font.SysFont("Consolas", 24)
font_small= pygame.font.SysFont("Consolas", 18)


# ── Helper: draw button ──────────────────────────────────
def draw_button(screen, text, rect, color, text_color=WHITE):
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, WHITE, rect, 2, border_radius=8)
    t = font_mid.render(text, True, text_color)
    screen.blit(t, (rect[0] + (rect[2]-t.get_width())//2,
                    rect[1] + (rect[3]-t.get_height())//2))

def is_clicked(mouse_pos, rect):
    return pygame.Rect(rect).collidepoint(mouse_pos)


# ── Alien ────────────────────────────────────────────────
class Alien:
    SIZE = 32
    def __init__(self, x, y, row):
        self.x, self.y = x, y
        self.row = row          # row 0 = top (harder color)
        self.alive = True

    def draw(self, screen):
        if not self.alive:
            return
        # Simple pixel-art alien shape drawn with rects
        color = [CYAN, GREEN, GREEN, YELLOW][self.row % 4]
        x, y, s = int(self.x), int(self.y), self.SIZE
        # body
        pygame.draw.rect(screen, color, (x+6, y+4, s-12, s-8), border_radius=4)
        # eyes
        pygame.draw.rect(screen, BLACK, (x+9,  y+9, 5, 5))
        pygame.draw.rect(screen, BLACK, (x+18, y+9, 5, 5))
        # legs
        pygame.draw.rect(screen, color, (x+4,  y+22, 5, 7))
        pygame.draw.rect(screen, color, (x+23, y+22, 5, 7))
        # antennae
        pygame.draw.line(screen, color, (x+10, y+4), (x+6,  y), 2)
        pygame.draw.line(screen, color, (x+22, y+4), (x+26, y), 2)

    def rect(self):
        return pygame.Rect(self.x+4, self.y+4, self.SIZE-8, self.SIZE-8)


# ── Player ───────────────────────────────────────────────
class Player:
    W, H = 44, 20
    def __init__(self):
        self.x = WIDTH // 2 - self.W // 2
        self.y = HEIGHT - 60
        self.cooldown = 0

    def move(self, keys):
        if keys[pygame.K_LEFT]  and self.x > 0:
            self.x -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] and self.x < WIDTH - self.W:
            self.x += PLAYER_SPEED

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        # ship hull
        pygame.draw.rect(screen, GREEN, (x, y+8, self.W, self.H-8), border_radius=4)
        # cockpit
        pygame.draw.rect(screen, CYAN, (x+16, y, 12, 12), border_radius=6)

    def shoot(self):
        if self.cooldown == 0:
            self.cooldown = SHOOT_COOLDOWN
            return Bullet(self.x + self.W//2 - 2, self.y, -BULLET_SPEED)
        return None

    def rect(self):
        return pygame.Rect(self.x, self.y+8, self.W, self.H)

    def tick(self):
        if self.cooldown > 0:
            self.cooldown -= 1


# ── Bullet ───────────────────────────────────────────────
class Bullet:
    def __init__(self, x, y, vy, color=WHITE):
        self.x, self.y = x, y
        self.vy = vy
        self.color = color

    def update(self):
        self.y += self.vy

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (int(self.x), int(self.y), 4, 12), border_radius=2)

    def rect(self):
        return pygame.Rect(self.x, self.y, 4, 12)

    def off_screen(self):
        return self.y < -20 or self.y > HEIGHT + 20


# ── Alien bullet ─────────────────────────────────────────
class AlienBullet(Bullet):
    def __init__(self, x, y):
        super().__init__(x, y, BULLET_SPEED - 1, RED)


# ── Shield block ─────────────────────────────────────────
class Shield:
    BLOCK = 8
    def __init__(self, cx, y):
        self.blocks = set()
        for r in range(4):
            for c in range(6):
                if not (r == 0 and c in (0, 5)):   # notch top-corners
                    self.blocks.add((cx - 3*self.BLOCK + c*self.BLOCK,
                                     y + r*self.BLOCK))

    def draw(self, screen):
        for (x, y) in self.blocks:
            pygame.draw.rect(screen, (0, 180, 0), (x, y, self.BLOCK, self.BLOCK))

    def hit(self, rect):
        for (x, y) in list(self.blocks):
            if rect.colliderect(pygame.Rect(x, y, self.BLOCK, self.BLOCK)):
                self.blocks.discard((x, y))
                return True
        return False


# ── Game ─────────────────────────────────────────────────
def build_aliens():
    aliens = []
    ox = (WIDTH - ALIEN_COLS * 44) // 2
    for r in range(ALIEN_ROWS):
        for c in range(ALIEN_COLS):
            aliens.append(Alien(ox + c*44, 60 + r*44, r))
    return aliens

def build_shields():
    positions = [WIDTH//5, 2*WIDTH//5, 3*WIDTH//5, 4*WIDTH//5]
    return [Shield(p, HEIGHT - 130) for p in positions]

def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Space Invaders")
    clock = pygame.time.Clock()

    while True:
        result = run_game(screen, clock)
        if not result:          # player closed window
            pygame.quit()
            sys.exit()
        # result == True → retry

def run_game(screen, clock):
    player   = Player()
    aliens   = build_aliens()
    shields  = build_shields()
    bullets  = []       # player bullets
    a_bullets= []       # alien bullets
    score    = 0
    lives    = 3
    alien_dx = ALIEN_SPEED
    alien_shoot_timer = 0
    alien_shoot_interval = 90  # frames between alien shots

    running = True
    while running:
        clock.tick(FPS)
        keys = pygame.key.get_pressed()

        # ── Events ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    b = player.shoot()
                    if b:
                        bullets.append(b)

        # ── Player ──
        player.move(keys)
        player.tick()

        # ── Bullets ──
        for b in bullets:
            b.update()
        bullets = [b for b in bullets if not b.off_screen()]

        for b in a_bullets:
            b.update()
        a_bullets = [b for b in a_bullets if not b.off_screen()]

        # ── Alien movement ──
        alive = [a for a in aliens if a.alive]
        if not alive:
            # All killed → win / next wave (just restart here)
            return show_result(screen, clock, score, lives, win=True)

        edge = False
        for a in alive:
            a.x += alien_dx
            if a.x <= 0 or a.x + Alien.SIZE >= WIDTH:
                edge = True

        if edge:
            alien_dx *= -1
            for a in alive:
                a.y += ALIEN_DROP
                a.x += alien_dx  # nudge back inside

        # ── Alien shooting ──
        alien_shoot_timer += 1
        if alien_shoot_timer >= alien_shoot_interval:
            alien_shoot_timer = 0
            shooter = random.choice(alive)
            a_bullets.append(AlienBullet(shooter.x + Alien.SIZE//2 - 2, shooter.y + Alien.SIZE))
            # speed up slightly as fewer aliens remain
            alien_shoot_interval = max(30, 90 - (ALIEN_ROWS*ALIEN_COLS - len(alive)) * 2)

        # ── Collision: player bullet → alien ──
        for b in bullets[:]:
            for a in alive:
                if b.rect().colliderect(a.rect()):
                    a.alive = False
                    bullets.remove(b)
                    score += (ALIEN_ROWS - a.row) * 10
                    break

        # ── Collision: player bullet → shield ──
        for b in bullets[:]:
            for s in shields:
                if s.hit(b.rect()):
                    if b in bullets:
                        bullets.remove(b)
                    break

        # ── Collision: alien bullet → shield ──
        for b in a_bullets[:]:
            for s in shields:
                if s.hit(b.rect()):
                    if b in a_bullets:
                        a_bullets.remove(b)
                    break

        # ── Collision: alien bullet → player ──
        for b in a_bullets[:]:
            if b.rect().colliderect(player.rect()):
                a_bullets.remove(b)
                lives -= 1
                if lives <= 0:
                    return show_result(screen, clock, score, lives, win=False)

        # ── Aliens reach bottom ──
        for a in alive:
            if a.y + Alien.SIZE >= player.y:
                return show_result(screen, clock, score, 0, win=False)

        # ── Draw ──
        screen.fill(BLACK)

        # stars background
        random.seed(42)
        for _ in range(60):
            sx, sy = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            screen.set_at((sx, sy), GRAY)
        random.seed()

        for s in shields:
            s.draw(screen)
        for a in aliens:
            a.draw(screen)
        for b in bullets:
            b.draw(screen)
        for b in a_bullets:
            b.draw(screen)
        player.draw(screen)

        # HUD
        score_t = font_mid.render(f"SCORE: {score}", True, WHITE)
        lives_t = font_mid.render(f"LIVES: {'♥ ' * lives}", True, RED)
        screen.blit(score_t, (10, 10))
        screen.blit(lives_t, (WIDTH - lives_t.get_width() - 10, 10))

        ctrl_t = font_small.render("← → MOVE   SPACE SHOOT", True, GRAY)
        screen.blit(ctrl_t, (WIDTH//2 - ctrl_t.get_width()//2, HEIGHT - 22))

        pygame.display.flip()

    return False


def show_result(screen, clock, score, lives, win):
    btn_retry = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 40,  200, 48)
    btn_quit  = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 100, 200, 48)

    while True:
        screen.fill(BLACK)

        title = "YOU WIN! 🎉" if win else "GAME OVER"
        t_col = GREEN if win else RED
        t = font_big.render(title, True, t_col)
        screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//3))

        s = font_mid.render(f"Score: {score}", True, WHITE)
        screen.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//3 + 55))

        draw_button(screen, "RETRY", btn_retry, (0, 130, 0))
        draw_button(screen, "QUIT",  btn_quit,  (160, 0, 0))

        pygame.display.flip()
        clock.tick(30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if is_clicked(event.pos, btn_retry):
                    return True
                if is_clicked(event.pos, btn_quit):
                    return False


if __name__ == "__main__":
    main()
