import cairosvg


def save_png_from_svg(topic_slug: str, timestamp: str):
    cairosvg.svg2png(
        url=f"svg/{topic_slug}_{timestamp}.svg",
        write_to=f"img/{topic_slug}_{timestamp}.png",
    )
