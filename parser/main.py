import os
import shutil
from blocks_parser import Parser
import pandas as pd
import traceback

# изменить на True для сохранения фотографий блоков
debug = True
# изменить путь до firefox.exe при необходимости
firefox_path = r'C:\Program Files\Mozilla Firefox\firefox.exe'
# ссылка на сайт для анализа
website_url = "https://gb.ru"

if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.realpath(__file__))
    screenshot_dir = None
    if debug:
        screenshot_dir = os.path.join(output_dir, "screenshots")
        if os.path.exists(screenshot_dir):
            shutil.rmtree(screenshot_dir)
        os.makedirs(screenshot_dir)

    urls = pd.read_excel(output_dir + "/urls.xlsx")
    parser = Parser(firefox_path=firefox_path, debug=debug, screenshot_path=screenshot_dir)
    
    # website_url: str = url["urls"]
    print(website_url)
    df = parser.parse(website_url)
    df.to_excel(screenshot_dir + "/analysis.xlsx")
    
    # for i, url in urls.iterrows():
    #     if os.path.exists(screenshot_dir):
    #         shutil.rmtree(screenshot_dir)
    #     os.makedirs(screenshot_dir)
    #     try:
    #         website_url: str = url["urls"]
    #         print(website_url)
    #         df = parser.parse(website_url)
    #         df.to_excel(screenshot_dir + "/analysis.xlsx")
    #         shutil.make_archive(output_dir + f'/{website_url.replace("https://", "")}', "zip", screenshot_dir)
    #     except Exception:
    #         print("                   Error: ", traceback.format_exc())
    #         continue