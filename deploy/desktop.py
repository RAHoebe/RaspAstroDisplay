"""Desktop adapters for Raspberry Pi OS Wayfire and labwc."""
import subprocess
import xml.etree.ElementTree as ET

MATRICES = {'normal': '1 0 0 0 1 0', '90': '0 -1 1 1 0 0',
            '180': '-1 0 1 0 -1 1', '270': '0 1 0 -1 0 1'}


def detect():
    for name in ('wayfire', 'labwc'):
        if subprocess.run(['pgrep', '-x', name], stdout=subprocess.DEVNULL).returncode == 0:
            return name
    raise ValueError('Start a Wayfire or labwc desktop session before configuring the display.')


def labwc_config(text, output, touch, rotation, cursor=None):
    root = ET.fromstring(text or '<labwc_config/>', parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    ns = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
    def tag(name):
        return ns+name
    def child(parent, name):
        found = parent.find(tag(name))
        return found if found is not None else ET.SubElement(parent,tag(name))
    current = next((node for node in root.findall(tag('touch'))
                    if node.get('deviceName',node.findtext(tag('deviceName'))) == touch), None)
    if current is None:
        current = ET.SubElement(root,tag('touch'))
    for old in list(current):
        if old.tag in (tag('deviceName'),tag('mapToOutput')):
            current.remove(old)
    current.set('deviceName',touch)
    current.set('mapToOutput',output)
    libinput = child(root,'libinput')
    device = next((node for node in libinput.findall(tag('device')) if node.get('category') == touch),None)
    if device is None:
        device = ET.SubElement(libinput,tag('device'),dict(category=touch))
    child(device,'calibrationMatrix').text = MATRICES[rotation]
    if cursor is not None:
        child(child(root,'theme'),'cursorTheme').text = 'AstroInvisible' if cursor else 'Adwaita'
    ET.indent(root,space='  ')
    return ET.tostring(root,encoding='unicode')+'\n'
