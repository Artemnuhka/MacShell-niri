<div align="center">

# MacShell · niri

**A macOS Tahoe-inspired menu bar, Dock, widgets and Liquid Glass — on Linux.**

[![niri](https://img.shields.io/badge/compositor-niri-89b4fa)](https://github.com/niri-wm/niri)
[![openSUSE](https://img.shields.io/badge/openSUSE-Tumbleweed-73ba25)](https://get.opensuse.org/tumbleweed/)
[![Checks](https://github.com/Artemnuhka/MacShell-niri/actions/workflows/check.yml/badge.svg)](https://github.com/Artemnuhka/MacShell-niri/actions)

A port of [0-ss/MacShell](https://github.com/0-ss/MacShell), with UI and widgets from [vsoultann/MacShell](https://github.com/vsoultann/MacShell).<br>
A native niri backend, an openSUSE installer and a dedicated session with scene refraction.

![MacShell on openSUSE: menu bar, widgets and Control Center](docs/media/control-center.png)

[Installation](#installation) · [Gallery](#gallery) · [Shortcuts](#shortcuts) · [Compatibility](#compatibility) · [Credits](#credits-and-licenses)

[🇷🇺 Русская версия](README.ru.md)

</div>

## Gallery

| Control Center | Alt+Tab |
| :---: | :---: |
| ![Opening and closing Control Center](docs/media/control-center.gif) | ![Switching applications](docs/media/app-switcher.gif) |
| Live glass, media controls and quick settings | Window switching through niri IPC |

| Settings | Lock Screen |
| :---: | :---: |
| ![Frosted settings and clock styles](docs/media/settings.png) | ![MacLock visual preview with media playback](docs/media/lock-screen.gif) |
| Frosted surfaces, rounded corners and five clock styles | Visual preview; actual session locking uses PAM |

| Spotlight · Apple Emoji | Music · MPRIS |
| :---: | :---: |
| ![Apple Color Emoji in Spotlight](docs/media/spotlight.png) | ![Pause, track change and seek](docs/media/music.gif) |

<details>
<summary>Desktop and appearance</summary>

![Desktop widgets](docs/media/desktop.png)

![Appearance settings](docs/media/appearance.png)

![Per-output display settings](docs/media/displays.png)

The screenshots use Tahoe Beach Dusk, selected separately in the test session. Full-resolution Apple wallpapers are not bundled or downloaded by the installer.

</details>

## Features

- **Menu bar and Dock:** application menus, workspaces, system tray, notifications, MPRIS media controls, application icons and a logo matching your distribution.
- **Control Center:** Wi-Fi, Bluetooth, volume, brightness, Focus and customizable controls. Tile entrance animations can be disabled.
- **Liquid Glass:** original MacShell shaders and rounded widgets; popovers refract a desktop snapshot, including windows. The private glass session enables experimental live scene refraction behind Dock and Spotlight by default. Settings use a denser frosted material.
- **Widgets:** clock, calendar, weather, batteries, music, notes, photos, reminders, stocks and timer/alarms; S/M/L sizes and four materials.
- **Settings:** appearance, menu bar, Dock, widgets, wallpapers and MacLock. Clock fonts are bundled.
- **Spotlight and Alt+Tab:** application and window search, clipboard history, emoji and application switching.
- **MacLock:** a separate PAM-enabled locker with media controls and customizable clocks.
- **Tahoe Dark + Bibata Modern Classic at 20 px** in the separate session, preserving shared desktop preferences. VirtualBox-specific terminal launchers work around virtual GPU limits. Ghostty, when already installed, gets a user-local launcher using Mesa software OpenGL only in VirtualBox niri sessions; the menu entry uses the same launcher.

This port preserves and adapts the existing MacShell components. See [PORT-PROVENANCE.md](PORT-PROVENANCE.md) for source revisions and attribution.

## Installation

**openSUSE Tumbleweed** is the primary tested distribution. Run the installer as your normal user; it requests `sudo` when system changes are needed.

```sh
git clone https://github.com/Artemnuhka/MacShell-niri.git
cd MacShell-niri
./install.sh --dry-run
./install.sh
```

On openSUSE, the default installation adds dependencies, user-local MacShell assets and a separate **MacShell Liquid Glass (username)** login entry. It creates `~/.config/niri/macshell.kdl` from your existing niri config (or the starter template), and a separate `macshell-glass.kdl` for refraction. Your original `niri/config.kdl` stays unchanged. Log out and choose MacShell when ready; installation does not switch or stop your current session.

### Keep Plasma and your configuration

By default, Plasma/KWin settings, shared GTK3/GTK4 CSS/preferences, Qt preferences, kitty settings and the original niri config are preserved. Themes/icons/cursors are installed as assets; MacShell selects its icon theme and passes the GTK theme to its own process tree. It does not change SDDM autologin, the default desktop, system graphics drivers or Plasma services.

**To return to KDE Plasma: log out and select Plasma in your login manager. No uninstall is needed.** Use `~/.local/bin/macshell-niri-session` for the separate stock-niri session, or `macshell-glass-session` for refraction. Never launch a second compositor inside your current desktop terminal.

Global appearance changes require explicit `--global-appearance`; editing the original niri config requires explicit `--integrate-config`. These options are unnecessary for the normal separate-session installation.

**The first installation may need to build Quickshell and niri-glass.** Builds run at low priority with one job; duration depends on your CPU and connection. Subsequent installations reuse suitable private builds. These live in your user directory and do not replace the system niri binary.

Without a login manager, start from a **text TTY**:

```sh
~/.local/bin/macshell-glass-session
```

Starting another compositor from a terminal inside your current desktop creates a nested session.

<details>
<summary>Installation options and updates</summary>

```sh
./install.sh --no-glass                   # stock niri, without optical refraction
./install.sh --theme keep --cursor keep --icons keep  # skip MacShell appearance assets/preferences
./install.sh --theme tahoe-light         # light theme
./install.sh --no-login-session          # TTY launcher only, no login-manager entry
./install.sh --skip-deps                 # dependencies and private compositor are ready
./install.sh --no-extras                 # skip optional utilities
./install.sh --no-clock-fonts            # skip bundled clock fonts
./install.sh --no-config                 # shell payload only; no private compositor config
./install.sh --keep-xwayland-config      # configure Xwayland manually
./install.sh --niri-config /path/config.kdl  # seed copied into adjacent macshell.kdl
./install.sh --global-appearance         # opt in to shared GTK/Qt/kitty appearance changes
./install.sh --integrate-config          # opt in to editing the original niri config
```

To update:

```sh
git pull --ff-only
./install.sh
```

Existing appearance and glass settings are preserved. Legacy widget settings are migrated only if the new file does not exist. After a Qt update, rebuild the private Quickshell if necessary with `./install.sh --build-quickshell`.

For a minimal **openSUSE guest in VirtualBox**, explicitly enable:

```sh
./install.sh --prepare-vm
```

This checks VirtualBox DMI, creates backups, changes official openSUSE HTTP mirrors to HTTPS and, if necessary, replaces `kernel-default-base` with `kernel-default` containing `vmwgfx`. The guest may need a reboot. This preparation is not part of a normal installation.

Third-party repositories are not added by default. You can explicitly enable the openSUSE X11:Wayland repository with `--with-wayland-repo` if needed.

</details>

### Existing systems and NVIDIA

The normal installer **does not run `zypper dup` or configure graphics drivers**. Before installing packages, it checks the XML output of `zypper --dry-run` and stops if the plan includes removals, vendor changes, kernel or KMP changes, or changes to NVIDIA/CUDA/nouveau/bbswitch packages. Existing configurations are backed up, and the proposed niri configuration is checked with `niri validate` before replacement.

These checks guard against those package-plan changes; they do not guarantee compatibility with every existing installation. Physical NVIDIA hardware has not been tested.

### Xwayland without a separate window

The port uses rootless **xwayland-satellite**, managed by niri:

```kdl
xwayland-satellite {
    path "xwayland-satellite"
}
```

Niri creates the socket, sets `DISPLAY` and launches satellite when the first X11 application starts. The installer removes simple legacy Xwayland startup commands and fixed `DISPLAY` values from the configuration it edits. Ambiguous shell commands and includes require manual migration; in that case, the original file is left untouched. External systemd/XDG-autostart services and shell profiles are not disabled by the installer.

### First steps

Open Settings from the Dock. Enter your city in **General → Desktop Widgets → City for weather**: weather uses Open-Meteo, with no automatic IP geolocation. Choose your wallpaper and arrange your widgets. If a keyboard shortcut is already assigned, the installer keeps your binding and reports the conflict.

## Shortcuts

| Shortcut | Action |
| --- | --- |
| `Super + Space` | Spotlight |
| `Super + V` | Clipboard history |
| `Super + .` | Emoji |
| `Alt + Tab` / `Alt + Shift + Tab` | Switch applications |
| Release `Alt` / press `Escape` | Confirm / cancel selection |
| `Super + L` | MacLock |
| `Ctrl + Alt + W` | Wallpaper picker |

You can also use IPC:

```sh
~/.local/bin/macshell-niri ipc call settings open
~/.local/bin/macshell-niri ipc call controlcenter open
~/.local/bin/macshell-niri ipc call clock open
~/.local/bin/macshell-niri ipc call about open
```

## Compatibility

Tested in **VirtualBox on openSUSE Tumbleweed 20261014**, with niri 26.04, xwayland-satellite 0.8.3 and a private Quickshell 0.3.2 build. MacLock requires a separate PAM-enabled Quickshell, which the installer checks independently.

| Environment | Status |
| --- | --- |
| openSUSE Tumbleweed / VirtualBox | Primary test environment: installation, updates and graphical session |
| Physical PC / NVIDIA / multiple monitors | Not tested on hardware |
| Arch / Fedora | pacman/dnf support exists in the installer; a full installation has not been tested |
| Leap / Slowroll | Requires sufficiently recent niri, Qt and satellite packages |
| MicroOS / Aeon / Kalpa | Automatic package installation is disabled; prepare dependencies using the normal transactional-update workflow, then use `--skip-deps` |

**Known limitations:**

- Real refraction requires the pinned private niri-glass session and remains experimental. Stock niri does not provide the same effect.
- Live per-window thumbnails in the Dock/Alt+Tab are not available yet; application icons are used instead.
- A single theme cannot make every GTK/Qt/Electron/X11 application identical to macOS. niri does not provide conventional window minimization into the Dock.
- Wi-Fi, Bluetooth, battery controls, Night Shift and screen recording need separate testing on real hardware. Screen sharing requires a working desktop portal.
- Do not run the original MacShell and this port simultaneously; other panels and notification daemons can also conflict.
- Glass uses GPU resources; choose its material and intensity in Settings. Performance in a small VM is not a reliable estimate for a physical PC.

## Uninstall and rollback

```sh
./install.sh --restore-theme  # restore saved GTK/kitty/niri settings
./install.sh --uninstall     # remove the shell, its bindings and managed login entry
```

Settings, recovery backups, dependencies, fonts/themes and private builds are retained. Unchanged managed launchers/configs are removed using a checksum manifest; edited files are preserved, and modified shell payloads are backed up. Identical reinstalls do not create extra launcher/payload backups. Default Xwayland changes are confined to private configs; if you explicitly used `--integrate-config`, restore its backup to undo that migration. Widgets are stored in `~/.config/macshell/widgets.json`, clock settings in `~/.config/macshell/clock.json`, and menu bar/Dock settings in `~/.config/macbar` and `~/.config/macdock`.

## Checks

```sh
python3 -m unittest discover -s tests -v
node tests/niri-state.test.cjs
node tests/display-state.test.cjs
```

CI checks the installer and migrations, niri event reducer, Python/shell syntax and QML parsing. Automated checks do not replace graphical testing. Test GUI applications, temporary recordings, logs and VM access keys are not included in the public tree.

## Credits and licenses

- [0-ss/MacShell](https://github.com/0-ss/MacShell) — original shell, MIT.
- [vsoultann/MacShell](https://github.com/vsoultann/MacShell) — settings UI, widgets and animation improvements, adapted for niri with attribution.
- [niri](https://github.com/niri-wm/niri) and [Niri-glass](https://github.com/zaroutt/Niri-glass) — compositor and glass integration, GPL-3.0. Sources and licenses are retained alongside the private build.
- [MacTahoe GTK](https://github.com/vinceliuice/MacTahoe-gtk-theme) — MIT; [MacTahoe icons](https://github.com/vinceliuice/MacTahoe-icon-theme) and [Bibata](https://github.com/ful1e5/Bibata_Cursor) — GPL-3.0.
- Bundled clock fonts — SIL Open Font License; licenses and pinned SHA-256 hashes are in `vendor/clock-fonts`.

Third-party licenses and pinned versions are in `vendor/`. The root [LICENSE](LICENSE) covers MacShell's MIT code and does not replace third-party licenses. Original documentation: [README.upstream.md](README.upstream.md).

## October 18 upstream refresh

Imported 0-ss/MacShell `831548c`. The default material now uses the original MacShell shader and
original clock/calendar/weather/player components, with a transparent menu bar and a smooth 22px
Dock. Extra Tahoe widgets remain available. Image widgets copy a selected picture into private
storage; Widget size scales widgets and the grid from 60% to 150%. Bluetooth scanning, pairing,
device state and errors are shared by the menu, Control Center and Settings.

The private niri compositor supplies live scene refraction behind the Dock and Spotlight. This
experimental path is enabled by default in the private glass session; older wallpaper-backed settings
are migrated once, while later explicit material choices are preserved. The original wallpaper
material remains available in Appearance. Per-window thumbnails remain unavailable.

Update commands (always target this niri fork):

```sh
macshell-niri-update check
macshell-niri-update log
macshell-niri-update update
macshell-niri-update rollback
macshell-niri-update channel main  # or release
```

The launcher prevents duplicate shells in one niri session and restarts after a crash. Updates preserve
settings and back up the previous shell together with MacLock. No automatic update timer is enabled.

Super + 1…9 switches to a workspace by position; the menu bar shows only active or occupied
workspaces, in position order, without precreating nine named workspaces. The bundled
MacOS-Like icon themes are the set recommended by the original repository. The installer
selects the dark variant by default; use `--icons macos-like-light` or `--icons keep`.
The font remains Inter; SF Pro is not bundled.

### Multiple displays, NVIDIA and emoji

The Dock can appear on all displays, the chosen primary display, or the focused display.
Disconnecting its selected output moves it to an available display. Widgets keep their saved
connector and coordinates: unplugged-display widgets remain accessible on a connected display,
then return when it reconnects. Edit mode offers **Next display**. Displays settings support
per-output resolution, refresh, fractional scale and relative position, with a 15-second rollback.
Saved settings are restored when the output reconnects. Qt and niri use logical coordinates
for mixed DPI, portrait outputs and negative desktop positions.

On NVIDIA hardware the installer adds an isolated user application profile for both `niri`
and `niri-glass`, limiting the driver's free VRAM buffer pool as recommended by niri. The private
session launcher checks it before starting the compositor. Existing driver profiles, PRIME
selection, boot parameters and driver packages are preserved. `macshell-niri-doctor` reports
GPU drivers, NVIDIA DRM modesetting and inherited rendering overrides. A recent GBM-capable
NVIDIA driver and DRM modesetting remain prerequisites; driver installation is distribution-specific.
References: [niri NVIDIA guide](https://niri-wm.github.io/niri/Nvidia.html),
[NVIDIA profile search paths](https://download.nvidia.com/XFree86/Linux-x86_64/570.124.04/README/profiles.html).
Physical NVIDIA and multi-monitor hotplug still need hardware validation; automated layout
checks cover three displays, mixed scaling and reconnect, and the GUI was checked in VirtualBox.

Spotlight prefers **Apple Color Emoji** when installed, including category icons and the emoji grid.
An optional user-local install is available with `macshell-niri-emoji install-apple`; it downloads
the pinned Linux font build from [apple-emoji-ttf](https://github.com/samuelngs/apple-emoji-ttf)
and verifies SHA-256. The font artwork is not bundled or relicensed by this fork. It changes
Spotlight's chosen emoji family without overriding system font aliases; restart MacShell after
installing. Other colour emoji fonts remain the fallback. The text UI font remains Inter.

Settings and Alt+Tab also capture the scene before opening, including application windows. Each Qt window owns its texture; the background remains still while open.
