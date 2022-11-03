import os
import shutil
from blocks_parser import Parser

# изменить на True для сохранения фотографий блоков
debug = False
# изменить путь до firefox.exe при необходимости
firefox_path = r'C:\Program Files\Mozilla Firefox\firefox.exe'
# ссылка на сайт для анализа
website_url = "http://www.laardo.ru"

if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.realpath(__file__))
    screenshot_dir = None
    if debug:
        screenshot_dir = os.path.join(output_dir, "screenshots")
        if os.path.exists(screenshot_dir):
            shutil.rmtree(screenshot_dir)
        os.makedirs(screenshot_dir)
    parser = Parser(firefox_path=firefox_path, debug=debug, screenshot_path=screenshot_dir)
    df = parser.parse(website_url)
    df.to_excel(output_dir + "/analysis.xlsx")