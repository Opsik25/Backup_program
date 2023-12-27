import configparser
import json
import time
from datetime import datetime
from pprint import pprint

import requests
from tqdm import tqdm


class VkToYDiscAPISaver:
    """
    VkToYDiscAPISaver class is used to download required quantity of photos from certain folder at VK
    and upload them to Yandex.Disk by API VK and Yandex.Disk.
    """

    VK_API_BASE_URL = 'https://api.vk.com/method'

    def __init__(self, tokens, user_id, quantity_of_photos, album_id):
        self.token_vk = tokens['token_vk']
        self.token_ydisk = tokens['token_yandex_disk']
        self.user_id = user_id
        self.quantity_of_photos = quantity_of_photos
        self.album_id = album_id
        self.headers_ydisk_auth = {'Authorization': self.token_ydisk}
        self.y_disk_link_for_upload = 'https://cloud-api.yandex.net/v1/disk/resources/upload'

    def _get_common_params_for_vk(self):
        """Get a dict of params to communicate with API VK."""
        return {
            'access_token': self.token_vk,
            'v': '5.199',
            'owner_id': self.user_id,
            'album_id': self.album_id,
            'rev': 1,
            'extended': 1,
            'count': self.quantity_of_photos
        }

    def _create_folder_ydisk(self):
        """Create a folder named 'Фото из ВК' at Yandex.Disk."""
        ydisk_url_create_folder = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {'path': 'Фото из ВК'}
        requests.put(ydisk_url_create_folder, params=params, headers=self.headers_ydisk_auth)

    def _get_photos(self):
        """Get required photos form VK page."""
        params = self._get_common_params_for_vk()
        response = requests.get(f'{self.VK_API_BASE_URL}/photos.get', params=params)
        return response.json()

    def _name_photos(self):
        """Name received photos by likes and date of publication.

        Key arguments:
        photos -- a raw dict of received from VK photos.
        """
        photos = self._get_photos()
        photos_info = []
        photos_likes = []
        for photo in photos.get('response').get('items'):
            each_photo = {}
            biggest_photo = sorted(photo.get('sizes'), key=lambda i: i['height'])[-1]
            each_photo['url'] = biggest_photo.get('url')
            each_photo['size_type'] = biggest_photo.get('type')
            each_photo['likes'] = photo.get('likes').get('count')
            each_photo['date'] = datetime.fromtimestamp(photo.get('date')).strftime('%d-%m-%Y')
            photos_likes.append(each_photo['likes'])
            photos_info.append(each_photo)
        for photo in photos_info:
            if photos_likes.count(photo['likes']) > 1:
                photo['name'] = f'{photo['likes']}, {photo['date']}'
            else:
                photo['name'] = f'{photo['likes']}'
        return photos_info

    def save_photos(self):
        """Save named required photos to the folder at Yandex.Disk.

        Key arguments:
        photos_info -- a prepared dict of photos from VK with name, url, likes, date of publication and size type.
        errors_list -- a list of unloaded to Yandex.Disk photos.
        json_value -- a list of uploaded to Yandex.Disk photos to create a result .json-file.
        """
        self._create_folder_ydisk()
        photos_info = self._name_photos()
        errors_list = []
        json_value = []
        for photo in tqdm(photos_info, ncols=60 + len(photos_info), ascii=' █', desc='Loading', colour='green'):
            errors_count = 0
            params = {
                'url': photo.get('url'),
                'path': f'Фото из ВК/{photo.get('name')}'
            }
            while True:
                if errors_count == 10:
                    errors_list.append(photo)
                    break
                response = requests.post(self.y_disk_link_for_upload, params=params, headers=self.headers_ydisk_auth)
                while True:
                    time.sleep(0.5)
                    status = requests.get(response.json().get('href'), headers=self.headers_ydisk_auth)
                    if status.json().get('status') != 'in-progress':
                        break
                if status.json().get('status') == 'failed':
                    errors_count += 1
                    continue
                elif status.json().get('status') == 'success':
                    json_info_photo = {
                        'file_name': f'{photo['name']}.jpg',
                        'size': photo['size_type']
                    }
                    json_value.append(json_info_photo)
                    break
        if not errors_list:
            print(f'Загрузка {len(photos_info)} фото прошла успешно.')
        else:
            print(f'Успешно загружено {len(photos_info) - len(errors_list)} фото.')
            pprint(f'Произошла неизвестная ошибка при загрузке следующих файлов: {errors_list}')
        create_json_info(json_value)


def token_parser():
    """Parse tokens for VK and Yandex.Disk."""
    config = configparser.ConfigParser()
    config.read('settings.ini')
    tokens = {}
    token_vk = config['VK_YDisk_data']['token_vk']
    tokens['token_vk'] = token_vk
    token_yandex_disk = config['VK_YDisk_data']['token_yandex_disk']
    tokens['token_yandex_disk'] = token_yandex_disk
    return tokens


def start_program():
    """Enter data and start program."""
    while True:
        try:
            vk_id = int(input('Введите id пользователя ВКонтакте: '))
            photos_quantity = 5
            question_by_default_quantity = input(
                'По умолчанию сохранется 5 фото. Хотите сохранить другое количество? '
                '(Y - да, Enter - нет): ')
            if question_by_default_quantity == 'Y':
                photos_quantity = int(input('Введите необходимое количество фото для сохранения: '))
            album = 'profile'
            question_by_default_album = input('По умолчанию для сохранения выбраны фото профиля. '
                                              'Хотите выбрать другой альбом? (Y - да, Enter - нет): ')
            if question_by_default_album == 'Y':
                album = input('Введите идентификатор альбома '
                              '(служебные: wall - фото со стены, saved - сохраненные фото): ')
            vk_client = VkToYDiscAPISaver(token_parser(), vk_id, photos_quantity, album)
            vk_client.save_photos()
        except requests.exceptions.MissingSchema:
            print('Введен некорректный токен Яндекс.Диска. Проверьте и повторите попытку.')
        except ValueError:
            print('id это цифровой идентификатор пользователя, а не никнейм.')
        except AttributeError:
            print('Такого пользователя (альбома) не существует. Попробуйте еще раз.')
        except Exception:
            print('Произошла неизвестная ошибка. Попробуйте позже')
            break
        else:
            break


def create_json_info(data_for_creating):
    """Create a .jsol-file with results of uploading (name and size type of each photo)."""
    with open('uploaded_photos_info.json', 'w') as file:
        json.dump(data_for_creating, file)


if __name__ == '__main__':
    start_program()
