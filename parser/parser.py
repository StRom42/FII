import io
from math import log
import shutil
from typing import List, Tuple
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os
import re
from PIL import Image


from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.color import Color


class Parser:
    def __init__(self, screenshot_path, firefox_path: str = r'C:\Program Files\Mozilla Firefox\firefox.exe', debug=True):
        self.driver = webdriver.Firefox(
            options=self.get_options(firefox_path=firefox_path), service=self.get_service())
        self.screenshot_path = screenshot_path
        self.debug = debug
        self.maps_regex = re.compile(
            "(.+\/www.google.com\/maps\/.+)|(.+\/yandex.ru\/map\/.+)")
        self.header_regex = re.compile("header")
        self.font_regex = re.compile("(\d+)[\w\%]{1,3}")
        self.title_regex = re.compile(".*[Tt]itle.*")
        self.not_input_regex = re.compile("^((?![Ii]nput).)*$")

    def parse(self, url: str) -> pd.DataFrame:
        self.driver.get(url)
        self.driver.maximize_window()
        self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight)")
        self.driver.execute_script("window.scrollBy(0, 0)")

        self.page_height = self.get_page_height()
        self.page_width = self.get_page_width()

        self.min_block_height = 30
        self.min_block_width = 0.7 * self.page_width

        if self.debug:
            print(self.page_width, self.page_height)

        elements_data = self.collect_elements_data()

        data = {
            "x": [],
            "y": [],
            "width": [],
            "height": [],
            "images_number": [],
            "buttons_number": [],
            "different_buttons_number": [],
            "links_number": [],
            "max_font_size": [],
            "words_number": [],
            "background_color": [],
            "contains_map": [],
            "contains_buttons": [],
            "contains_forms": [],
            "contains_head_texts": [],
            "contains_slider": [],
            "contains_images": [],
        }

        semantic_blocks = elements_data.loc[elements_data["type"].isin(
            ["head_text", "colored_block"])]
        semantic_blocks = semantic_blocks.sort_values("y")
        semantic_blocks["counter"] = 1
        semantic_blocks = semantic_blocks.groupby('y').agg({
            "type": "first",
            "x": "min",
            "width": "max",
            "height": "max",
            "background_color": "first",
            "counter": "count"
        })
        semantic_blocks = semantic_blocks[semantic_blocks["counter"] == 1]
        semantic_blocks = semantic_blocks.reset_index()

        if self.debug:
            print(semantic_blocks.to_string())

        accum_block = semantic_blocks.iloc[0].to_dict()
        accum_block["height"] = 0
        accum_block["blocks_count"] = 1
        accum_block["y_end"] = self.page_height
        
        for i, current_block in semantic_blocks.iterrows():
            print(i)

            next_block = None
            if i == (semantic_blocks.shape[0] - 1):
                next_block = {
                    "x": 0,
                    "y": self.page_height,
                    "height": 0,
                    "width": 0,
                    "background_color": None,
                    "type": "colored_block"
                }
            else:
                next_block = semantic_blocks.iloc[i + 1].to_dict()

            if (current_block["type"] == "colored_block" and next_block["type"] == "head_text") \
                and current_block["height"] > self.min_block_height:
                    accum_block["y_end"] = accum_block["y"] + current_block["height"]
            
            if next_block["y"] - accum_block["y"] < self.min_block_height:
                continue
            
            elems_between = elements_data[(~elements_data["type"].isin(["head_text", "colored_block"])) \
                                                  & elements_data["y"].between(accum_block["y"], next_block["y"] - 2)]
            if self.debug:
                print("Elems between", elems_between.shape[0])
            if elems_between.shape[0] < 1:
                continue

            accum_block["height"] = next_block["y"] - accum_block["y"]

            if current_block["background_color"] == next_block["background_color"] \
                    and i != (semantic_blocks.shape[0] - 1) \
                        and not (current_block["type"] == "head_text" and next_block["type"] == "head_text"):
                accum_block["blocks_count"] += 1
                accum_block["background_color"] = current_block["background_color"]
            else:                
                if accum_block["blocks_count"] < 2 \
                        and accum_block["height"] > current_block["height"] \
                                and (current_block["type"] == "colored_block" and next_block["type"] == "colored_block"):
                    self.collect_block_data(elements_data, data,
                                            0, accum_block["y"],
                                            self.page_width, accum_block["y"] + current_block["height"],
                                            current_block["background_color"])
                    self.collect_block_data(elements_data, data,
                                            0, accum_block["y"] + current_block["height"],
                                            self.page_width, accum_block["y"] + accum_block["height"],
                                            accum_block["background_color"])
                else:
                    self.collect_block_data(elements_data, data,
                                            0, accum_block["y"],
                                            self.page_width, accum_block["y"] + accum_block["height"],
                                            accum_block["background_color"])
                accum_block["y"] = next_block["y"]
                accum_block["y_end"] = next_block["y"] + next_block["height"]
                accum_block["height"] = 0
                accum_block["blocks_count"] = 1
                
        df = pd.DataFrame(data)
        return df

    def collect_block_data(self, elements_data: dict, data: dict, x_begin: float,
                           y_begin: float, x_end: float, y_end: float, background_color: str):

        if self.debug:
            block_shot_path = os.path.join(
                self.screenshot_path, f"{y_begin}-{y_end}.png")
            print(block_shot_path)
            self.take_screenshot(block_shot_path, x_begin, y_begin,
                                 x_end - x_begin, (y_end - y_begin))

        data["x"].append(x_begin)
        data["y"].append(y_begin)
        data["width"].append(x_end - x_begin)
        data["height"].append(y_end - y_begin)

        images_number = elements_data.loc[(elements_data["type"] == "image")
                                          & (elements_data["y"].between(y_begin, y_end))].shape[0]
        data["images_number"].append(images_number)
        data["contains_images"].append(images_number > 0)

        data["max_font_size"].append(
            self.get_max_font_size(y_begin, y_end))

        data["words_number"].append(
            self.get_words_number(y_begin, y_end))

        maps = elements_data.loc[(elements_data["type"] == "map")
                                 & (elements_data["y"].between(y_begin, y_end))]
        data["contains_map"].append(not maps.empty)

        buttons_number = elements_data.loc[(elements_data["type"] == "button")
                                           & (elements_data["y"].between(y_begin, y_end))].shape[0]
        links_number = elements_data.loc[(elements_data["type"] == "link")
                                         & (elements_data["y"].between(y_begin, y_end))].shape[0]
        data["contains_buttons"].append(buttons_number + links_number > 0)
        data["buttons_number"].append(buttons_number)
        data["links_number"].append(links_number)

        forms = elements_data.loc[(elements_data["type"] == "form")
                                  & (elements_data["y"].between(y_begin, y_end))]
        data["contains_forms"].append(not forms.empty)

        head_texts = elements_data.loc[(elements_data["type"] == "head_text")
                                       & (elements_data["y"].between(y_begin, y_end))]
        data["contains_head_texts"].append(not head_texts.empty)

        sliders = elements_data.loc[(elements_data["type"] == "slider")
                                    & (elements_data["y"].between(y_begin, y_end))]
        data["contains_slider"].append(not sliders.empty)

        all_buttons = elements_data.loc[(elements_data["type"] == "button")
                                        & (elements_data["y"].between(y_begin, y_end))]
        different_buttons_number = all_buttons.groupby(
            "text").first().shape[0]
        data["different_buttons_number"].append(different_buttons_number)

        data["background_color"].append(background_color)

    def collect_elements_data(self) -> pd.DataFrame:

        elements_data = {
            "type": [],
            "x": [],
            "y": [],
            "width": [],
            "height": [],
            "text": [],
            "background_color": []
        }

        imgs = self.get_imgs(self.driver)
        self.collect_coords_data(elements_data, imgs, "image")

        heads = self.get_heads(self.driver)
        self.collect_coords_data(elements_data, heads, "head_text")

        buttons = self.get_buttons(self.driver)
        self.collect_coords_data(elements_data, buttons, "button")

        links = self.get_links(self.driver)
        self.collect_coords_data(elements_data, links, "link")

        forms = self.get_forms(self.driver)
        self.collect_coords_data(elements_data, forms, "form")

        maps = self.get_map(self.driver)
        self.collect_coords_data(elements_data, maps, "map")

        colored_blocks = self.get_colored_blocks(self.driver)
        self.collect_coords_data(
            elements_data, colored_blocks, "colored_block")

        sliders = self.get_sliders(self.driver)
        self.collect_coords_data(elements_data, sliders, "slider")

        df = pd.DataFrame(elements_data)
        return df

    def collect_coords_data(self, data: dict, elements: List[WebElement], type: str):
        for element in elements:
            data["type"].append(type)
            data["x"].append(self.get_x(element))
            data["y"].append(self.get_y(element))
            data["width"].append(self.get_width(element))
            data["height"].append(self.get_height(element))
            if type in ["button", "link"]:
                data["text"].append(element.text)
            else:
                data["text"].append(None)

            if type in ["colored_block", "head_text"]:
                data["background_color"].append(
                    self.get_background_color(element))
            else:
                data["background_color"].append(None)

    def get_blocks(self, block: WebElement) -> List[WebElement]:
        headers = block.find_elements(By.CSS_SELECTOR, 'div[id*="header"]') + \
            block.find_elements(By.CSS_SELECTOR, 'div[class*="header"') + \
            block.find_elements(By.CSS_SELECTOR, 'header')

        elements = block.find_elements(By.TAG_NAME, "div")

        footers = block.find_elements(By.CSS_SELECTOR, 'div[id*="footer"') + \
            block.find_elements(By.CSS_SELECTOR, 'div[class*="footer"') + \
            block.find_elements(By.CSS_SELECTOR, 'footer')
        blocks = elements + headers + footers
        blocks = [elem for elem in blocks if elem.is_displayed()]
        return blocks

    def take_screenshot(self, path: str, x: float, y: float, width: float, height: float) -> None:
        data = self.driver.get_full_page_screenshot_as_png()
        screenshot = Image.open(io.BytesIO(data))
        area = (x, y, x + width, min(y + height, self.page_height))
        print(area)
        block_screen = screenshot.crop(area)
        block_screen.save(path)

    def get_colored_blocks(self, block: WebElement) -> List[WebElement]:
        blocks = self.get_blocks(block)
        all_blocks = [[self.get_y(t_block), t_block] for t_block in blocks]
        all_blocks.sort(key=lambda x: x[0])
        colored_blocks = []
        current_block = None
        for colored_block in all_blocks:
            current_block = colored_block[1]
            cur_color = self.get_background_color(current_block)
            if (not cur_color) \
                or (self.get_height(current_block) < self.min_block_height) \
                    or (self.get_width(current_block) < self.min_block_width) \
                    or not current_block.is_displayed():
                continue

            colored_blocks.append(current_block)
        return colored_blocks

    def get_background_image(self, block: WebElement) -> str:
        back_image = block.value_of_css_property("background-image")
        if back_image == "" or back_image == "none":
            return None
        else:
            return back_image

    def get_heads(self, block: WebElement) -> List[WebElement]:
        tags = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', "h6"]
        heads = ['h1', 'h2', 'h3', 'h4', 'h5', "h6"]
        elements = []
        for tag in tags:
            elements += [[self.get_font_size(elem), elem] for elem in block.find_elements(By.CSS_SELECTOR, f'{tag}')
                         if elem.is_displayed()]
        pair = max(elements, key=lambda x: x[0])
        min_font_size = pair[0] * 0.93
        elements = [elem[1] for elem in elements if elem[1].tag_name in heads or (elem[0] > min_font_size \
            or (self.title_regex.match(elem[1].get_attribute('class')) != None and self.not_input_regex.fullmatch(elem[1].get_attribute('class'))))]
        return elements

    def get_forms(self, block: WebElement) -> List[WebElement]:
        forms = block.find_elements(By.TAG_NAME, "form")
        forms += block.find_elements(By.CSS_SELECTOR, 'div[class*="form"]')
        forms += block.find_elements(By.CSS_SELECTOR, 'div[id*="form"]')
        forms = [elem for elem in forms if elem.is_displayed()]
        return forms

    def get_sliders(self, block: WebElement) -> List[WebElement]:
        sliders = self.driver.find_elements(
            By.CSS_SELECTOR, 'div[class*="slider"]')
        sliders = [elem for elem in sliders if elem.is_displayed()]
        return sliders

    def get_parent(self, element: WebElement) -> WebElement:
        parent = element.find_element(By.XPATH, "..")
        print(parent.tag_name)
        return parent

    def get_page_height(self) -> float:
        page = self.driver.find_element(By.TAG_NAME, "body")
        return page.size['height']

    def get_page_width(self) -> float:
        page = self.driver.find_element(By.TAG_NAME, "body")
        return page.size['width']

    def get_options(self, firefox_path: str) -> FirefoxOptions:
        options = FirefoxOptions()
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")  # linux only
        options.add_argument("--headless")
        # options.set_preference('permissions.default.image', 2)
        # options.set_preference(
        #     'dom.ipc.plugins.enabled.libflashplayer.so', 'false')
        options.binary_location = firefox_path
        return options

    def get_service(self,) -> Service:
        gecko = os.path.normpath(os.path.join(
            os.path.dirname(__file__), 'geckodriver.exe'))
        service = Service(executable_path=gecko,)
        return service

    def get_x(self, element: WebElement) -> float:
        x = element.rect["x"]
        return abs(x)

    def get_y(self, element: WebElement) -> float:
        y = element.rect["y"]
        return abs(y)

    def get_width(self, element: WebElement) -> float:
        width = element.size['width']
        return width

    def get_height(self, element: WebElement) -> float:
        height = element.size['height']
        return height

    def get_buttons(self, block: WebElement) -> List[WebElement]:
        buttons = block.find_elements(By.TAG_NAME, "button")
        buttons += block.find_elements(By.CSS_SELECTOR,
                                       'input[type*="button"]')
        buttons = [button for button in buttons if button.is_displayed()]
        return buttons

    def get_links(self, block: WebElement) -> List[WebElement]:
        links = block.find_elements(By.TAG_NAME, "a")
        links = [elem for elem in links if elem.is_displayed()]
        return links

    def get_map(self, block: WebElement) -> List[WebElement]:
        maps = block.find_elements(By.CSS_SELECTOR, "ymaps")
        maps += block.find_elements(By.ID, "map")
        maps += block.find_elements(By.CSS_SELECTOR, 'div[class*="map"]')
        iframes = block.find_elements(By.TAG_NAME, "iframe")
        maps += [iframe for iframe in iframes if self.maps_regex.search(
            iframe.get_attribute("src"))]
        maps = [elem for elem in maps if elem.is_displayed()]
        return maps

    def get_words_number(self, y_min: float, y_max: float, x_min: float = 0, x_max: float = float("inf")) -> int:
        elements = [elem for elem in self.driver.find_elements(By.CSS_SELECTOR, "*")
                    if y_min <= self.get_y(elem) <= y_max and elem.is_displayed()]
        words_number = 0
        for element in elements:
            words_number += len(element.text.split())
        return words_number
    
    def get_font_size(self, element: WebElement):
        font_size = element.value_of_css_property("font-size")
        match = self.font_regex.search(font_size)
        font_size_value = int(match.group(1)) if match else 0
        return font_size_value

    def get_max_font_size(self, y_min: float, y_max: float, x_min: float = 0, x_max: float = float("inf")) -> int:
        tags = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'table']
        elements = []
        for tag in tags:
            elements += [elem for elem in self.driver.find_elements(By.CSS_SELECTOR, f'{tag}')
                         if y_min <= self.get_y(elem) <= y_max and elem.is_displayed()]
        max_font_size = 0
        for element in elements:
            font_size_value = self.get_font_size(element)
            max_font_size = max(int(font_size_value), max_font_size)
        return max_font_size

    def get_background_color(self, block: WebElement) -> str:
        value = block.value_of_css_property("background-color")
        color = Color.from_string(value)
        if color.alpha == "0":
            return None
        return color.hex

    def get_imgs(self, block: WebElement) -> List[WebElement]:
        imgs = block.find_elements(By.TAG_NAME, "img")
        img_classes = ["img", "Image", "image", "Img"]
        for img_class in img_classes:
            imgs += block.find_elements(By.CSS_SELECTOR,
                                               "div[class*='{}']".format(img_class))
        imgs = [elem for elem in imgs if elem.is_displayed()]
        return imgs


if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.realpath(__file__))
    screenshot_dir = os.path.join(output_dir, "screenshots")
    if os.path.exists(screenshot_dir):
        shutil.rmtree(screenshot_dir)
    os.makedirs(screenshot_dir)
    parser = Parser(screenshot_dir)
    df = parser.parse("http://www.laardo.ru")
    df.to_excel(output_dir + "/analysis.xlsx")
