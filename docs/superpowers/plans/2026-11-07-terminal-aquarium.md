# Terminal Aquarium Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Один Python-скрипт `aquarium`: при первом запуске экран выбора рыб, затем анимированный ASCII-аквариум с рыбами, у каждой цвет и смешной ник.

**Architecture:** Один файл `aquarium.py` с чистой логикой (конфиг, ники, модель рыбы и её движение, состояние экрана выбора), отделённой от тонкого слоя `curses` (отрисовка и ввод). Логика тестируется `unittest` без терминала, `curses`-слой проверяется вручную. Точка входа `main(argv)` решает: показать выбор или сразу аквариум.

**Tech Stack:** Python 3 (стандартная библиотека: `curses`, `json`, `random`, `unittest`), fish `fish_greeting`.

**Spec:** `docs/superpowers/specs/2026-11-07-terminal-aquarium-design.md`

## Global Constraints

- Python 3, только стандартная библиотека, без внешних зависимостей.
- Один исполняемый скрипт `aquarium` (в репозитории `aquarium.py` с shebang `#!/usr/bin/env python3`, ставится как `~/.local/bin/aquarium`).
- Конфиг: `~/.config/aquarium/config.json`. Нет файла, битый файл, неизвестный вид или сумма рыб 0 означает показ экрана выбора.
- Не более 20 рыб на вид.
- Окно меньше 40×12: вместо аквариума сообщение «окно слишком маленькое», рыбы не рисуются.
- Терминал с меньше чем 8 цветами: рисовать без цвета; ник берёт цвет своей рыбы.
- Клавиши экрана выбора: `↑/↓` вид, `←/→` количество, пробел вкл/выкл вида, `r` случайный набор, `Enter` старт, `q` выход без сохранения.
- Клавиши аквариума: `q` выход, `f` кормить, `p` пауза, `c` вернуться к выбору. Флаг `--setup` открывает выбор принудительно.
- Аквариум не закрывается сам. Терминал всегда восстанавливается при выходе, Ctrl+C и изменении размера.
- Хук в `fish_greeting` описывается только в README, команды `--install` нет.
- Не рисуем ничего, если stdout не tty (скрипт молча выходит с кодом 0).

## Review Focus

- Окно уменьшили, пока рыбы плывут: рыбы за новой границей не должны вызывать `curses.error`, их позиции зажимаются в новые размеры.
- Конфиг с количеством больше 20, отрицательным или нецелым: значения зажимаются в 0…20, нецелое считается битым конфигом.
- Рыб больше, чем ников в списке: ники могут повторяться, программа не падает.
- Ctrl+C и исключение внутри цикла: терминал восстановлен (`curses.wrapper`), без трейсбека на экране при Ctrl+C.
- Каталог конфига не создаётся или не записывается (нет прав): сохранение молча пропускается, аквариум всё равно запускается.

---

## File Structure

- `aquarium.py`: вся логика и `curses`-слой, ~300–400 строк. Разделы внутри файла: данные (виды, ники), конфиг, модель рыбы, состояние выбора, UI выбора, UI аквариума, `main`.
- `tests/test_aquarium.py`: тесты чистой логики.
- `README.md`: установка и хук `fish_greeting`.

### Task 1: Конфигурация

**Files:**
- Create: `aquarium.py`, `tests/test_aquarium.py`

**Interfaces:**
- Produces: `MAX_PER_SPECIES = 20`; `config_path() -> pathlib.Path`; `load_config(path: Path, species: list[str]) -> dict[str, int] | None` (`None` для отсутствующего или битого конфига, неизвестного вида, нецелого значения, суммы 0; значения зажимаются в 0…20); `save_config(path: Path, counts: dict[str, int]) -> bool` (создаёт каталог, `False` вместо исключения при ошибке записи).

- [ ] **Step 1: `git init` в корне проекта, создать пустые `aquarium.py` и `tests/test_aquarium.py`, добавить `.superpowers/` в `.gitignore`**

- [ ] **Step 2: Write failing tests** в `tests/test_aquarium.py` (`unittest`, `tempfile`): `test_load_missing_returns_none`, `test_load_corrupt_json_returns_none`, `test_load_unknown_species_returns_none`, `test_load_zero_total_returns_none`, `test_load_non_int_returns_none` (значение `"3"` и `2.5`), `test_load_clamps_to_0_20` (`{"a": 99, "b": -4, "c": 2}` даёт `{"a": 20, "b": 0, "c": 2}`), `test_save_then_load_roundtrip`, `test_save_unwritable_returns_false` (путь внутри файла, а не каталога).

- [ ] **Step 3: Run:** `python3 -m unittest tests.test_aquarium -v`. Expected: FAIL (функции не определены).

- [ ] **Step 4: Implement** `config_path`, `load_config`, `save_config` по подписям выше (`json`, `pathlib`, `OSError` ловится).

- [ ] **Step 5: Run тесты.** Expected: PASS.

- [ ] **Step 6: Commit** `feat: config load/save with validation`.

### Task 2: Виды, ники, модель рыбы

**Files:**
- Modify: `aquarium.py`, `tests/test_aquarium.py`

**Interfaces:**
- Consumes: `MAX_PER_SPECIES` из Task 1.
- Produces:
  - `SPECIES: dict[str, Species]` с упорядоченными ключами; `Species` — `NamedTuple(name: str, right: list[str], left: list[str], speed: tuple[float, float])` (`right`/`left` — строки ASCII-рисунка вправо/влево, у медузы может быть несколько строк). Шесть видов: Рыбка, Рыба-меч, Окунь, Акула, Кит, Медуза.
  - `NICKS: list[str]` — не меньше 40 смешных русских и английских ников в IT-духе.
  - `Fish` — dataclass: `species: str`, `x: float`, `y: float`, `dx: int` (+1 или −1), `speed: float`, `color: int` (индекс 1…6), `nick: str`.
  - `spawn_fish(counts: dict[str, int], width: int, height: int, rng: random.Random) -> list[Fish]` (ники берутся из перемешанной копии `NICKS`, при нехватке цикл по кругу; `y` в пределах между поверхностью и дном).
  - `step_fish(fish: Fish, width: int, height: int, dt: float, food: tuple[float, float] | None) -> None` (двигает по `x`, у границы разворачивает `dx`; если `food` задан и в радиусе 15 клеток по `x`, плывёт к нему по обеим осям; позиция всегда зажата в `[0, width - ширина рисунка]` и `[1, height - 3]`).
  - `fish_width(fish: Fish) -> int`, `fish_lines(fish: Fish) -> list[str]`.

- [ ] **Step 1: Write failing tests:** `test_spawn_counts_match` (`{"Рыбка": 3, "Акула": 1}` даёт 4 рыбы с нужными видами), `test_spawn_more_fish_than_nicks_does_not_crash` (100 рыб при списке из `NICKS`, ники повторяются), `test_nicks_have_at_least_40`, `test_spawn_positions_inside_tank`, `test_step_turns_at_right_edge` (рыба у правой границы с `dx=1` после шага имеет `dx=-1`), `test_step_clamps_after_shrink` (рыба с `x=200` после `step_fish` при `width=60` внутри границ), `test_step_moves_toward_food` (рыба левее корма в радиусе 15 приближается по `x`).

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** по подписям. Рисунки и ники на ваше усмотрение, но ники из примеров спека (`segfault_петя`, `NullPointer_Вася`) включить.

- [ ] **Step 4: Run тесты.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: species, nicks and fish movement`.

### Task 3: Состояние и UI экрана выбора

**Files:**
- Modify: `aquarium.py`, `tests/test_aquarium.py`

**Interfaces:**
- Consumes: `SPECIES`, `MAX_PER_SPECIES`.
- Produces:
  - `PickerState` — dataclass: `counts: dict[str, int]`, `cursor: int`.
  - `picker_handle_key(state: PickerState, key: str, rng: random.Random) -> str | None` (ключи `"up"`, `"down"`, `"left"`, `"right"`, `"space"`, `"r"`; возвращает `None`; `"enter"` возвращает `"start"` только если сумма > 0, иначе `None`; `"q"` возвращает `"quit"`). `left`/`right` зажимают в 0…20; `space` переключает 0↔1 (из ненулевого в 0, из 0 в 1); `r` ставит случайные 0…5 на каждый вид, гарантируя сумму ≥ 1.
  - `run_picker(stdscr, initial: dict[str, int]) -> dict[str, int] | None` (`None` при `q`; рисует рамку, список, подсказки, кнопку «ENTER — СТАРТ» по утверждённому макету).

- [ ] **Step 1: Write failing tests:** `test_picker_right_increments_and_clamps_at_20`, `test_picker_left_clamps_at_0`, `test_picker_space_toggles`, `test_picker_cursor_wraps_up_down`, `test_picker_enter_with_zero_total_does_not_start`, `test_picker_enter_starts_when_total_positive`, `test_picker_q_quits`, `test_picker_random_sum_at_least_one`.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** `PickerState`, `picker_handle_key` (чистая функция), затем `run_picker`: преобразует коды `curses` в строки ключей, перерисовывает при `KEY_RESIZE`.

- [ ] **Step 4: Run тесты.** Expected: PASS.

- [ ] **Step 5: Ручная проверка:** временно запустить `run_picker` в `python3 -c "import curses, aquarium; print(curses.wrapper(aquarium.run_picker, {}))"`. Видно рамку, список видов, можно менять счётчики, Enter возвращает словарь, `q` возвращает `None`.

- [ ] **Step 6: Commit** `feat: fish picker screen`.

### Task 4: UI аквариума

**Files:**
- Modify: `aquarium.py`, `tests/test_aquarium.py`

**Interfaces:**
- Consumes: `spawn_fish`, `step_fish`, `fish_lines`, `fish_width`, `Fish`.
- Produces: `run_aquarium(stdscr, counts: dict[str, int]) -> str` (возвращает `"quit"` на `q` или `"setup"` на `c`). `MIN_WIDTH = 40`, `MIN_HEIGHT = 12`. `tank_too_small(width: int, height: int) -> bool`.

- [ ] **Step 1: Write failing test:** `test_tank_too_small_boundaries` (`(39, 12)`, `(40, 11)` — `True`, `(40, 12)` — `False`).

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** `tank_too_small` и `run_aquarium`: цикл ~20 FPS через `stdscr.timeout(50)`; рисует линию поверхности `^` сверху, водоросли `}`/`{` снизу, каждую рыбу построчно и ник под ней (цвет через `curses.init_pair` при `curses.COLORS >= 8`, иначе без цвета); `f` кладёт корм в случайный `x` сверху и он опускается, рыбы по `step_fish(..., food=...)` едят при касании; `p` пауза; `KEY_RESIZE` пересоздаёт размеры и зажимает позиции; рисование обёрнуто так, чтобы запись в правый нижний угол не бросала `curses.error`. При `tank_too_small` — только сообщение «окно слишком маленькое» по центру, `q` работает.

- [ ] **Step 4: Run тесты.** Expected: PASS.

- [ ] **Step 5: Ручная проверка:** `python3 -c "import curses, aquarium; curses.wrapper(aquarium.run_aquarium, {'Рыбка': 5, 'Акула': 1})"`. Рыбы плавают в обе стороны, с цветом и ником, `f` роняет корм, `p` ставит на паузу, уменьшение окна до очень маленького не роняет программу и показывает сообщение, `q` выходит, терминал нормальный.

- [ ] **Step 6: Commit** `feat: aquarium screen`.

### Task 5: Точка входа и README

**Files:**
- Modify: `aquarium.py`, `tests/test_aquarium.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `load_config`, `save_config`, `config_path`, `run_picker`, `run_aquarium`, `SPECIES`.
- Produces: `main(argv: list[str]) -> int`, `choose_start(config: dict | None, setup_flag: bool) -> str` (`"picker"` если конфига нет или `--setup`, иначе `"aquarium"`).

- [ ] **Step 1: Write failing tests:** `test_choose_start_no_config_is_picker`, `test_choose_start_with_config_is_aquarium`, `test_choose_start_setup_flag_forces_picker`.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** `choose_start` и `main`: если `not sys.stdout.isatty()`, вернуть 0 без вывода; вызывать `curses.wrapper`; цикл «выбор → сохранить → аквариум», по `"setup"` из аквариума вернуться к выбору с текущими значениями; `q` на выборе завершает без записи конфига; `KeyboardInterrupt` ловится и завершает с кодом 0. `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`. Файл `chmod +x`.

- [ ] **Step 4: Run все тесты.** `python3 -m unittest discover -s tests -v`. Expected: PASS.

- [ ] **Step 5: README.md:** установка (`ln -s $PWD/aquarium.py ~/.local/bin/aquarium`, проверить `PATH`), хук:
  ```fish
  function fish_greeting
      aquarium
  end
  ```
  (в `~/.config/fish/functions/fish_greeting.fish`), как сбросить выбор (`aquarium --setup` или удалить `~/.config/aquarium/config.json`), клавиши.

- [ ] **Step 6: Ручная сквозная проверка** (в настоящем терминале, с временным `HOME`): `HOME=$(mktemp -d) ./aquarium.py` показывает выбор, Enter сохраняет конфиг и открывает аквариум; второй запуск с тем же `HOME` открывает аквариум сразу; `c` возвращает к выбору; Ctrl+C и `q` оставляют терминал нормальным; `./aquarium.py | cat` ничего не печатает и выходит с кодом 0.

- [ ] **Step 7: Commit** `feat: entry point, setup flow and README`.
