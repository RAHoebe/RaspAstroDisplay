# Display setup

Profiles: original official Raspberry Pi 7-inch Touch Display (800×480 native) and 7-inch Touch Display 2 (720×1280 native). Use a Pi 4 with 4 GB RAM or newer, 64-bit Raspberry Pi OS Desktop and current KMS graphics. Connect one supported DSI display while configuring it.

## Wizard

From the checkout, as the desktop user:

```sh
python3 deploy/display.py wizard
sudo reboot
```

Choose English or Dutch, rotation, interface size and cursor visibility. The panel is detected from its connected DSI mode. With multiple touchscreens, choose the device belonging to this panel. The wizard previews the result and makes a dated backup under `~/raspdisplay-backups/` before saving.

| Profile | Native resolution | Default rotation | Browser scale | Landscape result |
| --- | --- | --- | --- | --- |
| `original` | 800×480 | 180° | 100% | 800×480 |
| `touch2` | 720×1280 | 90° | 150% | 1280×720, about 853×480 logical pixels |

Touch Display 2 also offers compact 125% scaling. All four rotations are supported; 90° and 270° swap native width and height. Choose the rotation that suits your enclosure. Portrait layouts scroll where needed.

Noninteractive setup or a preview without changes:

```sh
python3 deploy/display.py preview touch2 --rotation 270
python3 deploy/display.py apply touch2 --rotation 270 --cursor hidden
python3 deploy/display.py status
```

The saved profile is `~/.config/astro-display.json`. The kiosk reads it at startup. Without a profile, it uses original display dimensions and leaves desktop rotation as configured. The web application does not alter boot or desktop configuration.

## Changing panels

1. Update Raspberry Pi OS through its supported package-management path with the current display attached. `display.py status` checks whether the Touch Display 2 overlay is installed.
2. Run `sudo poweroff`, disconnect power and change the panel and cable following Raspberry Pi's instructions.
3. Boot, run the wizard through SSH or a terminal, and reboot to load display, touch and kiosk settings together.

Official references: [original Touch Display](https://www.raspberrypi.com/documentation/accessories/display.html), [Touch Display 2](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html). Use the ribbon cable appropriate to your Pi generation.

## Touch and cursor

**Wayfire:** an output transform and touchscreen-to-output mapping are written in `~/.config/wayfire.ini`. Wayfire applies the output transform to mapped touch. Do not add another XInput or udev rotation matrix on top.

**labwc:** touch mapping and the corresponding libinput calibration matrix go in `~/.config/labwc/rc.xml`. Kiosk startup applies the output transform through `wlr-randr`. Unrelated settings are preserved. This follows [labwc touch configuration](https://labwc.github.io/labwc-config.5.html); physical testing remains pending.

The original panel was verified on a Pi 4, Wayfire 0.7.5 and **6.12.96+rpt-rpi-v8**, rotated 180°. On this updated KMS installation an old `dtoverlay=rpi-ft5406` prevented native touch from probing. Commenting that legacy line in `/boot/firmware/config.txt`, retaining `display_auto_detect=1` and `dtoverlay=vc4-kms-v3d`, restored touch. The input became `10-0038 generic ft5x06 (79)`. Device names are detected; input event numbers are not hardcoded.

If a legacy upgrade produces an image but no touch, inspect `journalctl -b -k` and `/proc/bus/input/devices` for this conflict before adding overlays. Back up boot configuration before editing it. For a detected Wayfire device with missing mapping, run `python3 deploy/display.py touch-only` and restart the desktop.

A transparent Xcursor theme hides the pointer from desktop startup, including before first touch. Choose a visible cursor in the wizard for mouse use. CSS separately hides the cursor only on the kiosk page (`?kiosk=1`).

## Recovery

Use SSH to rerun the wizard or restore `wayfire.ini` / `rc.xml` and `astro-display.json` from the same dated backup, then reboot. A `no-previous-profile` marker means that reverting also requires removing the newly created `~/.config/astro-display.json`.

Check touch at top-right Settings and bottom-left Tonight after a change. Original display hardware is verified. Touch Display 2 dimensions, rotations and configuration have automated checks, but physical verification waits for the new panel.
## Automatic brightness (1.1)

In **Settings → Display**, select active brightness, idle brightness, automatic dimming and a timeout. Brightness is 5–100% in steps of five; idle cannot exceed active. The default is 10% idle after 60 seconds (allowed timeout: 10–3600 seconds). Upgrades keep the old active brightness; fresh installations use 70%.

Only interaction in the kiosk at `http://127.0.0.1:8080/?kiosk=1` counts as activity. The Pi backend uses a monotonic clock and fades up in approximately 0.2 seconds or down in one second. The entire first touch while dimmed is consumed, including over dialogs. Restarting begins at active brightness. Missing or failed backlight hardware does not intercept normal touches.

The existing `GET /api/settings` response now includes `display.profile` with `active`, `idle`, `timeout` and `auto_dim`, plus `available`, `dimmed`, `current` and `seconds_until_idle`. Save changes through `POST /api/settings` with `{"display":{"active":65,"idle":10,"timeout":60,"auto_dim":true}}`. Partial profile updates are allowed. The legacy `{"brightness":65}` input remains usable.

`GET /api/display` returns runtime status. `POST /api/display/activity` accepts an empty JSON object and the normal `X-Astro-Token`; it additionally requires a loopback client address. Forwarded headers cannot bypass this restriction. Remote browsers never send activity. Activity and fade steps do not write settings to disk. The migrated `brightness.json` retains `percent` for v1.0 rollback, adds the complete profile, and is included in application ZIP backups.
