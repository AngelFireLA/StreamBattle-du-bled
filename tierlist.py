import json
import os

from PIL import Image

def load_images(tiers, size=(150, 150)):
    tier_images = {}
    for tier, filenames in tiers.items():
        loaded_images = []
        for filename in filenames:
            img = Image.open("static/images/"+filename)
            img = img.resize(size)  # Resize to desired dimensions
            loaded_images.append(img)
        tier_images[tier] = loaded_images
    return tier_images


from PIL import Image, ImageDraw, ImageFont

from PIL import Image, ImageDraw, ImageFont
import colorsys


def generate_colors(n):
    # Generate colors using HSV color space and convert them to RGB
    hues = [x * (1.0 / n) for x in range(n)]
    colors = [tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, 0.5, 0.5)) for h in hues]
    return colors


def create_tier_list(tier_images, image_size=(150, 150), line_height=5):
    # Generate tier labels and colors
    tier_labels = list(tier_images.keys())
    tier_colors = generate_colors(len(tier_labels))

    # Set dimensions for the tier list image
    label_width = 50
    spacing = 10
    tier_height = image_size[1] + spacing * 2
    background_color = (30, 30, 30)  # Dark background for contrast
    tier_line_color = (60, 60, 60)  # Dark gray for lines

    # Determine the width and height of the full image
    max_images = max(len(images) for images in tier_images.values())
    width = max_images * (image_size[0] + spacing) + label_width
    height = len(tier_images) * tier_height

    # Create a new image with a dark background
    tier_list_img = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(tier_list_img)

    # Font settings (may require adjustment)
    try:
        font = ImageFont.truetype("arial.ttf", size=24)
    except IOError:
        font = ImageFont.load_default()

    y_offset = spacing  # Start spacing pixels from the top

    # Draw tiers, labels, and images
    for tier, color in zip(tier_labels, tier_colors):
        # Draw the tier label box
        draw.rectangle((0, y_offset, label_width, y_offset + image_size[1]), fill=color)
        # Draw the tier label text
        draw.text((label_width / 4, y_offset + image_size[1] / 3), str(tier), fill=(255, 255, 255), font=font)

        x_offset = label_width + spacing  # Start after the label
        for img in tier_images[tier]:
            # Paste the image into the tier list
            tier_list_img.paste(img, (x_offset, y_offset))
            x_offset += image_size[0] + spacing  # Move to the next image slot

        # Draw a dividing line between tiers
        draw.line((0, y_offset + tier_height - line_height, width, y_offset + tier_height - line_height),
                  fill=tier_line_color, width=line_height)
        y_offset += tier_height  # Move to the next tier row

    return tier_list_img


def convert_to_rankings(image_list):
    rankings = []
    for item in image_list:
        # Find if the rank already exists in the rankings list
        existing_rank = next((rank for rank in rankings if rank['rank'] == item['rank']), None)

        if existing_rank is None:
            # If the rank doesn't exist, add a new entry
            rankings.append({'rank': item['rank'], 'images': [item['file']]})
        else:
            # If the rank exists, append the file to the images list
            existing_rank['images'].append(item['file'])
    # Sorting the list based on rank
    rankings.sort(key=lambda x: x['rank'])
    return rankings

def convert_rankings(rankings):
    converted_rankings = {}
    for ranking in rankings:
        if ranking["rank"] in converted_rankings:
            for image in ranking["images"]:
                converted_rankings[ranking["rank"]].append(image)
        else:
            converted_rankings[ranking["rank"]] = ranking["images"]
    return converted_rankings

