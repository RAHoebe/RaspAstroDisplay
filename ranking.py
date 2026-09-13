"""Explainable photographic heuristics, not a calibrated success probability."""
import math


def clamp(value):
    return max(0., min(1., value))


def recommendation(target, scope, window='night'):
    altitude = target.get('altitude') if window == 'now' else target.get('best_altitude')
    duration = target.get('night_minutes_30', 0)
    height = clamp(((altitude or 0) - 10) / 55)
    visibility = height if window == 'now' else .7 * height + .3 * clamp(duration / 120)
    reasons = [('nu hoog' if window == 'now' else f'{duration} min boven 30°') if height > .5 else 'laag boven horizon']
    if window != 'now' and not duration:
        reasons[0] = 'geen lang venster boven 30°'
    major, minor = target.get('major'), target.get('minor')
    size = .45
    if major:
        # Compare both dimensions without claiming an actual camera orientation.
        long, short = sorted([scope['width'] * 60, scope['height'] * 60], reverse=True)
        extent = major / long
        overflow = max(extent, (minor or major) / short)
        size = min(1., extent / .18) * (1. if overflow <= .9 else max(.1, .9 / overflow) ** 2)
        reasons.append('erg klein' if extent < .06 else 'groter dan één kader' if overflow > 1 else 'bruikbare beeldvulling ≈')
    else:
        reasons.append('afmeting onbekend')
    magnitude = target.get('magnitude')
    brightness = .45
    if magnitude is not None and target.get('kind') != 'Donkere nevel':
        total = clamp((13 - magnitude) / 8)
        # Mean V surface brightness is only a rough estimate for extended objects.
        # Star clusters have resolved stars; don't treat their empty area as nebulosity.
        if target.get('category') in ('nebula', 'galaxy') and major and minor:
            mu = magnitude + 2.5 * math.log10(math.pi * major * minor * 900)
            brightness = .4 * total + .6 * clamp((25 - mu) / 7)
            reasons.append('helderheid + spreiding ≈')
        else:
            brightness = total
            reasons.append('helder' if total > .65 else 'zwak' if total < .3 else 'gemiddelde helderheid')
    else:
        reasons.append('helderheid onbekend')
    score = 100 * (.4 * visibility + .3 * size + .3 * brightness)
    # Low targets and sub-frame specks cannot become top candidates through brightness alone.
    score *= .4 + .6 * height
    score *= .35 + .65 * size
    if target.get('category') in ('planet', 'moon'):
        score *= .15
    return dict(score=round(score, 3), reasons=reasons,
                limited=not major or magnitude is None,
                basis='nu' if window == 'now' else 'komende nacht')
