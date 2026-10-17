#!/usr/bin/env python3
"""Connect MacShell's original Snell lens to the niri-glass scene framebuffer."""
from pathlib import Path
import sys


def apply(source):
    shader = Path(source) / 'src/render_helpers/shaders/clipped_surface.frag'
    text = shader.read_text()
    marker = '// MacShell Snell lens, adapted from 0-ss/macshell'
    if marker in text:
        return
    snippet = (Path(__file__).resolve().parent.parent / 'config/macshell-refraction.glsl').read_text()
    if text.count('void main() {') != 1 or text.count('    if (effectMask > 0.0) {') != 1:
        raise RuntimeError('The pinned compositor shader changed; refusing an ambiguous optical patch')
    text = text.replace('void main() {', snippet + '\nvoid main() {')
    a = text.index('    if (effectMask > 0.0) {')
    b = text.index('    color = postprocess(color);', a)
    text = text[:a] + '    if (effectMask > 0.0) {\n        color = macshell_liquid_glass(v_coords, windowUV);\n    }\n\n' + text[b:]
    shader.write_text(text)


if __name__ == '__main__':
    apply(Path(sys.argv[1]))
