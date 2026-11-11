// Сгенерировано gb/assets.py — руками не править.
#ifndef GEN_GFX_H
#define GEN_GFX_H
#include <gb/gb.h>
#include <stdint.h>

// тайлы фона (банк VRAM 0) — всего 157
#define T_WATER 0
#define T_WAVE 1
#define T_WEED_TOP 2
#define T_WEED_STEM 3
#define T_SAND_TOP 4
#define T_SAND 5
#define T_BOX_H 6
#define T_BOX_V 7
#define T_BOX_TL 8
#define T_BOX_TR 9
#define T_BOX_BL 10
#define T_BOX_BR 11
#define T_BIG_DICK 109
#define T_FONT 16
#define S_MEDIUM 62
#define S_SMALL 70
#define S_RIDER 74
#define S_SABER0 78
#define S_SABER1 80
#define S_SABER2 82
#define S_TINY0 84
#define S_TINY1 86
#define S_TINY2 88
#define S_SHOT 90
#define S_SPLAT 92
#define S_FOOD 94
#define S_BUBBLE 96
#define S_CURSOR 98
#define S_MARK 100

// спрайты 8×16 (банк VRAM 1) — всего 102
typedef struct { uint8_t tile, width, speed_lo, speed_hi; } SpeciesGfx;
extern const SpeciesGfx species_gfx[12];
extern const uint8_t weed_frames[64];
extern const uint8_t wave_tile[16];
extern const uint8_t UI_TITLE[];
extern const uint8_t UI_PAUSE[];
extern const uint8_t UI_BANNER[];
extern const uint8_t UI_COSSACK[];
extern const uint8_t UI_TINY[];
extern const uint8_t UI_KIND[];
extern const uint8_t UI_HINT1[];
extern const uint8_t UI_HINT2[];
extern const uint8_t UI_HINT3[];
extern const uint8_t UI_OF[];
extern const uint8_t UI_TIMES[];
extern const uint8_t UI_ARROW[];
extern const uint8_t UI_DIGITS[];
extern const uint8_t UI_HELP[];

void load_graphics(void) BANKED;
#endif
