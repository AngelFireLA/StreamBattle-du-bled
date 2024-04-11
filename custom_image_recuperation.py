import io
import os
import re
import shutil
import time
from urllib.request import urlopen

import instaloader
import requests
from bing_image_downloader import downloader
from flask import Blueprint, request, jsonify
import uuid

from flask_login import current_user

import shared
from class_utils import User

custom_image_recuperation = Blueprint('custom_image_recuperation', __name__, static_folder="static", template_folder="templates")

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
    downloader.download(search_term, limit=number_of_images, output_dir=download_path)

def safe_name(image_name:str, type_of_image:str)-> str:
    #rename an image with the original with the type of image, the original name of the image, and a way to not make it overwrite a previous image, making the name unique
    timestamp = int(time.time() * 1000)
    unique_id = uuid.uuid4()
    safe_image_name = f"{type_of_image}_{image_name}_{timestamp}_{unique_id}.png"
    return safe_image_name


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
    user = User.query.get(current_user.id)
    # Moving the images to the 'images' folder
    for image_file in os.listdir(instagram_folder_path):

        source_path = os.path.join(instagram_folder_path, image_file)
        safe_image_file = safe_name(image_file, "instagram_"+username)
        target_path = os.path.join(target_folder_path, safe_image_file)
        shutil.move(source_path, target_path)
        if user.current_images:
            user.current_images += ',' + safe_image_file
        else:
            user.current_images = image_file
    shared.db.session.commit()
    # Remove the now-empty Instagram folder
    shutil.rmtree(instagram_folder_path)

    return jsonify({'status': 'downloaded'})

def mal_request(pseudo):
    CLIENT_ID = '5a433618d10417e64a676117051f6c86'

    url = f'https://api.myanimelist.net/v2/users/{pseudo}/animelist?fields=list_status&limit=999&status=completed'

    response = requests.get(url, headers={
        'X-MAL-CLIENT-ID': CLIENT_ID
    })

    response.raise_for_status()
    anime_list = response.json()
    response.close()
    return anime_list

def get_score(anime: list):
    return int(anime["list_status"]["score"])


def get_name(anime: list):
    return anime["node"]["title"]

def getanimes(pseudo) -> dict:
    anime_list = mal_request(pseudo)
    actual_anime_list = {}
    for anime in anime_list['data']:
        actual_anime_list[get_name(anime)] = anime
    actual_anime_list = dict(sorted(actual_anime_list.items(), key=lambda x: get_score(x[1]), reverse=True))
    return actual_anime_list


def get_images(pseudo):
    actual_anime_list = list(getanimes(pseudo).values())
    anime_covers = {}
    for anime in actual_anime_list:
        anime_covers[get_name(anime)] = anime["node"]["main_picture"]["medium"]
    return anime_covers

def get_image_from_web(link):
    image_str = urlopen(link).read()
    image_file = io.BytesIO(image_str)
    return image_file


def download_mal_images(username, max_images=None):
    i = 0
    user = User.query.get(current_user.id)
    for k, v in get_images(username).items():
        if i == max_images:
            break
        i += 1
        image_object = get_image_from_web(v)
        image_name = v.split('/')[-1]

        safe_image_name = safe_name(image_name, "mal")

        save_path = os.path.join(custom_image_recuperation.static_folder, "images", safe_image_name)

        with open(save_path, "wb") as f:
            f.write(image_object.getbuffer())
        if user.current_images:
            user.current_images += ',' + safe_image_name
        else:
            user.current_images = safe_image_name
    shared.db.session.commit()
@custom_image_recuperation.route('/download-mal', methods=['POST'])
def download_mal_images_route():
    username = request.form['username']
    max_images = int(request.form['count'])
    if max_images == 69:
        print("downloading every image")
        max_images = None
    # Use the download_images function to download images
    download_mal_images(username, max_images)

    return jsonify({'status': 'downloaded'})


@custom_image_recuperation.route('/download-bing', methods=['POST'])
def download_bing_images_route():
    keywords = request.form['keywords']
    max_images = int(request.form['count'])

    # Target path to move images to
    target_folder_path = os.path.join(custom_image_recuperation.static_folder, 'images')

    # Use the download_images function to download images
    download_bing_images(keywords, max_images, target_folder_path)
    bing_folder_path = os.path.join(target_folder_path, keywords)
    user = User.query.get(current_user.id)
    # Moving the images to the 'images' folder
    for image_file in os.listdir(bing_folder_path):

        source_path = os.path.join(bing_folder_path, image_file)
        safe_image_file = safe_name(image_file, "instagram_" + keywords)
        target_path = os.path.join(target_folder_path, safe_image_file)
        if user.current_images:
            user.current_images += ',' + safe_image_file
        else:
            user.current_images = safe_image_file
        shutil.move(source_path, target_path)
    shared.db.session.commit()

    # Remove the now-empty Instagram folder
    shutil.rmtree(bing_folder_path)
    return jsonify({'status': 'downloaded'})