import os
import re
import shutil

import instaloader
from bing_image_downloader import downloader
from flask import Blueprint, request, jsonify

custom_image_recuperation = Blueprint('custom_image_recuperation', __name__)

count_by_images = False  # if instagram image downloader downloads posts or individual images


def download_instagram_images(username, max_images=None):
    loader = instaloader.Instaloader(download_comments=False,
                                     download_videos=False,
                                     download_video_thumbnails=False,
                                     download_geotags=False,
                                     save_metadata=False,
                                     post_metadata_txt_pattern='',
                                     filename_pattern='{date_utc}_UTC')
    p = instaloader.Profile.from_username(loader.context, username)

    image_count = 0

    for post in p.get_posts():
        if not post.is_video:
            # If the post is an image
            if max_images is None or image_count < max_images:
                # Download the image
                loader.download_post(post, target=p.username)
                image_count += 1
                if max_images is not None and image_count >= max_images:
                    break
    if count_by_images:
        # Clean-up: Remove images that don't end with UTC or UTC_1
        for image_file in os.listdir(username):
            if not re.search(r'UTC(_1)?\.(jpg|jpeg|png)$', image_file):
                os.remove(os.path.join(username, image_file))


def download_bing_images(search_term, number_of_images, download_path=''):
    """
    Downloads a specified number of images using Bing Image Downloader.

    :param search_term: The search term for the images you want to download.
    :param number_of_images: The number of images to download.
    :param download_path: The directory path where the images will be saved. Defaults to 'downloaded_images'.
    """
    print(download_path, number_of_images, search_term)
    downloader.download(search_term, limit=number_of_images, output_dir=download_path)


@custom_image_recuperation.route('/download-instagram', methods=['POST'])
def download_instagram_images_route():
    username = request.form['username']
    max_images = int(request.form['count'])
    if max_images == 69:
        print("downloading every image")
        max_images = None
    # Use the download_images function to download images
    download_instagram_images(username, max_images)

    # The path where downloaded images are stored
    instagram_folder_path = os.path.join(os.getcwd(), username)

    # Target path to move images to
    target_folder_path = os.path.join(custom_image_recuperation.static_folder, 'images')

    # Moving the images to the 'images' folder
    for image_file in os.listdir(instagram_folder_path):
        source_path = os.path.join(instagram_folder_path, image_file)
        target_path = os.path.join(target_folder_path, image_file)
        shutil.move(source_path, target_path)

    # Remove the now-empty Instagram folder
    shutil.rmtree(instagram_folder_path)

    return jsonify({'status': 'downloaded'})


@custom_image_recuperation.route('/download-bing', methods=['POST'])
def download_bing_images_route():
    keywords = request.form['keywords']
    max_images = int(request.form['count'])

    # Target path to move images to
    target_folder_path = os.path.join(custom_image_recuperation.static_folder, 'images')

    # Use the download_images function to download images
    download_bing_images(keywords, max_images, target_folder_path)
    instagram_folder_path = os.path.join(target_folder_path, keywords)
    for image_file in os.listdir(instagram_folder_path):
        source_path = os.path.join(instagram_folder_path, image_file)
        target_path = os.path.join(target_folder_path, image_file)
        shutil.move(source_path, target_path)

    # Remove the now-empty Instagram folder
    shutil.rmtree(instagram_folder_path)
    return jsonify({'status': 'downloaded'})