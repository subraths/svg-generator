import cairosvg


def save_png_from_svg(topic_slug, timestamp):
    svg_path = f"svg/{topic_slug}_{timestamp}.svg"
    png_path = f"img/{topic_slug}_{timestamp}.png"

    cairosvg.svg2png(
        url=svg_path,
        write_to=png_path,
        scale=2,  # ↑ try 2.0 or 3.0
        # or use explicit size:
        # output_width=1600,
        # output_height=900,
        background_color="white",  # set background to white (default is transparent
    )
