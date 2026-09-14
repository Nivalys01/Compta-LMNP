# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Générateur du sprite de l'assistante (outil de développement).

Pourquoi du PIXEL ART
---------------------
Une illustration dessinée « à la main » en courbes SVG demande un métier
que ce projet n'a pas : la première tentative était laide, et à juste
titre. Le pixel art contourne le problème — il est honnête sur sa
définition, lisible à petite taille, et se dessine sur une grille plutôt
qu'au trait. C'est la seule technique où l'on peut obtenir un résultat
correct sans savoir dessiner.

Pourquoi un générateur plutôt qu'un SVG écrit à la main
--------------------------------------------------------
Le sprite est décrit par une CARTE en caractères, lisible et modifiable
d'un coup d'œil : changer une couleur ou un pixel se fait dans la carte,
pas dans 200 balises <rect>. Le script fusionne ensuite les pixels voisins
de même couleur en rectangles — un sprite de 22x24 tombe ainsi de ~300
rectangles à moins de 120.

Le SVG produit est collé dans pages.py, qui doit rester de la présentation
PURE (aucun import, aucune fonction — un test le vérifie).

Lancer :  python outils_sprite.py          # aperçu texte + SVG
"""
from __future__ import annotations
PALETTE = {
    "K": "#14121c",   # contour, noir franc
    "A": "#e8e6ef",   # armure, clair
    "a": "#a8a6b8",   # armure, demi-teinte
    "d": "#6e6c82",   # armure, ombre
    "B": "#3a6ea8",   # tissu, bleu
    "b": "#26507d",   # tissu, ombre
    "V": "#2f8f5f",   # visière (la signature comptable)
    "v": "#57c98d",   # visière, reflet
    "G": "#f2c14e",   # or
    "g": "#b8862a",   # or, ombre
    "E": "#8ad8ff",   # regard
    "T": "#1e2b3d",   # écran de la tablette
    "l": "#8fb4e0",   # ligne de chiffres
    "j": "#f2c14e",   # ligne mise en avant
    "N": "#0f3320",   # tablette, fond validé
    "M": "#57c98d",   # tablette, coche
    "R": "#4a1410",   # tablette, fond alerte
    "r": "#ff8a72",   # tablette, signe d'alerte
}

# Carte du sprite — 22 colonnes × 24 lignes. « . » = transparent.
SPRITE = [
    "........KKKKKK..........",
    "......KKaaaaaaKK........",
    "....KKaAAAAAAAAaKK......",
    "..KKaaAAAAAAAAAAaaKK....",
    "..KaAAAAAAAAAAAAAAaK....",
    "..KaAVVVVVVVVVVVVAaK....",
    "..KaAvvvvvvvvvvvvAaK....",
    "..KKaaaaaaaaaaaaaaKK....",
    "....KddEEddddEEddK......",
    "....KddddddddddddK...KKK",
    ".....KKddddddddKK...KTTK",
    ".......KKddddKK.....KTTK",
    "...KKKKKGGGGGGKKKKK.KTTK",
    "..KAAAAKBBBBBBKAAAAKKKKK",
    "..KAaaAKBBGGBBKAaaAK....",
    "..KAaaAKBBGGBBKAaaAK....",
    "..KKKKKKBBBBBBKKKKKK....",
    "......KbBBBBBBbK........",
    "......KbbBBBBbbK........",
    "......KKbbbbbbKK........",
    "........KKKKKK..........",
]

# Zone de la tablette (superposée, change selon l'état). Coordonnées en
# pixels du sprite : x, y, largeur, hauteur.
TABLETTE = (21, 10, 2, 3)   # x, y, largeur, hauteur de l'écran

# Superpositions : seuls les pixels qui CHANGENT d'un état à l'autre. Le
# corps est dessiné une fois ; on ne repeint que l'écran de la tablette, la
# bouche et les sourcils. Trois états coûtent ainsi une trentaine de
# rectangles, pas trois sprites entiers.
ETATS = {
    "info": {
        (21, 10): "l", (22, 10): "l",
        (21, 11): "j", (22, 11): "T",
        (21, 12): "l", (22, 12): "l",
    },
    "valide": {
        (21, 10): "N", (22, 10): "M",
        (21, 11): "M", (22, 11): "N",
        (21, 12): "M", (22, 12): "N",
        (7, 8): "v", (8, 8): "v", (13, 8): "v", (14, 8): "v",
    },
    "anomalie": {
        (21, 10): "R", (22, 10): "r",
        (21, 11): "R", (22, 11): "r",
        (21, 12): "R", (22, 12): "r",
        (7, 8): "r", (8, 8): "r", (13, 8): "r", (14, 8): "r",
    },
}


def _rects(carte: list[str]) -> list[tuple[int, int, int, int, str]]:
    """Fusionne les pixels voisins de même couleur en rectangles.

    Fusion horizontale puis verticale : un aplat de 6x8 devient 1 rectangle
    au lieu de 48. Sans cela le SVG pèserait trois fois plus.
    """
    bandes: list[tuple[int, int, int, int, str]] = []
    for y, ligne in enumerate(carte):
        x = 0
        while x < len(ligne):
            c = ligne[x]
            if c == ".":
                x += 1
                continue
            fin = x
            while fin + 1 < len(ligne) and ligne[fin + 1] == c:
                fin += 1
            bandes.append((x, y, fin - x + 1, 1, c))
            x = fin + 1
    # fusion verticale des bandes identiques et contiguës
    fusionnes: list[list] = []
    for x, y, w, h, c in bandes:
        for prec in fusionnes:
            if (prec[0] == x and prec[2] == w and prec[4] == c
                    and prec[1] + prec[3] == y):
                prec[3] += 1
                break
        else:
            fusionnes.append([x, y, w, h, c])
    return [tuple(r) for r in fusionnes]


def apercu(carte: list[str]) -> str:
    """Rendu texte, pour vérifier la silhouette sans navigateur."""
    return "\n".join(
        "".join("██" if c != "." else "  " for c in ligne) for ligne in carte)


def svg(carte: list[str], indent: str = "      ") -> str:
    lignes = []
    for x, y, w, h, c in _rects(carte):
        lignes.append(f'{indent}<rect x="{x}" y="{y}" width="{w}" '
                      f'height="{h}" fill="{PALETTE[c]}"/>')
    return "\n".join(lignes)


def svg_complet() -> str:
    """SVG prêt à coller dans pages.py : corps + trois superpositions."""
    larg, haut = len(SPRITE[0]), len(SPRITE)
    out = [f'  <svg class="perso" viewBox="0 0 {larg} {haut}" '
           'xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges"',
           '       role="img" aria-hidden="true">',
           '    <g class="corps">',
           svg(SPRITE, "      "),
           '    </g>']
    for nom, pixels in ETATS.items():
        vide = ["." * larg for _ in range(haut)]
        carte = [list(ligne) for ligne in vide]
        for (x, y), c in pixels.items():
            carte[y][x] = c
        out.append(f'    <g class="sur-{nom}">')
        out.append(svg(["".join(x) for x in carte], "      "))
        out.append('    </g>')
    out.append('  </svg>')
    return "\n".join(out)


def main() -> None:
    print(apercu(SPRITE))
    r = _rects(SPRITE)
    pleins = sum(1 for ligne in SPRITE for c in ligne if c != ".")
    print(f"\n{pleins} pixels → {len(r)} rectangles "
          f"({100 - round(len(r) / pleins * 100)} % d'économie)")
    print(f"grille : {len(SPRITE[0])} × {len(SPRITE)}")
    print("\n--- SVG ---")
    print(svg_complet())


if __name__ == "__main__":
    main()
