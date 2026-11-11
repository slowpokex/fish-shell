/* Аквариум для Game Boy Color: рыбы с никами, реплики, корм и тычки,
 * пасхалка SELECT×5 — шквал хуёв с вайб-казаками. Порт aquarium.py.
 *
 * Мир: координаты рыб, корма и хуёв — в 1/16 пикселя (FX), рисуем спрайтами
 * 8×16 из VRAM-банка 1. Большой хуй — тайлы фона в полосе BAND, которую
 * прерывание LYC прокручивает отдельно от остального экрана.
 */
#include <gb/gb.h>
#include <gb/cgb.h>
#include <gb/hardware.h>
#include <stdint.h>
#include "gen_gfx.h"
#include "gen_text.h"

#define FX 16
#define MAX_FISH 8
#define FISH_TOP 10
#define FISH_BOTTOM 94          /* верх рыбы, px */
#define FLOOR_Y 104             /* корм ложится на дно */
#define FOOD_RADIUS 48
#define FLEE_SPEED 24
#define MIN_RETURN 10
#define MAX_FOOD 3
#define MAX_BUBBLES 4
#define MAX_SHOTS 6
#define MAX_SPLATS 4
#define MAX_MON 7
#define BAND_ROW 5
#define BAND_Y (BAND_ROW * 8)
#define BAND_COL 20             /* большой хуй живёт в столбцах 20..31 карты */
#define WIN_Y 112
#define DLG_TIME 180
#define DLG_MIN 50
#define EGG_PRESSES 5
#define EGG_GAP 90              /* кадров между нажатиями B */
#define SCARE_RADIUS 40

#define PAL_TEXT 0
#define PAL_BOX 1
#define PAL_LABEL 2
#define PAL_WEED 3
#define PAL_SAND 4
#define PAL_DICK 5
#define PAL_SURFACE 6
#define PAL_BANNER 7
#define OPAL_DICK 6
#define OPAL_UI 7
#define OPAL_FOOD 2

enum { MOOD_SWIM, MOOD_FLEE, MOOD_RETURN };
enum { MODE_PICKER, MODE_TANK };
enum { BIG, MEDIUM, SMALL };

typedef struct {
    int16_t x, y;
    int8_t dx;
    uint8_t speed, species, pal, nick, mood;
} Fish;

typedef struct {
    int16_t x;
    uint8_t y, kind, speed, phase, active, cooldown;
    int8_t dx;
    uint8_t delay;
} Monster;

typedef struct { int16_t x, y; uint8_t on; } Thing;
typedef struct { int16_t x; uint8_t y, speed, on; int8_t dx; } Shot;
typedef struct { int16_t x; uint8_t y, ttl; } Splat;

/* --- состояние ------------------------------------------------------------ */
static Fish fish[MAX_FISH];
static uint8_t n_fish, sel;
static uint8_t counts[N_SPECIES];
static Thing food[MAX_FOOD], bubbles[MAX_BUBBLES];
static Monster mon[MAX_MON];
static Shot shots[MAX_SHOTS];
static Splat splats[MAX_SPLATS];
static uint8_t swarm_on, banner_on, banner_dirty, cry_timer;
static volatile uint8_t band_scx;
static uint8_t scene_mode, paused, frame, keys, prev_keys, pressed;
static uint8_t egg_count, egg_timer;
static uint16_t seed = 0xACE1u;

static uint8_t dlg_label[24], dlg_text[48];
static uint8_t dlg_ttl, dlg_age, dlg_dirty, dlg_talker;

static uint8_t tbuf[32], abuf[32];
static uint8_t wave_buf[16];
static uint8_t spr_n, spr_last;
static uint8_t cursor_row;

/* --- случайность ---------------------------------------------------------- */
static uint16_t rnd(void) {
    seed ^= seed << 7;
    seed ^= seed >> 9;
    seed ^= seed << 8;
    return seed;
}
static uint8_t rnd_range(uint8_t lo, uint8_t hi) { return lo + (uint8_t)(rnd() % (hi - lo + 1)); }

/* --- спрайты -------------------------------------------------------------- */
static void spr(int16_t x, int16_t y, uint8_t tile, uint8_t prop) {
    if (spr_n >= 40 || x <= -8 || x >= 160 || y <= -16 || y >= 144) return;
    shadow_OAM[spr_n].y = (uint8_t)(y + 16);
    shadow_OAM[spr_n].x = (uint8_t)(x + 8);
    shadow_OAM[spr_n].tile = tile;
    shadow_OAM[spr_n].prop = prop;
    spr_n++;
}

/* картинка из w спрайтов 8×16; смотрит вправо, при dx<0 отражается */
static void spr_wide(int16_t x, int16_t y, uint8_t tile, uint8_t w, int8_t dx, uint8_t pal) {
    uint8_t i, prop = S_BANK | pal;
    if (dx < 0) prop |= S_FLIPX;
    for (i = 0; i < w; i++) {
        uint8_t t = tile + ((dx > 0 ? i : (uint8_t)(w - 1 - i)) << 1);
        spr(x + (i << 3), y, t, prop);
    }
}

static void spr_finish(void) {
    uint8_t i;
    for (i = spr_n; i < spr_last; i++) shadow_OAM[i].y = 0;
    spr_last = spr_n;
}

/* --- текст и карта ----------------------------------------------------------- */
static void blit(uint8_t win, uint8_t x, uint8_t y, uint8_t w) {
    VBK_REG = VBK_ATTRIBUTES;
    if (win) set_win_tiles(x, y, w, 1, abuf); else set_bkg_tiles(x, y, w, 1, abuf);
    VBK_REG = VBK_TILES;
    if (win) set_win_tiles(x, y, w, 1, tbuf); else set_bkg_tiles(x, y, w, 1, tbuf);
}

static void fill(uint8_t from, uint8_t to, uint8_t tile, uint8_t attr) {
    uint8_t i;
    for (i = from; i < to; i++) { tbuf[i] = tile; abuf[i] = attr; }
}

/* кладёт строку (до 0xFE/0xFF) в tbuf/abuf с позиции at; возвращает длину */
static uint8_t text_into(uint8_t at, const uint8_t *s, uint8_t pal, uint8_t max) {
    uint8_t n = 0;
    while (s[n] != 0xFF && s[n] != 0xFE && n < max) {
        tbuf[at + n] = s[n];
        abuf[at + n] = pal;
        n++;
    }
    return n;
}

static void put_text(uint8_t x, uint8_t y, const uint8_t *s, uint8_t pal) {
    uint8_t n = text_into(0, s, pal, 20);
    if (n) blit(0, x, y, n);
}

static uint8_t text_len(const uint8_t *s) {
    uint8_t n = 0;
    while (s[n] != 0xFF && s[n] != 0xFE) n++;
    return n;
}

/* --- сцена ------------------------------------------------------------------ */
static const uint8_t TALL_WEED[] = { 1, 5, 8, 12, 16, 19 };
static const uint8_t SHORT_WEED[] = { 3, 10, 14 };

static void draw_surface(void) {
    fill(0, 20, T_WAVE, PAL_SURFACE);
    blit(0, 0, 0, 20);
}

static void draw_scene(void) {
    uint8_t y, i;
    draw_surface();
    fill(0, 32, T_WATER, PAL_TEXT);
    for (y = 1; y < 18; y++) {
        VBK_REG = VBK_ATTRIBUTES; set_bkg_tiles(0, y, 32, 1, abuf);
        VBK_REG = VBK_TILES; set_bkg_tiles(0, y, 32, 1, tbuf);
    }
    for (i = 0; i < sizeof(TALL_WEED); i++) {
        tbuf[0] = T_WEED_TOP; abuf[0] = PAL_WEED; blit(0, TALL_WEED[i], 14, 1);
        tbuf[0] = T_WEED_STEM; blit(0, TALL_WEED[i], 15, 1);
    }
    for (i = 0; i < sizeof(SHORT_WEED); i++) {
        tbuf[0] = T_WEED_TOP; abuf[0] = PAL_WEED; blit(0, SHORT_WEED[i], 15, 1);
    }
    fill(0, 20, T_SAND_TOP, PAL_SAND);
    blit(0, 0, 16, 20);
    fill(0, 20, T_SAND, PAL_SAND);
    blit(0, 0, 17, 20);
}

static void animate_scene(void) {
    uint8_t i;
    if ((frame & 7) == 0) {  /* волна бежит: сдвигаем биты тайла */
        for (i = 0; i < 16; i++) wave_buf[i] = (uint8_t)((wave_buf[i] << 1) | (wave_buf[i] >> 7));
        set_bkg_data(T_WAVE, 1, wave_buf);
    }
    if ((frame & 31) == 0) {  /* водоросли качаются */
        set_bkg_data(T_WEED_TOP, 2, weed_frames + ((frame & 32) ? 32 : 0));
    }
}

/* --- диалог ------------------------------------------------------------------ */
static uint8_t dlg_can(uint8_t force) { return force || !dlg_ttl || dlg_age >= DLG_MIN; }

static void dlg_open(uint8_t talker) {
    dlg_ttl = DLG_TIME;
    dlg_age = 0;
    dlg_dirty = 1;
    dlg_talker = talker;
}

static void dlg_render(void) {
    uint8_t row, n;
    const uint8_t *s = dlg_text;
    /* верх рамки с ником */
    tbuf[0] = T_BOX_TL; abuf[0] = PAL_BOX;
    fill(1, 19, T_BOX_H, PAL_BOX);
    tbuf[19] = T_BOX_TR; abuf[19] = PAL_BOX;
    text_into(1, dlg_label, PAL_LABEL, 18);
    blit(1, 0, 0, 20);
    for (row = 1; row <= 2; row++) {
        tbuf[0] = T_BOX_V; abuf[0] = PAL_BOX;
        fill(1, 19, T_WATER, PAL_BOX);
        tbuf[19] = T_BOX_V; abuf[19] = PAL_BOX;
        if (*s != 0xFF) {
            n = text_into(1, s, PAL_BOX, 18);
            s += n;
            if (*s == 0xFE) s++;
        }
        blit(1, 0, row, 20);
    }
    tbuf[0] = T_BOX_BL; abuf[0] = PAL_BOX;
    fill(1, 19, T_BOX_H, PAL_BOX);
    tbuf[19] = T_BOX_BR; abuf[19] = PAL_BOX;
    blit(1, 0, 3, 20);
}

static void say(uint8_t i, uint8_t event, uint8_t force) {
    Fish *f = &fish[i];
    if (!dlg_can(force)) return;
    if (!get_phrase(f->species, f->nick, event, rnd(), dlg_text)) return;
    get_nick(f->nick, dlg_label);
    dlg_open(i);
}

static void show_selected(void) {
    uint8_t n = 0, k = 0;
    Fish *f = &fish[sel];
    get_nick(f->nick, dlg_label);
    while (UI_KIND[k] != 0xFF) dlg_text[n++] = UI_KIND[k++];
    get_species_name(f->species, dlg_text + n);
    dlg_open(sel);
}

static void copy_ui(uint8_t *dst, const uint8_t *src) {
    do { *dst++ = *src; } while (*src++ != 0xFF);
}

/* --- рыбы -------------------------------------------------------------------- */
static uint8_t fish_w(Fish *f) { return species_gfx[f->species].width; }   /* в спрайтах */
static int16_t fish_max_x(Fish *f) { return (int16_t)(160 - (fish_w(f) << 3)) * FX; }

static uint8_t nick_used(uint8_t nick) {
    uint8_t i;
    for (i = 0; i < n_fish; i++) if (fish[i].nick == nick) return 1;
    return 0;
}

static void spawn_fish(void) {
    uint8_t s, c, total = 0;
    n_fish = 0;
    for (s = 0; s < N_SPECIES; s++) total += counts[s];
    for (s = 0; s < N_SPECIES; s++) {
        for (c = 0; c < counts[s] && n_fish < MAX_FISH; c++) {
            Fish *f = &fish[n_fish];
            uint8_t nick, lane;
            f->species = s;
            f->dx = (rnd() & 1) ? 1 : -1;
            f->speed = rnd_range(species_gfx[s].speed_lo, species_gfx[s].speed_hi);
            f->pal = (uint8_t)(rnd() % 6);
            do { nick = (uint8_t)(rnd() % N_NICKS); } while (nick_used(nick));
            f->nick = nick;
            f->mood = MOOD_SWIM;
            /* раскладываем по «дорожкам», чтобы спрайты не стояли в одной строке */
            lane = FISH_TOP + (uint8_t)(((uint16_t)n_fish * (FISH_BOTTOM - FISH_TOP)) / total);
            f->y = (int16_t)(lane + rnd_range(0, 6)) * FX;
            if (f->y > FISH_BOTTOM * FX) f->y = FISH_BOTTOM * FX;
            f->x = (int16_t)(rnd() % (uint16_t)(fish_max_x(f) + 1));
            n_fish++;
        }
    }
    sel = 0;
}

static int8_t nearest_food(Fish *f) {
    uint8_t i;
    int8_t best = -1;
    int16_t bd = 0x7FFF, fx = f->x >> 4;
    for (i = 0; i < MAX_FOOD; i++) {
        int16_t d;
        if (!food[i].on) continue;
        d = (food[i].x >> 4) - fx;
        if (d < 0) d = -d;
        if (d <= FOOD_RADIUS && d < bd) { bd = d; best = (int8_t)i; }
    }
    return best;
}

static int16_t clamp16(int16_t v, int16_t lo, int16_t hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* возвращает 1, если рыба только что вернулась после испуга */
static uint8_t step_fish(Fish *f) {
    int16_t max_x = fish_max_x(f);
    if (f->mood == MOOD_FLEE) {
        f->x += f->dx * FLEE_SPEED;
        f->x = clamp16(f->x, -48 * FX, 208 * FX);
        return 0;
    }
    if (f->mood == MOOD_RETURN) {
        uint8_t sp = f->speed << 1;
        if (sp < MIN_RETURN) sp = MIN_RETURN;
        if (f->x >= 0 && f->x <= max_x) { f->mood = MOOD_SWIM; return 1; }
        if (f->x > max_x) { f->dx = -1; f->x -= sp; if (f->x < max_x) f->x = max_x; }
        else { f->dx = 1; f->x += sp; if (f->x > 0) f->x = 0; }
        return 0;
    }
    {
        int8_t k = nearest_food(f);
        if (k >= 0) {
            Thing *fd = &food[k];
            int16_t tx = fd->x - ((int16_t)fish_w(f) << 6);   /* центр рыбы к корму */
            int16_t ty = fd->y - 6 * FX;
            int16_t d = tx - f->x;
            f->dx = d >= 0 ? 1 : -1;
            f->x += clamp16(d, -(int16_t)f->speed, f->speed);
            f->y += clamp16(ty - f->y, -(int16_t)f->speed, f->speed);
            f->y = clamp16(f->y, FISH_TOP * FX, FISH_BOTTOM * FX);
        } else {
            f->x += f->dx * (int16_t)f->speed;
        }
    }
    if (f->x >= max_x) { f->x = max_x; f->dx = -1; }
    else if (f->x <= 0) { f->x = 0; f->dx = 1; }
    return 0;
}

static uint8_t fish_hit(Fish *f, int16_t px, int16_t py) {
    int16_t x = f->x >> 4, y = f->y >> 4;
    return px >= x && px < x + (fish_w(f) << 3) && py >= y + 2 && py < y + 14;
}

static void drop_food(void) {
    uint8_t i;
    int16_t x;
    for (i = 0; i < MAX_FOOD && food[i].on; i++) {}
    if (i == MAX_FOOD) return;
    x = n_fish ? (fish[sel].x >> 4) + (fish_w(&fish[sel]) << 2) : rnd_range(8, 150);
    food[i].x = clamp16(x, 4, 150) * FX;
    food[i].y = 8 * FX;
    food[i].on = 1;
    {   /* кто ближе — замечает корм */
        uint8_t k, best = 0xFF;
        int16_t bd = FOOD_RADIUS + 1;
        for (k = 0; k < n_fish; k++) {
            int16_t d = (fish[k].x >> 4) - x;
            if (d < 0) d = -d;
            if (fish[k].mood == MOOD_SWIM && d < bd) { bd = d; best = k; }
        }
        if (best != 0xFF) say(best, EV_FOOD_SEEN, 1);
    }
}

static void step_food(void) {
    uint8_t i, k;
    for (i = 0; i < MAX_FOOD; i++) {
        Thing *fd = &food[i];
        if (!fd->on) continue;
        fd->y += 4;
        if ((fd->y >> 4) >= FLOOR_Y) { fd->on = 0; continue; }
        for (k = 0; k < n_fish; k++) {
            if (fish[k].mood == MOOD_SWIM && fish_hit(&fish[k], (fd->x >> 4) + 4, (fd->y >> 4) + 3)) {
                fd->on = 0;
                say(k, EV_FOOD_EATEN, 0);
                break;
            }
        }
    }
}

static void step_bubbles(void) {
    uint8_t i, k;
    for (i = 0; i < MAX_BUBBLES; i++) {
        if (!bubbles[i].on) continue;
        bubbles[i].y -= 6;
        if ((bubbles[i].y >> 4) < 8) bubbles[i].on = 0;
    }
    if ((rnd() & 0xFF) < 4 && n_fish) {
        Fish *f = &fish[rnd() % n_fish];
        for (k = 0; k < MAX_BUBBLES && bubbles[k].on; k++) {}
        if (k < MAX_BUBBLES && f->mood == MOOD_SWIM) {
            bubbles[k].x = f->x + (f->dx > 0 ? ((int16_t)fish_w(f) << 7) - 6 * FX : 0);
            bubbles[k].y = f->y;
            bubbles[k].on = 1;
        }
    }
}

/* --- шквал ------------------------------------------------------------------- */
static const uint8_t MON_W[] = { 96, 32, 16 };

static void lcd_isr(void) {
    if (LYC_REG == BAND_Y - 1) {
        while (STAT_REG & 3) {}
        SCX_REG = band_scx;
        LYC_REG = BAND_Y + 31;
    } else {
        while (STAT_REG & 3) {}
        SCX_REG = 0;
        LYC_REG = BAND_Y - 1;
    }
}

static void band_tiles(uint8_t show, int8_t dx) {
    uint8_t r, c;
    for (r = 0; r < 4; r++) {
        for (c = 0; c < 12; c++) {
            if (show) {
                tbuf[c] = T_BIG_DICK + r * 12 + (dx > 0 ? c : 11 - c);
                abuf[c] = PAL_DICK | (dx > 0 ? 0 : 0x20);
            } else {
                tbuf[c] = T_WATER;
                abuf[c] = PAL_TEXT;
            }
        }
        blit(0, BAND_COL, BAND_ROW + r, 12);
    }
}

static void start_swarm(void) {
    uint8_t i, n = 0, k;
    int8_t dx = (rnd() & 1) ? 1 : -1;
    uint8_t mediums = rnd_range(1, 2), smalls = rnd_range(3, 4);
    for (i = 0; i < 1 + mediums + smalls; i++) {
        Monster *m = &mon[n++];
        m->kind = i == 0 ? BIG : (i <= mediums ? MEDIUM : SMALL);
        m->dx = dx;
        m->active = 1;
        m->phase = rnd_range(0, 2);
        if (m->kind == BIG) {
            m->speed = rnd_range(8, 10);
            m->y = BAND_Y;
            m->delay = 0;
        } else {
            m->speed = m->kind == MEDIUM ? rnd_range(10, 13) : rnd_range(12, 15);
            m->y = rnd_range(16, 92);
            m->delay = rnd_range(10, 180);
        }
        m->cooldown = rnd_range(10, 60);
        m->x = dx > 0 ? -(int16_t)MON_W[m->kind] * FX : 160 * FX;
    }
    for (k = n; k < MAX_MON; k++) mon[k].active = 0;
    band_tiles(1, dx);
    band_scx = (uint8_t)(160 - (mon[0].x >> 4));
    swarm_on = 1;
    banner_on = 0;
    banner_dirty = 1;
    cry_timer = 30;
}

static void end_swarm(void) {
    uint8_t i;
    for (i = 0; i < n_fish; i++) {
        if (fish[i].mood == MOOD_FLEE) { fish[i].mood = MOOD_RETURN; fish[i].dx = -fish[i].dx; }
    }
    band_tiles(0, 1);
    band_scx = 0;
    swarm_on = 0;
    banner_on = 0;
    banner_dirty = 1;
}

static void fire(Monster *m) {
    uint8_t i, w = MON_W[m->kind];
    int16_t px = m->x >> 4, tip = m->dx > 0 ? px + w : px - 8;
    if (tip < 0 || tip > 152) return;
    for (i = 0; i < MAX_SHOTS && shots[i].on; i++) {}
    if (i == MAX_SHOTS) return;
    shots[i].on = 1;
    shots[i].x = tip * FX;
    shots[i].y = m->kind == BIG ? BAND_Y + 12 : m->y + 4;
    shots[i].dx = m->dx;
    shots[i].speed = m->speed + 24;
    for (i = 0; i < MAX_SPLATS && splats[i].ttl; i++) {}
    if (i < MAX_SPLATS) {  /* вспышка «пиу» у ствола */
        splats[i].x = tip;
        splats[i].y = m->kind == BIG ? BAND_Y + 10 : m->y + 2;
        splats[i].ttl = 6;
    }
}

static void step_swarm(void) {
    uint8_t i, k, alive = 0;
    for (i = 0; i < MAX_MON; i++) {
        Monster *m = &mon[i];
        int16_t px, front, w;
        if (!m->active) continue;
        alive = 1;
        if (m->delay) { m->delay--; continue; }
        m->x += m->dx * (int16_t)m->speed;
        px = m->x >> 4;
        w = MON_W[m->kind];
        front = m->dx > 0 ? px + w : px;
        for (k = 0; k < n_fish; k++) {
            Fish *f = &fish[k];
            int16_t ahead;
            if (f->mood == MOOD_FLEE) continue;
            ahead = ((f->x >> 4) + (fish_w(f) << 2) - front) * m->dx;
            if (ahead >= -w - 2 && ahead <= SCARE_RADIUS) {
                f->mood = MOOD_FLEE;
                f->dx = m->dx;
                if ((rnd() & 0xFF) < 102) say(k, EV_PANIC, 0);
            }
        }
        if (--m->cooldown == 0) {
            m->cooldown = m->kind == BIG ? rnd_range(30, 54)
                        : m->kind == MEDIUM ? rnd_range(54, 90) : rnd_range(84, 144);
            fire(m);
        }
        if (m->dx > 0 ? px > 160 : px + w < 0) m->active = 0;
    }
    band_scx = mon[0].active ? (uint8_t)(160 - (mon[0].x >> 4)) : 0;
    if (!alive) { end_swarm(); return; }
    if (--cry_timer == 0) {
        cry_timer = rnd_range(100, 180);
        i = (uint8_t)(rnd() % MAX_MON);
        for (k = 0; k < MAX_MON; k++, i = (uint8_t)((i + 1) % MAX_MON)) {
            if (mon[i].active && !mon[i].delay && dlg_can(0)) {
                uint8_t tiny = mon[i].kind == SMALL;
                get_cry(tiny, rnd(), dlg_text);
                copy_ui(dlg_label, tiny ? UI_TINY : UI_COSSACK);
                dlg_open(0xFF);
                break;
            }
        }
    }
    if ((frame % 24) == 0) { banner_on = !banner_on; banner_dirty = 1; }
}

static void step_shots(void) {
    uint8_t i, k;
    for (i = 0; i < MAX_SHOTS; i++) {
        Shot *s = &shots[i];
        int16_t px, head;
        if (!s->on) continue;
        s->x += s->dx * (int16_t)s->speed;
        px = s->x >> 4;
        if (px < -8 || px > 160) { s->on = 0; continue; }
        head = s->dx > 0 ? px + 7 : px;
        for (k = 0; k < n_fish; k++) {
            if (fish_hit(&fish[k], head, s->y + 4)) {
                uint8_t j;
                s->on = 0;
                for (j = 0; j < MAX_SPLATS && splats[j].ttl; j++) {}
                if (j < MAX_SPLATS) { splats[j].x = head - 4; splats[j].y = s->y; splats[j].ttl = 40; }
                if ((rnd() & 0xFF) < 180) say(k, EV_HIT, 0);
                break;
            }
        }
    }
    for (i = 0; i < MAX_SPLATS; i++) if (splats[i].ttl) splats[i].ttl--;
}

/* --- отрисовка аквариума ------------------------------------------------------ */
static void draw_tank(void) {
    uint8_t i;
    spr_n = 0;
    /* курсор и «!» говорящего — первыми, чтобы не потерялись */
    if (n_fish && !(frame & 16) && fish[sel].mood == MOOD_SWIM) {
        Fish *f = &fish[sel];
        spr((f->x >> 4) + (fish_w(f) << 2) - 4, (f->y >> 4) - 6, S_CURSOR, S_BANK | OPAL_UI);
    }
    if (dlg_ttl && dlg_talker < n_fish) {
        Fish *f = &fish[dlg_talker];
        int16_t hx = (f->x >> 4) + (f->dx > 0 ? (fish_w(f) << 3) - 6 : -2);
        spr(hx, (f->y >> 4) - 4, S_MARK, S_BANK | OPAL_UI);
    }
    for (i = 0; i < n_fish; i++) {
        Fish *f = &fish[i];
        const SpeciesGfx *g = &species_gfx[f->species];
        spr_wide(f->x >> 4, f->y >> 4, g->tile, g->width, f->dx, f->pal);
    }
    for (i = 0; i < MAX_FOOD; i++)
        if (food[i].on) spr(food[i].x >> 4, food[i].y >> 4, S_FOOD, S_BANK | OPAL_FOOD);
    if (swarm_on) {
        for (i = 0; i < MAX_MON; i++) {
            Monster *m = &mon[i];
            int16_t px;
            uint8_t fr;
            if (!m->active || m->delay) continue;
            px = m->x >> 4;
            fr = (uint8_t)(((frame >> 3) + m->phase) % 3);
            if (m->kind == BIG) {
                int16_t bx = px + (m->dx > 0 ? 44 : 36);
                int16_t by = BAND_Y - 7;
                spr_wide(bx, by, S_RIDER, 2, m->dx, OPAL_UI);
                spr(m->dx > 0 ? bx + 11 : bx - 3, by + 1, S_SABER0 + fr * 2,
                    S_BANK | OPAL_UI | (m->dx > 0 ? 0 : S_FLIPX));
            } else {
                uint8_t w = m->kind == MEDIUM ? 4 : 2;
                uint8_t seat = m->kind == MEDIUM ? 12 : 4;
                int16_t rx = m->dx > 0 ? px + seat : px + (w << 3) - seat - 8;
                spr_wide(px, m->y, m->kind == MEDIUM ? S_MEDIUM : S_SMALL, w, m->dx, OPAL_DICK);
                spr(rx, m->y - (m->kind == MEDIUM ? 2 : 1), S_TINY0 + fr * 2,
                    S_BANK | OPAL_UI | (m->dx > 0 ? 0 : S_FLIPX));
            }
        }
    }
    for (i = 0; i < MAX_SHOTS; i++)
        if (shots[i].on)
            spr(shots[i].x >> 4, shots[i].y, S_SHOT,
                S_BANK | OPAL_UI | (shots[i].dx > 0 ? 0 : S_FLIPX));
    for (i = 0; i < MAX_SPLATS; i++)
        if (splats[i].ttl) spr(splats[i].x, splats[i].y, S_SPLAT, S_BANK | OPAL_UI);
    for (i = 0; i < MAX_BUBBLES; i++)
        if (bubbles[i].on) spr(bubbles[i].x >> 4, bubbles[i].y >> 4, S_BUBBLE, S_BANK | OPAL_UI);
    spr_finish();
}

static void draw_banner(void) {
    if (paused) {
        uint8_t n;
        fill(0, 20, T_WATER, PAL_BANNER);
        n = text_len(UI_PAUSE);
        text_into((uint8_t)((20 - n) >> 1), UI_PAUSE, PAL_BANNER, 20);
        blit(0, 0, 0, 20);
    } else if (swarm_on && banner_on) {
        uint8_t n;
        fill(0, 20, T_WATER, PAL_BANNER);
        n = text_len(UI_BANNER);
        text_into((uint8_t)((20 - n) >> 1), UI_BANNER, PAL_BANNER, 20);
        blit(0, 0, 0, 20);
    } else {
        draw_surface();
    }
}

/* --- сохранение (SRAM картриджа, Everdrive пишет на SD) ------------------------ */
#define SAVE ((volatile uint8_t *)0xA000)

static uint8_t total_count(void) {
    uint8_t s, t = 0;
    for (s = 0; s < N_SPECIES; s++) t += counts[s];
    return t;
}

static void save_counts(void) {
    uint8_t s, sum = 0;
    ENABLE_RAM;
    SWITCH_RAM(0);
    SAVE[0] = 'A'; SAVE[1] = 'Q'; SAVE[2] = '1';
    for (s = 0; s < N_SPECIES; s++) { SAVE[3 + s] = counts[s]; sum += counts[s]; }
    SAVE[3 + N_SPECIES] = sum ^ 0x5A;
    DISABLE_RAM;
}

static uint8_t load_counts(void) {
    uint8_t s, sum = 0, ok;
    ENABLE_RAM;
    SWITCH_RAM(0);
    ok = SAVE[0] == 'A' && SAVE[1] == 'Q' && SAVE[2] == '1';
    for (s = 0; ok && s < N_SPECIES; s++) {
        counts[s] = SAVE[3 + s];
        if (counts[s] > MAX_FISH) ok = 0;
        sum += counts[s];
    }
    if (ok && (SAVE[3 + N_SPECIES] != (sum ^ 0x5A) || sum == 0 || sum > MAX_FISH)) ok = 0;
    DISABLE_RAM;
    if (!ok) for (s = 0; s < N_SPECIES; s++) counts[s] = 0;
    return ok;
}

/* --- экран выбора ------------------------------------------------------------- */
static void picker_row(uint8_t s) {
    uint8_t buf[24];
    fill(0, 20, T_WATER, PAL_TEXT);
    if (s == cursor_row) { tbuf[1] = UI_ARROW[0]; abuf[1] = PAL_LABEL; }
    get_species_name(s, buf);
    text_into(3, buf, s == cursor_row ? PAL_LABEL : PAL_TEXT, 9);
    tbuf[12] = UI_TIMES[0];
    tbuf[13] = UI_DIGITS[counts[s]];
    if (s == cursor_row) { abuf[12] = PAL_LABEL; abuf[13] = PAL_LABEL; }
    blit(0, 0, 2 + s, 20);
}

static void picker_total(void) {
    uint8_t n, t = total_count();
    fill(0, 20, T_WATER, PAL_TEXT);
    n = text_into(1, UI_HINT3, PAL_TEXT, 18);
    tbuf[1 + n] = UI_DIGITS[t];
    text_into(2 + n, UI_OF, PAL_TEXT, 4);
    blit(0, 0, 17, 20);
}

static void picker_open(void) {
    uint8_t s, n;
    scene_mode = MODE_PICKER;
    HIDE_WIN;
    dlg_ttl = 0;
    band_scx = 0;
    swarm_on = 0;
    DISPLAY_OFF;
    fill(0, 32, T_WATER, PAL_TEXT);
    for (s = 0; s < 18; s++) blit(0, 0, s, 32);
    fill(0, 20, T_WATER, PAL_LABEL);
    n = text_len(UI_TITLE);
    text_into((uint8_t)((20 - n) >> 1), UI_TITLE, PAL_LABEL, 20);
    blit(0, 0, 0, 20);
    for (s = 0; s < N_SPECIES; s++) picker_row(s);
    put_text(1, 15, UI_HINT1, PAL_TEXT);
    put_text(1, 16, UI_HINT2, PAL_TEXT);
    picker_total();
    DISPLAY_ON;
}

static void picker_frame(void) {
    uint8_t old = cursor_row, s, changed = 0;
    if (pressed & J_UP) cursor_row = cursor_row ? cursor_row - 1 : N_SPECIES - 1;
    if (pressed & J_DOWN) cursor_row = (uint8_t)((cursor_row + 1) % N_SPECIES);
    if ((pressed & J_RIGHT) && total_count() < MAX_FISH) { counts[cursor_row]++; changed = 1; }
    if ((pressed & J_LEFT) && counts[cursor_row]) { counts[cursor_row]--; changed = 1; }
    if (pressed & J_B) { for (s = 0; s < N_SPECIES; s++) counts[s] = 0; changed = 2; }
    if (pressed & J_SELECT) {
        uint8_t want = rnd_range(3, MAX_FISH);
        for (s = 0; s < N_SPECIES; s++) counts[s] = 0;
        while (want--) counts[rnd() % N_SPECIES]++;
        changed = 2;
    }
    if (old != cursor_row) { picker_row(old); picker_row(cursor_row); }
    if (changed == 2) for (s = 0; s < N_SPECIES; s++) picker_row(s);
    else if (changed) picker_row(cursor_row);
    if (changed) picker_total();
    /* превью рыбы справа от курсора */
    spr_n = 0;
    {
        const SpeciesGfx *g = &species_gfx[cursor_row];
        spr_wide(116, (2 + cursor_row) * 8 - 4, g->tile, g->width, 1, (uint8_t)(cursor_row % 6));
    }
    spr_finish();
}

/* --- аквариум ----------------------------------------------------------------- */
static void tank_open(void) {
    uint8_t i;
    scene_mode = MODE_TANK;
    DISPLAY_OFF;
    draw_scene();
    spawn_fish();
    for (i = 0; i < MAX_FOOD; i++) food[i].on = 0;
    for (i = 0; i < MAX_BUBBLES; i++) bubbles[i].on = 0;
    for (i = 0; i < MAX_SHOTS; i++) shots[i].on = 0;
    for (i = 0; i < MAX_SPLATS; i++) splats[i].ttl = 0;
    for (i = 0; i < MAX_MON; i++) mon[i].active = 0;
    swarm_on = 0;
    paused = 0;
    band_scx = 0;
    egg_count = 0;
    /* подсказка по кнопкам при входе */
    copy_ui(dlg_label, UI_TITLE);
    copy_ui(dlg_text, UI_HELP);
    dlg_open(0xFF);
    DISPLAY_ON;
}

static void tank_frame(void) {
    uint8_t i;
    if (pressed & J_START) { paused = !paused; banner_dirty = 1; }
    if (paused && (pressed & J_SELECT)) { picker_open(); return; }
    if (paused) { draw_tank(); return; }
    /* пасхалка: B пять раз подряд (каждое нажатие ещё и тыкает рыбу) */
    if (pressed & J_B) {
        egg_count = egg_timer ? egg_count + 1 : 1;
        egg_timer = EGG_GAP;
        if (egg_count >= EGG_PRESSES) { egg_count = 0; if (!swarm_on) start_swarm(); }
    } else if (pressed) {
        egg_count = 0;
    }
    if (egg_timer) egg_timer--;
    if (n_fish && (pressed & J_RIGHT)) { sel = (uint8_t)((sel + 1) % n_fish); show_selected(); }
    if (n_fish && (pressed & J_LEFT)) { sel = sel ? sel - 1 : n_fish - 1; show_selected(); }
    if (pressed & J_A) drop_food();
    if ((pressed & J_B) && n_fish) say(sel, EV_POKE, 1);

    if (swarm_on) { step_swarm(); step_shots(); }
    else for (i = 0; i < MAX_SHOTS; i++) shots[i].on = 0;
    for (i = 0; i < n_fish; i++) {
        if (step_fish(&fish[i]) && (rnd() & 1)) say(i, EV_HOME, 0);
    }
    step_food();
    step_bubbles();
    if (!dlg_ttl && n_fish && (rnd() % 300) == 0) say((uint8_t)(rnd() % n_fish), EV_IDLE, 0);
    if (dlg_ttl) {
        dlg_ttl--;
        if (dlg_age < 255) dlg_age++;
        if (!dlg_ttl) dlg_dirty = 1;
    }
    draw_tank();
}

/* --- главный цикл ---------------------------------------------------------------- */
void main(void) {
    uint8_t i;
    DISPLAY_OFF;
    cpu_fast();
    load_graphics();
    for (i = 0; i < 16; i++) wave_buf[i] = wave_tile[i];
    SPRITES_8x16;
    SHOW_BKG;
    SHOW_SPRITES;
    move_win(7, WIN_Y);
    CRITICAL {
        STAT_REG = STATF_LYC;
        LYC_REG = BAND_Y - 1;
        add_LCD(lcd_isr);
    }
    set_interrupts(VBL_IFLAG | LCD_IFLAG);
    seed ^= DIV_REG;
    if (load_counts()) tank_open(); else picker_open();
    while (1) {
        wait_vbl_done();
        /* обновления VRAM — в начале кадра, пока идёт VBlank */
        if (scene_mode == MODE_TANK) {
            animate_scene();
            if (dlg_dirty) {
                dlg_dirty = 0;
                if (dlg_ttl) { dlg_render(); SHOW_WIN; } else HIDE_WIN;
            }
            if (banner_dirty) { banner_dirty = 0; draw_banner(); }
        }
        frame++;
        prev_keys = keys;
        keys = joypad();
        pressed = keys & ~prev_keys;
        if (pressed) seed ^= (uint16_t)DIV_REG << 3 | frame;
        if (scene_mode == MODE_PICKER) {
            if ((pressed & J_A) && total_count()) {
                save_counts();
                tank_open();
                continue;
            }
            picker_frame();
        } else {
            tank_frame();
        }
    }
}
