<div align="center">

# MacShell · niri

**Панель, Dock, виджеты и Liquid Glass в духе macOS Tahoe — на Linux.**

[![niri](https://img.shields.io/badge/compositor-niri-89b4fa)](https://github.com/niri-wm/niri)
[![openSUSE](https://img.shields.io/badge/openSUSE-Tumbleweed-73ba25)](https://get.opensuse.org/tumbleweed/)
[![Checks](https://github.com/Artemnuhka/MacShell-niri/actions/workflows/check.yml/badge.svg)](https://github.com/Artemnuhka/MacShell-niri/actions)

Порт [0-ss/MacShell](https://github.com/0-ss/MacShell) с интерфейсом и виджетами из [vsoultann/MacShell](https://github.com/vsoultann/MacShell).<br>
Собственный backend niri, установщик для openSUSE и отдельный сеанс с преломлением сцены.

![MacShell на openSUSE: панель, виджеты и Control Center](docs/media/control-center.png)

[Установка](#установка) · [Галерея](#галерея) · [Клавиши](#клавиши) · [Совместимость](#совместимость) · [Авторы](#авторы-и-лицензии)

</div>

## Галерея

Все кадры и GIF ниже сняты с этого порта в **openSUSE Tumbleweed / VirtualBox**, без макетов интерфейса. GIF уменьшены до 4 кадров/с для небольшого размера; они не показывают реальную плавность анимаций.

| Control Center | Alt+Tab |
| :---: | :---: |
| ![Открытие и закрытие Control Center](docs/media/control-center.gif) | ![Переключение приложений](docs/media/app-switcher.gif) |
| Живое стекло, плеер и быстрые настройки | Переключение окон через niri IPC |

| Настройки | Экран блокировки |
| :---: | :---: |
| ![Матовые настройки и выбор часов](docs/media/settings.png) | ![Визуальный предпросмотр MacLock](docs/media/lock-screen.png) |
| Матовые поверхности, скругления, пять стилей часов | Предпросмотр внешнего вида; настоящая блокировка использует PAM |

<details>
<summary>Рабочий стол и оформление</summary>

![Виджеты на рабочем столе](docs/media/desktop.png)

![Настройки оформления](docs/media/appearance.png)

Обои на снимках — Tahoe Beach Dusk, выбраны отдельно в тестовом сеансе. Полноразмерные обои Apple в репозиторий не включены и установщиком не загружаются.

</details>

## Что внутри

- **Панель и Dock:** меню приложений, рабочие столы, трей, уведомления, MPRIS-плеер, нормальные иконки приложений и логотип текущего дистрибутива.
- **Control Center:** Wi-Fi, Bluetooth, звук, яркость, Focus и настраиваемое расположение элементов. Анимацию появления плиток можно отключить.
- **Liquid Glass:** в отдельном сеансе niri-glass линзы преломляют сцену под панелями, включая окна приложений. Настройки используют более плотное матовое оформление.
- **Виджеты:** часы, календарь, погода, батареи, музыка, заметки, фотографии, напоминания, акции и таймер/будильники; размеры S/M/L и четыре материала.
- **Настройки:** оформление, панель, Dock, виджеты, обои и MacLock. Часовые шрифты включены в комплект.
- **Spotlight и Alt+Tab:** поиск приложений и окон, буфер обмена, эмодзи и переключатель приложений.
- **MacLock:** отдельный locker с PAM, музыкальным плеером и вариантами часов.
- **Tahoe Dark + Bibata Modern Classic 20 px** при новой установке. Для kitty в VirtualBox включается отдельный обход артефактов виртуального GPU.

Это перенос существующей оболочки: исходные компоненты MacShell сохранены и адаптированы. Подробности версий и заимствований — в [PORT-PROVENANCE.md](PORT-PROVENANCE.md).

## Установка

Основная проверенная система — **openSUSE Tumbleweed**. Запускайте от своего пользователя; `sudo` установщик запросит сам для системных действий.

```sh
git clone https://github.com/Artemnuhka/MacShell-niri.git
cd MacShell-niri
./install.sh --dry-run
./install.sh
```

На openSUSE обычная установка готовит зависимости, пользовательскую оболочку, тему, курсор, конфиг и отдельный пункт **MacShell Liquid Glass (имя пользователя)** в менеджере входа. После установки выйдите из текущего сеанса и выберите этот пункт. Установщик сам сеанс не запускает.

**Первая установка может потребовать сборку Quickshell и niri-glass.** Она идёт с низким приоритетом, в одно задание; продолжительность зависит от CPU и сети. При повторной установке подходящие частные сборки используются повторно. Они находятся в пользовательском каталоге и не заменяют системный niri.

Если менеджера входа нет, запускайте из **текстовой TTY**:

```sh
~/.local/bin/macshell-glass-session
```

Не запускайте ещё один compositor из терминала внутри действующего рабочего стола: получится вложенный сеанс.

<details>
<summary>Варианты установки и обновление</summary>

```sh
./install.sh --no-glass                   # штатный niri, без оптического преломления
./install.sh --theme keep --cursor keep  # сохранить оформление
./install.sh --theme tahoe-light         # светлая тема
./install.sh --no-login-session          # запуск из TTY, без пункта менеджера входа
./install.sh --skip-deps                 # зависимости и частный compositor уже готовы
./install.sh --no-extras                 # без необязательных утилит
./install.sh --no-clock-fonts            # не устанавливать комплект часовых шрифтов
./install.sh --no-config                 # не редактировать конфиг niri
./install.sh --keep-xwayland-config      # настройка Xwayland вручную
./install.sh --niri-config /path/config.kdl
```

Для обновления:

```sh
git pull --ff-only
./install.sh
```

Существующие настройки оформления и стекла сохраняются. Старые настройки виджетов мигрируются только при отсутствии нового файла. После обновления Qt частный Quickshell при необходимости пересобирается командой `./install.sh --build-quickshell`.

Для облегчённой **openSUSE в VirtualBox** есть явный режим:

```sh
./install.sh --prepare-vm
```

Он проверяет DMI VirtualBox, делает резервные копии, меняет официальные HTTP-зеркала openSUSE на HTTPS и при необходимости заменяет `kernel-default-base` на `kernel-default` с `vmwgfx`. Может потребоваться перезагрузка гостя. На обычной установке этот режим не выполняется.

Сторонние репозитории по умолчанию не добавляются. При необходимости можно явно выбрать `--with-wayland-repo` для openSUSE X11:Wayland.

</details>

### Существующая система и NVIDIA

Обычный установщик **не выполняет `zypper dup` и не настраивает видеодрайверы**. Перед установкой пакетов проверяется XML-план `zypper --dry-run`: при удалениях, смене поставщика, изменениях ядра, KMP-модулей или NVIDIA/CUDA/nouveau/bbswitch работа останавливается. Существующие конфиги сохраняются перед изменением, кандидат конфига niri проверяется через `niri validate`.

Это защита от таких изменений пакетного плана; совместимость с любой давно установленной системой не гарантирована. Физическая NVIDIA в тестировании не участвовала.

### Xwayland без отдельного окна

Используется rootless **xwayland-satellite**, которым управляет niri:

```kdl
xwayland-satellite {
    path "xwayland-satellite"
}
```

Niri создаёт сокет, выставляет `DISPLAY` и запускает satellite при первом X11-приложении. Установщик убирает простые старые автозапуски Xwayland и фиксированный `DISPLAY` из редактируемого конфига. Неоднозначные shell-команды и include требуют ручной миграции: исходник в таком случае не переписывается. Внешние systemd/XDG-autostart-сервисы и профили оболочки установщик не отключает.

### Первые настройки

Откройте Settings из Dock. В **General → Desktop Widgets → City for weather** укажите город: погода использует Open-Meteo, автоматического определения местоположения по IP нет. Выберите свои обои и расположение виджетов. При уже занятом сочетании клавиш установщик сохраняет вашу привязку и сообщает о конфликте.

## Клавиши

| Сочетание | Действие |
| --- | --- |
| `Super + Space` | Spotlight |
| `Super + V` | Буфер обмена |
| `Super + .` | Эмодзи |
| `Alt + Tab` / `Alt + Shift + Tab` | Переключение приложений |
| Отпустить `Alt` / `Escape` | Подтвердить / отменить выбор |
| `Super + L` | MacLock |
| `Ctrl + Alt + W` | Выбор обоев |

Также доступны команды:

```sh
~/.local/bin/macshell-niri ipc call settings open
~/.local/bin/macshell-niri ipc call controlcenter open
~/.local/bin/macshell-niri ipc call clock open
~/.local/bin/macshell-niri ipc call about open
```

## Совместимость

Проверки выполнены в **VirtualBox, openSUSE Tumbleweed 20261014**, niri 26.04, xwayland-satellite 0.8.3 и частном Quickshell 0.3.2. Для MacLock нужен отдельный Quickshell с поддержкой PAM; установщик проверяет его отдельно.

| Среда | Статус |
| --- | --- |
| openSUSE Tumbleweed / VirtualBox | Основная тестовая среда: установка, обновление и графический сеанс |
| Физический ПК / NVIDIA / несколько мониторов | Не проверено на оборудовании |
| Arch / Fedora | В установщике есть pacman/dnf; полная установка не проверена |
| Leap / Slowroll | Требуется доступность достаточно новых niri, Qt и satellite |
| MicroOS / Aeon / Kalpa | Автоустановка пакетов отключена; подготовьте зависимости штатным transactional-update, затем `--skip-deps` |

**Известные ограничения:**

- Сеанс с настоящим преломлением использует закреплённый частный niri-glass и остаётся экспериментальным. Штатный niri не даёт такой же эффект.
- Живых миниатюр отдельных окон в Dock/Alt+Tab пока нет: используются иконки приложений.
- Полная идентичность macOS для всех GTK/Qt/Electron/X11-приложений недостижима одной темой. niri не предоставляет обычное сворачивание окна в Dock.
- Wi-Fi, Bluetooth, батарея, Night Shift и экранная запись требуют отдельной проверки на реальном оборудовании. Для screen sharing нужен работающий desktop portal.
- Не запускайте одновременно оригинальный MacShell и этот порт; другие панели и демоны уведомлений тоже могут конфликтовать.
- Стекло расходует GPU; режим и интенсивность выбираются в настройках. Результаты маленькой VM нельзя переносить на физический ПК как оценку производительности.

## Удаление и откат

```sh
./install.sh --restore-theme  # вернуть сохранённые настройки GTK/kitty/niri
./install.sh --uninstall     # убрать оболочку, её привязки и управляемый пункт входа
```

Настройки, резервные копии, зависимости и частные сборки остаются. Для полного отката миграции Xwayland восстановите нужную резервную копию конфига niri. Виджеты хранятся в `~/.config/macshell/widgets.json`, настройки часов — `~/.config/macshell/clock.json`, панели и Dock — в `~/.config/macbar` и `~/.config/macdock`.

## Проверки

```sh
python3 -m unittest discover -s tests -v
node tests/niri-state.test.cjs
```

CI проверяет миграции и установщик, редуктор niri, синтаксис Python/shell и QML-парсер. Автоматические проверки не заменяют графическую сессию. В публичное дерево не включены тестовые GUI-приложения, временные записи, логи и ключи доступа к VM.

## Авторы и лицензии

- [0-ss/MacShell](https://github.com/0-ss/MacShell) — исходная оболочка, MIT.
- [vsoultann/MacShell](https://github.com/vsoultann/MacShell) — развитие интерфейса настроек, виджетов и анимаций; изменения адаптированы для niri с указанием происхождения.
- [niri](https://github.com/niri-wm/niri) и [Niri-glass](https://github.com/zaroutt/Niri-glass) — compositor и интеграция стекла, GPL-3.0. Исходники и лицензии сохраняются рядом с частной сборкой.
- [MacTahoe GTK](https://github.com/vinceliuice/MacTahoe-gtk-theme) — MIT; [MacTahoe icons](https://github.com/vinceliuice/MacTahoe-icon-theme) и [Bibata](https://github.com/ful1e5/Bibata_Cursor) — GPL-3.0.
- Комплект часовых шрифтов — SIL Open Font License; лицензии и закреплённые SHA-256 в `vendor/clock-fonts`.

Лицензии и закреплённые версии сторонних ресурсов находятся в `vendor/`. Корневой [LICENSE](LICENSE) относится к MIT-коду MacShell, а не заменяет лицензии сторонних частей. Исходный README: [README.upstream.md](README.upstream.md).
