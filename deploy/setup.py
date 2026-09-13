"""Generate portable services and desktop autostart for the current Linux user."""
import getpass
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

try:
    from . import desktop
    from .display import edit_section
    from .cursor import install_theme
except ImportError:
    import desktop
    from display import edit_section
    from cursor import install_theme

ROOT=Path(__file__).resolve().parents[1]
HOME=Path.home()


def quoted(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'


def run(*args):
    subprocess.run(args,check=True)


def install():
    backend=desktop.detect()
    account=getpass.getuser()
    state=HOME/'.local/share/astro-panel'
    state.mkdir(parents=True,exist_ok=True)
    user_units=HOME/'.config/systemd/user'
    user_units.mkdir(parents=True,exist_ok=True)
    service=(ROOT/'deploy/astro-panel.service').read_text()
    service=service.replace('@@USER@@',account).replace('@@ROOT@@',quoted(ROOT))
    service=service.replace('@@STATE_ENV@@',quoted('ASTRO_STATE='+str(state)))
    service=service.replace('@@PYTHON@@',quoted(ROOT/'.venv/bin/python')).replace('@@APP@@',quoted(ROOT/'app.py'))
    with tempfile.TemporaryDirectory() as temp:
        file=Path(temp)/'astro-panel.service'
        file.write_text(service)
        run('sudo','install','-m','644',str(file),'/etc/systemd/system/astro-panel.service')
    kiosk=(ROOT/'deploy/astro-kiosk.service').read_text().replace('@@KIOSK@@',quoted(ROOT/'deploy/kiosk.sh'))
    (user_units/'astro-kiosk.service').write_text(kiosk)
    for name in ('kiosk.sh','start-kiosk.sh','install-solver.sh'):
        (ROOT/'deploy'/name).chmod(0o755)
    command=shlex.quote(str(ROOT/'deploy/start-kiosk.sh'))
    theme=install_theme()
    if backend=='wayfire':
        config=HOME/'.config/wayfire.ini'
        before=config.read_text() if config.exists() else ''
        if config.exists():
            shutil.copy2(config,config.with_suffix('.ini.astro-backup'))
        after=edit_section(before,'autostart',dict(astro=command,screensaver='false',dpms='false'))
        after=edit_section(after,'input',dict(cursor_theme=theme))
        config.write_text(after)
    else:
        folder=HOME/'.config/labwc'
        folder.mkdir(parents=True,exist_ok=True)
        autostart=folder/'autostart'
        before=autostart.read_text() if autostart.exists() else '#!/bin/sh\n'
        if autostart.exists():
            shutil.copy2(autostart,folder/'autostart.astro-backup')
        lines=[line for line in before.splitlines() if not line.endswith('# astro-panel')]
        lines.append(command+' & # astro-panel')
        autostart.write_text('\n'.join(lines)+'\n')
    run('sudo','systemctl','daemon-reload')
    run('sudo','systemctl','enable','--now','astro-panel')
    run('sudo','systemctl','restart','astro-panel')
    run('systemctl','--user','daemon-reload')
    print('Installed for',account,'using',backend)
    print('Run the display wizard now: python3 deploy/display.py wizard')


if __name__=='__main__':
    install()
