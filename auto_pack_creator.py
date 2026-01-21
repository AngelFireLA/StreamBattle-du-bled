import os

from bing_image_downloader import downloader
from custom_image_recuperation import safe_name
import sqlite3

#pack format:
# new_pack = Pack(
#     name=pack_name,
#     categories=pack_category,
#     preview='',  # Temporarily empty
#     all_images='',  # Temporarily empty
#     user_id=current_user.id,
#     private=is_private,
#     authorized_users=str(authorized_users_ids)
# )

def download_pack(keyword_names, keyword_list: list, download_path='auto_packs'):
    #make folder for keyword names
    os.mkdir(download_path+"/"+keyword_names)
    keyword_paths = download_path+"/"+keyword_names
    for keyword in keyword_list:
        downloader.download(keyword, limit=1, output_dir=download_path, timeout=20)

        bing_folder_path = os.path.join(download_path, keyword)
        image = os.listdir(bing_folder_path)[0]
        new_file_name = f'{keyword}.{image.split(".")[-1]}'

        os.rename(os.path.join(bing_folder_path, image), os.path.join(keyword_paths, new_file_name))

        os.rmdir(bing_folder_path)

villes_du_monde = ["Paris", "Tokyo", "New York", "Dubai", "Sydney", "Rio de Janeiro", "Moscou", "Le Caire", "Londres", "Shanghai"]
download_pack("villes",villes_du_monde)

