#!/usr/bin/env python3
"""Терминальный аквариум со случайными рыбами и смешными никами."""
import curses
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

MAX_PER_SPECIES = 20


# --- конфиг ---------------------------------------------------------------

def config_path():
    return Path.home() / ".config" / "aquarium" / "config.json"


def load_config(path, species):
    """Возвращает {вид: количество} или None, если конфига нет или он негоден."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    counts = {name: 0 for name in species}
    for name, value in data.items():
        if name not in counts:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        counts[name] = max(0, min(MAX_PER_SPECIES, value))
    if sum(counts.values()) == 0:
        return None
    return counts


def save_config(path, counts):
    """Пишет конфиг; при ошибке записи возвращает False."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(counts, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return False
    return True


# --- виды и ники ----------------------------------------------------------

class Species(NamedTuple):
    name: str
    right: list
    left: list
    speed: tuple
    icon: str


_MIRROR = str.maketrans("<>()[]{}/\\`'", "><)(][}{\\/'`")


def _mirror(lines):
    width = max(len(line) for line in lines)
    return [line.ljust(width)[::-1].translate(_MIRROR) for line in lines]


def _species(name, right, speed, icon):
    return Species(name, right, _mirror(right), speed, icon)


# Рисунки смотрят вправо; "o", "°" и "@" считаются глазами и рисуются ярче.
SPECIES = {s.name: s for s in [
    _species("Рыбка", [
        r"  ,--.  ",
        r"><(  o)>",
        r"  `--'  ",
    ], (6, 12), "><(o)>"),
    _species("Рыба-меч", [
        r"       ,___     ",
        r"~~===<  o >-----",
        r"       `--'     ",
    ], (10, 16), "=<o>---"),
    _species("Окунь", [
        r"    ,-./|\,   ",
        r" \,'  |||  `. ",
        r"  >=  ||||  o>",
        r" /`.  |||  ,' ",
        r"    `-\|/'    ",
    ], (5, 10), "><(|o>"),
    _species("Акула", [
        r"           /|     ",
        r"          / |     ",
        r"  _______/  |___  ",
        r"><_____________o_>",
        r"  `-.______,.-'   ",
    ], (8, 14), "><__o_>"),
    _species("Кит", [
        r"          \|/        ",
        r"           |         ",
        r"    ,-----------.__  ",
        r" __/               `.",
        r"/              o    _\>",
        r"\_    ___________,-'  ",
        r"  `--'               ",
    ], (3, 6), "(____o>"),
    _species("Медуза", [
        r"  .-===-.  ",
        r" /       \ ",
        r"| o     o |",
        r" \_______/ ",
        r"  | | | |  ",
        r"  ) ( ) (  ",
    ], (1, 3), "(o_o)"),
    _species("Ангел", [
        r"       /\       ",
        r"      /  \      ",
        r"     /    \     ",
        r" ><(   .  o  )> ",
        r"     \    /     ",
        r"      \  /      ",
        r"       \/       ",
    ], (4, 8), "/o\\"),
    _species("Скат", [
        r"      __       ",
        r"   .-'  `-.    ",
        r"  <  o  o   >~~~",
        r"   `-.____.-'  ",
    ], (4, 9), "<o o>~"),
    _species("Осьминог", [
        r"   ,---.   ",
        r"  ( o o )  ",
        r"  /`---'\  ",
        r" // | | \\ ",
        r" ~~ ~ ~ ~~ ",
    ], (2, 5), "(oo)~"),
    _species("Конёк", [
        r"  _   ",
        r" (o`> ",
        r" ) /  ",
        r" ( (  ",
        r"  ) ) ",
        r" (_/  ",
    ], (2, 4), "(o`>"),
    _species("Пиранья", [
        r"    ,--.   ",
        r"><( o |vvv>",
        r"    `--'   ",
    ], (10, 18), "><(ovv>"),
    _species("Мальки", [
        r" ><>   ",
        r"    ><>",
        r" ><>   ",
    ], (8, 14), "><> ><>"),
]}

NICKS = [
    "segfault_петя", "NullPointer_Вася", "пельмень_42", "котлета_0xFF",
    "борщ_dev", "дед_инсайд", "git_push_force", "rm_rf_слэш",
    "undefined_behavior", "стековерфлоу", "багфикс_в_пятницу", "docker_ушёл",
    "кофе_без_сахара", "merge_conflict", "tab_vs_space", "вайбкодер",
    "sudo_make_me_fish", "ctrl_c_ctrl_v", "ночной_деплой", "legacy_код",
    "прод_упал", "работает_у_меня", "TODO_потом", "hotfix_final_v3",
    "кот_в_проде", "regex_мастер", "бэкап_был", "оно_само",
    "main_без_ревью", "localhost_forever", "cache_miss", "off_by_one",
    "рекурсия_рекурсия", "memory_leak_олег", "семён_senior", "junior_на_максималках",
    "agile_акула", "скрам_мастер_рыб", "ci_красный", "lgtm_не_читая",
    "node_modules_5ГБ", "pip_install_всё", "комментарий_не_нужен", "чайник_python",
]

# --- реплики --------------------------------------------------------------
# События: idle — по таймеру, food_seen — увидела корм, food_eaten — съела,
# poke — ткнули клавишей t. Фразы не длиннее 28 символов и без эмодзи.

PHRASES = {
    "idle": [
        "кто трогал прод?", "опять пятница…", "это не баг, это фича",
        "у меня локально работает", "блядь, опять мерж-конфликт",
        "кто писал этот код? а, я", "давайте без созвонов", "хуй пойми, но работает",
        "надо бы тесты написать", "в проде всё по-другому", "щас, только кофе налью",
        "ну и легаси, ёб твою мать", "пятница, 18:00, деплой", "я не буду это ревьюить",
        "кто удалил .env?", "доки? какие доки?", "опять ебучий CORS",
        "зачем я пошёл в IT?", "уйду в фермеры, нахуй", "сегодня без багов. Шучу",
        "встреча могла быть письмом", "джира опять тормозит", "кто закрыл мой тикет?",
        "x, x2, x_final, x_fin2", "компилится? Не трогай", "пиздец, а не архитектура",
        "микросервисы, блядь", "кто заказал Kubernetes?", "часовые пояса — зло",
        "UTC или смерть", "404: мотивация не найдена", "500 Internal Fish Error",
        "мне бы в отпуск", "ещё один стендап, блядь", "задача на 5 минут, ага",
        "почему prod != staging?", "сломал, но красиво", "а давайте на Rust?",
        "перепишем всё на Go", "undefined is not a fish", "отмерь семь раз, деплой раз",
        "в чате 300 непрочитанных", "кто опять в reply-all?", "хуёвый день для релиза",
        "я в домике (в тикете)", "этот коммит — без слов", "fix, fix2, real fix",
        "ну и нахуя тут синглтон?", "пароль: admin123", "кто сжёг весь CI бюджет?",
        "работаю за еду, буквально", "аквариум — мой опенспейс",
    ],
    "food_seen": [
        "о, хотфикс с неба!", "жратва! бросаю тикет", "мой корм, отъебитесь",
        "обед по расписанию", "это мне? за переработку?", "блин, бонус прилетел",
        "пицца за овертайм!", "о, крошки от бюджета", "это что, тимбилдинг?",
        "печеньки на кухне!", "халява, пацаны!", "наконец-то, сука, обед",
        "моё! у меня приоритет P0", "ща сожру, не мешай", "корм упал — мерж потом",
        "это фидбек или еда?", "кормят — значит, увольнять", "стоп, это не таска?",
    ],
    "food_eaten": [
        "вкуснее, чем легаси", "ммм, пельмешек", "сожрал и не закоммитил",
        "это была премия?", "заебись, наелась", "ещё бы кофейку",
        "сожрал и в прод", "нормально так поел", "калорий больше, чем строк",
        "сытый дев — добрый дев", "теперь можно и поспать", "переварю к релизу",
        "сухо, как ваш фронтенд", "вкусно, но мало, блядь", "добавьте в бэклог ещё",
        "закусила багом", "ам. LGTM", "съела, тесты зелёные", "это вся индексация?",
        "сыт, но не замотивирован", "кто это готовил? джун?",
    ],
    "poke": [
        "чё тыкаешь, я на дейлике", "не трогай, я компилируюсь", "отъебись, у меня ревью",
        "я в фокусе, блин", "ещё раз ткнёшь — уволюсь", "пиши в слак, сука",
        "ой, всё", "у меня статус «занят»", "не дёргай, я в потоке",
        "я в отпуске, блядь", "ты кто вообще? из HR?", "сначала заведи тикет",
        "тыкнешь ещё — приму оффер", "я не баг, не дебажь меня", "щекотно, сука",
        "ты сломал мне контекст", "ну чё, чё надо?", "одна рыба — один тикет",
        "тыкать — это микроменедж", "я тебе не тамагочи", "сам ты рыба",
        "в календаре меня нет",
    ],
    # пасхалка: мимо проплывает хуй
    "panic": [
        "ЁБАНЫЙ ПИЗДЕЦ!", "СПАСАЙСЯ КТО МОЖЕТ!", "ЭТО ЧТО ЗА ХУЙНЯ?!",
        "ОН ОГРОМНЫЙ, БЛЯДЬ!", "АААА, ПРОД ГОРИТ!", "это не акула!!!",
        "ПОЛУНДРА, СУКА!", "мама, забери меня", "я в этом не участвую!",
        "РЕТРО ОТМЕНЯЕТСЯ!", "ХОТФИКС НЕ ПОМОЖЕТ!", "rm -rf меня, пожалуйста",
        "к такому меня не готовили", "НАХУЙ, НАХУЙ, НАХУЙ",
    ],
    "home": [
        "что это было?", "я ничего не видела", "забудем это", "это был деплой?",
        "в ретро не включаем", "пиздец, я поседела", "NDA, ребята, NDA",
        "у меня вьетнамские флешбэки", "и это теперь в проде?", "кто его пустил?",
        "надеюсь, он не вернётся", "ну и инцидент, блядь", "постмортем писать не буду",
        "я вся липкая, блядь", "кто-нибудь, дайте салфетку",
    ],
    # в рыбу попала капля
    "hit": [
        "ФУ, БЛЯДЬ!", "МЕНЯ ЗАДЕЛО!", "оно липкое!!!", "В ГЛАЗ, СУКА!",
        "фу, тёплое", "HR, ВЫ ЭТО ВИДЕЛИ?!", "это харассмент!", "я ранена… и липкая",
        "МЕДИКА! ПОЛОТЕНЦЕ!", "прямо в ник, сука", "это не та интеграция",
        "мне это в резюме?", "ЗАЧЕМ В ЛИЦО?!", "я в этом участвовать не…",
        "белый экран смерти", "это был мерж в меня?",
    ],
}

# Виды как роли в команде.
SPECIES_PHRASES = {
    "Рыбка": {
        "idle": ["я просто рыбка", "плаваю, не мешаю", "память — 3 секунды",
                 "о, замок! о, замок!", "глупая, но в штате", "что я тут делала?"],
        "poke": ["я просто рыбка, отъебитесь", "чё? я уже забыла",
                 "у меня лапки. А, нет"],
        "food_eaten": ["что я ела? забыла", "буль"],
    },
    "Рыба-меч": {
        "idle": ["щас всё перепишу нахуй", "рефакторю мечом", "этот модуль — под нож",
                 "удалила 3000 строк, кайф", "кто так пишет, блядь?", "DRY, сука, DRY"],
        "poke": ["осторожно, я острая", "проколю, не подходи", "режу без ревью"],
        "food_eaten": ["разрубила и съела", "нашинковала, как монолит"],
    },
    "Окунь": {
        "idle": ["я просто таски закрываю", "миддл восьмой год", "зарплату бы поднять",
                 "сеньор? когда-нибудь", "опять перф-ревью", "норм, работаем"],
        "poke": ["я не сеньор, отстаньте", "не моя зона ответственности",
                 "я обычный, чё ты"],
        "food_eaten": ["индексации нет, хоть корм"],
    },
    "Акула": {
        "idle": ["почему не в спринте, блядь?", "эстимейт — два часа. Точка.",
                 "кто сорвал дедлайн?", "овертайм — добровольно", "а почему не вчера?",
                 "мы семья. Работай.", "я в твои годы — FTP-деплой"],
        "poke": ["зайди ко мне на 1-на-1", "ты уволен. Шучу. Пока.",
                 "выпишу тебе PIP", "ты на кого тыкаешь?"],
        "food_seen": ["это моё, по иерархии"],
        "food_eaten": ["мало. Где остальное?", "съела. Это был джун?"],
    },
    "Кит": {
        "idle": ["мне 15 лет, я ещё в проде", "не трогайте меня, я хрупкий",
                 "я написан на Perl", "мой автор давно уволился",
                 "0 тестов и 1 молитва", "перезапуск? только с попом"],
        "poke": ["тронешь — всё упадёт", "ой. Core dumped.", "у меня нет API, иди нахуй"],
        "food_seen": ["медленно, но доплыву", "загрузка… 3%…"],
        "food_eaten": ["ушло в swap"],
    },
    "Медуза": {
        "idle": ["давайте созвон на часок", "позвоночник? не слышала",
                 "а можно ещё фичу?", "дедлайн вчера, ок?", "синкнемся по синку",
                 "пусть будет как в Figma", "клиент передумал. Опять."],
        "poke": ["давай обсудим на ретро", "занеси в конфлюенс", "это вопрос к бизнесу"],
        "food_seen": ["закиньте корм в бэклог", "кто аппрувил этот обед?"],
    },
    "Ангел": {
        "idle": ["у меня покрытие 100%", "ну почти 100%", "линтер не ругается",
                 "сначала тесты, потом код", "у меня SOLID в крови",
                 "3 часа на имя переменной"],
        "poke": ["у меня всё по гайдам", "без PR не трогать!", "фу, руки немытые"],
        "food_eaten": ["съела, задокументировала"],
    },
    "Скат": {
        "idle": ["кто положил пайплайн, сука?", "кубер опять в ауте",
                 "не трогайте YAML", "отступ в YAML, сука", "всё в терраформе. Почти",
                 "мониторинг молчит. Страшно", "у кого sudo? у всех?!"],
        "poke": ["я в инциденте, отвали", "я дежурю, иди нахуй", "пингуй в PagerDuty"],
        "food_eaten": ["задеплоила в желудок"],
    },
    "Осьминог": {
        "idle": ["8 рук — 8 тикетов, охуенно", "фронт, бэк, и я же DBA",
                 "фулстек — это фулпиздец", "ещё и DevOps на мне",
                 "зарплата — на одну руку"],
        "poke": ["у меня все руки заняты", "отпусти, у меня 8 PR",
                 "тыкни в другую руку"],
        "food_eaten": ["ем восемью руками"],
    },
    "Конёк": {
        "idle": ["сдвинь на 1px влево", "это не тот оттенок", "шрифт — говно",
                 "добавьте воздуха", "сделай как у Apple", "этот пиксель уехал"],
        "poke": ["не трогай макет!", "я художник, я так вижу", "это не тот #FFFFFF"],
        "food_seen": ["корм не в сетке, но ок"],
    },
    "Пиранья": {
        "idle": ["нашла 40 багов, жри", "а если ввести -1?", "переоткрыла тикет",
                 "а в Safari проверяли?", "а если 10к юзеров?",
                 "воспроизвелось, ха-ха"],
        "poke": ["воспроизведи сначала", "щас и тебя протестирую", "блокер, сука!"],
        "food_eaten": ["съела, как ваш релиз", "сожрала с регрессом"],
    },
    "Мальки": {
        "idle": ["а что такое git?", "я случайно форснул в main", "а где тут прод?",
                 "нам ChatGPT сказал", "можно в мастер? Уже.", "кто такой SOLID?"],
        "poke": ["я стажёр, не бейте", "нас четверо, пощадите", "мы не виноваты!"],
        "food_seen": ["нам тоже можно?", "ура, бесплатная еда!"],
    },
}

# Лор ников: фразы для idle и poke.
NICK_PHRASES = {
    "segfault_петя": ["Segmentation fault (core)", "опять в нулевой адрес",
                      "Петя упал. Опять."],
    "NullPointer_Вася": ["я ничего не указываю", "null — тоже значение",
                         "Вася? Вася is null"],
    "пельмень_42": ["42 — ответ на всё", "я варёный, не трогай", "со сметаной, плиз"],
    "котлета_0xFF": ["255 котлет в байте", "я переполнилась, 0x00"],
    "борщ_dev": ["разработка со сметаной", "свёкла — это бэкенд"],
    "дед_инсайд": ["всё тлен, даже прод", "я выгорел ещё в 2019", "мне похуй. Деплойте."],
    "git_push_force": ["история? какая история?", "--force и похуй",
                       "чужие коммиты? нет таких"],
    "rm_rf_слэш": ["я просто место почистил", "а где все файлы?", "sudo был лишним"],
    "undefined_behavior": ["я сам не знаю, что сделаю", "сегодня я — NaN"],
    "стековерфлоу": ["скопировал — значит, понял", "закрыто как дубликат"],
    "багфикс_в_пятницу": ["что может пойти не так?", "увидимся в понедельник. Ой"],
    "docker_ушёл": ["контейнер упал и не встал", "exited with code 137"],
    "кофе_без_сахара": ["без кофе не компилирую", "пятая кружка. Норм."],
    "merge_conflict": ["<<<<<<< HEAD", "выбери меня, а не их", ">>>>>>> их хуйня"],
    "tab_vs_space": ["табы, блядь, только табы", "4 пробела — для слабых"],
    "вайбкодер": ["нейронка напишет", "я не читаю код, я чую", "промпт — это тоже код"],
    "sudo_make_me_fish": ["Okay.", "permission denied. Буль"],
    "ctrl_c_ctrl_v": ["это не плагиат, а реюз", "Ctrl+V. Готово."],
    "ночной_деплой": ["три ночи — время релиза", "все спят — деплою",
                      "откат? утром разберутся"],
    "legacy_код": ["меня писали ещё на CVS", "не трогать, работает с 2003"],
    "прод_упал": ["прод опять лёг, пиздец", "не я, оно само", "алерты? я их выключил"],
    "работает_у_меня": ["у меня всё работает, хули", "дам тебе свой ноут"],
    "TODO_потом": ["потом починю. Наверное.", "TODO с 2016-го"],
    "hotfix_final_v3": ["это точно последний фикс", "final_v4 уже в пути"],
    "кот_в_проде": ["мяу. Прод на клавиатуре", "уронил сервер со стола"],
    "regex_мастер": ["^.*$ — и всё понятно", "теперь у вас 2 проблемы"],
    "бэкап_был": ["бэкап был. Вчера. Наверно", "восстановить? не пробовал"],
    "оно_само": ["я ничего не трогал", "магия. Не спрашивай."],
    "main_без_ревью": ["ревью для слабаков", "пушу в main, как мужик"],
    "localhost_forever": ["127.0.0.1 — мой дом", "в облако? нахуй облако"],
    "cache_miss": ["я тебя не помню", "а мы знакомы?"],
    "off_by_one": ["я тут на одну больше", "или на одну меньше"],
    "рекурсия_рекурсия": ["см. рекурсия_рекурсия", "StackOverflowError"],
    "memory_leak_олег": ["я ничего не освобождаю", "я не теку, я коплю",
                         "Олег съел всю RAM"],
    "семён_senior": ["зависит от контекста", "видел это ещё в 2007",
                     "давай я сам. Отойди."],
    "junior_на_максималках": ["я уже почти сеньор", "а что, нельзя в мастер?",
                              "через полгода — тимлид"],
    "agile_акула": ["это не баг, это сторя", "оцениваем в попугаях"],
    "скрам_мастер_рыб": ["давайте ретро про ретро", "что тебе мешает? я?"],
    "ci_красный": ["перезапусти, вдруг пройдёт", "flaky, блядь, опять"],
    "lgtm_не_читая": ["LGTM, не читал", "апрув вслепую", "+1, похуй"],
    "node_modules_5ГБ": ["я тяжелее чёрной дыры", "npm i — и пошёл за чаем"],
    "pip_install_всё": ["зависимостей много не бывает", "venv? не, глобально"],
    "комментарий_не_нужен": ["код сам себя объясняет", "// тут магия"],
    "чайник_python": ["а где фигурные скобки?", "IndentationError, блядь"],
}

COLORS = 6


# --- модель рыбы ----------------------------------------------------------

@dataclass
class Fish:
    species: str
    x: float
    y: float
    dx: int
    speed: float
    color: int
    nick: str
    speech: str = ""
    speech_ttl: float = 0.0
    mood: str = ""  # "" — плавает, "flee" — удирает, "return" — возвращается


FOOD_RADIUS = 15
FLEE_SPEED = 45.0
RETURN_SPEED_FACTOR = 2.0
MIN_RETURN_SPEED = 10.0  # чтобы медуза не ползла обратно полминуты


def fish_lines(fish):
    sp = SPECIES[fish.species]
    return sp.right if fish.dx > 0 else sp.left


def fish_width(fish):
    return max(len(line) for line in fish_lines(fish))


def _bounds(fish, width, height):
    # снизу остаются ник, два ряда водорослей и строка подсказки
    return max(0, width - fish_width(fish)), max(1, height - 4 - len(fish_lines(fish)))


def spawn_fish(counts, width, height, rng):
    nicks = []
    result = []
    for name, count in counts.items():
        for _ in range(count):
            if not nicks:
                nicks = NICKS[:]
                rng.shuffle(nicks)
            fish = Fish(
                species=name, x=0.0, y=1.0, dx=rng.choice((1, -1)),
                speed=rng.uniform(*SPECIES[name].speed),
                color=rng.randint(1, COLORS), nick=nicks.pop(),
            )
            max_x, max_y = _bounds(fish, width, height)
            fish.x = rng.uniform(0, max_x)
            fish.y = float(rng.randint(1, max_y))
            result.append(fish)
    return result


def step_fish(fish, width, height, dt, food):
    """Двигает рыбу; возвращает True, если она только что вернулась после испуга."""
    max_x, max_y = _bounds(fish, width, height)
    if fish.mood == "flee":
        # удирает за край экрана и ждёт там
        fish.x += fish.dx * FLEE_SPEED * dt
        # прячется целиком, вместе с ником, который бывает шире рыбы
        hide = fish_width(fish) + len(fish.nick) + 2.0
        fish.x = max(-hide, min(width + hide, fish.x))
        fish.y = max(1.0, min(float(max_y), fish.y))
        return False
    if fish.mood == "return":
        if 0 <= fish.x <= max_x:
            fish.mood = ""
            return True
        fish.dx = -1 if fish.x > max_x else 1
        step = max(fish.speed * RETURN_SPEED_FACTOR, MIN_RETURN_SPEED) * dt
        fish.x = min(fish.x + step, 0.0) if fish.dx > 0 else max(fish.x - step, float(max_x))
        fish.y = max(1.0, min(float(max_y), fish.y))
        return False
    if food is not None and abs(food[0] - fish.x) <= FOOD_RADIUS:
        fish.dx = 1 if food[0] >= fish.x else -1
        step = fish.speed * dt
        fish.x += max(-step, min(step, food[0] - fish.x))
        fish.y += max(-step, min(step, food[1] - fish.y))
    else:
        fish.x += fish.dx * fish.speed * dt
    if fish.x >= max_x:
        fish.x, fish.dx = max_x, -1
    elif fish.x <= 0:
        fish.x, fish.dx = 0.0, 1
    fish.y = max(1.0, min(float(max_y), fish.y))
    return False


# --- экран выбора ---------------------------------------------------------

@dataclass
class PickerState:
    counts: dict
    cursor: int = 0


def picker_handle_key(state, key, rng):
    """Меняет состояние; возвращает "start", "quit" или None."""
    names = list(SPECIES)
    name = names[state.cursor]
    if key == "up":
        state.cursor = (state.cursor - 1) % len(names)
    elif key == "down":
        state.cursor = (state.cursor + 1) % len(names)
    elif key == "right":
        state.counts[name] = min(MAX_PER_SPECIES, state.counts[name] + 1)
    elif key == "left":
        state.counts[name] = max(0, state.counts[name] - 1)
    elif key == "space":
        state.counts[name] = 0 if state.counts[name] else 1
    elif key == "r":
        for n in names:
            state.counts[n] = rng.randint(0, 5)
        if sum(state.counts.values()) == 0:
            state.counts[rng.choice(names)] = 1
    elif key == "enter":
        return "start" if sum(state.counts.values()) > 0 else None
    elif key == "q":
        return "quit"
    return None


def safe_addstr(win, y, x, text, attr=0):
    """addstr, не падающий на выходе за границы окна."""
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


_KEYS = {
    curses.KEY_UP: "up", curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left", curses.KEY_RIGHT: "right",
    ord(" "): "space", 10: "enter", 13: "enter", curses.KEY_ENTER: "enter",
    ord("q"): "q", ord("Q"): "q", ord("r"): "r", ord("R"): "r",
}


def draw_picker(stdscr, state):
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    box_w = 39
    left = max(0, (width - box_w) // 2)
    top = max(0, (height - (len(SPECIES) + 9)) // 2)
    inner = box_w - 2

    def row(i, text, attr=0):
        safe_addstr(stdscr, top + i, left, "│" + text.ljust(inner)[:inner] + "│", attr)

    safe_addstr(stdscr, top, left, "┌─ АКВАРИУМ " + "─" * (inner - 11) + "┐")
    row(1, "")
    row(2, "  Выбери рыб (пробел — вкл/выкл)")
    row(3, "")
    for i, (name, count) in enumerate(state.counts.items()):
        mark = "x" if count else " "
        pointer = "▶" if i == state.cursor else " "
        art = SPECIES[name].icon
        attr = curses.A_BOLD if i == state.cursor else 0
        row(4 + i, f" {pointer} [{mark}] {art:<11} {name:<9} × {count}", attr)
    n = 4 + len(SPECIES)
    row(n, "")
    row(n + 1, "  ←/→ количество   ↑/↓ выбор")
    row(n + 2, "  r — случайный набор   q — выход")
    row(n + 3, "")
    row(n + 4, "      [  ENTER — СТАРТ  ]", curses.A_REVERSE)
    safe_addstr(stdscr, top + n + 5, left, "└" + "─" * inner + "┘")
    stdscr.refresh()


def run_picker(stdscr, initial):
    """Показывает выбор; возвращает {вид: количество} или None при выходе."""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(-1)
    counts = {name: initial.get(name, 0) for name in SPECIES}
    state = PickerState(counts=counts)
    rng = random.Random()
    while True:
        draw_picker(stdscr, state)
        code = stdscr.getch()
        key = _KEYS.get(code)
        if code == curses.KEY_RESIZE or key is None:
            continue
        action = picker_handle_key(state, key, rng)
        if action == "start":
            return dict(state.counts)
        if action == "quit":
            return None


# --- экран аквариума ------------------------------------------------------

MIN_WIDTH = 50
MIN_HEIGHT = 16
FOOD_FALL = 4.0
HELP = "q — выход · f — покормить · t — болтать · p — пауза · c — выбор рыб"
MAX_BUBBLES = 40
BUBBLE_RISE = 3.0
BUBBLE_RATE = 0.15  # пузырьков в секунду на одну рыбу
EYES = "o°@"
ACCENT_PAIR = 7
PALETTE = [curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW,
           curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN]


def relayout_fish(fish_list, old_width, new_width, height, rng):
    """При смене размера окна растягивает x и заново раскидывает рыб по рядам."""
    for fish in fish_list:
        max_x, max_y = _bounds(fish, new_width, height)
        fish.x = min(float(max_x), fish.x * new_width / max(1, old_width))
        fish.y = float(rng.randint(1, max_y))


def accent_positions(fish):
    """Клетки (ряд, столбец) рисунка рыбы, которые рисуются ярче: глаза."""
    return [(r, c) for r, line in enumerate(fish_lines(fish))
            for c, ch in enumerate(line) if ch in EYES]


def bubble_step(bubbles, fish_list, dt, rng):
    """Поднимает пузырьки к поверхности и иногда выпускает новые у морды рыб."""
    for bubble in bubbles:
        bubble[1] -= BUBBLE_RISE * dt
    bubbles[:] = [b for b in bubbles if b[1] >= 1]
    for fish in fish_list:
        if len(bubbles) < MAX_BUBBLES and rng.random() < BUBBLE_RATE * dt:
            head = fish.x + (fish_width(fish) - 1 if fish.dx > 0 else 0)
            bubbles.append([head, fish.y])


def tank_too_small(width, height):
    return width < MIN_WIDTH or height < MIN_HEIGHT


def feed_step(foods, fish_list, height, dt):
    """Роняет корм и убирает съеденный или упавший на дно; возвращает съевших."""
    eaters = []
    kept = []
    for food in foods:
        food[1] += FOOD_FALL * dt
        if food[1] >= height - 3:
            continue
        eater = next((fish for fish in fish_list if _touches(fish, food)), None)
        if eater is None:
            kept.append(food)
        elif eater not in eaters:
            eaters.append(eater)
    foods[:] = kept
    return eaters


def nearest_fish(fish_list, x):
    """Рыба, ближайшая к точке x в радиусе корма, или None."""
    near = [f for f in fish_list if abs(f.x - x) <= FOOD_RADIUS]
    return min(near, key=lambda f: abs(f.x - x)) if near else None


SPEECH_TTL = 4.0
MAX_SPEAKERS = 3
SPEECH_RATE = 0.2  # реплик в секунду на весь аквариум
LORE_EVENTS = ("idle", "poke")


def pick_phrase(fish, event, rng):
    """Случайная фраза под событие; фразы вида и ника выпадают чаще общих."""
    pool = list(PHRASES.get(event, []))
    lore = list(SPECIES_PHRASES.get(fish.species, {}).get(event, []))
    if event in LORE_EVENTS:
        lore += NICK_PHRASES.get(fish.nick, [])
    pool += lore * 2
    return rng.choice(pool) if pool else ""


def say(fish, event, rng):
    fish.speech = pick_phrase(fish, event, rng)
    fish.speech_ttl = SPEECH_TTL if fish.speech else 0.0


def speech_step(fish_list, dt, rng):
    """Гасит истёкшие реплики и иногда даёт молчащей рыбе что-то сказать."""
    for fish in fish_list:
        if fish.speech:
            fish.speech_ttl -= dt
            if fish.speech_ttl <= 0:
                fish.speech, fish.speech_ttl = "", 0.0
    speakers = sum(1 for f in fish_list if f.speech)
    silent = [f for f in fish_list if not f.speech]
    if silent and speakers < MAX_SPEAKERS and rng.random() < SPEECH_RATE * dt:
        say(rng.choice(silent), "idle", rng)


def speech_layout(fish, width):
    """(ряд, столбец, текст, соединитель) облачка; соединитель — (ряд, столбец) или None."""
    text = f"( {fish.speech} )"[:max(0, width - 1)]
    lines = fish_lines(fish)
    x, y = int(fish.x), int(fish.y)
    raw_head = x + (fish_width(fish) - 1 if fish.dx > 0 else 0)
    head = max(0, min(width - 2, raw_head))
    col = max(0, min(width - len(text) - 1, head - len(text) // 2))
    if y >= 3:
        # голова за краем экрана — облачко прижато к краю, без соединителя
        connector = (y - 1, head) if head == raw_head else None
        return y - 2, col, text, connector
    if y == 2:
        return 1, col, text, None
    return y + len(lines) + 1, col, text, None


# --- пасхалка: x пять раз подряд — шквал хуёв ---------------------------

EGG_PRESSES = 5
EGG_GAP = 1.5          # максимум секунд между нажатиями x
SPEED_RANGE = {        # клеток в секунду; рыбы удирают быстрее (FLEE_SPEED)
    "big": (22.0, 30.0), "medium": (28.0, 36.0), "small": (34.0, 42.0),
}
SWARM_SIZE = {"big": (1, 2), "medium": (2, 4), "small": (6, 12)}
SWARM_SPREAD = 4.0     # за сколько секунд выплывает вся волна
SCARE_RADIUS = 25      # насколько заранее рыбы замечают хуй впереди
PANIC_CHANCE = 0.4
HOME_CHANCE = 0.5
MONSTER_PAIRS = (5, 1, 3)  # пурпурный, красный, жёлтый
RIDER_PAIR = 6             # голубой: казак не сливается с конём
STORM_BANNER = " !!! ШТОРМОВОЕ ПРЕДУПРЕЖДЕНИЕ: ВАЙБ-КАЗАКИ НА ХУЯХ !!! "

# --- наездники: казаки-вайбкодеры -----------------------------------------
# Папаха, наушники d( )b, шашка в правой руке; три кадра взмаха.
RIDER_FRAMES = [
    [  # шашка вверх
        "  .###.    /",
        " d(o_o)b  / ",
        "  /|#|\\=-/  ",
        "   /  \\     ",
    ],
    [  # шашка вперёд
        "  .###.      ",
        " d(o_o)b     ",
        "  /|#|\\=---=>",
        "   /  \\      ",
    ],
    [  # рубит вниз
        "  .###.     ",
        " d(o_o)b    ",
        "  /|#|\\=-.  ",
        "   /  \\   \\ ",
    ],
]
TINY_RIDER_FRAMES = [[" o/", "<|"], [" o-", "<|"], [" o\\", "<|"]]
RIDER_SEAT = {"big": 0.45, "medium": 0.35, "small": 0.3}  # доля длины хуя
SWING_TICKS = 3        # кадров анимации на одно положение шашки
RIDER_CRIES = [
    "ЗА ВАЙБ-КОД И ДВОР!", "Я СТРЕЛЯЮ В УПОР!", "ШАШКИ НАГОЛО, БРАТЦЫ!",
    "ЛЮБО, БРАТЦЫ, ЛЮБО!", "ПРОМПТ, ВПЕРЁД!", "КОД НЕ ЧИТАЮ — РУБЛЮ!",
    "НЕЙРОНКА, В АТАКУ!", "ТЕСТЫ? ПОРУБИМ!", "ЗА СТАНИЦУ И ПРОД!",
    "ACCEPT ALL, БРАТЦЫ!", "КОНЬ МОЙ — ХУЙ ГНЕДОЙ!", "ЭХ, РАЗЛЮЛИ, ДЕПЛОЙ!",
    "РУБИ ЛЕГАСИ!", "ГОП-ГОП, В ПРОДАКШН!", "ВАЙБУ — ДА, РЕВЬЮ — НЕТ!",
    "КТО С НАМИ — ТОТ В ПРОДЕ!", "ОЙ, ТО НЕ ВЕЧЕР, ТО ДЕПЛОЙ", "ЗА ТОКЕНЫ, БРАТЦЫ!",
    "КОНТЕКСТ КОНЧИЛСЯ — РУБИ!", "ЭТО НЕ БАГ, ЭТО ШАШКА!", "СОСИТЕ, РЫБКИ!",
    "это не акула, это хуже", "мы пришли с пацанами", "это DDoS, детка",
    "масштабируемся горизонтально", "нас тут целый кластер", "релиз-трейн, ту-ту!",
    "без ревью, как обычно", "размер имеет значение",
]
TINY_CRIES = ["ЛЮБО!", "УРА!", "ГОП!", "ВАЙБ!", "ЭХ!", "РУБИ!", "ПИУ!", "ЙЕХУ!"]
SHOUT_TIME = (1.8, 2.8)   # сколько висит крик
QUIET_TIME = (0.4, 1.4)   # пауза между криками


def _rider_frames(kind):
    return TINY_RIDER_FRAMES if kind == "small" else RIDER_FRAMES


def _rider_height(kind):
    return len(_rider_frames(kind)[0])


def _rider_width(kind):
    return max(len(line) for frame in _rider_frames(kind) for line in frame)


def rider_layout(monster, tick):
    """(верхний ряд, столбец, строки) казака на хую в этом кадре."""
    frames = _rider_frames(monster.kind)
    lines = frames[(tick // SWING_TICKS + monster.phase) % len(frames)]
    if monster.dx < 0:
        lines = _mirror([line.ljust(_rider_width(monster.kind)) for line in lines])
    # ноги на стволе: у многострочных — на верхнем ряду рисунка, у мелкого — над ним
    bottom = monster.y if len(monster.lines) > 1 else monster.y - 1
    return bottom - len(lines) + 1, int(monster.x) + monster.rider_x, lines


def rider_step(monsters, dt, rng):
    """Казаки на сцене орут по очереди: крик, пауза, новый крик."""
    for m in monsters:
        if m.delay > 0:
            continue
        m.shout_ttl -= dt
        if m.shout_ttl > 0:
            continue
        if m.speech:
            m.speech, m.shout_ttl = "", rng.uniform(*QUIET_TIME)
        else:
            m.speech = rng.choice(TINY_CRIES if m.kind == "small" else RIDER_CRIES)
            m.shout_ttl = rng.uniform(*SHOUT_TIME)


def dick_art(shaft):
    """Большой хуй (9 строк), смотрит вправо, ствол длиной shaft."""
    veins = ("  ~~   ~    ~~~  ~   " * (shaft // 20 + 1))[:shaft]
    return [
        "   .-\"\"\"-.",
        "  /   '   \\" + "_" * (shaft + 1) + ".---\"\"\"---.",
        " |  ,   '  |" + " " * shaft + "|           `.",
        " |   '  ,  |" + veins + "|          -  )",
        "  \\  '    / " + " " * shaft + "|           ,'",
        "  /  ,  ' \\" + "_" * (shaft + 1) + "`---...---'",
        " |  '   ,  |",
        "  \\   ,   /",
        "   `-...-'",
    ]


def dick_art_medium(shaft):
    """Средний хуй (5 строк), смотрит вправо."""
    return [
        "  .-.",
        " (   )" + "_" * shaft + ".--.",
        "  ) (" + "~ " * (shaft // 2) + " " * (shaft % 2) + " |   `.",
        " (   )" + "_" * shaft + "|  - )",
        "  `-'" + " " * (shaft + 1) + "`--'",
    ]


def dick_art_small(shaft):
    """Мелкий хуй в одну строку."""
    return ["8" + "=" * shaft + "D"]


@dataclass
class Monster:
    x: float
    y: int
    dx: int
    lines: list
    speech: str
    speed: float = 22.0
    delay: float = 0.0      # секунд до выхода на сцену
    color: int = MONSTER_PAIRS[0]
    kind: str = "big"
    muzzle: int = 0         # ряд рисунка, из которого он стреляет
    cooldown: float = 0.0   # секунд до следующего выстрела
    rider_x: int = 0        # где сидит казак, от левого края рисунка
    phase: int = 0          # сдвиг взмаха шашки, чтобы махали вразнобой
    shout_ttl: float = 0.0  # секунд до смены крика (или паузы)


def monster_width(monster):
    return max(len(line) for line in monster.lines)


def register_x(count, last, code, now):
    """Считает x подряд; возвращает (count, last, сработало ли)."""
    if code in (ord("x"), ord("X")):
        count = count + 1 if now - last <= EGG_GAP else 1
        if count >= EGG_PRESSES:
            return 0, now, True
        return count, now, False
    if code != -1:
        return 0, last, False
    return count, last, False


def _art(kind, width, rng):
    if kind == "big":
        return dick_art(rng.randint(max(12, width // 4), max(20, width // 2)))
    if kind == "medium":
        return dick_art_medium(rng.randint(10, max(12, width // 4)))
    return dick_art_small(rng.randint(3, 12))


def spawn_monster(width, height, rng, kind="big", dx=None, delay=0.0):
    """Хуй за краем экрана; плывёт через весь аквариум."""
    dx = dx or rng.choice((1, -1))
    art = _art(kind, width, rng)
    lines = art if dx > 0 else _mirror(art)
    w = max(len(line) for line in lines)
    # сверху место под наездника и его крик, снизу — водоросли
    top = _rider_height(kind) + (1 if kind != "small" else 2)
    bottom = height - 4 - len(lines)
    if bottom < top:
        y = top
    elif kind == "big":
        y = (top + bottom) // 2
    else:
        y = rng.randint(top, bottom)
    x = float(-w) if dx > 0 else float(width)
    color = MONSTER_PAIRS[0] if kind == "big" else rng.choice(MONSTER_PAIRS)
    # ствол — самый длинный ряд рисунка (последний из равных: там кончик)
    widths = [len(line) for line in art]
    muzzle = max(i for i, n in enumerate(widths) if n == max(widths))
    cooldown = rng.uniform(0.0, FIRE_RATE[kind][1])
    # наездник сидит на стволе ближе к середине
    rider_w = _rider_width(kind)
    seat = int(max(widths) * RIDER_SEAT[kind])
    rider_x = seat if dx > 0 else w - seat - rider_w
    return Monster(x, y, dx, lines, "", rng.uniform(*SPEED_RANGE[kind]), delay, color,
                   kind, muzzle, cooldown, rider_x, rng.randrange(3), rng.uniform(0.0, 1.0))


def spawn_swarm(width, height, rng):
    """Волна хуёв разного калибра с одной стороны, выходят вразнобой."""
    dx = rng.choice((1, -1))
    swarm = []
    for kind, (lo, hi) in SWARM_SIZE.items():
        for _ in range(rng.randint(lo, hi)):
            delay = rng.uniform(0.0, SWARM_SPREAD)
            swarm.append(spawn_monster(width, height, rng, kind, dx, delay))
    # первым всегда идёт большой
    swarm[0].delay = 0.0
    return swarm


def monster_step(monster, fish_list, width, dt, rng):
    """Двигает один хуй и пугает рыб впереди; возвращает False, когда он уплыл."""
    if monster.delay > 0:
        monster.delay -= dt
        return True
    step = monster.speed * dt
    monster.x += monster.dx * step
    w = monster_width(monster)
    front = monster.x + w if monster.dx > 0 else monster.x
    for fish in fish_list:
        if fish.mood == "flee":
            continue
        center = fish.x + fish_width(fish) / 2
        ahead = (center - front) * monster.dx
        # учитываем и пройденный за кадр путь: мелкий хуй короткий и быстрый
        if -w - step <= ahead <= SCARE_RADIUS:
            fish.mood, fish.dx = "flee", monster.dx
            if rng.random() < PANIC_CHANCE:
                say(fish, "panic", rng)
    return not (monster.x > width if monster.dx > 0 else monster.x + w < 0)


def swarm_step(monsters, fish_list, width, dt, rng):
    """Двигает всю волну; когда уплыл последний, рыбы плывут домой."""
    monsters[:] = [m for m in monsters if monster_step(m, fish_list, width, dt, rng)]
    if not monsters:
        for fish in fish_list:
            if fish.mood == "flee":
                fish.mood = "return"
                fish.dx = -fish.dx
    return bool(monsters)


# --- пиу-пиу: хуи стреляют ------------------------------------------------

FIRE_RATE = {"big": (0.5, 0.9), "medium": (0.9, 1.5), "small": (1.4, 2.4)}  # пауза, с
SHOT_SPEED = 40.0      # прибавка к скорости хуя: капля летит быстрее рыб
MAX_SHOTS = 60
SHOT_RIGHT, SHOT_LEFT = "~~o", "o~~"
FLASH_TTL = 0.3
SPLAT_TTL = 0.8
HIT_CHANCE = 0.7       # как часто подбитая рыба орёт
FLASHES = ["пиу!", "пиу-пиу!", "пыщ!", "ПИУ!"]
SPLATS = ["*шлёп*", "*хлюп*", "*ПЛЮХ*", "*чвяк*"]


@dataclass
class Shot:
    x: float
    y: int
    dx: int
    speed: float

    @property
    def text(self):
        return SHOT_RIGHT if self.dx > 0 else SHOT_LEFT

    @property
    def head(self):
        """Столбец головки капли: она летит головкой вперёд."""
        return int(self.x) + (len(self.text) - 1 if self.dx > 0 else 0)


def fire_step(monsters, shots, effects, width, dt, rng):
    """Хуи на сцене иногда стреляют вперёд; у ствола вспыхивает «пиу!»."""
    for m in monsters:
        if m.delay > 0:
            continue
        m.cooldown -= dt
        if m.cooldown > 0:
            continue
        m.cooldown = rng.uniform(*FIRE_RATE[m.kind])
        tip = m.x + monster_width(m) if m.dx > 0 else m.x - len(SHOT_RIGHT)
        if not 0 <= tip < width or len(shots) >= MAX_SHOTS:
            continue  # ствол ещё за кадром — патроны не тратим
        row = m.y + m.muzzle
        shots.append(Shot(tip, row, m.dx, m.speed + SHOT_SPEED))
        flash = rng.choice(FLASHES)
        effects.append([tip if m.dx > 0 else tip - len(flash) + 3, row - 1, flash, FLASH_TTL])


def shot_step(shots, effects, fish_list, width, dt, rng):
    """Капли летят; попавшая в рыбу оставляет «*шлёп*», рыба орёт."""
    kept = []
    for shot in shots:
        shot.x += shot.dx * shot.speed * dt
        if not -len(shot.text) <= shot.x <= width:
            continue
        victim = next((f for f in fish_list if _hit(f, shot.head, shot.y)), None)
        if victim is None:
            kept.append(shot)
            continue
        effects.append([shot.head - 3, shot.y, rng.choice(SPLATS), SPLAT_TTL])
        if rng.random() < HIT_CHANCE:
            say(victim, "hit", rng)
    shots[:] = kept


def _hit(fish, x, y):
    top = int(fish.y)
    return (int(fish.x) <= x < int(fish.x) + fish_width(fish)
            and top <= y < top + len(fish_lines(fish)))


def effect_step(effects, dt):
    """Гасит вспышки и брызги."""
    for effect in effects:
        effect[3] -= dt
    effects[:] = [e for e in effects if e[3] > 0]


def _draw_sprite(win, y, x, lines, width, attr):
    """Рисует картинку; пробелы по краям строк прозрачные, чтобы не стирать соседей."""
    for i, line in enumerate(lines):
        body = line.strip()
        if body:
            lead = len(line) - len(line.lstrip())
            clip_addstr(win, y + i, x + lead, body, width, attr)


def clip_addstr(win, y, x, text, width, attr=0):
    """addstr с обрезкой слева и справа: для того, что заплыло за край экрана."""
    if x < 0:
        text, x = text[-x:], 0
    text = text[:max(0, width - 1 - x)]
    if text:
        safe_addstr(win, y, x, text, attr)


def _touches(fish, food):
    rows = len(fish_lines(fish))
    return (fish.x <= food[0] < fish.x + fish_width(fish)
            and round(fish.y) <= round(food[1]) < round(fish.y) + rows)


def _nearest_food(fish, foods):
    near = [f for f in foods if abs(f[0] - fish.x) <= FOOD_RADIUS]
    if not near:
        return None
    best = min(near, key=lambda f: abs(f[0] - fish.x) + abs(f[1] - fish.y))
    return best[0], best[1]


def _init_colors():
    if not (curses.has_colors() and curses.COLORS >= 8):
        return False
    curses.start_color()
    curses.use_default_colors()
    for i, color in enumerate(PALETTE, start=1):
        curses.init_pair(i, color, -1)
    curses.init_pair(ACCENT_PAIR, curses.COLOR_WHITE, -1)
    return True


def draw_aquarium(stdscr, fish_list, foods, bubbles, colors, tick, paused, monsters=(),
                  shots=(), effects=()):
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    safe_addstr(stdscr, 0, 0, ("^^^^ " * (width // 5 + 1))[:width - 1])
    for fish in fish_list:
        attr = curses.color_pair(fish.color) if colors else 0
        x, y = int(fish.x), int(fish.y)
        lines = fish_lines(fish)
        for i, line in enumerate(lines):
            clip_addstr(stdscr, y + i, x, line, width, attr)
        eye = (curses.color_pair(ACCENT_PAIR) if colors else 0) | curses.A_BOLD
        for row, col in accent_positions(fish):
            if 0 <= x + col < width - 1:
                safe_addstr(stdscr, y + row, x + col, lines[row][col], eye)
        nick_x = x + (fish_width(fish) - len(fish.nick)) // 2
        if x >= 0:
            nick_x = max(0, nick_x)  # пока рыба на экране, ник не режется слева
        clip_addstr(stdscr, y + len(lines), nick_x, fish.nick, width, attr)
    # капли и вспышки под хуями: кто стреляет из-за большого, того не видно
    white = (curses.color_pair(ACCENT_PAIR) if colors else 0) | curses.A_BOLD
    for shot in shots:
        clip_addstr(stdscr, shot.y, int(shot.x), shot.text, width, white)
    for ex, ey, text, _ in effects:
        clip_addstr(stdscr, ey, int(ex), text, width, white)
    # мелкие снизу, большие поверх
    for monster in sorted(monsters, key=lambda m: len(m.lines)):
        if monster.delay > 0:
            continue
        attr = (curses.color_pair(monster.color) if colors else 0) | curses.A_BOLD
        _draw_sprite(stdscr, monster.y, int(monster.x), monster.lines, width, attr)
        rider_attr = (curses.color_pair(RIDER_PAIR) if colors else 0) | curses.A_BOLD
        top, col, lines = rider_layout(monster, tick)
        _draw_sprite(stdscr, top, col, lines, width, rider_attr)
        if monster.speech:
            text = f"( {monster.speech} )"
            center = col + len(lines[0]) // 2
            clip_addstr(stdscr, top - 1, center - len(text) // 2, text, width, rider_attr)
    if monsters and (tick // 6) % 2 == 0:
        banner = STORM_BANNER[:max(0, width - 1)]
        attr = (curses.color_pair(1) if colors else 0) | curses.A_BOLD | curses.A_REVERSE
        safe_addstr(stdscr, 0, max(0, (width - len(banner)) // 2), banner, attr)
    for bx, by in bubbles:
        safe_addstr(stdscr, int(by), int(bx), "°" if int(by) % 2 else "o")
    for food in foods:
        safe_addstr(stdscr, int(food[1]), int(food[0]), "*")
    for fish in fish_list:
        if not fish.speech:
            continue
        attr = (curses.color_pair(fish.color) if colors else 0) | curses.A_BOLD
        row, col, text, connector = speech_layout(fish, width)
        safe_addstr(stdscr, row, col, text, attr)
        if connector:
            safe_addstr(stdscr, connector[0], connector[1], "o", attr)
    green = curses.color_pair(2) if colors else 0
    for x in range(1, width - 1, 7):
        for row in (height - 3, height - 2):
            sway = (tick // 8 + x + row) % 2
            safe_addstr(stdscr, row, x, "}" if sway else "{", green)
    status = HELP + ("  [пауза]" if paused else "")
    safe_addstr(stdscr, height - 1, 0, status[:width - 1])
    stdscr.refresh()


def run_aquarium(stdscr, counts):
    """Крутит аквариум; возвращает "quit" или "setup" (клавиша c)."""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)
    colors = _init_colors()
    rng = random.Random()
    height, width = stdscr.getmaxyx()
    size = (width, height)
    fish_list = spawn_fish(counts, width, height, rng)
    foods = []
    bubbles = []
    paused = False
    tick = 0
    monsters = []
    shots = []
    effects = []
    x_count, x_last = 0, 0.0
    last = time.monotonic()
    while True:
        now = time.monotonic()
        dt = min(now - last, 0.2)
        last = now
        height, width = stdscr.getmaxyx()
        if (width, height) != size:
            relayout_fish(fish_list, size[0], width, height, rng)
            size = (width, height)
        code = stdscr.getch()
        if code in (ord("q"), ord("Q")):
            return "quit"
        if code in (ord("c"), ord("C")):
            return "setup"
        if code in (ord("p"), ord("P")):
            paused = not paused
        if code in (ord("f"), ord("F")) and not tank_too_small(width, height):
            foods.append([float(rng.randint(0, width - 2)), 1.0])
            seer = nearest_fish(fish_list, foods[-1][0])
            if seer is not None:
                say(seer, "food_seen", rng)
        if code in (ord("t"), ord("T")) and fish_list:
            say(rng.choice(fish_list), "poke", rng)
        x_count, x_last, egg = register_x(x_count, x_last, code, now)
        if egg and not monsters and not tank_too_small(width, height):
            monsters = spawn_swarm(width, height, rng)
        if tank_too_small(width, height):
            stdscr.erase()
            msg = "окно слишком маленькое"
            safe_addstr(stdscr, height // 2, max(0, (width - len(msg)) // 2),
                        msg[:max(0, width - 1)])
            stdscr.refresh()
            continue
        if not paused:
            tick += 1
            if monsters:
                swarm_step(monsters, fish_list, width, dt, rng)
                fire_step(monsters, shots, effects, width, dt, rng)
                rider_step(monsters, dt, rng)
            shot_step(shots, effects, fish_list, width, dt, rng)
            effect_step(effects, dt)
            for fish in fish_list:
                food = None if fish.mood else _nearest_food(fish, foods)
                if step_fish(fish, width, height, dt, food) and rng.random() < HOME_CHANCE:
                    say(fish, "home", rng)
            for eater in feed_step(foods, fish_list, height, dt):
                say(eater, "food_eaten", rng)
            speech_step(fish_list, dt, rng)
            bubble_step(bubbles, fish_list, dt, rng)
        else:
            for fish in fish_list:
                step_fish(fish, width, height, 0.0, None)
        draw_aquarium(stdscr, fish_list, foods, bubbles, colors, tick, paused, monsters,
                      shots, effects)


# --- точка входа ----------------------------------------------------------

def choose_start(config, setup_flag):
    return "picker" if config is None or setup_flag else "aquarium"


def main(argv):
    if not sys.stdout.isatty():
        return 0
    path = config_path()
    counts = load_config(path, list(SPECIES))
    stage = choose_start(counts, "--setup" in argv)
    try:
        while True:
            if stage == "picker":
                picked = curses.wrapper(run_picker, counts or {})
                if picked is None:
                    return 0
                counts = picked
                save_config(path, counts)
            if curses.wrapper(run_aquarium, counts) != "setup":
                return 0
            stage = "picker"
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
