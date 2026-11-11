// Сгенерировано gb/assets.py — руками не править.
#ifndef GEN_TEXT_H
#define GEN_TEXT_H
#include <gb/gb.h>
#include <stdint.h>

#define N_SPECIES 12
#define N_NICKS 44
#define EV_IDLE 0
#define EV_FOOD_SEEN 1
#define EV_FOOD_EATEN 2
#define EV_POKE 3
#define EV_PANIC 4
#define EV_HOME 5
#define EV_HIT 6

// Тексты: коды тайлов шрифта, 0xFE — перевод строки, 0xFF — конец.
uint8_t get_phrase(uint8_t sp, uint8_t nick, uint8_t event, uint16_t r, uint8_t *out) BANKED;
void get_cry(uint8_t tiny, uint16_t r, uint8_t *out) BANKED;
void get_nick(uint8_t nick, uint8_t *out) BANKED;
void get_species_name(uint8_t sp, uint8_t *out) BANKED;
#endif
