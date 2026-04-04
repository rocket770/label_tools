def get_label_display_rgb(color_table, label_val):
    color = color_table[int(label_val) % len(color_table)]
    return int(color[0]), int(color[1]), int(color[2])


def format_label_text(label_val):
    return f"{int(label_val)}"