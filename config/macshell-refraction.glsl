// MacShell Snell lens, adapted from 0-ss/macshell liquidglass.frag at a05e0dc.
// Original slab geometry, squircle normal, Snell refraction and RGB dispersion.
// The input is niri's current framebuffer UNDER the pane, not wallpaper or a screenshot.
// Tint, grain and highlights remain in MacShell's QML foreground shader.
float macshell_round_box(vec2 q, vec2 hs, float r) {
    vec2 d = abs(q) - (hs - r);
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r;
}

vec2 macshell_texture_offset(vec2 logicalDelta) {
    vec2 delta = logicalDelta / geo_size;
    // Convert geometry-space displacement back to the sampled texture's coordinates.
    // This also handles rotated outputs, texture flips and cropped panes.
    float a = input_to_geo[0][0], b = input_to_geo[1][0];
    float c = input_to_geo[0][1], d = input_to_geo[1][1];
    float determinant = a * d - b * c;
    if (abs(determinant) < 0.000001) return vec2(0.0);
    return vec2(d * delta.x - b * delta.y, -c * delta.x + a * delta.y) / determinant;
}

vec4 macshell_liquid_glass(vec2 textureUV, vec2 paneUV) {
    float strength = clamp(lg_refraction_strength / 2.2, 0.0, 4.0);
    vec2 hs = geo_size * 0.5;
    vec2 p = paneUV * geo_size;
    vec2 q = p - hs;
    float radius = min(corner_radius.x, min(hs.x, hs.y));
    float sd = macshell_round_box(q, hs, radius);
    float t = max(-sd, 0.0);
    vec2 d2 = abs(q) - (hs - radius);
    vec2 sg = vec2(q.x >= 0.0 ? 1.0 : -1.0, q.y >= 0.0 ? 1.0 : -1.0);
    vec2 m = max(d2, 0.0);
    vec2 g = length(m) > 0.0001 ? normalize(m) * sg
        : (d2.x > d2.y ? vec2(sg.x, 0.0) : vec2(0.0, sg.y));
    float bz = max(min(geo_size.y * 0.36, 26.0), 1.0) * 1.45;
    float u = clamp(t / bz, 0.0, 1.0);
    float om = 1.0 - u;
    float om4 = om * om * om * om;
    float slope = (om * om * om) / pow(max(1.0 - om4, 0.001), 0.75);
    slope = min(slope, 7.0);
    vec3 normal = normalize(vec3(g * slope, 1.0));
    vec3 ray = refract(vec3(0.0, 0.0, -1.0), normal, 1.0 / 1.5);
    vec2 displacement = ray.xy / max(-ray.z, 0.2) * (24.0 * 1.6 * strength) * 1.35;
    vec2 lens = vec2(0.0, (p.y - hs.y) * (-0.05 * strength * 1.6 * 1.5));
    float dispersion = 0.06 * strength * 1.3 * 0.6;
    vec2 redUV = clamp(textureUV + macshell_texture_offset(lens + displacement * (1.0 + dispersion)), vec2(0.001), vec2(0.999));
    vec2 greenUV = clamp(textureUV + macshell_texture_offset(lens + displacement), vec2(0.001), vec2(0.999));
    vec2 blueUV = clamp(textureUV + macshell_texture_offset(lens + displacement * (1.0 - dispersion)), vec2(0.001), vec2(0.999));
    vec4 green = texture2D(tex, greenUV);
    return vec4(texture2D(tex, redUV).r, green.g, texture2D(tex, blueUV).b, green.a);
}
