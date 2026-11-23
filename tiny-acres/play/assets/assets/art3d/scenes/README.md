# Scenes: the 3D look's scenery

The painted scenery round the boards, in concept B's style
(docs/design/worlds-art-plan.md, "Home and other screens"). Each folder is
one screen's scenery, listed on its own in `app/pubspec.yaml` (Flutter's
asset folders are not recursive). The app loads `home/`'s hills and clouds with
the art kit before its first frame (`ArtKit.load`), and the play screen's
countryside and the hero island just after it (`KitScene.more`); without
them (tests that do not load the kit) the hills are two plain ridges in the
same greens and the clouds drawn shapes (`HillsPainter`, `CloudPainter`).

| Folder | Screen | Owner |
|---|---|---|
| `home/` | home: its hills, its big drifting clouds, the hero island (island A) and its pictures by hour and season | lane D |
| `play/` | the play screen: the countryside behind the see-through board (version 2) | lane D |
| `path/` | Worlds' path: each area's hills, weather sprites | lane A |

## Format

`scene.json`, version 1:

```json
{
 "version": 1,
 "screen": "home",
 "hills": {"image": "hills.webp", "size": [2048, 455], "ground": "#6B9D51"},
 "clouds": {"image": "clouds.webp", "sprites": {"cloud-wide": [x, y, w, h]}}
}
```

- **hills:** a strip of painted scenery, transparent above it, as wide as the
  screen it is drawn on: scaled to the screen's width, its bottom on the top
  of the ground band. `ground` is the colour of its bottom rows, for the
  ground band under it. In the hour's light: drawn through the hour's
  `HillTint` as a colour matrix (`BoardGround.matrixOf`), as the island is.
  2048 px wide (sharp on a 3x phone up to about 680 dp wide). The layout
  takes its height from the shipped size (`HillsPainter.aspectOf`, kept
  in step by `test/features/home_sky_test.dart`).
- **clouds:** sprites in one image, by name (`cloud-wide`, `cloud-tall`,
  `cloud-small`): white with a pale blue-grey underside; the sky's dark and
  night looks tint them (`CloudPainter`).
- WebP with alpha; `scene.json` names every image.

### Version 2: the play screen's countryside (UI direction A's play mock-up)

```json
{
 "version": 2,
 "screen": "play",
 "layers": [{"image": "far.webp", "size": [1600, 301], "bottom": 0.46, "haze": 0.42, "solid": 0.3}, ...],
 "windmill": {"tower": "windmill-tower.webp", "sails": "windmill-sails.webp",
              "layer": 0, "x": 0.11, "ground": 0.106, "height": 0.15, "hub": [0.29, 0.28]},
 "ground": "#686E3B"
}
```

- **layers:** painted strips, far to near, each drawn as wide as the box behind
  the board, its bottom at `bottom` of the box's height, blended `haze` of the
  way into the sky's colour (and a little greyer), then into the hour's light.
  `solid` is the share of the strip, from its top, that is skyline (see-through
  in places); below it the strip is solid, so the strip behind it is drawn
  reaching down at least that far (lower than its `bottom` where it must: a
  tall phone shows more sky, never a band of it between two strips). Written
  by `life_sprites.py wood`; 0.5 where it is missing.
  The app draws them, the windmill's tower and the sun's rays once per size and
  hour as one image (`CountrysideStill`).
- **windmill:** its tower stands on layer `layer`'s skyline at `x` of the width
  (`ground`: the skyline's height in that layer, from its top), `height` of the
  box's width tall; the sails turn round `hub` (a share of the tower picture).
- **ground:** the colour along the near strip's bottom (the tray's grass).
- The strips and the windmill decode after the app's first frame
  (`KitScene.more`); until then the play screen shows its plain hills.

### The home's hero island (`hero` in home/scene.json)

```json
"hero": {"image": "hero.webp", "size": [1080, 842], "widest": [0.3682, 0.0009, 0.9954],
         "rock": false, "shows": 0.62, "width": 0.96,
         "life": {"image": "hero-life.webp", "sprites": {}},
         "variants": {"sunset": {"image": "hero-sunset.webp", "life": "hero-life-sunset.webp"},
                      "night": {...}, "winter": {...}},
         "pieces": {"boat": {"sprite": [x, y, w, h], "move": "bob", "at": [x, y], "size": [w, h]},
                    "duck-1": {..., "move": "waddle"}, "sheep-1": {..., "move": "graze"}, ...},
         "spots": [[x, y, most], ...]}
```

Island A (2026-11-23): the clay home concept's own floating island, cut from
its pixels, with its own rock and roots (`rock: false`: no underside is
drawn under it). `variants` are the same island repainted for sunset, night
and winter, lined up with the day's picture, each with its own life sheet;
the app holds one at a time (`KitHero.show`). `pieces` are the boat, three
ducks and three sheep, lifted out of every picture in the same places and
drawn back over it moving (`HeroLife`): `sprite` in the life sheet, `at`
its top-left corner and `size`, shares of the picture. `widest` is the
island's widest line (its height, left and right ends); `shows` how far down
the island must show when the room under the home's cards is short; `width`
its width on a phone, a share of the screen's; `spots` where the season's
decorations may float clear of the island in every picture (middle, and the
most a piece there may measure, shares of the picture's width). The app
still reads the older render's life (`sheep`, `ducks`, `cart`, `smoke`,
`scale`, sprites by name), which nothing ships now.

A finished acre on its island, rendered from the kit's own scene
(`board_scene.py --transparent 1`), drawn as wide as the phone's screen just
under the cards (`HeroIsland`), the play scene's rock hanging from its
`widest` line (its height, left and right ends). Its life's places come from
the render's probe: sheep graze on its meadows, ducks paddle round their
spots (`r` the ring's radius), the pony and cart go between the two `cart`
ends, smoke rises from the `smoke` chimneys; all shares of the image's width
and height, `scale` a sheep's height as a share of its width.

## How they are made

`tools/art3d/life_sprites.py`: Gemini 3 Pro Image paints the hills on a
flat magenta key and the clouds on a flat green key, in concept B's style;
`scene` keys them out, keeps only what stands on the picture's bottom edge
(Gemini sometimes adds a faded copy of a strip above it), fills half
see-through patches, trims, scales to 2048 px and writes `scene.json`:

    python3 -I tools/art3d/life_sprites.py draw STYLE_REF.jpg OUT hills-home clouds-home
    BPY=/Applications/Blender.app/Contents/Resources/5.3/python/bin/python3.13
    $BPY -I tools/art3d/life_sprites.py scene home OUT/hills-home.jpg OUT/clouds-home.jpg SCENE_DIR

then `cwebp -q 84 -alpha_q 90 -m 6` each PNG into this folder. A Blender
render works as well, as long as it ends as the same strip and json.

The play screen's version 2 (the strips and the windmill):

    python3 -I tools/art3d/life_sprites.py draw STYLE_REF.jpg OUT wood-far wood-mid wood-near wood-windmill
    $BPY -I tools/art3d/life_sprites.py wood OUT SCENE_DIR

The style reference is a crop of the A concept's scenery.

The hero island (island A) is made in the art repo's `scenes/home/hero-a/`
(its README): `cut_orig.py` cuts the island out of the concept, `variants.py`
asks Gemini 3 Pro Image for the sunset, night and winter edits on magenta,
`register_variants.py` keys them and lines them up with the day's picture,
and `make_hero.py` lifts the pieces out and writes the pictures, the life
sheets and their places at 1080 px; then `cwebp` each PNG into `home/`.
