"""Display profiles and an interactive setup wizard for Wayfire and labwc."""
import argparse
import configparser
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
try:
    from . import desktop
    from .cursor import install_theme
except ImportError:
    import desktop
    from cursor import install_theme

PROFILES = {
    'original': dict(native='800x480', width=800, height=480, rotation='180', scale=1),
    'touch2': dict(native='720x1280', width=1280, height=720, rotation='90', scale=1.5),
}
CONFIG = Path.home() / '.config/astro-display.json'
WAYFIRE = Path.home() / '.config/wayfire.ini'


def selection(name='original', flipped=False, compact=False, rotation=None):
    profile = dict(PROFILES[name], profile=name)
    if flipped:
        profile['rotation'] = {'180': 'normal', '90': '270'}[profile['rotation']]
    if compact and name == 'touch2':
        profile['scale'] = 1.25
    if rotation is not None:
        if str(rotation) not in ('0','90','180','270'):
            raise ValueError('Rotation must be 0, 90, 180 or 270 degrees.')
        profile['rotation'] = 'normal' if str(rotation) == '0' else str(rotation)
    width,height = map(int,profile['native'].split('x'))
    profile['width'],profile['height'] = (height,width) if profile['rotation'] in ('90','270') else (width,height)
    return profile


def load_selection(path=CONFIG):
    if not path.exists():
        return selection()
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('profile') not in PROFILES or type(data.get('flipped')) is not bool
            or type(data.get('compact')) is not bool):
        raise ValueError('Ongeldig schermprofiel; gebruik display.py apply opnieuw.')
    return selection(data['profile'], data['flipped'], data['compact'], data.get('rotation'))


def kiosk_args(profile):
    # Chromium window-size uses logical pixels; kiosk maximizes on the output.
    scale = profile['scale']
    return [f"--window-size={round(profile['width'] / scale)},{round(profile['height'] / scale)}",
            f'--force-device-scale-factor={scale}']


def touch_names(devices):
    """INPUT_PROP_DIRECT + EV_ABS distinguish touchscreens from touchpads/mice."""
    names = []
    for block in devices.split('\n\n'):
        name = re.search(r'^N: Name="(.*)"$', block, re.M)
        prop = re.search(r'^B: PROP=([0-9a-f ]+)$', block, re.M)
        events = re.search(r'^B: EV=([0-9a-f ]+)$', block, re.M)
        if (name and prop and events and int(prop[1].split()[-1], 16) & 2
                and int(events[1].split()[-1], 16) & 8):
            names.append(name[1])
    return sorted(set(names))


def connected_displays(root=Path('/sys/class/drm')):
    found = []
    for path in root.glob('card*-*'):
        status = path / 'status'
        if status.exists() and status.read_text().strip() == 'connected':
            found.append(dict(output=path.name.split('-', 1)[1],
                              modes=(path / 'modes').read_text().splitlines()))
    return found


def check_hardware(profile, displays, names, requested_touch=None):
    if len(displays) != 1 or not displays[0]['output'].startswith('DSI-'):
        raise ValueError('Verwacht één actief DSI-scherm. Controleer display.py status.')
    if profile['native'] not in displays[0]['modes']:
        raise ValueError(f"Dit profiel vereist een aangesloten {profile['native']}-scherm; niets gewijzigd.")
    if requested_touch:
        if requested_touch not in names:
            raise ValueError('De opgegeven touchscreennaam is niet aangesloten.')
        touch = requested_touch
    elif len(names) == 1:
        touch = names[0]
    else:
        raise ValueError('Touchscreen niet eenduidig gevonden; controleer status en --touch-device.')
    if any(c in touch for c in '\r\n[]'):
        raise ValueError('Touchscreennaam bevat ongeldige configuratietekens.')
    return displays[0]['output'], touch


def edit_section(text, section, values):
    """Change only selected keys, preserving other sections and comments."""
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read_string(text)
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.strip() == f'[{section}]'), None)
    if start is None:
        text = text.rstrip() + f'\n\n[{section}]\n'
        return text + ''.join(f'{key} = {value}\n' for key, value in values.items() if value is not None)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
    remaining = dict(values)
    replacement = []
    for line in lines[start + 1:end]:
        key = line.split('=', 1)[0].strip()
        if '=' in line and key in values:
            value = remaining.pop(key, None)
            if value is not None:
                replacement.append(f'{key} = {value}\n')
        else:
            replacement.append(line if line.endswith('\n') else line + '\n')
    replacement.extend(f'{key} = {value}\n' for key, value in remaining.items() if value is not None)
    return ''.join(lines[:start + 1] + replacement + lines[end:])


def wayfire_config(text, profile, output, touch):
    # Remove the previous panel's fixed mode: Wayfire chooses its native mode.
    text = edit_section(text, f'output:{output}', dict(mode=None, transform=profile['rotation'],
                                                     scale='1.0', position='0,0'))
    return edit_section(text, f'input-device:{touch}', dict(output=output))


def atomic_write(path, text):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def save_changes(after, data=None, wayfire=WAYFIRE, config=CONFIG, backup_root=None):
    backup_root = backup_root or Path.home() / 'raspdisplay-backups'
    backup = backup_root / ('display-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    shutil.copy2(wayfire, backup / wayfire.name)
    old_profile = config.read_text(encoding='utf-8') if config.exists() else None
    if old_profile is not None:
        (backup / 'astro-display.json').write_text(old_profile, encoding='utf-8')
    else:
        (backup / 'no-previous-profile').touch()
    try:
        if data is not None:
            atomic_write(config, json.dumps(data, indent=2) + '\n')
        atomic_write(wayfire, after)
    except OSError:
        shutil.copy2(backup / wayfire.name, wayfire)
        if old_profile is None:
            config.unlink(missing_ok=True)
        else:
            atomic_write(config, old_profile)
        raise
    return backup


def apply_profile(name, flipped=False, compact=False, rotation=None, requested_touch=None, hide_cursor=None):
    chosen = selection(name,flipped,compact,rotation)
    output,touch = check_hardware(chosen,connected_displays(),touch_names(Path('/proc/bus/input/devices').read_text()),requested_touch)
    backend = desktop.detect()
    path = WAYFIRE if backend=='wayfire' else Path.home()/'.config/labwc/rc.xml'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        path.write_text('' if backend=='wayfire' else '<labwc_config/>')
    before = path.read_text(encoding='utf-8')
    if hide_cursor:
        install_theme()
    if backend=='wayfire':
        after = wayfire_config(before,chosen,output,touch)
        if hide_cursor is not None:
            after = edit_section(after,'input',dict(cursor_theme='AstroInvisible' if hide_cursor else 'default'))
    else:
        after = desktop.labwc_config(before,output,touch,chosen['rotation'],hide_cursor)
    data = dict(profile=name,flipped=flipped,compact=compact,rotation=rotation,backend=backend,output=output,touch=touch)
    backup = save_changes(after,data,wayfire=path)
    print('Saved profile. Configuration backup:',backup)
    print('Restart to load display, touch and kiosk together: sudo reboot')
    return backup


def wizard():
    language = input('Language / Taal [1 English, 2 Nederlands]: ').strip()
    nl = language == '2'
    def say(en,nl_text):
        return nl_text if nl else en
    displays = connected_displays()
    detected = next((name for name,p in PROFILES.items() if len(displays)==1 and p['native'] in displays[0]['modes']),None)
    if not detected:
        raise ValueError(say('Connect one supported official DSI display first.','Sluit eerst één ondersteund officieel DSI-scherm aan.'))
    print(say('Detected display: ','Gevonden scherm: ')+detected+' ('+PROFILES[detected]['native']+')')
    default = PROFILES[detected]['rotation']
    answer = input(say(f'Rotation [0/90/180/270, default {default}]: ',f'Rotatie [0/90/180/270, standaard {default}]: ')).strip() or default
    if answer not in ('0','90','180','270'):
        raise ValueError(say('Choose 0, 90, 180 or 270.','Kies 0, 90, 180 of 270.'))
    compact = detected=='touch2' and input(say('Interface [1 large touch buttons, 2 compact]: ','Interface [1 grote aanraakknoppen, 2 compact]: ')).strip()=='2'
    hidden = input(say('Hide desktop cursor? [Y/n]: ','Desktopcursor verbergen? [J/n]: ')).strip().lower() not in ('n','no','nee')
    names=touch_names(Path('/proc/bus/input/devices').read_text())
    touch=None
    if len(names)>1:
        for index,name in enumerate(names,1):
            print(index,name)
        touch=names[int(input(say('Touchscreen number: ','Touchscreennummer: ')))-1]
    chosen=selection(detected,compact=compact,rotation=answer)
    print(f"{chosen['width']}×{chosen['height']} · {chosen['rotation']}° · {chosen['scale']*100:g}%")
    if input(say('Save this display configuration? [y/N]: ','Deze scherminstellingen opslaan? [j/N]: ')).strip().lower() in ('y','yes','j','ja'):
        apply_profile(detected,compact=compact,rotation=answer,requested_touch=touch,hide_cursor=hidden)
    else:
        print(say('No changes made.','Niets gewijzigd.'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'preview', 'apply', 'kiosk-args', 'touch-only','wizard','activate'])
    parser.add_argument('profile', nargs='?', choices=PROFILES)
    parser.add_argument('--flipped', action='store_true', help='180 graden extra draaien')
    parser.add_argument('--compact', action='store_true', help='Touch Display 2: 125%% in plaats van 150%%')
    parser.add_argument('--touch-device', help='Exacte apparaatnaam, alleen bij meerdere touchscreens')
    parser.add_argument('--rotation', choices=['0','90','180','270'], help='Absolute rotation of the native panel')
    parser.add_argument('--cursor', choices=['hidden','visible'], help='Desktop cursor visibility for the kiosk')
    args = parser.parse_args(argv)
    try:
        if args.action=='wizard':
            wizard()
            return 0
        if args.action=='activate':
            if CONFIG.exists() and desktop.detect()=='labwc':
                profile=load_selection()
                data=json.loads(CONFIG.read_text())
                output,touch=check_hardware(profile,connected_displays(),touch_names(Path('/proc/bus/input/devices').read_text()),data.get('touch'))
                subprocess.run(['wlr-randr','--output',output,'--preferred','--transform',profile['rotation'],'--scale','1'],check=True)
            return 0
        if args.action == 'kiosk-args':
            print('\n'.join(kiosk_args(load_selection())))
            return 0
        if args.action == 'preview':
            if not args.profile:
                parser.error('preview vereist original of touch2')
            chosen = selection(args.profile, args.flipped, args.compact,args.rotation)
            print(json.dumps(dict(chosen, chromium=kiosk_args(chosen)), indent=2))
            return 0
        displays = connected_displays()
        names = touch_names(Path('/proc/bus/input/devices').read_text())
        if args.action == 'status':
            overlay = 'vc4-kms-dsi-ili9881-7inch.dtbo'
            supported = any((Path(base) / overlay).exists() for base in
                            ['/boot/firmware/overlays', '/boot/overlays'])
            print(json.dumps(dict(selected=load_selection(), displays=displays, touchscreens=names,
                                  touch2_overlay_present=supported), indent=2))
            if not supported:
                print('Touch Display 2-overlay ontbreekt: systeemondersteuning bijwerken vóór ombouw.')
            return 0
        if args.action=='apply':
            if not args.profile:
                parser.error('apply requires original or touch2')
            apply_profile(args.profile,args.flipped,args.compact,args.rotation,args.touch_device,
                          None if args.cursor is None else args.cursor=='hidden')
            return 0
        if desktop.detect()!='wayfire':
            raise ValueError('Use the display wizard to configure touch on labwc.')
        before = WAYFIRE.read_text(encoding='utf-8')
        if args.action == 'touch-only':
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read_string(before)
            if len(displays) != 1 or not displays[0]['modes']:
                raise ValueError('Verwacht één aangesloten DSI-scherm met een geldige modus.')
            output, touch = check_hardware(dict(native=displays[0]['modes'][0]), displays, names, args.touch_device)
            section = f'input-device:{touch}'
            if cfg.has_section(section) and cfg[section].get('output') not in (None, output):
                raise ValueError('Bestaande touchkoppeling wijkt af; controleer eerst de configuratie.')
            after = edit_section(before, section, dict(output=output))
            if after != before:
                print('Touchkoppeling opgeslagen; back-up:', save_changes(after))
            else:
                print('Touchscreen is al correct gekoppeld.')
            return 0
    except (OSError, ValueError, KeyError, IndexError, SyntaxError, configparser.Error, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
